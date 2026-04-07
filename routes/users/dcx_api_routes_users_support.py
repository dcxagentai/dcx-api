"""
CONTEXT:
This file groups small shared route helpers for the DCX users HTTP boundary modules.
It exists so closely related user route files can share trusted-proxy request parsing without
duplicating the same low-level edge logic in every boundary file.
"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse


def read_public_request_client_ip(request: Request) -> str:
    """
    CONTRACT:
      preconditions:
        - The caller provides one FastAPI request object from the active HTTP boundary.
      postconditions:
        - Returns one best-available client IP string.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Public routes need one shared definition of when trusted proxy headers should be honored.
      WHEN TO USE it:
        - Use it in HTTP boundary files that need client IP values for logging or rate limiting.
      WHEN NOT TO USE it:
        - Do not use it for security trust decisions outside the explicit proxy-header policy.
      WHAT CAN GO WRONG:
        - Misconfigured proxy trust can make the returned IP less useful.
      WHAT COMES NEXT:
        - Later boundary helpers can stay here if they are genuinely shared and still small.

    TESTS:
      - covered_indirectly_by_users_route_tests

    ERRORS:
      - USERS_ROUTE_CLIENT_IP_UNAVAILABLE:
          suggested_action: Fall back to request.client.host when proxy headers are absent.
          common_causes:
            - request came from a local test client
            - trusted proxy headers disabled
          recovery_steps:
            - Use the returned fallback value.
          retry_safe: true

    CODE:
    """
    if os.getenv("DCX_TRUST_PROXY_HEADERS", "").strip().lower() == "true":
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for != "":
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip != "":
            return real_ip

    return request.client.host if request.client is not None else "unknown"


def read_dcx_runtime_environment() -> str:
    """
    CONTRACT:
      preconditions:
        - none
      postconditions:
        - Returns one normalized DCX runtime environment label.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Multiple route families need one shared understanding of whether the backend is running
          in local/development or in a hosted environment.
      WHEN TO USE it:
        - Use it when a boundary temporarily allows local-only debug behavior.
      WHEN NOT TO USE it:
        - Do not treat it as a replacement for real authorization checks.
      WHAT CAN GO WRONG:
        - Misconfigured environment labels can leave temporary debug affordances enabled too broadly.
      WHAT COMES NEXT:
        - Real auth can replace local-debug route behavior while keeping this helper for other env-sensitive wiring.

    TESTS:
      - covered_indirectly_by_app_account_route_tests

    ERRORS: []

    CODE:
    """
    return os.getenv("DCX_ENVIRONMENT", "local").strip().lower() or "local"


def read_allowed_dcx_frontend_origins() -> set[str]:
    """
    CONTRACT:
      preconditions:
        - Frontend-origin environment variables may or may not be present.
      postconditions:
        - Returns the union of explicitly configured frontend origins and the safe local defaults
          needed during MVP development.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The API is now serving multiple browser surfaces, not just the public site.
      WHEN TO USE it:
        - Use it for application-wide CORS middleware configuration.
      WHEN NOT TO USE it:
        - Do not use it as the source of truth for signup-origin validation; the public signup flow
          still owns its stricter allowlist separately.
      WHAT CAN GO WRONG:
        - Missing hosted app/admin origins can block browser fetches even though the backend route exists.
      WHAT COMES NEXT:
        - Add the hosted app/admin origins explicitly through environment configuration before
          authenticated surfaces go fully live.

    TESTS:
      - covered_indirectly_by_app_and_root_cors_tests

    ERRORS: []

    CODE:
    """
    configured_additional_origins = {
        candidate.strip()
        for candidate in os.getenv("DCX_FRONTEND_ADDITIONAL_ALLOWED_ORIGINS", "").split(",")
        if candidate.strip() != ""
    }

    local_development_origins = set()
    if read_dcx_runtime_environment() in {"local", "development"}:
        local_development_origins = {
            "http://localhost:4321",
            "http://127.0.0.1:4321",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:4174",
            "http://127.0.0.1:4174",
            "https://dcx-public.pages.dev",
            "https://dcx-app.pages.dev",
            "https://dcx-admin.pages.dev",
        }

    return configured_additional_origins | local_development_origins


def read_permitted_local_debug_user_id_or_error_response(
    user_id: int | None,
) -> tuple[int | None, JSONResponse | None]:
    """
    CONTRACT:
      preconditions:
        - The caller provides the optional temporary `user_id` query parameter from one
          app-facing HTTP boundary.
      postconditions:
        - Returns the permitted local debug user id when temporary local testing is allowed.
        - Returns one canonical error response when no temporary user identity is available or
          when the temporary debug path is attempted outside local/development.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first app-facing account routes all need the same temporary identity rule before durable auth exists.
      WHEN TO USE it:
        - Use it in app HTTP boundaries that are temporarily testable with `?user_id=`.
      WHEN NOT TO USE it:
        - Do not mistake this for real user authentication.
      WHAT CAN GO WRONG:
        - The frontend forgets to supply the debug user id locally.
        - The temporary debug path is accidentally attempted in a hosted environment.
      WHAT COMES NEXT:
        - Replace this helper with real session-backed identity while keeping route contracts stable.

    TESTS:
      - covered_indirectly_by_app_route_tests_in_dcx_api_app_test

    ERRORS:
      - API_USERS_ME_AUTH_REQUIRED:
          suggested_action: Use `?user_id=<existing_user_id>` locally until app auth is connected.
          common_causes:
            - no authenticated app session yet
          recovery_steps:
            - Add `?user_id=<existing_user_id>` during local development.
          retry_safe: true
      - API_USERS_ME_DEBUG_USER_ID_FORBIDDEN:
          suggested_action: Remove the debug parameter and use the real authenticated account flow.
          common_causes:
            - local-only debug behavior attempted in staging or production
          recovery_steps:
            - Remove the query parameter.
            - Retry through the real app auth flow once it exists.
          retry_safe: true

    CODE:
    """
    if user_id is None:
        return None, JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_AUTH_REQUIRED",
                    "message": "No authenticated DCX app user is available yet.",
                    "suggested_action": "Use ?user_id=<existing_user_id> locally until app auth is connected.",
                },
            },
        )

    if read_dcx_runtime_environment() not in {"local", "development"}:
        return None, JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_DEBUG_USER_ID_FORBIDDEN",
                    "message": "The temporary debug user_id path is only allowed in local development.",
                    "suggested_action": "Remove the debug parameter and use the real authenticated account flow.",
                },
            },
        )

    return user_id, None
