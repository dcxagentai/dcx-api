Auth cleanup follow-up after the first shared session/password rollout.

What changed
- Removed the remaining executable `?user_id=` / `?admin_user_id=` auth fallback path from active route code.
- Deleted the unused `routes/admin/dcx_api_routes_admin_support.py` file.
- Removed the unused local-debug user-id helper from `routes/users/dcx_api_routes_users_support.py`.
- Updated `dcx_api_app_test.py` to patch the session-based auth helpers directly instead of calling routes with debug query params.
- Updated key route contracts/narratives so they now describe authenticated session cookies rather than temporary debug ids.

Why
- Runtime auth is now real enough that the old bootstrap query-param path was becoming misleading and risky.
- The frontend and backend had already moved to session cookies, but the assembled route tests were still asserting the older bootstrap-era behavior.

Verification
- `dcx_api_app_test.py`: 23 passed

Operational consequence
- App/admin protected routes now require a real authenticated session in all environments.
- Any old URLs such as `/me/account?user_id=...` or `/users?admin_user_id=...` should be treated as obsolete.
