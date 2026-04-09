"""
CONTEXT:
This file owns the admin-facing content-pages catalog HTTP boundary.
It exists so the admin pages surface can browse one stable list of current page identities.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.pages.read_dcx_admin_live_content_pages_catalog import (
    read_dcx_admin_live_content_pages_catalog_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_pages_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_pages_catalog_router.get(
    "/content/pages/catalog",
    response_model=None,
)
def get_dcx_admin_content_pages_catalog(
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
      postconditions:
        - Returns a canonical success wrapper containing the live original content-pages catalog.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin pages surface should begin from one stable list of page identities.
      WHEN TO USE it:
        - Use it from the admin `/content/pages` route only.
      WHEN NOT TO USE it:
        - Do not use it for public page builds.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The editor route can open one page key from this list.

    TESTS:
      - covered_indirectly_by_admin_content_pages_catalog_route_test

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGES_CATALOG_READ_FAILED:
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
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        pages_catalog = read_dcx_admin_live_content_pages_catalog_capability()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_CONTENT_PAGES_CATALOG_READ_FAILED",
                    "message": "We could not load the DCX content pages just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": pages_catalog,
        "context": {
            "surface": "admin",
            "view": "content_pages_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
