"""
CONTEXT:
This file owns the public DCX `/users/signup-email/verify-otp` HTTP boundary step.
It exists so OTP verification is locally complete and separately discoverable from the initial
signup submit and resend actions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from emails.transactional.send_public_email_signup_confirmation import (
    send_public_email_signup_confirmation,
)
from routes.users.dcx_api_routes_users_support import read_public_request_client_ip
from system.rate_limits.enforce_public_route_rate_limit import (
    enforce_public_route_rate_limit_capability,
)
from users.signup_email.public_email_signup_otp_support import (
    build_public_email_signup_confirmation_email_delivery_draft,
    hash_public_email_signup_identifier_for_logs,
)
from users.signup_email.verify_public_email_signup_otp import (
    verify_public_email_signup_otp_capability,
)

logger = logging.getLogger("uvicorn.error")

dcx_api_routes_users_signup_email_verify_otp_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersEmailOtpVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signup_flow_token: str
    otp_code: str
    language_code: str
    verification_page_url: str


@dcx_api_routes_users_signup_email_verify_otp_router.post("/signup-email/verify-otp")
def post_public_email_otp_verification_request(
    public_email_otp_verification_request: DcxUsersEmailOtpVerificationRequest,
    request: Request,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The request comes from one allowed DCX public origin.
        - The JSON body contains only signup_flow_token, otp_code, language_code, and verification_page_url.
      postconditions:
        - Returns one minimal canonical success wrapper when the OTP is verified.
        - Returns one generic canonical error wrapper when verification fails.
      side_effects:
        - may rate-limit one client IP window
        - may confirm the user and identity rows
        - may mutate challenge attempt or consumed state
        - may send one best-effort confirmation email
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_email_signup_verify_route:{client_ip}
      locks:
        - postgres-backed rate-limit row lock inside the rate-limit capability
        - active challenge row lock inside the verification capability
      contention_strategy: rate-limit first by IP, then let the verification capability serialize on the active challenge row

    NARRATIVE:
      WHY this exists:
        - The public signup flow needs one dedicated verification boundary that can confirm the account without exposing internal verification state back to the browser.
      WHEN TO USE it:
        - Use it only after the user has received an OTP and is attempting to verify it.
      WHEN NOT TO USE it:
        - Do not use it for initial signup submission, resend operations, or authenticated app actions.
      WHAT CAN GO WRONG:
        - Invalid or expired token state, invalid OTP, rate limiting, origin mismatch, or persistence failure can all reject the request.
      WHAT COMES NEXT:
        - The public flow can move into confirmation or account-completion steps once verification succeeds.

    TESTS:
      - test_users_email_verify_route_returns_generic_failure_wrapper
      - test_users_email_verify_route_sends_confirmation_email_but_keeps_browser_payload_minimal
      - test_users_email_verify_route_ignores_confirmation_email_delivery_failure

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED:
          suggested_action: Restart from the signup page.
          common_causes:
            - expired or invalid flow token
            - stale verification session
          recovery_steps:
            - Return to the signup page.
            - Start the flow again.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED:
          suggested_action: Request a new code or restart the signup flow.
          common_causes:
            - invalid OTP
            - verification persistence failure
            - rate limit exceeded
          recovery_steps:
            - Retry with a valid code.
            - Or request another code.
          retry_safe: true

    CODE:
    """
    client_ip = read_public_request_client_ip(request)
    origin_header = request.headers.get("origin")
    try:
        enforce_public_route_rate_limit_capability(
            route_key="users_signup_email_verify_otp",
            client_ip=client_ip,
            max_requests=30,
            window_ms=15 * 60 * 1000,
        )
        verification_result = verify_public_email_signup_otp_capability(
            signup_flow_token=public_email_otp_verification_request.signup_flow_token,
            otp_code=public_email_otp_verification_request.otp_code,
            language_code=public_email_otp_verification_request.language_code,
            verification_page_url=public_email_otp_verification_request.verification_page_url,
            origin_header=origin_header,
        )
        try:
            confirmation_email_delivery_draft = build_public_email_signup_confirmation_email_delivery_draft(
                language_code=verification_result["language_code"],
                normalized_email=verification_result["confirmed_email"],
            )
            send_public_email_signup_confirmation(
                email_delivery_draft=confirmation_email_delivery_draft,
                confirmed_email=verification_result["confirmed_email"],
            )
        except RuntimeError as confirmation_runtime_error:
            logger.info(
                "public_email_signup_confirmation_email_send_failed client_ip=%s confirmed_email_fingerprint=%s error_code=%s",
                client_ip,
                hash_public_email_signup_identifier_for_logs(verification_result["confirmed_email"]),
                str(confirmation_runtime_error),
            )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        logger.info(
            "public_email_signup_verify_request_rejected client_ip=%s origin=%s error_code=%s",
            client_ip,
            origin_header,
            error_code,
        )
        return {
            "ok": False,
            "error": _map_verify_error(error_code),
        }

    logger.info(
        "public_email_signup_verify_request_accepted client_ip=%s",
        client_ip,
    )

    return {
        "ok": True,
        "data": {},
    }


def _map_verify_error(error_code: str) -> dict:
    if error_code in {
        "API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED",
        "API_PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_INVALID",
    }:
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED",
            "message": "This verification session is no longer valid.",
            "suggested_action": "Please restart from the signup page.",
        }

    if error_code in {
        "API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_EXCEEDED",
        "API_PUBLIC_EMAIL_SIGNUP_SECRET_MISSING",
        "API_PUBLIC_EMAIL_SIGNUP_ALLOWED_ORIGINS_MISSING",
        "API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED",
        "API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFY_PERSISTENCE_FAILED",
        "API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_PERSISTENCE_FAILED",
    }:
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED",
            "message": "We could not verify that code.",
            "suggested_action": "Request a new code or restart the signup flow.",
        }

    return {
        "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_INVALID",
        "message": "We could not accept that verification request.",
        "suggested_action": "Reload the page and try again.",
    }
