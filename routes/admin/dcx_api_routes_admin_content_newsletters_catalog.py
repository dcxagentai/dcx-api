"""
CONTEXT:
This file owns the admin-facing newsletters catalog HTTP boundary.
It exists so the admin frontend can browse newsletter content separately from transactional templates.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.newsletters.read_dcx_admin_live_newsletters_catalog import (
    read_dcx_admin_live_newsletters_catalog_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_newsletters_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_newsletters_catalog_router.get(
    "/content/newsletters/catalog",
    response_model=None,
)
def get_dcx_admin_content_newsletters_catalog(
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
      postconditions:
        - Returns a canonical success wrapper containing the live original newsletter-content catalog.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Clients should see newsletter composing as its own content surface, not mixed into transactional templates.
      WHEN TO USE it:
        - Use it from the admin `/content/newsletters` route only.
      WHEN NOT TO USE it:
        - Do not use it for transactional templates or send dispatch.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The detail route can open one newsletter key from this list.

    TESTS:
      - covered_indirectly_by_admin_newsletters_catalog_route_test

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTERS_CATALOG_READ_FAILED:
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
        newsletters_catalog = read_dcx_admin_live_newsletters_catalog_capability()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_NEWSLETTERS_CATALOG_READ_FAILED",
                    "message": "We could not load the DCX newsletters catalog just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": newsletters_catalog,
        "context": {
            "surface": "admin",
            "view": "newsletters_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
