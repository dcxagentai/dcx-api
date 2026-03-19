# Context

This note records the point where the public waitlist signup route moved from validation-only intake to the first real persisted backend mechanics.

## What Changed

- added `create_or_refresh_public_waitlist_email_signup_artifacts_capability`
- `POST /waitlist/email-signup` now:
  - validates and normalizes the public payload
  - advisory-locks on the normalized email
  - creates or reuses the user row
  - creates or reuses the email auth identity row
  - creates or refreshes the active pending email OTP challenge row
  - generates a localized email draft for later Resend delivery

## Current Behavior

- the route still returns the canonical wrapper shape
- in local-style debug mode, the response can include `debug_email_delivery_draft`
- this debug draft includes the OTP code and plain-text email draft
- debug mode defaults on for localhost DB host unless explicitly overridden

## What Is Still Missing

- real Resend delivery
- OTP verification route
- OTP input page
- confirmation page

## Verification

- focused backend tests passed: `18 passed`

## Next Step

Use the generated email draft to wire the first real Resend send operation, then add OTP verification against the stored challenge hash.
