"""
CONTEXT:
This file owns the DCX app-auth UX-string bundle HTTP boundary.
It exists so unauthenticated app routes can fetch localized UX copy through one shared backend
contract rather than hardcoding English into login and password-reset pages.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from auth.ux.read_dcx_app_auth_ux_strings_bundle import (
    read_dcx_app_auth_ux_strings_bundle_capability,
)

dcx_api_routes_auth_app_ux_strings_bundle_router = APIRouter(prefix="/auth", tags=["auth"])


@dcx_api_routes_auth_app_ux_strings_bundle_router.get("/app-ux-strings-bundle", response_model=None)
def get_dcx_app_auth_ux_strings_bundle(
    language_code: str = Query(default="en"),
):
    """
    CONTRACT:
      preconditions:
        - language_code is one optional requested browser language code.
      postconditions:
        - Returns one canonical success wrapper containing the localized app-auth UX-string bundle.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - App auth pages need localized copy before the user has an authenticated session.
      WHEN TO USE it:
        - Use it from the app login, password-reset-request, and password-set pages.
      WHEN NOT TO USE it:
        - Do not use it for admin auth or authenticated account reads.
      WHAT CAN GO WRONG:
        - Database-backed UX-string reads can fail.
      WHAT COMES NEXT:
        - The frontend can render the requested language and preserve that language across auth transitions.

    TESTS:
      - covered_indirectly_by_app_auth_ux_bundle_route_tests

    ERRORS:
      - API_DCX_APP_AUTH_UX_STRINGS_READ_FAILED:
          suggested_action: Retry after the backend is healthy.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database health.
            - Retry.
          retry_safe: true

    CODE:
    """
    try:
        bundle = read_dcx_app_auth_ux_strings_bundle_capability(language_code=language_code)
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_APP_AUTH_UX_STRINGS_READ_FAILED",
                    "message": "We could not load the app auth UX strings just now.",
                    "suggested_action": "Retry after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": bundle,
        "context": {
            "surface": "app",
            "view": "auth_ux_strings_bundle",
        },
    }
