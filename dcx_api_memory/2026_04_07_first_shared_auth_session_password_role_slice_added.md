Auth slice added for the first shared DCX session flow across `dcx_app` and `dcx_admin`.

What was added:
- password hashing with `argon2id`
- shared opaque session cookie flow
- new auth schema objects in `dcx_initial_user_signup_schema_2026_03_18.sql`
  - `user_role` on `stephen_dcx_users`
  - `stephen_dcx_user_password_credentials`
  - `stephen_dcx_user_auth_sessions`
- auth routes
  - `POST /auth/login/password`
  - `GET /auth/session`
  - `POST /auth/logout`
- route authorization helpers
  - user helper resolves session first, then local debug fallback
  - admin helper resolves session first, applies role gate, then local debug fallback
- protected app/admin routes now use the new helpers instead of relying only on local query params

Verification completed:
- backend auth-focused tests: passed
- `dcx_api_app_test.py`: passed

Important implementation notes:
- `allow_credentials=True` is now enabled in backend CORS so cookie auth can work cross-origin for app/admin.
- `argon2-cffi` was added to `requirements.txt` and installed into the repo venv during this session.
- the local debug query param paths still exist as a fallback in `local/development`, but production still blocks those paths.

What is not done yet:
- password setup flow
- password reset flow
- role-management UI
- session refresh/rolling expiry policy polish
- revoking all sessions after password reset

Immediate next step:
- connect real user passwords in the database for one or more confirmed users so app/admin login can be tested end to end.
