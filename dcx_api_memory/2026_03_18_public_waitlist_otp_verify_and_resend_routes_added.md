# Context

This note records the session where the rest of the first DCX public waitlist mechanics were added on the backend after signup creation and Resend delivery were already working.

## What was added

- `verify_public_waitlist_email_otp_capability`
- `resend_public_waitlist_email_otp_capability`
- shared OTP support helpers in `dcx_api_public_waitlist_email_otp_support.py`
- FastAPI routes:
  - `POST /waitlist/email-otp/verify`
  - `POST /waitlist/email-otp/resend`

## Behavior now in place

- OTP verification:
  - validates email, otp, language, and page URL
  - locks by normalized email
  - finds the matching user, email identity, and active challenge
  - confirms the user primary email
  - confirms the identity email
  - sets `last_authenticated_at_ts_ms` only on successful OTP verification
  - marks the challenge as consumed
  - increments attempts on incorrect codes
  - locks the challenge after too many failures
  - marks the challenge expired when verification arrives after expiry

- OTP resend:
  - validates email, language, and resend page URL
  - locks by normalized email
  - rejects resend for already-confirmed users
  - refreshes the existing challenge with a new OTP hash and expiry
  - resets attempt state
  - increments `resend_count`
  - enforces a basic resend cooldown
  - sends the refreshed OTP through Resend

## Tests

The backend test suite passed after these additions:

- `50 passed`

## Important current caveats

- Debug-mode OTP visibility is still intentionally present for local development.
- Route and data security tightening are deliberately postponed to the next explicit review pass.
- The resend cooldown is currently basic and intended as an interim mechanic rather than the final security posture.
