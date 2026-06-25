"""
CONTEXT:
This file owns authenticated app routes for the first DCX Network feed.
The feed is app-private, short-form, and intentionally one reply level deep.
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
from network.dcx_network_capabilities import (
    append_authenticated_dcx_network_feed_reply,
    create_authenticated_dcx_network_feed_post,
    read_authenticated_dcx_network_feed,
)

dcx_api_routes_network_feed_router = APIRouter(prefix="/network", tags=["network"])


class DcxNetworkFeedPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_text: str
    language_code: str | None = "en"


class DcxNetworkFeedReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply_text: str
    language_code: str | None = "en"


@dcx_api_routes_network_feed_router.get("/feed", response_model=None)
def get_authenticated_dcx_network_feed(request: Request, scope: str = "following"):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        feed_payload = read_authenticated_dcx_network_feed(
            authenticated_user_id=authenticated_user_id,
            feed_scope=scope,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_FEED_READ_FAILED",
                    "message": "We could not load the DCX Network feed right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": feed_payload,
        "context": {
            "surface": "app",
            "view": "network_feed",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_network_feed_router.post("/feed/posts", response_model=None)
def post_authenticated_dcx_network_feed_post(
    request: Request,
    feed_post_request: DcxNetworkFeedPostRequest,
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
        feed_post_payload = create_authenticated_dcx_network_feed_post(
            authenticated_user_id=authenticated_user_id,
            post_text=feed_post_request.post_text,
            language_code=feed_post_request.language_code or "en",
        )
    except RuntimeError as runtime_error:
        return _read_network_feed_mutation_error_response(str(runtime_error))

    return {
        "ok": True,
        "data": feed_post_payload,
        "context": {
            "surface": "app",
            "view": "network_feed_post",
            "operation": "network_feed_post_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_network_feed_router.post("/feed/posts/{feed_post_id}/replies", response_model=None)
def post_authenticated_dcx_network_feed_reply(
    request: Request,
    feed_post_id: int,
    feed_reply_request: DcxNetworkFeedReplyRequest,
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
        feed_post_payload = append_authenticated_dcx_network_feed_reply(
            authenticated_user_id=authenticated_user_id,
            feed_post_id=feed_post_id,
            reply_text=feed_reply_request.reply_text,
            language_code=feed_reply_request.language_code or "en",
        )
    except RuntimeError as runtime_error:
        return _read_network_feed_mutation_error_response(str(runtime_error))

    return {
        "ok": True,
        "data": feed_post_payload,
        "context": {
            "surface": "app",
            "view": "network_feed_post",
            "operation": "network_feed_reply_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


def _read_network_feed_mutation_error_response(error_code: str) -> JSONResponse:
    if error_code in {
        "API_DCX_NETWORK_FEED_POST_INVALID",
        "API_DCX_NETWORK_FEED_REPLY_INVALID",
        "API_DCX_NETWORK_FEED_POST_NOT_FOUND",
        "API_DCX_NETWORK_NICKNAME_REQUIRED",
        "API_DCX_NETWORK_CONTENT_PROHIBITED",
    }:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not save that network post.",
                    "suggested_action": "Keep the text short, choose a nickname in Settings if needed, and avoid prohibited content.",
                },
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {
                "code": "API_DCX_NETWORK_FEED_SAVE_FAILED",
                "message": "We could not save that network post right now.",
                "suggested_action": "Retry in a moment after the backend is healthy.",
            },
        },
    )
