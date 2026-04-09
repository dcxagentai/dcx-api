"""
CONTEXT:
This file saves one new immutable live content-page row version for the DCX admin content surface.
It exists so page editing can autosave durable draft/published/archived content without mutating
rows in place and without losing the version trail already established elsewhere in the project.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from storage.db_config import DB_CONFIG


def save_dcx_admin_live_content_page_row_version_capability(
    target_page_id: int,
    next_category_key: str,
    next_page_title: str,
    next_page_lede: str,
    next_page_body_markdown: str,
    next_meta_title: str,
    next_meta_description: str,
    next_page_slug: str,
    next_publication_status: str,
    next_published_at_ts_ms: int | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - target_page_id identifies one current live row in `stephen_dcx_content_pages`.
        - next_category_key and next_page_title are non-empty candidate values.
        - next_publication_status is one of `draft`, `published`, or `archived`.
        - The configured database is reachable.
      postconditions:
        - Saves one new immutable live row version when page content or workflow state changed.
        - Turns the previous live row off and links the new row through `version_of_id`.
        - Preserves page identity, language identity, original/translation identity, and live uniqueness.
        - Returns a stable no-op result when nothing changed.
      side_effects:
        - updates one current live content-page row to `is_live = false`
        - inserts one new live content-page row when content changed
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_admin_live_content_page_row_version:{target_page_id}:{next_category_key}:{next_page_title}:{next_page_slug}:{next_publication_status}:{next_published_at_ts_ms}
      locks:
        - one row-level lock on `stephen_dcx_content_pages.id`
      contention_strategy: serialize competing saves through a `FOR UPDATE` lock on the target live row and reject stale non-live ids

    NARRATIVE:
      WHY this exists:
        - The admin page editor should autosave safely while preserving the exact durable version model
          already used for multilingual strings and emails.
      WHEN TO USE it:
        - Use it from admin page draft autosave, publish, and archive flows.
      WHEN NOT TO USE it:
        - Do not use it to create a brand-new page identity.
      WHAT CAN GO WRONG:
        - The target row can be stale.
        - Required fields can be blank.
        - Category identity can be invalid for this language.
        - A slug conflict can already exist on another live row.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The public build bundle can read only `published` live rows after publish status is updated.

    TESTS:
      - inserts_new_live_page_version_when_content_changes
      - returns_noop_when_page_content_is_unchanged
      - raises_clear_error_for_missing_live_row
      - raises_clear_error_for_invalid_category
      - raises_clear_error_for_conflicting_live_slug

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_SAVE_INVALID:
          suggested_action: Use a non-empty title, one valid category, and one unique slug before retrying.
          common_causes:
            - blank title
            - blank category key
            - invalid publication status
            - conflicting slug
          recovery_steps:
            - Correct the page fields.
            - Retry from the current live row.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_LIVE_ROW_NOT_FOUND:
          suggested_action: Refresh the page editor and retry from the current live row.
          common_causes:
            - stale page id
            - another save already created a new live version
          recovery_steps:
            - Reload the editor detail.
            - Retry from the new live row if needed.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_NOT_FOUND:
          suggested_action: Refresh the categories list and retry with one valid category.
          common_causes:
            - stale category selection
            - missing category translation row
          recovery_steps:
            - Reload the category catalog.
            - Retry with one current category.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_SAVE_FAILED:
          suggested_action: Retry once the backend/database are healthy.
          common_causes:
            - database unavailable
            - write failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target page key before retrying

    CODE:
    """
    normalized_category_key = next_category_key.strip()
    normalized_page_title = next_page_title.strip()
    normalized_page_lede = next_page_lede.strip()
    normalized_page_body_markdown = next_page_body_markdown.strip()
    normalized_meta_title = next_meta_title.strip()
    normalized_meta_description = next_meta_description.strip()
    normalized_page_slug = (
        build_dcx_slugified_text_identifier(next_page_slug)
        if next_page_slug.strip() != ""
        else build_dcx_slugified_text_identifier(normalized_page_title)
    )
    normalized_publication_status = next_publication_status.strip().lower()

    if (
        not isinstance(target_page_id, int)
        or target_page_id <= 0
        or normalized_category_key == ""
        or normalized_page_title == ""
        or normalized_publication_status not in {"draft", "published", "archived"}
    ):
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_SAVE_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        page_key,
                        category_key,
                        language_id,
                        page_title,
                        page_lede,
                        page_body_markdown,
                        meta_title,
                        meta_description,
                        page_slug,
                        publication_status,
                        published_at_ts_ms,
                        is_original,
                        translation_of_id
                    FROM stephen_dcx_content_pages
                    WHERE id = %s
                      AND is_live = TRUE
                    FOR UPDATE
                    """,
                    (target_page_id,),
                )
                existing_live_row = cursor.fetchone()
                if existing_live_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_LIVE_ROW_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT 1
                    FROM stephen_dcx_content_page_categories
                    WHERE category_key = %s
                      AND language_id = %s
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_category_key, existing_live_row[3]),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT 1
                    FROM stephen_dcx_content_pages
                    WHERE category_key = %s
                      AND language_id = %s
                      AND page_slug = %s
                      AND is_live = TRUE
                      AND id <> %s
                    LIMIT 1
                    """,
                    (
                        normalized_category_key,
                        existing_live_row[3],
                        normalized_page_slug,
                        existing_live_row[0],
                    ),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_SAVE_INVALID")

                if (
                    existing_live_row[2] == normalized_category_key
                    and existing_live_row[4] == normalized_page_title
                    and (existing_live_row[5] or "") == normalized_page_lede
                    and (existing_live_row[6] or "") == normalized_page_body_markdown
                    and (existing_live_row[7] or "") == normalized_meta_title
                    and (existing_live_row[8] or "") == normalized_meta_description
                    and existing_live_row[9] == normalized_page_slug
                    and existing_live_row[10] == normalized_publication_status
                    and existing_live_row[11] == next_published_at_ts_ms
                ):
                    return {
                        "page_id": existing_live_row[0],
                        "was_noop": True,
                    }

                cursor.execute(
                    """
                    UPDATE stephen_dcx_content_pages
                    SET
                        is_live = FALSE,
                        updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    WHERE id = %s
                    """,
                    (existing_live_row[0],),
                )

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_content_pages (
                        page_key,
                        category_key,
                        language_id,
                        page_title,
                        page_lede,
                        page_body_markdown,
                        meta_title,
                        meta_description,
                        page_slug,
                        publication_status,
                        published_at_ts_ms,
                        is_original,
                        is_live,
                        version_of_id,
                        translation_of_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                    RETURNING id
                    """,
                    (
                        existing_live_row[1],
                        normalized_category_key,
                        existing_live_row[3],
                        normalized_page_title,
                        normalized_page_lede,
                        normalized_page_body_markdown,
                        normalized_meta_title,
                        normalized_meta_description,
                        normalized_page_slug,
                        normalized_publication_status,
                        next_published_at_ts_ms,
                        existing_live_row[12],
                        existing_live_row[0],
                        existing_live_row[13],
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_SAVE_FAILED") from exc

    return {
        "page_id": inserted_row[0],
        "previous_page_id": existing_live_row[0],
        "was_noop": False,
    }
