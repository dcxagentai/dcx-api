"""
CONTEXT:
This file rejects one authenticated DCX user trade candidate.
It exists so traders can explicitly tell DCX that a projected trade candidate should not move forward.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
import psycopg2.extras

from messages.create_new_dcx_trade_version_and_promote_current_trade import (
    create_new_dcx_trade_version_and_promote_current_trade,
)
from messages.read_current_dcx_trade_identity_and_version_rows_for_authenticated_user import (
    read_current_dcx_trade_identity_and_version_rows_for_authenticated_user,
)
from storage.db_config import DB_CONFIG


def reject_authenticated_dcx_user_trade_candidate(
    authenticated_user_id: int,
    trade_id: int,
    rejection_reason_text: str = "",
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies the owning DCX user.
        - trade_id identifies one persisted trade candidate for that user.
      postconditions:
        - Returns the stable trade id when the candidate belongs to the user.
        - Appends one new immutable rejected/archived trade version.
      side_effects:
        - updates one stephen_dcx_trade_versions row to is_live = false
        - inserts one stephen_dcx_trade_versions row
        - updates one stephen_dcx_trades current-version pointer
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Traders need one explicit way to tell DCX that an extraction is wrong or unwanted.
      WHEN TO USE it:
        - Use it from the authenticated Trades surface when the projected trade should not proceed.
      WHEN NOT TO USE it:
        - Do not use it for another user’s trade or for destructive deletion of source messages.
      WHAT CAN GO WRONG:
        - The trade may not exist for the current user.
      WHAT COMES NEXT:
        - Rejected trade candidates remain available as historical context without cluttering active workflow.

    TESTS:
      - none yet

    ERRORS: []

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        return None
    if not isinstance(trade_id, int) or trade_id <= 0:
        return None

    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()
    connect = connect_to_database or psycopg2.connect

    with connect(**DB_CONFIG) as connection:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            trade_identity_row, current_trade_version_row = (
                read_current_dcx_trade_identity_and_version_rows_for_authenticated_user(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    trade_id=trade_id,
                    lock_for_update=True,
                )
            )
            if trade_identity_row is None or current_trade_version_row is None:
                return None
            if current_trade_version_row["trade_confirmation_status"] == "rejected":
                return {"trade_id": trade_id, "was_noop": True}

            next_trade_version_values = {
                **current_trade_version_row,
                "trade_confirmation_status": "rejected",
                "trade_status": "archived",
                "trade_metadata_json": {
                    **(current_trade_version_row.get("trade_metadata_json") or {}),
                    "rejected_at_ts_ms": now_ts_ms,
                    "rejected_by_user_id": authenticated_user_id,
                    "rejection_reason_text": rejection_reason_text.strip(),
                },
            }
            create_new_dcx_trade_version_and_promote_current_trade(
                cursor=cursor,
                trade_identity_row=trade_identity_row,
                current_trade_version_row=current_trade_version_row,
                next_trade_version_values=next_trade_version_values,
                version_source_type="user_reject",
                now_ts_ms=now_ts_ms,
            )

    return {"trade_id": trade_id, "was_noop": False}


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
