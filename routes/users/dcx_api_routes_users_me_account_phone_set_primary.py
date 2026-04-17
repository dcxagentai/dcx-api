"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for setting one verified phone contact method
as the user's primary phone.
It exists so primary-phone changes happen through an explicit user action instead of as an implicit
side effect of phone verification.
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
from users.account_phone.set_authenticated_dcx_user_primary_phone_contact_method import (
    set_authenticated_dcx_user_primary_phone_contact_method,
)

dcx_api_routes_users_me_account_phone_set_primary_router = APIRouter(
    prefix="/users",
    tags=["users"],
)


class DcxUsersMeAccountPhoneSetPrimaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_contact_method_id: int


@dcx_api_routes_users_me_account_phone_set_primary_router.post(
    "/me/account-phone/set-primary",
    response_model=None,
)
def post_authenticated_dcx_user_account_phone_set_primary(
    request: Request,
    account_phone_set_primary_request: DcxUsersMeAccountPhoneSetPrimaryRequest,
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
        primary_phone_result = set_authenticated_dcx_user_primary_phone_contact_method(
            authenticated_user_id=authenticated_user_id,
            phone_contact_method_id=account_phone_set_primary_request.phone_contact_method_id,
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
                        "code": "API_USERS_ME_ACCOUNT_PHONE_PRIMARY_ACCOUNT_NOT_FOUND",
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
                        "code": "API_USERS_ME_ACCOUNT_PHONE_PRIMARY_CONTACT_NOT_FOUND",
                        "message": "That phone number can't be set as primary for this account.",
                        "suggested_action": "Refresh the account page and retry with one current phone number from this account.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_VERIFIED":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_PRIMARY_CONTACT_NOT_VERIFIED",
                        "message": "Only verified phone numbers can become primary.",
                        "suggested_action": "Verify the phone number first, then retry.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_ACCOUNT_PHONE_PRIMARY_SET_FAILED",
                    "message": "We could not update the primary phone right now.",
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
            "operation": f"account_phone_{primary_phone_result['status']}",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
