"""
CONTEXT:
This file confirms one authenticated DCX user trade candidate.
It exists so Slice 1 can move extracted trade candidates from pending review into the first real
open-trade state once the owning trader confirms the extraction.
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

DCX_TRADE_REQUIRED_NORMALIZED_FIELDS = {
    "normalized_trade_side",
    "normalized_material_name",
}


def confirm_authenticated_dcx_user_trade_candidate(
    authenticated_user_id: int,
    trade_id: int,
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
        - Appends one new immutable confirmed/open trade version when no required fields are missing.
        - Returns null when the trade is missing for that user.
      side_effects:
        - updates one stephen_dcx_trade_versions row to is_live = false
        - inserts one stephen_dcx_trade_versions row
        - updates one stephen_dcx_trades current-version pointer
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: trade_confirm:{authenticated_user_id}:{trade_id}
      locks:
        - row lock on the target stephen_dcx_trades row
      contention_strategy: latest valid confirm wins while converging on the same confirmed state

    NARRATIVE:
      WHY this exists:
        - Trade extraction alone is not enough; the trader must explicitly confirm the projected structure.
      WHEN TO USE it:
        - Use it from the authenticated Trades surface once the candidate has enough detail.
      WHEN NOT TO USE it:
        - Do not use it for trades belonging to another user or candidates still missing essential fields.
      WHAT CAN GO WRONG:
        - The trade may not exist.
        - The trade may still need more detail.
        - The trade may already be rejected.
      WHAT COMES NEXT:
        - Slice 2 can route confirmed trades into trader-to-trader interaction workflows.

    TESTS:
      - none yet

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_TRADE_CONFIRMATION_FIELDS_MISSING:
          suggested_action: Fill the missing trade fields first, then confirm again.
          common_causes:
            - incomplete extracted trade candidate
          recovery_steps:
            - Update the missing fields from the Trades page.
            - Retry confirmation.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_TRADE_CONFIRMATION_REJECTED:
          suggested_action: Recreate the trade from a new message if this extraction was rejected accidentally.
          common_causes:
            - trader rejected the candidate earlier
          recovery_steps:
            - Review the source message.
            - Re-ingest or recreate if still needed.
          retry_safe: true

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
                raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_CONFIRMATION_REJECTED")
            if (
                current_trade_version_row["trade_confirmation_status"] == "confirmed"
                and current_trade_version_row["trade_status"] == "open"
            ):
                return {"trade_id": trade_id, "was_noop": True}

            missing_required_fields = _read_trade_missing_required_fields(dict(current_trade_version_row))
            if missing_required_fields:
                raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_CONFIRMATION_FIELDS_MISSING")

            next_trade_version_values = {
                **current_trade_version_row,
                "trade_confirmation_status": "confirmed",
                "trade_status": "open",
                "missing_required_fields_json": missing_required_fields,
                "trade_metadata_json": {
                    **(current_trade_version_row.get("trade_metadata_json") or {}),
                    "confirmed_at_ts_ms": now_ts_ms,
                    "confirmed_by_user_id": authenticated_user_id,
                },
            }
            create_new_dcx_trade_version_and_promote_current_trade(
                cursor=cursor,
                trade_identity_row=trade_identity_row,
                current_trade_version_row=current_trade_version_row,
                next_trade_version_values=next_trade_version_values,
                version_source_type="user_confirm",
                now_ts_ms=now_ts_ms,
            )

    return {"trade_id": trade_id, "was_noop": False}


def _read_trade_missing_required_fields(trade_row: dict) -> list[str]:
    missing_fields: list[str] = []
    for field_name in sorted(DCX_TRADE_REQUIRED_NORMALIZED_FIELDS):
        field_value = trade_row.get(field_name)
        if field_value is None:
            missing_fields.append(field_name)
            continue
        if isinstance(field_value, str) and field_value.strip() == "":
            missing_fields.append(field_name)
    return missing_fields


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
