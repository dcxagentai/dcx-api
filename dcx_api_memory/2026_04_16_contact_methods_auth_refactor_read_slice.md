CONTEXT:
Second backend refactor slice after the first contact-method auth migration.

SUMMARY:
- Authenticated session reads now resolve `primary_email` from the normalized primary email contact
  method first, with fallback to the legacy user-row snapshot.
- Authenticated account summary reads now resolve:
  - primary email from contact methods first
  - primary phone from contact methods first, but still fall back to legacy user phone fields
    because the phone-link flow has not been fully migrated yet.
- Admin user-list reads now resolve primary email and its verified timestamps from contact methods
  first, with fallback to the legacy user-row snapshot.
- Login response now returns the normalized email contact-method value from the login lookup query.

IMPORTANT DECISION:
- This read slice does NOT mean the legacy `stephen_dcx_users` contact columns can be dropped yet.
- Remaining blockers before cleanup SQL:
  - signup create still writes `users.primary_email`
  - signup verify still updates legacy email-confirmed snapshot fields
  - phone/WhatsApp flows still depend on legacy phone columns

VERIFICATION:
- `py_compile` passed for:
  - `auth/session/read_authenticated_dcx_session_from_request.py`
  - `users/account/read_authenticated_dcx_user_account_summary.py`
  - `admin/users/read_dcx_admin_user_list.py`
  - `auth/login/login_dcx_user_with_email_and_password.py`
- Inline smoke checks passed for session/account/admin read shapes using fake DB connections.

WHAT COMES NEXT:
- Refactor phone-link flows onto `stephen_dcx_users_contact_methods`.
- Remove remaining write-side dependence on `users.primary_email` and phone fields.
- Only then prepare the final cleanup SQL to remove legacy contact columns from `stephen_dcx_users`.
