"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading one message detail payload.
It exists so message creation and future detail views can rely on one narrow route contract.
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
from messages.read_authenticated_dcx_user_contact_message_detail import (
    read_authenticated_dcx_user_contact_message_detail,
)

dcx_api_routes_users_me_messages_detail_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_messages_detail_router.get("/me/messages/{message_id}", response_model=None)
def get_authenticated_dcx_user_message_detail(
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

    try:
        message_detail = read_authenticated_dcx_user_contact_message_detail(
            authenticated_user_id=authenticated_user_id,
            message_id=message_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MESSAGE_DETAIL_READ_FAILED",
                    "message": "We could not load that message right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if message_detail is None:
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

    return {
        "ok": True,
        "data": message_detail,
        "context": {
            "surface": "app",
            "view": "message_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
