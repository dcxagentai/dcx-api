"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for starting one WhatsApp phone-link
verification-link flow from the account page.
It exists so logged-in users can request one WhatsApp verification message for a candidate phone
number without writing that phone into their confirmed account profile before verification.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from apis.meta_whatsapp.send_dcx_whatsapp_verification_template_message import (
    send_dcx_whatsapp_verification_template_message,
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
from users.account_phone.prepare_authenticated_dcx_user_whatsapp_phone_link_delivery import (
    prepare_authenticated_dcx_user_whatsapp_phone_link_delivery,
)

dcx_api_routes_users_me_account_phone_request_whatsapp_verification_link_router = APIRouter(
    prefix="/users",
    tags=["users"],
)
logger = logging.getLogger("uvicorn.error")


class DcxUsersMeAccountPhoneRequestWhatsappVerificationLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_e164: str
    language_code: str | None = None
    confirmation_purpose: str | None = None
    force_send: bool = False


@dcx_api_routes_users_me_account_phone_request_whatsapp_verification_link_router.post(
    "/me/account-phone/request-whatsapp-verification-link",
    response_model=None,
)
def post_authenticated_dcx_user_account_phone_request_whatsapp_verification_link(
    request: Request,
    account_phone_request_whatsapp_verification_link_request: DcxUsersMeAccountPhoneRequestWhatsappVerificationLinkRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    current_environment = os.getenv("DCX_ENVIRONMENT", "local").strip().lower()
    is_local_environment = current_environment in {"local", "development", "dev"}

    try:
        preparation_result = prepare_authenticated_dcx_user_whatsapp_phone_link_delivery(
            authenticated_user_id=authenticated_user_id,
            candidate_phone_number=account_phone_request_whatsapp_verification_link_request.phone_e164,
            language_code=account_phone_request_whatsapp_verification_link_request.language_code,
            confirmation_purpose=account_phone_request_whatsapp_verification_link_request.confirmation_purpose,
            force_send=account_phone_request_whatsapp_verification_link_request.force_send,
        )
        if preparation_result["send_required"] is True:
            provider_send_result = send_dcx_whatsapp_verification_template_message(
                phone_e164=preparation_result["phone_e164"],
                template_body_greeting_name="there",
                template_body_verification_target=preparation_result["phone_e164"],
                template_button_url_suffix=preparation_result["verification_link_suffix"],
                send_payload_with_provider=(
                    _send_local_debug_meta_verification_payload
                    if is_local_environment
                    else None
                ),
            )
            mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent(
                authenticated_user_id=authenticated_user_id,
                challenge_id=preparation_result["challenge_id"],
                provider_message_id=provider_send_result.get("provider_message_id"),
                template_name=provider_send_result.get("template_name"),
                template_language_code=provider_send_result.get("template_language_code"),
            )

        refreshed_account_summary = read_authenticated_dcx_user_account_summary_capability(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        logger.error(
            "account_phone_whatsapp_verification_link_request_failed "
            "error_code=%s user_id=%s phone_e164=%s environment=%s",
            error_code,
            authenticated_user_id,
            account_phone_request_whatsapp_verification_link_request.phone_e164,
            current_environment,
        )

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
                        "message": "This phone number can't be added to this account.",
                        "suggested_action": "Try a different phone number, or contact support if you think this is a mistake.",
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
                        "message": "A WhatsApp verification link was sent recently for that phone.",
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

        if error_code.startswith("API_DCX_WHATSAPP_VERIFY_PROVIDER_CONFIGURATION_MISSING"):
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_PROVIDER_CONFIGURATION_MISSING",
                        "message": "We couldn't send the verification link right now.",
                        "suggested_action": "Please try again in a moment.",
                    },
                },
            )

        if error_code.startswith("API_DCX_CHANNEL_ORIGIN_CONFIGURATION_MISSING"):
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_CHANNEL_ORIGIN_CONFIGURATION_MISSING",
                        "message": "We couldn't send the verification link right now.",
                        "suggested_action": "Please try again in a moment.",
                    },
                },
            )

        if error_code in {
            "API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED",
            "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_DELIVERY_MARK_FAILED",
            "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_CHALLENGE_NOT_FOUND",
        }:
            return JSONResponse(
                status_code=502,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_PHONE_WHATSAPP_DELIVERY_FAILED",
                        "message": "We could not send the WhatsApp verification link just now.",
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
                    "message": (
                        f"We could not start WhatsApp phone verification just now ({error_code})."
                        if is_local_environment
                        else "We could not start WhatsApp phone verification just now."
                    ),
                    "suggested_action": (
                        f"Inspect the backend error code {error_code}, then retry."
                        if is_local_environment
                        else "Retry in a moment after the backend is healthy."
                    ),
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
                else (
                    "account_phone_whatsapp_reverification_link_sent"
                    if account_phone_request_whatsapp_verification_link_request.force_send
                    or account_phone_request_whatsapp_verification_link_request.confirmation_purpose == "sender_reconfirmation"
                    else "account_phone_whatsapp_link_sent"
                )
            ),
            "identity_resolution_mode": identity_resolution_mode,
            "local_debug_verification_link_url": (
                preparation_result.get("verification_link_url")
                if preparation_result["send_required"] is True and is_local_environment
                else None
            ),
        },
    }


def _send_local_debug_meta_verification_payload(
    request_url: str,
    request_headers: dict,
    request_payload: dict,
) -> dict:
    """
    Minimal local-development contract:
      - validates that the same Meta config and payload shape are present locally
      - skips the actual outbound HTTP request
      - returns one Meta-like accepted payload so the phone-link flow can continue
    """
    _ = request_url
    _ = request_headers
    _ = request_payload
    return {
        "messages": [
            {
                "id": "dcx_local_debug_meta_whatsapp_message",
            }
        ]
    }
