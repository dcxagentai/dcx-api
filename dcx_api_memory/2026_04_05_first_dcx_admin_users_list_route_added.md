The first admin-facing users-list backend contract is now in place.

Files added:
- `admin/users/read_dcx_admin_user_list.py`
- `admin/users/read_dcx_admin_user_list_test.py`
- `routes/admin/dcx_api_routes_admin_users_list.py`

Files updated:
- `dcx_api_app.py`
- `dcx_api_app_test.py`

What this backend slice does:
- Adds `GET /admin/users/list`
- Returns one canonical wrapper with the current DCX users list payload
- Reads directly from `stephen_dcx_users` and left-joins `stephen_dcx_languages`
- Orders users by latest activity/update first using:
  - `COALESCE(last_seen_at_ts_ms, updated_at_ts_ms, created_at_ts_ms) DESC`
- Returns:
  - `users`
  - `total_user_count`
- Each user row includes:
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
- Real admin auth is not wired yet.
- In `local` or `development`, the route temporarily accepts `?admin_user_id=<id>`.
- Without that local debug admin id, the route returns:
  - `401`
  - `API_DCX_ADMIN_AUTH_REQUIRED`
- Outside local/development, the debug `admin_user_id` path is rejected with:
  - `400`
  - `API_DCX_ADMIN_DEBUG_USER_ID_FORBIDDEN`

Verification:
- `admin/users/read_dcx_admin_user_list_test.py` passed
- `dcx_api_app_test.py` passed
- focused backend result: `19 passed`

Why this shape was chosen:
- The admin frontend now has a stable read-only contract before auth, roles, or editing are added.
- The route name is already future-safe for a real admin surface.
- Real session/role enforcement can later replace the temporary `?admin_user_id=` path without changing the frontend fetch contract.

Next most natural backend step:
- replace temporary `?admin_user_id=` resolution with real admin session and role checks
- then add adjacent admin read/edit contracts for email templates and UX strings
