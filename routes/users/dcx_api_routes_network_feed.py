"""
CONTEXT:
This file owns authenticated app routes for the first DCX Network feed.
The feed is app-private, short-form, and intentionally one reply level deep.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
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
    read_authenticated_dcx_network_feed_post,
    read_authenticated_dcx_network_feed_post_attachment_stream,
    set_authenticated_dcx_network_feed_post_bookmark,
    set_authenticated_dcx_network_feed_post_like,
    set_authenticated_dcx_network_feed_post_repost,
)

dcx_api_routes_network_feed_router = APIRouter(prefix="/network", tags=["network"])


class DcxNetworkFeedReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply_text: str
    language_code: str | None = "en"


class DcxNetworkFeedLikeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_like: bool


class DcxNetworkFeedRepostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_repost: bool


class DcxNetworkFeedBookmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_bookmark: bool


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


@dcx_api_routes_network_feed_router.get("/feed/posts/{feed_post_id}", response_model=None)
def get_authenticated_dcx_network_feed_post(
    request: Request,
    feed_post_id: int,
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
        feed_post_payload = read_authenticated_dcx_network_feed_post(
            authenticated_user_id=authenticated_user_id,
            feed_post_id=feed_post_id,
        )
    except RuntimeError as runtime_error:
        if str(runtime_error) == "API_DCX_NETWORK_FEED_POST_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_DCX_NETWORK_FEED_POST_NOT_FOUND",
                        "message": "That network post is not available.",
                        "suggested_action": "Refresh the feed and retry with a current post.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_FEED_READ_FAILED",
                    "message": "We could not load that network post right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": feed_post_payload,
        "context": {
            "surface": "app",
            "view": "network_feed_post",
            "operation": "network_feed_post_read",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_network_feed_router.post("/feed/posts", response_model=None)
async def post_authenticated_dcx_network_feed_post(
    request: Request,
    post_text: str = Form(""),
    language_code: str = Form("en"),
    post_file: UploadFile | None = File(None),
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    attachment_input = None
    if post_file is not None and post_file.filename:
        content_type = (post_file.content_type or "").strip().lower()
        if not (content_type.startswith("image/") or content_type.startswith("audio/")):
            return _read_network_feed_mutation_error_response("API_DCX_NETWORK_FEED_ATTACHMENT_INVALID")
        attachment_input = {
            "original_filename": post_file.filename,
            "content_type": content_type,
            "file_bytes": await post_file.read(),
        }

    try:
        feed_post_payload = create_authenticated_dcx_network_feed_post(
            authenticated_user_id=authenticated_user_id,
            post_text=post_text,
            language_code=language_code or "en",
            attachment_input=attachment_input,
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


@dcx_api_routes_network_feed_router.post("/feed/posts/{feed_post_id}/like", response_model=None)
def post_authenticated_dcx_network_feed_like(
    request: Request,
    feed_post_id: int,
    feed_like_request: DcxNetworkFeedLikeRequest,
):
    return _post_authenticated_dcx_network_feed_action(
        request=request,
        feed_post_id=feed_post_id,
        action_label="network_feed_like_set",
        action_callable=lambda authenticated_user_id: set_authenticated_dcx_network_feed_post_like(
            authenticated_user_id=authenticated_user_id,
            feed_post_id=feed_post_id,
            should_like=feed_like_request.should_like,
        ),
    )


@dcx_api_routes_network_feed_router.post("/feed/posts/{feed_post_id}/repost", response_model=None)
def post_authenticated_dcx_network_feed_repost(
    request: Request,
    feed_post_id: int,
    feed_repost_request: DcxNetworkFeedRepostRequest,
):
    return _post_authenticated_dcx_network_feed_action(
        request=request,
        feed_post_id=feed_post_id,
        action_label="network_feed_repost_set",
        action_callable=lambda authenticated_user_id: set_authenticated_dcx_network_feed_post_repost(
            authenticated_user_id=authenticated_user_id,
            feed_post_id=feed_post_id,
            should_repost=feed_repost_request.should_repost,
        ),
    )


@dcx_api_routes_network_feed_router.post("/feed/posts/{feed_post_id}/bookmark", response_model=None)
def post_authenticated_dcx_network_feed_bookmark(
    request: Request,
    feed_post_id: int,
    feed_bookmark_request: DcxNetworkFeedBookmarkRequest,
):
    return _post_authenticated_dcx_network_feed_action(
        request=request,
        feed_post_id=feed_post_id,
        action_label="network_feed_bookmark_set",
        action_callable=lambda authenticated_user_id: set_authenticated_dcx_network_feed_post_bookmark(
            authenticated_user_id=authenticated_user_id,
            feed_post_id=feed_post_id,
            should_bookmark=feed_bookmark_request.should_bookmark,
        ),
    )


@dcx_api_routes_network_feed_router.get("/feed/posts/{feed_post_id}/attachment/file", response_model=None)
def get_authenticated_dcx_network_feed_post_attachment_file(
    request: Request,
    feed_post_id: int,
):
    authenticated_user_id, _identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        attachment_stream = read_authenticated_dcx_network_feed_post_attachment_stream(
            authenticated_user_id=authenticated_user_id,
            feed_post_id=feed_post_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_FEED_ATTACHMENT_READ_FAILED",
                    "message": "We could not load that network attachment right now.",
                    "suggested_action": "Retry in a moment after storage is healthy.",
                },
            },
        )

    if attachment_stream is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_FEED_ATTACHMENT_NOT_FOUND",
                    "message": "That network attachment is not available.",
                    "suggested_action": "Refresh the feed and retry with a current post.",
                },
            },
        )

    return Response(
        content=attachment_stream["content_bytes"],
        media_type=attachment_stream["content_type"],
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{attachment_stream["original_filename"]}"',
            "Content-Length": str(len(attachment_stream["content_bytes"])),
            "X-Content-Type-Options": "nosniff",
        },
    )


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


def _post_authenticated_dcx_network_feed_action(
    request: Request,
    feed_post_id: int,
    action_label: str,
    action_callable,
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
        feed_post_payload = action_callable(authenticated_user_id)
    except RuntimeError as runtime_error:
        return _read_network_feed_mutation_error_response(str(runtime_error))

    return {
        "ok": True,
        "data": feed_post_payload,
        "context": {
            "surface": "app",
            "view": "network_feed_post",
            "operation": action_label,
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


def _read_network_feed_mutation_error_response(error_code: str) -> JSONResponse:
    if error_code == "API_DCX_NETWORK_FEED_ACTION_FAILED":
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not update that network action right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if error_code in {
        "API_DCX_NETWORK_FEED_POST_INVALID",
        "API_DCX_NETWORK_FEED_REPLY_INVALID",
        "API_DCX_NETWORK_FEED_POST_NOT_FOUND",
        "API_DCX_NETWORK_NICKNAME_REQUIRED",
        "API_DCX_NETWORK_CONTENT_PROHIBITED",
        "API_DCX_NETWORK_FEED_ATTACHMENT_INVALID",
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
