# Context

This pass tightened the local newsletter send test path without changing the broader email architecture.

# What Changed

- `apis/resend/send_email.py`
  - now accepts generic Resend sender env names:
    - `DCX_RESEND_FROM_NAME`
    - `DCX_RESEND_FROM_EMAIL`
    - `DCX_RESEND_TEST_RECIPIENT`
    - `DCX_RESEND_ALLOW_TEST_RECIPIENT_OVERRIDE`
  - still accepts the older signup-specific names as backwards-compatible fallbacks
- `.env.example`
  - now documents the generic Resend env names as the preferred configuration surface
  - now documents `RESEND_WEBHOOK_SECRET`
  - now documents the exact Resend webhook URL shape:
    - `{DCX_API_BASE_URL}/public/webhooks/resend`
  - now makes the real DCX sender setup the main example instead of the old Resend safe test inbox path
- `system/background_jobs/run_one_due_dcx_newsletter_resend_dispatch_pass.py`
  - added one one-shot local/manual dispatch entrypoint for prepared due sends

# Why This Helps

- Transactional emails and newsletter emails now share the same preferred Resend configuration language.
- Local newsletter testing no longer requires starting the infinite worker loop if we only want one quick send pass.
- Cloudflare tunnel testing has one clear setup shape:
  - set `DCX_API_BASE_URL` to the tunnel hostname
  - register `https://<tunnel-host>/public/webhooks/resend` in Resend
  - set `RESEND_WEBHOOK_SECRET` in the backend env

# Practical Local Test Path

1. Confirm backend env values:
   - `RESEND_API_KEY`
   - `DCX_RESEND_FROM_NAME=DCX`
   - `DCX_RESEND_FROM_EMAIL=team@dcxagent.ai`
   - `DCX_API_BASE_URL`
2. Leave `DCX_RESEND_TEST_RECIPIENT` unset if we want real test inbox delivery.
3. Prepare a newsletter send from the admin UI.
4. Run one dispatch pass locally:
   - `python system/background_jobs/run_one_due_dcx_newsletter_resend_dispatch_pass.py`
5. If we want webhook-driven delivered / bounced / complained updates locally:
   - point a Cloudflare tunnel at the backend
   - set `DCX_API_BASE_URL` to that tunnel hostname
   - register `https://<tunnel-host>/public/webhooks/resend` in Resend
   - set `RESEND_WEBHOOK_SECRET`

# Verification

- `pytest apis/resend/send_email_test.py routes/public/dcx_api_routes_public_resend_webhooks_test.py`
- one-shot script import smoke check returned `True`
