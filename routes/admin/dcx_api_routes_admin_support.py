"""
CONTEXT:
This file groups small shared route helpers for the DCX admin HTTP boundary modules.
It exists so closely related admin route files can share the same temporary local-debug
admin identity gate while the real admin auth and role system is still being built.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

from routes.users.dcx_api_routes_users_support import read_dcx_runtime_environment


def read_permitted_local_debug_admin_user_id_or_error_response(
    admin_user_id: int | None,
) -> tuple[int | None, JSONResponse | None]:
    """
    CONTRACT:
      preconditions:
        - The caller provides the optional temporary `admin_user_id` query parameter from one
          admin-facing HTTP boundary.
      postconditions:
        - Returns the permitted local debug admin user id when temporary local testing is allowed.
        - Returns one canonical error response when no temporary admin identity is available or
          when the temporary debug path is attempted outside local/development.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin surfaces all need the same temporary identity rule before durable auth exists.
      WHEN TO USE it:
        - Use it in admin HTTP boundaries that are temporarily testable with `?admin_user_id=`.
      WHEN NOT TO USE it:
        - Do not mistake this for real admin authorization or role enforcement.
      WHAT CAN GO WRONG:
        - The frontend forgets to supply the debug admin id locally.
        - The temporary debug path is accidentally attempted in a hosted environment.
      WHAT COMES NEXT:
        - Replace this helper with real session-backed identity and admin-role checks while keeping
          the route contracts stable.

    TESTS:
      - covered_indirectly_by_admin_route_tests_in_dcx_api_app_test

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Use `?admin_user_id=<existing_user_id>` locally until admin auth is connected.
          common_causes:
            - no authenticated admin session yet
          recovery_steps:
            - Add `?admin_user_id=<existing_user_id>` during local development.
          retry_safe: true
      - API_DCX_ADMIN_DEBUG_USER_ID_FORBIDDEN:
          suggested_action: Remove the debug parameter and use the real authenticated admin flow.
          common_causes:
            - local-only debug behavior attempted in staging or production
          recovery_steps:
            - Remove the query parameter.
            - Retry through the real admin auth flow once it exists.
          retry_safe: true

    CODE:
    """
    if admin_user_id is None:
        return None, JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_AUTH_REQUIRED",
                    "message": "No authenticated DCX admin user is available yet.",
                    "suggested_action": "Use ?admin_user_id=<existing_user_id> locally until admin auth is connected.",
                },
            },
        )

    if read_dcx_runtime_environment() not in {"local", "development"}:
        return None, JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_DEBUG_USER_ID_FORBIDDEN",
                    "message": "The temporary debug admin_user_id path is only allowed in local development.",
                    "suggested_action": "Remove the debug parameter and use the real authenticated admin flow.",
                },
            },
        )

    return admin_user_id, None
