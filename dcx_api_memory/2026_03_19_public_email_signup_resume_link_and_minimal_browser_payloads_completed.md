# Context

This note records the follow-up refactor that completed the DCX public email-signup OTP
security flow after the earlier router extraction and hardening pass.

## What Changed

- removed the fallback from `DCX_EMAIL_SIGNUP_OTP_SECRET` to `RESEND_API_KEY`
- made the signup OTP/email flow fail closed when `DCX_EMAIL_SIGNUP_OTP_SECRET` is missing
- changed the OTP email draft so it now includes a localized verification link carrying the
  same opaque `signup_flow_token`
- kept the browser-side same-tab convenience, but made the email link the durable recovery
  mechanism for:
  - browser crashes
  - tab closure
  - delays
  - cross-device completion
- fixed the cooldown branch so it does not silently rotate the resume token without sending a
  fresh email
- minimized the public `/users/signup-email` success payload to:
  - `ok: true`
  - `data.signup_flow_token` only when a fresh send occurred
  - otherwise `data: {}`
- kept `/users/signup-email/verify-otp` success payload at:
  - `ok: true`
  - `data: {}`
- kept `/users/signup-email/resend-otp` success payload at:
  - `ok: true`
  - `data.signup_flow_token`

## Why It Matters

The earlier browser-only token handoff worked well for the immediate same-tab journey, but it
was too fragile for real-world user behavior. The revised flow now supports both:

- immediate redirect to the OTP page after fresh signup
- later recovery from the email link using the same challenge token

without putting the user email in visible browser URLs.

## Verification

- backend pytest suite rerun:
  - `38 passed`

## Current Backend Outcome

The backend now treats the opaque signup flow token as a proper challenge resume token, not
just a short-lived browser convenience token, while still preserving minimal browser-facing
payloads.
