"""
CONTEXT:
This file publishes all existing draft translation rows for one DCX content page.
It exists so admins can translate a source page, then promote the generated draft language rows
to public-ready published rows without opening every language one by one.
"""

from __future__ import annotations

from time import time
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def publish_dcx_admin_content_page_translated_drafts_capability(
    page_key: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - page_key is one non-empty stable content-page identity.
        - The configured database is reachable.
      postconditions:
        - Publishes every current live non-original draft row for the page key.
        - Preserves immutable version history by retiring each draft row and inserting a published successor row.
        - Returns a no-op when the page exists but has no draft translations.
      side_effects:
        - updates zero or more current live content-page translation rows to `is_live = false`
        - inserts zero or more published live content-page translation rows
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_admin_content_page_translated_drafts_publish:{page_key}
      locks:
        - row-level locks on matching current live draft translation rows
      contention_strategy: serialize competing bulk publishes through `FOR UPDATE OF page`; a retry after the first success returns no-op

    NARRATIVE:
      WHY this exists:
        - AI page translation intentionally creates drafts first, but admins need one simple action to publish
          the translated set for public route testing and launch.
      WHEN TO USE it:
        - Use it from the admin page editor after translation jobs have completed and draft translations exist.
      WHEN NOT TO USE it:
        - Do not use it for publishing the source/original row or for creating missing translations.
      WHAT CAN GO WRONG:
        - The page key may be stale or missing.
        - A draft translation may now conflict with another live row in the same language/category/slug.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The public-site publish flow can rebuild Astro so the newly published language routes are generated.

    TESTS:
      - publishes_existing_translated_draft_rows
      - returns_noop_when_page_exists_without_draft_translations

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_PUBLISH_INVALID:
          suggested_action: Reopen the page from the pages list and retry.
          common_causes:
            - blank page key
          recovery_steps:
            - Refresh the editor route.
            - Retry from one valid page row.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_NOT_FOUND:
          suggested_action: Return to the pages list and reopen the current page.
          common_causes:
            - stale page key
            - page was archived or deleted
          recovery_steps:
            - Reload the pages catalog.
            - Retry from a current page row.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_CONFLICT:
          suggested_action: Inspect the draft translation slugs and retry after resolving conflicts.
          common_causes:
            - another live row already uses the same category, language, and slug
          recovery_steps:
            - Open the affected language row.
            - Change its slug or archive the conflicting page.
            - Retry the bulk publish.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_PUBLISH_FAILED:
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
          rollback_operation: inspect the page key's live translated rows before retrying

    CODE:
    """
    normalized_page_key = page_key.strip()
    if normalized_page_key == "":
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_PUBLISH_INVALID")

    connect = connect_to_database or psycopg2.connect
    published_at_ts_ms = int(time() * 1000)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        page.id,
                        page.page_key,
                        page.category_key,
                        page.language_id,
                        page.page_title,
                        page.page_lede,
                        page.page_body_markdown,
                        page.meta_title,
                        page.meta_description,
                        page.page_slug,
                        page.is_original,
                        page.translation_of_id,
                        language.language_code
                    FROM stephen_dcx_content_pages AS page
                    JOIN stephen_dcx_languages AS language
                      ON language.id = page.language_id
                    WHERE page.page_key = %s
                      AND page.is_live = TRUE
                      AND page.is_original = FALSE
                      AND page.publication_status = 'draft'
                    ORDER BY language.id ASC, page.id ASC
                    FOR UPDATE OF page
                    """,
                    (normalized_page_key,),
                )
                draft_rows = cursor.fetchall()

                if not draft_rows:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM stephen_dcx_content_pages
                        WHERE page_key = %s
                          AND is_live = TRUE
                        LIMIT 1
                        """,
                        (normalized_page_key,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_NOT_FOUND")
                    return {
                        "page_key": normalized_page_key,
                        "published_count": 0,
                        "published_languages": [],
                        "published_page_ids": [],
                        "was_noop": True,
                    }

                published_languages = []
                published_page_ids = []
                previous_page_ids = []

                for draft_row in draft_rows:
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
                        (draft_row[2], draft_row[3], draft_row[9], draft_row[0]),
                    )
                    if cursor.fetchone() is not None:
                        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_CONFLICT")

                    cursor.execute(
                        """
                        UPDATE stephen_dcx_content_pages
                        SET
                            is_live = FALSE,
                            updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                        WHERE id = %s
                        """,
                        (draft_row[0],),
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
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'published', %s, %s, TRUE, %s, %s)
                        RETURNING id
                        """,
                        (
                            draft_row[1],
                            draft_row[2],
                            draft_row[3],
                            draft_row[4],
                            draft_row[5] or "",
                            draft_row[6] or "",
                            draft_row[7] or "",
                            draft_row[8] or "",
                            draft_row[9],
                            published_at_ts_ms,
                            draft_row[10],
                            draft_row[0],
                            draft_row[11],
                        ),
                    )
                    inserted_row = cursor.fetchone()
                    previous_page_ids.append(draft_row[0])
                    published_page_ids.append(inserted_row[0])
                    published_languages.append(draft_row[12])
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_PUBLISH_FAILED") from exc

    return {
        "page_key": normalized_page_key,
        "published_count": len(published_page_ids),
        "published_languages": published_languages,
        "published_page_ids": published_page_ids,
        "previous_page_ids": previous_page_ids,
        "was_noop": False,
    }
