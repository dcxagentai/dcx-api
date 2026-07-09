"""
CONTEXT:
This file stores validated AI translation results into the existing DCX content tables.
It preserves the current immutable live-row model: existing live translations are replaced by a
new live version, while missing translations are inserted as first live translated rows.
"""

from __future__ import annotations

from typing import Any

from admin.translations.build_dcx_admin_ai_translation_hash import (
    build_dcx_admin_ai_translation_content_hash,
)
from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from emails.validate_live_email_template_placeholder_contract import (
    validate_live_email_template_placeholder_contract_capability,
)


def store_dcx_admin_ai_translation_result(
    cursor: Any,
    source_payload: dict,
    target_language: dict,
    translated_fields: dict[str, str],
) -> dict:
    entity_kind = source_payload["entity_kind"]
    if entity_kind == "content_page":
        return _store_content_page_translation(
            cursor=cursor,
            source_payload=source_payload,
            target_language=target_language,
            translated_fields=translated_fields,
        )
    if entity_kind == "content_page_category":
        return _store_content_page_category_translation(
            cursor=cursor,
            source_payload=source_payload,
            target_language=target_language,
            translated_fields=translated_fields,
        )
    if entity_kind in {"email", "newsletter"}:
        return _store_email_translation(
            cursor=cursor,
            source_payload=source_payload,
            target_language=target_language,
            translated_fields=translated_fields,
        )
    raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_INVALID")


def _store_content_page_translation(
    cursor: Any,
    source_payload: dict,
    target_language: dict,
    translated_fields: dict[str, str],
) -> dict:
    page_key = source_payload["entity_key"]
    target_language_id = target_language["language_id"]
    translated_page_slug = build_dcx_slugified_text_identifier(
        translated_fields.get("page_slug")
        or translated_fields.get("page_title")
        or source_payload["stable_fields"]["page_slug"]
    )

    cursor.execute(
        """
        SELECT id
        FROM stephen_dcx_content_pages
        WHERE page_key = %s
          AND is_original = TRUE
          AND is_live = TRUE
        LIMIT 1
        """,
        (page_key,),
    )
    original_row = cursor.fetchone()
    translation_of_id = original_row[0] if original_row is not None else source_payload["source_row_id"]

    cursor.execute(
        """
        SELECT
            id,
            category_key,
            page_slug,
            publication_status,
            published_at_ts_ms,
            is_original,
            translation_of_id
        FROM stephen_dcx_content_pages
        WHERE page_key = %s
          AND language_id = %s
          AND is_live = TRUE
        FOR UPDATE
        """,
        (page_key, target_language_id),
    )
    existing_target_row = cursor.fetchone()

    if existing_target_row is None:
        stored_page_slug = _build_unique_content_page_slug(
            cursor=cursor,
            category_key=source_payload["category_key"],
            language_id=target_language_id,
            candidate_slug=translated_page_slug,
            exclude_page_id=None,
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
                translation_of_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', NULL, FALSE, TRUE, %s)
            RETURNING id
            """,
            (
                page_key,
                source_payload["category_key"],
                target_language_id,
                translated_fields["page_title"],
                translated_fields["page_lede"],
                translated_fields["page_body_markdown"],
                translated_fields["meta_title"],
                translated_fields["meta_description"],
                stored_page_slug,
                translation_of_id,
            ),
        )
        target_row_id = cursor.fetchone()[0]
        was_existing_versioned = False
    else:
        stored_page_slug = _build_unique_content_page_slug(
            cursor=cursor,
            category_key=existing_target_row[1],
            language_id=target_language_id,
            candidate_slug=translated_page_slug,
            exclude_page_id=existing_target_row[0],
        )
        cursor.execute(
            """
            UPDATE stephen_dcx_content_pages
            SET is_live = FALSE,
                updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
            WHERE id = %s
            """,
            (existing_target_row[0],),
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, TRUE, %s, %s)
            RETURNING id
            """,
            (
                page_key,
                existing_target_row[1],
                target_language_id,
                translated_fields["page_title"],
                translated_fields["page_lede"],
                translated_fields["page_body_markdown"],
                translated_fields["meta_title"],
                translated_fields["meta_description"],
                stored_page_slug,
                existing_target_row[3],
                existing_target_row[4],
                existing_target_row[0],
                existing_target_row[6] or translation_of_id,
            ),
        )
        target_row_id = cursor.fetchone()[0]
        was_existing_versioned = True

    stored_translated_fields = {
        **translated_fields,
        "page_slug": stored_page_slug,
    }
    return {
        "target_row_id": target_row_id,
        "target_content_hash": build_dcx_admin_ai_translation_content_hash(stored_translated_fields),
        "was_existing_versioned": was_existing_versioned,
    }


