"""
CONTEXT:
This file reads the live UX-string catalog for the DCX admin content surface.
It exists so the internal admin frontend can browse string groups, keys, and language
variants from the `stephen_dcx_ux_strings` table before editing tools are added.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_ux_strings_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns the current live UX-string rows with language metadata included.
        - Orders rows predictably by group, key, original-first, then language code.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin content screens should display the multilingual string system directly
          from the durable content table before CRUD tooling exists.
      WHEN TO USE it:
        - Use it from the read-only admin UX-strings viewer surface only.
      WHEN NOT TO USE it:
        - Do not use it for public-site bundle generation or content mutation.
      WHAT CAN GO WRONG:
        - Database reads can fail.
      WHAT COMES NEXT:
        - Keep this read-only catalog stable, then layer controlled edit flows on top after
          admin auth and permissions are added.

    TESTS:
      - returns_live_ux_string_rows_with_language_details
      - returns_empty_catalog_when_no_live_ux_strings_exist

    ERRORS:
      - API_DCX_ADMIN_UX_STRINGS_CATALOG_READ_FAILED:
          suggested_action: Confirm database health and retry the admin UX-strings read after the backend is stable.
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
                        s.id,
                        s.string_group,
                        s.string_key,
                        s.text,
                        s.is_original,
                        s.is_live,
                        s.version_of_id,
                        s.translation_of_id,
                        s.created_at_ts_ms,
                        s.updated_at_ts_ms,
                        l.id,
                        l.language_code,
                        l.language_name_en,
                        l.language_name_native,
                        l.is_rtl
                    FROM stephen_dcx_ux_strings s
                    INNER JOIN stephen_dcx_languages l
                      ON l.id = s.language_id
                    WHERE s.is_live = TRUE
                    ORDER BY
                        s.string_group ASC,
                        s.string_key ASC,
                        s.is_original DESC,
                        l.language_code ASC,
                        s.id ASC
                    """
                )
                catalog_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_UX_STRINGS_CATALOG_READ_FAILED") from exc

    ux_strings = [
        {
            "ux_string_id": catalog_row[0],
            "string_group": catalog_row[1],
            "string_key": catalog_row[2],
            "text": catalog_row[3],
            "is_original": catalog_row[4],
            "is_live": catalog_row[5],
            "version_of_id": catalog_row[6],
            "translation_of_id": catalog_row[7],
            "created_at_ts_ms": catalog_row[8],
            "updated_at_ts_ms": catalog_row[9],
            "language": {
                "id": catalog_row[10],
                "language_code": catalog_row[11],
                "language_name_en": catalog_row[12],
                "language_name_native": catalog_row[13],
                "is_rtl": catalog_row[14],
            },
        }
        for catalog_row in catalog_rows
    ]

    return {
        "ux_strings": ux_strings,
        "total_live_row_count": len(ux_strings),
    }
