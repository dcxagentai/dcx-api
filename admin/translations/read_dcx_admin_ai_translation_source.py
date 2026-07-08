"""
CONTEXT:
This file reads the live source rows and target language rows for admin AI translation jobs.
It keeps entity-specific table details behind one small adapter boundary.
"""

from __future__ import annotations

from typing import Any

from admin.translations.build_dcx_admin_ai_translation_hash import (
    build_dcx_admin_ai_translation_content_hash,
)


def read_dcx_admin_ai_translation_source_or_error(
    cursor: Any,
    entity_kind: str,
    entity_key: str,
    source_language_code: str,
) -> dict:
    normalized_entity_kind = entity_kind.strip()
    normalized_entity_key = entity_key.strip()
    normalized_source_language_code = source_language_code.strip().lower()
    if normalized_entity_kind == "" or normalized_entity_key == "" or normalized_source_language_code == "":
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_INVALID")

    if normalized_entity_kind == "content_page":
        return _read_content_page_source_or_error(
            cursor=cursor,
            page_key=normalized_entity_key,
            source_language_code=normalized_source_language_code,
        )
    if normalized_entity_kind == "content_page_category":
        return _read_content_page_category_source_or_error(
            cursor=cursor,
            category_key=normalized_entity_key,
            source_language_code=normalized_source_language_code,
        )
    if normalized_entity_kind == "newsletter":
        return _read_email_source_or_error(
            cursor=cursor,
            entity_kind="newsletter",
            email_key=normalized_entity_key,
            source_language_code=normalized_source_language_code,
            newsletter_only=True,
        )
    if normalized_entity_kind == "email":
        return _read_email_source_or_error(
            cursor=cursor,
            entity_kind="email",
            email_key=normalized_entity_key,
            source_language_code=normalized_source_language_code,
            newsletter_only=False,
        )

    raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_INVALID")


def read_dcx_admin_ai_translation_target_language_or_error(
    cursor: Any,
    target_language_code: str,
) -> dict:
    normalized_target_language_code = target_language_code.strip().lower()
    if normalized_target_language_code == "":
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_INVALID")

    cursor.execute(
        """
        SELECT
            id,
            language_code,
            language_name_en,
            language_name_native,
            is_rtl
        FROM stephen_dcx_languages
        WHERE language_code = %s
          AND is_active = TRUE
        LIMIT 1
        """,
        (normalized_target_language_code,),
    )
    language_row = cursor.fetchone()
    if language_row is None:
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_INVALID")

    return {
        "language_id": language_row[0],
        "language_code": language_row[1],
        "language_name_en": language_row[2],
        "language_name_native": language_row[3],
        "is_rtl": language_row[4],
    }


def read_dcx_admin_active_target_languages(
    cursor: Any,
    source_language_id: int,
) -> list[dict]:
    cursor.execute(
        """
        SELECT
            id,
            language_code,
            language_name_en,
            language_name_native,
            is_rtl
        FROM stephen_dcx_languages
        WHERE is_active = TRUE
          AND id <> %s
        ORDER BY id ASC
        """,
        (source_language_id,),
    )
    return [
        {
            "language_id": row[0],
            "language_code": row[1],
            "language_name_en": row[2],
            "language_name_native": row[3],
            "is_rtl": row[4],
        }
        for row in cursor.fetchall()
    ]


