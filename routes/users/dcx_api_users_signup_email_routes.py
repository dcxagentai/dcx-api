"""
CONTEXT:
This file owns the public DCX `/users/signup-email` HTTP surface.
It exists so `dcx_api_app.py` stays a composition root while the signup, verify, and resend
handlers remain visible together as one secure boundary module.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from dcx_api_create_or_refresh_public_email_signup_artifacts_capability import (
    create_or_refresh_public_email_signup_artifacts_capability,
)
from dcx_api_enforce_public_route_rate_limit_capability import (
    enforce_public_route_rate_limit_capability,
)
from dcx_api_public_email_signup_otp_support import (
    hash_public_email_signup_identifier_for_logs,
)
from dcx_api_reset_public_email_signup_send_cooldown_after_delivery_failure_capability import (
    reset_public_email_signup_send_cooldown_after_delivery_failure_capability,
)
from dcx_api_resend_public_email_signup_otp_capability import (
    resend_public_email_signup_otp_capability,
)
from dcx_api_send_public_email_signup_otp_via_resend_capability import (
    send_public_email_signup_otp_via_resend_capability,
)
from dcx_api_verify_public_email_signup_otp_capability import (
    verify_public_email_signup_otp_capability,
)

logger = logging.getLogger("uvicorn.error")

dcx_api_users_signup_email_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersEmailSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    language_code: str
    signup_page_url: str


class DcxUsersEmailOtpVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signup_flow_token: str
    otp_code: str
    language_code: str
    verification_page_url: str


class DcxUsersEmailOtpResendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signup_flow_token: str
    language_code: str
    resend_page_url: str


@dcx_api_users_signup_email_router.post("/signup-email")
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
        - Do not use it for OTP verify/resend or authenticated user actions.
      WHAT CAN GO WRONG:
        - Bad request shape, wrong origin, rate-limit excess, DB failure, or provider failure can all reject the request.
      WHAT COMES NEXT:
        - The browser stores the returned signup flow token and continues to the OTP page.

    TESTS:
      - signup_route_returns_minimal_flow_token_payload
      - signup_route_rejects_unknown_origin
      - signup_route_rejects_extra_fields
      - signup_route_returns_generic_error_wrapper_on_validation_failure

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
    client_ip = _read_public_request_client_ip(request)
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
            send_public_email_signup_otp_via_resend_capability(
                email_delivery_draft=signup_result["email_delivery_draft"],
                challenge_id=signup_result["challenge_id"],
            )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if (
            error_code in {
                "API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED",
                "API_PUBLIC_EMAIL_SIGNUP_RESEND_API_KEY_MISSING",
                "API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN",
            }
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


@dcx_api_users_signup_email_router.post("/signup-email/verify-otp")
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
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_email_signup_verify_route:{client_ip}
      locks:
        - postgres-backed rate-limit row lock inside the rate-limit capability
        - active challenge row lock inside the verification capability
      contention_strategy: rate-limit first by IP, then let the verification capability serialize on the active challenge row

    CODE:
    """
    client_ip = _read_public_request_client_ip(request)
    origin_header = request.headers.get("origin")
    resend_result: dict | None = None

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


@dcx_api_users_signup_email_router.post("/signup-email/resend-otp")
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

    CODE:
    """
    client_ip = _read_public_request_client_ip(request)
    origin_header = request.headers.get("origin")

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
        send_public_email_signup_otp_via_resend_capability(
            email_delivery_draft=resend_result["email_delivery_draft"],
            challenge_id=resend_result["challenge_id"],
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if (
            error_code in {
                "API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED",
                "API_PUBLIC_EMAIL_SIGNUP_RESEND_API_KEY_MISSING",
                "API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN",
            }
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


def _map_signup_error(error_code: str) -> dict:
    if error_code == "API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_EXCEEDED":
        return {
            "code": error_code,
            "message": "Please wait a little before trying again.",
            "suggested_action": "Retry the signup flow in a moment.",
        }

    if error_code in {
        "API_PUBLIC_EMAIL_SIGNUP_PERSISTENCE_FAILED",
        "API_PUBLIC_EMAIL_SIGNUP_SECRET_MISSING",
        "API_PUBLIC_EMAIL_SIGNUP_ALLOWED_ORIGINS_MISSING",
        "API_PUBLIC_EMAIL_SIGNUP_SEND_LIMIT_REACHED",
        "API_PUBLIC_EMAIL_SIGNUP_RESEND_API_KEY_MISSING",
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


def _map_resend_error(error_code: str) -> dict:
    if error_code == "API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_COOLDOWN_ACTIVE":
        return {
            "code": error_code,
            "message": "Please wait a little before requesting another code.",
            "suggested_action": "Retry resend in a moment.",
        }

    if error_code in {
        "API_PUBLIC_EMAIL_SIGNUP_SEND_LIMIT_REACHED",
        "API_PUBLIC_EMAIL_SIGNUP_RESEND_API_KEY_MISSING",
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


def _read_public_request_client_ip(request: Request) -> str:
    """Minimal contract: read the client IP from trusted proxy headers only when explicitly enabled."""
    if os.getenv("DCX_TRUST_PROXY_HEADERS", "").strip().lower() == "true":
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for != "":
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip != "":
            return real_ip

    return request.client.host if request.client is not None else "unknown"
