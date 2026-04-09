"""
CONTEXT:
This file reads the prepared-send catalog for one DCX newsletter identity in the admin workspace.
It exists so the admin newsletters editor can show which newsletter sends have already been prepared,
scheduled, or cancelled before the actual provider-dispatch worker is connected.
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
        - Returns one ordered list of prepared send rows for the requested newsletter key.
        - Includes recipient/link summary counts for each prepared send row.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Internal users need to see the operational preparation state of one newsletter without
          leaving the editor that owns the content.
      WHEN TO USE it:
        - Use it from the admin newsletter editor route only.
      WHEN NOT TO USE it:
        - Do not use it for actual provider dispatch or click-event reporting yet.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The UI can allow `prepare now`, `schedule`, and `cancel` actions against these rows.

    TESTS:
      - returns_prepared_send_rows_with_summary_counts
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
                        email_send.scheduled_send_at_ts_ms,
                        email_send.send_started_at_ts_ms,
                        email_send.send_completed_at_ts_ms,
                        email_send.cancelled_at_ts_ms,
                        email_send.created_at_ts_ms,
                        email_send.updated_at_ts_ms,
                        language.language_code,
                        COUNT(DISTINCT recipient.id) AS total_recipient_count,
                        COUNT(DISTINCT CASE WHEN recipient.delivery_decision = 'send' THEN recipient.id END) AS send_candidate_count,
                        COUNT(DISTINCT CASE WHEN recipient.delivery_status = 'skipped' THEN recipient.id END) AS skipped_recipient_count,
                        COUNT(DISTINCT link.id) AS tracked_link_count
                    FROM stephen_dcx_emails_sends AS email_send
                    INNER JOIN stephen_dcx_emails AS email_row
                      ON email_row.id = email_send.source_email_id
                    INNER JOIN stephen_dcx_languages AS language
                      ON language.id = email_row.language_id
                    LEFT JOIN stephen_dcx_emails_sends_recipients AS recipient
                      ON recipient.email_send_id = email_send.id
                    LEFT JOIN stephen_dcx_emails_sends_links AS link
                      ON link.email_send_id = email_send.id
                    WHERE email_send.email_key_snapshot = %s
                    GROUP BY
                        email_send.id,
                        email_send.source_email_id,
                        email_send.email_key_snapshot,
                        email_send.send_status,
                        email_send.send_audience_type,
                        email_send.scheduled_send_at_ts_ms,
                        email_send.send_started_at_ts_ms,
                        email_send.send_completed_at_ts_ms,
                        email_send.cancelled_at_ts_ms,
                        email_send.created_at_ts_ms,
                        email_send.updated_at_ts_ms,
                        language.language_code
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
                "scheduled_send_at_ts_ms": row[5],
                "send_started_at_ts_ms": row[6],
                "send_completed_at_ts_ms": row[7],
                "cancelled_at_ts_ms": row[8],
                "created_at_ts_ms": row[9],
                "updated_at_ts_ms": row[10],
                "language_code": row[11],
                "total_recipient_count": row[12],
                "send_candidate_count": row[13],
                "skipped_recipient_count": row[14],
                "tracked_link_count": row[15],
            }
        )

    return {
        "newsletter_sends": newsletter_sends,
        "total_send_count": len(newsletter_sends),
    }
