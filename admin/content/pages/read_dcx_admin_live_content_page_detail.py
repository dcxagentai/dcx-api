"""
CONTEXT:
This file reads one live content-page row detail for the DCX admin page editor.
It exists so the admin frontend can open one stable editor route for one page/language pair
without reading the entire catalog again or relying on query-string selectors.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_content_page_detail_capability(
    page_key: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - page_key is one non-empty stable content-page identity.
        - language_code is one non-empty language code such as `en`.
        - The configured database is reachable.
      postconditions:
        - Returns one current live content-page row for the requested page/language pair.
        - Includes category and language metadata required by the admin editor.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin pages editor should open one precise live row rather than reusing the list catalog
          as a pseudo-detail source.
      WHEN TO USE it:
        - Use it from the admin `/content/pages/<language>/<page_key>` route only.
      WHEN NOT TO USE it:
        - Do not use it for public page rendering or to read historical versions.
      WHAT CAN GO WRONG:
        - The requested live row may not exist.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The save and publish capabilities can use the returned row id as the immutable live-row target.

    TESTS:
      - returns_requested_live_content_page_detail
      - raises_clear_error_when_live_content_page_detail_missing

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_DETAIL_NOT_FOUND:
          suggested_action: Return to the pages list, refresh it, and reopen the current live page row.
          common_causes:
            - stale page route
            - page not yet created in the requested language
          recovery_steps:
            - Reload the pages catalog.
            - Retry from the current live row if needed.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_DETAIL_READ_FAILED:
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
    normalized_page_key = page_key.strip()
    normalized_language_code = language_code.strip().lower()
    if normalized_page_key == "" or normalized_language_code == "":
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_DETAIL_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        page.id,
                        page.page_key,
                        page.category_key,
                        page.page_title,
                        page.page_lede,
                        page.page_body_markdown,
                        page.meta_title,
                        page.meta_description,
                        page.page_slug,
                        page.publication_status,
                        page.published_at_ts_ms,
                        page.is_original,
                        page.is_live,
                        page.version_of_id,
                        page.translation_of_id,
                        page.created_at_ts_ms,
                        page.updated_at_ts_ms,
                        language.id,
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native,
                        language.is_rtl,
                        category.id,
                        category.category_name,
                        category.category_description,
                        category.category_slug
                    FROM stephen_dcx_content_pages AS page
                    JOIN stephen_dcx_languages AS language
                      ON language.id = page.language_id
                    JOIN stephen_dcx_content_page_categories AS category
                      ON category.category_key = page.category_key
                     AND category.language_id = page.language_id
                     AND category.is_live = TRUE
                    WHERE page.page_key = %s
                      AND language.language_code = %s
                      AND page.is_live = TRUE
                    ORDER BY page.id DESC
                    LIMIT 1
                    """,
                    (normalized_page_key, normalized_language_code),
                )
                page_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_DETAIL_READ_FAILED") from exc

    if page_row is None:
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_DETAIL_NOT_FOUND")

    return {
        "page_id": page_row[0],
        "page_key": page_row[1],
        "category_key": page_row[2],
        "page_title": page_row[3],
        "page_lede": page_row[4],
        "page_body_markdown": page_row[5],
        "meta_title": page_row[6],
        "meta_description": page_row[7],
        "page_slug": page_row[8],
        "publication_status": page_row[9],
        "published_at_ts_ms": page_row[10],
        "is_original": page_row[11],
        "is_live": page_row[12],
        "version_of_id": page_row[13],
        "translation_of_id": page_row[14],
        "created_at_ts_ms": page_row[15],
        "updated_at_ts_ms": page_row[16],
        "language": {
            "id": page_row[17],
            "language_code": page_row[18],
            "language_name_en": page_row[19],
            "language_name_native": page_row[20],
            "is_rtl": page_row[21],
        },
        "category": {
            "category_id": page_row[22],
            "category_name": page_row[23],
            "category_description": page_row[24],
            "category_slug": page_row[25],
        },
    }
