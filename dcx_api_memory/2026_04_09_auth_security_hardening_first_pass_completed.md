Auth/security hardening first pass completed on 2026-04-09.

What changed:
- Added explicit browser-origin validation for authenticated and password-auth POST routes via `read_allowed_dcx_frontend_origin_or_error_response.py`.
- Added first-party login throttling via `enforce_dcx_auth_login_rate_limits.py`.
- Reduced default auth-session TTL from 14 days to 24 hours in `read_dcx_auth_session_cookie_settings.py`.
- Moved password-reset session revocation into the same transaction as password write + challenge consumption in `complete_dcx_password_set_from_challenge.py`.
- Replaced the API root route JSON/route dump with a minimal placeholder HTML page in `dcx_api_app.py`.

Routes now guarded by strict frontend-origin checks:
- `/auth/login/password`
- `/auth/logout`
- `/auth/password/request-reset`
- `/auth/password/complete-set`
- `/users/me/account-settings`
- `/admin/content/ux-strings/save-live-row`
- `/admin/content/emails/save-live-row`
- `/admin/publish/public-site/run`
- `/admin/publish/public-site/mark-local-rebuild-complete`

Verification:
- Focused backend auth/security suite passed: `34 passed`.
- Coverage included root placeholder response, login/session behavior, password-link flows, and one explicit forbidden-origin rejection test.

Operational notes:
- `DCX_AUTH_SESSION_TTL_HOURS` can still override the new 24h default if we later want 2h or another shorter value.
- No database migration was required for this hardening pass.
- Existing hosted env config for `DCX_FRONTEND_ADDITIONAL_ALLOWED_ORIGINS` remains important for app/admin browser POSTs.

What still might come later, but was not required for this pass:
- breached/common-password screening
- stronger/session-rotation policy beyond fixed 24h TTL
- more exhaustive CSRF/origin rejection tests across every browser POST route
- even smoother cross-tab logout UX beyond focus/poll/storage sync
