"""
CONTEXT:
This file claims and dispatches one due DCX newsletter send through Resend.
It exists so a background worker can turn prepared newsletter send rows into real provider sends
without mixing queue orchestration into admin HTTP routes.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable
from urllib.parse import quote

import psycopg2

from apis.resend.send_email import send_email_batch_via_resend
from content.newsletter_sends.append_dcx_email_preferences_footer_to_newsletter_email_bodies import (
    append_dcx_email_preferences_footer_to_newsletter_email_bodies,
)
from content.newsletter_sends.render_dcx_newsletter_markdown_to_email_bodies import (
    render_dcx_newsletter_markdown_to_email_bodies,
)
from storage.db_config import DB_CONFIG


def dispatch_one_due_dcx_newsletter_send_via_resend_capability(
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    send_email: Callable[[dict], dict] | None = None,
    send_email_batch: Callable[[list[dict]], list[dict]] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
        - Resend configuration is present when a due send exists and recipient delivery is attempted.
      postconditions:
        - Claims at most one due newsletter send row in `scheduled` state.
        - Attempts provider delivery for each pending `send` recipient on that send.
        - Updates recipient delivery rows with sent/failed provider outcomes.
        - Updates the parent send row with final status and dispatch summary.
      side_effects:
        - updates one send row in `stephen_dcx_emails_sends`
        - updates one or more recipient rows in `stephen_dcx_emails_sends_recipients`
        - sends one or more provider emails through Resend
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: none
      locks:
        - row-level lock on one due `stephen_dcx_emails_sends` row via `FOR UPDATE SKIP LOCKED`
      contention_strategy: each worker claims at most one due send row and skips already-locked rows so parallel workers do not double-dispatch the same send

    NARRATIVE:
      WHY this exists:
        - Prepared newsletter sends are now real operational rows and need one worker-safe dispatch step.
      WHEN TO USE it:
        - Use it from a background worker loop that repeatedly asks for the next due newsletter send.
      WHEN NOT TO USE it:
        - Do not use it from browser-facing routes.
        - Do not use it for transactional emails or sequence sends yet.
      WHAT CAN GO WRONG:
        - No due send may exist.
        - Resend may reject a recipient send.
        - A partially failing send may produce mixed sent/failed recipient outcomes.
      WHAT COMES NEXT:
        - Later webhook ingestion can upgrade `sent` rows to `delivered`, `bounced`, or `complained`.

    TESTS:
      - returns_idle_when_no_due_newsletter_send_exists
      - dispatches_due_newsletter_send_and_updates_recipient_rows
      - marks_parent_send_failed_when_any_recipient_send_fails

    ERRORS:
      - API_DCX_NEWSLETTER_SEND_DISPATCH_FAILED:
          suggested_action: Inspect the newsletter send row and retry once the backend or provider issue is resolved.
          common_causes:
            - database unavailable
            - query failure
            - unexpected provider adapter failure outside per-recipient handling
          recovery_steps:
            - Verify database connectivity.
            - Inspect the claimed send row status.
            - Retry the worker once the backend is healthy.
          retry_safe: true
          what_changed:
            - one send row may already be marked `sending`
            - some recipient rows may already be marked `sent` or `failed`
          rollback_needed: false
          rollback_operation:
            - none automatic; inspect the claimed send and recipient rows before any manual replay

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    read_current_timestamp_ms = current_timestamp_ms_provider or _read_current_timestamp_ms
    send_newsletter_email_batch = (
        send_email_batch
        or (
            (lambda drafts: [send_email(draft) for draft in drafts])
            if send_email is not None
            else send_email_batch_via_resend
        )
    )
    current_timestamp_ms = read_current_timestamp_ms()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        email_send.id,
                        email_send.email_key_snapshot
                    FROM stephen_dcx_emails_sends AS email_send
                    WHERE email_send.send_kind IN ('newsletter', 'sequence')
                      AND email_send.send_status = 'scheduled'
                      AND email_send.scheduled_send_at_ts_ms <= %s
                    ORDER BY email_send.scheduled_send_at_ts_ms ASC, email_send.id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """,
                    (current_timestamp_ms,),
                )
                due_send_row = cursor.fetchone()

                if due_send_row is None:
                    return {
                        "status": "idle",
                        "dispatched_send": None,
                    }

                email_send_id = due_send_row[0]

                cursor.execute(
                    """
                    UPDATE stephen_dcx_emails_sends
                    SET send_status = 'sending',
                        send_started_at_ts_ms = COALESCE(send_started_at_ts_ms, %s),
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        current_timestamp_ms,
                        current_timestamp_ms,
                        email_send_id,
                    ),
                )

                cursor.execute(
                    """
                    SELECT
                        link_row.original_url,
                        link_row.tracking_token
                    FROM stephen_dcx_emails_sends_links AS link_row
                    WHERE link_row.email_send_id = %s
                    ORDER BY link_row.id ASC
                    """,
                    (email_send_id,),
                )
                link_rows = cursor.fetchall()
                tracked_url_by_original_url = {
                    link_row[0]: _build_dcx_email_send_tracking_redirect_url(link_row[1])
                    for link_row in link_rows
                }

                cursor.execute(
                    """
                    SELECT
                        recipient.id,
                        recipient.user_id,
                        recipient.recipient_email_snapshot,
                        recipient.resolved_email_id,
                        email_row.email_subject,
                        email_row.email_body,
                        ai_translation_job.id
                    FROM stephen_dcx_emails_sends_recipients AS recipient
                    INNER JOIN stephen_dcx_emails AS email_row
                      ON email_row.id = recipient.resolved_email_id
                    LEFT JOIN LATERAL (
                        SELECT translation_job.id
                        FROM stephen_dcx_ai_translation_jobs AS translation_job
                        WHERE translation_job.target_row_id = email_row.id
                          AND translation_job.job_status = 'completed'
                          AND (
                            (email_row.email_type = 'newsletter' AND translation_job.entity_kind = 'newsletter')
                            OR (email_row.email_type <> 'newsletter' AND translation_job.entity_kind = 'email')
                          )
                        ORDER BY translation_job.id DESC
                        LIMIT 1
                    ) ai_translation_job
                      ON TRUE
                    WHERE recipient.email_send_id = %s
                      AND recipient.delivery_decision = 'send'
                      AND recipient.delivery_status = 'pending'
                    ORDER BY recipient.id ASC
                    """,
                    (email_send_id,),
                )
                recipient_rows = cursor.fetchall()

                sent_recipient_count = 0
                failed_recipient_count = 0
                failed_recipient_reasons: list[dict[str, Any]] = []

                recipient_delivery_drafts: list[dict[str, Any]] = []
                for recipient_row in recipient_rows:
                    recipient_id = recipient_row[0]
                    recipient_user_id = recipient_row[1]
                    recipient_email = recipient_row[2]
                    rendered_bodies = render_dcx_newsletter_markdown_to_email_bodies(
                        markdown_text=recipient_row[5],
                        tracked_url_by_original_url=tracked_url_by_original_url,
                    )
                    if recipient_row[6] is not None:
                        rendered_bodies = _append_ai_translated_label_to_email_bodies(rendered_bodies)
                    rendered_bodies = append_dcx_email_preferences_footer_to_newsletter_email_bodies(
                        rendered_bodies=rendered_bodies,
                        user_id=recipient_user_id,
                        recipient_email=recipient_email,
                        current_timestamp_ms_provider=read_current_timestamp_ms,
                    )

                    cursor.execute(
                        """
                        UPDATE stephen_dcx_emails_sends_recipients
                        SET delivery_status = 'sending',
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            current_timestamp_ms,
                            recipient_id,
                        ),
                    )

                    recipient_delivery_drafts.append(
                        {
                            "recipient_id": recipient_id,
                            "recipient_email": recipient_email,
                            "subject": recipient_row[4],
                            "text_body": rendered_bodies["text_body"],
                            "html_body": rendered_bodies["html_body"],
                        }
                    )

                for recipient_delivery_draft_chunk in _chunk_dcx_newsletter_delivery_drafts(recipient_delivery_drafts, 100):
                    try:
                        provider_summaries = send_newsletter_email_batch(recipient_delivery_draft_chunk)
                        if len(provider_summaries) != len(recipient_delivery_draft_chunk):
                            raise RuntimeError("API_DCX_RESEND_BATCH_RESPONSE_INVALID")
                    except RuntimeError as runtime_error:
                        failed_recipient_count += len(recipient_delivery_draft_chunk)
                        failure_reason = _build_dcx_newsletter_send_failure_reason(
                            runtime_error=runtime_error
                        )
                        for recipient_delivery_draft in recipient_delivery_draft_chunk:
                            failed_recipient_reasons.append(
                                {
                                    "recipient_id": recipient_delivery_draft["recipient_id"],
                                    "recipient_email": recipient_delivery_draft["recipient_email"],
                                    "failure_reason": failure_reason,
                                }
                            )
                            cursor.execute(
                                """
                                UPDATE stephen_dcx_emails_sends_recipients
                                SET delivery_status = 'failed',
                                    failed_at_ts_ms = %s,
                                    failure_reason = %s,
                                    last_provider_event_at_ts_ms = %s,
                                    last_provider_event_type = 'failed',
                                    updated_at_ts_ms = %s
                                WHERE id = %s
                                """,
                                (
                                    current_timestamp_ms,
                                    failure_reason,
                                    current_timestamp_ms,
                                    current_timestamp_ms,
                                    recipient_delivery_draft["recipient_id"],
                                ),
                            )
                        continue

                    for recipient_delivery_draft, provider_summary in zip(recipient_delivery_draft_chunk, provider_summaries):
                        sent_recipient_count += 1
                        cursor.execute(
                            """
                            UPDATE stephen_dcx_emails_sends_recipients
                            SET delivery_status = 'sent',
                                provider_message_id = %s,
                                sent_at_ts_ms = %s,
                                failed_at_ts_ms = NULL,
                                failure_reason = NULL,
                                last_provider_event_at_ts_ms = %s,
                                last_provider_event_type = 'sent',
                                updated_at_ts_ms = %s
                            WHERE id = %s
                            """,
                            (
                                provider_summary.get("provider_message_id"),
                                current_timestamp_ms,
                                current_timestamp_ms,
                                current_timestamp_ms,
                                recipient_delivery_draft["recipient_id"],
                            ),
                        )

                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS total_recipient_count,
                        COUNT(CASE WHEN delivery_status = 'sent' THEN 1 END) AS sent_recipient_count,
                        COUNT(CASE WHEN delivery_status = 'failed' THEN 1 END) AS failed_recipient_count,
                        COUNT(CASE WHEN delivery_status = 'skipped' THEN 1 END) AS skipped_recipient_count,
                        COUNT(CASE WHEN delivery_status IN ('pending', 'sending') THEN 1 END) AS remaining_recipient_count
                    FROM stephen_dcx_emails_sends_recipients
                    WHERE email_send_id = %s
                    """,
                    (email_send_id,),
                )
                aggregate_row = cursor.fetchone()

                total_recipient_count = aggregate_row[0] or 0
                sent_recipient_count = aggregate_row[1] or 0
                failed_recipient_count = aggregate_row[2] or 0
                skipped_recipient_count = aggregate_row[3] or 0
                remaining_recipient_count = aggregate_row[4] or 0
                final_send_status = (
                    "sending"
                    if remaining_recipient_count > 0
                    else "failed"
                    if failed_recipient_count > 0
                    else "sent"
                )
                send_completed_at_ts_ms = current_timestamp_ms if remaining_recipient_count == 0 else None
                dispatch_summary = {
                    "total_recipient_count": total_recipient_count,
                    "sent_recipient_count": sent_recipient_count,
                    "failed_recipient_count": failed_recipient_count,
                    "skipped_recipient_count": skipped_recipient_count,
                    "remaining_recipient_count": remaining_recipient_count,
                }

                cursor.execute(
                    """
                    UPDATE stephen_dcx_emails_sends
                    SET send_status = %s,
                        send_completed_at_ts_ms = %s,
                        send_summary_json = send_summary_json || %s::jsonb,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        final_send_status,
                        send_completed_at_ts_ms,
                        json.dumps(dispatch_summary),
                        current_timestamp_ms,
                        email_send_id,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NEWSLETTER_SEND_DISPATCH_FAILED") from exc

    return {
        "status": "dispatched",
        "dispatched_send": {
            "email_send_id": email_send_id,
            "send_status": final_send_status,
            "summary": dispatch_summary,
            "failed_recipient_reasons": failed_recipient_reasons,
        },
    }


