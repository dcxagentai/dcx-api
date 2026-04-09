"""
CONTEXT:
This file creates one new live draft content-page row for the DCX admin content surface.
It exists so internal users can start a new page identity in the immutable version model before
autosave and publish operations take over.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from storage.db_config import DB_CONFIG


def create_dcx_admin_content_page_draft_capability(
    category_key: str,
    page_title: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - category_key identifies one current live content-page category row for the requested language.
        - page_title is one non-empty candidate page title.
        - language_code is one non-empty language code.
        - The configured database is reachable.
      postconditions:
        - Creates one new live draft content-page row with a unique `page_key` and `page_slug`.
        - Marks the new row as original and live for the requested language.
        - Initializes markdown/meta fields as empty strings ready for autosave.
      side_effects:
        - inserts one new live content-page row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on the candidate page-key base
      contention_strategy: serialize competing draft creation attempts for the same title/category base through one advisory transaction lock

    NARRATIVE:
      WHY this exists:
        - The admin content surface needs one explicit way to start a new page identity before the
          editor can autosave immutable versions.
      WHEN TO USE it:
        - Use it from the `New page` action in the admin pages list.
      WHEN NOT TO USE it:
        - Do not use it to create translations of existing pages yet.
      WHAT CAN GO WRONG:
        - The requested category can be missing in the requested language.
        - The title can be blank.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The frontend should navigate immediately to the new editor route and continue through autosave.

    TESTS:
      - inserts_new_live_draft_content_page
      - appends_numeric_suffix_when_page_key_or_slug_already_used
      - raises_clear_error_for_blank_title
      - raises_clear_error_for_unknown_category

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_DRAFT_INVALID:
          suggested_action: Enter a page title and choose one valid category before creating the draft.
          common_causes:
            - blank title
            - blank category key
            - blank language code
          recovery_steps:
            - Fill in the required values and retry.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_NOT_FOUND:
          suggested_action: Refresh the categories list and retry with a current category.
          common_causes:
            - stale category selection
            - missing category translation row
          recovery_steps:
            - Reload the category catalog.
            - Retry with one current category.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_DRAFT_CREATE_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - insert failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target page key before retrying

    CODE:
    """
    normalized_category_key = category_key.strip()
    normalized_page_title = page_title.strip()
    normalized_language_code = language_code.strip().lower()
    if (
        normalized_category_key == ""
        or normalized_page_title == ""
        or normalized_language_code == ""
    ):
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_DRAFT_INVALID")

    base_page_identifier = build_dcx_slugified_text_identifier(normalized_page_title)
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"dcx_content_page_draft:{normalized_category_key}:{base_page_identifier}",),
                )
                cursor.execute(
                    """
                    SELECT language.id
                    FROM stephen_dcx_content_page_categories AS category
                    JOIN stephen_dcx_languages AS language
                      ON language.id = category.language_id
                    WHERE category.category_key = %s
                      AND language.language_code = %s
                      AND category.is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_category_key, normalized_language_code),
                )
                language_row = cursor.fetchone()
                if language_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT page_key, page_slug
                    FROM stephen_dcx_content_pages
                    WHERE language_id = %s
                      AND category_key = %s
                    ORDER BY id ASC
                    """,
                    (language_row[0], normalized_category_key),
                )
                existing_rows = cursor.fetchall()
                existing_page_keys = {existing_row[0] for existing_row in existing_rows}
                existing_page_slugs = {existing_row[1] for existing_row in existing_rows}

                next_page_key = base_page_identifier
                next_page_slug = base_page_identifier
                suffix_counter = 2
                while next_page_key in existing_page_keys or next_page_slug in existing_page_slugs:
                    next_page_key = f"{base_page_identifier}-{suffix_counter}"
                    next_page_slug = f"{base_page_identifier}-{suffix_counter}"
                    suffix_counter += 1

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
                        is_original,
                        is_live
                    )
                    VALUES (%s, %s, %s, %s, '', '', '', '', %s, 'draft', TRUE, TRUE)
                    RETURNING id
                    """,
                    (
                        next_page_key,
                        normalized_category_key,
                        language_row[0],
                        normalized_page_title,
                        next_page_slug,
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_DRAFT_CREATE_FAILED") from exc

    return {
        "page_id": inserted_row[0],
        "page_key": next_page_key,
        "page_slug": next_page_slug,
        "language_code": normalized_language_code,
        "publication_status": "draft",
    }
