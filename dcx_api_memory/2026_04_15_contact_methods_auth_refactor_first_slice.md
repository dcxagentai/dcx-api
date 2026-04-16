CONTEXT:
First backend refactor slice after introducing `stephen_dcx_users_contact_methods` and linking
`stephen_dcx_user_auth_identities.contact_method_id`.

SUMMARY:
- Public email signup creation now resolves the submitted email through
  `stephen_dcx_users_contact_methods` first, creates the contact-method row when needed, and links
  the email auth identity back to that contact method.
- Public email OTP verification now marks the verified email contact-method row as verified before
  continuing to update the legacy user snapshot fields and consume the challenge.
- Password setup/reset lookup now resolves through one verified login-enabled email contact method
  plus the matching email auth identity rather than `stephen_dcx_users.primary_email`.
- Email/password login now resolves the submitted email through the normalized contact-method table
  plus the matching email auth identity, while still returning the legacy `users.primary_email`
  snapshot in the response for compatibility.

FILES TOUCHED:
- `users/signup_email/create_or_refresh_public_email_signup_artifacts.py`
- `users/signup_email/verify_public_email_signup_otp.py`
- `auth/password/read_confirmed_dcx_user_identity_for_password_link_by_email.py`
- `auth/password/request_dcx_password_reset_email_challenge.py`
- `auth/password/create_dcx_password_setup_link_after_confirmed_signup.py`
- `auth/login/login_dcx_user_with_email_and_password.py`
- focused tests adjacent to those files

VERIFICATION:
- `py_compile` passed for all changed backend files and focused test files.
- The repo-local venv pytest launcher still failed from this shell with Windows access-denied, so a
  direct inline smoke script was run instead using the venv site-packages on `sys.path`.
- That smoke covered:
  - signup artifact creation
  - OTP verification
  - password-link target lookup
  - login lookup

IMPORTANT MODEL DECISION:
- For now `stephen_dcx_users.primary_email` and the related confirmed flags remain compatibility
  snapshot fields only.
- The intended source of truth for which emails belong to which user is now
  `stephen_dcx_users_contact_methods`.

WHAT COMES NEXT:
- Refactor authenticated session/account/admin read surfaces to derive primary email/phone from
  contact methods instead of the legacy user columns.
- After the read surfaces are migrated, prepare the schema cleanup that removes legacy contact
  columns from `stephen_dcx_users`.
