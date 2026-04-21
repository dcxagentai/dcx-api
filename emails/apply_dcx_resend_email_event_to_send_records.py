"""
CONTEXT:
This file applies one verified Resend email-event webhook payload to DCX send and suppression records.
It exists so delivered, failed, bounced, and complained events can update local operational state
after the initial provider send request succeeds.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG

_HANDLED_DCX_RESEND_EMAIL_EVENT_TYPES = {
    "email.delivered",
    "email.failed",
    "email.bounced",
    "email.complained",
}


def apply_dcx_resend_email_event_to_send_records_capability(
    webhook_payload: dict,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - webhook_payload is one verified Resend webhook payload.
        - The configured database is reachable.
      postconditions:
        - Updates the matching recipient send row when the payload refers to a known provider message id.
        - Creates or refreshes one active `all_email` suppression for bounces and complaints.
        - Returns one summary of the applied or ignored webhook event.
      side_effects:
        - updates one `stephen_dcx_emails_sends_recipients` row when matched
        - may insert or update one `stephen_dcx_emails_suppressions` row
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: resend_email_event:{event_type}:{provider_message_id}
      locks:
        - one row-level lock on the matched recipient row
      contention_strategy: duplicate or reordered webhooks converge on the same recipient row through deterministic updates

    NARRATIVE:
      WHY this exists:
        - Newsletter send rows need provider-truth updates after the initial send request only marks emails as `sent`.
      WHEN TO USE it:
        - Use it only after the webhook request has already been verified.
      WHEN NOT TO USE it:
        - Do not use it for unsigned webhook requests.
        - Do not use it for admin-triggered send preparation.
      WHAT CAN GO WRONG:
        - The event type can be irrelevant.
        - The provider message id may not match a known local recipient row.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The admin UI can surface truer delivery state, and suppression-aware future sends can respect bounces and complaints automatically.

    TESTS:
      - applies_delivered_event_to_matching_recipient
      - applies_bounced_event_and_creates_all_email_suppression
      - ignores_unmatched_provider_message_id

    ERRORS:
      - API_DCX_RESEND_EMAIL_EVENT_INVALID:
          suggested_action: Retry with a verified Resend email-event payload.
          common_causes:
            - missing event type
            - missing provider message id
          recovery_steps:
            - Confirm the webhook payload shape.
            - Retry after verification succeeds.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_RESEND_EMAIL_EVENT_APPLY_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - write failure
          recovery_steps:
            - Verify database connectivity.
            - Retry on the next webhook replay if needed.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the recipient and suppression rows before manual replay

    CODE:
    """
    event_type = (webhook_payload.get("type") or "").strip()
    event_data = webhook_payload.get("data") if isinstance(webhook_payload.get("data"), dict) else {}
    provider_message_id = (event_data.get("email_id") or "").strip()
    if event_type == "" or provider_message_id == "":
        raise RuntimeError("API_DCX_RESEND_EMAIL_EVENT_INVALID")

    if event_type not in _HANDLED_DCX_RESEND_EMAIL_EVENT_TYPES:
        return {
            "status": "ignored",
            "event_type": event_type,
            "provider_message_id": provider_message_id,
            "reason": "event_type_not_handled",
        }

    event_timestamp_ms = _read_dcx_resend_webhook_event_timestamp_ms(webhook_payload)
    current_timestamp_ms = (
        current_timestamp_ms_provider() if current_timestamp_ms_provider else event_timestamp_ms
    )
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        recipient.id,
                        recipient.user_id,
                        recipient.email_send_id,
                        recipient.recipient_email_snapshot
                    FROM stephen_dcx_emails_sends_recipients AS recipient
                    WHERE recipient.provider_message_id = %s
                    FOR UPDATE
                    """,
                    (provider_message_id,),
                )
                recipient_row = cursor.fetchone()
                if recipient_row is None:
                    return {
                        "status": "ignored",
                        "event_type": event_type,
                        "provider_message_id": provider_message_id,
                        "reason": "recipient_not_found",
                    }

                failure_reason = _read_dcx_resend_event_failure_reason(
                    event_type=event_type,
                    event_data=event_data,
                )

                if event_type == "email.delivered":
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_emails_sends_recipients
                        SET delivery_status = 'delivered',
                            delivered_at_ts_ms = %s,
                            last_provider_event_at_ts_ms = %s,
                            last_provider_event_type = 'delivered',
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            event_timestamp_ms,
                            event_timestamp_ms,
                            current_timestamp_ms,
                            recipient_row[0],
                        ),
                    )
                elif event_type == "email.failed":
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
                            event_timestamp_ms,
                            failure_reason,
                            event_timestamp_ms,
                            current_timestamp_ms,
                            recipient_row[0],
                        ),
                    )
                elif event_type == "email.bounced":
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_emails_sends_recipients
                        SET delivery_status = 'bounced',
                            bounced_at_ts_ms = %s,
                            failure_reason = %s,
                            last_provider_event_at_ts_ms = %s,
                            last_provider_event_type = 'bounced',
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            event_timestamp_ms,
                            failure_reason,
                            event_timestamp_ms,
                            current_timestamp_ms,
                            recipient_row[0],
                        ),
                    )
                    _ensure_active_dcx_email_provider_suppression(
                        cursor=cursor,
                        user_id=recipient_row[1],
                        normalized_contact_value=(recipient_row[3] or "").strip().lower(),
                        current_timestamp_ms=current_timestamp_ms,
                        provider_reference_id=provider_message_id,
                        suppression_reason="provider_bounce:resend",
                    )
                elif event_type == "email.complained":
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_emails_sends_recipients
                        SET delivery_status = 'complained',
                            complained_at_ts_ms = %s,
                            failure_reason = %s,
                            last_provider_event_at_ts_ms = %s,
                            last_provider_event_type = 'complained',
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            event_timestamp_ms,
                            failure_reason,
                            event_timestamp_ms,
                            current_timestamp_ms,
                            recipient_row[0],
                        ),
                    )
                    _ensure_active_dcx_email_provider_suppression(
                        cursor=cursor,
                        user_id=recipient_row[1],
                        normalized_contact_value=(recipient_row[3] or "").strip().lower(),
                        current_timestamp_ms=current_timestamp_ms,
                        provider_reference_id=provider_message_id,
                        suppression_reason="provider_complaint:resend",
                    )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_RESEND_EMAIL_EVENT_APPLY_FAILED") from exc

    return {
        "status": "applied",
        "event_type": event_type,
        "provider_message_id": provider_message_id,
        "email_send_id": recipient_row[2],
        "recipient_id": recipient_row[0],
    }


def _ensure_active_dcx_email_provider_suppression(
    cursor: Any,
    user_id: int,
    normalized_contact_value: str,
    current_timestamp_ms: int,
    provider_reference_id: str,
    suppression_reason: str,
) -> None:
    cursor.execute(
        """
        SELECT id
        FROM stephen_dcx_emails_suppressions
        WHERE is_active = TRUE
          AND normalized_contact_value = %s
          AND suppression_scope = 'all_email'
        LIMIT 1
        """,
        (normalized_contact_value,),
    )
    active_suppression_row = cursor.fetchone()
    if active_suppression_row is not None:
        cursor.execute(
            """
            UPDATE stephen_dcx_emails_suppressions
            SET user_id = %s,
                suppression_source = CASE WHEN %s = 'provider_complaint:resend' THEN 'complaint' ELSE 'bounce' END,
                suppression_reason = %s,
                provider_name = 'resend',
                provider_reference_id = %s,
                updated_at_ts_ms = %s
            WHERE id = %s
            """,
            (
                user_id,
                suppression_reason,
                suppression_reason,
                provider_reference_id,
                current_timestamp_ms,
                active_suppression_row[0],
            ),
        )
        return

    cursor.execute(
        """
        INSERT INTO stephen_dcx_emails_suppressions (
            user_id,
            normalized_contact_value,
            suppression_source,
            suppression_scope,
            suppression_reason,
            provider_name,
            provider_reference_id,
            suppressed_at_ts_ms,
            is_active
        )
        VALUES (
            %s,
            %s,
            CASE WHEN %s = 'provider_complaint:resend' THEN 'complaint' ELSE 'bounce' END,
            'all_email',
            %s,
            'resend',
            %s,
            %s,
            TRUE
        )
        """,
        (
            user_id,
            normalized_contact_value,
            suppression_reason,
            suppression_reason,
            provider_reference_id,
            current_timestamp_ms,
        ),
    )


def _read_dcx_resend_webhook_event_timestamp_ms(webhook_payload: dict) -> int:
    raw_timestamp = webhook_payload.get("created_at")
    if not isinstance(raw_timestamp, str) or raw_timestamp.strip() == "":
        raw_timestamp = webhook_payload.get("data", {}).get("created_at")
    if not isinstance(raw_timestamp, str) or raw_timestamp.strip() == "":
        raise RuntimeError("API_DCX_RESEND_EMAIL_EVENT_INVALID")

    normalized_timestamp = raw_timestamp.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized_timestamp).timestamp() * 1000)


def _read_dcx_resend_event_failure_reason(event_type: str, event_data: dict) -> str:
    if event_type == "email.bounced" and isinstance(event_data.get("bounce"), dict):
        bounce_payload = event_data["bounce"]
        return (bounce_payload.get("message") or "resend_bounce").strip()
    if event_type == "email.complained":
        return "resend_complaint"
    if event_type == "email.failed":
        return (event_data.get("message") or "resend_failed").strip()
    return event_type
