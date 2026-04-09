"""
CONTEXT:
This file owns the admin-facing content-page categories catalog HTTP boundary.
It exists so the admin page list/editor can read category choices from the durable content table.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.pages.read_dcx_admin_live_content_page_categories_catalog import (
    read_dcx_admin_live_content_page_categories_catalog_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_categories_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_page_categories_catalog_router.get(
    "/content/pages/categories",
    response_model=None,
)
def get_dcx_admin_content_page_categories_catalog(
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
      postconditions:
        - Returns a canonical success wrapper containing the live content-page category catalog.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin pages surface should not hardcode categories.
      WHEN TO USE it:
        - Use it from the admin pages list and editor only.
      WHEN NOT TO USE it:
        - Do not use it as the public build source of truth.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The page editor can render one stable category dropdown from this response.

    TESTS:
      - covered_indirectly_by_admin_content_page_categories_catalog_route_test

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_CATEGORIES_CATALOG_READ_FAILED:
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
        categories_catalog = read_dcx_admin_live_content_page_categories_catalog_capability()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_CONTENT_PAGE_CATEGORIES_CATALOG_READ_FAILED",
                    "message": "We could not load the DCX content page categories just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": categories_catalog,
        "context": {
            "surface": "admin",
            "view": "content_page_categories_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
