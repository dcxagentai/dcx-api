"""
CONTEXT:
This file runs the first real AI analysis pass for one stored DCX contact message.
It exists so app, WhatsApp, and email intake can move from raw stored message plus attachments to
message-level and file-level analysis fields using one shared lifecycle.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import psycopg2
import psycopg2.extras

from apis.gemini.generate_dcx_gemini_structured_message_analysis import (
    PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS,
    generate_dcx_gemini_structured_message_analysis,
)
from apis.gemini.generate_dcx_gemini_structured_market_topic_seed import (
    generate_dcx_gemini_structured_market_topic_seed,
)
from apis.gemini.generate_dcx_gemini_structured_trade_projection import (
    generate_dcx_gemini_structured_trade_projection,
)
from apis.gemini.generate_dcx_gemini_user_content_policy_check import (
    generate_dcx_gemini_user_content_policy_check,
)
from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)
from apis.meta_whatsapp.send_dcx_whatsapp_message_workflow_outcome_notification import (
    send_dcx_whatsapp_message_workflow_outcome_notification,
)
from emails.transactional.send_dcx_email_message_workflow_outcome_notification import (
    send_dcx_email_message_workflow_outcome_notification,
)
from files.build_dcx_r2_s3_client import build_dcx_r2_s3_client
from files.read_dcx_r2_bucket_name_for_alias import read_dcx_r2_bucket_name_for_alias
from messages.build_dcx_market_topic_cross_surface_notification_text import (
    build_dcx_market_topic_cross_surface_notification_text,
)
from messages.build_dcx_app_trade_candidate_review_url import (
    build_dcx_app_trade_candidate_review_url,
)
from messages.create_dcx_trade_identity_with_first_version import (
    create_dcx_trade_identity_with_first_version,
)
from activity.record_dcx_user_activity_event import record_dcx_user_activity_event
from storage.db_config import DB_CONFIG
from usage.record_dcx_user_llm_usage_event import record_dcx_user_llm_usage_event

logger = logging.getLogger("uvicorn.error")


def process_stored_dcx_contact_message_analysis(
    message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    build_r2_client: Callable[[], Any] | None = None,
    analyze_message_content: Callable[[dict, list[dict]], dict] | None = None,
    check_content_policy: Callable[..., dict] | None = None,
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
      - process_stored_dcx_contact_message_analysis_test.py::test_rebuild_market_topic_projection_uses_supplied_database_connect_for_usage_recording
      - process_stored_dcx_contact_message_analysis_test.py::test_builds_one_consolidated_workflow_outcome_for_mixed_email_message

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
            - Confirm GEMINI_API_KEY and GEMINI_MESSAGE_ANALYSIS_MODEL.
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
            "moderation_status": message_input.get("moderation_status", "not_reviewed"),
            "workflow_classification_status": message_input.get("workflow_classification_status", "completed"),
            "was_noop": True,
        }

    try:
        file_inputs = _read_message_analysis_file_inputs_from_r2(
            attachment_inputs=attachment_inputs,
            build_r2_client=build_r2_client,
        )
        policy_check_result = (check_content_policy or generate_dcx_gemini_user_content_policy_check)(
            content_input=message_input,
            file_inputs=file_inputs,
        )
        _record_best_effort_content_policy_usage_event(
            user_id=message_input.get("user_id"),
            usage_source_id=message_id,
            policy_check_result=policy_check_result,
            connect=connect,
        )
        if _read_policy_check_moderation_status(policy_check_result) == "prohibited":
            analysis_result = _build_policy_blocked_analysis_result(
                message_input=message_input,
                file_inputs=file_inputs,
                policy_check_result=policy_check_result,
            )
        else:
            analysis_callable = analyze_message_content or generate_dcx_gemini_structured_message_analysis
            analysis_result = analysis_callable(message_input, file_inputs)
            analysis_result = _apply_content_policy_check_to_analysis_result(
                analysis_result=analysis_result,
                policy_check_result=policy_check_result,
            )
        analysis_run_status = "completed"
        analysis_error_code = None
    except RuntimeError as runtime_error:
        analysis_result = _build_failed_analysis_result(
            error_code=str(runtime_error),
            error_detail=_read_exception_detail(runtime_error),
            model_name=_read_best_effort_gemini_message_analysis_model_name(),
        )
        analysis_run_status = "failed"
        analysis_error_code = str(runtime_error)
    except Exception as exc:
        analysis_result = _build_failed_analysis_result(
            error_code="API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED",
            error_detail=_read_exception_detail(exc),
            model_name=_read_best_effort_gemini_message_analysis_model_name(),
        )
        analysis_run_status = "failed"
        analysis_error_code = "API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED"

    try:
        pending_workflow_outcome_notification = _persist_message_analysis_result(
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

    if analysis_run_status == "completed":
        _record_best_effort_llm_usage_event(
            user_id=message_input.get("user_id"),
            provider_name=analysis_result.get("provider_name", ""),
            model_name=analysis_result.get("model_name", ""),
            prompt_version=analysis_result.get("prompt_version", PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS),
            usage_source_kind="contact_message_analysis",
            usage_source_id=message_id,
            usage_metadata=analysis_result.get("usage_metadata"),
            connect=connect,
        )
        _record_best_effort_activity_event(
            user_id=message_input.get("user_id"),
            activity_kind="message_analysis_completed",
            surface=str(message_input.get("channel_type") or "app"),
            entity_kind="contact_message",
            entity_id=message_id,
            activity_summary="Message analysis completed.",
            activity_metadata={
                "message_format": message_input.get("message_format"),
                "moderation_status": analysis_result.get("moderation_status"),
                "primary_workflow_kind": analysis_result.get("primary_workflow_kind"),
            },
            connect=connect,
        )

    _deliver_message_workflow_outcome_notification(
        pending_notification=pending_workflow_outcome_notification,
        connect=connect,
        now_ts_ms=now_ts_ms,
    )

    return {
        "message_id": message_id,
        "job_id": active_job_id,
        "processing_status": "ready" if analysis_run_status == "completed" else "failed",
        "analysis_status": analysis_result.get("message_analysis_status", "failed"),
        "derivation_status": "completed" if analysis_run_status == "completed" else "failed",
        "moderation_status": analysis_result.get("moderation_status", "not_reviewed"),
        "workflow_classification_status": analysis_result.get("workflow_classification_status", "failed"),
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
                    user_id,
                    contact_method_id,
                    processing_status,
                    derivation_status,
                    analysis_status,
                    analysis_metadata_json,
                    workflow_classification_status,
                    primary_workflow_kind,
                    contains_trade_items,
                    contains_market_topic_items,
                    contains_other_items,
                    workflow_reason_summary,
                    workflow_metadata_json,
                    source_handle_normalized
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

            if (
                message_row[10] in {"completed", "partial"}
                and message_row[8] == "ready"
                and str(message_row[12] or "").strip().lower() == "completed"
            ):
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
                        "processing_status": message_row[8],
                        "derivation_status": message_row[9],
                        "analysis_status": message_row[10],
                        "moderation_status": _read_moderation_status_from_message_metadata(message_row[11]),
                        "workflow_classification_status": str(message_row[12] or "completed").strip() or "completed",
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
            "user_id": message_row[6],
            "contact_method_id": message_row[7],
            "source_handle_normalized": message_row[19],
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
) -> list[dict]:
    message_analysis_status = analysis_result.get("message_analysis_status", "failed")
    message_moderation_status = analysis_result.get("moderation_status", "not_reviewed")
    message_is_prohibited = message_moderation_status == "prohibited"
    processing_status = "ready" if analysis_run_status == "completed" else "failed"
    derivation_status = "completed" if analysis_run_status == "completed" else "failed"
    moderated_message_summary = (
        "Message blocked for prohibited content."
        if message_is_prohibited
        else analysis_result.get("message_summary", "")
    )
    moderated_message_text_synthesis = (
        ""
        if message_is_prohibited
        else analysis_result.get("message_text_synthesis", "")
    )
    moderated_message_subject = "" if message_is_prohibited else message_input.get("message_subject", "")
    moderated_raw_text_content = "" if message_is_prohibited else message_input.get("raw_text_content", "")
    moderation_metadata_json = {
        "moderation_status": message_moderation_status,
        "moderation_reason_codes": analysis_result.get("matched_prohibited_categories", []),
        "moderation_reason_summary": analysis_result.get("moderation_reason_summary", ""),
        "content_policy_check": analysis_result.get("policy_check_metadata_json", {}),
    }
    workflow_projection_state = _build_message_workflow_projection_state(
        analysis_result=analysis_result,
        analysis_run_status=analysis_run_status,
    )

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
                    message_subject = %s,
                    raw_text_content = %s,
                    analysis_summary_text = %s,
                    derived_text_content = %s,
                    detected_language_id = %s,
                    processing_status = %s,
                    derivation_status = %s,
                    analysis_status = %s,
                    analysis_model_name = %s,
                    analysis_metadata_json = analysis_metadata_json || %s::jsonb,
                    workflow_classification_status = %s,
                    primary_workflow_kind = %s,
                    contains_trade_items = %s,
                    contains_market_topic_items = %s,
                    contains_other_items = %s,
                    workflow_reason_summary = %s,
                    workflow_metadata_json = workflow_metadata_json || %s::jsonb,
                    analysis_completed_at_ts_ms = %s
                WHERE id = %s
                """,
                (
                    moderated_message_subject,
                    moderated_raw_text_content,
                    moderated_message_summary,
                    moderated_message_text_synthesis,
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
                            **moderation_metadata_json,
                        }
                    ),
                    workflow_projection_state["workflow_classification_status"],
                    workflow_projection_state["primary_workflow_kind"],
                    workflow_projection_state["contains_trade_items"],
                    workflow_projection_state["contains_market_topic_items"],
                    workflow_projection_state["contains_other_items"],
                    workflow_projection_state["workflow_reason_summary"],
                    psycopg2.extras.Json(workflow_projection_state["workflow_metadata_json"]),
                    now_ts_ms if analysis_run_status == "completed" else None,
                    message_id,
                ),
            )

            workflow_projection_result = _rebuild_message_workflow_projections(
                cursor=cursor,
                message_id=message_id,
                message_input=message_input,
                attachment_inputs=attachment_inputs,
                analysis_result=analysis_result,
                analysis_run_status=analysis_run_status,
                now_ts_ms=now_ts_ms,
                connect=connect,
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
                        (
                            "skipped"
                            if message_is_prohibited
                            else attachment_analysis.get("analysis_status", "completed")
                        ),
                        (
                            ""
                            if message_is_prohibited
                            else attachment_analysis.get("summary", "")
                        ),
                        (
                            ""
                            if message_is_prohibited
                            else attachment_analysis.get("description", "")
                        ),
                        (
                            ""
                            if message_is_prohibited
                            else attachment_analysis.get("transcription", "")
                        ),
                        (
                            ""
                            if message_is_prohibited
                            else attachment_analysis.get("synthesis", "")
                        ),
                        (
                            ""
                            if message_is_prohibited
                            else attachment_analysis.get("context_within_message", "")
                        ),
                        analysis_result.get("model_name", ""),
                        psycopg2.extras.Json(
                            {
                                "provider_name": analysis_result.get("provider_name", ""),
                                "analysis_mode": analysis_result.get("analysis_mode", ""),
                                "prompt_version": analysis_result.get("prompt_version", ""),
                                "attachment_id": attachment_analysis.get("attachment_id"),
                                **moderation_metadata_json,
                            }
                        ),
                        now_ts_ms if (
                            message_is_prohibited
                            or attachment_analysis.get("analysis_status") in {"completed", "partial", "skipped"}
                        ) else None,
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
                        (
                            "failed"
                            if analysis_run_status == "failed"
                            else "skipped"
                        ),
                        analysis_result.get("model_name", ""),
                        psycopg2.extras.Json(
                            {
                                "provider_name": analysis_result.get("provider_name", ""),
                                "analysis_mode": analysis_result.get("analysis_mode", ""),
                                "prompt_version": analysis_result.get("prompt_version", ""),
                                "error_code": analysis_error_code,
                                **moderation_metadata_json,
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

    return _build_message_workflow_outcome_notification_payload(
        message_id=message_id,
        message_input=message_input,
        analysis_result=analysis_result,
        analysis_run_status=analysis_run_status,
        workflow_projection_result=workflow_projection_result,
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


def _build_failed_analysis_result(
    error_code: str = "",
    error_detail: str = "",
    model_name: str = "",
) -> dict:
    return {
        "provider_name": "google_gemini",
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS,
        "analysis_mode": "failed",
        "message_language_code": None,
        "message_summary": "Message analysis failed.",
        "message_text_synthesis": "",
        "message_analysis_status": "failed",
        "moderation_status": "not_reviewed",
        "moderation_reason_summary": "",
        "matched_prohibited_categories": [],
        "primary_workflow_kind": "",
        "workflow_reason_summary": "",
        "workflow_classification_status": "failed",
        "workflow_items": [],
        "attachments": [],
        "usage_metadata": {},
        "raw_output_json": {
            "error_code": error_code,
            "error_detail": error_detail,
        },
    }


def _build_policy_blocked_analysis_result(
    message_input: dict,
    file_inputs: list[dict],
    policy_check_result: dict,
) -> dict:
    return {
        "provider_name": policy_check_result.get("provider_name", "google_gemini"),
        "model_name": policy_check_result.get("model_name", ""),
        "prompt_version": policy_check_result.get("prompt_version", ""),
        "analysis_mode": "policy_blocked",
        "message_language_code": None,
        "message_summary": "",
        "message_text_synthesis": "",
        "message_analysis_status": "completed",
        "moderation_status": "prohibited",
        "moderation_reason_summary": str(policy_check_result.get("moderation_reason_summary") or "").strip(),
        "matched_prohibited_categories": policy_check_result.get("matched_prohibited_categories", []),
        "primary_workflow_kind": "",
        "workflow_reason_summary": "",
        "workflow_classification_status": "completed",
        "workflow_items": [],
        "attachments": [
            {
                "attachment_id": file_input["attachment_id"],
                "file_object_id": file_input["file_object_id"],
                "filename": file_input["original_filename"],
                "file_kind": file_input["file_kind"],
                "language_code": None,
                "summary": "",
                "description": "",
                "transcription": "",
                "synthesis": "",
                "context_within_message": "",
                "analysis_status": "skipped",
            }
            for file_input in file_inputs
        ],
        "usage_metadata": {},
        "policy_check_metadata_json": _build_content_policy_metadata(policy_check_result),
        "raw_output_json": {
            "policy_check_result": policy_check_result.get("raw_output_json", {}),
            "message_id": message_input.get("message_id"),
        },
    }


def _apply_content_policy_check_to_analysis_result(
    analysis_result: dict,
    policy_check_result: dict,
) -> dict:
    normalized_result = {**analysis_result}
    normalized_result["policy_check_metadata_json"] = _build_content_policy_metadata(policy_check_result)
    policy_moderation_status = _read_policy_check_moderation_status(policy_check_result)
    if policy_moderation_status not in {"allowed", "prohibited"}:
        return normalized_result

    normalized_result["moderation_status"] = policy_moderation_status
    normalized_result["moderation_reason_summary"] = str(
        policy_check_result.get("moderation_reason_summary") or ""
    ).strip()
    normalized_result["matched_prohibited_categories"] = policy_check_result.get(
        "matched_prohibited_categories",
        [],
    )
    if policy_moderation_status == "prohibited":
        normalized_result["primary_workflow_kind"] = ""
        normalized_result["workflow_reason_summary"] = ""
        normalized_result["workflow_items"] = []
    return normalized_result


def _build_content_policy_metadata(policy_check_result: dict) -> dict:
    return {
        "provider_name": policy_check_result.get("provider_name", ""),
        "model_name": policy_check_result.get("model_name", ""),
        "prompt_version": policy_check_result.get("prompt_version", ""),
        "analysis_mode": policy_check_result.get("analysis_mode", ""),
        "policy_check_status": policy_check_result.get("policy_check_status", ""),
        "moderation_status": policy_check_result.get("moderation_status", ""),
        "matched_prohibited_categories": policy_check_result.get("matched_prohibited_categories", []),
        "should_redact_original": policy_check_result.get("should_redact_original") is True,
    }


def _read_policy_check_moderation_status(policy_check_result: dict) -> str:
    normalized_status = str(policy_check_result.get("moderation_status") or "").strip().lower()
    if normalized_status in {"allowed", "prohibited", "not_reviewed"}:
        return normalized_status
    return "not_reviewed"


def _record_best_effort_content_policy_usage_event(
    user_id: Any,
    usage_source_id: int | None,
    policy_check_result: dict,
    connect: Callable[..., Any],
) -> None:
    if policy_check_result.get("policy_check_status") != "completed":
        return
    _record_best_effort_llm_usage_event(
        user_id=user_id,
        provider_name=str(policy_check_result.get("provider_name") or ""),
        model_name=str(policy_check_result.get("model_name") or ""),
        prompt_version=str(policy_check_result.get("prompt_version") or ""),
        usage_source_kind="content_policy_check",
        usage_source_id=usage_source_id,
        usage_metadata=policy_check_result.get("usage_metadata"),
        connect=connect,
    )


def _record_best_effort_llm_usage_event(
    user_id: Any,
    provider_name: str,
    model_name: str,
    prompt_version: str,
    usage_source_kind: str,
    usage_source_id: int | None,
    usage_metadata: Any,
    connect: Callable[..., Any],
) -> None:
    if not isinstance(user_id, int) or user_id <= 0:
        return
    try:
        record_dcx_user_llm_usage_event(
            authenticated_user_id=user_id,
            provider_name=provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            usage_source_kind=usage_source_kind,
            usage_source_id=usage_source_id,
            usage_metadata=usage_metadata if isinstance(usage_metadata, dict) else {},
            connect_to_database=connect,
        )
    except RuntimeError:
        logger.exception(
            "dcx_llm_usage_record_failed user_id=%s source_kind=%s source_id=%s",
            user_id,
            usage_source_kind,
            usage_source_id,
        )


def _record_best_effort_activity_event(
    user_id: Any,
    activity_kind: str,
    surface: str,
    entity_kind: str,
    entity_id: int | None,
    activity_summary: str,
    activity_metadata: dict,
    connect: Callable[..., Any],
) -> None:
    if not isinstance(user_id, int) or user_id <= 0:
        return
    try:
        record_dcx_user_activity_event(
            user_id=user_id,
            activity_kind=activity_kind,
            surface=surface,
            entity_kind=entity_kind,
            entity_id=entity_id,
            activity_summary=activity_summary,
            activity_metadata=activity_metadata,
            connect_to_database=connect,
        )
    except RuntimeError:
        logger.exception(
            "dcx_activity_record_failed user_id=%s activity_kind=%s entity_kind=%s entity_id=%s",
            user_id,
            activity_kind,
            entity_kind,
            entity_id,
        )


def _read_best_effort_gemini_message_analysis_model_name() -> str:
    try:
        return read_dcx_gemini_message_analysis_model_name()
    except RuntimeError:
        return ""


def _read_moderation_status_from_message_metadata(message_metadata: Any) -> str:
    if not isinstance(message_metadata, dict):
        return "not_reviewed"
    normalized_status = str(message_metadata.get("moderation_status") or "").strip().lower()
    if normalized_status in {"allowed", "prohibited"}:
        return normalized_status
    return "not_reviewed"


def _build_attachment_projection_inputs(
    attachment_inputs: list[dict],
    analysis_result: dict,
) -> list[dict]:
    analysis_by_attachment_id = {
        attachment_analysis.get("attachment_id"): attachment_analysis
        for attachment_analysis in analysis_result.get("attachments", [])
        if attachment_analysis.get("attachment_id") is not None
    }
    return [
        {
            **attachment_input,
            "analysis_summary_text": str(
                analysis_by_attachment_id.get(attachment_input["attachment_id"], {}).get("summary") or ""
            ).strip(),
            "analysis_description_text": str(
                analysis_by_attachment_id.get(attachment_input["attachment_id"], {}).get("description") or ""
            ).strip(),
            "analysis_transcription_text": str(
                analysis_by_attachment_id.get(attachment_input["attachment_id"], {}).get("transcription") or ""
            ).strip(),
            "analysis_synthesis_text": str(
                analysis_by_attachment_id.get(attachment_input["attachment_id"], {}).get("synthesis") or ""
            ).strip(),
            "context_within_message": str(
                analysis_by_attachment_id.get(attachment_input["attachment_id"], {}).get("context_within_message") or ""
            ).strip(),
        }
        for attachment_input in attachment_inputs
    ]


def _build_message_workflow_projection_state(
    analysis_result: dict,
    analysis_run_status: str,
) -> dict:
    if analysis_run_status != "completed":
        return {
            "workflow_classification_status": "failed",
            "primary_workflow_kind": None,
            "contains_trade_items": False,
            "contains_market_topic_items": False,
            "contains_other_items": False,
            "workflow_reason_summary": "",
            "workflow_metadata_json": {
                "workflow_items": [],
                "projection_errors": [],
            },
        }

    if analysis_result.get("moderation_status") == "prohibited":
        return {
            "workflow_classification_status": "completed",
            "primary_workflow_kind": None,
            "contains_trade_items": False,
            "contains_market_topic_items": False,
            "contains_other_items": False,
            "workflow_reason_summary": "",
            "workflow_metadata_json": {
                "workflow_items": [],
                "projection_errors": [],
            },
        }

    workflow_items = analysis_result.get("workflow_items", [])
    primary_workflow_kind = str(analysis_result.get("primary_workflow_kind") or "").strip() or None
    return {
        "workflow_classification_status": str(analysis_result.get("workflow_classification_status") or "completed").strip() or "completed",
        "primary_workflow_kind": primary_workflow_kind,
        "contains_trade_items": any(item.get("item_kind") == "trade" for item in workflow_items),
        "contains_market_topic_items": any(item.get("item_kind") == "market_topic" for item in workflow_items),
        "contains_other_items": any(item.get("item_kind") == "other" for item in workflow_items),
        "workflow_reason_summary": str(analysis_result.get("workflow_reason_summary") or "").strip(),
        "workflow_metadata_json": {
            "workflow_items": workflow_items,
            "projection_errors": [],
        },
    }


def _rebuild_message_workflow_projections(
    cursor: Any,
    message_id: int,
    message_input: dict,
    attachment_inputs: list[dict],
    analysis_result: dict,
    analysis_run_status: str,
    now_ts_ms: int,
    connect: Callable[..., Any],
) -> dict:
    enriched_attachment_inputs = _build_attachment_projection_inputs(
        attachment_inputs=attachment_inputs,
        analysis_result=analysis_result,
    )
    cursor.execute(
        """
        DELETE FROM stephen_dcx_market_topic_turns
        WHERE market_topic_id IN (
            SELECT id
            FROM stephen_dcx_market_topics
            WHERE source_message_id = %s
        )
        """,
        (message_id,),
    )
    cursor.execute(
        "DELETE FROM stephen_dcx_trades WHERE source_message_id_initial = %s",
        (message_id,),
    )
    cursor.execute(
        "DELETE FROM stephen_dcx_market_topics WHERE source_message_id = %s",
        (message_id,),
    )
    cursor.execute(
        "DELETE FROM stephen_dcx_message_workflow_items WHERE message_id = %s",
        (message_id,),
    )

    if analysis_run_status != "completed" or analysis_result.get("moderation_status") == "prohibited":
        return _build_empty_workflow_projection_result()

    workflow_items = analysis_result.get("workflow_items", [])
    if not isinstance(workflow_items, list) or not workflow_items:
        return _build_empty_workflow_projection_result()

    projection_errors: list[dict] = []
    workflow_projection_result = _build_empty_workflow_projection_result()

    for workflow_item_index, workflow_item in enumerate(workflow_items, start=1):
        referenced_attachment_ids = workflow_item.get("referenced_attachment_ids", [])
        cursor.execute(
            """
            INSERT INTO stephen_dcx_message_workflow_items (
                message_id,
                item_index,
                item_kind,
                item_status,
                item_title,
                item_summary_text,
                source_excerpt_text,
                referenced_attachment_ids_json,
                confidence_label,
                workflow_item_metadata_json,
                created_at_ts_ms,
                updated_at_ts_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (
                message_id,
                workflow_item_index,
                workflow_item.get("item_kind", "other"),
                "identified",
                workflow_item.get("item_title", ""),
                workflow_item.get("item_summary", ""),
                workflow_item.get("source_excerpt_text", ""),
                psycopg2.extras.Json(referenced_attachment_ids),
                workflow_item.get("confidence_label", "medium"),
                psycopg2.extras.Json({"source_prompt": "message_analysis"}),
                now_ts_ms,
                now_ts_ms,
            ),
        )
        workflow_item_id = cursor.fetchone()[0]
        referenced_attachment_inputs = [
            attachment_input
            for attachment_input in enriched_attachment_inputs
            if attachment_input["attachment_id"] in referenced_attachment_ids
        ]

        item_kind = workflow_item.get("item_kind")
        if item_kind == "trade":
            try:
                trade_projection = generate_dcx_gemini_structured_trade_projection(
                    message_input={
                        **message_input,
                        "analysis_summary_text": analysis_result.get("message_summary", ""),
                        "derived_text_content": analysis_result.get("message_text_synthesis", ""),
                    },
                    workflow_item=workflow_item,
                    attachment_inputs=referenced_attachment_inputs,
                )
                _record_best_effort_llm_usage_event(
                    user_id=message_input.get("user_id"),
                    provider_name=trade_projection.get("provider_name", ""),
                    model_name=trade_projection.get("model_name", ""),
                    prompt_version=trade_projection.get("prompt_version", ""),
                    usage_source_kind="trade_projection",
                    usage_source_id=message_id,
                    usage_metadata=trade_projection.get("usage_metadata"),
                    connect=connect,
                )
                source_language_id = _read_language_id_for_code(
                    cursor=cursor,
                    language_code=analysis_result.get("message_language_code"),
                )
                trade_id = create_dcx_trade_identity_with_first_version(
                    cursor=cursor,
                    initiating_user_id=message_input.get("user_id"),
                    initiating_contact_method_id=message_input.get("contact_method_id"),
                    source_message_id=message_id,
                    source_workflow_item_id=workflow_item_id,
                    source_channel_type=message_input.get("channel_type", ""),
                    source_language_id=source_language_id,
                    trade_projection_status="completed",
                    trade_confirmation_status=(
                        "needs_more_detail" if trade_projection.get("missing_required_fields") else "pending_confirmation"
                    ),
                    trade_status="draft",
                    trade_projection=trade_projection,
                    version_source_type="llm_projection",
                    now_ts_ms=now_ts_ms,
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_message_workflow_items
                    SET item_status = 'projected', updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, workflow_item_id),
                )
                workflow_projection_result["trade_outputs"].append(
                    {
                        "trade_id": trade_id,
                        "workflow_item_id": workflow_item_id,
                        "title": str(workflow_item.get("item_title") or "").strip(),
                        "summary": str(trade_projection.get("trade_summary_text") or workflow_item.get("item_summary") or "").strip(),
                    }
                )
                _record_best_effort_activity_event(
                    user_id=message_input.get("user_id"),
                    activity_kind="trade_candidate_created",
                    surface=str(message_input.get("channel_type") or "app"),
                    entity_kind="trade",
                    entity_id=trade_id,
                    activity_summary="Trade candidate created from a message.",
                    activity_metadata={
                        "source_message_id": message_id,
                        "source_workflow_item_id": workflow_item_id,
                    },
                    connect=connect,
                )
            except Exception as exc:
                projection_errors.append(
                    {
                        "item_index": workflow_item_index,
                        "item_kind": item_kind,
                        "error_code": "API_DCX_GEMINI_TRADE_PROJECTION_FAILED",
                        "error_detail": _read_exception_detail(exc),
                    }
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_message_workflow_items
                    SET item_status = 'failed', updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, workflow_item_id),
                )
        elif item_kind in {"market_topic", "other"}:
            try:
                topic_seed = generate_dcx_gemini_structured_market_topic_seed(
                    message_input={
                        **message_input,
                        "analysis_summary_text": analysis_result.get("message_summary", ""),
                        "derived_text_content": analysis_result.get("message_text_synthesis", ""),
                    },
                    workflow_item=workflow_item,
                    attachment_inputs=referenced_attachment_inputs,
                )
                _record_best_effort_llm_usage_event(
                    user_id=message_input.get("user_id"),
                    provider_name=topic_seed.get("provider_name", ""),
                    model_name=topic_seed.get("model_name", ""),
                    prompt_version=topic_seed.get("prompt_version", ""),
                    usage_source_kind="market_topic_seed",
                    usage_source_id=message_id,
                    usage_metadata=topic_seed.get("usage_metadata"),
                    connect=connect,
                )
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_market_topics (
                        source_message_id,
                        source_workflow_item_id,
                        initiating_user_id,
                        initiating_contact_method_id,
                        topic_status,
                        topic_title,
                        topic_summary_text,
                        topic_scope_text,
                        topic_tags_json,
                        topic_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                    RETURNING id
                    """,
                    (
                        message_id,
                        workflow_item_id,
                        message_input.get("user_id"),
                        message_input.get("contact_method_id"),
                        topic_seed.get("topic_title", ""),
                        topic_seed.get("topic_summary_text", ""),
                        topic_seed.get("topic_scope_text", ""),
                        psycopg2.extras.Json(topic_seed.get("topic_tags", [])),
                        psycopg2.extras.Json(
                            {
                                "provider_name": topic_seed.get("provider_name", ""),
                                "model_name": topic_seed.get("model_name", ""),
                                "prompt_version": topic_seed.get("prompt_version", ""),
                                "grounding_metadata": topic_seed.get("grounding_metadata", {}),
                                "raw_output_json": topic_seed.get("raw_output_json", {}),
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                market_topic_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_market_topic_turns (
                        market_topic_id,
                        turn_role,
                        source_message_id,
                        turn_text,
                        turn_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES
                        (%s, 'user', %s, %s, %s::jsonb, %s, %s),
                        (%s, 'assistant', %s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        market_topic_id,
                        message_id,
                        workflow_item.get("source_excerpt_text") or workflow_item.get("item_summary", ""),
                        psycopg2.extras.Json(
                            {
                                "seed_turn": True,
                                "source_surface": message_input.get("channel_type") or "app",
                                "source_channel_type": message_input.get("channel_type") or "app",
                                "source_contact_method_id": message_input.get("contact_method_id"),
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                        market_topic_id,
                        message_id,
                        topic_seed.get("opening_ai_response_text", ""),
                        psycopg2.extras.Json({"seed_turn": True, "source_surface": "ai"}),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_message_workflow_items
                    SET item_status = 'projected', updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, workflow_item_id),
                )
                workflow_projection_result["market_topic_outputs"].append(
                    {
                        "market_topic_id": market_topic_id,
                        "workflow_item_id": workflow_item_id,
                        "title": str(topic_seed.get("topic_title") or workflow_item.get("item_title") or "").strip(),
                        "summary": str(topic_seed.get("topic_summary_text") or workflow_item.get("item_summary") or "").strip(),
                        "opening_ai_response_text": str(topic_seed.get("opening_ai_response_text") or "").strip(),
                    }
                )
                _record_best_effort_activity_event(
                    user_id=message_input.get("user_id"),
                    activity_kind="market_topic_created",
                    surface=str(message_input.get("channel_type") or "app"),
                    entity_kind="market_topic",
                    entity_id=market_topic_id,
                    activity_summary="Market topic created from a message.",
                    activity_metadata={
                        "source_message_id": message_id,
                        "source_workflow_item_id": workflow_item_id,
                    },
                    connect=connect,
                )
            except Exception as exc:
                projection_errors.append(
                    {
                        "item_index": workflow_item_index,
                        "item_kind": item_kind,
                        "error_code": "API_DCX_GEMINI_MARKET_TOPIC_SEED_FAILED",
                        "error_detail": _read_exception_detail(exc),
                    }
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_message_workflow_items
                    SET item_status = 'failed', updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, workflow_item_id),
                )
        else:
            cursor.execute(
                """
                UPDATE stephen_dcx_message_workflow_items
                SET item_status = 'projected', updated_at_ts_ms = %s
                WHERE id = %s
                """,
                (now_ts_ms, workflow_item_id),
            )
            workflow_projection_result["other_outputs"].append(
                {
                    "workflow_item_id": workflow_item_id,
                    "title": str(workflow_item.get("item_title") or "Other message").strip(),
                    "summary": str(workflow_item.get("item_summary") or "").strip(),
                }
            )

    workflow_classification_status = "partial" if projection_errors else "completed"
    workflow_projection_result["projection_errors"] = projection_errors
    cursor.execute(
        """
        UPDATE stephen_dcx_contact_messages
        SET
            workflow_classification_status = %s,
            workflow_metadata_json = workflow_metadata_json || %s::jsonb,
            workflow_completed_at_ts_ms = %s
        WHERE id = %s
        """,
        (
            workflow_classification_status,
            psycopg2.extras.Json(
                {
                    "workflow_items": workflow_items,
                    "projection_errors": projection_errors,
                }
            ),
            now_ts_ms,
            message_id,
        ),
    )
    return workflow_projection_result


def _build_empty_workflow_projection_result() -> dict:
    return {
        "trade_outputs": [],
        "market_topic_outputs": [],
        "other_outputs": [],
        "projection_errors": [],
    }


def _build_message_workflow_outcome_notification_payload(
    message_id: int,
    message_input: dict,
    analysis_result: dict,
    analysis_run_status: str,
    workflow_projection_result: dict,
) -> dict | None:
    channel_type = str(message_input.get("channel_type") or "").strip().lower()
    recipient_handle = str(message_input.get("source_handle_normalized") or "").strip()
    if channel_type not in {"whatsapp", "email"} or recipient_handle == "" or analysis_run_status != "completed":
        return None

    trade_outputs = workflow_projection_result.get("trade_outputs", [])
    topic_outputs = workflow_projection_result.get("market_topic_outputs", [])
    other_outputs = workflow_projection_result.get("other_outputs", [])
    projection_errors = workflow_projection_result.get("projection_errors", [])
    moderation_status = str(analysis_result.get("moderation_status") or "").strip().lower()

    if moderation_status == "prohibited":
        return {
            "message_id": message_id,
            "channel_type": channel_type,
            "recipient_handle": recipient_handle,
            "subject": "DCX message blocked",
            "message_text": (
                "We received your message, but it was blocked by DCX content policy.\n\n"
                "It has not been routed into a trade or market topic workflow."
            ),
            "trade_ids": [],
            "market_topic_ids": [],
        }

    message_lines: list[str] = []

    if trade_outputs:
        message_lines.append("")
        message_lines.append("Trade candidates:")
        for trade_output in trade_outputs:
            trade_id = trade_output["trade_id"]
            trade_summary = _read_first_nonempty_text(
                trade_output.get("summary"),
                trade_output.get("title"),
                f"Trade candidate #{trade_id}",
            )
            message_lines.append(trade_summary)
            message_lines.append(f"Review: {build_dcx_app_trade_candidate_review_url(trade_id)}")

    if topic_outputs:
        if message_lines:
            message_lines.append("")
        for topic_output in topic_outputs:
            market_topic_id = topic_output["market_topic_id"]
            topic_reference_code = f"T{market_topic_id}"
            topic_title = _read_first_nonempty_text(
                topic_output.get("title"),
                topic_output.get("summary"),
                f"Market topic #{market_topic_id}",
            )
            opening_ai_response_text = _read_first_nonempty_text(topic_output.get("opening_ai_response_text"))
            if opening_ai_response_text:
                message_lines.append(
                    build_dcx_market_topic_cross_surface_notification_text(
                        market_topic_id=market_topic_id,
                        route_reference_code=topic_reference_code,
                        topic_title=topic_title,
                        message_text=opening_ai_response_text,
                        include_source_links=channel_type != "whatsapp",
                    )
                )

    if not trade_outputs and not topic_outputs and other_outputs:
        message_lines.append("")
        message_lines.append("We saved your message. It was not treated as a trade or market topic.")

    if not trade_outputs and not topic_outputs and not other_outputs:
        message_lines.append("")
        message_lines.append("We saved your message, but no trade or market topic workflow was created.")

    if projection_errors:
        message_lines.append("")
        message_lines.append("Some items could not be routed yet. You can retry workflow processing from the DCX app.")

    subject = "DCX processed your message"
    if trade_outputs and topic_outputs:
        subject = "DCX found trades and market topics"
    elif trade_outputs:
        subject = "DCX found trade candidates"
    elif topic_outputs:
        if len(topic_outputs) == 1:
            topic_title = _read_first_nonempty_text(
                topic_outputs[0].get("title"),
                topic_outputs[0].get("summary"),
                f"Market topic #{topic_outputs[0]['market_topic_id']}",
            )
            subject = f"DCX: {topic_title}"
        else:
            subject = "DCX opened market topics"
    elif other_outputs:
        subject = "DCX saved your message"

    return {
        "message_id": message_id,
        "channel_type": channel_type,
        "recipient_handle": recipient_handle,
        "subject": subject,
        "message_text": "\n".join(message_lines).strip(),
        "trade_ids": [trade_output["trade_id"] for trade_output in trade_outputs],
        "market_topic_ids": [topic_output["market_topic_id"] for topic_output in topic_outputs],
    }


def _read_first_nonempty_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip() != "":
            return value.strip()
    return ""


def _deliver_message_workflow_outcome_notification(
    pending_notification: dict | None,
    connect: Callable[..., Any],
    now_ts_ms: int,
) -> None:
    if pending_notification is None:
        return

    try:
        if pending_notification["channel_type"] == "whatsapp":
            send_dcx_whatsapp_message_workflow_outcome_notification(
                phone_e164=pending_notification["recipient_handle"],
                message_text=pending_notification["message_text"],
            )
        elif pending_notification["channel_type"] == "email":
            send_dcx_email_message_workflow_outcome_notification(
                recipient_email=pending_notification["recipient_handle"],
                subject=pending_notification["subject"],
                message_text=pending_notification["message_text"],
            )
        _mark_message_workflow_outcome_notification_result(
            connect=connect,
            pending_notification=pending_notification,
            notification_status="sent",
            notification_error="",
            now_ts_ms=now_ts_ms,
        )
    except Exception as exc:
        logger.warning(
            "message_workflow_outcome_notification_failed "
            "message_id=%s channel=%s recipient=%s error=%s",
            pending_notification.get("message_id"),
            pending_notification.get("channel_type"),
            pending_notification.get("recipient_handle"),
            _read_exception_detail(exc),
        )
        _mark_message_workflow_outcome_notification_result(
            connect=connect,
            pending_notification=pending_notification,
            notification_status="failed",
            notification_error=_read_exception_detail(exc),
            now_ts_ms=now_ts_ms,
        )


def _mark_message_workflow_outcome_notification_result(
    connect: Callable[..., Any],
    pending_notification: dict,
    notification_status: str,
    notification_error: str,
    now_ts_ms: int,
) -> None:
    trade_ids = [
        trade_id
        for trade_id in pending_notification.get("trade_ids", [])
        if isinstance(trade_id, int) and trade_id > 0
    ]
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_contact_messages
                SET workflow_metadata_json = workflow_metadata_json || %s::jsonb
                WHERE id = %s
                """,
                (
                    psycopg2.extras.Json(
                        {
                            "workflow_outcome_notification": {
                                "status": notification_status,
                                "error": notification_error,
                                "channel_type": pending_notification.get("channel_type"),
                                "sent_at_ts_ms": now_ts_ms if notification_status == "sent" else None,
                                "trade_ids": trade_ids,
                                "market_topic_ids": pending_notification.get("market_topic_ids", []),
                            }
                        }
                    ),
                    pending_notification["message_id"],
                ),
            )
            if trade_ids:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_trade_versions trade_version
                    SET
                        trade_metadata_json = trade_version.trade_metadata_json || %s::jsonb
                    FROM stephen_dcx_trades trade
                    WHERE trade.id = ANY(%s)
                      AND trade.current_version_id = trade_version.id
                    """,
                    (
                        psycopg2.extras.Json(
                            {
                                "confirmation_notification_status": notification_status,
                                "confirmation_notification_error": notification_error,
                                "confirmation_notification_sent_at_ts_ms": (
                                    now_ts_ms if notification_status == "sent" else None
                                ),
                                "workflow_outcome_notification_status": notification_status,
                                "workflow_outcome_notification_error": notification_error,
                                "workflow_outcome_notification_sent_at_ts_ms": (
                                    now_ts_ms if notification_status == "sent" else None
                                ),
                            }
                        ),
                        trade_ids,
                    ),
                )


def _mark_trade_candidate_confirmation_notification_result(
    connect: Callable[..., Any],
    trade_id: int,
    notification_status: str,
    notification_error: str,
    now_ts_ms: int,
) -> None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_trade_versions trade_version
                SET
                    trade_metadata_json = trade_version.trade_metadata_json || %s::jsonb
                FROM stephen_dcx_trades trade
                WHERE trade.id = %s
                  AND trade.current_version_id = trade_version.id
                """,
                (
                    psycopg2.extras.Json(
                        {
                            "confirmation_notification_status": notification_status,
                            "confirmation_notification_error": notification_error,
                            "confirmation_notification_sent_at_ts_ms": (
                                now_ts_ms if notification_status == "sent" else None
                            ),
                        }
                    ),
                    trade_id,
                ),
            )


def _read_exception_detail(exc: Exception) -> str:
    if exc.__cause__ is not None:
        return f"{type(exc.__cause__).__name__}: {exc.__cause__}"
    return f"{type(exc).__name__}: {exc}"


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
