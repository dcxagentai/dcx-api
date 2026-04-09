"""
CONTEXT:
This file owns the DCX forgot-password request HTTP boundary.
It exists so app and admin login screens can request a password-reset email through one generic,
enumeration-safe backend contract.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from fastapi.responses import JSONResponse

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.password.request_dcx_password_reset_email_challenge import (
    request_dcx_password_reset_email_challenge,
)
from emails.transactional.send_dcx_password_reset_email import (
    send_dcx_password_reset_email,
)
from routes.users.dcx_api_routes_users_support import read_public_request_client_ip
from system.rate_limits.enforce_public_route_rate_limit import (
    enforce_public_route_rate_limit_capability,
)

logger = logging.getLogger("uvicorn.error")

dcx_api_routes_auth_password_request_reset_router = APIRouter(prefix="/auth", tags=["auth"])


class DcxAuthPasswordRequestResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


@dcx_api_routes_auth_password_request_reset_router.post("/password/request-reset")
def post_dcx_auth_password_request_reset(
    request: Request,
    reset_request: DcxAuthPasswordRequestResetRequest,
):
    """
    CONTRACT:
      preconditions:
        - The body contains one email field.
      postconditions:
        - Returns one generic canonical success wrapper whether or not the email belongs to an eligible account.
        - May send one password-reset email for an eligible confirmed account.
      side_effects:
        - may create or refresh one password-reset challenge row
        - may send one password-reset email
        - may write one rate-limit row
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Users who forgot their password need one safe email-based recovery start point.
      WHEN TO USE it:
        - Use it from app/admin login screens.
      WHEN NOT TO USE it:
        - Do not use it for authenticated password changes.
      WHAT CAN GO WRONG:
        - The database or provider can fail.
        - The email may not belong to an eligible confirmed account.
      WHAT COMES NEXT:
        - If the account exists, the user receives an email link to the shared app password-set page.

    TESTS:
      - covered_indirectly_by_password_reset_route_tests

    ERRORS: []

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    client_ip = read_public_request_client_ip(request)

    try:
        enforce_public_route_rate_limit_capability(
            route_key="auth_password_request_reset",
            client_ip=client_ip,
            max_requests=10,
            window_ms=15 * 60 * 1000,
        )
        reset_result = request_dcx_password_reset_email_challenge(
            email=reset_request.email,
        )
        if reset_result["email_delivery_draft"] is not None:
            try:
                send_dcx_password_reset_email(
                    email_delivery_draft=reset_result["email_delivery_draft"],
                )
            except RuntimeError as runtime_error:
                logger.info(
                    "dcx_password_reset_email_send_failed client_ip=%s error_code=%s",
                    client_ip,
                    str(runtime_error),
                )
    except RuntimeError as runtime_error:
        logger.info(
            "dcx_password_reset_request_failed client_ip=%s error_code=%s",
            client_ip,
            str(runtime_error),
        )
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "data": {
                    "accepted": True,
                },
                "context": {
                    "surface": "shared_auth",
                    "view": "password_request_reset",
                    "delivery_visibility": "enumeration_safe_generic",
                },
            },
        )

    return {
        "ok": True,
        "data": {
            "accepted": True,
        },
        "context": {
            "surface": "shared_auth",
            "view": "password_request_reset",
            "delivery_visibility": "enumeration_safe_generic",
        },
    }
