"""
CONTEXT:
This file owns the first DCX shared auth email/password login HTTP boundary.
It exists so both the app and admin frontends can establish one secure browser session against the
same backend auth contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from fastapi.responses import JSONResponse

from auth.login.login_dcx_user_with_email_and_password import (
    login_dcx_user_with_email_and_password,
)
from auth.login.enforce_dcx_auth_login_rate_limits import (
    enforce_dcx_auth_login_rate_limits,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.session.set_dcx_auth_session_cookie_on_response import (
    set_dcx_auth_session_cookie_on_response,
)
from routes.users.dcx_api_routes_users_support import read_public_request_client_ip

dcx_api_routes_auth_login_password_router = APIRouter(prefix="/auth", tags=["auth"])


class DcxAuthLoginPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


@dcx_api_routes_auth_login_password_router.post("/login/password", response_model=None)
def post_dcx_auth_login_password(
    request: Request,
    login_request: DcxAuthLoginPasswordRequest,
):
    """
    CONTRACT:
      preconditions:
        - The body contains one email/password pair.
      postconditions:
        - Returns a canonical success wrapper with one authenticated session summary.
        - Sets the shared DCX session cookie on the response.
      side_effects:
        - may create one new auth session row
        - mutates the outgoing response with one Set-Cookie header
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The app and admin frontends need one shared login contract from the start.
      WHEN TO USE it:
        - Use it from the app/admin login forms.
      WHEN NOT TO USE it:
        - Do not use it for password setup or reset.
      WHAT CAN GO WRONG:
        - Credentials can be wrong or no password may be set.
        - Database/session creation can fail.
      WHAT COMES NEXT:
        - Session-check and logout routes can then manage the same browser session.

    TESTS:
      - covered_indirectly_by_auth_login_route_tests

    ERRORS:
      - API_DCX_AUTH_LOGIN_INVALID_CREDENTIALS:
          suggested_action: Retry with the correct email and password.
          common_causes:
            - wrong password
            - no password set
            - unknown email
          recovery_steps:
            - Re-enter the credentials carefully.
            - Use password setup/reset once those flows are connected.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    try:
        enforce_dcx_auth_login_rate_limits(
            client_ip=read_public_request_client_ip(request),
            normalized_email=login_request.email.strip().lower(),
        )
        login_result = login_dcx_user_with_email_and_password(
            email=login_request.email,
            candidate_password=login_request.password,
            request_ip=read_public_request_client_ip(request),
            request_user_agent=request.headers.get("user-agent"),
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_DCX_AUTH_LOGIN_RATE_LIMIT_EXCEEDED":
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "Too many DCX login attempts were received for this window.",
                        "suggested_action": "Wait a little and retry the login.",
                    },
                },
            )

        if error_code == "API_DCX_AUTH_LOGIN_INVALID_CREDENTIALS":
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "The email or password was not accepted.",
                        "suggested_action": "Retry with the correct email and password.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_AUTH_LOGIN_FAILED",
                    "message": "We could not complete the DCX login just now.",
                    "suggested_action": "Retry after the backend is healthy.",
                },
            },
        )

    response = JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "data": {
                "user": login_result["user"],
                "session_expires_at_ts_ms": login_result["session_expires_at_ts_ms"],
            },
            "context": {
                "surface": "shared_auth",
                "view": "login_password",
                "auth_mode": "session_cookie",
            },
        },
    )
    set_dcx_auth_session_cookie_on_response(
        response=response,
        raw_session_token=login_result["raw_session_token"],
    )
    return response
