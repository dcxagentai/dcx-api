"""
CONTEXT:
This file reads the recipient-level delivery snapshot for one DCX newsletter send.
It exists so the admin newsletter editor can answer the practical question: who did this
send go to, and what happened to each recipient row?
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_newsletter_send_recipients_capability(
    email_send_id: int,
    email_search: str = "",
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_send_id is one positive `stephen_dcx_emails_sends.id` value.
        - email_search is either blank or a partial recipient email string.
        - The configured database is reachable.
      postconditions:
        - Returns summary counts across every recipient row for the send.
        - Returns at most 25 recipient rows, filtered by email_search when provided.
        - Does not expose email body, user messages, attachments, trades, topics, or chat content.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Admin users need a lightweight operational audit view for newsletter delivery.
      WHEN TO USE it:
        - Use it from the admin newsletter send row recipient sheet.
      WHEN NOT TO USE it:
        - Do not use it for exporting a full marketing list or for message/content inspection.
      WHAT CAN GO WRONG:
        - The send id may be invalid.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - Later slices can add CSV export, pagination, resend-failed actions, and provider event timelines.

    TESTS:
      - returns_summary_counts_and_first_twenty_five_recipient_rows
      - filters_visible_recipient_rows_by_email_without_changing_summary_totals
      - returns_empty_result_for_invalid_send_id

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SEND_RECIPIENTS_READ_FAILED:
          suggested_action: Retry after confirming the backend and database are healthy.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry when the backend is healthy.
          retry_safe: true

    CODE:
    """
    if not isinstance(email_send_id, int) or email_send_id <= 0:
        return _empty_dcx_admin_newsletter_send_recipients_payload(email_send_id=email_send_id)

    normalized_email_search = email_search.strip().lower() if isinstance(email_search, str) else ""
    visible_rows_limit = 25
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS total_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'pending') AS pending_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'sending') AS sending_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'sent') AS sent_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'delivered') AS delivered_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'failed') AS failed_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'bounced') AS bounced_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'complained') AS complained_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'cancelled') AS cancelled_recipient_count,
                        COUNT(*) FILTER (WHERE recipient.delivery_status = 'skipped') AS skipped_recipient_count
                    FROM stephen_dcx_emails_sends_recipients AS recipient
                    WHERE recipient.email_send_id = %s
                    """,
                    (email_send_id,),
                )
                summary_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM stephen_dcx_emails_sends_recipients AS recipient
                    WHERE recipient.email_send_id = %s
                      AND (
                        %s = ''
                        OR LOWER(recipient.recipient_email_snapshot) LIKE '%%' || %s || '%%'
                      )
                    """,
                    (
                        email_send_id,
                        normalized_email_search,
                        normalized_email_search,
                    ),
                )
                filtered_recipient_count_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT
                        recipient.id,
                        recipient.user_id,
                        recipient.recipient_email_snapshot,
                        COALESCE(user_row.user_role, '') AS user_role,
                        recipient.delivery_decision,
                        recipient.delivery_status,
                        recipient.provider_message_id,
                        recipient.sent_at_ts_ms,
                        recipient.delivered_at_ts_ms,
                        recipient.bounced_at_ts_ms,
                        recipient.complained_at_ts_ms,
                        recipient.failed_at_ts_ms,
                        recipient.failure_reason,
                        recipient.last_provider_event_at_ts_ms,
                        recipient.last_provider_event_type,
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native
                    FROM stephen_dcx_emails_sends_recipients AS recipient
                    LEFT JOIN stephen_dcx_users AS user_row
                      ON user_row.id = recipient.user_id
                    LEFT JOIN stephen_dcx_languages AS language
                      ON language.id = user_row.preferred_language_id
                    WHERE recipient.email_send_id = %s
                      AND (
                        %s = ''
                        OR LOWER(recipient.recipient_email_snapshot) LIKE '%%' || %s || '%%'
                      )
                    ORDER BY recipient.id ASC
                    LIMIT %s
                    """,
                    (
                        email_send_id,
                        normalized_email_search,
                        normalized_email_search,
                        visible_rows_limit,
                    ),
                )
                recipient_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SEND_RECIPIENTS_READ_FAILED") from exc

    summary = {
        "total_recipient_count": summary_row[0] if summary_row is not None else 0,
        "pending_recipient_count": summary_row[1] if summary_row is not None else 0,
        "sending_recipient_count": summary_row[2] if summary_row is not None else 0,
        "sent_recipient_count": summary_row[3] if summary_row is not None else 0,
        "delivered_recipient_count": summary_row[4] if summary_row is not None else 0,
        "failed_recipient_count": summary_row[5] if summary_row is not None else 0,
        "bounced_recipient_count": summary_row[6] if summary_row is not None else 0,
        "complained_recipient_count": summary_row[7] if summary_row is not None else 0,
        "cancelled_recipient_count": summary_row[8] if summary_row is not None else 0,
        "skipped_recipient_count": summary_row[9] if summary_row is not None else 0,
    }

    recipients = []
    for row in recipient_rows:
        recipients.append(
            {
                "email_send_recipient_id": row[0],
                "user_id": row[1],
                "recipient_email": row[2],
                "user_role": row[3],
                "delivery_decision": row[4],
                "delivery_status": row[5],
                "provider_message_id": row[6],
                "sent_at_ts_ms": row[7],
                "delivered_at_ts_ms": row[8],
                "bounced_at_ts_ms": row[9],
                "complained_at_ts_ms": row[10],
                "failed_at_ts_ms": row[11],
                "failure_reason": row[12],
                "last_provider_event_at_ts_ms": row[13],
                "last_provider_event_type": row[14],
                "preferred_language": {
                    "language_code": row[15],
                    "language_name": row[16],
                    "language_name_native": row[17],
                } if row[15] is not None else None,
            }
        )

    return {
        "email_send_id": email_send_id,
        "email_search": normalized_email_search,
        "visible_rows_limit": visible_rows_limit,
        "filtered_recipient_count": (
            filtered_recipient_count_row[0] if filtered_recipient_count_row is not None else 0
        ),
        "summary": summary,
        "recipients": recipients,
    }


def _empty_dcx_admin_newsletter_send_recipients_payload(email_send_id: int) -> dict:
    return {
        "email_send_id": email_send_id,
        "email_search": "",
        "visible_rows_limit": 25,
        "filtered_recipient_count": 0,
        "summary": {
            "total_recipient_count": 0,
            "pending_recipient_count": 0,
            "sending_recipient_count": 0,
            "sent_recipient_count": 0,
            "delivered_recipient_count": 0,
            "failed_recipient_count": 0,
            "bounced_recipient_count": 0,
            "complained_recipient_count": 0,
            "cancelled_recipient_count": 0,
            "skipped_recipient_count": 0,
        },
        "recipients": [],
    }
