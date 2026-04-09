"""
CONTEXT:
This file applies the first DCX email/password login rate limits.
It exists so the shared login route can slow brute-force and credential-stuffing attempts using
both per-IP and per-email budgets before password verification begins.
"""

from __future__ import annotations

from system.rate_limits.enforce_public_route_rate_limit import (
    enforce_public_route_rate_limit_capability,
)


def enforce_dcx_auth_login_rate_limits(
    client_ip: str,
    normalized_email: str,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - client_ip is the best-available client address at the HTTP boundary.
        - normalized_email is the lowercased login email candidate.
      postconditions:
        - Enforces one per-IP login budget and one per-email login budget.
        - Raises a stable runtime error when either budget is exceeded.
      side_effects:
        - writes to stephen_dcx_public_route_rate_limits
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: none
      locks:
        - advisory lock inside the shared rate-limit capability for the relevant budget window row
      contention_strategy: serialize increments per budget row through the shared Postgres rate-limit capability

    NARRATIVE:
      WHY this exists:
        - Login is the highest-value credential-stuffing target in the current MVP.
      WHEN TO USE it:
        - Use it before any password verification work in the shared login route.
      WHEN NOT TO USE it:
        - Do not use it as the only auth defense; keep password hashing and generic failures too.
      WHAT CAN GO WRONG:
        - Missing database/rate-limit table can fail closed.
        - Overly tight budgets can frustrate legitimate users.
      WHAT COMES NEXT:
        - The login route can continue into password verification only when both budgets remain open.

    TESTS:
      - covered_indirectly_by_auth_login_route_tests

    ERRORS:
      - API_DCX_AUTH_LOGIN_RATE_LIMIT_EXCEEDED:
          suggested_action: Wait a little and retry the login.
          common_causes:
            - too many login attempts from one IP
            - too many login attempts against one email
          recovery_steps:
            - Pause for the window to roll forward.
            - Retry with the correct credentials.
          retry_safe: true

    CODE:
    """
    try:
        ip_budget = enforce_public_route_rate_limit_capability(
            route_key="auth_login_password_ip",
            client_ip=client_ip,
            max_requests=15,
            window_ms=15 * 60 * 1000,
        )
        email_budget = enforce_public_route_rate_limit_capability(
            route_key="auth_login_password_email",
            client_ip=normalized_email or "unknown-email",
            max_requests=8,
            window_ms=15 * 60 * 1000,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_EXCEEDED":
            raise RuntimeError("API_DCX_AUTH_LOGIN_RATE_LIMIT_EXCEEDED") from runtime_error
        raise

    return {
        "ip_budget": ip_budget,
        "email_budget": email_budget,
    }
