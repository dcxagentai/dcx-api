"""
CONTEXT:
This file publishes, shares, or withdraws one authenticated user's trade candidate.
It exists for the MVP market slice where a trader can keep a trade private, make it
visible to anyone with a link, or publish it onto the global Market > Deals board.

CONTRACT:
preconditions:
- authenticated_user_id is the initiating user who owns the trade.
- trade_id points to an existing stephen_dcx_trades row with a current version.
- visibility_status is private, shareable, or public.
postconditions:
- stephen_dcx_trades.visibility_status reflects the requested visibility.
- private trades have no active publication.
- shareable/public trades have one active stephen_dcx_trade_publications row.
side_effects:
- mutates stephen_dcx_trades and stephen_dcx_trade_publications.
idempotent: true for repeated calls with the same visibility.
retry_safe: true.
async_or_blocking: blocking database transaction.
idempotency_key: trade_id + visibility_status.
locks: SELECT FOR UPDATE on the trade identity row and any active publication row.
lock_strategy: short transaction; concurrent callers serialize on the trade row.

NARRATIVE:
WHY this exists: traders need a simple visibility switch before conversations and
global market boards can exist. The trade remains the durable private object; the
publication is a projection for market discovery or shared links.
WHEN TO USE it: from the app trade form, and later from explicit email/WhatsApp commands.
WHEN NOT TO USE it: do not use it to edit trade terms; trade versions own that.
WHAT CAN GO WRONG: missing SQL migration, invalid visibility, or a trade owned by another user.
WHAT COMES NEXT: public catalog views and trade conversation threads can attach to publications.

TESTS:
- No dedicated unit test exists yet. Smoke with PATCH /users/me/trades/{id}/visibility.

ERRORS:
- API_DCX_TRADE_VISIBILITY_INVALID: retry with private, shareable, or public.
- API_DCX_TRADE_VISIBILITY_NOT_FOUND: refresh the Trades view and retry with a current trade.
- API_DCX_TRADE_VISIBILITY_UPDATE_FAILED: retry after backend/database health is restored.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG

DCX_TRADE_VISIBILITY_STATUSES = {"private", "shareable", "public"}


def set_authenticated_dcx_user_trade_visibility(
    authenticated_user_id: int,
    trade_id: int,
    visibility_status: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    normalized_visibility_status = (visibility_status or "").strip().lower()
    if normalized_visibility_status not in DCX_TRADE_VISIBILITY_STATUSES:
        raise RuntimeError("API_DCX_TRADE_VISIBILITY_INVALID")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        trade.id,
                        trade.current_version_id,
                        trade.initiating_user_id
                    FROM stephen_dcx_trades trade
                    WHERE trade.id = %s
                      AND trade.initiating_user_id = %s
                    FOR UPDATE
                    """,
                    (trade_id, authenticated_user_id),
                )
                trade_row = cursor.fetchone()
                if trade_row is None:
                    return None

                current_version_id = trade_row[1]
                cursor.execute(
                    """
                    UPDATE stephen_dcx_trades
                    SET visibility_status = %s,
                        visibility_updated_at_ts_ms = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (normalized_visibility_status, now_ts_ms, now_ts_ms, trade_id),
                )

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_trade_publications
                    WHERE trade_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (trade_id,),
                )
                publication_row = cursor.fetchone()

                if normalized_visibility_status == "private":
                    if publication_row is not None:
                        cursor.execute(
                            """
                            UPDATE stephen_dcx_trade_publications
                            SET publication_status = 'withdrawn',
                                updated_at_ts_ms = %s
                            WHERE id = %s
                            """,
                            (now_ts_ms, publication_row[0]),
                        )
                    return {
                        "trade_id": trade_id,
                        "visibility_status": "private",
                        "trade_publication_id": None,
                    }

                published_summary_json = _build_trade_publication_summary_json(
                    cursor=cursor,
                    trade_id=trade_id,
                    current_version_id=current_version_id,
                )

                if publication_row is not None:
                    trade_publication_id = publication_row[0]
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_trade_publications
                        SET visibility_status = %s,
                            publication_status = 'active',
                            published_trade_version_id = %s,
                            published_summary_json = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            normalized_visibility_status,
                            current_version_id,
                            Json(published_summary_json),
                            now_ts_ms,
                            trade_publication_id,
                        ),
                    )
                else:
                    public_reference_code = f"T{trade_id}"
                    share_token = f"trade_{uuid.uuid4().hex}"
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_trade_publications (
                            trade_id,
                            owner_user_id,
                            published_trade_version_id,
                            visibility_status,
                            publication_status,
                            public_reference_code,
                            share_token,
                            published_summary_json,
                            publication_metadata_json,
                            created_at_ts_ms,
                            updated_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            trade_id,
                            authenticated_user_id,
                            current_version_id,
                            normalized_visibility_status,
                            public_reference_code,
                            share_token,
                            Json(published_summary_json),
                            Json({}),
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                    trade_publication_id = cursor.fetchone()[0]

        return {
            "trade_id": trade_id,
            "visibility_status": normalized_visibility_status,
            "trade_publication_id": trade_publication_id,
        }
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_VISIBILITY_UPDATE_FAILED") from exc


def _build_trade_publication_summary_json(
    cursor: Any,
    trade_id: int,
    current_version_id: int | None,
) -> dict:
    if current_version_id is None:
        return {"trade_id": trade_id}

    cursor.execute(
        """
        SELECT
            trade_summary_text,
            normalized_trade_side,
            normalized_material_name,
            normalized_quantity_value,
            normalized_quantity_unit,
            normalized_price_value,
            normalized_price_unit_basis,
            normalized_currency_code,
            normalized_origin_location,
            normalized_destination_location
        FROM stephen_dcx_trade_versions
        WHERE id = %s
        LIMIT 1
        """,
        (current_version_id,),
    )
    version_row = cursor.fetchone()
    if version_row is None:
        return {"trade_id": trade_id}

    return {
        "trade_id": trade_id,
        "trade_summary_text": version_row[0] or "",
        "normalized_trade_side": version_row[1] or "",
        "normalized_material_name": version_row[2] or "",
        "normalized_quantity_value": float(version_row[3]) if version_row[3] is not None else None,
        "normalized_quantity_unit": version_row[4] or "",
        "normalized_price_value": float(version_row[5]) if version_row[5] is not None else None,
        "normalized_price_unit_basis": version_row[6] or "",
        "normalized_currency_code": version_row[7] or "",
        "normalized_origin_location": version_row[8] or "",
        "normalized_destination_location": version_row[9] or "",
    }