def _read_current_timestamp_ms() -> int:
    return int(time.time() * 1000)


def _build_dcx_newsletter_send_failure_reason(runtime_error: RuntimeError) -> str:
    base_error_code = str(runtime_error)
    provider_exception = runtime_error.__cause__

    if provider_exception is None:
        return base_error_code

    provider_exception_message = str(provider_exception).strip()
    provider_exception_type = type(provider_exception).__name__

    if provider_exception_message == "":
        return f"{base_error_code} [{provider_exception_type}]"

    return f"{base_error_code} [{provider_exception_type}: {provider_exception_message}]"


def _append_ai_translated_label_to_email_bodies(rendered_bodies: dict[str, str]) -> dict[str, str]:
    return {
        "text_body": f"{rendered_bodies.get('text_body', '').rstrip()}\n\nAI translated from English.",
        "html_body": (
            f"{rendered_bodies.get('html_body', '').rstrip()}"
            "<p style=\"margin-top:24px;color:#64748b;font-size:12px;line-height:1.5;\">"
            "AI translated from English."
            "</p>"
        ),
    }


def _build_dcx_email_send_tracking_redirect_url(tracking_token: str) -> str:
    """Minimal contract: return one absolute tracked-link redirect URL for a non-empty token."""
    configured_api_base_url = os.getenv("DCX_API_BASE_URL", "").strip().rstrip("/")
    if configured_api_base_url != "":
        return f"{configured_api_base_url}/public/email-links/{quote(tracking_token)}"

    runtime_environment = os.getenv("DCX_ENVIRONMENT", "local").strip().lower() or "local"
    default_api_base_url = (
        "https://api.dcxagent.ai"
        if runtime_environment in {"production", "staging"}
        else "http://localhost:8000"
    )
    return f"{default_api_base_url}/public/email-links/{quote(tracking_token)}"


def _chunk_dcx_newsletter_delivery_drafts(
    recipient_delivery_drafts: list[dict[str, Any]],
    chunk_size: int,
) -> list[list[dict[str, Any]]]:
    return [
        recipient_delivery_drafts[start_index : start_index + chunk_size]
        for start_index in range(0, len(recipient_delivery_drafts), chunk_size)
    ]
