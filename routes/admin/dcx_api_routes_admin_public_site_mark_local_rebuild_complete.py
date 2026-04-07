"""
CONTEXT:
This file owns the first admin-facing local public-site rebuild-complete HTTP boundary.
It exists so local development can acknowledge a manual dcx_public rebuild and reset the pending
public-change baseline without calling Cloudflare Pages.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from admin.publish.public_site.mark_dcx_admin_public_site_local_rebuild_complete import (
    mark_dcx_admin_public_site_local_rebuild_complete_capability,
)
from routes.admin.dcx_api_routes_admin_support import (
    read_permitted_local_debug_admin_user_id_or_error_response,
)

dcx_api_routes_admin_public_site_mark_local_rebuild_complete_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_public_site_mark_local_rebuild_complete_router.post(
    "/publish/public-site/mark-local-rebuild-complete",
    response_model=None,
)
def post_dcx_admin_public_site_mark_local_rebuild_complete(
    admin_user_id: int | None = Query(default=None, ge=1),
):
    """
    CONTRACT:
      preconditions:
        - Real admin auth is not wired yet, so local development may temporarily supply one
          `admin_user_id` query parameter for screen testing.
        - The backend runtime environment is `local` or `development`.
      postconditions:
        - Records one local rebuild completion and advances the accepted publish baseline.
        - Returns the canonical success wrapper when the acknowledgement is recorded.
      side_effects:
        - writes publish-state metadata to `stephen_dcx_public_content_publish_state`
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Local development should not trigger Cloudflare, but it still needs a way to mark that a
          manual `dcx_public` rebuild has happened.
      WHEN TO USE it:
        - Use it only after manually rebuilding or refreshing the local `dcx_public` frontend.
      WHEN NOT TO USE it:
        - Do not use it in hosted environments.
      WHAT CAN GO WRONG:
        - No temporary local admin identity is present yet.
        - The route can be called outside local/development.
        - The publish-state SQL may not be applied yet.
      WHAT COMES NEXT:
        - The publish status screen can then show zero pending changes until the next content edit lands.

    TESTS:
      - test_mark_local_rebuild_complete_route_returns_payload_for_local_debug_admin_user_id

    ERRORS:
      - API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FORBIDDEN:
          suggested_action: Use the hosted publish flow outside local development.
          common_causes:
            - route called in production or staging
          recovery_steps:
            - Trigger the normal hosted publish flow instead.
          retry_safe: true
      - API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FAILED:
          suggested_action: Confirm the publish-state SQL exists and retry after backend/database health is restored.
          common_causes:
            - publish-state table missing
            - database unavailable
          recovery_steps:
            - Apply the publish-state SQL.
            - Retry after backend health is restored.
          retry_safe: true

    CODE:
    """
    resolved_admin_user_id, error_response = read_permitted_local_debug_admin_user_id_or_error_response(
        admin_user_id
    )
    if error_response is not None:
        return error_response

    try:
        mark_complete_result = mark_dcx_admin_public_site_local_rebuild_complete_capability(
            completed_by_user_id=resolved_admin_user_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code == "API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FORBIDDEN":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "Local rebuild completion is only available in local development.",
                        "suggested_action": "Use the hosted publish flow outside local development.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FAILED",
                    "message": "We could not record the local public rebuild completion just now.",
                    "suggested_action": "Apply the publish-state SQL if needed, then retry after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": mark_complete_result,
        "context": {
            "surface": "admin",
            "view": "public_site_publish_status",
            "operation": "local_rebuild_completed",
            "identity_resolution_mode": "temporary_admin_user_id_query_parameter",
        },
    }
