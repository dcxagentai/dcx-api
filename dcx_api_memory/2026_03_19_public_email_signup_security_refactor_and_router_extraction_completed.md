# Context

This note records the completion of the DCX public email-signup security refactor and the
extraction of the public user-signup HTTP surface out of the monolithic FastAPI app file.

## What Changed

- extracted the public signup HTTP surface into:
  - `routes/users/dcx_api_users_signup_email_routes.py`
- kept `dcx_api_app.py` as the composition root for:
  - app construction
  - middleware
  - lifespan/startup wiring
  - router inclusion
- renamed the public email-signup routes to the durable `/users/...` surface:
  - `POST /users/signup-email`
  - `POST /users/signup-email/verify-otp`
  - `POST /users/signup-email/resend-otp`
- removed `waitlist` naming from the transport and protocol layer
- renamed the public capabilities and support helpers away from `public_waitlist`
- changed `challenge_purpose` from `waitlist_signup` to `email_signup`

## Security Hardening Implemented

- removed raw OTP and email-draft exposure from normal route responses
- removed route-level debug-mode dependence for OTP/draft visibility
- narrowed route logging to safe structured fields
- hardened request validation so public JSON bodies reject extra fields
- validated exact `Origin` values for public POST routes
- normalized public page URLs server-side:
  - strips query strings
  - strips fragments
  - enforces explicit approved public paths
- tightened CORS to explicit allowed origins with `allow_credentials = false`
- replaced email-in-browser-URL handoff with opaque `signup_flow_token`
- minimized public success payloads to flow-safe fields only
- collapsed public-facing error responses into safer generic categories

## OTP And State Hardening

- replaced deterministic OTP hashing with keyed HMAC plus per-challenge salt
- added hardened challenge fields:
  - `otp_salt`
  - `public_signup_flow_token_hash`
  - `public_signup_flow_token_expires_at_ts_ms`
  - `next_send_allowed_at_ts_ms`
  - `locked_until_ts_ms`
  - `send_count`
- enforced one active pending challenge per identity/type/purpose with a partial unique index
- made signup reuse/update the active challenge row instead of creating competing pending rows
- added cooldown handling to signup as well as resend
- added verify lockout behavior after repeated bad OTP attempts
- added Postgres-backed per-IP throttling table:
  - `stephen_dcx_public_route_rate_limits`

## Provider Behavior

- kept Resend as the delivery provider
- marked the send capability as effectively not retry-safe inside the request cycle
- relied on challenge cooldown checks so repeated signup submits do not re-send immediately
- updated env var names to the durable email-signup naming:
  - `DCX_EMAIL_SIGNUP_RESEND_FROM_NAME`
  - `DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL`
  - `DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT`
  - `DCX_EMAIL_SIGNUP_OTP_SECRET`

## Verification

- backend test suite rerun after the refactor:
  - `38 passed`

## Current Outcome

The backend now exposes a durable, future-extensible public user-signup email OTP flow under
`/users/...`, with stronger request validation, safer logging, token-based browser handoff,
rate limiting, cooldowns, lockouts, and hardened OTP storage.

## What Comes Next

- rerun the security review agents against the hardened codebase
- then proceed to landing/OTP/confirmation page design and branding improvements
