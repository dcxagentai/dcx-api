"""
CONTEXT:
This file reads one live newsletter-content row detail for the DCX admin newsletter editor.
It exists so the admin frontend can open one newsletter/language editor route without using
query-string identity selectors.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_newsletter_detail_capability(
    email_key: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_key is one non-empty stable newsletter identity.
        - language_code is one non-empty language code such as `en`.
        - The configured database is reachable.
      postconditions:
        - Returns the current live newsletter row for the requested key/language pair.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The newsletter editor should open one explicit immutable live row rather than overloading
          the catalog response.
      WHEN TO USE it:
        - Use it from the admin `/content/newsletters/<language>/<email_key>` route only.
      WHEN NOT TO USE it:
        - Do not use it for transactional templates or send dispatch.
      WHAT CAN GO WRONG:
        - The requested newsletter row may not exist.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The existing email save capability can continue editing this row because newsletter content
          still lives in `stephen_dcx_emails`.

    TESTS:
      - returns_requested_live_newsletter_detail
      - raises_clear_error_when_live_newsletter_detail_missing

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND:
          suggested_action: Return to the newsletters list, refresh it, and reopen the current live row.
          common_causes:
            - stale newsletter route
            - newsletter not yet created in the requested language
          recovery_steps:
            - Reload the newsletters catalog.
            - Retry from the current live row if needed.
          retry_safe: true
      - API_DCX_ADMIN_NEWSLETTER_DETAIL_READ_FAILED:
          suggested_action: Confirm database health and retry.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_email_key = email_key.strip()
    normalized_language_code = language_code.strip().lower()
    if normalized_email_key == "" or normalized_language_code == "":
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        e.id,
                        e.email_type,
                        e.email_key,
                        e.email_subject,
                        e.email_body,
                        e.is_original,
                        e.is_live,
                        e.version_of_id,
                        e.translation_of_id,
                        e.created_at_ts_ms,
                        e.updated_at_ts_ms,
                        l.id,
                        l.language_code,
                        l.language_name_en,
                        l.language_name_native,
                        l.is_rtl
                    FROM stephen_dcx_emails e
                    INNER JOIN stephen_dcx_languages l
                      ON l.id = e.language_id
                    WHERE e.is_live = TRUE
                      AND e.email_type = 'newsletter'
                      AND e.email_key = %s
                      AND l.language_code = %s
                    ORDER BY e.id DESC
                    LIMIT 1
                    """,
                    (normalized_email_key, normalized_language_code),
                )
                newsletter_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DETAIL_READ_FAILED") from exc

    if newsletter_row is None:
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND")

    return {
        "email_id": newsletter_row[0],
        "email_type": newsletter_row[1],
        "email_key": newsletter_row[2],
        "email_subject": newsletter_row[3],
        "email_body": newsletter_row[4],
        "is_original": newsletter_row[5],
        "is_live": newsletter_row[6],
        "version_of_id": newsletter_row[7],
        "translation_of_id": newsletter_row[8],
        "created_at_ts_ms": newsletter_row[9],
        "updated_at_ts_ms": newsletter_row[10],
        "language": {
            "id": newsletter_row[11],
            "language_code": newsletter_row[12],
            "language_name_en": newsletter_row[13],
            "language_name_native": newsletter_row[14],
            "is_rtl": newsletter_row[15],
        },
    }
