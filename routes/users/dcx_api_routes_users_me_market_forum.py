"""
CONTEXT:
This file owns authenticated app routes for Market > Forum.
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
from messages.append_authenticated_dcx_forum_comment import append_authenticated_dcx_forum_comment
from messages.read_authenticated_dcx_market_forum_catalog import (
    read_authenticated_dcx_market_forum_catalog,
)
from messages.read_authenticated_dcx_market_forum_post_detail import (
    read_authenticated_dcx_market_forum_post_detail,
)

dcx_api_routes_users_me_market_forum_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersMeForumCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment_text: str
    language_code: str | None = "en"


@dcx_api_routes_users_me_market_forum_router.get("/me/market/forum", response_model=None)
def get_authenticated_dcx_market_forum_catalog(request: Request):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        catalog_payload = read_authenticated_dcx_market_forum_catalog(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_FORUM_READ_FAILED",
                    "message": "We could not load Market forum right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": catalog_payload,
        "context": {
            "surface": "app",
            "view": "market_forum_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_users_me_market_forum_router.get("/me/market/forum/{forum_post_id}", response_model=None)
def get_authenticated_dcx_market_forum_post_detail(request: Request, forum_post_id: int):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        detail_payload = read_authenticated_dcx_market_forum_post_detail(
            authenticated_user_id=authenticated_user_id,
            forum_post_id=forum_post_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_FORUM_POST_READ_FAILED",
                    "message": "We could not load that forum post right now.",
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
                    "code": "API_USERS_ME_MARKET_FORUM_POST_NOT_FOUND",
                    "message": "That forum post is not available.",
                    "suggested_action": "Refresh Market forum and retry with a current row.",
                },
            },
        )

    return {
        "ok": True,
        "data": detail_payload,
        "context": {
            "surface": "app",
            "view": "market_forum_post_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_users_me_market_forum_router.post(
    "/me/market/forum/{forum_post_id}/comments",
    response_model=None,
)
def post_authenticated_dcx_market_forum_comment(
    request: Request,
    forum_post_id: int,
    comment_request: DcxUsersMeForumCommentRequest,
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
        comment_payload = append_authenticated_dcx_forum_comment(
            authenticated_user_id=authenticated_user_id,
            forum_post_id=forum_post_id,
            comment_text=comment_request.comment_text,
            language_code=comment_request.language_code or "en",
        )
    except RuntimeError as runtime_error:
        if str(runtime_error) == "API_DCX_FORUM_COMMENT_EMPTY":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MARKET_FORUM_COMMENT_EMPTY",
                        "message": "That forum comment is empty.",
                        "suggested_action": "Add a comment and retry.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_FORUM_COMMENT_FAILED",
                    "message": "We could not save that forum comment right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if comment_payload is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MARKET_FORUM_POST_NOT_FOUND",
                    "message": "That forum post is not open for comments.",
                    "suggested_action": "Refresh Market forum and retry with a current open post.",
                },
            },
        )

    detail_payload = read_authenticated_dcx_market_forum_post_detail(
        authenticated_user_id=authenticated_user_id,
        forum_post_id=forum_post_id,
    )

    return {
        "ok": True,
        "data": detail_payload,
        "context": {
            "surface": "app",
            "view": "market_forum_post_detail",
            "operation": "forum_comment_added",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