def _read_content_page_source_or_error(
    cursor: Any,
    page_key: str,
    source_language_code: str,
) -> dict:
    cursor.execute(
        """
        SELECT
            page.id,
            page.page_key,
            page.category_key,
            page.language_id,
            language.language_code,
            language.language_name_en,
            language.language_name_native,
            page.page_title,
            page.page_lede,
            page.page_body_markdown,
            page.meta_title,
            page.meta_description,
            page.page_slug
        FROM stephen_dcx_content_pages AS page
        INNER JOIN stephen_dcx_languages AS language
          ON language.id = page.language_id
        WHERE page.page_key = %s
          AND page.is_live = TRUE
          AND language.language_code = %s
        LIMIT 1
        """,
        (page_key, source_language_code),
    )
    source_row = cursor.fetchone()
    if source_row is None:
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_SOURCE_NOT_FOUND")

    fields = {
        "page_title": source_row[7],
        "page_lede": source_row[8],
        "page_body_markdown": source_row[9],
        "meta_title": source_row[10],
        "meta_description": source_row[11],
    }
    return {
        "entity_kind": "content_page",
        "entity_key": source_row[1],
        "email_type": "",
        "source_row_id": source_row[0],
        "category_key": source_row[2],
        "source_language_id": source_row[3],
        "source_language_code": source_row[4],
        "source_language_name_en": source_row[5],
        "source_language_name_native": source_row[6],
        "fields": fields,
        "source_content_hash": build_dcx_admin_ai_translation_content_hash(fields),
        "stable_fields": {
            "page_slug": source_row[12],
        },
    }


def _read_content_page_category_source_or_error(
    cursor: Any,
    category_key: str,
    source_language_code: str,
) -> dict:
    cursor.execute(
        """
        SELECT
            category.id,
            category.category_key,
            category.language_id,
            language.language_code,
            language.language_name_en,
            language.language_name_native,
            category.category_name,
            category.category_description,
            category.category_slug
        FROM stephen_dcx_content_page_categories AS category
        INNER JOIN stephen_dcx_languages AS language
          ON language.id = category.language_id
        WHERE category.category_key = %s
          AND category.is_live = TRUE
          AND language.language_code = %s
        LIMIT 1
        """,
        (category_key, source_language_code),
    )
    source_row = cursor.fetchone()
    if source_row is None:
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_SOURCE_NOT_FOUND")

    fields = {
        "category_name": source_row[6],
        "category_description": source_row[7],
    }
    return {
        "entity_kind": "content_page_category",
        "entity_key": source_row[1],
        "email_type": "",
        "source_row_id": source_row[0],
        "source_language_id": source_row[2],
        "source_language_code": source_row[3],
        "source_language_name_en": source_row[4],
        "source_language_name_native": source_row[5],
        "fields": fields,
        "source_content_hash": build_dcx_admin_ai_translation_content_hash(fields),
        "stable_fields": {
            "category_slug": source_row[8],
        },
    }


def _read_email_source_or_error(
    cursor: Any,
    entity_kind: str,
    email_key: str,
    source_language_code: str,
    newsletter_only: bool,
) -> dict:
    email_type_filter = "source_email.email_type = 'newsletter'" if newsletter_only else "source_email.email_type <> 'newsletter'"
    cursor.execute(
        f"""
        SELECT
            source_email.id,
            source_email.email_type,
            source_email.email_key,
            source_email.language_id,
            language.language_code,
            language.language_name_en,
            language.language_name_native,
            source_email.email_subject,
            source_email.email_body
        FROM stephen_dcx_emails AS source_email
        INNER JOIN stephen_dcx_languages AS language
          ON language.id = source_email.language_id
        WHERE source_email.email_key = %s
          AND source_email.is_live = TRUE
          AND language.language_code = %s
          AND {email_type_filter}
        ORDER BY source_email.id DESC
        LIMIT 1
        """,
        (email_key, source_language_code),
    )
    source_row = cursor.fetchone()
    if source_row is None:
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_SOURCE_NOT_FOUND")

    fields = {
        "email_subject": source_row[7],
        "email_body": source_row[8],
    }
    return {
        "entity_kind": entity_kind,
        "entity_key": source_row[2],
        "email_type": source_row[1],
        "source_row_id": source_row[0],
        "source_language_id": source_row[3],
        "source_language_code": source_row[4],
        "source_language_name_en": source_row[5],
        "source_language_name_native": source_row[6],
        "fields": fields,
        "source_content_hash": build_dcx_admin_ai_translation_content_hash(fields),
        "stable_fields": {},
    }
