# Exact admin role allowlist

The admin authorization policy now grants access only to the exact stored role values `admin`, `dev`, and `shareholder`.

Plural forms, investor terms, case variants, whitespace variants, blank roles, and normal users are rejected. The policy remains centralized in `auth/authorization/read_dcx_user_role_may_access_admin.py`, which supplies both login/session `allowed_surfaces.admin` values and direct admin-route authorization.

Focused tests were added beside the policy and pass together with the existing login authorization tests.
