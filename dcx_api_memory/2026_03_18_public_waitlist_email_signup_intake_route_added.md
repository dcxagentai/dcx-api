# Context

This note records the first real public waitlist intake boundary added for the DCX MVP.

## What Changed

- added `accept_public_waitlist_email_signup_request_capability`
- added adjacent pytest coverage for the intake capability
- added `POST /waitlist/email-signup` to `dcx_api_app.py`
- the route currently:
  - accepts `email`
  - accepts `language_code`
  - accepts `signup_page_url`
  - normalizes and validates them
  - returns canonical wrapped success or error responses
- the route is intentionally side-effect free for now

## Why This Shape

We wanted the first real public landing-page form to send a realistic payload to the backend without yet forcing the full OTP persistence and email delivery layer into the same implementation step.

That means this route proves:

- public frontend -> backend payload shape
- backend-side normalization and validation
- canonical runtime response wrappers

without yet mutating:

- `stephen_dcx_users`
- `stephen_dcx_user_auth_identities`
- `stephen_dcx_user_auth_challenges`

## Next Step

Replace the current side-effect free intake with the first persisted mechanics:

- create or reuse user row
- create or reuse email auth identity row
- create or refresh email OTP challenge row
- send OTP via Resend
