"""
CONTEXT:
This capability validates one build-time token and returns a tiny proof payload for Astro builds.
It exists so we can verify that local Astro builds and Cloudflare Pages Astro builds can securely
fetch data from `dcx_api` during static generation before we refactor the real public UX-string
bundle away from the generated TypeScript snapshot.
"""

from __future__ import annotations

import hmac
import os
import time

from routes.users.dcx_api_routes_users_support import read_dcx_runtime_environment


def read_dcx_public_build_time_api_test_payload_capability(
    provided_build_token: str | None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The caller provides the incoming build token from the dedicated public-build boundary.
        - The backend environment config includes a non-empty `DCX_PUBLIC_BUILD_API_TOKEN`.
      postconditions:
        - Returns one small canonical payload proving the backend accepted a secure build-time read.
        - Rejects missing or invalid tokens without touching database state.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - We need a narrow proof that Astro can fetch from the backend at build time before we
          replace the committed generated UX-string bundle.
        - The proof should be production-safe, so it must not expose an unauthenticated build-only route.
      WHEN TO USE it:
        - Use it from one temporary Astro build-time test page or one deployment smoke test.
      WHEN NOT TO USE it:
        - Do not use it for runtime browser fetches.
        - Do not use it as the real public UX-string export contract.
      WHAT CAN GO WRONG:
        - The build token can be missing locally or in Cloudflare Pages.
        - The token can be set differently between the public build and the backend.
      WHAT COMES NEXT:
        - Once this build-time fetch path is proven, add the real live public UX-string bundle route
          behind the same token pattern and remove the generated-file dependency.

    TESTS:
      - returns_build_time_test_payload_for_matching_token
      - raises_when_backend_build_token_missing
      - raises_when_request_token_missing
      - raises_when_request_token_invalid

    ERRORS:
      - API_PUBLIC_BUILD_TOKEN_NOT_CONFIGURED:
          suggested_action: Set the same non-empty build token in the backend environment before retrying the build.
          common_causes:
            - missing local `.env` value
            - missing Render production env value
          recovery_steps:
            - Add `DCX_PUBLIC_BUILD_API_TOKEN` to the backend environment.
            - Restart or redeploy the backend.
          retry_safe: true
      - API_PUBLIC_BUILD_TOKEN_REQUIRED:
          suggested_action: Configure the Astro build to send the required build token header.
          common_causes:
            - missing frontend env variable
            - fetch helper forgot the header
          recovery_steps:
            - Add the frontend build token env value.
            - Retry the build.
          retry_safe: true
      - API_PUBLIC_BUILD_TOKEN_INVALID:
          suggested_action: Confirm the frontend build token exactly matches the backend token and retry.
          common_causes:
            - mismatched local and backend env values
            - stale Cloudflare Pages secret
          recovery_steps:
            - Compare the frontend and backend token values.
            - Redeploy after correcting the mismatch.
          retry_safe: true

    CODE:
    """
    configured_build_token = os.getenv("DCX_PUBLIC_BUILD_API_TOKEN", "").strip()
    if configured_build_token == "":
        raise RuntimeError("API_PUBLIC_BUILD_TOKEN_NOT_CONFIGURED")

    normalized_provided_build_token = (provided_build_token or "").strip()
    if normalized_provided_build_token == "":
        raise RuntimeError("API_PUBLIC_BUILD_TOKEN_REQUIRED")

    if not hmac.compare_digest(normalized_provided_build_token, configured_build_token):
        raise RuntimeError("API_PUBLIC_BUILD_TOKEN_INVALID")

    return {
        "build_test_message": (
            "DCX public Astro builds can securely fetch from dcx_api during static generation."
        ),
        "backend_runtime_environment": read_dcx_runtime_environment(),
        "issued_at_ts_ms": int(time.time() * 1000),
    }
