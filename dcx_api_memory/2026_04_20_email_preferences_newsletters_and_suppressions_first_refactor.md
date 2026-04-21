The email preference and newsletter-preparation code now matches the new schema vocabulary.

Summary:
- account settings now allow `no_email`, `newsletters`, and `all_email`
- account summary now returns those three options to the app surface
- account-summary labels are resilient during the transition by falling back from the new UX-string keys to the older `announcements` / `essential_only` keys when needed
- newsletter readiness and newsletter send preparation now treat both `newsletters` and `all_email` users as newsletter-eligible
- newsletter readiness and preparation now exclude addresses with active suppressions scoped to `newsletters` or `all_email`
- newsletter send preparation now writes `send_kind='newsletter'` and `send_audience_type='newsletters'`

Files changed:
- `users/account/save_authenticated_dcx_user_account_editable_settings.py`
- `users/account/read_dcx_app_account_page_ux_strings.py`
- `users/account/read_authenticated_dcx_user_account_summary.py`
- `admin/content/newsletters/read_dcx_admin_live_newsletter_detail.py`
- `admin/content/newsletter_sends/prepare_dcx_admin_newsletter_send.py`
- related backend tests and route-contract tests

Verification:
- ran targeted backend pytest slice in the repo virtualenv
- result: `38 passed`

Recommended next step:
- build the newsletter dispatch worker against `stephen_dcx_emails_sends` / `stephen_dcx_emails_sends_recipients`
- then add unsubscribe routes plus Resend webhook ingestion so suppressions and recipient event columns start being populated for real
