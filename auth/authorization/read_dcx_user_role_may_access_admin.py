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
    "shareholders",
    "investor",
    "investors",
}


def read_dcx_user_role_may_access_admin(user_role: str | None) -> bool:
    """
    CONTRACT:
      preconditions:
        - user_role is the role value from stephen_dcx_users, or null.
      postconditions:
        - Returns true for the small internal admin/investor/dev group.
        - Returns false for normal users and blank roles.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - DCX currently wants the small admin, investor/shareholder, and dev group to have full admin access.
      WHEN TO USE it:
        - Use it wherever a session or login response needs to compute admin-surface access.
      WHEN NOT TO USE it:
        - Do not use it for feature-level permissions once read-only investor restrictions are introduced.
      WHAT CAN GO WRONG:
        - A role string outside this set will be treated as a normal app-only user.
      WHAT COMES NEXT:
        - Replace or narrow this helper when the investor group needs read-only access or module-level rules.

    TESTS:
      - covered_indirectly_by_auth_and_admin_route_tests

    ERRORS: []

    CODE:
    """
    return (user_role or "").strip().lower() in DCX_ADMIN_CAPABLE_USER_ROLES
