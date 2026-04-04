# 2026_04_04_transactional_email_templates_moved_to_stephen_dcx_emails

## Context

The first multilingual public signup flow already had:

- real `en/es/fr/de` public routes
- DB-backed frontend UX strings from `stephen_dcx_ux_strings`

The missing multilingual backend piece was the transactional email copy. OTP and confirmation emails were still being hardcoded inside `users/signup_email/public_email_signup_otp_support.py`.

## What Changed

Added backend email-template capabilities:

- `emails/read_live_email_template.py`
- `emails/render_email_template_with_allowed_placeholders.py`
- `emails/transactional/build_public_email_signup_otp_email_delivery_draft.py`
- `emails/transactional/build_public_email_signup_confirmation_email_delivery_draft.py`

Added adjacent tests for each new capability.

Refactored the public signup flow to use the new managed templates:

- `users/signup_email/create_or_refresh_public_email_signup_artifacts.py`
- `users/signup_email/resend_public_email_signup_otp.py`
- `routes/users/dcx_api_routes_users_signup_email_verify_otp.py`

Removed the old hardcoded OTP and confirmation email-draft builders from:

- `users/signup_email/public_email_signup_otp_support.py`

## Important Current Truth

- Live transactional email copy now comes from `stephen_dcx_emails`.
- Initial live transactional templates are:
  - `transactional / signup_verify_otp`
  - `transactional / signup_thanks_welcome`
- The OTP email currently allows only:
  - `{{ otp_code }}`
  - `{{ verify_otp_url }}`
- The confirmation email currently allows no placeholders.

## Validation

Focused backend tests passed:

- email template reader
- placeholder renderer
- OTP draft builder
- confirmation draft builder
- signup artifact capability
- resend capability
- transactional email sender modules

Route/app boundary tests also passed:

- `dcx_api_app_test.py`

## What Comes Next

- manual real-email verification through the live signup flow
- expand placeholder support only when a real email requires it
- later admin editing/publish flow for managed email templates
