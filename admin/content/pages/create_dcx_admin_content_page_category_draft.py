"""
CONTEXT:
This file creates one new live original content-page category row for the DCX admin CMS.
It exists so the admin content workflow can add new public editorial categories before translated
rows or content pages are created beneath them.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from storage.db_config import DB_CONFIG


def create_dcx_admin_content_page_category_draft_capability(
    category_name: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - category_name is non-empty.
        - language_code identifies one supported language.
        - The configured database is reachable.
      postconditions:
        - Creates one new live original category row.
        - Uses the slugified category name as both stable category key and initial public slug.
      side_effects:
        - inserts one new live category row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin CMS needs one explicit `New category` action before category editing takes over.
      WHEN TO USE it:
        - Use it from the page-category list only.
      WHEN NOT TO USE it:
        - Do not use it to create translations of existing categories.
      WHAT CAN GO WRONG:
        - The name can be blank.
        - The target language can be invalid.
        - The derived category key/slug can already exist.
      WHAT COMES NEXT:
        - The frontend should navigate to the editor route for the returned category key and language.

    TESTS:
      - covered_indirectly_by_admin_content_page_category_create_draft_route_test

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DRAFT_INVALID:
          suggested_action: Enter one category name and retry.
          common_causes:
            - blank name
            - blank language code
            - duplicate category key
          recovery_steps:
            - Choose one distinct category name.
            - Retry the request.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DRAFT_CREATE_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - insert failure
          recovery_steps:
            - Verify backend/database health.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    normalized_category_name = category_name.strip()
    normalized_language_code = language_code.strip().lower()
    normalized_category_key = build_dcx_slugified_text_identifier(normalized_category_name)
    if (
        normalized_category_name == ""
        or normalized_language_code == ""
        or normalized_category_key == ""
    ):
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DRAFT_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_languages
                    WHERE language_code = %s
                    LIMIT 1
                    """,
                    (normalized_language_code,),
                )
                language_row = cursor.fetchone()
                if language_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DRAFT_INVALID")

                cursor.execute(
                    """
                    SELECT 1
                    FROM stephen_dcx_content_page_categories
                    WHERE category_key = %s
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_category_key,),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DRAFT_INVALID")

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_content_page_categories (
                        category_key,
                        language_id,
                        category_name,
                        category_description,
                        category_slug,
                        is_original,
                        is_live
                    )
                    VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
                    RETURNING id
                    """,
                    (
                        normalized_category_key,
                        language_row[0],
                        normalized_category_name,
                        "",
                        normalized_category_key,
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DRAFT_CREATE_FAILED") from exc

    return {
        "category_id": inserted_row[0],
        "category_key": normalized_category_key,
        "language_code": normalized_language_code,
    }
