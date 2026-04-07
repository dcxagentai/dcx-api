"""
CONTEXT:
This file owns the first admin-facing UX-strings content HTTP boundary.
It exists so the admin frontend can browse multilingual UX-string rows without editing them yet.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from admin.content.ux_strings.read_dcx_admin_live_ux_strings_catalog import (
    read_dcx_admin_live_ux_strings_catalog_capability,
)
from routes.admin.dcx_api_routes_admin_support import (
    read_permitted_local_debug_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_ux_strings_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_ux_strings_catalog_router.get(
    "/content/ux-strings/catalog",
    response_model=None,
)
def get_dcx_admin_content_ux_strings_catalog(
    admin_user_id: int | None = Query(default=None, ge=1),
):
    """
    CONTRACT:
      preconditions:
        - Real admin auth is not wired yet, so local development may temporarily supply one
          `admin_user_id` query parameter for screen testing.
      postconditions:
        - Returns a canonical success wrapper containing the live UX-string catalog.
        - Returns a canonical error wrapper when no temporary local admin identity is supplied yet.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin content viewer should let internal users inspect multilingual UX strings
          directly from the durable content table before CRUD is added.
      WHEN TO USE it:
        - Use it from the read-only admin UX-strings viewer only.
      WHEN NOT TO USE it:
        - Do not treat this as the final admin authorization design.
      WHAT CAN GO WRONG:
        - No temporary local admin identity is present yet.
        - Database reads can fail.
      WHAT COMES NEXT:
        - Keep this read contract stable while real admin session and role checks replace the
          temporary debug-identity path.

    TESTS:
      - test_admin_ux_strings_catalog_route_returns_payload_for_local_debug_admin_user_id

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Use `?admin_user_id=` locally until admin auth is connected.
          common_causes:
            - no authenticated admin session yet
          recovery_steps:
            - Add `?admin_user_id=<existing_user_id>` during local development.
          retry_safe: true
      - API_DCX_ADMIN_UX_STRINGS_CATALOG_READ_FAILED:
          suggested_action: Retry after backend/database health is restored.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify backend/database health.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    _, error_response = read_permitted_local_debug_admin_user_id_or_error_response(admin_user_id)
    if error_response is not None:
        return error_response

    try:
        ux_strings_catalog = read_dcx_admin_live_ux_strings_catalog_capability()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_UX_STRINGS_CATALOG_READ_FAILED",
                    "message": "We could not load the live DCX UX-strings catalog just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": ux_strings_catalog,
        "context": {
            "surface": "admin",
            "view": "ux_strings_catalog",
            "identity_resolution_mode": "temporary_admin_user_id_query_parameter",
        },
    }
