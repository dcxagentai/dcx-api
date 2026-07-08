"""
CONTEXT:
This file claims and processes queued admin AI translation jobs.
It is intentionally small and database-backed so HTTP background tasks, cron, and a future
long-running worker can all reuse the same work loop.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Any, Callable

import psycopg2

from admin.translations.read_dcx_admin_ai_translation_source import (
    read_dcx_admin_ai_translation_source_or_error,
    read_dcx_admin_ai_translation_target_language_or_error,
)
from admin.translations.store_dcx_admin_ai_translation_result import (
    store_dcx_admin_ai_translation_result,
)
from apis.gemini.translate_dcx_gemini_structured_admin_content import (
    translate_dcx_gemini_structured_admin_content,
)
from storage.db_config import DB_CONFIG
from usage.record_dcx_user_llm_usage_event import record_dcx_user_llm_usage_event

LOGGER = logging.getLogger(__name__)
MAX_TRANSLATION_PROVIDER_ATTEMPTS = 3


def process_due_dcx_admin_ai_translation_jobs_capability(
    max_jobs: int = 5,
    worker_name: str | None = None,
    connect_to_database: Callable[..., Any] | None = None,
    translate_structured_content: Callable[..., dict] | None = None,
) -> dict:
    normalized_max_jobs = max(1, min(int(max_jobs or 1), 25))
    resolved_worker_name = worker_name or _build_default_worker_name()
    processed_jobs = []

    for _ in range(normalized_max_jobs):
        claimed_job = _claim_one_translation_job(
            worker_name=resolved_worker_name,
            connect_to_database=connect_to_database,
        )
        if claimed_job is None:
            break
        processed_jobs.append(
            _process_claimed_translation_job(
                claimed_job=claimed_job,
                worker_name=resolved_worker_name,
                connect_to_database=connect_to_database,
                translate_structured_content=translate_structured_content,
            )
        )

    return {
        "ok": True,
        "status": "processed" if processed_jobs else "idle",
        "processed_job_count": len(processed_jobs),
        "jobs": processed_jobs,
    }


def _claim_one_translation_job(
    worker_name: str,
    connect_to_database: Callable[..., Any] | None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect
    current_timestamp_ms = _read_current_timestamp_ms()

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
                    target_language.language_code,
                    job.source_row_id_snapshot,
                    job.source_content_hash,
                    job.requested_by_user_id,
                    job.attempt_count
                FROM stephen_dcx_ai_translation_jobs AS job
                INNER JOIN stephen_dcx_languages AS source_language
                  ON source_language.id = job.source_language_id
                INNER JOIN stephen_dcx_languages AS target_language
                  ON target_language.id = job.target_language_id
                WHERE job.job_status = 'queued'
                  AND job.available_at_ts_ms <= %s
                ORDER BY job.id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """,
                (current_timestamp_ms,),
            )
            job_row = cursor.fetchone()
            if job_row is None:
                return None

            cursor.execute(
                """
                UPDATE stephen_dcx_ai_translation_jobs
                SET job_status = 'processing',
                    attempt_count = attempt_count + 1,
                    locked_at_ts_ms = %s,
                    locked_by_worker = %s,
                    last_error_code = NULL,
                    last_error_detail = NULL
                WHERE id = %s
                """,
                (current_timestamp_ms, worker_name, job_row[0]),
            )

    return {
        "job_id": job_row[0],
        "entity_kind": job_row[1],
        "entity_key": job_row[2],
        "email_type": job_row[3],
        "source_language_code": job_row[4],
        "target_language_code": job_row[5],
        "source_row_id_snapshot": job_row[6],
        "source_content_hash": job_row[7],
        "requested_by_user_id": job_row[8],
        "attempt_count": job_row[9] + 1,
    }


