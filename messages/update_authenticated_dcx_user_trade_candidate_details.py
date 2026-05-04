"""
CONTEXT:
This file updates normalized fields on one authenticated DCX user trade candidate.
It exists so Slice 1 can let traders repair or complete extracted trade details before confirmation.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
import psycopg2.extras

from messages.create_new_dcx_trade_version_and_promote_current_trade import (
    create_new_dcx_trade_version_and_promote_current_trade,
)
from messages.read_dcx_trade_interest_material_key import read_dcx_trade_interest_material_key
from messages.read_current_dcx_trade_identity_and_version_rows_for_authenticated_user import (
    read_current_dcx_trade_identity_and_version_rows_for_authenticated_user,
)
from storage.db_config import DB_CONFIG

DCX_TRADE_EDITABLE_NORMALIZED_FIELDS = {
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
    "trade_confirmation_status",
    "trade_status",
}

DCX_TRADE_REQUIRED_NORMALIZED_FIELDS = {
    "normalized_trade_side",
    "normalized_material_name",
}

DCX_TRADE_ALLOWED_CONFIRMATION_STATUSES = {
    "draft",
    "needs_more_detail",
    "pending_confirmation",
    "confirmed",
    "under_revision",
    "rejected",
}

DCX_TRADE_ALLOWED_TRADE_STATUSES = {
    "draft",
    "open",
    "archived",
}


def update_authenticated_dcx_user_trade_candidate_details(
    authenticated_user_id: int,
    trade_id: int,
    patch_payload: dict,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies the owning DCX user.
        - trade_id identifies one persisted trade candidate for that user.
        - patch_payload contains only supported normalized trade fields.
      postconditions:
        - Appends one new immutable trade version when the allowed normalized fields changed.
        - Recomputes the missing-fields list on the new head version.
        - Moves the current confirmation status to pending_confirmation when required fields are now complete.
      side_effects:
        - updates one stephen_dcx_trade_versions row to is_live = false
        - inserts one stephen_dcx_trade_versions row
        - updates one stephen_dcx_trades current-version pointer
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first trade-candidate flow needs a way to repair the LLM projection without losing the original raw message.
      WHEN TO USE it:
        - Use it from the authenticated Trades surface when details are missing or need correction.
      WHEN NOT TO USE it:
        - Do not use it to rewrite raw source text or change trade ownership.
      WHAT CAN GO WRONG:
        - The trade may not exist.
        - The patch payload may contain unsupported fields.
      WHAT COMES NEXT:
        - Slice 2 can add richer structured validation and commodity-specific normalization rules.

    TESTS:
      - none yet

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_TRADE_PATCH_INVALID:
          suggested_action: Retry with only supported normalized trade fields.
          common_causes:
            - unsupported patch keys
            - empty patch payload
          recovery_steps:
            - Remove unsupported fields.
            - Retry with one or more editable normalized values.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_TRADE_PATCH_REJECTED:
          suggested_action: Review the source message and recreate the trade candidate if needed.
          common_causes:
            - candidate already rejected
          recovery_steps:
            - Stop editing the rejected candidate.
            - Create a fresh trade candidate from a new message if appropriate.
          retry_safe: true

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        return None
    if not isinstance(trade_id, int) or trade_id <= 0:
        return None
    if not isinstance(patch_payload, dict):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_PATCH_INVALID")

    normalized_patch_payload = {
        key: value
        for key, value in patch_payload.items()
        if key in DCX_TRADE_EDITABLE_NORMALIZED_FIELDS
    }
    if not normalized_patch_payload or len(normalized_patch_payload) != len(patch_payload):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_PATCH_INVALID")

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
            if "normalized_material_key" in normalized_patch_payload:
                _raise_if_trade_material_key_is_not_active(
                    cursor=cursor,
                    material_key=_normalize_trade_patch_value(
                        "normalized_material_key",
                        normalized_patch_payload["normalized_material_key"],
                    ),
                )
            recompute_source = dict(current_trade_version_row)
            changed_field_names: list[str] = []
            for field_name, field_value in normalized_patch_payload.items():
                normalized_value = _normalize_trade_patch_value(field_name, field_value)
                if recompute_source.get(field_name) == normalized_value:
                    continue
                recompute_source[field_name] = normalized_value
                changed_field_names.append(field_name)

            if "normalized_material_name" in changed_field_names and "normalized_material_key" not in normalized_patch_payload:
                inferred_material_key = read_dcx_trade_interest_material_key(
                    recompute_source.get("normalized_material_name")
                ) or ""
                if recompute_source.get("normalized_material_key") != inferred_material_key:
                    recompute_source["normalized_material_key"] = inferred_material_key
                    changed_field_names.append("normalized_material_key")

            if not changed_field_names:
                return {"trade_id": trade_id, "was_noop": True}

            recomputed_missing_fields = _read_trade_missing_required_fields(recompute_source)
            requested_confirmation_status = recompute_source.get("trade_confirmation_status")
            next_confirmation_status = (
                requested_confirmation_status
                if requested_confirmation_status in DCX_TRADE_ALLOWED_CONFIRMATION_STATUSES
                else (
                    "pending_confirmation"
                    if not recomputed_missing_fields
                    else "needs_more_detail"
                )
            )
            requested_trade_status = recompute_source.get("trade_status")
            next_trade_status = (
                requested_trade_status
                if requested_trade_status in DCX_TRADE_ALLOWED_TRADE_STATUSES
                else current_trade_version_row.get("trade_status", "draft")
            )
            next_trade_version_values = {
                **current_trade_version_row,
                **{
                    field_name: recompute_source.get(field_name)
                    for field_name in DCX_TRADE_EDITABLE_NORMALIZED_FIELDS
                    if field_name not in {"trade_confirmation_status", "trade_status"}
                },
                "missing_required_fields_json": recomputed_missing_fields,
                "trade_confirmation_status": next_confirmation_status,
                "trade_status": next_trade_status,
                "trade_metadata_json": {
                    **(current_trade_version_row.get("trade_metadata_json") or {}),
                    "user_updated_at_ts_ms": now_ts_ms,
                    "user_updated_by_user_id": authenticated_user_id,
                    "user_updated_fields": sorted(changed_field_names),
                },
            }
            create_new_dcx_trade_version_and_promote_current_trade(
                cursor=cursor,
                trade_identity_row=trade_identity_row,
                current_trade_version_row=current_trade_version_row,
                next_trade_version_values=next_trade_version_values,
                version_source_type="user_edit",
                now_ts_ms=now_ts_ms,
            )

    return {"trade_id": trade_id, "was_noop": False}


def _normalize_trade_patch_value(field_name: str, field_value: Any) -> Any:
    if field_name in {"normalized_quantity_value", "normalized_price_value", "normalized_total_price_value"}:
        if field_value in {None, ""}:
            return None
        return float(field_value)

    if field_value is None:
        return ""
    if isinstance(field_value, str):
        normalized_text = field_value.strip()
        if normalized_text.upper() == "NOT SPECIFIED":
            return ""
        if field_name == "trade_confirmation_status":
            if normalized_text not in DCX_TRADE_ALLOWED_CONFIRMATION_STATUSES:
                raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_PATCH_INVALID")
            return normalized_text
        if field_name == "trade_status":
            if normalized_text not in DCX_TRADE_ALLOWED_TRADE_STATUSES:
                raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_PATCH_INVALID")
            return normalized_text
        if field_name == "normalized_material_key":
            return normalized_text.lower()
        return normalized_text
    return field_value


def _raise_if_trade_material_key_is_not_active(cursor: Any, material_key: str) -> None:
    if material_key == "":
        return
    cursor.execute(
        """
        SELECT 1
        FROM stephen_dcx_trade_interest_material_options
        WHERE material_key = %s
          AND is_active = TRUE
        LIMIT 1
        """,
        (material_key,),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_TRADE_PATCH_INVALID")


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
