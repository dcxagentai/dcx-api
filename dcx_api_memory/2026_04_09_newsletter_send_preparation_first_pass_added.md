Newsletter send preparation first pass is now in place without actual provider dispatch yet.

What was added:
- markdown link extraction helper:
  - `content/newsletter_sends/build_dcx_emails_sends_links_from_newsletter_markdown.py`
- admin newsletter-send preparation capabilities:
  - `admin/content/newsletter_sends/read_dcx_admin_newsletter_sends_catalog.py`
  - `admin/content/newsletter_sends/prepare_dcx_admin_newsletter_send.py`
  - `admin/content/newsletter_sends/cancel_dcx_admin_newsletter_send.py`
- admin routes:
  - `GET /admin/content/newsletters/{language_code}/{email_key}/sends`
  - `POST /admin/content/newsletters/{language_code}/{email_key}/sends/prepare`
  - `POST /admin/content/newsletters/sends/{email_send_id}/cancel`
- application root includes those routers now in `dcx_api_app.py`

Important design decisions:
- newsletter content remains in `stephen_dcx_emails` with `email_type='newsletter'`
- send preparation is separate operational state, not new content state
- prepared sends are anchored to:
  - the live source email row used from the admin route
  - the `email_key` snapshot
- recipient rows snapshot:
  - recipient email
  - preferred language
  - communication preference
  - resolved newsletter email row
  - send/skip decision
- tracked links are extracted from the resolved newsletter body variants used by that prepared send

Tables are intentionally separate:
- `stephen_dcx_emails_sends`
- `stephen_dcx_emails_sends_recipients`
- `stephen_dcx_emails_sends_links`
- `stephen_dcx_emails_sends_link_clicks`

Current scope:
- prepare now
- prepare scheduled send
- cancel prepared send
- list prepared sends with recipient/link counts
- no Resend dispatch yet
- no click redirect route yet

Tests/builds:
- targeted backend tests for link extraction + prepare/cancel capabilities passed (`8 passed`)
- `dcx_api_app_test.py` passed (`25 passed`)

Schema note:
- the new send-prep tables were added in a separate SQL file:
  - `storage/dcx_add_emails_sends_tables_2026_04_09.sql`
- the main startup schema file is currently behind the real database state and still does not contain some newer content/email/public-publish tables
- do not forget that this send-prep SQL must be applied on local and live before using the new routes/UI
