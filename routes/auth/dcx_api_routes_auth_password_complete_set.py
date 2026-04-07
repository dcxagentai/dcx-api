"""
CONTEXT:
This file owns the DCX password set/reset completion HTTP boundary.
It exists so the shared app-side password page can complete either signup setup or forgotten-password
reset using one token-driven backend contract.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from fastapi.responses import JSONResponse

from auth.password.complete_dcx_password_set_from_challenge import (
    complete_dcx_password_set_from_challenge,
)

dcx_api_routes_auth_password_complete_set_router = APIRouter(prefix="/auth", tags=["auth"])


class DcxAuthPasswordCompleteSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password_challenge_token: str
    password: str
    confirm_password: str


@dcx_api_routes_auth_password_complete_set_router.post("/password/complete-set")
def post_dcx_auth_password_complete_set(
    complete_set_request: DcxAuthPasswordCompleteSetRequest,
):
    """
    CONTRACT:
      preconditions:
        - The body contains the password challenge token plus password and confirmation values.
      postconditions:
        - Returns one canonical success wrapper after the password has been set successfully.
      side_effects:
        - may create or update the password credential row
        - consumes the password-link challenge row
        - revokes existing sessions for the user
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The app password-set page should have one direct contract for completing either setup or reset.
      WHEN TO USE it:
        - Use it from the app-side password-set form only.
      WHEN NOT TO USE it:
        - Do not use it for login or logout.
      WHAT CAN GO WRONG:
        - The token can be invalid or expired.
        - The password can fail validation.
      WHAT COMES NEXT:
        - The user can return to `/login` and sign in with the new password.

    TESTS:
      - covered_indirectly_by_password_complete_set_route_tests

    ERRORS: []

    CODE:
    """
    try:
        completion_result = complete_dcx_password_set_from_challenge(
            raw_password_link_token=complete_set_request.password_challenge_token,
            candidate_password=complete_set_request.password,
            confirmed_password=complete_set_request.confirm_password,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_DCX_PASSWORD_CONFIRMATION_MISMATCH":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "The password confirmation did not match.",
                        "suggested_action": "Re-enter the same password in both fields.",
                    },
                },
            )

        if error_code == "API_DCX_PASSWORD_INVALID":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "That password did not meet the current DCX rule set.",
                        "suggested_action": "Use a password with at least 12 characters.",
                    },
                },
            )

        if error_code in {
            "API_DCX_PASSWORD_LINK_TOKEN_INVALID",
            "API_DCX_PASSWORD_CHALLENGE_NOT_FOUND",
            "API_DCX_PASSWORD_CHALLENGE_EXPIRED",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "That password link is no longer valid.",
                        "suggested_action": "Request a fresh password link and retry.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_PASSWORD_COMPLETE_SET_FAILED",
                    "message": "We could not set the DCX password just now.",
                    "suggested_action": "Retry after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": {
            "challenge_purpose": completion_result["challenge_purpose"],
            "password_set_at_ts_ms": completion_result["password_set_at_ts_ms"],
        },
        "context": {
            "surface": "shared_auth",
            "view": "password_complete_set",
        },
    }
