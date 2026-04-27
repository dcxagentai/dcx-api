"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading the Messages inbox.
It exists so the new `/me/messages` surface can fetch one canonical backend payload instead of
querying the database indirectly through unrelated account routes.
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
from messages.read_authenticated_dcx_user_messages_inbox import (
    read_authenticated_dcx_user_messages_inbox,
)

dcx_api_routes_users_me_messages_inbox_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_messages_inbox_router.get("/me/messages", response_model=None)
def get_authenticated_dcx_user_messages_inbox(
    request: Request,
    message_format_filter: str | None = None,
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
        inbox_payload = read_authenticated_dcx_user_messages_inbox(
            authenticated_user_id=authenticated_user_id,
            message_format_filter=message_format_filter,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_AUTHENTICATED_DCX_USER_MESSAGES_FILTER_INVALID":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGES_FILTER_INVALID",
                        "message": "That messages filter is not supported.",
                        "suggested_action": "Retry with all, text, image, audio, or document.",
                    },
                },
            )
        if error_code == "API_AUTHENTICATED_DCX_USER_MESSAGES_USER_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGES_USER_NOT_FOUND",
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
                    "code": "API_USERS_ME_MESSAGES_INBOX_READ_FAILED",
                    "message": "We could not load the Messages inbox right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": inbox_payload,
        "context": {
            "surface": "app",
            "view": "messages_inbox",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