def _store_content_page_category_translation(
    cursor: Any,
    source_payload: dict,
    target_language: dict,
    translated_fields: dict[str, str],
) -> dict:
    category_key = source_payload["entity_key"]
    target_language_id = target_language["language_id"]
    translated_category_slug = build_dcx_slugified_text_identifier(
        translated_fields.get("category_slug")
        or translated_fields.get("category_name")
        or source_payload["stable_fields"]["category_slug"]
    )

    cursor.execute(
        """
        SELECT id
        FROM stephen_dcx_content_page_categories
        WHERE category_key = %s
          AND is_original = TRUE
          AND is_live = TRUE
        LIMIT 1
        """,
        (category_key,),
    )
    original_row = cursor.fetchone()
    translation_of_id = original_row[0] if original_row is not None else source_payload["source_row_id"]

    cursor.execute(
        """
        SELECT
            id,
            category_slug,
            is_original,
            translation_of_id
        FROM stephen_dcx_content_page_categories
        WHERE category_key = %s
          AND language_id = %s
          AND is_live = TRUE
        FOR UPDATE
        """,
        (category_key, target_language_id),
    )
    existing_target_row = cursor.fetchone()

    if existing_target_row is None:
        stored_category_slug = _build_unique_content_page_category_slug(
            cursor=cursor,
            language_id=target_language_id,
            candidate_slug=translated_category_slug,
            exclude_category_id=None,
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
                translation_of_id
            )
            VALUES (%s, %s, %s, %s, %s, FALSE, TRUE, %s)
            RETURNING id
            """,
            (
                category_key,
                target_language_id,
                translated_fields["category_name"],
                translated_fields["category_description"],
                stored_category_slug,
                translation_of_id,
            ),
        )
        target_row_id = cursor.fetchone()[0]
        was_existing_versioned = False
    else:
        stored_category_slug = _build_unique_content_page_category_slug(
            cursor=cursor,
            language_id=target_language_id,
            candidate_slug=translated_category_slug,
            exclude_category_id=existing_target_row[0],
        )
        cursor.execute(
            """
            UPDATE stephen_dcx_content_page_categories
            SET is_live = FALSE,
                updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
            WHERE id = %s
            """,
            (existing_target_row[0],),
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
            VALUES (%s, %s, %s, %s, %s, FALSE, TRUE, %s, %s)
            RETURNING id
            """,
            (
                category_key,
                target_language_id,
                translated_fields["category_name"],
                translated_fields["category_description"],
                stored_category_slug,
                existing_target_row[0],
                existing_target_row[3] or translation_of_id,
            ),
        )
        target_row_id = cursor.fetchone()[0]
        was_existing_versioned = True

    stored_translated_fields = {
        **translated_fields,
        "category_slug": stored_category_slug,
    }
    return {
        "target_row_id": target_row_id,
        "target_content_hash": build_dcx_admin_ai_translation_content_hash(stored_translated_fields),
        "was_existing_versioned": was_existing_versioned,
    }


