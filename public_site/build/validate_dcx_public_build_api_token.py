"""
CONTEXT:
This capability validates the shared token used by `dcx_public` Astro builds when they fetch from
`dcx_api` during static generation.
It exists so multiple build-time public routes can share one secure token gate without repeating
inline secret-comparison logic.
"""

from __future__ import annotations

import hmac
import os


def validate_dcx_public_build_api_token_capability(
    provided_build_token: str | None,
) -> None:
    """
    CONTRACT:
      preconditions:
        - The backend environment may define `DCX_PUBLIC_BUILD_API_TOKEN`.
        - The caller provides the incoming build token from the request header.
      postconditions:
        - Returns `None` when the configured backend build token exists and matches exactly.
        - Raises one stable runtime error code when the token is missing, unconfigured, or invalid.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Multiple public build-time routes need the same secure gate.
        - The build token must never leak into browser runtime code, but it should still be
          enforced consistently for Astro static generation.
      WHEN TO USE it:
        - Use it in backend capability or route code that services build-time `dcx_public` requests.
      WHEN NOT TO USE it:
        - Do not use it as a replacement for real user or admin auth.
        - Do not use it for browser runtime API routes.
      WHAT CAN GO WRONG:
        - The backend token can be unset.
        - The frontend build token can be missing or mismatched.
      WHAT COMES NEXT:
        - Reuse this guard for the real live public UX-string bundle route and later publish-trigger
          support routes if they need the same machine-to-machine secret.

    TESTS:
      - returns_none_for_matching_token
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
