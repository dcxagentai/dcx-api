"""
CONTEXT:
This file reads the newsletter-send catalog for one DCX newsletter identity in the admin workspace.
It exists so the admin newsletters editor can show which newsletter sends have already been prepared,
scheduled, dispatched, cancelled, clicked, delivered, bounced, or complained without requiring a
separate operations surface.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_newsletter_sends_catalog_capability(
    email_key: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_key is one non-empty newsletter identity key.
        - language_code is one non-empty language code used by the current editor route.
        - The configured database is reachable.
      postconditions:
        - Returns one ordered list of newsletter send rows for the requested newsletter key.
        - Includes recipient, provider-outcome, and click summary counts for each send row.
        - Includes a count of recipients blocked because newsletter translations are still missing.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Internal users need to see the operational state of one newsletter without
          leaving the editor that owns the content.
      WHEN TO USE it:
        - Use it from the admin newsletter editor route only.
      WHEN NOT TO USE it:
        - Do not use it for raw per-recipient audit trails; this is an admin summary surface.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The UI can show real send outcomes instead of only prepared-send snapshots.
        - A later deeper operations surface can drill into individual recipients when needed.

    TESTS:
      - returns_newsletter_send_rows_with_delivery_and_click_summary_counts
      - returns_empty_catalog_when_no_prepared_sends_exist

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SENDS_CATALOG_READ_FAILED:
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
    normalized_email_key = email_key.strip()
    normalized_language_code = language_code.strip().lower()
    if normalized_email_key == "" or normalized_language_code == "":
        return {
            "newsletter_sends": [],
            "total_send_count": 0,
        }

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        email_send.id,
                        email_send.source_email_id,
                        email_send.email_key_snapshot,
                        email_send.send_status,
                        email_send.send_audience_type,
                        COALESCE(email_send.send_summary_json ->> 'send_audience_scope', 'all') AS send_audience_scope,
                        email_send.scheduled_send_at_ts_ms,
                        email_send.send_started_at_ts_ms,
                        email_send.send_completed_at_ts_ms,
                        email_send.cancelled_at_ts_ms,
                        email_send.created_at_ts_ms,
                        email_send.updated_at_ts_ms,
                        language.language_code,
                        COALESCE(recipient_counts.total_recipient_count, 0) AS total_recipient_count,
                        COALESCE(recipient_counts.send_candidate_count, 0) AS send_candidate_count,
                        COALESCE(recipient_counts.skipped_recipient_count, 0) AS skipped_recipient_count,
                        COALESCE(recipient_counts.blocked_missing_translation_count, 0) AS blocked_missing_translation_count,
                        COALESCE(recipient_counts.pending_recipient_count, 0) AS pending_recipient_count,
                        COALESCE(recipient_counts.sending_recipient_count, 0) AS sending_recipient_count,
                        COALESCE(recipient_counts.sent_recipient_count, 0) AS sent_recipient_count,
                        COALESCE(recipient_counts.delivered_recipient_count, 0) AS delivered_recipient_count,
                        COALESCE(recipient_counts.failed_recipient_count, 0) AS failed_recipient_count,
                        COALESCE(recipient_counts.bounced_recipient_count, 0) AS bounced_recipient_count,
                        COALESCE(recipient_counts.complained_recipient_count, 0) AS complained_recipient_count,
                        COALESCE(recipient_counts.cancelled_recipient_count, 0) AS cancelled_recipient_count,
                        COALESCE(link_counts.tracked_link_count, 0) AS tracked_link_count,
                        COALESCE(click_counts.total_click_count, 0) AS total_click_count,
                        COALESCE(click_counts.unique_clicked_link_count, 0) AS unique_clicked_link_count
                    FROM stephen_dcx_emails_sends AS email_send
                    INNER JOIN stephen_dcx_emails AS email_row
                      ON email_row.id = email_send.source_email_id
                    INNER JOIN stephen_dcx_languages AS language
                      ON language.id = email_row.language_id
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*) AS total_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_decision = 'send') AS send_candidate_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'skipped') AS skipped_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.failure_reason LIKE 'missing_translation:%%') AS blocked_missing_translation_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'pending') AS pending_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'sending') AS sending_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'sent') AS sent_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'delivered') AS delivered_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'failed') AS failed_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'bounced') AS bounced_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'complained') AS complained_recipient_count,
                            COUNT(*) FILTER (WHERE recipient.delivery_status = 'cancelled') AS cancelled_recipient_count
                        FROM stephen_dcx_emails_sends_recipients AS recipient
                        WHERE recipient.email_send_id = email_send.id
                    ) AS recipient_counts
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*) AS tracked_link_count
                        FROM stephen_dcx_emails_sends_links AS link_row
                        WHERE link_row.email_send_id = email_send.id
                    ) AS link_counts
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*) AS total_click_count,
                            COUNT(DISTINCT click_row.email_send_link_id) AS unique_clicked_link_count
                        FROM stephen_dcx_emails_sends_link_clicks AS click_row
                        INNER JOIN stephen_dcx_emails_sends_links AS link_row
                          ON link_row.id = click_row.email_send_link_id
                        WHERE link_row.email_send_id = email_send.id
                    ) AS click_counts
                      ON TRUE
                    WHERE email_send.email_key_snapshot = %s
                      AND email_send.send_kind = 'newsletter'
                    ORDER BY email_send.created_at_ts_ms DESC, email_send.id DESC
                    """,
                    (normalized_email_key,),
                )
                rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SENDS_CATALOG_READ_FAILED") from exc

    newsletter_sends = []
    for row in rows:
        newsletter_sends.append(
            {
                "email_send_id": row[0],
                "source_email_id": row[1],
                "email_key": row[2],
                "send_status": row[3],
                "send_audience_type": row[4],
                "send_audience_scope": row[5],
                "scheduled_send_at_ts_ms": row[6],
                "send_started_at_ts_ms": row[7],
                "send_completed_at_ts_ms": row[8],
                "cancelled_at_ts_ms": row[9],
                "created_at_ts_ms": row[10],
                "updated_at_ts_ms": row[11],
                "language_code": row[12],
                "total_recipient_count": row[13],
                "send_candidate_count": row[14],
                "skipped_recipient_count": row[15],
                "blocked_missing_translation_count": row[16],
                "pending_recipient_count": row[17],
                "sending_recipient_count": row[18],
                "sent_recipient_count": row[19],
                "delivered_recipient_count": row[20],
                "failed_recipient_count": row[21],
                "bounced_recipient_count": row[22],
                "complained_recipient_count": row[23],
                "cancelled_recipient_count": row[24],
                "tracked_link_count": row[25],
                "total_click_count": row[26],
                "unique_clicked_link_count": row[27],
            }
        )

    return {
        "newsletter_sends": newsletter_sends,
        "total_send_count": len(newsletter_sends),
    }
