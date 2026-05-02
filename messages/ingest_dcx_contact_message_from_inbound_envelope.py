"""
CONTEXT:
This file ingests one already-normalized inbound provider envelope into the DCX contact-message
system and runs the first derivation pass when text is available.
It exists so WhatsApp and inbound email can converge on the same canonical message model without
duplicating persistence rules in each provider-specific flow.
"""

from __future__ import annotations

from email.utils import parseaddr
from typing import Any, Callable

import psycopg2
import psycopg2.extras

from messages.process_stored_dcx_contact_message_analysis import (
    process_stored_dcx_contact_message_analysis,
)
from messages.read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds import (
    read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds,
)
from messages.route_dcx_inbound_contact_message_to_trade_thread_if_applicable import (
    route_dcx_inbound_contact_message_to_trade_thread_if_applicable,
)
from messages.store_dcx_contact_message_attachment_file_object import (
    store_dcx_contact_message_attachment_file_object,
)
from storage.db_config import DB_CONFIG


def ingest_dcx_contact_message_from_inbound_envelope(
    provider_event_row_id: int,
    provider_type: str,
    channel_type: str,
    provider_message_id: str,
    source_handle: str,
    target_handle: str | None,
    message_format: str,
    raw_text_content: str,
    received_at_ts_ms: int,
    message_subject: str = "",
    message_metadata_json: dict | None = None,
    attachment_inputs: list[dict] | None = None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    derive_message_with_llm: Callable[[str], dict] | None = None,
    store_message_attachment: Callable[..., dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - provider_event_row_id identifies one stored provider-event row.
        - provider_message_id uniquely identifies the inbound provider message.
        - source_handle identifies the provider-side sender.
        - The configured database is reachable.
      postconditions:
        - Persists one canonical inbound message row, reusing the existing row on duplicate provider-message delivery.
        - Resolves the sender to a user/contact method when a verified DCX contact match exists.
        - Persists supported attachment rows when attachment_inputs are provided.
        - Runs the first derivation pass when raw text is present.
      side_effects:
        - writes to stephen_dcx_contact_messages
        - may write to stephen_dcx_file_objects
        - may write to stephen_dcx_contact_message_attachments
        - may write to stephen_dcx_contact_message_processing_jobs
        - may write to stephen_dcx_contact_message_analysis_runs
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: inbound_message:{provider_type}:{provider_message_id}
      locks:
        - unique-index contention on stephen_dcx_contact_messages(provider_type, external_message_id, message_direction)
      contention_strategy: duplicate provider-message deliveries converge on one canonical inbound message row

    NARRATIVE:
      WHY this exists:
        - Each provider-specific intake path should normalize to one stored message row before any
          downstream workflow classification begins.
      WHEN TO USE it:
        - Use it after one provider payload has been verified and reduced to a single message envelope.
      WHEN NOT TO USE it:
        - Do not use it for browser-authenticated app messages.
      WHAT CAN GO WRONG:
        - The sender may not map to a known DCX user.
        - The message row insert can fail.
        - One attachment can be unsupported or too large.
        - The derivation step can fail after the message row already exists.
      WHAT COMES NEXT:
        - Later media attachment storage and richer classification can hang off the same canonical row.

    TESTS:
      - none yet in this first provider-intake pass

    ERRORS:
      - API_DCX_CONTACT_MESSAGE_INBOUND_ENVELOPE_INVALID:
          suggested_action: Retry only after confirming the provider envelope fields are complete.
          common_causes:
            - missing provider_message_id
            - missing source_handle
          recovery_steps:
            - Confirm the provider payload was normalized correctly.
            - Retry with a complete envelope.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_INBOUND_ENVELOPE_INGEST_FAILED:
          suggested_action: Retry after the backend and database are healthy.
          common_causes:
            - database unavailable
            - insert failure
          recovery_steps:
            - Confirm database connectivity.
            - Retry once the backend is stable.
          retry_safe: true
          what_changed: the provider event may already exist while the message row is incomplete
          rollback_needed: inspect_before_manual_replay
          rollback_operation: inspect provider-event and message rows for the provider message id

    CODE:
    """
    normalized_provider_message_id = provider_message_id.strip() if isinstance(provider_message_id, str) else ""
    if normalized_provider_message_id == "" or not isinstance(source_handle, str) or source_handle.strip() == "":
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_INBOUND_ENVELOPE_INVALID")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()
    resolution = _resolve_dcx_user_contact_for_inbound_handle(
        channel_type=channel_type,
        source_handle=source_handle,
        connect_to_database=connect,
    )
    normalized_source_handle = resolution["normalized_source_handle"]
    normalized_target_handle = _normalize_inbound_handle(channel_type=channel_type, raw_handle=target_handle)
    normalized_raw_text = raw_text_content.strip() if isinstance(raw_text_content, str) else ""
    normalized_attachment_inputs = [
        attachment_input
        for attachment_input in (attachment_inputs or [])
        if isinstance(attachment_input, dict)
    ]
    next_processing_status = "queued" if normalized_raw_text != "" else "ready"
    next_derivation_status = "pending" if normalized_raw_text != "" else "not_required"
    merged_message_metadata_json = {
        "resolution_status": resolution["resolution_status"],
        "source_contact_is_verified": resolution["source_contact_is_verified"],
        **(message_metadata_json or {}),
    }

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_contact_messages (
                        user_id,
                        contact_method_id,
                        provider_event_id,
                        channel_type,
                        provider_type,
                        message_direction,
                        message_format,
                        external_message_id,
                        source_handle_normalized,
                        target_handle_normalized,
                        message_subject,
                        raw_text_content,
                        message_metadata_json,
                        processing_status,
                        derivation_status,
                        visible_to_user,
                        received_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, 'inbound', %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, TRUE, %s)
                    ON CONFLICT (provider_type, external_message_id, message_direction)
                    WHERE external_message_id IS NOT NULL
                    DO UPDATE
                    SET
                        updated_at_ts_ms = %s,
                        provider_event_id = COALESCE(stephen_dcx_contact_messages.provider_event_id, EXCLUDED.provider_event_id),
                        message_metadata_json = stephen_dcx_contact_messages.message_metadata_json || EXCLUDED.message_metadata_json
                    RETURNING id
                    """,
                    (
                        resolution["user_id"],
                        resolution["contact_method_id"],
                        provider_event_row_id,
                        channel_type,
                        provider_type,
                        message_format,
                        normalized_provider_message_id,
                        normalized_source_handle,
                        normalized_target_handle,
                        message_subject.strip() if isinstance(message_subject, str) else "",
                        normalized_raw_text,
                        psycopg2.extras.Json(merged_message_metadata_json),
                        next_processing_status,
                        next_derivation_status,
                        received_at_ts_ms,
                        now_ts_ms,
                    ),
                )
                stored_message_id = cursor.fetchone()[0]
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_INBOUND_ENVELOPE_INGEST_FAILED") from exc

    stored_attachment_rows: list[dict] = []
    skipped_attachment_errors: list[dict] = []
    for attachment_index, attachment_input in enumerate(normalized_attachment_inputs, start=1):
        try:
            stored_attachment_rows.append(
                (store_message_attachment or store_dcx_contact_message_attachment_file_object)(
                    message_id=stored_message_id,
                    owner_user_id=resolution["user_id"],
                    source_channel_type=channel_type,
                    source_provider_type=provider_type,
                    original_filename=attachment_input.get("original_filename"),
                    file_bytes=attachment_input.get("file_bytes"),
                    content_type=attachment_input.get("content_type"),
                    provider_media_id=attachment_input.get("provider_media_id"),
                    sort_order=attachment_index,
                    connect_to_database=connect,
                    current_timestamp_ms_provider=current_timestamp_ms_provider,
                )
            )
        except RuntimeError as runtime_error:
            skipped_attachment_errors.append(
                {
                    "index": attachment_index,
                    "error_code": str(runtime_error),
                    "original_filename": attachment_input.get("original_filename"),
                    "provider_media_id": attachment_input.get("provider_media_id"),
                }
            )

    final_message_format = read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds(
        raw_text_content=normalized_raw_text,
        attachment_file_kinds=[row["file_kind"] for row in stored_attachment_rows],
        fallback_message_format=message_format,
    )
    if len(stored_attachment_rows) > 0 or len(skipped_attachment_errors) > 0:
        try:
            with connect(**DB_CONFIG) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_contact_messages
                        SET
                            message_format = %s,
                            message_metadata_json = message_metadata_json || %s::jsonb
                        WHERE id = %s
                        """,
                        (
                            final_message_format,
                            psycopg2.extras.Json(
                                {
                                    "attachment_count": len(stored_attachment_rows),
                                    "skipped_attachments": skipped_attachment_errors,
                                }
                            ),
                            stored_message_id,
                        ),
                    )
        except Exception as exc:
            raise RuntimeError("API_DCX_CONTACT_MESSAGE_INBOUND_ENVELOPE_INGEST_FAILED") from exc

    trade_thread_route_result = route_dcx_inbound_contact_message_to_trade_thread_if_applicable(
        contact_message_id=stored_message_id,
        connect_to_database=connect,
    )
    if trade_thread_route_result is not None:
        return {
            "message_id": stored_message_id,
            "job_id": None,
            "processing_status": trade_thread_route_result["processing_status"],
            "derivation_status": trade_thread_route_result["derivation_status"],
            "normalized_source_handle": normalized_source_handle,
            "normalized_target_handle": normalized_target_handle,
            "resolved_user_id": resolution["user_id"],
            "resolved_contact_method_id": resolution["contact_method_id"],
            "resolution_status": resolution["resolution_status"],
            "stored_attachment_count": len(stored_attachment_rows),
            "skipped_attachment_count": len(skipped_attachment_errors),
            "trade_thread_route": trade_thread_route_result,
        }

    derivation_result = process_stored_dcx_contact_message_analysis(
        message_id=stored_message_id,
        connect_to_database=connect,
        current_timestamp_ms_provider=current_timestamp_ms_provider,
        analyze_message_content=(
            _wrap_legacy_dcx_message_derivation_callable_for_analysis(derive_message_with_llm)
            if derive_message_with_llm is not None
            else None
        ),
    )

    return {
        "message_id": stored_message_id,
        "job_id": derivation_result["job_id"],
        "processing_status": derivation_result["processing_status"],
        "derivation_status": derivation_result["derivation_status"],
        "normalized_source_handle": normalized_source_handle,
        "normalized_target_handle": normalized_target_handle,
        "resolved_user_id": resolution["user_id"],
        "resolved_contact_method_id": resolution["contact_method_id"],
        "resolution_status": resolution["resolution_status"],
        "stored_attachment_count": len(stored_attachment_rows),
        "skipped_attachment_count": len(skipped_attachment_errors),
    }


def _resolve_dcx_user_contact_for_inbound_handle(
    channel_type: str,
    source_handle: str,
    connect_to_database: Callable[..., Any],
) -> dict:
    normalized_source_handle = _normalize_inbound_handle(channel_type=channel_type, raw_handle=source_handle)
    if normalized_source_handle is None:
        return {
            "normalized_source_handle": source_handle.strip(),
            "user_id": None,
            "contact_method_id": None,
            "source_contact_is_verified": False,
            "resolution_status": "unresolved_invalid_handle",
        }

    lookup_contact_type = "phone" if channel_type == "whatsapp" else "email"

    with connect_to_database(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    user_id,
                    id,
                    is_verified
                FROM stephen_dcx_users_contact_methods
                WHERE contact_type = %s
                  AND normalized_value = %s
                  AND is_active = TRUE
                ORDER BY
                    is_verified DESC,
                    is_primary DESC,
                    id ASC
                LIMIT 1
                """,
                (
                    lookup_contact_type,
                    normalized_source_handle,
                ),
            )
            matched_row = cursor.fetchone()

    if matched_row is None:
        return {
            "normalized_source_handle": normalized_source_handle,
            "user_id": None,
            "contact_method_id": None,
            "source_contact_is_verified": False,
            "resolution_status": "unresolved_no_contact_match",
        }

    return {
        "normalized_source_handle": normalized_source_handle,
        "user_id": matched_row[0],
        "contact_method_id": matched_row[1],
        "source_contact_is_verified": matched_row[2],
        "resolution_status": "matched_contact_method",
    }


