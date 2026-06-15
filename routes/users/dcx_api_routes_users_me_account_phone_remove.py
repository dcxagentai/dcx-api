"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for removing one unused phone contact method.
It exists so phone cleanup goes through the same origin/auth checks and account-summary refresh pattern
as the other account-phone actions.
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
from users.account.read_authenticated_dcx_user_account_summary import (
    read_authenticated_dcx_user_account_summary_capability,
)
from users.account_phone.remove_authenticated_dcx_user_phone_contact_method import (
    remove_authenticated_dcx_user_phone_contact_method,
)

dcx_api_routes_users_me_account_phone_remove_router = APIRouter(
    prefix="/users",
    tags=["users"],
)


class DcxUsersMeAccountPhoneRemoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_contact_method_id: int


@dcx_api_routes_users_me_account_phone_remove_router.post(
    "/me/account-phone/remove",
    response_model=None,
)
def post_authenticated_dcx_user_account_phone_remove(
    request: Request,
    account_phone_remove_request: DcxUsersMeAccountPhoneRemoveRequest,
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
        remove_result = remove_authenticated_dcx_user_phone_contact_method(
            authenticated_user_id=authenticated_user_id,
            phone_contact_method_id=account_phone_remove_request.phone_contact_method_id,
        )
        refreshed_account_summary = read_authenticated_dcx_user_account_summary_capability(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code == "API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_REMOVE_ACCOUNT_NOT_FOUND",
                        "message": "We could not find that DCX user account.",
                        "suggested_action": "Sign in again and retry after confirming the account still exists.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_REMOVE_CONTACT_NOT_FOUND",
                        "message": "That phone number can't be removed from this account.",
                        "suggested_action": "Refresh the account page and retry with one current phone number from this account.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_REMOVE_BLOCKED_PRIMARY":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_REMOVE_BLOCKED_PRIMARY",
                        "message": "The primary phone number can't be removed.",
                        "suggested_action": "Set another verified phone as primary before removing this one.",
                    },
                },
            )

        if error_code.startswith("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_REMOVE_BLOCKED"):
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_REMOVE_BLOCKED_BY_HISTORY",
                        "message": "That phone number is attached to account history and can't be removed.",
                        "suggested_action": "Keep the number on the account, or contact support if it should be archived.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_ACCOUNT_PHONE_REMOVE_FAILED",
                    "message": "We could not remove the phone number right now.",
                    "suggested_action": "Please try again in a moment.",
                },
            },
        )

    return {
        "ok": True,
        "data": refreshed_account_summary,
        "context": {
            "surface": "app",
            "view": "account_summary",
            "operation": f"account_phone_{remove_result['status']}",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
