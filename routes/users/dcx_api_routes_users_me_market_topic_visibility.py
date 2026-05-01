"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for changing topic visibility.
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
from messages.read_authenticated_dcx_user_market_topic_detail import (
    read_authenticated_dcx_user_market_topic_detail,
)
from messages.set_authenticated_dcx_user_market_topic_visibility import (
    set_authenticated_dcx_user_market_topic_visibility,
)

dcx_api_routes_users_me_market_topic_visibility_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersMeMarketTopicVisibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility_status: str


@dcx_api_routes_users_me_market_topic_visibility_router.patch(
    "/me/market-topics/{market_topic_id}/visibility",
    response_model=None,
)
def patch_authenticated_dcx_user_market_topic_visibility(
    request: Request,
    market_topic_id: int,
    visibility_request: DcxUsersMeMarketTopicVisibilityRequest,
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
        result = set_authenticated_dcx_user_market_topic_visibility(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=market_topic_id,
            visibility_status=visibility_request.visibility_status,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_DCX_MARKET_TOPIC_VISIBILITY_INVALID":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MARKET_TOPIC_VISIBILITY_INVALID",
                        "message": "We could not use that topic visibility.",
                        "suggested_action": "Retry with private, shareable, or public.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TOPIC_VISIBILITY_FAILED",
                    "message": "We could not change that topic visibility right now.",
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
                    "code": "API_USERS_ME_MARKET_TOPIC_NOT_FOUND",
                    "message": "That topic does not exist for this account.",
                    "suggested_action": "Refresh Topics and retry with a current topic.",
                },
            },
        )

    topic_detail = read_authenticated_dcx_user_market_topic_detail(
        authenticated_user_id=authenticated_user_id,
        market_topic_id=market_topic_id,
    )

    return {
        "ok": True,
        "data": topic_detail,
        "context": {
            "surface": "app",
            "view": "market_topic_detail",
            "operation": "market_topic_visibility_updated",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
