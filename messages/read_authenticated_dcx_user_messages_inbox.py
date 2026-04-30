"""
CONTEXT:
This file reads the first authenticated Messages inbox payload for one DCX app user.
It exists so the user app can show real persisted message rows instead of a placeholder shell.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_user_messages_inbox(
    authenticated_user_id: int,
    message_format_filter: str | None = None,
    workflow_kind_filter: str | None = None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one current DCX user.
        - message_format_filter is null or one of the supported message format filters.
        - workflow_kind_filter is null or one supported workflow-kind filter.
        - The configured database is reachable.
      postconditions:
        - Returns one stable inbox payload of user-visible messages for the authenticated user.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The new Messages app surface needs one dedicated backend read contract.
      WHEN TO USE it:
        - Use it for the primary inbox list and its simple format/workflow filters.
      WHEN NOT TO USE it:
        - Do not use it for admin operations or provider-event debugging.
      WHAT CAN GO WRONG:
        - The user may not exist.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - Later inbox reads can add pagination and richer filters on top of the new workflow-aware
          message filtering.

    TESTS:
      - returns_filtered_visible_messages_for_authenticated_user
      - raises_when_message_format_filter_is_invalid
      - raises_when_workflow_kind_filter_is_invalid

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_MESSAGES_USER_NOT_FOUND:
          suggested_action: Sign in again and retry after confirming the account still exists.
          common_causes:
            - stale session
            - deleted user row
          recovery_steps:
            - Sign in again.
            - Confirm the account still exists.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_MESSAGES_FILTER_INVALID:
          suggested_action: Retry with one supported message format filter.
          common_causes:
            - unsupported query parameter value
          recovery_steps:
            - Use all, text, image, audio, or document.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_MESSAGES_WORKFLOW_FILTER_INVALID:
          suggested_action: Retry with all, trade, market_topic, or other.
          common_causes:
            - unsupported workflow filter query parameter value
          recovery_steps:
            - Use all, trade, market_topic, or other.
          retry_safe: true

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGES_USER_NOT_FOUND")

    normalized_filter = (message_format_filter or "all").strip().lower()
    if normalized_filter not in {"all", "text", "image", "audio", "document"}:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGES_FILTER_INVALID")

    normalized_workflow_kind_filter = (workflow_kind_filter or "all").strip().lower()
    if normalized_workflow_kind_filter not in {"all", "trade", "market_topic", "other"}:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGES_WORKFLOW_FILTER_INVALID")

    workflow_where_clause = ""
    if normalized_workflow_kind_filter == "trade":
        workflow_where_clause = "AND message.contains_trade_items = TRUE"
    elif normalized_workflow_kind_filter == "market_topic":
        workflow_where_clause = "AND message.contains_market_topic_items = TRUE"
    elif normalized_workflow_kind_filter == "other":
        workflow_where_clause = "AND message.contains_other_items = TRUE"

    format_where_clause = ""
    format_params: tuple[Any, ...] = ()
    if normalized_filter != "all":
        format_where_clause = """
          AND (
            message.message_format = %s
            OR EXISTS (
                SELECT 1
                FROM stephen_dcx_contact_message_attachments attachment
                INNER JOIN stephen_dcx_file_objects file_object
                  ON file_object.id = attachment.file_object_id
                WHERE attachment.message_id = message.id
                  AND file_object.file_kind = %s
            )
          )
        """
        format_params = (normalized_filter, normalized_filter)

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (authenticated_user_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGES_USER_NOT_FOUND")

                cursor.execute(
                    f"""
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
                        message.analysis_metadata_json,
                        message.workflow_classification_status,
                        message.primary_workflow_kind,
                        message.contains_trade_items,
                        message.contains_market_topic_items,
                        message.contains_other_items,
                        message.workflow_reason_summary,
                        message.workflow_metadata_json,
                        (
                            SELECT COUNT(*)
                            FROM stephen_dcx_message_workflow_items workflow_item
                            WHERE workflow_item.message_id = message.id
                        ) AS workflow_item_count,
                        (
                            SELECT COUNT(*)
                            FROM stephen_dcx_message_workflow_items workflow_item
                            WHERE workflow_item.message_id = message.id
                              AND workflow_item.item_kind = 'trade'
                        ) AS trade_item_count,
                        (
                            SELECT COUNT(*)
                            FROM stephen_dcx_message_workflow_items workflow_item
                            WHERE workflow_item.message_id = message.id
                              AND workflow_item.item_kind = 'market_topic'
                        ) AS market_topic_item_count,
                        (
                            SELECT COUNT(*)
                            FROM stephen_dcx_message_workflow_items workflow_item
                            WHERE workflow_item.message_id = message.id
                              AND workflow_item.item_kind = 'other'
                        ) AS other_item_count,
                        EXISTS (
                            SELECT 1
                            FROM stephen_dcx_trades trade
                            INNER JOIN stephen_dcx_trade_versions trade_version
                              ON trade_version.id = trade.current_version_id
                            WHERE trade.source_message_id_initial = message.id
                              AND trade_version.trade_confirmation_status IN ('draft', 'pending_confirmation', 'needs_more_detail', 'under_revision')
                        ) AS requires_user_attention,
                        language.language_code,
                        message.received_at_ts_ms,
                        message.created_at_ts_ms,
                        message.contact_method_id,
                        contact_method.contact_type,
                        contact_method.contact_value,
                        contact_method.normalized_value,
                        contact_method.display_label,
                        message.source_handle_normalized,
                        message.target_handle_normalized,
                        COALESCE(
                            jsonb_agg(
                                jsonb_build_object(
                                    'attachment_id', attachment.id,
                                    'file_kind', file_object.file_kind,
                                    'original_filename', file_object.original_filename,
                                    'analysis_summary_text', file_object.analysis_summary_text
                                )
                                ORDER BY attachment.sort_order ASC, attachment.id ASC
                            ) FILTER (WHERE attachment.id IS NOT NULL),
                            '[]'::jsonb
                        ) AS attachment_summaries
                    FROM stephen_dcx_contact_messages message
                    LEFT JOIN stephen_dcx_languages language
                      ON language.id = message.detected_language_id
                    LEFT JOIN stephen_dcx_users_contact_methods contact_method
                      ON contact_method.id = message.contact_method_id
                    LEFT JOIN stephen_dcx_contact_message_attachments attachment
                      ON attachment.message_id = message.id
                    LEFT JOIN stephen_dcx_file_objects file_object
                      ON file_object.id = attachment.file_object_id
                    WHERE message.user_id = %s
                      AND message.visible_to_user = TRUE
                      {workflow_where_clause}
                      {format_where_clause}
                    GROUP BY
                        message.id,
                        language.language_code,
                        contact_method.id
                    ORDER BY message.created_at_ts_ms DESC, message.id DESC
                    """,
                    (authenticated_user_id, *format_params),
                )
                message_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGES_INBOX_READ_FAILED") from exc

    messages = [
        {
            "message_id": row[0],
            "channel_type": row[1],
            "provider_type": row[2],
            "message_direction": row[3],
            "message_format": row[4],
            "message_subject": "" if _read_dcx_message_is_prohibited_from_analysis_metadata_json(row[12]) else row[5],
            "raw_text_content": "" if _read_dcx_message_is_prohibited_from_analysis_metadata_json(row[12]) else row[6],
            "derived_text_content": "" if _read_dcx_message_is_prohibited_from_analysis_metadata_json(row[12]) else row[7],
            "analysis_summary_text": row[8],
            "processing_status": row[9],
            "derivation_status": row[10],
            "analysis_status": row[11],
            "analysis_metadata_json": row[12] if isinstance(row[12], dict) else {},
            "workflow_classification_status": row[13],
            "primary_workflow_kind": row[14],
            "contains_trade_items": row[15],
            "contains_market_topic_items": row[16],
            "contains_other_items": row[17],
            "workflow_reason_summary": row[18],
            "workflow_metadata_json": row[19] if isinstance(row[19], dict) else {},
            "workflow_item_count": row[20],
            "trade_item_count": row[21],
            "market_topic_item_count": row[22],
            "other_item_count": row[23],
            "requires_user_attention": row[24],
            "detected_language_code": row[25],
            "received_at_ts_ms": row[26],
            "created_at_ts_ms": row[27],
            "contact_method": (
                {
                    "id": row[28],
                    "contact_type": row[29],
                    "contact_value": row[30],
                    "normalized_value": row[31],
                    "display_label": row[32],
                }
                if row[28] is not None
                else None
            ),
            "source_handle_normalized": row[33],
            "target_handle_normalized": row[34],
            "attachment_summaries": row[35] if isinstance(row[35], list) else [],
        }
        for row in message_rows
    ]

    return {
        "messages": messages,
        "selected_filter": normalized_filter,
        "selected_workflow_kind_filter": normalized_workflow_kind_filter,
        "total_message_count": len(messages),
    }


def _read_dcx_message_is_prohibited_from_analysis_metadata_json(analysis_metadata_json: Any) -> bool:
    if not isinstance(analysis_metadata_json, dict):
        return False
    return str(analysis_metadata_json.get("moderation_status") or "").strip().lower() == "prohibited"
