"""
CONTEXT:
This file appends one immutable DCX trade version and promotes it to the current live head.
It exists so trade edits, confirmations, and rejections can preserve exact version history while
keeping one stable trade id for routes and future attached objects.
"""

from __future__ import annotations

from typing import Any

import psycopg2.extras


DCX_TRADE_VERSION_FIELDS = [
    "source_message_id",
    "source_workflow_item_id",
    "source_channel_type",
    "source_language_id",
    "trade_projection_status",
    "trade_confirmation_status",
    "trade_status",
    "raw_trade_side_text",
    "raw_material_text",
    "raw_quantity_text",
    "raw_price_text",
    "raw_origin_text",
    "raw_destination_text",
    "raw_shipping_method_text",
    "raw_incoterm_text",
    "raw_delivery_window_text",
    "raw_quality_text",
    "raw_payment_terms_text",
    "raw_counterparty_scope_text",
    "normalized_trade_side",
    "normalized_material_name",
    "normalized_material_key",
    "normalized_quantity_value",
    "normalized_quantity_unit",
    "normalized_price_mode",
    "normalized_price_value",
    "normalized_price_unit_basis",
    "normalized_currency_code",
    "normalized_total_price_value",
    "normalized_origin_location",
    "normalized_destination_location",
    "normalized_shipping_method",
    "normalized_incoterm_code",
    "normalized_delivery_window_start_text",
    "normalized_delivery_window_end_text",
    "normalized_quality_summary_text",
    "normalized_payment_terms_summary_text",
    "trade_summary_text",
    "trade_extraction_notes_text",
    "missing_required_fields_json",
    "trade_metadata_json",
]


def create_new_dcx_trade_version_and_promote_current_trade(
    cursor: Any,
    trade_identity_row: dict,
    current_trade_version_row: dict,
    next_trade_version_values: dict,
    version_source_type: str,
    now_ts_ms: int,
) -> int:
    """
    CONTRACT:
      preconditions:
        - cursor is one open psycopg cursor inside the caller transaction.
        - trade_identity_row and current_trade_version_row were read inside the same transaction.
        - next_trade_version_values contains the complete next head state for the trade.
      postconditions:
        - Turns the prior current version row off.
        - Inserts one new live version row linked through version_of_id.
        - Moves the trade current_version_id pointer and mirrored status fields to the new version.
      side_effects:
        - updates one previous stephen_dcx_trade_versions row to is_live = false
        - inserts one stephen_dcx_trade_versions row
        - updates one stephen_dcx_trades row current_version_id and mirrored statuses
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The trade row is the stable identity, while all changing terms should be appended as immutable
          versions to preserve a true commercial history.
      WHEN TO USE it:
        - Use it for any meaningful trade-state change after the first extraction, including edit,
          confirm, and reject actions.
      WHEN NOT TO USE it:
        - Do not use it for the first projected version or for read-only operations.
      WHAT CAN GO WRONG:
        - The caller can pass an incomplete next version shape.
        - Concurrent writers can race if the caller failed to lock the current trade/version rows first.
      WHAT COMES NEXT:
        - The caller can return the stable trade id while the latest terms remain readable from the
          new current version row.

    TESTS:
      - none yet

    ERRORS: []

    CODE:
    """
    cursor.execute(
        """
        UPDATE stephen_dcx_trade_versions
        SET
            is_live = FALSE,
            updated_at_ts_ms = %s
        WHERE id = %s
        """,
        (now_ts_ms, current_trade_version_row["id"]),
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
            normalized_material_key,
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
            %s, %s, %s, %s, %s, %s,
            TRUE,
            %s,
            %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s,
            %s::jsonb,
            %s::jsonb,
            %s,
            %s
        )
        RETURNING id AS version_id
        """,
        (
            trade_identity_row["id"],
            next_trade_version_values["source_message_id"],
            next_trade_version_values["source_workflow_item_id"],
            next_trade_version_values["source_channel_type"],
            next_trade_version_values["source_language_id"],
            current_trade_version_row["version_number"] + 1,
            current_trade_version_row["id"],
            version_source_type,
            next_trade_version_values["trade_projection_status"],
            next_trade_version_values["trade_confirmation_status"],
            next_trade_version_values["trade_status"],
            next_trade_version_values["raw_trade_side_text"],
            next_trade_version_values["raw_material_text"],
            next_trade_version_values["raw_quantity_text"],
            next_trade_version_values["raw_price_text"],
            next_trade_version_values["raw_origin_text"],
            next_trade_version_values["raw_destination_text"],
            next_trade_version_values["raw_shipping_method_text"],
            next_trade_version_values["raw_incoterm_text"],
            next_trade_version_values["raw_delivery_window_text"],
            next_trade_version_values["raw_quality_text"],
            next_trade_version_values["raw_payment_terms_text"],
            next_trade_version_values["raw_counterparty_scope_text"],
            next_trade_version_values["normalized_trade_side"],
            next_trade_version_values["normalized_material_name"],
            next_trade_version_values.get("normalized_material_key", ""),
            next_trade_version_values["normalized_quantity_value"],
            next_trade_version_values["normalized_quantity_unit"],
            next_trade_version_values["normalized_price_mode"],
            next_trade_version_values["normalized_price_value"],
            next_trade_version_values["normalized_price_unit_basis"],
            next_trade_version_values["normalized_currency_code"],
            next_trade_version_values["normalized_total_price_value"],
            next_trade_version_values["normalized_origin_location"],
            next_trade_version_values["normalized_destination_location"],
            next_trade_version_values["normalized_shipping_method"],
            next_trade_version_values["normalized_incoterm_code"],
            next_trade_version_values["normalized_delivery_window_start_text"],
            next_trade_version_values["normalized_delivery_window_end_text"],
            next_trade_version_values["normalized_quality_summary_text"],
            next_trade_version_values["normalized_payment_terms_summary_text"],
            next_trade_version_values["trade_summary_text"],
            next_trade_version_values["trade_extraction_notes_text"],
            psycopg2.extras.Json(next_trade_version_values["missing_required_fields_json"]),
            psycopg2.extras.Json(next_trade_version_values["trade_metadata_json"]),
            now_ts_ms,
            now_ts_ms,
        ),
    )
    next_version_row = cursor.fetchone()
    next_version_id = _read_returned_id(next_version_row, "version_id")
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
            next_version_id,
            next_trade_version_values["trade_projection_status"],
            next_trade_version_values["trade_confirmation_status"],
            next_trade_version_values["trade_status"],
            now_ts_ms,
            trade_identity_row["id"],
        ),
    )
    return next_version_id


def _read_returned_id(row: Any, column_name: str) -> int:
    if isinstance(row, dict):
        return int(row[column_name])
    return int(row[0])
