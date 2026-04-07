"""
CONTEXT:
This file resolves the cookie settings for DCX authenticated browser sessions.
It exists so login, logout, and session reads all use one consistent cookie contract across
`app.dcxagent.ai`, `admin.dcxagent.ai`, and local development.
"""

from __future__ import annotations

import os


def read_dcx_auth_session_cookie_settings() -> dict:
    """
    CONTRACT:
      preconditions:
        - Optional auth cookie environment variables may or may not be present.
      postconditions:
        - Returns one normalized cookie-settings dictionary for DCX browser auth sessions.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - App and admin should share one session cookie shape.
      WHEN TO USE it:
        - Use it when setting, clearing, or reading the auth session cookie.
      WHEN NOT TO USE it:
        - Do not use it for public build-time API tokens.
      WHAT CAN GO WRONG:
        - Wrong cookie domain can stop subdomain sharing.
        - Wrong secure flag can break local development or weaken hosted cookies.
      WHAT COMES NEXT:
        - Real auth routes and browser fetches can all rely on one session-cookie contract.

    TESTS:
      - cookie_settings_default_for_local_runtime

    ERRORS: []

    CODE:
    """
    runtime_environment = os.getenv("DCX_ENVIRONMENT", "local").strip().lower() or "local"
    raw_cookie_domain = os.getenv("DCX_AUTH_SESSION_COOKIE_DOMAIN", "").strip()
    raw_cookie_name = os.getenv("DCX_AUTH_SESSION_COOKIE_NAME", "").strip()
    raw_same_site = os.getenv("DCX_AUTH_SESSION_COOKIE_SAMESITE", "").strip().lower()
    raw_ttl_hours = os.getenv("DCX_AUTH_SESSION_TTL_HOURS", "").strip()
    raw_secure_override = os.getenv("DCX_AUTH_SESSION_COOKIE_SECURE", "").strip().lower()

    max_age_seconds = int(raw_ttl_hours) * 60 * 60 if raw_ttl_hours.isdigit() else 14 * 24 * 60 * 60
    secure_default = runtime_environment not in {"local", "development"}
    secure = (
        raw_secure_override == "true"
        if raw_secure_override in {"true", "false"}
        else secure_default
    )

    return {
        "cookie_name": raw_cookie_name or "dcx_session",
        "cookie_domain": raw_cookie_domain or None,
        "cookie_path": "/",
        "cookie_secure": secure,
        "cookie_http_only": True,
        "cookie_same_site": raw_same_site if raw_same_site in {"lax", "strict", "none"} else "lax",
        "max_age_seconds": max_age_seconds,
        "runtime_environment": runtime_environment,
    }
