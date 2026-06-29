"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading the AI Chats catalog.
It exists so routed market-topic seeds can be surfaced as private AI chats.
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
from messages.create_authenticated_dcx_user_ai_chat import create_authenticated_dcx_user_ai_chat
from messages.read_authenticated_dcx_user_market_topic_detail import (
    read_authenticated_dcx_user_market_topic_detail,
)
from messages.read_authenticated_dcx_user_market_topics_catalog import (
    read_authenticated_dcx_user_market_topics_catalog,
)

dcx_api_routes_users_me_market_topics_catalog_router = APIRouter(tags=["ai"])


class DcxUsersMeAiChatCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_text: str
    language_code: str | None = "en"


@dcx_api_routes_users_me_market_topics_catalog_router.get("/ai/chats", response_model=None)
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
                    "message": "We could not load AI Chats right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": catalog_payload,
        "context": {
            "surface": "app",
            "view": "ai_chats_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_users_me_market_topics_catalog_router.post("/ai/chats", response_model=None)
def post_authenticated_dcx_user_ai_chat(
    request: Request,
    ai_chat_request: DcxUsersMeAiChatCreateRequest,
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
        creation_result = create_authenticated_dcx_user_ai_chat(
            authenticated_user_id=authenticated_user_id,
            initial_user_turn_text=ai_chat_request.chat_text,
            preferred_language_code=ai_chat_request.language_code or "en",
        )
        market_topic_detail = read_authenticated_dcx_user_market_topic_detail(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=creation_result["market_topic_id"],
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code in {
            "API_DCX_AI_CHAT_EMPTY",
            "API_DCX_AI_CHAT_CONTEXT_LIMIT_REACHED",
            "API_DCX_AI_CHAT_PROHIBITED",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "We could not start that AI chat.",
                        "suggested_action": "Keep the first message short and avoid prohibited content.",
                    },
                },
            )
        if error_code == "API_DCX_AI_CHAT_USER_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
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
                    "code": "API_DCX_AI_CHAT_CREATE_FAILED",
                    "message": "We could not start that AI chat right now.",
                    "suggested_action": "Retry in a moment after the backend and AI provider are healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": market_topic_detail,
        "context": {
            "surface": "app",
            "view": "ai_chat_detail",
            "operation": "ai_chat_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
