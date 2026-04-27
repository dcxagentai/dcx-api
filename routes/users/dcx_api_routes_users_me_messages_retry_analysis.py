"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for retrying one stored message analysis pass.
It exists so traders can explicitly retry an LLM analysis failure without resending the underlying message.
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
from messages.process_stored_dcx_contact_message_analysis import (
    process_stored_dcx_contact_message_analysis,
)
from messages.read_authenticated_dcx_user_contact_message_detail import (
    read_authenticated_dcx_user_contact_message_detail,
)

dcx_api_routes_users_me_messages_retry_analysis_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_messages_retry_analysis_router.post(
    "/me/messages/{message_id}/retry-analysis",
    response_model=None,
)
def post_authenticated_dcx_user_message_retry_analysis(
    request: Request,
    message_id: int,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    existing_detail = read_authenticated_dcx_user_contact_message_detail(
        authenticated_user_id=authenticated_user_id,
        message_id=message_id,
    )
    if existing_detail is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MESSAGE_NOT_FOUND",
                    "message": "That message does not exist for this account.",
                    "suggested_action": "Refresh the inbox and retry with one current message row.",
                },
            },
        )

    try:
        retry_result = process_stored_dcx_contact_message_analysis(message_id=message_id)
        message_detail = read_authenticated_dcx_user_contact_message_detail(
            authenticated_user_id=authenticated_user_id,
            message_id=message_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED":
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGE_ANALYSIS_RETRY_FAILED",
                        "message": "We could not retry the LLM call right now.",
                        "suggested_action": "Retry in a moment after the analysis provider is healthy.",
                    },
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MESSAGE_ANALYSIS_RETRY_FAILED",
                    "message": "We could not retry that message right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": message_detail,
        "context": {
            "surface": "app",
            "view": "message_detail",
            "operation": (
                "message_analysis_retried_ready"
                if retry_result["processing_status"] == "ready"
                else "message_analysis_retried_failed"
            ),
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
