"""
CONTEXT:
This file owns the shared DCX app HTTP boundary for verifying one WhatsApp phone-link challenge
from a secure app-domain link.
It exists so a WhatsApp button click can complete phone verification using the opaque token in the
browser fragment without requiring an authenticated session cookie first.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from users.account_phone.verify_dcx_whatsapp_phone_link_from_challenge_token import (
    verify_dcx_whatsapp_phone_link_from_challenge_token,
)

dcx_api_routes_users_account_phone_verify_whatsapp_link_router = APIRouter(
    prefix="/users",
    tags=["users"],
)


class DcxUsersAccountPhoneVerifyWhatsappLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    whatsapp_phone_link_token: str


@dcx_api_routes_users_account_phone_verify_whatsapp_link_router.post(
    "/account-phone/verify-whatsapp-link",
    response_model=None,
)
def post_dcx_users_account_phone_verify_whatsapp_link(
    request: Request,
    account_phone_verify_whatsapp_link_request: DcxUsersAccountPhoneVerifyWhatsappLinkRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    try:
        verification_result = verify_dcx_whatsapp_phone_link_from_challenge_token(
            raw_phone_link_token=account_phone_verify_whatsapp_link_request.whatsapp_phone_link_token,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code == "API_DCX_WHATSAPP_PHONE_LINK_TOKEN_INVALID":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "That WhatsApp verification link is not valid.",
                        "suggested_action": "Open the newest WhatsApp verification message or request another link.",
                    },
                },
            )

        if error_code == "API_DCX_WHATSAPP_PHONE_LINK_TOKEN_EXPIRED":
            return JSONResponse(
                status_code=410,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "That WhatsApp verification link has expired.",
                        "suggested_action": "Request a fresh WhatsApp verification link from the account page.",
                    },
                },
            )

        if error_code == "API_DCX_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "This phone number can't be added to this account.",
                        "suggested_action": "Try a different phone number, or contact support if you think this is a mistake.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_WHATSAPP_PHONE_LINK_VERIFY_FAILED",
                    "message": "We could not verify the WhatsApp phone link just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": {
            "status": verification_result["status"],
            "phone_e164": verification_result["phone_e164"],
            "verified_at_ts_ms": verification_result["verified_at_ts_ms"],
        },
        "context": {
            "surface": "shared_auth",
            "view": "whatsapp_phone_link_verify",
        },
    }
