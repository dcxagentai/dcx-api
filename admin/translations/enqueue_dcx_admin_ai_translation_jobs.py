"""
CONTEXT:
This file creates purpose-built AI translation jobs for admin-authored content.
It exists so admin screens can enqueue one or many target languages through a single backend
contract while the worker handles the LLM call and storage.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from admin.translations.read_dcx_admin_ai_translation_source import (
    read_dcx_admin_active_target_languages,
    read_dcx_admin_ai_translation_source_or_error,
    read_dcx_admin_ai_translation_target_language_or_error,
)
from storage.db_config import DB_CONFIG


def enqueue_dcx_admin_ai_translation_jobs_capability(
    authenticated_admin_user_id: int,
    entity_kind: str,
    entity_key: str,
    source_language_code: str,
    target_language_codes: list[str] | None = None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    normalized_entity_kind = entity_kind.strip()
    normalized_entity_key = entity_key.strip()
    normalized_source_language_code = source_language_code.strip().lower()
    normalized_target_language_codes = [
        target_language_code.strip().lower()
        for target_language_code in (target_language_codes or [])
        if isinstance(target_language_code, str) and target_language_code.strip() != ""
    ]
    if (
        not isinstance(authenticated_admin_user_id, int)
        or authenticated_admin_user_id <= 0
        or normalized_entity_kind == ""
        or normalized_entity_key == ""
        or normalized_source_language_code == ""
    ):
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                source_payload = read_dcx_admin_ai_translation_source_or_error(
                    cursor=cursor,
                    entity_kind=normalized_entity_kind,
                    entity_key=normalized_entity_key,
                    source_language_code=normalized_source_language_code,
                )

                if normalized_target_language_codes:
                    target_languages = [
                        read_dcx_admin_ai_translation_target_language_or_error(
                            cursor=cursor,
                            target_language_code=target_language_code,
                        )
                        for target_language_code in normalized_target_language_codes
                    ]
                else:
                    target_languages = read_dcx_admin_active_target_languages(
                        cursor=cursor,
                        source_language_id=source_payload["source_language_id"],
                    )

                job_rows = []
                for target_language in target_languages:
                    if target_language["language_id"] == source_payload["source_language_id"]:
                        continue
                    job_rows.append(
                        _enqueue_one_target_language_job(
                            cursor=cursor,
                            source_payload=source_payload,
                            target_language=target_language,
                            authenticated_admin_user_id=authenticated_admin_user_id,
                        )
                    )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_ENQUEUE_FAILED") from exc

    return {
        "entity_kind": source_payload["entity_kind"],
        "entity_key": source_payload["entity_key"],
        "source_language_code": source_payload["source_language_code"],
        "source_row_id": source_payload["source_row_id"],
        "source_content_hash": source_payload["source_content_hash"],
        "jobs": job_rows,
    }


def _enqueue_one_target_language_job(
    cursor: Any,
    source_payload: dict,
    target_language: dict,
    authenticated_admin_user_id: int,
) -> dict:
    lock_key = (
        "dcx_ai_translation_job:"
        f"{source_payload['entity_kind']}:"
        f"{source_payload['entity_key']}:"
        f"{source_payload['email_type']}:"
        f"{source_payload['source_language_id']}:"
        f"{target_language['language_id']}"
    )
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_key,))

    cursor.execute(
        """
        SELECT id, job_status, target_row_id
        FROM stephen_dcx_ai_translation_jobs
        WHERE entity_kind = %s
          AND entity_key = %s
          AND email_type = %s
          AND source_language_id = %s
          AND target_language_id = %s
          AND job_status IN ('queued', 'processing')
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            source_payload["entity_kind"],
            source_payload["entity_key"],
            source_payload["email_type"],
            source_payload["source_language_id"],
            target_language["language_id"],
        ),
    )
    active_job_row = cursor.fetchone()
    if active_job_row is not None:
        return _format_job_row(
            job_id=active_job_row[0],
            job_status=active_job_row[1],
            target_row_id=active_job_row[2],
            target_language=target_language,
            was_enqueued=False,
        )

    fresh_target_row_id = _read_fresh_ai_translated_target_row_id(
        cursor=cursor,
        source_payload=source_payload,
        target_language=target_language,
    )
    if fresh_target_row_id is not None:
        return _format_job_row(
            job_id=None,
            job_status="completed",
            target_row_id=fresh_target_row_id,
            target_language=target_language,
            was_enqueued=False,
        )

    cursor.execute(
        """
        INSERT INTO stephen_dcx_ai_translation_jobs (
            entity_kind,
            entity_key,
            email_type,
            source_language_id,
            target_language_id,
            source_row_id_snapshot,
            source_content_hash,
            job_status,
            requested_by_user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'queued', %s)
        RETURNING id, job_status, target_row_id
        """,
        (
            source_payload["entity_kind"],
            source_payload["entity_key"],
            source_payload["email_type"],
            source_payload["source_language_id"],
            target_language["language_id"],
            source_payload["source_row_id"],
            source_payload["source_content_hash"],
            authenticated_admin_user_id,
        ),
    )
    inserted_job_row = cursor.fetchone()
    return _format_job_row(
        job_id=inserted_job_row[0],
        job_status=inserted_job_row[1],
        target_row_id=inserted_job_row[2],
        target_language=target_language,
        was_enqueued=True,
    )


def _read_fresh_ai_translated_target_row_id(
    cursor: Any,
    source_payload: dict,
    target_language: dict,
) -> int | None:
    target_table_name, key_column_name, live_filter_sql = _read_target_lookup_shape(source_payload)
    cursor.execute(
        f"""
        SELECT target_row.id
        FROM {target_table_name} AS target_row
        INNER JOIN stephen_dcx_ai_translation_jobs AS translation_job
          ON translation_job.target_row_id = target_row.id
         AND translation_job.entity_kind = %s
         AND translation_job.job_status = 'completed'
         AND translation_job.source_content_hash = %s
        WHERE target_row.{key_column_name} = %s
          AND target_row.language_id = %s
          AND target_row.is_live = TRUE
          {live_filter_sql}
        ORDER BY translation_job.id DESC
        LIMIT 1
        """,
        (
            source_payload["entity_kind"],
            source_payload["source_content_hash"],
            source_payload["entity_key"],
            target_language["language_id"],
        ),
    )
    fresh_target_row = cursor.fetchone()
    return fresh_target_row[0] if fresh_target_row is not None else None


def _read_target_lookup_shape(source_payload: dict) -> tuple[str, str, str]:
    if source_payload["entity_kind"] == "content_page":
        return "stephen_dcx_content_pages", "page_key", ""
    if source_payload["entity_kind"] == "content_page_category":
        return "stephen_dcx_content_page_categories", "category_key", ""
    return (
        "stephen_dcx_emails",
        "email_key",
        f"AND target_row.email_type = '{source_payload['email_type']}'",
    )


def _format_job_row(
    job_id: int | None,
    job_status: str,
    target_row_id: int | None,
    target_language: dict,
    was_enqueued: bool,
) -> dict:
    return {
        "job_id": job_id,
        "job_status": job_status,
        "target_row_id": target_row_id,
        "was_enqueued": was_enqueued,
        "target_language": {
            "id": target_language["language_id"],
            "language_code": target_language["language_code"],
            "language_name_en": target_language["language_name_en"],
            "language_name_native": target_language["language_name_native"],
            "is_rtl": target_language["is_rtl"],
        },
    }
