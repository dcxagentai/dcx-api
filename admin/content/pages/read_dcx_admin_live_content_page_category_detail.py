"""
CONTEXT:
This file reads one live DCX content-page category row for the admin CMS surface.
It exists so the admin workspace can open one stable path-based category editor route and show
the existing and missing translation rows for that category identity.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_content_page_category_detail_capability(
    category_key: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - category_key identifies one category identity.
        - language_code identifies one supported language.
        - The configured database is reachable.
      postconditions:
        - Returns one current live category row for the requested category/language pair.
        - Returns existing live translations and missing supported languages for that category identity.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Category editing should be path-based and multilingual-aware in the same way as pages and newsletters.
      WHEN TO USE it:
        - Use it from the admin `/content/page-categories/<language>/<category_key>` route only.
      WHEN NOT TO USE it:
        - Do not use it as the public build source of truth.
      WHAT CAN GO WRONG:
        - The requested live row can be missing.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The editor can autosave/save the returned row and create translations for missing languages.

    TESTS:
      - covered_indirectly_by_admin_content_page_category_detail_route_test

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_INVALID:
          suggested_action: Open one valid category route and retry.
          common_causes:
            - blank category key
            - blank language code
          recovery_steps:
            - Return to the categories list and reopen one current row.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_NOT_FOUND:
          suggested_action: Refresh the categories list and reopen the current live row.
          common_causes:
            - stale route
            - missing live translation row
          recovery_steps:
            - Reload the categories catalog.
            - Retry from the current live row.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_READ_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify backend/database health.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    normalized_category_key = category_key.strip()
    normalized_language_code = language_code.strip().lower()
    if normalized_category_key == "" or normalized_language_code == "":
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        category.id,
                        category.category_key,
                        category.category_name,
                        category.category_description,
                        category.category_slug,
                        category.language_id,
                        category.is_original,
                        category.translation_of_id,
                        category.created_at_ts_ms,
                        category.updated_at_ts_ms,
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native,
                        language.is_rtl
                    FROM stephen_dcx_content_page_categories AS category
                    JOIN stephen_dcx_languages AS language
                      ON language.id = category.language_id
                    WHERE category.category_key = %s
                      AND category.is_live = TRUE
                      AND language.language_code = %s
                    LIMIT 1
                    """,
                    (normalized_category_key, normalized_language_code),
                )
                category_row = cursor.fetchone()
                if category_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        category.id,
                        category.category_key,
                        category.is_original,
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native,
                        language.is_rtl
                    FROM stephen_dcx_content_page_categories AS category
                    JOIN stephen_dcx_languages AS language
                      ON language.id = category.language_id
                    WHERE category.category_key = %s
                      AND category.is_live = TRUE
                    ORDER BY language.display_sort_order ASC, category.id ASC
                    """,
                    (normalized_category_key,),
                )
                translation_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native,
                        language.is_rtl
                    FROM stephen_dcx_languages AS language
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM stephen_dcx_content_page_categories AS category
                        WHERE category.category_key = %s
                          AND category.language_id = language.id
                          AND category.is_live = TRUE
                    )
                    ORDER BY language.display_sort_order ASC, language.id ASC
                    """,
                    (normalized_category_key,),
                )
                missing_language_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_READ_FAILED") from exc

    return {
        "category_id": category_row[0],
        "category_key": category_row[1],
        "category_name": category_row[2],
        "category_description": category_row[3],
        "category_slug": category_row[4],
        "language_id": category_row[5],
        "is_original": category_row[6],
        "translation_of_id": category_row[7],
        "created_at_ts_ms": category_row[8],
        "updated_at_ts_ms": category_row[9],
        "language": {
            "language_code": category_row[10],
            "language_name_en": category_row[11],
            "language_name_native": category_row[12],
            "is_rtl": category_row[13],
        },
        "translation_summary": {
            "existing_translations": [
                {
                    "category_id": translation_row[0],
                    "category_key": translation_row[1],
                    "is_original": translation_row[2],
                    "is_current_language": translation_row[3] == normalized_language_code,
                    "language": {
                        "language_code": translation_row[3],
                        "language_name_en": translation_row[4],
                        "language_name_native": translation_row[5],
                        "is_rtl": translation_row[6],
                    },
                }
                for translation_row in translation_rows
            ],
            "missing_languages": [
                {
                    "language_code": missing_language_row[0],
                    "language_name_en": missing_language_row[1],
                    "language_name_native": missing_language_row[2],
                    "is_rtl": missing_language_row[3],
                }
                for missing_language_row in missing_language_rows
            ],
        },
    }
