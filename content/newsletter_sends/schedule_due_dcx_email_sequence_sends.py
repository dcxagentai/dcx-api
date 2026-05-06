"""
CONTEXT:
This file schedules due DCX email sequences into owned send rows.
It exists so MVP sequences use DCX's database, schedules, and Resend dispatcher instead of relying
on Resend Automations private-alpha workflow state.

FLOW/SYSTEM:
- Admin marks a sequence live and optionally sets scheduled_launch_at_ts_ms.
- A Render cron/background job calls this capability.
- The capability converts active sequence steps into ordinary stephen_dcx_emails_sends rows.
- The existing newsletter dispatcher sends those rows through Resend when each step is due.

CONTRACT:
  preconditions:
    - The configured database is reachable.
    - Usage/activity/sequence delivery migration has been applied.
  postconditions:
    - Claims at most one due live scheduled sequence.
    - Creates active user enrollments.
    - Creates one scheduled send row per active sequence step.
    - Creates recipient snapshots and tracked links for each step send.
    - Clears scheduled_launch_at_ts_ms so the sequence is not scheduled twice.
  side_effects:
    - writes stephen_dcx_email_sequence_enrollments
    - writes stephen_dcx_email_sequence_step_deliveries
    - writes stephen_dcx_emails_sends, recipients, and links
    - updates stephen_dcx_emails_sequences
  idempotent: false
  retry_safe: true
  async: false
  idempotency_key: sequence_id plus unique active enrollment/step delivery constraints
  locks:
    - row-level lock on one due sequence via FOR UPDATE SKIP LOCKED
  contention_strategy: parallel workers skip locked sequences and unique indexes prevent duplicate active user enrollments

NARRATIVE:
  WHY this exists:
    - MVP sequences should be basic and owned by DCX: Postgres rows, Render cron, existing Resend send adapter.
  WHEN TO USE it:
    - Use it from a scheduled worker before calling the ordinary send dispatcher.
  WHEN NOT TO USE it:
    - Do not use it for transactional auth emails or third-party workflow automation.
  WHAT CAN GO WRONG:
    - A sequence can have no active steps, no eligible users, or missing migrations.
  WHAT COMES NEXT:
    - Add per-trigger enrollments, unsubscribe scopes, retry dashboards, and per-recipient step progression.

TESTS:
  - compile smoke; integration coverage can be added with the sequence-delivery migration.

ERRORS:
  - API_DCX_EMAIL_SEQUENCE_SCHEDULE_FAILED:
      suggested_action: Inspect the due sequence and retry after database health is restored.
      common_causes:
        - missing migration
        - database unavailable
      recovery_steps:
        - Run migrations.
        - Retry the cron job.
      retry_safe: true
      what_changed:
        - a sequence may have partially scheduled rows if the transaction boundary is not trusted
      rollback_needed: inspect_if_partial_commit_suspected
      rollback_operation: inspect sequence send rows before replay

CODE:
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any, Callable

import psycopg2

from content.newsletter_sends.build_dcx_emails_sends_links_from_newsletter_markdown import (
    build_dcx_emails_sends_links_from_newsletter_markdown,
)
from storage.db_config import DB_CONFIG


def schedule_due_dcx_email_sequence_sends_capability(
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    tracking_token_provider: Callable[[], str] | None = None,
) -> dict:
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()
    build_tracking_token = tracking_token_provider or _build_tracking_token

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, sequence_key, audience_type, COALESCE(scheduled_launch_at_ts_ms, %s)
                    FROM stephen_dcx_emails_sequences
                    WHERE is_live = TRUE
                      AND trigger_type = 'scheduled_launch'
                      AND COALESCE(scheduled_launch_at_ts_ms, %s) <= %s
                    ORDER BY COALESCE(scheduled_launch_at_ts_ms, %s) ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """,
                    (now_ts_ms, now_ts_ms, now_ts_ms, now_ts_ms),
                )
                sequence_row = cursor.fetchone()
                if sequence_row is None:
                    return {"status": "idle", "scheduled_sequence": None}

                sequence_id = sequence_row[0]
                sequence_key = sequence_row[1]
                sequence_audience_type = sequence_row[2]
                sequence_launch_ts_ms = sequence_row[3]

                cursor.execute(
                    """
                    SELECT step.id, step.step_key, step.step_order, step.source_email_id, step.delay_minutes_from_trigger,
                           email.email_key, email.email_subject, email.email_body
                    FROM stephen_dcx_emails_sequence_steps step
                    INNER JOIN stephen_dcx_emails email
                      ON email.id = step.source_email_id
                    WHERE step.sequence_id = %s
                      AND step.is_active = TRUE
                    ORDER BY step.step_order ASC, step.id ASC
                    """,
                    (sequence_id,),
                )
                step_rows = cursor.fetchall()
                if not step_rows:
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_emails_sequences
                        SET scheduled_launch_at_ts_ms = NULL,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (now_ts_ms, sequence_id),
                    )
                    return {"status": "scheduled", "scheduled_sequence": {"sequence_id": sequence_id, "send_count": 0}}

                cursor.execute(
                    """
                    SELECT user_row.id, primary_email.normalized_value, user_row.email_communication_preference, user_row.user_role
                    FROM stephen_dcx_users user_row
                    LEFT JOIN LATERAL (
                        SELECT normalized_value, is_verified
                        FROM stephen_dcx_users_contact_methods
                        WHERE user_id = user_row.id
                          AND contact_type = 'email'
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) primary_email ON TRUE
                    WHERE user_row.account_status = 'confirmed'
                      AND primary_email.normalized_value IS NOT NULL
                      AND primary_email.is_verified = TRUE
                      AND user_row.email_communication_preference IN ('newsletters', 'all_email')
                      AND (
                        %s IN ('all_email', 'newsletters')
                        OR (%s = 'admins' AND user_row.user_role = 'admin')
                        OR (%s = 'devs' AND user_row.user_role = 'dev')
                        OR (%s = 'shareholders' AND user_row.user_role IN ('shareholder', 'shareholders'))
                      )
                    ORDER BY user_row.id ASC
                    """,
                    (
                        sequence_audience_type,
                        sequence_audience_type,
                        sequence_audience_type,
                        sequence_audience_type,
                    ),
                )
                user_rows = cursor.fetchall()

                enrollment_ids_by_user_id: dict[int, int] = {}
                for user_row in user_rows:
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_email_sequence_enrollments (
                            sequence_id,
                            user_id,
                            enrollment_status,
                            current_step_order,
                            started_at_ts_ms
                        )
                        VALUES (%s, %s, 'active', 0, %s)
                        ON CONFLICT DO NOTHING
                        RETURNING id
                        """,
                        (sequence_id, user_row[0], now_ts_ms),
                    )
                    inserted_row = cursor.fetchone()
                    if inserted_row is not None:
                        enrollment_ids_by_user_id[user_row[0]] = inserted_row[0]
                    else:
                        cursor.execute(
                            """
                            SELECT id
                            FROM stephen_dcx_email_sequence_enrollments
                            WHERE sequence_id = %s
                              AND user_id = %s
                              AND enrollment_status = 'active'
                            LIMIT 1
                            """,
                            (sequence_id, user_row[0]),
                        )
                        existing_row = cursor.fetchone()
                        if existing_row is not None:
                            enrollment_ids_by_user_id[user_row[0]] = existing_row[0]

                send_count = 0
                recipient_count = 0
                for step_row in step_rows:
                    scheduled_send_at_ts_ms = sequence_launch_ts_ms + int(step_row[4] or 0) * 60 * 1000
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_emails_sends (
                            source_email_id,
                            email_key_snapshot,
                            send_kind,
                            source_sequence_id,
                            source_sequence_step_id,
                            send_status,
                            send_audience_type,
                            scheduled_send_at_ts_ms,
                            send_summary_json
                        )
                        VALUES (%s, %s, 'sequence', %s, %s, 'scheduled', %s, %s, %s::jsonb)
                        RETURNING id
                        """,
                        (
                            step_row[3],
                            step_row[5],
                            sequence_id,
                            step_row[0],
                            sequence_audience_type,
                            scheduled_send_at_ts_ms,
                            json.dumps(
                                {
                                    "sequence_key": sequence_key,
                                    "step_key": step_row[1],
                                    "sequence_audience_type": sequence_audience_type,
                                }
                            ),
                        ),
                    )
                    email_send_id = cursor.fetchone()[0]
                    send_count += 1

                    for link_row in build_dcx_emails_sends_links_from_newsletter_markdown(step_row[7]):
                        cursor.execute(
                            """
                            INSERT INTO stephen_dcx_emails_sends_links (
                                email_send_id,
                                resolved_email_id,
                                original_url,
                                tracking_token,
                                link_label
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                email_send_id,
                                step_row[3],
                                link_row["original_url"],
                                build_tracking_token(),
                                link_row["link_label"],
                            ),
                        )

                    for user_row in user_rows:
                        enrollment_id = enrollment_ids_by_user_id.get(user_row[0])
                        if enrollment_id is None:
                            continue
                        cursor.execute(
                            """
                            INSERT INTO stephen_dcx_emails_sends_recipients (
                                email_send_id,
                                user_id,
                                resolved_email_id,
                                recipient_email_snapshot,
                                email_communication_preference_snapshot,
                                delivery_decision,
                                delivery_status
                            )
                            VALUES (%s, %s, %s, %s, %s, 'send', 'pending')
                            """,
                            (email_send_id, user_row[0], step_row[3], user_row[1], user_row[2]),
                        )
                        cursor.execute(
                            """
                            INSERT INTO stephen_dcx_email_sequence_step_deliveries (
                                enrollment_id,
                                sequence_id,
                                sequence_step_id,
                                email_send_id,
                                user_id,
                                scheduled_send_at_ts_ms,
                                delivery_status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, 'scheduled')
                            ON CONFLICT DO NOTHING
                            """,
                            (enrollment_id, sequence_id, step_row[0], email_send_id, user_row[0], scheduled_send_at_ts_ms),
                        )
                        recipient_count += 1

                cursor.execute(
                    """
                    UPDATE stephen_dcx_emails_sequences
                    SET scheduled_launch_at_ts_ms = NULL,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, sequence_id),
                )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_EMAIL_SEQUENCE_SCHEDULE_FAILED") from exc

    return {
        "status": "scheduled",
        "scheduled_sequence": {
            "sequence_id": sequence_id,
            "sequence_key": sequence_key,
            "send_count": send_count,
            "recipient_count": recipient_count,
        },
    }


def _read_current_timestamp_ms() -> int:
    return int(time.time() * 1000)


def _build_tracking_token() -> str:
    return secrets.token_urlsafe(18)
