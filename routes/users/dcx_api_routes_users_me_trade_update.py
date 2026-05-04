"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for patching one trade candidate's details.
It exists so traders can repair or complete extracted trade fields before confirmation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from messages.read_authenticated_dcx_user_trade_detail import (
    read_authenticated_dcx_user_trade_detail,
)
from messages.update_authenticated_dcx_user_trade_candidate_details import (
    update_authenticated_dcx_user_trade_candidate_details,
)

dcx_api_routes_users_me_trade_update_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersMeTradeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_confirmation_status: str | None = None
    trade_status: str | None = None
    normalized_trade_side: str | None = None
    normalized_material_name: str | None = None
    normalized_material_key: str | None = None
    normalized_quantity_value: float | None = None
    normalized_quantity_unit: str | None = None
    normalized_price_mode: str | None = None
    normalized_price_value: float | None = None
    normalized_price_unit_basis: str | None = None
    normalized_currency_code: str | None = None
    normalized_total_price_value: float | None = None
    normalized_origin_location: str | None = None
    normalized_destination_location: str | None = None
    normalized_shipping_method: str | None = None
    normalized_incoterm_code: str | None = None
    normalized_delivery_window_start_text: str | None = None
    normalized_delivery_window_end_text: str | None = None
    normalized_quality_summary_text: str | None = None
    normalized_payment_terms_summary_text: str | None = None


@dcx_api_routes_users_me_trade_update_router.patch("/me/trades/{trade_id}", response_model=None)
def patch_authenticated_dcx_user_trade_update(
    request: Request,
    trade_id: int,
    trade_update_request: DcxUsersMeTradeUpdateRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    patch_payload = {
        field_name: field_value
        for field_name, field_value in trade_update_request.model_dump().items()
        if field_value is not None
    }

    try:
        result = update_authenticated_dcx_user_trade_candidate_details(
            authenticated_user_id=authenticated_user_id,
            trade_id=trade_id,
            patch_payload=patch_payload,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_AUTHENTICATED_DCX_USER_TRADE_PATCH_INVALID":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_TRADE_PATCH_INVALID",
                        "message": "We could not use that trade update payload.",
                        "suggested_action": "Retry with one or more supported trade fields.",
                    },
                },
            )
        if error_code == "API_AUTHENTICATED_DCX_USER_TRADE_PATCH_REJECTED":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_TRADE_PATCH_REJECTED",
                        "message": "This trade candidate has already been rejected.",
                        "suggested_action": "Use a current active trade candidate instead.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_TRADE_PATCH_FAILED",
                    "message": "We could not update that trade right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if result is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_TRADE_NOT_FOUND",
                    "message": "That trade does not exist for this account.",
                    "suggested_action": "Refresh the Trades view and retry with one current row.",
                },
            },
        )

    trade_detail = read_authenticated_dcx_user_trade_detail(
        authenticated_user_id=authenticated_user_id,
        trade_id=trade_id,
    )

    return {
        "ok": True,
        "data": trade_detail,
        "context": {
            "surface": "app",
            "view": "trade_detail",
            "operation": "trade_updated",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