def _process_claimed_translation_job(
    claimed_job: dict,
    worker_name: str,
    connect_to_database: Callable[..., Any] | None,
    translate_structured_content: Callable[..., dict] | None,
) -> dict:
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                source_payload = read_dcx_admin_ai_translation_source_or_error(
                    cursor=cursor,
                    entity_kind=claimed_job["entity_kind"],
                    entity_key=claimed_job["entity_key"],
                    source_language_code=claimed_job["source_language_code"],
                )
                target_language = read_dcx_admin_ai_translation_target_language_or_error(
                    cursor=cursor,
                    target_language_code=claimed_job["target_language_code"],
                )

        if (
            source_payload["source_row_id"] != claimed_job["source_row_id_snapshot"]
            or source_payload["source_content_hash"] != claimed_job["source_content_hash"]
        ):
            _mark_translation_job_finished(
                job_id=claimed_job["job_id"],
                job_status="stale_source",
                error_code="API_DCX_ADMIN_AI_TRANSLATION_STALE_SOURCE",
                error_detail="The live source content changed before this queued translation was processed.",
                connect_to_database=connect_to_database,
            )
            return {
                "job_id": claimed_job["job_id"],
                "job_status": "stale_source",
                "target_language_code": claimed_job["target_language_code"],
            }

        translation_result = _translate_structured_content_with_retries(
            translate_structured_content=(
                translate_structured_content or translate_dcx_gemini_structured_admin_content
            ),
            entity_kind=source_payload["entity_kind"],
            source_language_code=source_payload["source_language_code"],
            target_language_code=target_language["language_code"],
            source_fields=source_payload["fields"],
        )

        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                latest_source_payload = read_dcx_admin_ai_translation_source_or_error(
                    cursor=cursor,
                    entity_kind=claimed_job["entity_kind"],
                    entity_key=claimed_job["entity_key"],
                    source_language_code=claimed_job["source_language_code"],
                )
                if (
                    latest_source_payload["source_row_id"] != claimed_job["source_row_id_snapshot"]
                    or latest_source_payload["source_content_hash"] != claimed_job["source_content_hash"]
                ):
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_ai_translation_jobs
                        SET job_status = 'stale_source',
                            locked_at_ts_ms = NULL,
                            locked_by_worker = NULL,
                            last_error_code = %s,
                            last_error_detail = %s
                        WHERE id = %s
                        """,
                        (
                            "API_DCX_ADMIN_AI_TRANSLATION_STALE_SOURCE",
                            "The live source content changed while this translation was running.",
                            claimed_job["job_id"],
                        ),
                    )
                    return {
                        "job_id": claimed_job["job_id"],
                        "job_status": "stale_source",
                        "target_language_code": claimed_job["target_language_code"],
                    }

                storage_result = store_dcx_admin_ai_translation_result(
                    cursor=cursor,
                    source_payload=latest_source_payload,
                    target_language=target_language,
                    translated_fields=translation_result["translated_fields"],
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_ai_translation_jobs
                    SET job_status = 'completed',
                        target_row_id = %s,
                        target_content_hash = %s,
                        locked_at_ts_ms = NULL,
                        locked_by_worker = NULL,
                        provider_name = %s,
                        model_name = %s,
                        prompt_version = %s,
                        last_error_code = NULL,
                        last_error_detail = NULL
                    WHERE id = %s
                    """,
                    (
                        storage_result["target_row_id"],
                        storage_result["target_content_hash"],
                        translation_result["provider_name"],
                        translation_result["model_name"],
                        translation_result["prompt_version"],
                        claimed_job["job_id"],
                    ),
                )

        usage_event_id = _record_translation_usage_event(
            claimed_job=claimed_job,
            translation_result=translation_result,
            connect_to_database=connect_to_database,
        )
        if usage_event_id is not None:
            _set_translation_job_usage_event_id(
                job_id=claimed_job["job_id"],
                usage_event_id=usage_event_id,
                connect_to_database=connect_to_database,
            )

        return {
            "job_id": claimed_job["job_id"],
            "job_status": "completed",
            "target_language_code": claimed_job["target_language_code"],
            "target_row_id": storage_result["target_row_id"],
        }
    except Exception as exc:
        error_code = _read_translation_error_code(exc)
        next_status = "failed"
        LOGGER.warning(
            "AI translation job failed job_id=%s entity_kind=%s entity_key=%s target_language_code=%s error_code=%s error_detail=%s",
            claimed_job["job_id"],
            claimed_job["entity_kind"],
            claimed_job["entity_key"],
            claimed_job["target_language_code"],
            error_code,
            str(exc)[:1000],
            exc_info=True,
        )
        _mark_translation_job_finished(
            job_id=claimed_job["job_id"],
            job_status=next_status,
            error_code=error_code,
            error_detail=str(exc)[:1000],
            connect_to_database=connect_to_database,
        )
        return {
            "job_id": claimed_job["job_id"],
            "job_status": next_status,
            "target_language_code": claimed_job["target_language_code"],
            "error_code": error_code,
        }


