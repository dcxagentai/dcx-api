"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for rejecting one trade candidate.
It exists so traders can explicitly stop an incorrect extraction from moving into active flow.
"""

from __future__ import annotations

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
from messages.reject_authenticated_dcx_user_trade_candidate import (
    reject_authenticated_dcx_user_trade_candidate,
)

dcx_api_routes_users_me_trade_reject_router = APIRouter(tags=["trades"])


class DcxUsersMeTradeRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rejection_reason_text: str | None = None


@dcx_api_routes_users_me_trade_reject_router.post("/trades/objects/{trade_id}/reject", response_model=None)
def post_authenticated_dcx_user_trade_reject(
    request: Request,
    trade_id: int,
    trade_reject_request: DcxUsersMeTradeRejectRequest,
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
        result = reject_authenticated_dcx_user_trade_candidate(
            authenticated_user_id=authenticated_user_id,
            trade_id=trade_id,
            rejection_reason_text=trade_reject_request.rejection_reason_text or "",
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_TRADE_REJECTION_FAILED",
                    "message": "We could not reject that Trade Object right now.",
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
                    "message": "That Trade Object does not exist for this account.",
                    "suggested_action": "Refresh Trade Objects and retry with one current row.",
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
            "view": "trade_object_detail",
            "operation": "trade_rejected",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
