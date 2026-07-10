"""
CONTEXT:
These tests lock the exact early-stage role allowlist for the DCX admin surface.
They prevent convenient-looking synonyms from silently widening admin access.
"""

from auth.authorization.read_dcx_user_role_may_access_admin import (
    read_dcx_user_role_may_access_admin,
)


def test_allows_only_exact_admin_capable_roles() -> None:
    for user_role in ("admin", "dev", "shareholder"):
        assert read_dcx_user_role_may_access_admin(user_role) is True


def test_rejects_role_synonyms_and_unprivileged_values() -> None:
    for user_role in (
        None,
        "",
        "user",
        "shareholders",
        "investor",
        "investors",
        "Admin",
        "ADMIN",
        " admin ",
    ):
        assert read_dcx_user_role_may_access_admin(user_role) is False
