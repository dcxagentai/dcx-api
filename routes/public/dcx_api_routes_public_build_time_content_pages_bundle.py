"""
CONTEXT:
This file exposes the token-gated live public content-pages bundle route under `/public/build-time`.
It exists so `dcx_public` Astro builds can read the current live published content pages directly
from `dcx_api` during static generation.
"""

from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from public_site.build.read_dcx_public_build_time_content_pages_bundle import (
    read_dcx_public_build_time_content_pages_bundle_capability,
)

dcx_api_routes_public_build_time_content_pages_bundle_router = APIRouter(
    prefix="/public/build-time",
    tags=["public_build_time"],
)


@dcx_api_routes_public_build_time_content_pages_bundle_router.get("/content-pages-bundle")
def get_dcx_public_build_time_content_pages_bundle(
    x_dcx_public_build_token: str | None = Header(default=None),
) -> JSONResponse:
    """
    CONTRACT:
      preconditions:
        - The caller provides the `X-DCX-Public-Build-Token` header.
        - The backend environment config includes `DCX_PUBLIC_BUILD_API_TOKEN`.
      postconditions:
        - Returns one canonical success wrapper containing the current live published content-pages bundle.
        - Returns one canonical error wrapper when token validation or bundle reading fails.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The public site should build real published category/page routes from the live database-backed content model.
      WHEN TO USE it:
        - Use it only from Astro build-time code and deployment smoke tests.
      WHEN NOT TO USE it:
        - Do not call it from browser runtime code.
      WHAT CAN GO WRONG:
        - The build token can be missing or mismatched.
        - The database can be unavailable while Cloudflare Pages is building.
      WHAT COMES NEXT:
        - Point the public Astro category/page routes at this bundle and fold it into publish-status counting.

    TESTS:
      - covered_indirectly_by_public_build_time_content_pages_bundle_route_test

    ERRORS:
      - API_PUBLIC_BUILD_TOKEN_NOT_CONFIGURED:
          suggested_action: Set the backend build token env var and retry the public build.
          common_causes:
            - missing backend secret
          recovery_steps:
            - Add `DCX_PUBLIC_BUILD_API_TOKEN` to the backend environment.
            - Restart or redeploy the backend.
          retry_safe: true
      - API_PUBLIC_BUILD_TOKEN_REQUIRED:
          suggested_action: Configure the Astro build helper to send the token header.
          common_causes:
            - missing frontend build env value
          recovery_steps:
            - Add the frontend build token env value.
            - Retry the build.
          retry_safe: true
      - API_PUBLIC_BUILD_TOKEN_INVALID:
          suggested_action: Confirm the frontend and backend build tokens match exactly and retry.
          common_causes:
            - mismatched build secrets
          recovery_steps:
            - Compare both token values.
            - Retry after correcting the mismatch.
          retry_safe: true

    CODE:
    """
    try:
        bundle = read_dcx_public_build_time_content_pages_bundle_capability(
            x_dcx_public_build_token
        )
    except RuntimeError as exc:
        error_code = str(exc)
        return JSONResponse(
            status_code=401
            if error_code in {
                "API_PUBLIC_BUILD_TOKEN_REQUIRED",
                "API_PUBLIC_BUILD_TOKEN_INVALID",
            }
            else 503,
            content={
                "ok": False,
                "error": _map_dcx_public_build_time_content_pages_bundle_error(error_code),
            },
        )

    return JSONResponse(
        content={
            "ok": True,
            "data": {
                "bundle": bundle,
            },
            "context": {
                "what_happened": "The backend returned the current live published content-pages bundle for Astro static generation.",
                "side_effects_executed": [],
                "next_steps": [
                    "Continue the public build using the returned published content-pages bundle.",
                ],
                "related_operations": [
                    "read_dcx_public_build_time_content_pages_bundle_capability",
                ],
            },
        }
    )


def _map_dcx_public_build_time_content_pages_bundle_error(error_code: str) -> dict:
    if error_code == "API_PUBLIC_BUILD_TOKEN_NOT_CONFIGURED":
        return {
            "code": error_code,
            "message": "The public build token is not configured on the backend.",
            "suggested_action": "Set DCX_PUBLIC_BUILD_API_TOKEN on the backend and retry the build.",
        }

    if error_code == "API_PUBLIC_BUILD_TOKEN_REQUIRED":
        return {
            "code": error_code,
            "message": "The public build token header is required.",
            "suggested_action": "Configure the Astro build to send X-DCX-Public-Build-Token and retry.",
        }

    if error_code == "API_PUBLIC_BUILD_TOKEN_INVALID":
        return {
            "code": error_code,
            "message": "The provided public build token is invalid.",
            "suggested_action": "Confirm the frontend and backend build tokens match exactly and retry.",
        }

    if error_code == "API_PUBLIC_CONTENT_PAGES_DB_UNAVAILABLE":
        return {
            "code": error_code,
            "message": "The backend could not read the live published content pages from the database.",
            "suggested_action": "Restore database connectivity and retry the public build.",
        }

    return {
        "code": "API_PUBLIC_BUILD_TIME_CONTENT_PAGES_BUNDLE_FAILED",
        "message": "We could not read the live public content-pages bundle for the public build.",
        "suggested_action": "Retry once the backend build route is healthy.",
    }
