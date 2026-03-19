## Context

This note records the follow-up hardening pass after the first `/users/signup-email` security refactor.

## What Changed

- `DCX_EMAIL_SIGNUP_OTP_SECRET` is now required for OTP and flow-token HMAC operations.
- `RESEND_API_KEY` remains email-delivery-only and is no longer used as a fallback secret.
- public signup/resend flows now build verification links with the opaque `signup_flow_token` in the URL fragment:
  - `.../users/signup-email/verify-otp#signup_flow_token=...`
- allowed public origins now fail closed in `staging` and `production` if `DCX_PUBLIC_ALLOWED_ORIGINS` is missing.
- per-recipient send ceiling was enforced through the challenge lifecycle:
  - 6 sends per 24-hour window per identity
- test-recipient override now requires:
  - `DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE=true`
  - runtime environment in `local` or `development`
- delivery-failure recovery was strengthened:
  - the route now restores prior `send_count`, `resend_count`, `sent_at_ts_ms`, and `next_send_allowed_at_ts_ms`
  - this avoids stranding the user behind cooldown or spending send budget on failed provider sends

## Key Files

- `dcx_api_public_email_signup_otp_support.py`
- `dcx_api_create_or_refresh_public_email_signup_artifacts_capability.py`
- `dcx_api_resend_public_email_signup_otp_capability.py`
- `dcx_api_reset_public_email_signup_send_cooldown_after_delivery_failure_capability.py`
- `routes/users/dcx_api_users_signup_email_routes.py`
- `dcx_api_send_public_email_signup_otp_via_resend_capability.py`

## Verification

- backend pytest: `41 passed`

## Outcome

The public email-signup backend now supports cross-device resume with fragment-based links, stricter secret separation, stronger send-budget controls, and safer recovery when the provider send fails after challenge mutation.
