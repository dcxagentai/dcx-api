Context
- This note records the slice completed on 2026-04-20 after unsubscribe links and Resend webhook ingestion were already in place.
- The goal of this slice was to make the admin newsletter editor start showing useful operational send state instead of only the earlier "prepared send" snapshot model.

What changed
- `admin/content/newsletter_sends/read_dcx_admin_newsletter_sends_catalog.py`
  - The catalog query now filters to `send_kind = 'newsletter'`.
  - It now uses lateral aggregate subqueries instead of one large recipient/link join so counts stay trustworthy as recipient rows, tracked links, and click rows grow independently.
  - The capability now returns:
    - `pending_recipient_count`
    - `sending_recipient_count`
    - `sent_recipient_count`
    - `delivered_recipient_count`
    - `failed_recipient_count`
    - `bounced_recipient_count`
    - `complained_recipient_count`
    - `cancelled_recipient_count`
    - `total_click_count`
    - `unique_clicked_link_count`
  - Existing counts remain:
    - `total_recipient_count`
    - `send_candidate_count`
    - `skipped_recipient_count`
    - `blocked_missing_translation_count`
    - `tracked_link_count`
- `routes/admin/dcx_api_routes_admin_content_newsletter_sends_catalog.py`
  - Updated wording to reflect that this route now serves newsletter send rows with operational state, not only prepared rows.
- `dcx_api_app_test.py`
  - Added direct route-level coverage for `/admin/content/newsletters/{language_code}/{email_key}/sends`.
- `admin/content/newsletter_sends/read_dcx_admin_newsletter_sends_catalog_test.py`
  - Added focused capability tests for the richer aggregate shape and empty-catalog behavior.

Why this shape
- The original catalog was fine while sends were only prepared/scheduled.
- Once we added dispatch, tracked link redirects, and webhook-updated recipient statuses, the old join-based query would have become progressively less trustworthy for admin reporting.
- The lateral aggregate approach is more explicit and avoids accidental count inflation from multi-table joins.

Verification
- Focused backend pytest slice passed:
  - `admin/content/newsletter_sends/read_dcx_admin_newsletter_sends_catalog_test.py`
  - `dcx_api_app_test.py`
  - Result: `28 passed`

Notes
- The new test file needed to add the repo root to `sys.path` explicitly for this repo's current pytest/import setup.
- This slice does not yet add a per-recipient drill-down surface; it only improves the summary layer already used by the admin newsletter editor.

Likely next step
- If we want deeper operational debugging next, the natural follow-up is one admin route/capability for recipient-level detail on a single `email_send_id`.
