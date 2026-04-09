Content pages and newsletter-content backend foundations were added for the current MVP milestone.

What now exists:
- immutable multilingual-ready admin capabilities and routes for content pages
- immutable multilingual-ready admin capabilities and routes for newsletter content using `stephen_dcx_emails` with `email_type='newsletter'`
- token-gated public build-time content-pages bundle route
- public publish-status reader widened so published content pages count alongside public UX strings

Key new backend boundaries:
- `/admin/content/pages/categories`
- `/admin/content/pages/catalog`
- `/admin/content/pages/{language_code}/{page_key}`
- `/admin/content/pages/create-draft`
- `/admin/content/pages/save-live-row`
- `/admin/content/pages/publish-live-row`
- `/admin/content/pages/archive-live-row`
- `/admin/content/newsletters/catalog`
- `/admin/content/newsletters/{language_code}/{email_key}`
- `/admin/content/newsletters/create-draft`
- `/public/build-time/content-pages-bundle`

Important shape decisions:
- pages use `stephen_dcx_content_pages` as the immutable multilingual content/version table
- newsletters reuse `stephen_dcx_emails` with `email_type='newsletter'`
- actual send scheduling/delivery is intentionally deferred to a later `stephen_dcx_emails_sends` step
- publish status now treats both public UX strings and published content pages as public deploy inputs

Verification completed:
- `dcx_api_app_test.py`: 25 passed
- focused publish-status tests: 4 passed

Residual follow-up:
- content-page and newsletter-specific route tests are still worth adding later
- actual newsletter sending, recipient joins, clicks, and unsubscribe/bounce workflow remain a separate later step
