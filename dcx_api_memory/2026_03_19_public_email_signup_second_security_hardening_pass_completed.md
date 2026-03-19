CONTEXT:
This note records the second security hardening pass on the DCX public email-signup and OTP flow.
It exists so later agents can see which reviewer findings were closed after the first `/users/...`
security refactor, what changed in the backend, and what residual risks remain.

Summary
- We closed the newly reported backend/systemic issues around token leakage, secret separation, test-recipient override safety, send-budget enforcement, and provider-send recovery.
- The backend suite now passes cleanly after the second pass: `41 passed`.

What Changed
- `DCX_EMAIL_SIGNUP_OTP_SECRET` is now mandatory for OTP and flow-token HMAC work.
  - There is no fallback to `RESEND_API_KEY`.
- Public verification links now carry `signup_flow_token` in the URL fragment instead of the query string.
  - The fragment is not sent to the server and does not appear in referrer headers.
- Allowed origins now fail closed in `production` and `staging` when `DCX_PUBLIC_ALLOWED_ORIGINS` is missing.
- `DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT` is now blocked unless both conditions are true:
  - runtime environment is `local` or `development`
  - `DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE=true`
- A per-recipient daily send ceiling is now enforced through the challenge table:
  - `PUBLIC_EMAIL_SIGNUP_MAX_SENDS_PER_WINDOW = 6`
  - `PUBLIC_EMAIL_SIGNUP_SEND_BUDGET_WINDOW_MS = 24h`
- Delivery-failure recovery is now stronger.
  - The route keeps an internal recovery snapshot.
  - On Resend failure, the backend restores prior `send_count`, `resend_count`, `sent_at_ts_ms`, and `next_send_allowed_at_ts_ms`.
  - This avoids burning recipient send budget or trapping the user behind cooldown after a failed provider call.

Files Touched
- `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_public_email_signup_otp_support.py`
- `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_create_or_refresh_public_email_signup_artifacts_capability.py`
- `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_resend_public_email_signup_otp_capability.py`
- `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_reset_public_email_signup_send_cooldown_after_delivery_failure_capability.py`
- `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_send_public_email_signup_otp_via_resend_capability.py`
- `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\routes\users\dcx_api_users_signup_email_routes.py`

Verification
- `pytest`: `41 passed`

Residual Risks
- The browser still stores the in-flight token in `sessionStorage` after fragment capture.
  - This is materially better than email/query transport, but any future same-origin XSS would still expose it while the flow is active.
- We still use Postgres-backed route-rate limiting instead of Redis.
  - This is acceptable for now, but the rate-limit table still needs a future pruning policy.
- Root route success wrappers still include richer `context` than the public signup/verify/resend routes.
  - That is acceptable because it is no longer part of the public signup boundary, but it is worth keeping narrow.

Recommended Next Steps
- Re-run reviewer agents after any further auth-related changes.
- If we later move to CSP hardening, remember that the OTP page currently uses a small inline script to capture the fragment token before island hydration.
