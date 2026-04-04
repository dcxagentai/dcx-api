"""
CONTEXT:
This file owns the public DCX `/users/signup-email/resend-otp` HTTP boundary step.
It exists so OTP resend behavior is locally complete and independently discoverable from the initial
signup submit and verification actions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from emails.transactional.send_public_email_signup_otp import (
    send_public_email_signup_otp,
)
from routes.users.dcx_api_routes_users_support import read_public_request_client_ip
from system.rate_limits.enforce_public_route_rate_limit import (
    enforce_public_route_rate_limit_capability,
)
from users.signup_email.public_email_signup_otp_support import (
    hash_public_email_signup_identifier_for_logs,
)
from users.signup_email.resend_public_email_signup_otp import (
    resend_public_email_signup_otp_capability,
)
from users.signup_email.reset_public_email_signup_send_cooldown_after_delivery_failure import (
    reset_public_email_signup_send_cooldown_after_delivery_failure_capability,
)

logger = logging.getLogger("uvicorn.error")

dcx_api_routes_users_signup_email_resend_otp_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersEmailOtpResendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signup_flow_token: str
    language_code: str
    resend_page_url: str


@dcx_api_routes_users_signup_email_resend_otp_router.post("/signup-email/resend-otp")
def post_public_email_otp_resend_request(
    public_email_otp_resend_request: DcxUsersEmailOtpResendRequest,
    request: Request,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The request comes from one allowed DCX public origin.
        - The JSON body contains only signup_flow_token, language_code, and resend_page_url.
      postconditions:
        - Returns one minimal canonical success wrapper with the refreshed signup flow token when resend succeeds.
        - Returns one generic error wrapper when resend is blocked or restart is required.
      side_effects:
        - may rate-limit one client IP window
        - may refresh the active challenge row
        - may send one fresh OTP email
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_email_signup_resend_route:{client_ip}
      locks:
        - postgres-backed rate-limit row lock inside the rate-limit capability
        - active challenge row lock inside the resend capability
      contention_strategy: rate-limit first by IP, then let the resend capability serialize on the active challenge row

    NARRATIVE:
      WHY this exists:
        - The public signup flow needs one dedicated resend boundary so cooldowns, limits, and recovery behavior are locally legible and independently testable.
      WHEN TO USE it:
        - Use it only when the user needs another OTP for the current signup flow.
      WHEN NOT TO USE it:
        - Do not use it for initial signup submission, verification, or authenticated email operations.
      WHAT CAN GO WRONG:
        - Cooldown, send-limit, invalid flow state, provider failure, or origin mismatch can all reject the request.
      WHAT COMES NEXT:
        - The browser stores the refreshed signup flow token and stays on the verification path.

    TESTS:
      - test_users_email_resend_route_returns_refreshed_flow_token

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_COOLDOWN_ACTIVE:
          suggested_action: Wait a little before requesting another code.
          common_causes:
            - resend requested too soon
          recovery_steps:
            - Pause briefly.
            - Retry resend later.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED:
          suggested_action: Restart from the signup page.
          common_causes:
            - stale or invalid flow token
            - challenge can no longer be resent safely
          recovery_steps:
            - Return to the signup page.
            - Start the flow again.
          retry_safe: true

    CODE:
    """
    client_ip = read_public_request_client_ip(request)
    origin_header = request.headers.get("origin")
    resend_result: dict | None = None

    try:
        enforce_public_route_rate_limit_capability(
            route_key="users_signup_email_resend_otp",
            client_ip=client_ip,
            max_requests=5,
            window_ms=15 * 60 * 1000,
        )
        resend_result = resend_public_email_signup_otp_capability(
            signup_flow_token=public_email_otp_resend_request.signup_flow_token,
            language_code=public_email_otp_resend_request.language_code,
            resend_page_url=public_email_otp_resend_request.resend_page_url,
            origin_header=origin_header,
        )
        send_public_email_signup_otp(
            email_delivery_draft=resend_result["email_delivery_draft"],
            challenge_id=resend_result["challenge_id"],
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        is_resend_configuration_missing = error_code.startswith(
            "API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING"
        )
        is_resend_draft_invalid = error_code.startswith(
            "API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID"
        )
        if (
            (
                error_code in {
                    "API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED",
                    "API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN",
                }
                or is_resend_configuration_missing
                or is_resend_draft_invalid
            )
            and resend_result is not None
        ):
            try:
                reset_public_email_signup_send_cooldown_after_delivery_failure_capability(
                    **resend_result["delivery_failure_recovery_state"],
                )
            except RuntimeError:
                logger.info(
                    "public_email_signup_resend_delivery_failure_recovery_failed client_ip=%s challenge_id=%s",
                    client_ip,
                    resend_result["challenge_id"],
                )
        logger.info(
            "public_email_signup_resend_request_rejected client_ip=%s origin=%s error_code=%s",
            client_ip,
            origin_header,
            error_code,
        )
        return {
            "ok": False,
            "error": _map_resend_error(error_code),
        }

    logger.info(
        "public_email_signup_resend_request_accepted client_ip=%s signup_fingerprint=%s",
        client_ip,
        hash_public_email_signup_identifier_for_logs(resend_result["signup_flow_token"]),
    )

    return {
        "ok": True,
        "data": {
            "signup_flow_token": resend_result["signup_flow_token"],
        },
    }


def _map_resend_error(error_code: str) -> dict:
    if error_code == "API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_COOLDOWN_ACTIVE":
        return {
            "code": error_code,
            "message": "Please wait a little before requesting another code.",
            "suggested_action": "Retry resend in a moment.",
        }

    if error_code.startswith("API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING"):
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
            "message": "We could not resend a code right now.",
            "suggested_action": "Please wait a little and try again.",
        }

    if error_code.startswith("API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID"):
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
            "message": "We could not resend a code right now.",
            "suggested_action": "Please wait a little and try again.",
        }

    if error_code in {
        "API_PUBLIC_EMAIL_SIGNUP_SEND_LIMIT_REACHED",
        "API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED",
        "API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN",
        "API_PUBLIC_EMAIL_SIGNUP_ALLOWED_ORIGINS_MISSING",
        "API_PUBLIC_EMAIL_SIGNUP_DELIVERY_FAILURE_RECOVERY_FAILED",
    }:
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
            "message": "We could not resend a code right now.",
            "suggested_action": "Please wait a little and try again.",
        }

    if error_code in {
        "API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED",
        "API_PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_INVALID",
    }:
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED",
            "message": "This verification session is no longer valid.",
            "suggested_action": "Please restart from the signup page.",
        }

    return {
        "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
        "message": "We could not resend a code right now.",
        "suggested_action": "Please wait a little and try again.",
    }
