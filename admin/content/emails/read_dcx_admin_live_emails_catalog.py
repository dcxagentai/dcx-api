"""
CONTEXT:
This file reads the live email-template catalog for the DCX admin content surface.
It exists so the internal admin frontend can browse email types, keys, and language
variants from the `stephen_dcx_emails` table before editing tools are added.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_emails_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns the current live email-template rows with language metadata included.
        - Orders rows predictably by email type, key, original-first, then language code.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin content screens should display the multilingual email system directly
          from the durable content table before CRUD tooling exists.
      WHEN TO USE it:
        - Use it from the read-only admin emails viewer surface only.
      WHEN NOT TO USE it:
        - Do not use it for outbound email sending or content mutation.
      WHAT CAN GO WRONG:
        - Database reads can fail.
      WHAT COMES NEXT:
        - Keep this read-only catalog stable, then layer controlled edit flows on top after
          admin auth and permissions are added.

    TESTS:
      - returns_live_email_rows_with_language_details
      - returns_empty_catalog_when_no_live_emails_exist

    ERRORS:
      - API_DCX_ADMIN_EMAILS_CATALOG_READ_FAILED:
          suggested_action: Confirm database health and retry the admin emails read after the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend and database are healthy.
          retry_safe: true

    CODE:
    """
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
                    ORDER BY
                        e.email_type ASC,
                        e.email_key ASC,
                        e.is_original DESC,
                        l.language_code ASC,
                        e.id ASC
                    """
                )
                catalog_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_EMAILS_CATALOG_READ_FAILED") from exc

    emails = [
        {
            "email_id": catalog_row[0],
            "email_type": catalog_row[1],
            "email_key": catalog_row[2],
            "email_subject": catalog_row[3],
            "email_body": catalog_row[4],
            "is_original": catalog_row[5],
            "is_live": catalog_row[6],
            "version_of_id": catalog_row[7],
            "translation_of_id": catalog_row[8],
            "created_at_ts_ms": catalog_row[9],
            "updated_at_ts_ms": catalog_row[10],
            "language": {
                "id": catalog_row[11],
                "language_code": catalog_row[12],
                "language_name_en": catalog_row[13],
                "language_name_native": catalog_row[14],
                "is_rtl": catalog_row[15],
            },
        }
        for catalog_row in catalog_rows
    ]

    return {
        "emails": emails,
        "total_live_row_count": len(emails),
    }
