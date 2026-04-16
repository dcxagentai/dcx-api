"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for starting one WhatsApp phone-link
OTP flow from the account page.
It exists so logged-in users can request one WhatsApp code for a candidate phone number
without writing that phone into their confirmed account profile before verification.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from apis.meta_whatsapp.send_dcx_whatsapp_otp_template_message import (
    send_dcx_whatsapp_otp_template_message,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from users.account.read_authenticated_dcx_user_account_summary import (
    read_authenticated_dcx_user_account_summary_capability,
)
from users.account_phone.mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent import (
    mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent,
)
from users.account_phone.prepare_authenticated_dcx_user_whatsapp_phone_link_otp_delivery import (
    prepare_authenticated_dcx_user_whatsapp_phone_link_otp_delivery,
)

dcx_api_routes_users_me_account_phone_request_whatsapp_otp_router = APIRouter(
    prefix="/users",
    tags=["users"],
)


class DcxUsersMeAccountPhoneRequestWhatsappOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_e164: str


@dcx_api_routes_users_me_account_phone_request_whatsapp_otp_router.post(
    "/me/account-phone/request-whatsapp-otp",
    response_model=None,
)
def post_authenticated_dcx_user_account_phone_request_whatsapp_otp(
    request: Request,
    account_phone_request_whatsapp_otp_request: DcxUsersMeAccountPhoneRequestWhatsappOtpRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
        - The body contains one candidate phone number string.
      postconditions:
        - Starts or refreshes one pending WhatsApp phone-link challenge.
        - Sends one OTP via the configured Meta WhatsApp template when the phone is not already confirmed.
        - Returns a canonical success wrapper containing the refreshed account-summary payload.
      side_effects:
        - writes to stephen_dcx_user_auth_challenges
        - may send one WhatsApp template message
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The app account page needs one explicit action for proving phone ownership through WhatsApp.
      WHEN TO USE it:
        - Use it when the authenticated user clicks `Send code` or `Resend code` for the phone field.
      WHEN NOT TO USE it:
        - Do not use it for public signup, password reset, or admin user edits.
      WHAT CAN GO WRONG:
        - The phone may be malformed or already linked elsewhere.
        - Cooldown and send-budget rules may block the request.
        - Meta template delivery may fail.
      WHAT COMES NEXT:
        - The user submits the OTP through the verify route, and only then does the confirmed phone update.

    TESTS:
      - capability tests live in the underlying prepare and provider files

    ERRORS:
      - API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_REQUEST_INVALID:
          suggested_action: Re-enter the phone number with country code and retry.
          common_causes:
            - invalid phone shape
          recovery_steps:
            - Enter the phone in E.164 format, for example +34600000001.
          retry_safe: true
      - API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_REQUEST_CONFLICT:
          suggested_action: Use a different phone number or inspect the existing linked account first.
          common_causes:
            - phone already linked to another user
          recovery_steps:
            - Confirm which account owns the phone.
            - Retry with the intended number.
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
        preparation_result = prepare_authenticated_dcx_user_whatsapp_phone_link_otp_delivery(
            authenticated_user_id=authenticated_user_id,
            candidate_phone_number=account_phone_request_whatsapp_otp_request.phone_e164,
        )
        if preparation_result["send_required"] is True:
            send_dcx_whatsapp_otp_template_message(
                phone_e164=preparation_result["phone_e164"],
                otp_code=preparation_result["otp_code"],
            )
            mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent(
                authenticated_user_id=authenticated_user_id,
                challenge_id=preparation_result["challenge_id"],
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
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_ACCOUNT_NOT_FOUND",
                        "message": "We could not find that DCX user account.",
                        "suggested_action": "Sign in again and retry after confirming the account still exists.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_INVALID":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_REQUEST_INVALID",
                        "message": "We could not use that phone number for WhatsApp verification.",
                        "suggested_action": "Re-enter the phone with country code, then retry.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_REQUEST_CONFLICT",
                        "message": "That phone number is already linked to another DCX account.",
                        "suggested_action": "Use a different phone number or inspect the existing linked account first.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_ACTIVE":
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_REQUEST_COOLDOWN_ACTIVE",
                        "message": "A WhatsApp code was sent recently for that phone.",
                        "suggested_action": "Wait a moment for the resend cooldown to pass, then retry.",
                    },
                },
            )

        if error_code == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_SEND_LIMIT_REACHED":
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_REQUEST_LIMIT_REACHED",
                        "message": "We have reached the temporary WhatsApp send limit for that phone.",
                        "suggested_action": "Wait for the send window to reset, then retry.",
                    },
                },
            )

        if error_code.startswith("API_DCX_WHATSAPP_OTP_PROVIDER_CONFIGURATION_MISSING"):
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_PROVIDER_CONFIGURATION_MISSING",
                        "message": "WhatsApp verification is not configured correctly right now.",
                        "suggested_action": "Retry later after the WhatsApp provider configuration is complete.",
                    },
                },
            )

        if error_code in {
            "API_DCX_WHATSAPP_OTP_PROVIDER_SEND_FAILED",
            "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_DELIVERY_MARK_FAILED",
            "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_CHALLENGE_NOT_FOUND",
        }:
            return JSONResponse(
                status_code=502,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_DELIVERY_FAILED",
                        "message": "We could not send the WhatsApp verification code just now.",
                        "suggested_action": "Retry in a moment after the WhatsApp provider is healthy.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_REQUEST_FAILED",
                    "message": "We could not start WhatsApp phone verification just now.",
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
            "operation": (
                "account_phone_whatsapp_already_confirmed"
                if preparation_result["send_required"] is False
                else "account_phone_whatsapp_otp_sent"
            ),
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
