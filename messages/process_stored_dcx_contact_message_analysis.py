"""
CONTEXT:
This file runs the first real AI analysis pass for one stored DCX contact message.
It exists so app, WhatsApp, and email intake can move from raw stored message plus attachments to
message-level and file-level analysis fields using one shared lifecycle.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
import psycopg2.extras

from apis.gemini.generate_dcx_gemini_structured_message_analysis import (
    PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS,
    generate_dcx_gemini_structured_message_analysis,
)
from files.build_dcx_r2_s3_client import build_dcx_r2_s3_client
from files.read_dcx_r2_bucket_name_for_alias import read_dcx_r2_bucket_name_for_alias
from storage.db_config import DB_CONFIG


def process_stored_dcx_contact_message_analysis(
    message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    build_r2_client: Callable[[], Any] | None = None,
    analyze_message_content: Callable[[dict, list[dict]], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - message_id identifies one existing stephen_dcx_contact_messages row.
        - Any attached files have already been stored in stephen_dcx_file_objects and R2.
      postconditions:
        - Creates or reuses one analyze_message_content processing job row.
        - Updates stephen_dcx_contact_messages.analysis_summary_text and analysis fields.
        - Updates stephen_dcx_file_objects analysis fields for each analysed attachment.
        - Writes one stephen_dcx_contact_message_analysis_runs row with prompt/run trace data.
      side_effects:
        - reads private file bytes from R2
        - may call Gemini through the injected/default analyzer
        - writes to stephen_dcx_contact_message_processing_jobs
        - updates stephen_dcx_contact_messages
        - updates stephen_dcx_file_objects
        - writes to stephen_dcx_contact_message_analysis_runs
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: message_analysis:{message_id}:{PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS}
      locks:
        - row lock on the target stephen_dcx_contact_messages row
        - row lock on the newest analyze_message_content processing job row when one exists
      contention_strategy: duplicate attempts converge on the completed message state when analysis already finished

    NARRATIVE:
      WHY this exists:
        - DCX needs one shared way to understand mixed messages across app, email, and WhatsApp after
          the storage plumbing has already captured raw text and files.
      WHEN TO USE it:
        - Use it immediately after one canonical message and its attachments have been persisted.
      WHEN NOT TO USE it:
        - Do not use it as final trade extraction, compliance screening, or counterpart matching.
      WHAT CAN GO WRONG:
        - The message can be missing.
        - R2 file reads can fail.
        - The model call can fail or return invalid JSON.
        - The database update can fail after model output is available.
      WHAT COMES NEXT:
        - Larger messages can later split into file-level jobs followed by one message synthesis job.

    TESTS:
      - to be added with the first implementation smoke tests

    ERRORS:
      - API_DCX_CONTACT_MESSAGE_ANALYSIS_MESSAGE_NOT_FOUND:
          suggested_action: Retry only after confirming the target message row exists.
          common_causes:
            - stale message id
            - prior insert rollback
          recovery_steps:
            - Confirm the message row exists in stephen_dcx_contact_messages.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED:
          suggested_action: Retry after the backend, database, storage, and model provider are healthy.
          common_causes:
            - database unavailable
            - R2 unavailable
            - model provider failure
            - malformed model output
          recovery_steps:
            - Confirm database and R2 connectivity.
            - Confirm GEMINI_API_KEY and model configuration.
            - Retry once dependencies are healthy.
          retry_safe: true
          what_changed: the message and files may exist while analysis state is incomplete
          rollback_needed: inspect_before_manual_replay
          rollback_operation: inspect the message, file objects, job, and analysis-run rows

    CODE:
    """
    if not isinstance(message_id, int) or message_id <= 0:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ANALYSIS_MESSAGE_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()

    try:
        message_input, attachment_inputs, active_job_id = _claim_message_analysis_work(
            message_id=message_id,
            connect=connect,
            now_ts_ms=now_ts_ms,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED") from exc

    if message_input.get("was_noop") is True:
        return {
            "message_id": message_id,
            "job_id": active_job_id,
            "processing_status": message_input["processing_status"],
            "analysis_status": message_input["analysis_status"],
            "derivation_status": message_input.get("derivation_status", "completed"),
            "was_noop": True,
        }

    try:
        file_inputs = _read_message_analysis_file_inputs_from_r2(
            attachment_inputs=attachment_inputs,
            build_r2_client=build_r2_client,
        )
        analysis_callable = analyze_message_content or generate_dcx_gemini_structured_message_analysis
        analysis_result = analysis_callable(message_input, file_inputs)
        analysis_run_status = "completed"
        analysis_error_code = None
    except RuntimeError as runtime_error:
        analysis_result = _build_failed_analysis_result(
            error_code=str(runtime_error),
            error_detail=_read_exception_detail(runtime_error),
        )
        analysis_run_status = "failed"
        analysis_error_code = str(runtime_error)
    except Exception as exc:
        analysis_result = _build_failed_analysis_result(
            error_code="API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED",
            error_detail=_read_exception_detail(exc),
        )
        analysis_run_status = "failed"
        analysis_error_code = "API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED"

    try:
        _persist_message_analysis_result(
            message_id=message_id,
            active_job_id=active_job_id,
            message_input=message_input,
            file_inputs=file_inputs if "file_inputs" in locals() else [],
            attachment_inputs=attachment_inputs,
            analysis_result=analysis_result,
            analysis_run_status=analysis_run_status,
            analysis_error_code=analysis_error_code,
            connect=connect,
            now_ts_ms=now_ts_ms,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED") from exc

    return {
        "message_id": message_id,
        "job_id": active_job_id,
        "processing_status": "ready" if analysis_run_status == "completed" else "failed",
        "analysis_status": analysis_result.get("message_analysis_status", "failed"),
        "derivation_status": "completed" if analysis_run_status == "completed" else "failed",
        "was_noop": False,
    }


def _claim_message_analysis_work(message_id: int, connect: Callable[..., Any], now_ts_ms: int) -> tuple[dict, list[dict], int | None]:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    channel_type,
                    provider_type,
                    message_format,
                    message_subject,
                    raw_text_content,
                    processing_status,
                    derivation_status,
                    analysis_status
                FROM stephen_dcx_contact_messages
                WHERE id = %s
                LIMIT 1
                FOR UPDATE
                """,
                (message_id,),
            )
            message_row = cursor.fetchone()
            if message_row is None:
                raise RuntimeError("API_DCX_CONTACT_MESSAGE_ANALYSIS_MESSAGE_NOT_FOUND")

            if message_row[8] in {"completed", "partial"} and message_row[6] == "ready":
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_contact_message_processing_jobs
                    WHERE message_id = %s
                      AND job_type = 'analyze_message_content'
                    ORDER BY created_at_ts_ms DESC, id DESC
                    LIMIT 1
                    """,
                    (message_id,),
                )
                latest_job_row = cursor.fetchone()
                return (
                    {
                        "was_noop": True,
                        "processing_status": message_row[6],
                        "derivation_status": message_row[7],
                        "analysis_status": message_row[8],
                    },
                    [],
                    latest_job_row[0] if latest_job_row is not None else None,
                )

            cursor.execute(
                """
                SELECT
                    attachment.id,
                    attachment.file_object_id,
                    attachment.sort_order,
                    file_object.bucket_alias,
                    file_object.object_key,
                    file_object.content_type,
                    file_object.file_size_bytes,
                    file_object.original_filename,
                    file_object.file_kind
                FROM stephen_dcx_contact_message_attachments attachment
                INNER JOIN stephen_dcx_file_objects file_object
                  ON file_object.id = attachment.file_object_id
                WHERE attachment.message_id = %s
                ORDER BY attachment.sort_order ASC, attachment.id ASC
                """,
                (message_id,),
            )
            attachment_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT id, job_status, attempt_count
                FROM stephen_dcx_contact_message_processing_jobs
                WHERE message_id = %s
                  AND job_type = 'analyze_message_content'
                ORDER BY created_at_ts_ms DESC, id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (message_id,),
            )
            existing_job_row = cursor.fetchone()
            if existing_job_row is None or existing_job_row[1] in {"completed", "failed", "cancelled"}:
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_contact_message_processing_jobs (
                        message_id,
                        job_type,
                        job_status,
                        attempt_count,
                        available_at_ts_ms,
                        locked_at_ts_ms,
                        locked_by_worker
                    )
                    VALUES (%s, 'analyze_message_content', 'processing', %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (message_id, 1, now_ts_ms, now_ts_ms, "inline_message_analysis"),
                )
                active_job_id = cursor.fetchone()[0]
            else:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_contact_message_processing_jobs
                    SET
                        job_status = 'processing',
                        attempt_count = %s,
                        locked_at_ts_ms = %s,
                        locked_by_worker = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (existing_job_row[2] + 1, now_ts_ms, "inline_message_analysis", existing_job_row[0]),
                )
                active_job_id = cursor.fetchone()[0]

            cursor.execute(
                """
                UPDATE stephen_dcx_contact_messages
                SET
                    processing_status = 'processing',
                    analysis_status = 'processing',
                    derivation_status = 'pending'
                WHERE id = %s
                """,
                (message_id,),
            )

            if attachment_rows:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_file_objects
                    SET analysis_status = 'processing'
                    WHERE id = ANY(%s)
                    """,
                    ([row[1] for row in attachment_rows],),
                )

    return (
        {
            "message_id": message_row[0],
            "channel_type": message_row[1],
            "provider_type": message_row[2],
            "message_format": message_row[3],
            "message_subject": message_row[4],
            "raw_text_content": message_row[5],
        },
        [
            {
                "attachment_id": row[0],
                "file_object_id": row[1],
                "sort_order": row[2],
                "bucket_alias": row[3],
                "object_key": row[4],
                "content_type": row[5],
                "file_size_bytes": row[6],
                "original_filename": row[7],
                "file_kind": row[8],
            }
            for row in attachment_rows
        ],
        active_job_id,
    )


def _read_message_analysis_file_inputs_from_r2(
    attachment_inputs: list[dict],
    build_r2_client: Callable[[], Any] | None = None,
) -> list[dict]:
    if not attachment_inputs:
        return []

    r2_client = (build_r2_client or build_dcx_r2_s3_client)()
    file_inputs = []
    for attachment_input in attachment_inputs:
        response = r2_client.get_object(
            Bucket=read_dcx_r2_bucket_name_for_alias(attachment_input["bucket_alias"]),
            Key=attachment_input["object_key"],
        )
        file_bytes = response["Body"].read()
        file_inputs.append(
            {
                "attachment_id": attachment_input["attachment_id"],
                "file_object_id": attachment_input["file_object_id"],
                "file_kind": attachment_input["file_kind"],
                "content_type": attachment_input["content_type"],
                "file_size_bytes": attachment_input["file_size_bytes"],
                "original_filename": attachment_input["original_filename"],
                "file_bytes": file_bytes,
            }
        )
    return file_inputs


def _persist_message_analysis_result(
    message_id: int,
    active_job_id: int,
    message_input: dict,
    file_inputs: list[dict],
    attachment_inputs: list[dict],
    analysis_result: dict,
    analysis_run_status: str,
    analysis_error_code: str | None,
    connect: Callable[..., Any],
    now_ts_ms: int,
) -> None:
    message_analysis_status = analysis_result.get("message_analysis_status", "failed")
    processing_status = "ready" if analysis_run_status == "completed" else "failed"
    derivation_status = "completed" if analysis_run_status == "completed" else "failed"

    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            detected_language_id = _read_language_id_for_code(
                cursor=cursor,
                language_code=analysis_result.get("message_language_code"),
            )

            cursor.execute(
                """
                UPDATE stephen_dcx_contact_messages
                SET
                    analysis_summary_text = %s,
                    derived_text_content = %s,
                    detected_language_id = %s,
                    processing_status = %s,
                    derivation_status = %s,
                    analysis_status = %s,
                    analysis_model_name = %s,
                    analysis_metadata_json = analysis_metadata_json || %s::jsonb,
                    analysis_completed_at_ts_ms = %s
                WHERE id = %s
                """,
                (
                    analysis_result.get("message_summary", ""),
                    analysis_result.get("message_text_synthesis", ""),
                    detected_language_id,
                    processing_status,
                    derivation_status,
                    message_analysis_status,
                    analysis_result.get("model_name", ""),
                    psycopg2.extras.Json(
                        {
                            "provider_name": analysis_result.get("provider_name", ""),
                            "analysis_mode": analysis_result.get("analysis_mode", ""),
                            "prompt_version": analysis_result.get("prompt_version", ""),
                        }
                    ),
                    now_ts_ms if analysis_run_status == "completed" else None,
                    message_id,
                ),
            )

            for attachment_analysis in analysis_result.get("attachments", []):
                file_language_id = _read_language_id_for_code(
                    cursor=cursor,
                    language_code=attachment_analysis.get("language_code"),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_file_objects
                    SET
                        analysis_status = %s,
                        analysis_summary_text = %s,
                        analysis_description_text = %s,
                        analysis_transcription_text = %s,
                        analysis_synthesis_text = %s,
                        context_within_message = %s,
                        analysis_model_name = %s,
                        analysis_metadata_json = analysis_metadata_json || %s::jsonb,
                        analysis_completed_at_ts_ms = %s,
                        detected_language_id = %s
                    WHERE id = %s
                    """,
                    (
                        attachment_analysis.get("analysis_status", "completed"),
                        attachment_analysis.get("summary", ""),
                        attachment_analysis.get("description", ""),
                        attachment_analysis.get("transcription", ""),
                        attachment_analysis.get("synthesis", ""),
                        attachment_analysis.get("context_within_message", ""),
                        analysis_result.get("model_name", ""),
                        psycopg2.extras.Json(
                            {
                                "provider_name": analysis_result.get("provider_name", ""),
                                "analysis_mode": analysis_result.get("analysis_mode", ""),
                                "prompt_version": analysis_result.get("prompt_version", ""),
                                "attachment_id": attachment_analysis.get("attachment_id"),
                            }
                        ),
                        now_ts_ms if attachment_analysis.get("analysis_status") in {"completed", "partial", "skipped"} else None,
                        file_language_id,
                        attachment_analysis["file_object_id"],
                    ),
                )

            analyzed_file_object_ids = {
                attachment_analysis.get("file_object_id")
                for attachment_analysis in analysis_result.get("attachments", [])
                if attachment_analysis.get("file_object_id") is not None
            }
            unresolved_file_object_ids = [
                attachment_input["file_object_id"]
                for attachment_input in attachment_inputs
                if attachment_input["file_object_id"] not in analyzed_file_object_ids
            ]
            if unresolved_file_object_ids:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_file_objects
                    SET
                        analysis_status = %s,
                        analysis_model_name = %s,
                        analysis_metadata_json = analysis_metadata_json || %s::jsonb,
                        analysis_completed_at_ts_ms = %s
                    WHERE id = ANY(%s)
                    """,
                    (
                        "failed" if analysis_run_status == "failed" else "skipped",
                        analysis_result.get("model_name", ""),
                        psycopg2.extras.Json(
                            {
                                "provider_name": analysis_result.get("provider_name", ""),
                                "analysis_mode": analysis_result.get("analysis_mode", ""),
                                "prompt_version": analysis_result.get("prompt_version", ""),
                                "error_code": analysis_error_code,
                            }
                        ),
                        now_ts_ms if analysis_run_status == "completed" else None,
                        unresolved_file_object_ids,
                    ),
                )

            cursor.execute(
                """
                UPDATE stephen_dcx_contact_message_processing_jobs
                SET
                    job_status = %s,
                    last_error_code = %s,
                    locked_at_ts_ms = %s,
                    locked_by_worker = %s
                WHERE id = %s
                """,
                (
                    "completed" if analysis_run_status == "completed" else "failed",
                    analysis_error_code,
                    now_ts_ms,
                    "inline_message_analysis",
                    active_job_id,
                ),
            )

            cursor.execute(
                """
                INSERT INTO stephen_dcx_contact_message_analysis_runs (
                    message_id,
                    analysis_stage,
                    model_name,
                    input_summary_json,
                    output_text,
                    output_json,
                    run_status,
                    error_code,
                    completed_at_ts_ms
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    message_id,
                    "message_analysis",
                    analysis_result.get("model_name", ""),
                    psycopg2.extras.Json(
                        {
                            "provider_name": analysis_result.get("provider_name", ""),
                            "prompt_version": analysis_result.get("prompt_version", PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS),
                            "message_input": {
                                "message_id": message_input.get("message_id"),
                                "channel_type": message_input.get("channel_type"),
                                "provider_type": message_input.get("provider_type"),
                                "message_format": message_input.get("message_format"),
                                "message_subject_present": bool(message_input.get("message_subject")),
                                "raw_text_length": len(message_input.get("raw_text_content") or ""),
                            },
                            "attachments": [
                                {
                                    "attachment_id": attachment_input["attachment_id"],
                                    "file_object_id": attachment_input["file_object_id"],
                                    "file_kind": attachment_input["file_kind"],
                                    "content_type": attachment_input["content_type"],
                                    "file_size_bytes": attachment_input["file_size_bytes"],
                                    "original_filename": attachment_input["original_filename"],
                                    "included": any(
                                        file_input["file_object_id"] == attachment_input["file_object_id"]
                                        for file_input in file_inputs
                                    ),
                                }
                                for attachment_input in attachment_inputs
                            ],
                        }
                    ),
                    analysis_result.get("message_summary", ""),
                    psycopg2.extras.Json(analysis_result.get("raw_output_json", analysis_result)),
                    analysis_run_status,
                    analysis_error_code,
                    now_ts_ms if analysis_run_status == "completed" else None,
                ),
            )


def _read_language_id_for_code(cursor: Any, language_code: Any) -> int | None:
    if not isinstance(language_code, str) or language_code.strip() == "":
        return None
    cursor.execute(
        """
        SELECT id
        FROM stephen_dcx_languages
        WHERE language_code = %s
          AND is_active = TRUE
        LIMIT 1
        """,
        (language_code.strip().lower(),),
    )
    language_row = cursor.fetchone()
    return language_row[0] if language_row is not None else None


def _build_failed_analysis_result(error_code: str = "", error_detail: str = "") -> dict:
    return {
        "provider_name": "google_gemini",
        "model_name": "",
        "prompt_version": PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS,
        "analysis_mode": "failed",
        "message_language_code": None,
        "message_summary": "Message analysis failed.",
        "message_text_synthesis": "",
        "message_analysis_status": "failed",
        "attachments": [],
        "raw_output_json": {
            "error_code": error_code,
            "error_detail": error_detail,
        },
    }


def _read_exception_detail(exc: Exception) -> str:
    if exc.__cause__ is not None:
        return f"{type(exc.__cause__).__name__}: {exc.__cause__}"
    return f"{type(exc).__name__}: {exc}"


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
