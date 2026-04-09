"""
CONTEXT:
This file validates one browser Origin header against the frontend origins DCX explicitly owns.
It exists so cookie-authenticated and password-auth browser POST routes can reject cross-origin
state changes from unknown websites instead of relying only on SameSite cookie behavior.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from routes.users.dcx_api_routes_users_support import read_allowed_dcx_frontend_origins


def read_allowed_dcx_frontend_origin_or_error_response(
    request: Request,
) -> tuple[str | None, JSONResponse | None]:
    """
    CONTRACT:
      preconditions:
        - request is one browser-facing HTTP request expected to come from a DCX-owned frontend.
      postconditions:
        - Returns one normalized allowed origin string when the request Origin is present and owned by DCX.
        - Returns one canonical error response when the Origin header is missing or not allowed.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Browser routes that create sessions or mutate authenticated state should reject requests
          from arbitrary origins, even when cookies are already hardened.
      WHEN TO USE it:
        - Use it at the top of browser POST boundaries for app/admin/shared-auth routes.
      WHEN NOT TO USE it:
        - Do not use it for the public signup routes; they already own their stricter origin policy.
        - Do not use it for non-browser server-to-server routes.
      WHAT CAN GO WRONG:
        - A missing hosted origin env var can block legitimate browser requests.
        - Browsers without an Origin header should be rejected for these POST routes.
      WHAT COMES NEXT:
        - Route handlers can continue only after this helper confirms the request came from one of
          our controlled browser surfaces.

    TESTS:
      - covered_indirectly_by_authenticated_browser_post_route_tests

    ERRORS:
      - API_DCX_FRONTEND_ORIGIN_FORBIDDEN:
          suggested_action: Retry the request from an allowed DCX frontend origin.
          common_causes:
            - missing Origin header
            - request sent from an unexpected website
            - backend frontend-origin allowlist not configured for the current hostname
          recovery_steps:
            - Open the intended app, admin, or public frontend directly.
            - Confirm the backend allowlist includes that hostname.
            - Retry from the proper surface.
          retry_safe: true

    CODE:
    """
    normalized_origin = request.headers.get("origin", "").strip()
    if normalized_origin == "":
        return None, JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_FRONTEND_ORIGIN_FORBIDDEN",
                    "message": "This browser request did not come from an allowed DCX frontend origin.",
                    "suggested_action": "Retry the request from an allowed DCX frontend origin.",
                },
            },
        )

    if normalized_origin not in read_allowed_dcx_frontend_origins():
        return None, JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_FRONTEND_ORIGIN_FORBIDDEN",
                    "message": "This browser request did not come from an allowed DCX frontend origin.",
                    "suggested_action": "Retry the request from an allowed DCX frontend origin.",
                },
            },
        )

    return normalized_origin, None
