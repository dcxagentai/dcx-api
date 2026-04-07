"""
CONTEXT:
This file exposes one narrow token-gated public-build proof route under `/public/build-time`.
It exists so we can verify that Astro static builds can securely fetch from `dcx_api` during local
and Cloudflare Pages builds before replacing the generated public UX-string snapshot workflow.
"""

from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from public_site.build.read_dcx_public_build_time_api_test_payload import (
    read_dcx_public_build_time_api_test_payload_capability,
)

dcx_api_routes_public_build_time_api_test_router = APIRouter(
    prefix="/public/build-time",
    tags=["public_build_time"],
)


@dcx_api_routes_public_build_time_api_test_router.get("/api-test")
def get_dcx_public_build_time_api_test_payload(
    x_dcx_public_build_token: str | None = Header(default=None),
) -> JSONResponse:
    """
    CONTRACT:
      preconditions:
        - The caller provides the `X-DCX-Public-Build-Token` header.
        - The backend environment config includes `DCX_PUBLIC_BUILD_API_TOKEN`.
      postconditions:
        - Returns one canonical success wrapper containing a small build-time proof payload.
        - Returns one canonical error wrapper when the build token is missing, invalid, or unconfigured.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The next public-content publish step depends on knowing whether Astro builds can securely read from `dcx_api`.
        - This route proves the network and token path first, before we move real content onto it.
      WHEN TO USE it:
        - Use it only from build-time fetch helpers and deployment smoke tests.
      WHEN NOT TO USE it:
        - Do not use it from browser runtime code.
        - Do not keep this as the long-term public UX-string delivery contract.
      WHAT CAN GO WRONG:
        - Missing or mismatched build token secrets can make the build fail.
        - If the API is down during a Cloudflare Pages build, the build should fail loudly.
      WHAT COMES NEXT:
        - Add the real token-gated public UX-string bundle route and point Astro at that live backend data.

    TESTS:
      - build_time_api_test_route_returns_payload_for_valid_token
      - build_time_api_test_route_rejects_missing_token
      - build_time_api_test_route_rejects_invalid_token

    ERRORS:
      - API_PUBLIC_BUILD_TOKEN_NOT_CONFIGURED:
          suggested_action: Set the backend build token env var and retry the Astro build.
          common_causes:
            - missing backend secret
          recovery_steps:
            - Add `DCX_PUBLIC_BUILD_API_TOKEN` to the backend environment.
            - Restart or redeploy the backend.
          retry_safe: true
      - API_PUBLIC_BUILD_TOKEN_REQUIRED:
          suggested_action: Configure the Astro build to send the token header.
          common_causes:
            - missing frontend build env value
          recovery_steps:
            - Add the frontend build token env value.
            - Retry the build.
          retry_safe: true
      - API_PUBLIC_BUILD_TOKEN_INVALID:
          suggested_action: Make the frontend build token exactly match the backend token and retry.
          common_causes:
            - env mismatch between frontend and backend
          recovery_steps:
            - Compare both token values.
            - Redeploy after correcting the mismatch.
          retry_safe: true

    CODE:
    """
    try:
        payload = read_dcx_public_build_time_api_test_payload_capability(
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
                "error": _map_dcx_public_build_time_api_test_error(error_code),
            },
        )

    return JSONResponse(
        content={
            "ok": True,
            "data": payload,
            "context": {
                "what_happened": "The backend accepted one secure build-time proof read for the DCX public Astro build.",
                "side_effects_executed": [],
                "next_steps": [
                    "Wire the real public UX-string bundle onto the same build-time fetch pattern.",
                ],
                "related_operations": [
                    "read_dcx_public_build_time_api_test_payload_capability",
                ],
            },
        }
    )


def _map_dcx_public_build_time_api_test_error(error_code: str) -> dict:
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

    return {
        "code": "API_PUBLIC_BUILD_TIME_API_TEST_FAILED",
        "message": "We could not complete the secure public build-time API test.",
        "suggested_action": "Retry once the backend build route is healthy.",
    }
