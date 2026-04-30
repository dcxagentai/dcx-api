"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading one Topic detail payload.
It exists so Slice 1 can render the first AI-seeded topic detail view.
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
from messages.read_authenticated_dcx_user_market_topic_detail import (
    read_authenticated_dcx_user_market_topic_detail,
)

dcx_api_routes_users_me_market_topic_detail_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_market_topic_detail_router.get("/me/market-topics/{market_topic_id}", response_model=None)
def get_authenticated_dcx_user_market_topic_detail(
    request: Request,
    market_topic_id: int,
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
        market_topic_detail = read_authenticated_dcx_user_market_topic_detail(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=market_topic_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TOPIC_DETAIL_READ_FAILED",
                    "message": "We could not load that topic right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if market_topic_detail is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TOPIC_NOT_FOUND",
                    "message": "That topic does not exist for this account.",
                    "suggested_action": "Refresh the Topics view and retry with one current row.",
                },
            },
        )

    return {
        "ok": True,
        "data": market_topic_detail,
        "context": {
            "surface": "app",
            "view": "market_topic_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
