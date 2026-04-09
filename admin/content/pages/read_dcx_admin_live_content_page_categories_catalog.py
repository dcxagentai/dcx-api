"""
CONTEXT:
This file reads the live content-page category catalog for the DCX admin content surface.
It exists so the admin page editor can offer stable category choices from the durable
multilingual category table without mutating category rows in place.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_live_content_page_categories_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns the current live original content-page category rows ordered by category name.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Admin page editing should pull category choices from the live category table instead of
          hardcoding them into the frontend.
      WHEN TO USE it:
        - Use it from the admin content-page list and editor surfaces.
      WHEN NOT TO USE it:
        - Do not use it as the public route source of truth.
      WHAT CAN GO WRONG:
        - Database reads can fail.
      WHAT COMES NEXT:
        - Category editing can later reuse the same table and catalog shape.

    TESTS:
      - returns_live_original_category_rows

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORIES_CATALOG_READ_FAILED:
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
                        category.id,
                        category.category_key,
                        category.category_name,
                        category.category_description,
                        category.category_slug,
                        category.language_id,
                        category.created_at_ts_ms,
                        category.updated_at_ts_ms,
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native,
                        language.is_rtl
                    FROM stephen_dcx_content_page_categories AS category
                    JOIN stephen_dcx_languages AS language
                      ON language.id = category.language_id
                    WHERE category.is_live = TRUE
                      AND category.is_original = TRUE
                    ORDER BY category.category_name ASC, category.id ASC
                    """
                )
                category_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORIES_CATALOG_READ_FAILED") from exc

    categories = [
        {
            "category_id": category_row[0],
            "category_key": category_row[1],
            "category_name": category_row[2],
            "category_description": category_row[3],
            "category_slug": category_row[4],
            "language_id": category_row[5],
            "created_at_ts_ms": category_row[6],
            "updated_at_ts_ms": category_row[7],
            "language": {
                "language_code": category_row[8],
                "language_name_en": category_row[9],
                "language_name_native": category_row[10],
                "is_rtl": category_row[11],
            },
        }
        for category_row in category_rows
    ]

    return {
        "categories": categories,
        "total_live_category_count": len(categories),
    }