def _translate_structured_content_with_retries(
    translate_structured_content: Callable[..., dict],
    entity_kind: str,
    source_language_code: str,
    target_language_code: str,
    source_fields: dict,
) -> dict:
    for attempt_number in range(1, MAX_TRANSLATION_PROVIDER_ATTEMPTS + 1):
        try:
            return translate_structured_content(
                entity_kind=entity_kind,
                source_language_code=source_language_code,
                target_language_code=target_language_code,
                source_fields=source_fields,
            )
        except RuntimeError as exc:
            if (
                not _is_retryable_structured_translation_error(exc)
                or attempt_number >= MAX_TRANSLATION_PROVIDER_ATTEMPTS
            ):
                raise
            LOGGER.warning(
                "AI translation provider attempt failed attempt=%s target_language_code=%s error_code=%s error_detail=%s",
                attempt_number,
                target_language_code,
                _read_translation_error_code(exc),
                str(exc)[:1000],
            )

    raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_PROCESS_FAILED")


def _is_retryable_structured_translation_error(exc: RuntimeError) -> bool:
    return _read_translation_error_code(exc) == "API_DCX_GEMINI_ADMIN_TRANSLATION_FAILED"


def _mark_translation_job_finished(
    job_id: int,
    job_status: str,
    error_code: str | None,
    error_detail: str | None,
    connect_to_database: Callable[..., Any] | None,
) -> None:
    connect = connect_to_database or psycopg2.connect
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_ai_translation_jobs
                SET job_status = %s,
                    locked_at_ts_ms = NULL,
                    locked_by_worker = NULL,
                    last_error_code = %s,
                    last_error_detail = %s
                WHERE id = %s
                """,
                (job_status, error_code, error_detail, job_id),
            )


def _record_translation_usage_event(
    claimed_job: dict,
    translation_result: dict,
    connect_to_database: Callable[..., Any] | None,
) -> int | None:
    requested_by_user_id = claimed_job.get("requested_by_user_id")
    if not isinstance(requested_by_user_id, int) or requested_by_user_id <= 0:
        return None
    try:
        usage_event = record_dcx_user_llm_usage_event(
            authenticated_user_id=requested_by_user_id,
            provider_name=translation_result.get("provider_name", ""),
            model_name=translation_result.get("model_name", ""),
            prompt_version=translation_result.get("prompt_version", ""),
            usage_source_kind="ai_translation_job",
            usage_source_id=claimed_job["job_id"],
            usage_metadata=translation_result.get("usage_metadata", {}),
            connect_to_database=connect_to_database,
        )
        return usage_event["usage_event_id"]
    except Exception:
        return None


def _set_translation_job_usage_event_id(
    job_id: int,
    usage_event_id: int,
    connect_to_database: Callable[..., Any] | None,
) -> None:
    connect = connect_to_database or psycopg2.connect
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_ai_translation_jobs
                SET usage_event_id = %s
                WHERE id = %s
                """,
                (usage_event_id, job_id),
            )


def _read_translation_error_code(exc: Exception) -> str:
    raw_error = str(exc)
    if raw_error.startswith("API_"):
        return raw_error.split(":", 1)[0]
    return "API_DCX_ADMIN_AI_TRANSLATION_PROCESS_FAILED"


def _read_current_timestamp_ms() -> int:
    return int(time.time() * 1000)


def _build_default_worker_name() -> str:
    configured_name = os.getenv("DCX_AI_TRANSLATION_WORKER_NAME", "").strip()
    if configured_name != "":
        return configured_name
    return f"ai-translation:{socket.gethostname()}:{os.getpid()}"
