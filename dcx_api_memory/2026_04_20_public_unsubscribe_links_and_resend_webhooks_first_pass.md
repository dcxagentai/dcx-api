The DCX email system now has the first real public unsubscribe path and the first real Resend webhook ingestion path.

What changed:
- Added signed unsubscribe-token helpers under `users/account/dcx_email_preference_unsubscribe_support.py`
  - builds stateless unsubscribe tokens
  - reads and verifies them later
  - builds absolute public unsubscribe URLs
- Added `apply_dcx_public_email_unsubscribe_request.py`
  - `all` => sets `email_communication_preference` to `no_email`
  - `promotional` => steps `all_email` users down to `newsletters`
  - `newsletters` =>
    - `newsletters` users go to `no_email`
    - `all_email` users stay `all_email` but get an active `newsletters` suppression row
- Added public route:
  - `GET /public/email-preferences/unsubscribe/{unsubscribe_kind}/{raw_unsubscribe_token}`
  - returns a minimal human-readable HTML confirmation/error page
- Added newsletter email footer helper:
  - appends all / promotional / newsletters unsubscribe links to outbound newsletter email bodies
- Updated the newsletter dispatcher to append that footer per recipient before sending

Webhook handling:
- Added `apis/resend/verify_dcx_resend_webhook_request.py`
  - verifies raw request body plus Svix-compatible signature headers
  - expects `RESEND_WEBHOOK_SECRET`
  - enforces a 5-minute timestamp tolerance
- Added `emails/apply_dcx_resend_email_event_to_send_records.py`
  - handles:
    - `email.delivered`
    - `email.failed`
    - `email.bounced`
    - `email.complained`
  - updates matching recipient rows by `provider_message_id`
  - creates/refreshes active `all_email` suppressions for bounces and complaints
- Added public route:
  - `POST /public/webhooks/resend`
  - verifies the webhook first, then applies the event

Important design note:
- The three unsubscribe behaviors now fit the current schema because we use the suppression table for the newsletter-only case.
- That means:
  - preference row = user intent baseline
  - suppression row = narrower operational override when needed

Verification:
- Focused pytest slice passed:
  - unsubscribe support tests
  - unsubscribe apply-capability tests
  - newsletter footer tests
  - public unsubscribe route tests
  - Resend webhook verification tests
  - Resend webhook apply-capability tests
  - public webhook route tests
  - newsletter dispatch tests
  - app root regression tests
- Result: `44 passed`

Docs alignment:
- The webhook verification implementation was checked against current official docs:
  - Resend verify-webhook docs (Svix headers + raw body requirement)
  - Resend event-types docs

Likely next backend steps:
1. Decide whether to surface unsubscribe confirmation on a richer frontend route instead of minimal API HTML.
2. Add admin/newsletter-send detail reporting for:
   - delivered count
   - bounced count
   - complained count
3. Start the first sequence execution slice on top of the now more complete send engine.
