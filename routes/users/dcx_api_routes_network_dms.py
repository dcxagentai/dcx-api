"""
CONTEXT:
This file owns authenticated app routes for DCX Network DMs.
DMs are deliberately separate from structured Trade Chats and live under `/network/dms`.
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
    append_authenticated_dcx_network_dm_message,
    read_authenticated_dcx_network_dm_thread,
    read_authenticated_dcx_network_dm_threads,
    start_authenticated_dcx_network_dm_thread,
)

dcx_api_routes_network_dms_router = APIRouter(prefix="/network", tags=["network"])


class DcxNetworkDmStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_nickname: str


class DcxNetworkDmMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_text: str
    language_code: str | None = "en"


@dcx_api_routes_network_dms_router.get("/dms", response_model=None)
def get_authenticated_dcx_network_dm_threads(request: Request):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        dm_threads_payload = read_authenticated_dcx_network_dm_threads(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_DMS_READ_FAILED",
                    "message": "We could not load DMs right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": dm_threads_payload,
        "context": {
            "surface": "app",
            "view": "network_dms",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_network_dms_router.post("/dms/start", response_model=None)
def post_authenticated_dcx_network_dm_start(
    request: Request,
    dm_start_request: DcxNetworkDmStartRequest,
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
        dm_thread_payload = start_authenticated_dcx_network_dm_thread(
            authenticated_user_id=authenticated_user_id,
            network_nickname=dm_start_request.network_nickname,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code in {
            "API_DCX_NETWORK_PROFILE_NOT_FOUND",
            "API_DCX_NETWORK_DM_NOT_ALLOWED",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "We could not start that DM.",
                        "suggested_action": "Refresh the profile and check whether that trader accepts DMs.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_DM_START_FAILED",
                    "message": "We could not start that DM right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": dm_thread_payload,
        "context": {
            "surface": "app",
            "view": "network_dm_thread",
            "operation": "network_dm_started",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_network_dms_router.get("/dms/{dm_thread_id}", response_model=None)
def get_authenticated_dcx_network_dm_thread(request: Request, dm_thread_id: int):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        dm_thread_payload = read_authenticated_dcx_network_dm_thread(
            authenticated_user_id=authenticated_user_id,
            dm_thread_id=dm_thread_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_DM_READ_FAILED",
                    "message": "We could not load that DM right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if dm_thread_payload is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_DM_NOT_FOUND",
                    "message": "That DM is not available.",
                    "suggested_action": "Refresh DMs and retry with a current thread.",
                },
            },
        )

    return {
        "ok": True,
        "data": dm_thread_payload,
        "context": {
            "surface": "app",
            "view": "network_dm_thread",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_network_dms_router.post("/dms/{dm_thread_id}/messages", response_model=None)
def post_authenticated_dcx_network_dm_message(
    request: Request,
    dm_thread_id: int,
    dm_message_request: DcxNetworkDmMessageRequest,
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
        dm_thread_payload = append_authenticated_dcx_network_dm_message(
            authenticated_user_id=authenticated_user_id,
            dm_thread_id=dm_thread_id,
            message_text=dm_message_request.message_text,
            language_code=dm_message_request.language_code or "en",
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code in {
            "API_DCX_NETWORK_DM_NOT_FOUND",
            "API_DCX_NETWORK_DM_MESSAGE_INVALID",
            "API_DCX_NETWORK_CONTENT_PROHIBITED",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "We could not save that DM message.",
                        "suggested_action": "Refresh the thread, keep the message short, and avoid prohibited content.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_DM_MESSAGE_CREATE_FAILED",
                    "message": "We could not save that DM message right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": dm_thread_payload,
        "context": {
            "surface": "app",
            "view": "network_dm_thread",
            "operation": "network_dm_message_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
