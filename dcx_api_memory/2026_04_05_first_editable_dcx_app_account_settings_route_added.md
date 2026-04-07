The first editable `dcx_app` account-save backend contract is now in place.

Files added:
- `users/account/save_authenticated_dcx_user_account_editable_settings.py`
- `users/account/save_authenticated_dcx_user_account_editable_settings_test.py`
- `routes/users/dcx_api_routes_users_me_account_settings.py`

Files updated:
- `routes/users/dcx_api_routes_users_support.py`
- `users/account/read_authenticated_dcx_user_account_summary.py`
- `users/account/read_authenticated_dcx_user_account_summary_test.py`
- `routes/users/dcx_api_routes_users_me_account_summary.py`
- `dcx_api_app.py`
- `dcx_api_app_test.py`

What this backend slice does:
- Adds `POST /users/me/account-settings`
- Keeps the current account read route at `GET /users/me/account-summary`
- Enriches the account-summary payload with:
  - `available_languages`
  - `available_email_communication_preferences`
- Saves the first low-risk editable account fields:
  - `preferred_language_id`
  - `email_communication_preference`

Important implementation decision:
- User rows remain mutable.
- The save capability still uses one upsert-shaped write path rather than branching into separate insert/update statements.
- The capability intentionally does **not** touch `primary_email`; that change needs its own verification flow later.

Temporary identity strategy:
- The app routes now share one helper for temporary local `?user_id=` handling.
- In `local` or `development`, app routes may use `?user_id=<id>`.
- Without that local debug id:
  - `401`
  - `API_USERS_ME_AUTH_REQUIRED`
- Outside local/development, the debug user-id path is rejected with:
  - `400`
  - `API_USERS_ME_DEBUG_USER_ID_FORBIDDEN`

Editable field rules:
- `preferred_language_id`
  - may be `null`
  - must refer to one active row in `stephen_dcx_languages` when present
- `email_communication_preference`
  - currently allowed values:
    - `announcements`
    - `essential_only`

Why this shape was chosen:
- It proves inline autosave and write contracts on low-risk fields first.
- It avoids faking an unsafe primary-email edit before the proper verification flow exists.
- It keeps the app route contracts stable while real auth is still pending.

Verification:
- focused backend result: `27 passed`
- includes:
  - account summary capability tests
  - account settings save capability tests
  - app assembly / route tests

Next most natural backend step:
- add the real verified email-change flow later
- reuse the same save/refresh contract pattern for future account mutations that are safe to inline-edit
