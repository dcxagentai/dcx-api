"""
CONTEXT:
This file creates one first live translation row for an existing DCX content-page category identity.
It exists so the admin category editor can demonstrate multilingual category mechanics before the
category surface receives deeper polish.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def create_dcx_admin_content_page_category_translation_capability(
    category_key: str,
    source_language_code: str,
    target_language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - category_key identifies one category identity.
        - source_language_code and target_language_code identify different supported languages.
        - The configured database is reachable.
      postconditions:
        - Creates one new live translated category row if it does not already exist.
        - Copies the source row as the starting translated draft.
      side_effects:
        - inserts one new live category translation row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Clients should be able to see categories follow the same original/translation model as pages and newsletters.
      WHEN TO USE it:
        - Use it from the admin page-category editor when creating a missing translation row.
      WHEN NOT TO USE it:
        - Do not use it to overwrite an existing translation.
      WHAT CAN GO WRONG:
        - The source row can be missing.
        - The target language can already exist.
        - The target language can be invalid.
      WHAT COMES NEXT:
        - The new translated category row opens in the same editor route and whole-document save takes over.

    TESTS:
      - covered_indirectly_by_admin_content_page_category_translation_route_test

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_INVALID:
          suggested_action: Choose one valid source and target language pair and retry.
          common_causes:
            - blank category key
            - blank language code
            - same source and target language
          recovery_steps:
            - Reopen the category from the catalog.
            - Retry with one different target language.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_SOURCE_NOT_FOUND:
          suggested_action: Refresh the categories list and reopen the source row before retrying.
          common_causes:
            - stale source route
            - source live row no longer exists
          recovery_steps:
            - Reload the categories catalog.
            - Retry from the editor.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_ALREADY_EXISTS:
          suggested_action: Open the existing translation instead of creating a new one.
          common_causes:
            - target-language row already exists
          recovery_steps:
            - Open the existing translation from the translation list.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_CREATE_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - insert failure
          recovery_steps:
            - Verify backend/database health.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_category_key = category_key.strip()
    normalized_source_language_code = source_language_code.strip().lower()
    normalized_target_language_code = target_language_code.strip().lower()
    if (
        normalized_category_key == ""
        or normalized_source_language_code == ""
        or normalized_target_language_code == ""
        or normalized_source_language_code == normalized_target_language_code
    ):
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (
                        f"dcx_content_page_category_translation:{normalized_category_key}:{normalized_target_language_code}",
                    ),
                )
                cursor.execute(
                    """
                    SELECT
                        category.id,
                        category.category_key,
                        category.category_name,
                        category.category_description,
                        category.category_slug
                    FROM stephen_dcx_content_page_categories AS category
                    JOIN stephen_dcx_languages AS language
                      ON language.id = category.language_id
                    WHERE category.category_key = %s
                      AND category.is_live = TRUE
                      AND language.language_code = %s
                    LIMIT 1
                    """,
                    (normalized_category_key, normalized_source_language_code),
                )
                source_row = cursor.fetchone()
                if source_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_SOURCE_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_languages
                    WHERE language_code = %s
                    LIMIT 1
                    """,
                    (normalized_target_language_code,),
                )
                target_language_row = cursor.fetchone()
                if target_language_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_INVALID")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_content_page_categories
                    WHERE category_key = %s
                      AND language_id = %s
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_category_key, target_language_row[0]),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_ALREADY_EXISTS")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_content_page_categories
                    WHERE category_key = %s
                      AND is_original = TRUE
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_category_key,),
                )
                original_row = cursor.fetchone()
                translation_of_id = original_row[0] if original_row is not None else source_row[0]

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
                        translation_of_id
                    )
                    VALUES (%s, %s, %s, %s, %s, FALSE, TRUE, %s)
                    RETURNING id
                    """,
                    (
                        source_row[1],
                        target_language_row[0],
                        source_row[2],
                        source_row[3],
                        source_row[4],
                        translation_of_id,
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_CREATE_FAILED") from exc

    return {
        "category_id": inserted_row[0],
        "category_key": normalized_category_key,
        "language_code": normalized_target_language_code,
    }
