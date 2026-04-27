# 2026_04_26_account_summary_ux_bundle_messages_send_keys_synced

The authenticated app surface was still showing several Messages/Send labels in English even after the live/local `stephen_dcx_ux_strings` seed was applied.

## Cause

The app Messages and Send pages read `ux_strings` from the authenticated `/users/me/account-summary` payload, not directly from the auth UX bundle route.

That account-summary payload is built by:

- `users/account/read_authenticated_dcx_user_account_summary.py`
- which calls `users/account/read_dcx_app_account_page_ux_strings.py`

The DB-backed UX reader only returns keys that exist in `DCX_APP_ACCOUNT_PAGE_DEFAULT_UX_STRINGS`. The new Messages/Send keys had been wired in the frontend and seeded into the database, but they were missing from the backend default map, so the backend never requested or projected them.

## Fix

Synced the backend default UX-string map in:

- `users/account/read_dcx_app_account_page_ux_strings.py`

with the newer Messages/Send keys already present in the frontend defaults, including:

- Send nav/page keys
- message search/filter keys
- show/hide/download labels
- format labels
- compose progress/status labels
- attachment status labels
- description/context/transcription labels
- analysing status label
- title fallback labels

Also extended:

- `users/account/read_dcx_app_account_page_ux_strings_test.py`

to prove that one of the newly added keys (`messages_search_placeholder`) resolves to the requested translated row when present.

## Verification

Focused backend test:

- `read_dcx_app_account_page_ux_strings_test.py` -> `2 passed`

## Practical note

No new SQL is required for this specific fix if the updated multilingual seed has already been pasted into local/live. The remaining step is just to let the backend serve the now-recognized keys and refresh the app surface.
