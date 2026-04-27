"""
CONTEXT:
This file reads one authenticated DCX user message detail payload.
It exists so the app create route and future detail surfaces can render one canonical message row
without duplicating SQL in route boundaries.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_user_contact_message_detail(
    authenticated_user_id: int,
    message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one current DCX user.
        - message_id identifies one message row owned by that user.
      postconditions:
        - Returns one detailed message payload when the row belongs to the user.
        - Returns null when no such visible message exists.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Message creation should return a stable detail payload, not just an id.
      WHEN TO USE it:
        - Use it after creating one message or when opening one future detail panel.
      WHEN NOT TO USE it:
        - Do not use it for cross-user admin inspection.
      WHAT CAN GO WRONG:
        - The message may not belong to the current user.
      WHAT COMES NEXT:
        - Attachments and richer provider metadata can be layered onto this contract later.

    TESTS:
      - returns_message_detail_when_visible_message_belongs_to_user
      - returns_none_when_message_is_missing

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_MESSAGE_DETAIL_READ_FAILED:
          suggested_action: Retry after confirming database health.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true

    CODE:
    """
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        message.id,
                        message.channel_type,
                        message.provider_type,
                        message.message_direction,
                        message.message_format,
                        message.message_subject,
                        message.raw_text_content,
                        message.derived_text_content,
                        message.analysis_summary_text,
                        message.processing_status,
                        message.derivation_status,
                        message.analysis_status,
                        message.analysis_model_name,
                        message.analysis_metadata_json,
                        message.analysis_completed_at_ts_ms,
                        language.language_code,
                        message.received_at_ts_ms,
                        message.created_at_ts_ms,
                        message.updated_at_ts_ms
                    FROM stephen_dcx_contact_messages message
                    LEFT JOIN stephen_dcx_languages language
                      ON language.id = message.detected_language_id
                    WHERE message.user_id = %s
                      AND message.id = %s
                      AND message.visible_to_user = TRUE
                    LIMIT 1
                    """,
                    (
                        authenticated_user_id,
                        message_id,
                    ),
                )
                message_row = cursor.fetchone()
                attachment_rows = []
                if message_row is not None:
                    cursor.execute(
                        """
                        SELECT
                            attachment.id,
                            attachment.file_object_id,
                            attachment.attachment_role,
                            attachment.provider_media_id,
                            attachment.sort_order,
                            file_object.file_uuid,
                            file_object.file_kind,
                            file_object.content_type,
                            file_object.file_size_bytes,
                            file_object.original_filename,
                            file_object.analysis_status,
                            file_object.analysis_summary_text,
                            file_object.analysis_description_text,
                            file_object.analysis_transcription_text,
                            file_object.analysis_synthesis_text,
                            file_object.context_within_message,
                            file_object.analysis_model_name,
                            file_object.analysis_metadata_json,
                            file_object.analysis_completed_at_ts_ms,
                            file_language.language_code
                        FROM stephen_dcx_contact_message_attachments attachment
                        INNER JOIN stephen_dcx_file_objects file_object
                          ON file_object.id = attachment.file_object_id
                        LEFT JOIN stephen_dcx_languages file_language
                          ON file_language.id = file_object.detected_language_id
                        WHERE attachment.message_id = %s
                        ORDER BY attachment.sort_order ASC, attachment.id ASC
                        """,
                        (message_id,),
                    )
                    attachment_rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGE_DETAIL_READ_FAILED") from exc

    if message_row is None:
        return None

    return {
        "message_id": message_row[0],
        "channel_type": message_row[1],
        "provider_type": message_row[2],
        "message_direction": message_row[3],
        "message_format": message_row[4],
        "message_subject": message_row[5],
        "raw_text_content": message_row[6],
        "derived_text_content": message_row[7],
        "analysis_summary_text": message_row[8],
        "processing_status": message_row[9],
        "derivation_status": message_row[10],
        "analysis_status": message_row[11],
        "analysis_model_name": message_row[12],
        "analysis_metadata_json": message_row[13],
        "analysis_completed_at_ts_ms": message_row[14],
        "detected_language_code": message_row[15],
        "received_at_ts_ms": message_row[16],
        "created_at_ts_ms": message_row[17],
        "updated_at_ts_ms": message_row[18],
        "attachments": [
            {
                "attachment_id": attachment_row[0],
                "file_object_id": attachment_row[1],
                "attachment_role": attachment_row[2],
                "provider_media_id": attachment_row[3],
                "sort_order": attachment_row[4],
                "file_uuid": str(attachment_row[5]) if attachment_row[5] is not None else None,
                "file_kind": attachment_row[6],
                "content_type": attachment_row[7],
                "file_size_bytes": attachment_row[8],
                "original_filename": attachment_row[9],
                "analysis_status": attachment_row[10],
                "analysis_summary_text": attachment_row[11],
                "analysis_description_text": attachment_row[12],
                "analysis_transcription_text": attachment_row[13],
                "analysis_synthesis_text": attachment_row[14],
                "context_within_message": attachment_row[15],
                "analysis_model_name": attachment_row[16],
                "analysis_metadata_json": attachment_row[17],
                "analysis_completed_at_ts_ms": attachment_row[18],
                "detected_language_code": attachment_row[19],
                "attachment_url_path": f"/users/me/messages/{message_id}/attachments/{attachment_row[0]}/file",
            }
            for attachment_row in attachment_rows
        ],
    }
