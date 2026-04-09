"""
CONTEXT:
This file reads the live newsletter-content catalog for the DCX admin content surface.
It exists so the internal admin frontend can browse newsletter drafts and later sent-ready
campaign content directly from the immutable multilingual emails table.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_newsletters_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns the current live original newsletter rows with language metadata included.
        - Orders rows predictably by newest update first.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Newsletter content should get its own admin browsing surface even while it still reuses
          the durable multilingual emails table underneath.
      WHEN TO USE it:
        - Use it from the admin `/content/newsletters` route only.
      WHEN NOT TO USE it:
        - Do not use it for transactional email templates or actual send dispatch.
      WHAT CAN GO WRONG:
        - Database reads can fail.
      WHAT COMES NEXT:
        - The detail route and editor can open one newsletter by `email_key`.

    TESTS:
      - returns_live_original_newsletter_rows_with_language_details

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTERS_CATALOG_READ_FAILED:
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
                      AND e.is_original = TRUE
                      AND e.email_type = 'newsletter'
                    ORDER BY
                        e.updated_at_ts_ms DESC,
                        e.id DESC
                    """
                )
                catalog_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTERS_CATALOG_READ_FAILED") from exc

    newsletters = [
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
        "newsletters": newsletters,
        "total_live_row_count": len(newsletters),
    }
