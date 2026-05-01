"""
CONTEXT:
This file reads the first authenticated Trades catalog payload for one DCX app user.
It exists so Slice 1 can project routed trade candidates into a dedicated user-visible list.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_user_trades_catalog(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADES_USER_NOT_FOUND")

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
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADES_USER_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        trade.id,
                        trade.source_message_id_initial,
                        trade_version.trade_confirmation_status,
                        trade_version.trade_status,
                        trade_version.trade_summary_text,
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
                        trade_version.missing_required_fields_json,
                        trade_version.trade_metadata_json,
                        trade.visibility_status,
                        publication.id AS trade_publication_id,
                        publication.public_reference_code,
                        publication.visibility_status AS publication_visibility_status,
                        publication.publication_status,
                        trade.updated_at_ts_ms,
                        message.channel_type,
                        message.created_at_ts_ms
                    FROM stephen_dcx_trades trade
                    INNER JOIN stephen_dcx_trade_versions trade_version
                      ON trade_version.id = trade.current_version_id
                    INNER JOIN stephen_dcx_contact_messages message
                      ON message.id = trade.source_message_id_initial
                    LEFT JOIN stephen_dcx_trade_publications publication
                      ON publication.trade_id = trade.id
                     AND publication.publication_status = 'active'
                    WHERE trade.initiating_user_id = %s
                    ORDER BY trade.updated_at_ts_ms DESC, trade.id DESC
                    """,
                    (authenticated_user_id,),
                )
                trade_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADES_CATALOG_READ_FAILED") from exc

    return {
        "trades": [
            {
                "trade_id": row[0],
                "source_message_id": row[1],
                "trade_confirmation_status": row[2],
                "trade_status": row[3],
                "trade_summary_text": row[4],
                "normalized_trade_side": row[5],
                "normalized_material_name": row[6],
                "normalized_quantity_value": float(row[7]) if row[7] is not None else None,
                "normalized_quantity_unit": row[8],
                "normalized_price_mode": row[9],
                "normalized_price_value": float(row[10]) if row[10] is not None else None,
                "normalized_price_unit_basis": row[11],
                "normalized_currency_code": row[12],
                "normalized_total_price_value": float(row[13]) if row[13] is not None else None,
                "normalized_origin_location": row[14],
                "normalized_destination_location": row[15],
                "missing_required_fields_json": row[16] if isinstance(row[16], list) else [],
                "trade_metadata_json": row[17] if isinstance(row[17], dict) else {},
                "visibility_status": row[18] or "private",
                "trade_publication_id": row[19],
                "public_reference_code": row[20],
                "publication_visibility_status": row[21],
                "publication_status": row[22],
                "requires_user_attention": row[2] in {"pending_confirmation", "needs_more_detail"},
                "updated_at_ts_ms": row[23],
                "source_channel_type": row[24],
                "source_created_at_ts_ms": row[25],
            }
            for row in trade_rows
        ],
        "total_trade_count": len(trade_rows),
    }
