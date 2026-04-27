"""
CONTEXT:
This file creates one authenticated app-originated DCX contact message and completes the first
derivation pass for that message.
It exists so the `/me/messages` app surface can become a real persisted inbox before WhatsApp and
email are wired into the same intake pipeline.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
import psycopg2.extras

from messages.process_stored_dcx_contact_message_analysis import (
    process_stored_dcx_contact_message_analysis,
)
from messages.read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds import (
    read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds,
)
from messages.store_dcx_contact_message_attachment_file_object import (
    delete_prepared_dcx_contact_message_attachment_file_object_from_r2,
    persist_prepared_dcx_contact_message_attachment_file_object_rows,
    prepare_dcx_contact_message_attachment_file_object_storage,
    store_dcx_contact_message_attachment_file_object,
)
from storage.db_config import DB_CONFIG


def create_authenticated_dcx_app_contact_message(
    authenticated_user_id: int,
    message_text: str,
    attachment_inputs: list[dict] | None = None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    derive_message_with_llm: Callable[[str], dict] | None = None,
    store_message_attachment: Callable[..., dict] | None = None,
    prepare_message_attachment: Callable[..., dict] | None = None,
    persist_prepared_message_attachment: Callable[..., dict] | None = None,
    delete_prepared_message_attachment: Callable[..., None] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one current DCX user.
        - message_text contains one app-authored body or attachment_inputs contains at least one file.
        - The configured database is reachable.
      postconditions:
        - Persists one inbound app-originated contact message row for the user.
        - For app uploads, validates and stores attachment bytes before creating the message row.
        - Persists attachment rows when files were uploaded.
        - Reuses the shared stored-message derivation lifecycle.
      side_effects:
        - writes to stephen_dcx_contact_messages
        - may write to stephen_dcx_file_objects
        - may write to stephen_dcx_contact_message_attachments
        - writes to stephen_dcx_contact_message_processing_jobs
        - writes to stephen_dcx_contact_message_analysis_runs
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: null
      locks:
        - row lock on the authenticated user record before attachment preparation and again during final message creation
      contention_strategy: each submit intentionally creates a new message row; failed attachment preparation creates no message row

    NARRATIVE:
      WHY this exists:
        - The first app-facing Messages page needs one concrete write path that does more than stage
          text locally in the browser.
      WHEN TO USE it:
        - Use it when an authenticated app user presses Send on the first app Messages composer,
          including mixed text-plus-file messages.
      WHEN NOT TO USE it:
        - Do not use it yet for WhatsApp or inbound email webhooks.
      WHAT CAN GO WRONG:
        - The user row may be missing.
        - The user can submit neither text nor files.
        - One uploaded file can be unsupported, too large, or fail R2 storage before the message exists.
        - The LLM derivation step can fail after the message is already persisted.
      WHAT COMES NEXT:
        - Later inbound channels and file uploads should create the same canonical message row and
          then reuse or extract this derivation/update behavior.

    TESTS:
      - creates_ready_message_job_and_analysis_run_when_derivation_succeeds
      - creates_mixed_message_after_preparing_attachment_when_file_is_present
      - does_not_create_message_when_attachment_preparation_fails
      - raises_when_message_text_is_blank

    ERRORS:
      - API_AUTHENTICATED_DCX_CONTACT_MESSAGE_USER_NOT_FOUND:
          suggested_action: Sign in again and retry after confirming the user still exists.
          common_causes:
            - stale session
            - deleted user row
          recovery_steps:
            - Sign in again.
            - Confirm the account still exists in admin.
          retry_safe: true
      - API_AUTHENTICATED_DCX_CONTACT_MESSAGE_TEXT_REQUIRED:
          suggested_action: Enter some text or attach at least one file before sending the message.
          common_causes:
            - empty textarea
            - whitespace-only input
            - no files attached
          recovery_steps:
            - Type the message content or add one file.
            - Retry the send.
          retry_safe: true
      - API_AUTHENTICATED_DCX_CONTACT_MESSAGE_ATTACHMENT_TOO_LARGE:
          suggested_action: Retry with a file under 10 MB.
          common_causes:
            - selected file exceeds the current DCX upload limit
          recovery_steps:
            - Choose a smaller file.
            - Retry the send.
          retry_safe: true
      - API_AUTHENTICATED_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED:
          suggested_action: Retry with one supported image, audio, PDF, DOCX, or PPTX file.
          common_causes:
            - unsupported extension
            - unsupported MIME type
          recovery_steps:
            - Choose a supported file type.
            - Retry the send.
          retry_safe: true
      - API_AUTHENTICATED_DCX_CONTACT_MESSAGE_CREATE_FAILED:
          suggested_action: Retry after the backend and database are healthy.
          common_causes:
            - database unavailable
            - insert failure
          recovery_steps:
            - Confirm database connectivity.
            - Retry once the backend is stable.
          retry_safe: true

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_USER_NOT_FOUND")

    normalized_message_text = message_text.strip()
    normalized_attachment_inputs = [
        attachment_input
        for attachment_input in (attachment_inputs or [])
        if isinstance(attachment_input, dict)
    ]
    if normalized_message_text == "" and len(normalized_attachment_inputs) == 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_TEXT_REQUIRED")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()

    if len(normalized_attachment_inputs) > 0 and store_message_attachment is None:
        try:
            with connect(**DB_CONFIG) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM stephen_dcx_users
                        WHERE id = %s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        (authenticated_user_id,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_USER_NOT_FOUND")
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_CREATE_FAILED") from exc

        prepared_attachment_rows: list[dict] = []
        try:
            for attachment_index, attachment_input in enumerate(normalized_attachment_inputs, start=1):
                prepared_attachment_rows.append(
                    (prepare_message_attachment or prepare_dcx_contact_message_attachment_file_object_storage)(
                        owner_user_id=authenticated_user_id,
                        source_channel_type="app",
                        source_provider_type="dcx_app",
                        original_filename=attachment_input.get("original_filename"),
                        file_bytes=attachment_input.get("file_bytes"),
                        content_type=attachment_input.get("content_type"),
                        sort_order=attachment_index,
                        current_timestamp_ms_provider=current_timestamp_ms_provider,
                    )
                )
        except RuntimeError:
            for prepared_attachment in prepared_attachment_rows:
                (delete_prepared_message_attachment or delete_prepared_dcx_contact_message_attachment_file_object_from_r2)(
                    prepared_attachment=prepared_attachment,
                )
            raise

        try:
            with connect(**DB_CONFIG) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM stephen_dcx_users
                        WHERE id = %s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        (authenticated_user_id,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_USER_NOT_FOUND")

                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_contact_messages (
                            user_id,
                            channel_type,
                            provider_type,
                            message_direction,
                            message_format,
                            raw_text_content,
                            processing_status,
                            derivation_status,
                            visible_to_user,
                            received_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            authenticated_user_id,
                            "app",
                            "dcx_app",
                            "inbound",
                            "text",
                            normalized_message_text,
                            "queued",
                            "pending",
                            True,
                            now_ts_ms,
                        ),
                    )
                    created_message_id = cursor.fetchone()[0]

                    stored_attachment_rows = [
                        (persist_prepared_message_attachment or persist_prepared_dcx_contact_message_attachment_file_object_rows)(
                            cursor=cursor,
                            message_id=created_message_id,
                            attachment_role="primary_media",
                            prepared_attachment=prepared_attachment,
                        )
                        for prepared_attachment in prepared_attachment_rows
                    ]

                    final_message_format = read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds(
                        raw_text_content=normalized_message_text,
                        attachment_file_kinds=[row["file_kind"] for row in stored_attachment_rows],
                        fallback_message_format="text",
                    )
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_contact_messages
                        SET
                            message_format = %s,
                            message_metadata_json = %s::jsonb
                        WHERE id = %s
                        """,
                        (
                            final_message_format,
                            psycopg2.extras.Json(
                                {
                                    "attachment_count": len(stored_attachment_rows),
                                }
                            ),
                            created_message_id,
                        ),
                    )
        except RuntimeError:
            for prepared_attachment in prepared_attachment_rows:
                (delete_prepared_message_attachment or delete_prepared_dcx_contact_message_attachment_file_object_from_r2)(
                    prepared_attachment=prepared_attachment,
                )
            raise
        except Exception as exc:
            for prepared_attachment in prepared_attachment_rows:
                (delete_prepared_message_attachment or delete_prepared_dcx_contact_message_attachment_file_object_from_r2)(
                    prepared_attachment=prepared_attachment,
                )
            raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_CREATE_FAILED") from exc
    else:
        try:
            with connect(**DB_CONFIG) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM stephen_dcx_users
                        WHERE id = %s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        (authenticated_user_id,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_USER_NOT_FOUND")

                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_contact_messages (
                            user_id,
                            channel_type,
                            provider_type,
                            message_direction,
                            message_format,
                            raw_text_content,
                            processing_status,
                            derivation_status,
                            visible_to_user,
                            received_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            authenticated_user_id,
                            "app",
                            "dcx_app",
                            "inbound",
                            "text",
                            normalized_message_text,
                            "queued",
                            "pending",
                            True,
                            now_ts_ms,
                        ),
                    )
                    created_message_id = cursor.fetchone()[0]
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_CREATE_FAILED") from exc

        try:
            stored_attachment_rows: list[dict] = []
            for attachment_index, attachment_input in enumerate(normalized_attachment_inputs, start=1):
                stored_attachment_rows.append(
                    (store_message_attachment or store_dcx_contact_message_attachment_file_object)(
                        message_id=created_message_id,
                        owner_user_id=authenticated_user_id,
                        source_channel_type="app",
                        source_provider_type="dcx_app",
                        original_filename=attachment_input.get("original_filename"),
                        file_bytes=attachment_input.get("file_bytes"),
                        content_type=attachment_input.get("content_type"),
                        sort_order=attachment_index,
                        connect_to_database=connect,
                        current_timestamp_ms_provider=current_timestamp_ms_provider,
                    )
                )

            final_message_format = read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds(
                raw_text_content=normalized_message_text,
                attachment_file_kinds=[row["file_kind"] for row in stored_attachment_rows],
                fallback_message_format="text",
            )
            with connect(**DB_CONFIG) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_contact_messages
                        SET
                            message_format = %s,
                            message_metadata_json = %s::jsonb
                        WHERE id = %s
                        """,
                        (
                            final_message_format,
                            psycopg2.extras.Json(
                                {
                                    "attachment_count": len(stored_attachment_rows),
                                }
                            ),
                            created_message_id,
                        ),
                    )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_CREATE_FAILED") from exc

    try:
        derivation_result = process_stored_dcx_contact_message_analysis(
            message_id=created_message_id,
            connect_to_database=connect,
            current_timestamp_ms_provider=current_timestamp_ms_provider,
            analyze_message_content=(
                _wrap_legacy_dcx_message_derivation_callable_for_analysis(derive_message_with_llm)
                if derive_message_with_llm is not None
                else None
            ),
        )
        created_job_id = derivation_result["job_id"]
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_CONTACT_MESSAGE_CREATE_FAILED") from exc

    return {
        "message_id": created_message_id,
        "job_id": created_job_id,
        "processing_status": derivation_result["processing_status"],
        "derivation_status": derivation_result["derivation_status"],
    }


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
            "moderation_status": "allowed",
            "moderation_reason_summary": "",
            "matched_prohibited_categories": [],
            "attachments": [],
            "raw_output_json": derivation_result,
        }

    return _wrapped_analyze_message_content
