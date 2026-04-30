"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading the Topics catalog.
It exists so Slice 1 can surface routed market-topic seeds in a dedicated app view.
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
from messages.read_authenticated_dcx_user_market_topics_catalog import (
    read_authenticated_dcx_user_market_topics_catalog,
)

dcx_api_routes_users_me_market_topics_catalog_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_market_topics_catalog_router.get("/me/market-topics", response_model=None)
def get_authenticated_dcx_user_market_topics_catalog(request: Request):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        catalog_payload = read_authenticated_dcx_user_market_topics_catalog(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_AUTHENTICATED_DCX_USER_MARKET_TOPICS_USER_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MARKET_TOPICS_USER_NOT_FOUND",
                        "message": "We could not find that DCX user account.",
                        "suggested_action": "Sign in again and retry after confirming the account still exists.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TOPICS_CATALOG_READ_FAILED",
                    "message": "We could not load the Topics view right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": catalog_payload,
        "context": {
            "surface": "app",
            "view": "market_topics_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
