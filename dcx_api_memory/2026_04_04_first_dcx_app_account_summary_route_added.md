The first app-facing account-summary backend contract is now in place.

Files added:
- `users/account/read_authenticated_dcx_user_account_summary.py`
- `users/account/read_authenticated_dcx_user_account_summary_test.py`
- `routes/users/dcx_api_routes_users_me_account_summary.py`

Files updated:
- `routes/users/dcx_api_routes_users_support.py`
- `dcx_api_app.py`
- `dcx_api_app_test.py`

What this backend slice does:
- Adds `GET /users/me/account-summary`
- Returns one canonical wrapper with the current user account summary payload
- Reads directly from `stephen_dcx_users` and left-joins `stephen_dcx_languages`
- Returns:
  - `user_id`
  - `user_uuid`
  - `primary_email`
  - `primary_email_confirmed`
  - `primary_email_confirmed_at_ts_ms`
  - `account_status`
  - `email_communication_preference`
  - `last_seen_at_ts_ms`
  - `created_at_ts_ms`
  - `updated_at_ts_ms`
  - nested `preferred_language` object or `null`

Temporary identity strategy:
- Real auth is not wired yet.
- In `local` or `development`, the route temporarily accepts `?user_id=<id>`.
- Without that local debug user id, the route returns:
  - `401`
  - `API_USERS_ME_AUTH_REQUIRED`
- Outside local/development, the debug `user_id` path is rejected with:
  - `400`
  - `API_USERS_ME_DEBUG_USER_ID_FORBIDDEN`

CORS changes:
- Backend CORS no longer assumes only the public site exists.
- `read_allowed_dcx_frontend_origins()` was added to provide:
  - local public/app/admin defaults during development
  - optional hosted additions via `DCX_FRONTEND_ADDITIONAL_ALLOWED_ORIGINS`
- This keeps existing local development smooth while leaving a clear env hook for future hosted app/admin origins.

Verification:
- `users/account/read_authenticated_dcx_user_account_summary_test.py` passed
- `dcx_api_app_test.py` passed
- total focused backend result: `16 passed`

Why this shape was chosen:
- The frontend contract is already future-safe:
  - `GET /users/me/account-summary`
- Later auth can replace the temporary `?user_id=` resolution without changing the frontend fetch path.
- This keeps the app/account page build small while still giving the auth phase a real destination route and real payload to protect.

Next most natural backend step:
- replace temporary `?user_id=` resolution with real session/auth principal resolution
- then add role/permission-aware boundaries for admin surfaces
