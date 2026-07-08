"""
CONTEXT:
This file reads recent AI translation jobs for one admin content identity.
It exists so the admin frontend can poll queued/processing/failed/completed states.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_ai_translation_jobs_capability(
    entity_kind: str,
    entity_key: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    normalized_entity_kind = entity_kind.strip()
    normalized_entity_key = entity_key.strip()
    if normalized_entity_kind == "" or normalized_entity_key == "":
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        job.id,
                        job.entity_kind,
                        job.entity_key,
                        job.email_type,
                        source_language.language_code,
                        target_language.id,
                        target_language.language_code,
                        target_language.language_name_en,
                        target_language.language_name_native,
                        target_language.is_rtl,
                        job.source_row_id_snapshot,
                        job.target_row_id,
                        job.source_content_hash,
                        job.target_content_hash,
                        job.job_status,
                        job.attempt_count,
                        job.provider_name,
                        job.model_name,
                        job.prompt_version,
                        job.last_error_code,
                        job.last_error_detail,
                        job.created_at_ts_ms,
                        job.updated_at_ts_ms
                    FROM stephen_dcx_ai_translation_jobs AS job
                    INNER JOIN stephen_dcx_languages AS source_language
                      ON source_language.id = job.source_language_id
                    INNER JOIN stephen_dcx_languages AS target_language
                      ON target_language.id = job.target_language_id
                    WHERE job.entity_kind = %s
                      AND job.entity_key = %s
                    ORDER BY job.created_at_ts_ms DESC, job.id DESC
                    LIMIT 100
                    """,
                    (normalized_entity_kind, normalized_entity_key),
                )
                job_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_JOBS_READ_FAILED") from exc

    return {
        "entity_kind": normalized_entity_kind,
        "entity_key": normalized_entity_key,
        "jobs": [
            {
                "job_id": row[0],
                "entity_kind": row[1],
                "entity_key": row[2],
                "email_type": row[3],
                "source_language_code": row[4],
                "target_language": {
                    "id": row[5],
                    "language_code": row[6],
                    "language_name_en": row[7],
                    "language_name_native": row[8],
                    "is_rtl": row[9],
                },
                "source_row_id_snapshot": row[10],
                "target_row_id": row[11],
                "source_content_hash": row[12],
                "target_content_hash": row[13],
                "job_status": row[14],
                "attempt_count": row[15],
                "provider_name": row[16],
                "model_name": row[17],
                "prompt_version": row[18],
                "last_error_code": row[19],
                "last_error_detail": row[20],
                "created_at_ts_ms": row[21],
                "updated_at_ts_ms": row[22],
            }
            for row in job_rows
        ],
    }
