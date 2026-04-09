"""
CONTEXT:
This file saves one new immutable live content-page category row version for the DCX admin CMS.
It exists so category editing can follow the same durable version model as pages, strings, and emails
without mutating rows in place.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from storage.db_config import DB_CONFIG


def save_dcx_admin_live_content_page_category_row_version_capability(
    target_category_id: int,
    next_category_name: str,
    next_category_description: str,
    next_category_slug: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - target_category_id identifies one current live category row.
        - next_category_name is non-empty.
        - The configured database is reachable.
      postconditions:
        - Saves one new immutable live category row version when content changed.
        - Preserves category identity, language, and original/translation links.
        - Returns a stable no-op when nothing changed.
      side_effects:
        - updates one current live category row to `is_live = false`
        - inserts one new live category row when content changed
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Categories should follow the same immutable editing model as the rest of the CMS.
      WHEN TO USE it:
        - Use it from the admin page-category editor autosave/manual save flow.
      WHEN NOT TO USE it:
        - Do not use it to create a new category identity.
      WHAT CAN GO WRONG:
        - The target row can be stale.
        - The category name can be blank.
        - The slug can conflict with another live category in the same language.
      WHAT COMES NEXT:
        - Public publish status and public build reads can pick up category changes after the next publish.

    TESTS:
      - covered_indirectly_by_admin_content_page_category_save_route_test

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_SAVE_INVALID:
          suggested_action: Use a non-empty category name and one unique slug before retrying.
          common_causes:
            - blank category name
            - conflicting slug
          recovery_steps:
            - Correct the category fields.
            - Retry from the current live row.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_LIVE_ROW_NOT_FOUND:
          suggested_action: Refresh the category editor and retry from the current live row.
          common_causes:
            - stale category id
            - another save already created a new live version
          recovery_steps:
            - Reload the editor detail.
            - Retry from the new live row.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_SAVE_FAILED:
          suggested_action: Retry once the backend/database are healthy.
          common_causes:
            - database unavailable
            - write failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_category_name = next_category_name.strip()
    normalized_category_description = next_category_description.strip()
    normalized_category_slug = (
        build_dcx_slugified_text_identifier(next_category_slug)
        if next_category_slug.strip() != ""
        else build_dcx_slugified_text_identifier(normalized_category_name)
    )

    if (
        not isinstance(target_category_id, int)
        or target_category_id <= 0
        or normalized_category_name == ""
        or normalized_category_slug == ""
    ):
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_SAVE_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        category_key,
                        language_id,
                        category_name,
                        category_description,
                        category_slug,
                        is_original,
                        translation_of_id
                    FROM stephen_dcx_content_page_categories
                    WHERE id = %s
                      AND is_live = TRUE
                    FOR UPDATE
                    """,
                    (target_category_id,),
                )
                existing_live_row = cursor.fetchone()
                if existing_live_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_LIVE_ROW_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT 1
                    FROM stephen_dcx_content_page_categories
                    WHERE language_id = %s
                      AND category_slug = %s
                      AND is_live = TRUE
                      AND id <> %s
                    LIMIT 1
                    """,
                    (
                        existing_live_row[2],
                        normalized_category_slug,
                        existing_live_row[0],
                    ),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_SAVE_INVALID")

                if (
                    existing_live_row[3] == normalized_category_name
                    and (existing_live_row[4] or "") == normalized_category_description
                    and existing_live_row[5] == normalized_category_slug
                ):
                    return {
                        "category_id": existing_live_row[0],
                        "was_noop": True,
                    }

                cursor.execute(
                    """
                    UPDATE stephen_dcx_content_page_categories
                    SET
                        is_live = FALSE,
                        updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    WHERE id = %s
                    """,
                    (existing_live_row[0],),
                )

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_content_page_categories (
                        category_key,
                        language_id,
                        category_name,
                        category_description,
                        category_slug,
                        is_original,
                        is_live,
                        version_of_id,
                        translation_of_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                    RETURNING id
                    """,
                    (
                        existing_live_row[1],
                        existing_live_row[2],
                        normalized_category_name,
                        normalized_category_description,
                        normalized_category_slug,
                        existing_live_row[6],
                        existing_live_row[0],
                        existing_live_row[7],
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_SAVE_FAILED") from exc

    return {
        "category_id": inserted_row[0],
        "previous_category_id": existing_live_row[0],
        "was_noop": False,
    }
