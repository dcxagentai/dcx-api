"""
CONTEXT:
This file reads the current live published content pages for the DCX public build-time bundle.
It exists so Astro can build public category/page routes from the database-backed content model
instead of from committed snapshots or hardcoded page files.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_public_live_content_pages_bundle(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict[str, list[dict[str, object]]]:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns only current live rows where `publication_status = 'published'`.
        - Groups the resulting content pages by language code.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Public category/page routes should build from the same durable content source that admin edits.
      WHEN TO USE it:
        - Use it from token-gated build-time backend routes only.
      WHEN NOT TO USE it:
        - Do not use it from runtime browser code.
      WHAT CAN GO WRONG:
        - Database reads can fail.
      WHAT COMES NEXT:
        - Astro can statically generate public page routes from the returned bundle.

    TESTS:
      - returns_grouped_published_live_content_pages_bundle

    ERRORS:
      - API_PUBLIC_CONTENT_PAGES_DB_UNAVAILABLE:
          suggested_action: Restore database connectivity and retry the public build.
          common_causes:
            - database outage
            - incorrect backend DB configuration
          recovery_steps:
            - Check backend database connectivity.
            - Retry once the database is healthy.
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
                        language.language_code,
                        page.page_key,
                        page.category_key,
                        page.page_title,
                        page.page_lede,
                        page.page_body_markdown,
                        page.meta_title,
                        page.meta_description,
                        page.page_slug,
                        page.published_at_ts_ms,
                        page.updated_at_ts_ms,
                        COALESCE(category_localized.category_name, category_original.category_name),
                        COALESCE(category_localized.category_slug, category_original.category_slug)
                    FROM stephen_dcx_content_pages AS page
                    JOIN stephen_dcx_languages AS language
                      ON language.id = page.language_id
                    LEFT JOIN stephen_dcx_content_page_categories AS category_localized
                      ON category_localized.category_key = page.category_key
                     AND category_localized.language_id = page.language_id
                     AND category_localized.is_live = TRUE
                    LEFT JOIN stephen_dcx_content_page_categories AS category_original
                      ON category_original.category_key = page.category_key
                     AND category_original.is_original = TRUE
                     AND category_original.is_live = TRUE
                    WHERE page.is_live = TRUE
                      AND page.publication_status = 'published'
                    ORDER BY
                        language.language_code ASC,
                        COALESCE(category_localized.category_slug, category_original.category_slug) ASC,
                        page.page_slug ASC,
                        page.id ASC
                    """
                )
                page_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_CONTENT_PAGES_DB_UNAVAILABLE") from exc

    bundle: dict[str, list[dict[str, object]]] = {}
    for page_row in page_rows:
        language_code = page_row[0]
        bundle.setdefault(language_code, []).append(
            {
                "page_key": page_row[1],
                "category_key": page_row[2],
                "page_title": page_row[3],
                "page_lede": page_row[4],
                "page_body_markdown": page_row[5],
                "meta_title": page_row[6],
                "meta_description": page_row[7],
                "page_slug": page_row[8],
                "published_at_ts_ms": page_row[9],
                "updated_at_ts_ms": page_row[10],
                "category_name": page_row[11],
                "category_slug": page_row[12],
            }
        )

    return bundle
