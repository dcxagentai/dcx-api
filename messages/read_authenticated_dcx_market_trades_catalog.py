"""
CONTEXT:
This file reads the public Market > Deals catalog for an authenticated DCX app user.
It projects active public trade publications, not the user's private trade workspace.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_market_trades_catalog(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_DCX_MARKET_TRADES_USER_NOT_FOUND")

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
                    raise RuntimeError("API_DCX_MARKET_TRADES_USER_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        publication.id,
                        publication.trade_id,
                        publication.owner_user_id,
                        publication.public_reference_code,
                        publication.visibility_status,
                        publication.updated_at_ts_ms,
                        CASE
                          WHEN owner_user.public_identity_mode = 'anonymous' THEN 'Trader #' || owner_user.id::text
                          WHEN owner_user.public_identity_mode = 'handle' AND NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          WHEN NULLIF(owner_user.public_display_name, '') IS NOT NULL THEN owner_user.public_display_name
                          WHEN NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          ELSE 'Trader #' || owner_user.id::text
                        END AS owner_public_identity_label,
                        trade_version.trade_summary_text,
                        trade_version.normalized_trade_side,
                        trade_version.normalized_material_name,
                        trade_version.normalized_quantity_value,
                        trade_version.normalized_quantity_unit,
                        trade_version.normalized_price_value,
                        trade_version.normalized_price_unit_basis,
                        trade_version.normalized_currency_code,
                        trade_version.normalized_origin_location,
                        trade_version.normalized_destination_location,
                        trade_version.trade_confirmation_status,
                        trade_version.trade_status
                    FROM stephen_dcx_trade_publications publication
                    INNER JOIN stephen_dcx_trades trade
                      ON trade.id = publication.trade_id
                    INNER JOIN stephen_dcx_users owner_user
                      ON owner_user.id = publication.owner_user_id
                    INNER JOIN stephen_dcx_trade_versions trade_version
                      ON trade_version.id = trade.current_version_id
                    WHERE publication.visibility_status = 'public'
                      AND publication.publication_status = 'active'
                    ORDER BY publication.updated_at_ts_ms DESC, publication.id DESC
                    """,
                )
                trade_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_MARKET_TRADES_CATALOG_READ_FAILED") from exc

    return {
        "market_trades": [
            {
                "trade_publication_id": row[0],
                "trade_id": row[1],
                "owner_user_id": row[2],
                "public_reference_code": row[3],
                "visibility_status": row[4],
                "updated_at_ts_ms": row[5],
                "owner_public_identity_label": row[6],
                "trade_summary_text": row[7],
                "normalized_trade_side": row[8],
                "normalized_material_name": row[9],
                "normalized_quantity_value": float(row[10]) if row[10] is not None else None,
                "normalized_quantity_unit": row[11],
                "normalized_price_value": float(row[12]) if row[12] is not None else None,
                "normalized_price_unit_basis": row[13],
                "normalized_currency_code": row[14],
                "normalized_origin_location": row[15],
                "normalized_destination_location": row[16],
                "trade_confirmation_status": row[17],
                "trade_status": row[18],
                "is_owned_by_authenticated_user": row[2] == authenticated_user_id,
            }
            for row in trade_rows
        ],
        "total_market_trade_count": len(trade_rows),
    }
