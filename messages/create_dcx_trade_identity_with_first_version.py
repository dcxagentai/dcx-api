"""
CONTEXT:
This file creates one stable DCX trade identity row together with its first immutable version row.
It exists so workflow-routed trade extraction can create a durable trade anchor without mutating
the initial structured terms in place.
"""

from __future__ import annotations

from typing import Any

import psycopg2.extras


def create_dcx_trade_identity_with_first_version(
    cursor: Any,
    initiating_user_id: int | None,
    initiating_contact_method_id: int | None,
    source_message_id: int,
    source_workflow_item_id: int,
    source_channel_type: str,
    source_language_id: int | None,
    trade_projection_status: str,
    trade_confirmation_status: str,
    trade_status: str,
    trade_projection: dict,
    version_source_type: str,
    now_ts_ms: int,
) -> int:
    """
    CONTRACT:
      preconditions:
        - cursor is one open psycopg cursor inside the caller transaction.
        - source_message_id and source_workflow_item_id identify the originating workflow extraction.
        - trade_projection contains the normalized/raw trade fields to persist as the first version.
      postconditions:
        - Creates one stephen_dcx_trades anchor row.
        - Creates one stephen_dcx_trade_versions live row linked to that trade.
        - Points the trade current_version_id at the inserted version.
      side_effects:
        - inserts one stephen_dcx_trades row
        - inserts one stephen_dcx_trade_versions row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The trade id should stay stable even as trade terms evolve through later user edits and confirmations.
      WHEN TO USE it:
        - Use it once, when the workflow projection first creates a trade from one routed message item.
      WHEN NOT TO USE it:
        - Do not use it to append later edits or confirmations to an existing trade.
      WHAT CAN GO WRONG:
        - The caller can pass an invalid source message or workflow item id.
        - The caller can pass incomplete structured projection data.
      WHAT COMES NEXT:
        - Later edits should append immutable versions and move the parent head pointer instead of
          mutating this first version.

    TESTS:
      - none yet

    ERRORS: []

    CODE:
    """
    cursor.execute(
        """
        INSERT INTO stephen_dcx_trades (
            trade_key,
            initiating_user_id,
            initiating_contact_method_id,
            source_message_id,
            source_workflow_item_id,
            source_message_id_initial,
            source_workflow_item_id_initial,
            current_trade_projection_status,
            current_trade_confirmation_status,
            current_trade_status,
            created_at_ts_ms,
            updated_at_ts_ms
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        RETURNING id AS trade_id
        """,
        (
            f"trade_pending_{source_message_id}_{source_workflow_item_id}_{now_ts_ms}",
            initiating_user_id,
            initiating_contact_method_id,
            source_message_id,
            source_workflow_item_id,
            source_message_id,
            source_workflow_item_id,
            trade_projection_status,
            trade_confirmation_status,
            trade_status,
            now_ts_ms,
            now_ts_ms,
        ),
    )
    trade_row = cursor.fetchone()
    trade_id = _read_returned_id(trade_row, "trade_id")
    trade_key = f"trade_{trade_id}"
    cursor.execute(
        """
        UPDATE stephen_dcx_trades
        SET trade_key = %s
        WHERE id = %s
        """,
        (trade_key, trade_id),
    )

    cursor.execute(
        """
        INSERT INTO stephen_dcx_trade_versions (
            trade_id,
            source_message_id,
            source_workflow_item_id,
            source_channel_type,
            source_language_id,
            version_number,
            is_live,
            version_of_id,
            version_source_type,
            trade_projection_status,
            trade_confirmation_status,
            trade_status,
            raw_trade_side_text,
            raw_material_text,
            raw_quantity_text,
            raw_price_text,
            raw_origin_text,
            raw_destination_text,
            raw_shipping_method_text,
            raw_incoterm_text,
            raw_delivery_window_text,
            raw_quality_text,
            raw_payment_terms_text,
            raw_counterparty_scope_text,
            normalized_trade_side,
            normalized_material_name,
            normalized_quantity_value,
            normalized_quantity_unit,
            normalized_price_mode,
            normalized_price_value,
            normalized_price_unit_basis,
            normalized_currency_code,
            normalized_total_price_value,
            normalized_origin_location,
            normalized_destination_location,
            normalized_shipping_method,
            normalized_incoterm_code,
            normalized_delivery_window_start_text,
            normalized_delivery_window_end_text,
            normalized_quality_summary_text,
            normalized_payment_terms_summary_text,
            trade_summary_text,
            trade_extraction_notes_text,
            missing_required_fields_json,
            trade_metadata_json,
            created_at_ts_ms,
            updated_at_ts_ms
        )
        VALUES (
            %s, %s, %s, %s, %s,
            1,
            TRUE,
            NULL,
            %s,
            %s,
            %s,
            %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s::jsonb,
            %s::jsonb,
            %s,
            %s
        )
        RETURNING id AS version_id
        """,
        (
            trade_id,
            source_message_id,
            source_workflow_item_id,
            source_channel_type,
            source_language_id,
            version_source_type,
            trade_projection_status,
            trade_confirmation_status,
            trade_status,
            trade_projection.get("raw_trade_side_text", ""),
            trade_projection.get("raw_material_text", ""),
            trade_projection.get("raw_quantity_text", ""),
            trade_projection.get("raw_price_text", ""),
            trade_projection.get("raw_origin_text", ""),
            trade_projection.get("raw_destination_text", ""),
            trade_projection.get("raw_shipping_method_text", ""),
            trade_projection.get("raw_incoterm_text", ""),
            trade_projection.get("raw_delivery_window_text", ""),
            trade_projection.get("raw_quality_text", ""),
            trade_projection.get("raw_payment_terms_text", ""),
            trade_projection.get("raw_counterparty_scope_text", ""),
            trade_projection.get("normalized_trade_side", ""),
            trade_projection.get("normalized_material_name", ""),
            trade_projection.get("normalized_quantity_value"),
            trade_projection.get("normalized_quantity_unit", ""),
            trade_projection.get("normalized_price_mode", ""),
            trade_projection.get("normalized_price_value"),
            trade_projection.get("normalized_price_unit_basis", ""),
            trade_projection.get("normalized_currency_code", ""),
            trade_projection.get("normalized_total_price_value"),
            trade_projection.get("normalized_origin_location", ""),
            trade_projection.get("normalized_destination_location", ""),
            trade_projection.get("normalized_shipping_method", ""),
            trade_projection.get("normalized_incoterm_code", ""),
            trade_projection.get("normalized_delivery_window_start_text", ""),
            trade_projection.get("normalized_delivery_window_end_text", ""),
            trade_projection.get("normalized_quality_summary_text", ""),
            trade_projection.get("normalized_payment_terms_summary_text", ""),
            trade_projection.get("trade_summary_text", ""),
            trade_projection.get("trade_extraction_notes_text", ""),
            psycopg2.extras.Json(trade_projection.get("missing_required_fields", [])),
            psycopg2.extras.Json(
                {
                    "provider_name": trade_projection.get("provider_name", ""),
                    "model_name": trade_projection.get("model_name", ""),
                    "prompt_version": trade_projection.get("prompt_version", ""),
                    "raw_output_json": trade_projection.get("raw_output_json", {}),
                }
            ),
            now_ts_ms,
            now_ts_ms,
        ),
    )
    current_version_row = cursor.fetchone()
    current_version_id = _read_returned_id(current_version_row, "version_id")

    cursor.execute(
        """
        UPDATE stephen_dcx_trades
        SET
            current_version_id = %s,
            current_trade_projection_status = %s,
            current_trade_confirmation_status = %s,
            current_trade_status = %s,
            updated_at_ts_ms = %s
        WHERE id = %s
        """,
        (
            current_version_id,
            trade_projection_status,
            trade_confirmation_status,
            trade_status,
            now_ts_ms,
            trade_id,
        ),
    )
    return trade_id


def _read_returned_id(row: Any, column_name: str) -> int:
    if isinstance(row, dict):
        return int(row[column_name])
    return int(row[0])
