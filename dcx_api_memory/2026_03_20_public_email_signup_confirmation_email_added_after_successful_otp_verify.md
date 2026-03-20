## Context

Added one best-effort confirmation email to the public DCX email-signup flow after a successful OTP verification.

## What changed

- Added `build_public_email_signup_confirmation_email_delivery_draft(...)` to:
  - `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_public_email_signup_otp_support.py`
- Added a dedicated Resend provider boundary for the follow-up message:
  - `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_send_public_email_signup_confirmation_via_resend_capability.py`
- Extended OTP verification to return the internally needed confirmed recipient email:
  - `C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_verify_public_email_signup_otp_capability.py`
- Updated the verify route so that:
  - user confirmation still happens first
  - the browser response stays `{"ok": true, "data": {}}`
  - confirmation email delivery is attempted after successful verification
  - confirmation email delivery failures are logged and ignored rather than breaking the user-visible success path

## Email content

English:
- Subject: `You're on the DCX Agentic waitlist`
- Simple short body confirming receipt and saying more will follow soon

Spanish:
- Added a matching minimal Spanish variant for consistency with the existing localized OTP flow

## Why this shape

The follow-up email is product polish rather than a critical authentication step. Treating it as best-effort avoids turning a successful OTP verification into a failed browser experience because of a transient provider problem.

## Tests

Focused backend verification passed:
- `dcx_api_app_test.py`
- `dcx_api_verify_public_email_signup_otp_capability_test.py`
- `dcx_api_send_public_email_signup_confirmation_via_resend_capability_test.py`

Result:
- `15 passed`

## Remaining note

This currently sends after each successful confirmation event. If the product later wants strict “first confirmation only” behavior, add an explicit deduplication marker for the follow-up email rather than overloading the core signup confirmation state.
