"""
CONTEXT:
This file reads one authenticated user trade-candidate detail payload.
It exists so the app can open the first structured trade detail view in Slice 1.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from messages.read_authenticated_dcx_source_message_first_image_attachment import (
    read_authenticated_dcx_source_message_first_image_attachment,
)
from storage.db_config import DB_CONFIG

DCX_TRADE_CONFIRMABLE_NORMALIZED_FIELDS = {
    "normalized_trade_side",
    "normalized_material_name",
}


def read_authenticated_dcx_user_trade_detail(
    authenticated_user_id: int,
    trade_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        trade.id,
                        trade.source_message_id_initial,
                        trade_version.trade_projection_status,
                        trade_version.trade_confirmation_status,
                        trade_version.trade_status,
                        trade_version.raw_trade_side_text,
                        trade_version.raw_material_text,
                        trade_version.raw_quantity_text,
                        trade_version.raw_price_text,
                        trade_version.raw_origin_text,
                        trade_version.raw_destination_text,
                        trade_version.raw_shipping_method_text,
                        trade_version.raw_incoterm_text,
                        trade_version.raw_delivery_window_text,
                        trade_version.raw_quality_text,
                        trade_version.raw_payment_terms_text,
                        trade_version.raw_counterparty_scope_text,
                        trade_version.normalized_trade_side,
                        trade_version.normalized_material_name,
                        trade_version.normalized_quantity_value,
                        trade_version.normalized_quantity_unit,
                        trade_version.normalized_price_mode,
                        trade_version.normalized_price_value,
                        trade_version.normalized_price_unit_basis,
                        trade_version.normalized_currency_code,
                        trade_version.normalized_total_price_value,
                        trade_version.normalized_origin_location,
                        trade_version.normalized_destination_location,
                        trade_version.normalized_shipping_method,
                        trade_version.normalized_incoterm_code,
                        trade_version.normalized_delivery_window_start_text,
                        trade_version.normalized_delivery_window_end_text,
                        trade_version.normalized_quality_summary_text,
                        trade_version.normalized_payment_terms_summary_text,
                        trade_version.trade_summary_text,
                        trade_version.trade_extraction_notes_text,
                        trade_version.missing_required_fields_json,
                        trade_version.trade_metadata_json,
                        trade.visibility_status,
                        publication.id AS trade_publication_id,
                        publication.public_reference_code,
                        publication.visibility_status AS publication_visibility_status,
                        publication.publication_status,
                        trade.created_at_ts_ms,
                        trade.updated_at_ts_ms,
                        trade_version.normalized_material_key
                    FROM stephen_dcx_trades trade
                    INNER JOIN stephen_dcx_trade_versions trade_version
                      ON trade_version.id = trade.current_version_id
                    LEFT JOIN stephen_dcx_trade_publications publication
                      ON publication.trade_id = trade.id
                     AND publication.publication_status = 'active'
                    WHERE trade.id = %s
                      AND trade.initiating_user_id = %s
                    LIMIT 1
                    """,
                    (trade_id, authenticated_user_id),
                )
                trade_row = cursor.fetchone()
                trade_version_rows = []
                source_first_image_attachment = None
                if trade_row is not None:
                    source_first_image_attachment = read_authenticated_dcx_source_message_first_image_attachment(
                        cursor=cursor,
                        authenticated_user_id=authenticated_user_id,
                        source_message_id=trade_row[1],
                    )
                    cursor.execute(
                        """
                        SELECT
                            trade_version.id,
                            trade_version.version_number,
                            trade_version.is_live,
                            trade_version.version_of_id,
                            trade_version.version_source_type,
                            trade_version.trade_confirmation_status,
                            trade_version.trade_status,
                            trade_version.normalized_trade_side,
                            trade_version.normalized_material_name,
                            trade_version.normalized_quantity_value,
                            trade_version.normalized_quantity_unit,
                            trade_version.normalized_price_value,
                            trade_version.normalized_currency_code,
                            trade_version.normalized_total_price_value,
                            trade_version.normalized_origin_location,
                            trade_version.normalized_destination_location,
                            trade_version.updated_at_ts_ms,
                            trade_version.normalized_material_key
                        FROM stephen_dcx_trade_versions trade_version
                        WHERE trade_version.trade_id = %s
                        ORDER BY trade_version.version_number DESC, trade_version.id DESC
                        """,
                        (trade_id,),
                    )
                    trade_version_rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_DETAIL_READ_FAILED") from exc

    if trade_row is None:
        return None

    return {
        "trade_id": trade_row[0],
        "source_message_id": trade_row[1],
        "source_first_image_attachment": source_first_image_attachment,
        "trade_projection_status": trade_row[2],
        "trade_confirmation_status": trade_row[3],
        "trade_status": trade_row[4],
        "raw_trade_side_text": trade_row[5],
        "raw_material_text": trade_row[6],
        "raw_quantity_text": trade_row[7],
        "raw_price_text": trade_row[8],
        "raw_origin_text": trade_row[9],
        "raw_destination_text": trade_row[10],
        "raw_shipping_method_text": trade_row[11],
        "raw_incoterm_text": trade_row[12],
        "raw_delivery_window_text": trade_row[13],
        "raw_quality_text": trade_row[14],
        "raw_payment_terms_text": trade_row[15],
        "raw_counterparty_scope_text": trade_row[16],
        "normalized_trade_side": trade_row[17],
        "normalized_material_name": trade_row[18],
        "normalized_material_key": trade_row[45] or "",
        "normalized_quantity_value": float(trade_row[19]) if trade_row[19] is not None else None,
        "normalized_quantity_unit": trade_row[20],
        "normalized_price_mode": trade_row[21],
        "normalized_price_value": float(trade_row[22]) if trade_row[22] is not None else None,
        "normalized_price_unit_basis": trade_row[23],
        "normalized_currency_code": trade_row[24],
        "normalized_total_price_value": float(trade_row[25]) if trade_row[25] is not None else None,
        "normalized_origin_location": trade_row[26],
        "normalized_destination_location": trade_row[27],
        "normalized_shipping_method": trade_row[28],
        "normalized_incoterm_code": trade_row[29],
        "normalized_delivery_window_start_text": trade_row[30],
        "normalized_delivery_window_end_text": trade_row[31],
        "normalized_quality_summary_text": trade_row[32],
        "normalized_payment_terms_summary_text": trade_row[33],
        "trade_summary_text": trade_row[34],
        "trade_extraction_notes_text": trade_row[35],
        "missing_required_fields_json": trade_row[36] if isinstance(trade_row[36], list) else [],
        "trade_metadata_json": trade_row[37] if isinstance(trade_row[37], dict) else {},
        "visibility_status": trade_row[38] or "private",
        "trade_publication_id": trade_row[39],
        "public_reference_code": trade_row[40],
        "publication_visibility_status": trade_row[41],
        "publication_status": trade_row[42],
        "requires_user_attention": trade_row[3] in {"pending_confirmation", "needs_more_detail"},
        "can_confirm": trade_row[3] != "rejected" and not _read_trade_confirm_blocking_missing_fields(
            {
                "normalized_trade_side": trade_row[17],
                "normalized_material_name": trade_row[18],
            }
        ),
        "can_reject": trade_row[3] != "rejected",
        "created_at_ts_ms": trade_row[43],
        "updated_at_ts_ms": trade_row[44],
        "trade_versions": [
            {
                "version_id": version_row[0],
                "version_number": version_row[1],
                "is_live": version_row[2],
                "version_of_id": version_row[3],
                "version_source_type": version_row[4],
                "trade_confirmation_status": version_row[5],
                "trade_status": version_row[6],
                "normalized_trade_side": version_row[7],
                "normalized_material_name": version_row[8],
                "normalized_material_key": version_row[17] or "",
                "normalized_quantity_value": float(version_row[9]) if version_row[9] is not None else None,
                "normalized_quantity_unit": version_row[10],
                "normalized_price_value": float(version_row[11]) if version_row[11] is not None else None,
                "normalized_currency_code": version_row[12],
                "normalized_total_price_value": float(version_row[13]) if version_row[13] is not None else None,
                "normalized_origin_location": version_row[14],
                "normalized_destination_location": version_row[15],
                "updated_at_ts_ms": version_row[16],
            }
            for version_row in trade_version_rows
        ],
    }


def _read_trade_confirm_blocking_missing_fields(trade_row: dict) -> list[str]:
    missing_fields: list[str] = []
    for field_name in sorted(DCX_TRADE_CONFIRMABLE_NORMALIZED_FIELDS):
        field_value = trade_row.get(field_name)
        if field_value is None:
            missing_fields.append(field_name)
            continue
        if isinstance(field_value, str) and field_value.strip() == "":
            missing_fields.append(field_name)
    return missing_fields
