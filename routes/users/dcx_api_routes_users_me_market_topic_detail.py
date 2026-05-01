"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading one Topic detail payload.
It exists so Slice 1 can render the first AI-seeded topic detail view.
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
from messages.append_authenticated_dcx_user_market_topic_ai_chat_turn import (
    append_authenticated_dcx_user_market_topic_ai_chat_turn,
)
from messages.read_authenticated_dcx_user_market_topic_detail import (
    read_authenticated_dcx_user_market_topic_detail,
)

dcx_api_routes_users_me_market_topic_detail_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersMeMarketTopicAiTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_text: str
    language_code: str | None = "en"


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


@dcx_api_routes_users_me_market_topic_detail_router.post(
    "/me/market-topics/{market_topic_id}/turns",
    response_model=None,
)
def post_authenticated_dcx_user_market_topic_ai_turn(
    request: Request,
    market_topic_id: int,
    turn_request: DcxUsersMeMarketTopicAiTurnRequest,
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
        append_result = append_authenticated_dcx_user_market_topic_ai_chat_turn(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=market_topic_id,
            user_turn_text=turn_request.turn_text,
            preferred_language_code=turn_request.language_code or "en",
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_DCX_MARKET_TOPIC_CHAT_EMPTY":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MARKET_TOPIC_CHAT_EMPTY",
                        "message": "That chat message is empty.",
                        "suggested_action": "Add a market-topic question or instruction and retry.",
                    },
                },
            )
        if error_code == "API_DCX_MARKET_TOPIC_CHAT_CONTEXT_LIMIT_REACHED":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MARKET_TOPIC_CHAT_CONTEXT_LIMIT_REACHED",
                        "message": "This MVP topic chat has reached its context limit.",
                        "suggested_action": "Start a new topic with the latest question.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_TOPIC_CHAT_FAILED",
                    "message": "We could not continue that topic chat right now.",
                    "suggested_action": "Retry in a moment after the backend and Gemini provider are healthy.",
                },
            },
        )

    if append_result is None:
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

    market_topic_detail = read_authenticated_dcx_user_market_topic_detail(
        authenticated_user_id=authenticated_user_id,
        market_topic_id=market_topic_id,
    )

    return {
        "ok": True,
        "data": market_topic_detail,
        "context": {
            "surface": "app",
            "view": "market_topic_detail",
            "operation": "market_topic_ai_turn_added",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
