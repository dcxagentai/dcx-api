"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for confirming one trade candidate.
It exists so the Trades surface can move a projected trade into the first real open state.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from messages.confirm_authenticated_dcx_user_trade_candidate import (
    confirm_authenticated_dcx_user_trade_candidate,
)
from messages.read_authenticated_dcx_user_trade_detail import (
    read_authenticated_dcx_user_trade_detail,
)

dcx_api_routes_users_me_trade_confirm_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_trade_confirm_router.post("/me/trades/{trade_id}/confirm", response_model=None)
def post_authenticated_dcx_user_trade_confirm(
    request: Request,
    trade_id: int,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        result = confirm_authenticated_dcx_user_trade_candidate(
            authenticated_user_id=authenticated_user_id,
            trade_id=trade_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_AUTHENTICATED_DCX_USER_TRADE_CONFIRMATION_FIELDS_MISSING":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_TRADE_CONFIRMATION_FIELDS_MISSING",
                        "message": "This trade still needs more detail before it can be confirmed.",
                        "suggested_action": "Fill the missing fields, then confirm again.",
                    },
                },
            )
        if error_code == "API_AUTHENTICATED_DCX_USER_TRADE_CONFIRMATION_REJECTED":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_TRADE_CONFIRMATION_REJECTED",
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
                    "code": "API_USERS_ME_TRADE_CONFIRMATION_FAILED",
                    "message": "We could not confirm that trade right now.",
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
            "operation": "trade_confirmed",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
