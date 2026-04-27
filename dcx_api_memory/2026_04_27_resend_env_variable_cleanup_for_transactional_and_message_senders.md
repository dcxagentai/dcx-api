Context
- We cleaned up the Resend-related backend environment-variable naming while preparing live email-message smoke tests.
- The goal was to separate provider-owned configuration from shared DCX runtime configuration, and to split transactional sender identity from future message-thread sender identity.

What changed
- The Resend sender adapter now reads:
  - `RESEND_API_KEY`
  - `RESEND_WEBHOOK_SECRET`
  - `RESEND_FROM_NAME`
  - `RESEND_FROM_EMAIL_TRANSACTIONAL`
  - `RESEND_FROM_EMAIL_MESSAGES`
  - optional local-only:
    - `RESEND_TEST_RECIPIENT`
    - `RESEND_ALLOW_TEST_RECIPIENT_OVERRIDE`
- Signup/shared HMAC flows now read:
  - `DCX_SIGNUP_OTP_SECRET`
- The backend `.env.example` was updated to match the new names exactly.

Sender policy
- `RESEND_FROM_EMAIL_TRANSACTIONAL`
  - use for signup OTPs, confirmations, and other account/transactional mail
  - current intended value: `team@mail.dcxagent.ai`
- `RESEND_FROM_EMAIL_MESSAGES`
  - reserved for user-facing message-thread traffic and future processed-message outbound mail
  - current intended value: `chat@mail.dcxagent.ai`

Webhook
- Live Resend webhook URL:
  - `https://api.dcxagent.ai/public/webhooks/resend`
- Local/dev webhook URL:
  - `{DCX_API_BASE_URL}/public/webhooks/resend`
- The webhook signing secret stored in Resend for that specific webhook must be copied into:
  - `RESEND_WEBHOOK_SECRET`

Notes
- Old sender/signup-specific env aliases were removed from executable code during this cleanup pass.
- Historical memory notes still mention the older names; those were left untouched as session history.
- Focused backend pytest coverage for the refactor passed: `23 passed`.