def _normalize_inbound_handle(channel_type: str, raw_handle: str | None) -> str | None:
    if not isinstance(raw_handle, str) or raw_handle.strip() == "":
        return None

    if channel_type == "email":
        parsed_address = parseaddr(raw_handle)[1].strip().lower()
        return parsed_address or None

    if channel_type == "whatsapp":
        digits_only = "".join(character for character in raw_handle if character.isdigit())
        if digits_only == "":
            return None
        return f"+{digits_only}"

    return raw_handle.strip()


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)


def _wrap_legacy_dcx_message_derivation_callable_for_analysis(derive_message_with_llm: Callable[[str], dict]) -> Callable[[dict, list[dict]], dict]:
    def _wrapped_analyze_message_content(message_input: dict, _file_inputs: list[dict]) -> dict:
        derivation_result = derive_message_with_llm(message_input.get("raw_text_content", ""))
        return {
            "provider_name": "legacy_test_derivation",
            "model_name": derivation_result.get("model_name", ""),
            "prompt_version": "legacy_test_derivation",
            "analysis_mode": derivation_result.get("derivation_mode", "legacy_test_derivation"),
            "message_language_code": derivation_result.get("detected_language_code"),
            "message_summary": derivation_result.get("analysis_summary_text", ""),
            "message_text_synthesis": derivation_result.get("derived_text_content", ""),
            "message_analysis_status": "completed",
            "attachments": [],
            "raw_output_json": derivation_result,
        }

    return _wrapped_analyze_message_content
