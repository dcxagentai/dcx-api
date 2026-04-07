"""
CONTEXT:
This capability validates one public-build token and returns the live public UX-string bundle for
Astro static generation.
It exists so `dcx_public` can treat the live backend/database as the source of truth at build time
without introducing runtime browser fetches or request-time SSR.
"""

from __future__ import annotations

from languages.read_live_dcx_public_ux_strings_bundle import (
    read_live_dcx_public_ux_strings_bundle,
)
from public_site.build.validate_dcx_public_build_api_token import (
    validate_dcx_public_build_api_token_capability,
)


def read_dcx_public_build_time_ux_strings_bundle_capability(
    provided_build_token: str | None,
) -> dict[str, dict[str, dict[str, str]]]:
    """
    CONTRACT:
      preconditions:
        - The caller provides the incoming build token from the dedicated public-build boundary.
        - The backend environment config includes a non-empty `DCX_PUBLIC_BUILD_API_TOKEN`.
        - The live public UX-string capability can read the configured database.
      postconditions:
        - Returns the current live public UX-string bundle for all supported public languages and groups.
        - Rejects missing or invalid tokens before returning any content.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The committed generated TypeScript snapshot is no longer the right source of truth once
          admin editing exists.
        - The public site should still build statically, but from live backend data at build time.
      WHEN TO USE it:
        - Use it from Astro build-time fetch helpers and deploy-time smoke checks.
      WHEN NOT TO USE it:
        - Do not call it from browser runtime code.
        - Do not use it for app/admin UX-string groups.
      WHAT CAN GO WRONG:
        - The build token can be missing or mismatched.
        - The database can be unavailable during the build.
      WHAT COMES NEXT:
        - Replace the remaining generated-file imports in `dcx_public`.
        - Add publish-status and deploy-trigger surfaces once the static build source is fully live.

    TESTS:
      - returns_live_public_bundle_for_matching_token
      - raises_when_token_validation_fails
      - raises_when_live_public_bundle_reader_fails

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
          suggested_action: Make the frontend and backend build tokens match exactly and retry.
          common_causes:
            - env mismatch between frontend and backend
          recovery_steps:
            - Compare both token values.
            - Redeploy after correcting the mismatch.
          retry_safe: true
      - API_PUBLIC_UX_STRINGS_DB_UNAVAILABLE:
          suggested_action: Restore database connectivity, then retry the public build.
          common_causes:
            - backend database outage
            - wrong DB configuration
          recovery_steps:
            - Check DB connectivity from `dcx_api`.
            - Retry after the database is healthy.
          retry_safe: true

    CODE:
    """
    validate_dcx_public_build_api_token_capability(provided_build_token)
    return read_live_dcx_public_ux_strings_bundle()
