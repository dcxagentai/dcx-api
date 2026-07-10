"""
CONTEXT:
This file owns the intentionally broad early-stage admin access role policy.
It exists so app/admin session summaries and login responses compute admin access from one place.
"""

from __future__ import annotations

DCX_ADMIN_CAPABLE_USER_ROLES = {
    "admin",
    "dev",
    "shareholder",
}


def read_dcx_user_role_may_access_admin(user_role: str | None) -> bool:
    """
    CONTRACT:
      preconditions:
        - user_role is the role value from stephen_dcx_users, or null.
      postconditions:
        - Returns true only for the exact admin, dev, and shareholder roles.
        - Returns false for normal users and blank roles.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - DCX currently wants only the explicitly named admin, dev, and shareholder roles to have full admin access.
      WHEN TO USE it:
        - Use it wherever a session or login response needs to compute admin-surface access.
      WHEN NOT TO USE it:
        - Do not use it for feature-level permissions if module-specific restrictions are introduced.
      WHAT CAN GO WRONG:
        - A role string outside this exact set, including plural or investor-like synonyms, will be treated as a normal app-only user.
      WHAT COMES NEXT:
        - Replace or narrow this helper if module-level rules are introduced.

    TESTS:
      - test_allows_only_exact_admin_capable_roles
      - test_rejects_role_synonyms_and_unprivileged_values

    ERRORS: []

    CODE:
    """
    return user_role in DCX_ADMIN_CAPABLE_USER_ROLES
