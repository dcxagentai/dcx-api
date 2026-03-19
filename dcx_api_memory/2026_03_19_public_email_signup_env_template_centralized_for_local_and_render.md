CONTEXT:
This note records the environment-template cleanup for the DCX public email-signup / OTP flow.
It exists so later agents know there is now one obvious backend env reference file for both local
development and Render deployment.

What Changed
- Rewrote `dcx_site/dcx_api/.env.example` into one centralized reference block.
- The file now covers:
  - database configuration
  - OTP/token secret
  - allowed origins
  - proxy-header trust
  - Resend sender config
  - hosted-test mode using `delivered@resend.dev`
  - real production mode using a verified sending domain

Important Operational Note
- Because the client does not yet have a verified sending domain, the current hosted test setup
  should use:
  - `DCX_ENVIRONMENT=development`
  - `DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT=delivered@resend.dev`
  - `DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE=true`
- Real production mode should remove those override vars and switch to:
  - `DCX_ENVIRONMENT=production`
  - verified sender email domain
