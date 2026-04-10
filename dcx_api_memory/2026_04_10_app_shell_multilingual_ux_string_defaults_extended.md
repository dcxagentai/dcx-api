# Context

The authenticated app shell now depends on additional `app_account_page` UX-string keys for navigation labels, lower user-menu labels, page titles, and compact field-state labels.

# What changed

- Extended `users/account/read_dcx_app_account_page_ux_strings.py` English defaults with the new shell/menu/title/status keys.
- Added missing defaults for:
  - `settings_eyebrow`
  - `settings_title`
  - `settings_subtitle`
  - `activity_subtitle`

# Why

`read_authenticated_dcx_user_account_summary` already returns one multilingual `ux_strings` bundle for the app. Extending that existing group keeps the shell and the page content on one consistent translation path instead of creating a second frontend-only system.

# Seed

Additive SQL file:

- `storage/dcx_seed_app_shell_multilingual_ux_strings_2026_04_10.sql`

This seeds the newly required `app_account_page` rows in English, Spanish, French, and German.

# Next

- Once the seed is applied on local and live, the refreshed `dcx_app` shell should switch language along with the user’s preferred language immediately via the existing account-summary payload.
