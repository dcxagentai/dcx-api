"""
CONTEXT:
This file creates one first live translation row for an existing DCX content page identity.
It exists so the admin pages editor can demonstrate multilingual page mechanics before any real
translation workflow polish or translated public category model is added.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def create_dcx_admin_content_page_translation_capability(
    page_key: str,
    source_language_code: str,
    target_language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - page_key identifies one current live content-page identity.
        - source_language_code identifies one current live source row for that page.
        - target_language_code identifies one supported language distinct from the source language.
        - The configured database is reachable.
      postconditions:
        - Creates one new live translated content-page row if it does not already exist.
        - Copies current source content into the new target-language row as a starting translation draft.
        - Links the new row back to the live original row through `translation_of_id`.
      side_effects:
        - inserts one new live translated content-page row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on page key plus target language
      contention_strategy: serialize competing translation-create attempts for the same page/language pair

    NARRATIVE:
      WHY this exists:
        - Clients should already see that pages are truly multilingual-capable even before real translated content is written.
      WHEN TO USE it:
        - Use it from the admin pages editor when one missing language translation is created from the source page.
      WHEN NOT TO USE it:
        - Do not use it to overwrite an existing translation.
        - Do not use it for public page rendering.
      WHAT CAN GO WRONG:
        - The source row can be missing.
        - The target translation may already exist.
        - The target language may be invalid.
      WHAT COMES NEXT:
        - The new translated row opens in the same editor route shape and autosave can take over from there.

    TESTS:
      - creates_translation_row_from_source_page
      - raises_clear_error_when_translation_already_exists

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_INVALID:
          suggested_action: Choose one valid source and target language pair and retry.
          common_causes:
            - blank page key
            - blank language code
            - same source and target language
          recovery_steps:
            - Reopen the page from the catalog.
            - Retry with one different target language.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_SOURCE_NOT_FOUND:
          suggested_action: Refresh the pages list and reopen the source page before retrying.
          common_causes:
            - stale source route
            - source live row no longer exists
          recovery_steps:
            - Reload the current live page row.
            - Retry from the editor.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_ALREADY_EXISTS:
          suggested_action: Open the existing translation instead of creating a new one.
          common_causes:
            - target-language row already exists
          recovery_steps:
            - Open the existing translation from the translation list.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_CREATE_FAILED:
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
          rollback_operation: inspect the target page/language row before retrying

    CODE:
    """
    normalized_page_key = page_key.strip()
    normalized_source_language_code = source_language_code.strip().lower()
    normalized_target_language_code = target_language_code.strip().lower()
    if (
        normalized_page_key == ""
        or normalized_source_language_code == ""
        or normalized_target_language_code == ""
        or normalized_source_language_code == normalized_target_language_code
    ):
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (
                        f"dcx_content_page_translation:{normalized_page_key}:{normalized_target_language_code}",
                    ),
                )
                cursor.execute(
                    """
                    SELECT
                        source_page.id,
                        source_page.page_key,
                        source_page.category_key,
                        source_page.page_title,
                        source_page.page_lede,
                        source_page.page_body_markdown,
                        source_page.meta_title,
                        source_page.meta_description,
                        source_page.page_slug,
                        source_page.publication_status,
                        source_page.published_at_ts_ms
                    FROM stephen_dcx_content_pages AS source_page
                    INNER JOIN stephen_dcx_languages AS source_language
                      ON source_language.id = source_page.language_id
                    WHERE source_page.page_key = %s
                      AND source_page.is_live = TRUE
                      AND source_language.language_code = %s
                    LIMIT 1
                    """,
                    (normalized_page_key, normalized_source_language_code),
                )
                source_row = cursor.fetchone()
                if source_row is None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_SOURCE_NOT_FOUND")

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
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_INVALID")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_content_pages
                    WHERE page_key = %s
                      AND language_id = %s
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_page_key, target_language_row[0]),
                )
                existing_translation_row = cursor.fetchone()
                if existing_translation_row is not None:
                    raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_ALREADY_EXISTS")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_content_pages
                    WHERE page_key = %s
                      AND is_original = TRUE
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_page_key,),
                )
                original_row = cursor.fetchone()
                translation_of_id = original_row[0] if original_row is not None else source_row[0]

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
                        translation_of_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, TRUE, %s)
                    RETURNING id
                    """,
                    (
                        source_row[1],
                        source_row[2],
                        target_language_row[0],
                        source_row[3],
                        source_row[4],
                        source_row[5],
                        source_row[6],
                        source_row[7],
                        source_row[8],
                        source_row[9],
                        source_row[10],
                        translation_of_id,
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_CREATE_FAILED") from exc

    return {
        "page_id": inserted_row[0],
        "page_key": normalized_page_key,
        "language_code": normalized_target_language_code,
    }
