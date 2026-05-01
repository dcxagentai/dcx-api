"""
CONTEXT:
This file owns authenticated app routes for Market > Deals.
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
from messages.read_authenticated_dcx_market_trade_detail import (
    read_authenticated_dcx_market_trade_detail,
)
from messages.read_authenticated_dcx_market_trades_catalog import (
    read_authenticated_dcx_market_trades_catalog,
)
from messages.start_authenticated_dcx_trade_thread_from_market_trade import (
    start_authenticated_dcx_trade_thread_from_market_trade,
)

dcx_api_routes_users_me_market_trades_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_market_trades_router.get("/me/market/trades", response_model=None)
def get_authenticated_dcx_market_trades_catalog(request: Request):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        catalog_payload = read_authenticated_dcx_market_trades_catalog(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TRADES_READ_FAILED",
                    "message": "We could not load Market deals right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": catalog_payload,
        "context": {
            "surface": "app",
            "view": "market_trades_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_users_me_market_trades_router.get("/me/market/trades/{trade_publication_id}", response_model=None)
def get_authenticated_dcx_market_trade_detail(request: Request, trade_publication_id: int):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        detail_payload = read_authenticated_dcx_market_trade_detail(
            authenticated_user_id=authenticated_user_id,
            trade_publication_id=trade_publication_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TRADE_READ_FAILED",
                    "message": "We could not load that Market deal right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if detail_payload is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TRADE_NOT_FOUND",
                    "message": "That Market deal is not available.",
                    "suggested_action": "Refresh Market deals and retry with a current row.",
                },
            },
        )

    return {
        "ok": True,
        "data": detail_payload,
        "context": {
            "surface": "app",
            "view": "market_trade_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_users_me_market_trades_router.post(
    "/me/market/trades/{trade_publication_id}/threads",
    response_model=None,
)
def post_authenticated_dcx_market_trade_thread(request: Request, trade_publication_id: int):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        thread_payload = start_authenticated_dcx_trade_thread_from_market_trade(
            authenticated_user_id=authenticated_user_id,
            trade_publication_id=trade_publication_id,
        )
    except RuntimeError as runtime_error:
        if str(runtime_error) == "API_DCX_TRADE_THREAD_SELF_NOT_ALLOWED":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MARKET_TRADE_THREAD_SELF_NOT_ALLOWED",
                        "message": "This is your own trade.",
                        "suggested_action": "Use the private Trades view to edit it.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TRADE_THREAD_START_FAILED",
                    "message": "We could not start that trade conversation right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if thread_payload is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TRADE_NOT_FOUND",
                    "message": "That Market deal is not available.",
                    "suggested_action": "Refresh Market deals and retry with a current row.",
                },
            },
        )

    return {
        "ok": True,
        "data": thread_payload,
        "context": {
            "surface": "app",
            "view": "trade_thread",
            "operation": "trade_thread_started",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
