"""
CONTEXT:
This file owns the first admin-facing public-site publish trigger HTTP boundary.
It exists so the admin frontend can request a Cloudflare Pages rebuild after public UX-string
edits land in Postgres and the public Astro build now reads the live bundle from `dcx_api`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)
from admin.publish.public_site.trigger_dcx_admin_public_site_publish_run import (
    trigger_dcx_admin_public_site_publish_run_capability,
)

dcx_api_routes_admin_public_site_publish_run_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_public_site_publish_run_router.post(
    "/publish/public-site/run",
    response_model=None,
)
def post_dcx_admin_public_site_publish_run(
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The backend environment includes a valid Cloudflare Pages deploy hook URL.
      postconditions:
        - Records one attempted publish trigger and calls the configured Cloudflare Pages deploy hook.
        - Returns the canonical success wrapper when the deploy hook accepts the request.
      side_effects:
        - writes publish-state metadata to `stephen_dcx_public_content_publish_state`
        - performs one outbound HTTP POST to the configured Cloudflare Pages deploy hook
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first publish/deploy button needs one explicit backend trigger route after the public
          site switched to build-time reads from the backend/database.
      WHEN TO USE it:
        - Use it from the admin `/publish/public-site` screen only.
      WHEN NOT TO USE it:
        - Do not use it as a substitute for final admin auth/permissions.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The deploy hook can be missing or unavailable.
        - The publish-state table can be missing before its SQL is applied.
      WHAT COMES NEXT:
        - Auth can later protect this route in production while keeping the same publish contract.

    TESTS:
      - test_public_site_publish_run_route_returns_payload_for_authenticated_admin_session

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_PUBLIC_SITE_DEPLOY_HOOK_NOT_CONFIGURED:
          suggested_action: Set DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL on the backend and retry.
          common_causes:
            - missing backend env var
          recovery_steps:
            - Add the deploy hook URL to the backend environment.
            - Redeploy the backend.
            - Retry the publish request.
          retry_safe: true
      - API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_TRIGGER_FAILED:
          suggested_action: Retry after Cloudflare hook/network health is restored.
          common_causes:
            - Cloudflare deploy hook unavailable
            - publish-state table missing
          recovery_steps:
            - Verify the deploy hook URL and publish-state SQL.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    resolved_admin_user_id, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        publish_run_result = trigger_dcx_admin_public_site_publish_run_capability(
            triggered_by_user_id=resolved_admin_user_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code == "API_DCX_ADMIN_PUBLIC_SITE_DEPLOY_HOOK_NOT_CONFIGURED":
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": {
                        "code": error_code,
                        "message": "The public-site Cloudflare deploy hook is not configured on the backend.",
                        "suggested_action": "Set DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL on the backend and retry.",
                    },
                },
            )

        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_TRIGGER_FAILED",
                    "message": "We could not trigger the public-site publish request just now.",
                    "suggested_action": "Retry after the Cloudflare hook and backend are healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": publish_run_result,
        "context": {
            "surface": "admin",
            "view": "public_site_publish_status",
            "operation": "publish_triggered",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
