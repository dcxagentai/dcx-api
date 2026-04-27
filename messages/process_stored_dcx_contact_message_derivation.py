"""
CONTEXT:
This file runs the first derivation pass for one already-persisted DCX contact message row.
It exists so inbound app, WhatsApp, and email message paths can converge on one shared stored-message
derivation lifecycle once the canonical message row already exists.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
import psycopg2.extras

from messages.derive_dcx_contact_message_text_and_language_with_llm import (
    derive_dcx_contact_message_text_and_language_with_llm,
)
from storage.db_config import DB_CONFIG


def process_stored_dcx_contact_message_derivation(
    message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    derive_message_with_llm: Callable[[str], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - message_id identifies one existing row in stephen_dcx_contact_messages.
        - The stored message contains raw text when derivation should run.
        - The configured database is reachable.
      postconditions:
        - Creates or reuses one processing job row for the message.
        - Updates the message row with one derivation result, or marks the message failed.
        - Writes one analysis-run row when derivation is attempted.
      side_effects:
        - writes to stephen_dcx_contact_message_processing_jobs
        - updates stephen_dcx_contact_messages
        - writes to stephen_dcx_contact_message_analysis_runs
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: message_derivation:{message_id}
      locks:
        - row lock on the target stephen_dcx_contact_messages row
        - row lock on the newest processing job row when one exists
      contention_strategy: duplicate derivation attempts converge on the same message row and return the completed state when derivation already finished

    NARRATIVE:
      WHY this exists:
        - All ingress channels need one shared way to move a stored message from raw text to the first
          derived-text / summary / language state.
      WHEN TO USE it:
        - Use it immediately after inserting one inbound message row from a provider or app surface.
      WHEN NOT TO USE it:
        - Do not use it as the final business-intent classifier.
      WHAT CAN GO WRONG:
        - The message row can be missing.
        - The model call can fail.
        - The follow-up update transaction can fail after the model already returned.
      WHAT COMES NEXT:
        - Later stages can branch from this stored derivation into trade, reply, question, or noise workflows.

    TESTS:
      - marks_message_not_required_when_raw_text_is_blank
      - returns_existing_completed_state_without_duplicate_derivation

    ERRORS:
      - API_DCX_CONTACT_MESSAGE_DERIVATION_MESSAGE_NOT_FOUND:
          suggested_action: Retry only after confirming the target message row exists.
          common_causes:
            - stale message id
            - prior insert rollback
          recovery_steps:
            - Confirm the message row exists in stephen_dcx_contact_messages.
            - Retry from the ingress flow if needed.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_DERIVATION_PROCESS_FAILED:
          suggested_action: Retry after the backend and database are healthy.
          common_causes:
            - database unavailable
            - write failure after derivation
          recovery_steps:
            - Confirm database connectivity.
            - Retry once the backend is stable.
          retry_safe: true
          what_changed: the message may already exist but the derivation state may be incomplete
          rollback_needed: inspect_before_manual_replay
          rollback_operation: inspect the message, job, and analysis tables for the target message id

    CODE:
    """
    if not isinstance(message_id, int) or message_id <= 0:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_DERIVATION_MESSAGE_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        raw_text_content,
                        processing_status,
                        derivation_status
                    FROM stephen_dcx_contact_messages
                    WHERE id = %s
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (message_id,),
                )
                message_row = cursor.fetchone()
                if message_row is None:
                    raise RuntimeError("API_DCX_CONTACT_MESSAGE_DERIVATION_MESSAGE_NOT_FOUND")

                if message_row[2] == "ready" and message_row[3] in {"completed", "not_required"}:
                    cursor.execute(
                        """
                        SELECT id
                        FROM stephen_dcx_contact_message_processing_jobs
                        WHERE message_id = %s
                        ORDER BY created_at_ts_ms DESC, id DESC
                        LIMIT 1
                        """,
                        (message_id,),
                    )
                    latest_job_row = cursor.fetchone()
                    return {
                        "message_id": message_id,
                        "job_id": latest_job_row[0] if latest_job_row is not None else None,
                        "processing_status": message_row[2],
                        "derivation_status": message_row[3],
                        "was_noop": True,
                    }

                normalized_raw_text = (message_row[1] or "").strip()
                if normalized_raw_text == "":
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_contact_messages
                        SET
                            processing_status = 'ready',
                            derivation_status = 'not_required',
                            analysis_summary_text = CASE
                                WHEN analysis_summary_text = '' THEN %s
                                ELSE analysis_summary_text
                            END
                        WHERE id = %s
                        """,
                        ("No textual content was available for the first derivation pass.", message_id),
                    )
                    return {
                        "message_id": message_id,
                        "job_id": None,
                        "processing_status": "ready",
                        "derivation_status": "not_required",
                        "was_noop": False,
                    }

                cursor.execute(
                    """
                    SELECT id, job_status, attempt_count
                    FROM stephen_dcx_contact_message_processing_jobs
                    WHERE message_id = %s
                      AND job_type = 'derive_message_content'
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
                        VALUES (%s, 'derive_message_content', 'processing', %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            message_id,
                            1,
                            now_ts_ms,
                            now_ts_ms,
                            "inline_message_derivation",
                        ),
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
                        (
                            existing_job_row[2] + 1,
                            now_ts_ms,
                            "inline_message_derivation",
                            existing_job_row[0],
                        ),
                    )
                    active_job_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    UPDATE stephen_dcx_contact_messages
                    SET
                        processing_status = 'processing',
                        derivation_status = 'pending'
                    WHERE id = %s
                    """,
                    (message_id,),
                )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_DERIVATION_PROCESS_FAILED") from exc

    derivation_callable = derive_message_with_llm or derive_dcx_contact_message_text_and_language_with_llm
    try:
        derivation_result = derivation_callable(normalized_raw_text)
        derivation_status = "completed"
        processing_status = "ready"
        analysis_run_status = "completed"
        analysis_error_code = None
    except RuntimeError as runtime_error:
        derivation_result = {
            "derived_text_content": "",
            "analysis_summary_text": "Message derivation failed.",
            "detected_language_code": None,
            "derivation_mode": "failed",
            "model_name": "",
        }
        derivation_status = "failed"
        processing_status = "failed"
        analysis_run_status = "failed"
        analysis_error_code = str(runtime_error)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                detected_language_id = None
                detected_language_code = derivation_result.get("detected_language_code")
                if isinstance(detected_language_code, str) and detected_language_code != "":
                    cursor.execute(
                        """
                        SELECT id
                        FROM stephen_dcx_languages
                        WHERE language_code = %s
                          AND is_active = TRUE
                        LIMIT 1
                        """,
                        (detected_language_code,),
                    )
                    language_row = cursor.fetchone()
                    if language_row is not None:
                        detected_language_id = language_row[0]

                cursor.execute(
                    """
                    UPDATE stephen_dcx_contact_messages
                    SET
                        derived_text_content = %s,
                        analysis_summary_text = %s,
                        detected_language_id = %s,
                        processing_status = %s,
                        derivation_status = %s,
                        message_metadata_json = message_metadata_json || %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        derivation_result["derived_text_content"],
                        derivation_result["analysis_summary_text"],
                        detected_language_id,
                        processing_status,
                        derivation_status,
                        psycopg2.extras.Json(
                            {
                                "derivation_mode": derivation_result["derivation_mode"],
                                "model_name": derivation_result["model_name"],
                            }
                        ),
                        message_id,
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
                        "inline_message_derivation",
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
                        "message_derivation",
                        derivation_result["model_name"],
                        psycopg2.extras.Json(
                            {
                                "raw_text_preview": normalized_raw_text[:400],
                            }
                        ),
                        derivation_result["analysis_summary_text"],
                        psycopg2.extras.Json(
                            {
                                "derived_text_content": derivation_result["derived_text_content"],
                                "detected_language_code": derivation_result["detected_language_code"],
                                "derivation_mode": derivation_result["derivation_mode"],
                            }
                        ),
                        analysis_run_status,
                        analysis_error_code,
                        now_ts_ms,
                    ),
                )
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_DERIVATION_PROCESS_FAILED") from exc

    return {
        "message_id": message_id,
        "job_id": active_job_id,
        "processing_status": processing_status,
        "derivation_status": derivation_status,
        "was_noop": False,
    }


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
