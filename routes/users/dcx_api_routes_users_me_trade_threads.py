"""
CONTEXT:
This file owns authenticated app routes for private trader-to-trader Trade Chats.
"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from messages.append_authenticated_dcx_trade_thread_message import (
    append_authenticated_dcx_trade_thread_message,
)
from messages.read_authenticated_dcx_trade_thread_detail import (
    read_authenticated_dcx_trade_thread_detail,
)
from messages.read_authenticated_dcx_trade_threads_catalog import (
    read_authenticated_dcx_trade_threads_catalog,
)

dcx_api_routes_users_me_trade_threads_router = APIRouter(prefix="/users", tags=["users"])


class DcxAuthenticatedUserTradeThreadMessageAppendPayload(BaseModel):
    message_text: str
    language_code: str = "en"


@dcx_api_routes_users_me_trade_threads_router.get("/me/trade-threads", response_model=None)
def get_authenticated_dcx_trade_threads_catalog(request: Request):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        catalog_payload = read_authenticated_dcx_trade_threads_catalog(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_TRADE_THREADS_READ_FAILED",
                    "message": "We could not load your trade conversations right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": catalog_payload,
        "context": {
            "surface": "app",
            "view": "trade_threads_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_users_me_trade_threads_router.get("/me/trade-threads/{trade_thread_id}", response_model=None)
def get_authenticated_dcx_trade_thread_detail(request: Request, trade_thread_id: int):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        detail_payload = read_authenticated_dcx_trade_thread_detail(
            authenticated_user_id=authenticated_user_id,
            trade_thread_id=trade_thread_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_TRADE_THREAD_READ_FAILED",
                    "message": "We could not load that trade conversation right now.",
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
                    "code": "API_USERS_ME_TRADE_THREAD_NOT_FOUND",
                    "message": "That trade conversation is not available.",
                    "suggested_action": "Refresh Trade Chats and choose a current conversation.",
                },
            },
        )

    return {
        "ok": True,
        "data": detail_payload,
        "context": {
            "surface": "app",
            "view": "trade_thread_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_users_me_trade_threads_router.post(
    "/me/trade-threads/{trade_thread_id}/messages",
    response_model=None,
)
def post_authenticated_dcx_trade_thread_message(
    request: Request,
    trade_thread_id: int,
    append_payload: DcxAuthenticatedUserTradeThreadMessageAppendPayload,
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
        detail_payload = append_authenticated_dcx_trade_thread_message(
            authenticated_user_id=authenticated_user_id,
            trade_thread_id=trade_thread_id,
            message_text=append_payload.message_text,
            language_code=append_payload.language_code,
        )
    except RuntimeError as runtime_error:
        runtime_error_code = str(runtime_error)
        if runtime_error_code == "API_DCX_TRADE_THREAD_MESSAGE_EMPTY":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_TRADE_THREAD_MESSAGE_EMPTY",
                        "message": "Write a message before sending.",
                        "suggested_action": "Enter a message and try again.",
                    },
                },
            )
        if runtime_error_code == "API_DCX_TRADE_THREAD_NOT_OPEN":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_TRADE_THREAD_NOT_OPEN",
                        "message": "That trade conversation is not open.",
                        "suggested_action": "Choose another open conversation.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_TRADE_THREAD_MESSAGE_APPEND_FAILED",
                    "message": "We could not send that trade chat message right now.",
                    "suggested_action": "Refresh the conversation before retrying.",
                },
            },
        )

    if detail_payload is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_TRADE_THREAD_NOT_FOUND",
                    "message": "That trade conversation is not available.",
                    "suggested_action": "Refresh Trade Chats and choose a current conversation.",
                },
            },
        )

    return {
        "ok": True,
        "data": detail_payload,
        "context": {
            "surface": "app",
            "view": "trade_thread_detail",
            "operation": "message_appended",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
