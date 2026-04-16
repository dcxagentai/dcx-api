"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for verifying one WhatsApp phone-link
OTP from the account page.
It exists so logged-in users can prove phone ownership before the app promotes that number
into the user's confirmed profile.
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
from users.account_phone.verify_authenticated_dcx_user_whatsapp_phone_link_otp import (
    verify_authenticated_dcx_user_whatsapp_phone_link_otp,
)

dcx_api_routes_users_me_account_phone_verify_whatsapp_otp_router = APIRouter(
    prefix="/users",
    tags=["users"],
)


class DcxUsersMeAccountPhoneVerifyWhatsappOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    otp_code: str


@dcx_api_routes_users_me_account_phone_verify_whatsapp_otp_router.post(
    "/me/account-phone/verify-whatsapp-otp",
    response_model=None,
)
def post_authenticated_dcx_user_account_phone_verify_whatsapp_otp(
    request: Request,
    account_phone_verify_whatsapp_otp_request: DcxUsersMeAccountPhoneVerifyWhatsappOtpRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
        - The body contains one six-digit OTP candidate.
      postconditions:
        - Verifies and consumes the active pending WhatsApp phone-link challenge on success.
        - Returns a canonical success wrapper containing the refreshed account-summary payload.
      side_effects:
        - updates stephen_dcx_user_auth_challenges
        - updates stephen_dcx_users
        - inserts or updates stephen_dcx_user_auth_identities
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The app account page needs one explicit verification door before treating the entered phone as confirmed.
      WHEN TO USE it:
        - Use it when the authenticated user pastes the WhatsApp OTP from the received message.
      WHEN NOT TO USE it:
        - Do not use it for public signup OTPs or password reset.
      WHAT CAN GO WRONG:
        - The OTP can be malformed, expired, wrong, or temporarily locked out.
        - Another user may have claimed the phone before verification finished.
      WHAT COMES NEXT:
        - Once the route succeeds, the confirmed phone is available for later inbound WhatsApp identity routing.

    TESTS:
      - capability tests live in the underlying verification file

    ERRORS:
      - API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_FAILED:
          suggested_action: Retry the newest WhatsApp code or request a fresh one from the account page.
          common_causes:
            - wrong code
            - expired code
            - verification lockout
          recovery_steps:
            - Retry with the newest code.
            - Request a new code if needed.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        verify_authenticated_dcx_user_whatsapp_phone_link_otp(
            authenticated_user_id=authenticated_user_id,
            candidate_otp_code=account_phone_verify_whatsapp_otp_request.otp_code,
        )
        refreshed_account_summary = read_authenticated_dcx_user_account_summary_capability(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_OTP_INVALID":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_INVALID",
                        "message": "That WhatsApp code is not in the correct format.",
                        "suggested_action": "Enter the six-digit code exactly as received.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_RESTART_REQUIRED":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_RESTART_REQUIRED",
                        "message": "There is no active WhatsApp code to verify right now.",
                        "suggested_action": "Request a new WhatsApp code from the account page, then retry.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_EXPIRED":
            return JSONResponse(
                status_code=410,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_EXPIRED",
                        "message": "That WhatsApp code has expired.",
                        "suggested_action": "Request a new WhatsApp code, then retry with the newest code only once.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_LOCKED":
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_LOCKED",
                        "message": "WhatsApp code verification is temporarily locked.",
                        "suggested_action": "Wait a few minutes or request a fresh code later.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_VERIFICATION_FAILED":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_FAILED",
                        "message": "That WhatsApp code did not match.",
                        "suggested_action": "Re-enter the newest code carefully or request another one.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_CONFLICT",
                        "message": "That phone number is already linked to another DCX account.",
                        "suggested_action": "Use a different phone number or inspect the existing linked account first.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_VERIFY_FAILED",
                    "message": "We could not verify the WhatsApp phone code just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": refreshed_account_summary,
        "context": {
            "surface": "app",
            "view": "account_summary",
            "operation": "account_phone_whatsapp_verified",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
