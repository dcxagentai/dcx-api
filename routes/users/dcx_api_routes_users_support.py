"""
CONTEXT:
This file groups small shared route helpers for the DCX users HTTP boundary modules.
It exists so closely related user route files can share trusted-proxy request parsing without
duplicating the same low-level edge logic in every boundary file.
"""

from __future__ import annotations

import os

from fastapi import Request


def read_public_request_client_ip(request: Request) -> str:
    """
    CONTRACT:
      preconditions:
        - The caller provides one FastAPI request object from the active HTTP boundary.
      postconditions:
        - Returns one best-available client IP string.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Public routes need one shared definition of when trusted proxy headers should be honored.
      WHEN TO USE it:
        - Use it in HTTP boundary files that need client IP values for logging or rate limiting.
      WHEN NOT TO USE it:
        - Do not use it for security trust decisions outside the explicit proxy-header policy.
      WHAT CAN GO WRONG:
        - Misconfigured proxy trust can make the returned IP less useful.
      WHAT COMES NEXT:
        - Later boundary helpers can stay here if they are genuinely shared and still small.

    TESTS:
      - covered_indirectly_by_users_route_tests

    ERRORS:
      - USERS_ROUTE_CLIENT_IP_UNAVAILABLE:
          suggested_action: Fall back to request.client.host when proxy headers are absent.
          common_causes:
            - request came from a local test client
            - trusted proxy headers disabled
          recovery_steps:
            - Use the returned fallback value.
          retry_safe: true

    CODE:
    """
    if os.getenv("DCX_TRUST_PROXY_HEADERS", "").strip().lower() == "true":
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for != "":
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip != "":
            return real_ip

    return request.client.host if request.client is not None else "unknown"
