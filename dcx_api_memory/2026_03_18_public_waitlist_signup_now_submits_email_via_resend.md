# Context

This note records the point where the public waitlist signup route started submitting the OTP email through Resend instead of stopping at draft generation.

## What Changed

- added `send_public_waitlist_email_otp_via_resend_capability`
- `POST /waitlist/email-signup` now:
  - creates or refreshes the user row
  - creates or refreshes the email identity row
  - creates or refreshes the pending OTP challenge row
  - generates the localized email draft
  - submits that draft to Resend

## Current Environment Contract

Added backend env expectations:

- `RESEND_API_KEY`
- `DCX_WAITLIST_RESEND_FROM_NAME`
- `DCX_WAITLIST_RESEND_FROM_EMAIL`
- optional `DCX_WAITLIST_RESEND_TEST_RECIPIENT`

For early development, the default sender is:

- `onboarding@resend.dev`

and the optional test recipient can be:

- `delivered@resend.dev`

## Important Behavior Notes

- the route still returns the canonical wrapper shape
- in explicit or local debug mode, the raw email draft can still be exposed for testing
- `last_authenticated_at_ts_ms` is no longer set during signup creation
- actual authentication timing should begin only after OTP verification succeeds

## Verification

- focused backend suite passed: `22 passed`

## Next Step

Build:

- OTP verification route and capability
- OTP input pages
- resend route and cooldown logic