def _store_email_translation(
    cursor: Any,
    source_payload: dict,
    target_language: dict,
    translated_fields: dict[str, str],
) -> dict:
    email_key = source_payload["entity_key"]
    email_type = source_payload["email_type"]
    target_language_id = target_language["language_id"]

    validate_live_email_template_placeholder_contract_capability(
        email_type=email_type,
        email_key=email_key,
        email_subject=translated_fields["email_subject"],
        email_body=translated_fields["email_body"],
    )

    cursor.execute(
        """
        SELECT id
        FROM stephen_dcx_emails
        WHERE email_type = %s
          AND email_key = %s
          AND is_original = TRUE
          AND is_live = TRUE
        LIMIT 1
        """,
        (email_type, email_key),
    )
    original_row = cursor.fetchone()
    translation_of_id = original_row[0] if original_row is not None else source_payload["source_row_id"]

    cursor.execute(
        """
        SELECT
            id,
            is_original,
            translation_of_id
        FROM stephen_dcx_emails
        WHERE email_type = %s
          AND email_key = %s
          AND language_id = %s
          AND is_live = TRUE
        FOR UPDATE
        """,
        (email_type, email_key, target_language_id),
    )
    existing_target_row = cursor.fetchone()

    if existing_target_row is None:
        cursor.execute(
            """
            INSERT INTO stephen_dcx_emails (
                email_type,
                email_key,
                language_id,
                email_subject,
                email_body,
                is_original,
                is_live,
                translation_of_id
            )
            VALUES (%s, %s, %s, %s, %s, FALSE, TRUE, %s)
            RETURNING id
            """,
            (
                email_type,
                email_key,
                target_language_id,
                translated_fields["email_subject"],
                translated_fields["email_body"],
                translation_of_id,
            ),
        )
        target_row_id = cursor.fetchone()[0]
        was_existing_versioned = False
    else:
        cursor.execute(
            """
            UPDATE stephen_dcx_emails
            SET is_live = FALSE,
                updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
            WHERE id = %s
            """,
            (existing_target_row[0],),
        )
        cursor.execute(
            """
            INSERT INTO stephen_dcx_emails (
                email_type,
                email_key,
                language_id,
                email_subject,
                email_body,
                is_original,
                is_live,
                version_of_id,
                translation_of_id
            )
            VALUES (%s, %s, %s, %s, %s, FALSE, TRUE, %s, %s)
            RETURNING id
            """,
            (
                email_type,
                email_key,
                target_language_id,
                translated_fields["email_subject"],
                translated_fields["email_body"],
                existing_target_row[0],
                existing_target_row[2] or translation_of_id,
            ),
        )
        target_row_id = cursor.fetchone()[0]
        was_existing_versioned = True

    return {
        "target_row_id": target_row_id,
        "target_content_hash": build_dcx_admin_ai_translation_content_hash(translated_fields),
        "was_existing_versioned": was_existing_versioned,
    }


def _build_unique_content_page_slug(
    cursor: Any,
    category_key: str,
    language_id: int,
    candidate_slug: str,
    exclude_page_id: int | None,
) -> str:
    base_slug = build_dcx_slugified_text_identifier(candidate_slug)
    cursor.execute(
        """
        SELECT page_slug
        FROM stephen_dcx_content_pages
        WHERE category_key = %s
          AND language_id = %s
          AND is_live = TRUE
          AND (%s IS NULL OR id <> %s)
        """,
        (category_key, language_id, exclude_page_id, exclude_page_id),
    )
    existing_slugs = {str(row[0]) for row in cursor.fetchall()}
    return _build_unique_slug_from_existing_slugs(base_slug=base_slug, existing_slugs=existing_slugs)


def _build_unique_content_page_category_slug(
    cursor: Any,
    language_id: int,
    candidate_slug: str,
    exclude_category_id: int | None,
) -> str:
    base_slug = build_dcx_slugified_text_identifier(candidate_slug)
    cursor.execute(
        """
        SELECT category_slug
        FROM stephen_dcx_content_page_categories
        WHERE language_id = %s
          AND is_live = TRUE
          AND (%s IS NULL OR id <> %s)
        """,
        (language_id, exclude_category_id, exclude_category_id),
    )
    existing_slugs = {str(row[0]) for row in cursor.fetchall()}
    return _build_unique_slug_from_existing_slugs(base_slug=base_slug, existing_slugs=existing_slugs)


def _build_unique_slug_from_existing_slugs(base_slug: str, existing_slugs: set[str]) -> str:
    if base_slug not in existing_slugs:
        return base_slug

    suffix_counter = 2
    while f"{base_slug}-{suffix_counter}" in existing_slugs:
        suffix_counter += 1
    return f"{base_slug}-{suffix_counter}"
