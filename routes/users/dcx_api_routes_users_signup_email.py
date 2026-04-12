"""
CONTEXT:
This file owns the public DCX `/users/signup-email` HTTP boundary step.
It exists so the initial email-submit stage of the signup flow is locally complete and independently
discoverable from the later OTP verification and resend steps.
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
from users.signup_email.create_or_refresh_public_email_signup_artifacts import (
    create_or_refresh_public_email_signup_artifacts_capability,
)
from users.signup_email.public_email_signup_otp_support import (
    hash_public_email_signup_identifier_for_logs,
)
from users.signup_email.reset_public_email_signup_send_cooldown_after_delivery_failure import (
    reset_public_email_signup_send_cooldown_after_delivery_failure_capability,
)

logger = logging.getLogger("uvicorn.error")

dcx_api_routes_users_signup_email_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersEmailSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    language_code: str
    signup_page_url: str


@dcx_api_routes_users_signup_email_router.post("/signup-email")
def post_public_email_signup_request(
    public_email_signup_request: DcxUsersEmailSignupRequest,
    request: Request,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The request comes from one allowed DCX public origin.
        - The JSON body contains only email, language_code, and signup_page_url.
      postconditions:
        - Returns one minimal canonical success wrapper for browser continuation.
        - May create or refresh the user, identity, and challenge rows.
        - May send one fresh OTP email when the cooldown allows it.
      side_effects:
        - may rate-limit one client IP window
        - may create or refresh user signup state
        - may send one OTP email
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_email_signup_route:{client_ip}:{email}
      locks:
        - postgres-backed rate-limit row lock inside the rate-limit capability
        - normalized-email advisory lock inside the signup artifacts capability
      contention_strategy: rate-limit first by IP, then serialize same-email state changes inside the persistence capability

    NARRATIVE:
      WHY this exists:
        - The public landing pages need a narrow durable entry point for email signup that does not leak internals back to the browser.
      WHEN TO USE it:
        - Use it from the public signup form only.
      WHEN NOT TO USE it:
        - Do not use it for OTP verification, OTP resend, or authenticated user actions.
      WHAT CAN GO WRONG:
        - Bad request shape, wrong origin, rate-limit excess, database failure, or provider failure can all reject the request.
      WHAT COMES NEXT:
        - The browser stores the returned signup flow token and continues to the OTP page.

    TESTS:
      - test_users_email_signup_route_returns_minimal_flow_token_payload
      - test_users_email_signup_route_rejects_extra_fields
      - test_users_email_signup_route_returns_generic_error_wrapper_on_validation_failure

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_REQUEST_INVALID:
          suggested_action: Check the signup form input and try again.
          common_causes:
            - malformed payload
            - unknown origin
            - invalid landing-page URL
          recovery_steps:
            - Reload the official public page.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED:
          suggested_action: Wait a little and try again.
          common_causes:
            - IP rate limit exceeded
            - temporary provider or database issue
          recovery_steps:
            - Pause briefly.
            - Retry from the public page.
          retry_safe: true

    CODE:
    """
    client_ip = read_public_request_client_ip(request)
    origin_header = request.headers.get("origin")
    signup_result: dict | None = None

    try:
        enforce_public_route_rate_limit_capability(
            route_key="users_signup_email",
            client_ip=client_ip,
            max_requests=5,
            window_ms=15 * 60 * 1000,
        )
        signup_result = create_or_refresh_public_email_signup_artifacts_capability(
            email=public_email_signup_request.email,
            language_code=public_email_signup_request.language_code,
            signup_page_url=public_email_signup_request.signup_page_url,
            origin_header=origin_header,
        )

        if signup_result["send_required"] and signup_result["email_delivery_draft"] is not None:
            send_public_email_signup_otp(
                email_delivery_draft=signup_result["email_delivery_draft"],
                challenge_id=signup_result["challenge_id"],
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
            and signup_result is not None
        ):
            try:
                reset_public_email_signup_send_cooldown_after_delivery_failure_capability(
                    **signup_result["delivery_failure_recovery_state"],
                )
            except RuntimeError:
                logger.info(
                    "public_email_signup_delivery_failure_recovery_failed client_ip=%s challenge_id=%s",
                    client_ip,
                    signup_result["challenge_id"],
                )
        logger.info(
            "public_email_signup_request_rejected client_ip=%s origin=%s error_code=%s",
            client_ip,
            origin_header,
            error_code,
        )
        return {
            "ok": False,
            "error": _map_signup_error(error_code),
        }

    signup_fingerprint = (
        hash_public_email_signup_identifier_for_logs(signup_result["signup_flow_token"])
        if isinstance(signup_result["signup_flow_token"], str) and signup_result["signup_flow_token"].strip() != ""
        else "not_issued"
    )

    logger.info(
        "public_email_signup_request_accepted client_ip=%s signup_fingerprint=%s send_required=%s",
        client_ip,
        signup_fingerprint,
        signup_result["send_required"],
    )

    return {
        "ok": True,
        "data": (
            {"signup_flow_token": signup_result["signup_flow_token"]}
            if isinstance(signup_result["signup_flow_token"], str) and signup_result["signup_flow_token"].strip() != ""
            else {}
        ),
    }


def _map_signup_error(error_code: str) -> dict:
    if error_code == "API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_EXCEEDED":
        return {
            "code": error_code,
            "message": "Please wait a little before trying again.",
            "suggested_action": "Retry the signup flow in a moment.",
        }

    if error_code.startswith("API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING"):
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
            "message": "We could not accept that signup request just now.",
            "suggested_action": "Please wait a little and try again.",
        }

    if error_code.startswith("API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID"):
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
            "message": "We could not accept that signup request just now.",
            "suggested_action": "Please wait a little and try again.",
        }

    if error_code.startswith("API_LIVE_EMAIL_TEMPLATE_"):
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
            "message": "We could not accept that signup request just now.",
            "suggested_action": "Please wait a little and try again.",
        }

    if error_code in {
        "API_PUBLIC_EMAIL_SIGNUP_PERSISTENCE_FAILED",
        "API_PUBLIC_EMAIL_SIGNUP_SECRET_MISSING",
        "API_PUBLIC_EMAIL_SIGNUP_ALLOWED_ORIGINS_MISSING",
        "API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE",
        "API_PUBLIC_EMAIL_SIGNUP_SEND_LIMIT_REACHED",
        "API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED",
        "API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN",
        "API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_PERSISTENCE_FAILED",
        "API_PUBLIC_EMAIL_SIGNUP_DELIVERY_FAILURE_RECOVERY_FAILED",
    }:
        return {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_REJECTED",
            "message": "We could not accept that signup request just now.",
            "suggested_action": "Please wait a little and try again.",
        }

    return {
        "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_INVALID",
        "message": "We could not accept that signup request.",
        "suggested_action": "Check the form input and try again.",
    }
