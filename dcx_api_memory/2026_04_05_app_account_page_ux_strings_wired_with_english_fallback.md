The `dcx_app` account summary contract now includes an `ux_strings` map for the `app_account_page` group. This is assembled by the new capability `users/account/read_dcx_app_account_page_ux_strings.py`, which reads from `stephen_dcx_ux_strings` when rows exist and falls back to a local English default map while the group is still being seeded or translated.

This keeps the first app account surface aligned with the shared multilingual content model without making the page brittle during the English-shape iteration phase. The resolver prefers selected-language live rows, then original live rows, then the local default string for any missing key.

Verification for this step was a focused pytest run in `dcx_site/dcx_api` covering the new UX-string reader plus the account read/save and app-route tests, with `30 passed`.
