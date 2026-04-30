"""
CONTEXT:
This file reads one current DCX trade identity row together with its current live version row.
It exists so trade update, confirm, and reject flows can lock one stable trade anchor while
reasoning over the current immutable version snapshot.
"""

from __future__ import annotations

from typing import Any


def read_current_dcx_trade_identity_and_version_rows_for_authenticated_user(
    cursor: Any,
    authenticated_user_id: int,
    trade_id: int,
    lock_for_update: bool = False,
) -> tuple[dict | None, dict | None]:
    """
    CONTRACT:
      preconditions:
        - cursor is one open psycopg cursor inside the caller transaction.
        - authenticated_user_id identifies the owning user for the requested trade.
        - trade_id identifies the stable trade identity row.
      postconditions:
        - Returns the trade identity row and current live version row when visible to the user.
        - Returns (null, null) when the trade does not exist for that user.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Slice 1 trade versioning needs one shared way to reason about the stable trade anchor and
          its current live terms without duplicating fragile join SQL across every trade mutation.
      WHEN TO USE it:
        - Use it before mutating or reading the current head state of one authenticated user trade.
      WHEN NOT TO USE it:
        - Do not use it for catalog reads across many trades; those queries should join directly.
      WHAT CAN GO WRONG:
        - The trade may not exist for the authenticated user.
        - The trade may exist but be missing a current version, which indicates broken persistence.
      WHAT COMES NEXT:
        - Callers can append a new immutable version and then move the parent head pointer.

    TESTS:
      - none yet

    ERRORS: []

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        return None, None
    if not isinstance(trade_id, int) or trade_id <= 0:
        return None, None

    for_update_clause = "FOR UPDATE OF trade, trade_version" if lock_for_update else ""
    cursor.execute(
        f"""
        SELECT
            trade.id AS trade_id,
            trade.trade_key AS trade_key,
            trade.initiating_user_id AS initiating_user_id,
            trade.initiating_contact_method_id AS initiating_contact_method_id,
            trade.source_message_id_initial AS source_message_id_initial,
            trade.source_workflow_item_id_initial AS source_workflow_item_id_initial,
            trade.current_version_id AS current_version_id,
            trade.current_trade_projection_status AS current_trade_projection_status,
            trade.current_trade_confirmation_status AS current_trade_confirmation_status,
            trade.current_trade_status AS current_trade_status,
            trade.created_at_ts_ms AS trade_created_at_ts_ms,
            trade.updated_at_ts_ms AS trade_updated_at_ts_ms,
            trade_version.id AS version_id,
            trade_version.trade_id AS version_trade_id,
            trade_version.source_message_id AS version_source_message_id,
            trade_version.source_workflow_item_id AS version_source_workflow_item_id,
            trade_version.source_channel_type AS version_source_channel_type,
            trade_version.source_language_id AS version_source_language_id,
            trade_version.version_number AS version_number,
            trade_version.is_live AS version_is_live,
            trade_version.version_of_id AS version_of_id,
            trade_version.version_source_type AS version_source_type,
            trade_version.trade_projection_status AS version_trade_projection_status,
            trade_version.trade_confirmation_status AS version_trade_confirmation_status,
            trade_version.trade_status AS version_trade_status,
            trade_version.raw_trade_side_text AS raw_trade_side_text,
            trade_version.raw_material_text AS raw_material_text,
            trade_version.raw_quantity_text AS raw_quantity_text,
            trade_version.raw_price_text AS raw_price_text,
            trade_version.raw_origin_text AS raw_origin_text,
            trade_version.raw_destination_text AS raw_destination_text,
            trade_version.raw_shipping_method_text AS raw_shipping_method_text,
            trade_version.raw_incoterm_text AS raw_incoterm_text,
            trade_version.raw_delivery_window_text AS raw_delivery_window_text,
            trade_version.raw_quality_text AS raw_quality_text,
            trade_version.raw_payment_terms_text AS raw_payment_terms_text,
            trade_version.raw_counterparty_scope_text AS raw_counterparty_scope_text,
            trade_version.normalized_trade_side AS normalized_trade_side,
            trade_version.normalized_material_name AS normalized_material_name,
            trade_version.normalized_quantity_value AS normalized_quantity_value,
            trade_version.normalized_quantity_unit AS normalized_quantity_unit,
            trade_version.normalized_price_mode AS normalized_price_mode,
            trade_version.normalized_price_value AS normalized_price_value,
            trade_version.normalized_price_unit_basis AS normalized_price_unit_basis,
            trade_version.normalized_currency_code AS normalized_currency_code,
            trade_version.normalized_total_price_value AS normalized_total_price_value,
            trade_version.normalized_origin_location AS normalized_origin_location,
            trade_version.normalized_destination_location AS normalized_destination_location,
            trade_version.normalized_shipping_method AS normalized_shipping_method,
            trade_version.normalized_incoterm_code AS normalized_incoterm_code,
            trade_version.normalized_delivery_window_start_text AS normalized_delivery_window_start_text,
            trade_version.normalized_delivery_window_end_text AS normalized_delivery_window_end_text,
            trade_version.normalized_quality_summary_text AS normalized_quality_summary_text,
            trade_version.normalized_payment_terms_summary_text AS normalized_payment_terms_summary_text,
            trade_version.trade_summary_text AS trade_summary_text,
            trade_version.trade_extraction_notes_text AS trade_extraction_notes_text,
            trade_version.missing_required_fields_json AS missing_required_fields_json,
            trade_version.trade_metadata_json AS trade_metadata_json,
            trade_version.created_at_ts_ms AS version_created_at_ts_ms,
            trade_version.updated_at_ts_ms AS version_updated_at_ts_ms
        FROM stephen_dcx_trades trade
        INNER JOIN stephen_dcx_trade_versions trade_version
          ON trade_version.id = trade.current_version_id
        WHERE trade.id = %s
          AND trade.initiating_user_id = %s
        LIMIT 1
        {for_update_clause}
        """,
        (trade_id, authenticated_user_id),
    )
    row = cursor.fetchone()
    if row is None:
        return None, None

    trade_identity_row = {
        "id": _read_row_value(row, "trade_id", 0),
        "trade_key": _read_row_value(row, "trade_key", 1),
        "initiating_user_id": _read_row_value(row, "initiating_user_id", 2),
        "initiating_contact_method_id": _read_row_value(row, "initiating_contact_method_id", 3),
        "source_message_id_initial": _read_row_value(row, "source_message_id_initial", 4),
        "source_workflow_item_id_initial": _read_row_value(row, "source_workflow_item_id_initial", 5),
        "current_version_id": _read_row_value(row, "current_version_id", 6),
        "current_trade_projection_status": _read_row_value(row, "current_trade_projection_status", 7),
        "current_trade_confirmation_status": _read_row_value(row, "current_trade_confirmation_status", 8),
        "current_trade_status": _read_row_value(row, "current_trade_status", 9),
        "created_at_ts_ms": _read_row_value(row, "trade_created_at_ts_ms", 10),
        "updated_at_ts_ms": _read_row_value(row, "trade_updated_at_ts_ms", 11),
    }
    missing_required_fields_json = _read_row_value(row, "missing_required_fields_json", 56)
    trade_metadata_json = _read_row_value(row, "trade_metadata_json", 57)
    trade_version_row = {
        "id": _read_row_value(row, "version_id", 12),
        "trade_id": _read_row_value(row, "version_trade_id", 13),
        "source_message_id": _read_row_value(row, "version_source_message_id", 14),
        "source_workflow_item_id": _read_row_value(row, "version_source_workflow_item_id", 15),
        "source_channel_type": _read_row_value(row, "version_source_channel_type", 16),
        "source_language_id": _read_row_value(row, "version_source_language_id", 17),
        "version_number": _read_row_value(row, "version_number", 18),
        "is_live": _read_row_value(row, "version_is_live", 19),
        "version_of_id": _read_row_value(row, "version_of_id", 20),
        "version_source_type": _read_row_value(row, "version_source_type", 21),
        "trade_projection_status": _read_row_value(row, "version_trade_projection_status", 22),
        "trade_confirmation_status": _read_row_value(row, "version_trade_confirmation_status", 23),
        "trade_status": _read_row_value(row, "version_trade_status", 24),
        "raw_trade_side_text": _read_row_value(row, "raw_trade_side_text", 25),
        "raw_material_text": _read_row_value(row, "raw_material_text", 26),
        "raw_quantity_text": _read_row_value(row, "raw_quantity_text", 27),
        "raw_price_text": _read_row_value(row, "raw_price_text", 28),
        "raw_origin_text": _read_row_value(row, "raw_origin_text", 29),
        "raw_destination_text": _read_row_value(row, "raw_destination_text", 30),
        "raw_shipping_method_text": _read_row_value(row, "raw_shipping_method_text", 31),
        "raw_incoterm_text": _read_row_value(row, "raw_incoterm_text", 32),
        "raw_delivery_window_text": _read_row_value(row, "raw_delivery_window_text", 33),
        "raw_quality_text": _read_row_value(row, "raw_quality_text", 34),
        "raw_payment_terms_text": _read_row_value(row, "raw_payment_terms_text", 35),
        "raw_counterparty_scope_text": _read_row_value(row, "raw_counterparty_scope_text", 36),
        "normalized_trade_side": _read_row_value(row, "normalized_trade_side", 37),
        "normalized_material_name": _read_row_value(row, "normalized_material_name", 38),
        "normalized_quantity_value": _read_row_value(row, "normalized_quantity_value", 39),
        "normalized_quantity_unit": _read_row_value(row, "normalized_quantity_unit", 40),
        "normalized_price_mode": _read_row_value(row, "normalized_price_mode", 41),
        "normalized_price_value": _read_row_value(row, "normalized_price_value", 42),
        "normalized_price_unit_basis": _read_row_value(row, "normalized_price_unit_basis", 43),
        "normalized_currency_code": _read_row_value(row, "normalized_currency_code", 44),
        "normalized_total_price_value": _read_row_value(row, "normalized_total_price_value", 45),
        "normalized_origin_location": _read_row_value(row, "normalized_origin_location", 46),
        "normalized_destination_location": _read_row_value(row, "normalized_destination_location", 47),
        "normalized_shipping_method": _read_row_value(row, "normalized_shipping_method", 48),
        "normalized_incoterm_code": _read_row_value(row, "normalized_incoterm_code", 49),
        "normalized_delivery_window_start_text": _read_row_value(row, "normalized_delivery_window_start_text", 50),
        "normalized_delivery_window_end_text": _read_row_value(row, "normalized_delivery_window_end_text", 51),
        "normalized_quality_summary_text": _read_row_value(row, "normalized_quality_summary_text", 52),
        "normalized_payment_terms_summary_text": _read_row_value(row, "normalized_payment_terms_summary_text", 53),
        "trade_summary_text": _read_row_value(row, "trade_summary_text", 54),
        "trade_extraction_notes_text": _read_row_value(row, "trade_extraction_notes_text", 55),
        "missing_required_fields_json": missing_required_fields_json if isinstance(missing_required_fields_json, list) else [],
        "trade_metadata_json": trade_metadata_json if isinstance(trade_metadata_json, dict) else {},
        "created_at_ts_ms": _read_row_value(row, "version_created_at_ts_ms", 58),
        "updated_at_ts_ms": _read_row_value(row, "version_updated_at_ts_ms", 59),
    }
    return trade_identity_row, trade_version_row


def _read_row_value(row: Any, column_name: str, column_index: int) -> Any:
    if isinstance(row, dict):
        return row[column_name]
    return row[column_index]
