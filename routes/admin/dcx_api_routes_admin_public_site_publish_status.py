"""
CONTEXT:
This file owns the first admin-facing public-site publish-status HTTP boundary.
It exists so the admin frontend can see whether public content edits are waiting for the next
Cloudflare Pages rebuild after the public site switched to build-time reads from `dcx_api`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from admin.publish.public_site.read_dcx_admin_public_site_publish_status import (
    read_dcx_admin_public_site_publish_status_capability,
)
from routes.admin.dcx_api_routes_admin_support import (
    read_permitted_local_debug_admin_user_id_or_error_response,
)

dcx_api_routes_admin_public_site_publish_status_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_public_site_publish_status_router.get(
    "/publish/public-site/status",
    response_model=None,
)
def get_dcx_admin_public_site_publish_status(
    admin_user_id: int | None = Query(default=None, ge=1),
):
    """
    CONTRACT:
      preconditions:
        - Real admin auth is not wired yet, so local development may temporarily supply one
          `admin_user_id` query parameter for screen testing.
      postconditions:
        - Returns the canonical success wrapper containing the current public-site publish status.
        - Returns the canonical error wrapper when no temporary local admin identity is supplied yet.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin publish screen needs one explicit backend read contract for the first manual
          public-site deploy loop.
      WHEN TO USE it:
        - Use it from the admin `/publish/public-site` screen only.
      WHEN NOT TO USE it:
        - Do not use it as a replacement for real admin authorization.
      WHAT CAN GO WRONG:
        - No temporary local admin identity is present yet.
        - The publish-state SQL may not be applied yet.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The matching trigger route can request a new Cloudflare Pages rebuild and this status
          route can then reflect the latest accepted publish attempt.

    TESTS:
      - test_public_site_publish_status_route_returns_payload_for_local_debug_admin_user_id

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Use `?admin_user_id=` locally until admin auth is connected.
          common_causes:
            - no authenticated admin session yet
          recovery_steps:
            - Add `?admin_user_id=<existing_user_id>` during local development.
          retry_safe: true
      - API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_STATUS_READ_FAILED:
          suggested_action: Confirm the publish-state table exists and retry after backend/database health is restored.
          common_causes:
            - publish-state SQL not applied yet
            - database unavailable
          recovery_steps:
            - Apply the publish-state SQL.
            - Retry after backend health is restored.
          retry_safe: true

    CODE:
    """
    _, error_response = read_permitted_local_debug_admin_user_id_or_error_response(admin_user_id)
    if error_response is not None:
        return error_response

    try:
        publish_status = read_dcx_admin_public_site_publish_status_capability()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_STATUS_READ_FAILED",
                    "message": "We could not load the public-site publish status just now.",
                    "suggested_action": "Apply the publish-state SQL if needed, then retry after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": publish_status,
        "context": {
            "surface": "admin",
            "view": "public_site_publish_status",
            "identity_resolution_mode": "temporary_admin_user_id_query_parameter",
        },
    }
