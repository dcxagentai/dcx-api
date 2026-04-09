"""
CONTEXT:
This file reads the live original content-page rows for the DCX admin pages catalog.
It exists so internal users can browse current draft/published/archived page identities before
opening one editor route for a specific page.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_content_pages_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns the current live original content pages with language and category metadata.
        - Orders pages by newest update first.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin pages surface needs one stable list of current page identities before the user
          enters the full editor.
      WHEN TO USE it:
        - Use it from the `/content/pages` admin route only.
      WHEN NOT TO USE it:
        - Do not use it for public page builds.
      WHAT CAN GO WRONG:
        - Database reads can fail.
      WHAT COMES NEXT:
        - The editor route can open one page by `page_key` from this catalog.

    TESTS:
      - returns_live_original_content_pages_with_category_metadata

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGES_CATALOG_READ_FAILED:
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
                        page.id,
                        page.page_key,
                        page.category_key,
                        page.page_title,
                        page.page_lede,
                        page.page_slug,
                        page.publication_status,
                        page.published_at_ts_ms,
                        page.language_id,
                        page.created_at_ts_ms,
                        page.updated_at_ts_ms,
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native,
                        language.is_rtl,
                        category.category_name,
                        category.category_slug
                    FROM stephen_dcx_content_pages AS page
                    JOIN stephen_dcx_languages AS language
                      ON language.id = page.language_id
                    JOIN stephen_dcx_content_page_categories AS category
                      ON category.category_key = page.category_key
                     AND category.language_id = page.language_id
                     AND category.is_live = TRUE
                    WHERE page.is_live = TRUE
                      AND page.is_original = TRUE
                    ORDER BY page.updated_at_ts_ms DESC, page.id DESC
                    """
                )
                page_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGES_CATALOG_READ_FAILED") from exc

    pages = [
        {
            "page_id": page_row[0],
            "page_key": page_row[1],
            "category_key": page_row[2],
            "page_title": page_row[3],
            "page_lede": page_row[4],
            "page_slug": page_row[5],
            "publication_status": page_row[6],
            "published_at_ts_ms": page_row[7],
            "language_id": page_row[8],
            "created_at_ts_ms": page_row[9],
            "updated_at_ts_ms": page_row[10],
            "language": {
                "language_code": page_row[11],
                "language_name_en": page_row[12],
                "language_name_native": page_row[13],
                "is_rtl": page_row[14],
            },
            "category": {
                "category_name": page_row[15],
                "category_slug": page_row[16],
            },
        }
        for page_row in page_rows
    ]

    return {
        "pages": pages,
        "total_live_page_count": len(pages),
    }
