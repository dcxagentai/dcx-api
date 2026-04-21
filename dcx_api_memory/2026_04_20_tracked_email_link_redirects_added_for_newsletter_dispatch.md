The newsletter send pipeline now has a real tracked-link redirect path instead of only preparatory link rows.

What changed:
- Added `emails/send_links/record_dcx_email_send_link_click_and_read_redirect_target.py`
  - resolves one tracking token from `stephen_dcx_emails_sends_links`
  - inserts one click row into `stephen_dcx_emails_sends_link_clicks`
  - returns the original outbound URL for redirect
- Added a new public route:
  - `GET /public/email-links/{tracking_token}`
  - records the click and returns a `307` redirect to the original URL
- Wired the route into `dcx_api_app.py`
- Updated the newsletter dispatcher so outbound markdown links now render as tracked API redirect URLs instead of direct original URLs
- Added `DCX_API_BASE_URL` documentation to `.env.example` for absolute tracked-link generation

Important current limitation:
- Click attribution is still send-link level, not recipient level.
- The current schema stores one `tracking_token` per `stephen_dcx_emails_sends_links` row, not per recipient.
- That means:
  - we can count clicks for a send/link
  - we cannot honestly attribute a click to one exact recipient yet
- The new route deliberately records `email_send_recipient_id = NULL` rather than faking recipient identity.

Why this matters:
- The admin sends catalog already shows tracked-link counts.
- Now those tracked links are operational instead of only being staged rows.
- The newsletter dispatcher can send real tracked URLs immediately.

Verification:
- Focused pytest slice passed:
  - `emails/send_links/record_dcx_email_send_link_click_and_read_redirect_target_test.py`
  - `routes/public/dcx_api_routes_public_emails_send_link_redirect_test.py`
  - `content/newsletter_sends/dispatch_one_due_dcx_newsletter_send_via_resend_test.py`
  - `dcx_api_app_test.py`
- Result: `33 passed`

Likely next backend steps:
1. Add unsubscribe routes for:
   - unsubscribe from all non-transactional email
   - unsubscribe from promotional email
   - unsubscribe from newsletters
2. Add Resend webhook ingestion for:
   - delivered
   - failed
   - bounced
   - complained
3. Use webhook outcomes to populate:
   - recipient event fields on `stephen_dcx_emails_sends_recipients`
   - active rows in `stephen_dcx_emails_suppressions`
