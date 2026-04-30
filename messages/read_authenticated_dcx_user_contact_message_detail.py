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
        - Trades, topics, and later interaction-thread context can be layered onto this contract.

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
                        message.workflow_classification_status,
                        message.primary_workflow_kind,
                        message.contains_trade_items,
                        message.contains_market_topic_items,
                        message.contains_other_items,
                        message.workflow_reason_summary,
                        message.workflow_metadata_json,
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
                workflow_item_rows = []
                trade_rows = []
                topic_rows = []
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

                    cursor.execute(
                        """
                        SELECT
                            workflow_item.id,
                            workflow_item.item_index,
                            workflow_item.item_kind,
                            workflow_item.item_status,
                            workflow_item.item_title,
                            workflow_item.item_summary_text,
                            workflow_item.source_excerpt_text,
                            workflow_item.referenced_attachment_ids_json,
                            workflow_item.confidence_label,
                            workflow_item.workflow_item_metadata_json
                        FROM stephen_dcx_message_workflow_items workflow_item
                        WHERE workflow_item.message_id = %s
                        ORDER BY workflow_item.item_index ASC, workflow_item.id ASC
                        """,
                        (message_id,),
                    )
                    workflow_item_rows = cursor.fetchall()

                    cursor.execute(
                        """
                        SELECT
                            trade.id,
                            trade.source_workflow_item_id_initial,
                            trade_version.trade_confirmation_status,
                            trade_version.trade_status,
                            trade_version.trade_summary_text,
                            trade_version.normalized_trade_side,
                            trade_version.normalized_material_name
                        FROM stephen_dcx_trades trade
                        INNER JOIN stephen_dcx_trade_versions trade_version
                          ON trade_version.id = trade.current_version_id
                        WHERE trade.source_message_id_initial = %s
                        ORDER BY trade.id ASC
                        """,
                        (message_id,),
                    )
                    trade_rows = cursor.fetchall()

                    cursor.execute(
                        """
                        SELECT
                            topic.id,
                            topic.source_workflow_item_id,
                            topic.topic_status,
                            topic.topic_title,
                            topic.topic_summary_text
                        FROM stephen_dcx_market_topics topic
                        WHERE topic.source_message_id = %s
                        ORDER BY topic.id ASC
                        """,
                        (message_id,),
                    )
                    topic_rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGE_DETAIL_READ_FAILED") from exc

    if message_row is None:
        return None

    moderation_status = _read_dcx_message_moderation_status_from_analysis_metadata_json(message_row[13])
    message_is_prohibited = moderation_status == "prohibited"

    return {
        "requires_user_attention": any(
            trade_row[2] in {"pending_confirmation", "needs_more_detail"}
            for trade_row in trade_rows
        ),
        "message_id": message_row[0],
        "channel_type": message_row[1],
        "provider_type": message_row[2],
        "message_direction": message_row[3],
        "message_format": message_row[4],
        "message_subject": "" if message_is_prohibited else message_row[5],
        "raw_text_content": "" if message_is_prohibited else message_row[6],
        "derived_text_content": "" if message_is_prohibited else message_row[7],
        "analysis_summary_text": message_row[8],
        "processing_status": message_row[9],
        "derivation_status": message_row[10],
        "analysis_status": message_row[11],
        "analysis_model_name": message_row[12],
        "analysis_metadata_json": message_row[13],
        "analysis_completed_at_ts_ms": message_row[14],
        "workflow_classification_status": message_row[15],
        "primary_workflow_kind": message_row[16],
        "contains_trade_items": message_row[17],
        "contains_market_topic_items": message_row[18],
        "contains_other_items": message_row[19],
        "workflow_reason_summary": message_row[20],
        "workflow_metadata_json": message_row[21] if isinstance(message_row[21], dict) else {},
        "detected_language_code": message_row[22],
        "received_at_ts_ms": message_row[23],
        "created_at_ts_ms": message_row[24],
        "updated_at_ts_ms": message_row[25],
        "workflow_items": [] if message_is_prohibited else [
            {
                "workflow_item_id": workflow_item_row[0],
                "item_index": workflow_item_row[1],
                "item_kind": workflow_item_row[2],
                "item_status": workflow_item_row[3],
                "item_title": workflow_item_row[4],
                "item_summary_text": workflow_item_row[5],
                "source_excerpt_text": workflow_item_row[6],
                "referenced_attachment_ids_json": workflow_item_row[7] if isinstance(workflow_item_row[7], list) else [],
                "confidence_label": workflow_item_row[8],
                "workflow_item_metadata_json": workflow_item_row[9] if isinstance(workflow_item_row[9], dict) else {},
                "requires_user_attention": any(
                    trade_row[1] == workflow_item_row[0]
                    and trade_row[2] in {"pending_confirmation", "needs_more_detail"}
                    for trade_row in trade_rows
                ),
            }
            for workflow_item_row in workflow_item_rows
        ],
        "linked_trades": [
            {
                "trade_id": trade_row[0],
                "source_workflow_item_id": trade_row[1],
                "trade_confirmation_status": trade_row[2],
                "trade_status": trade_row[3],
                "trade_summary_text": trade_row[4],
                "normalized_trade_side": trade_row[5],
                "normalized_material_name": trade_row[6],
            }
            for trade_row in trade_rows
        ],
        "linked_market_topics": [
            {
                "market_topic_id": topic_row[0],
                "source_workflow_item_id": topic_row[1],
                "topic_status": topic_row[2],
                "topic_title": topic_row[3],
                "topic_summary_text": topic_row[4],
            }
            for topic_row in topic_rows
        ],
        "attachments": ([] if message_is_prohibited else [
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
        ]),
    }


def _read_dcx_message_moderation_status_from_analysis_metadata_json(analysis_metadata_json: Any) -> str:
    if not isinstance(analysis_metadata_json, dict):
        return "not_reviewed"

    normalized_status = str(analysis_metadata_json.get("moderation_status") or "").strip().lower()
    if normalized_status in {"allowed", "prohibited"}:
        return normalized_status
    return "not_reviewed"
