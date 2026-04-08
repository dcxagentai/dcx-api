App auth and app account multilingual UX-string seeding was prepared so the live multilingual system can now cover:

- unauthenticated app auth routes:
  - `app_auth_common`
  - `app_auth_login_page`
  - `app_auth_password_reset_request_page`
  - `app_auth_password_set_page`
- authenticated account route:
  - `app_account_page`

What was already in code before this note:

- backend route `GET /auth/app-ux-strings-bundle`
- backend shared UX-group fallback reader
- account summary now resolves account-page UX strings by `preferred_language.language_code`
- password reset/setup links now carry `language_code`
- app auth routes now resolve language from:
  - `language_code` query param
  - local storage
  - English fallback
- account page persists preferred language into local storage

What was added in this pass:

- rerunnable SQL seed file:
  - `dcx_site/dcx_api/storage/dcx_seed_app_auth_and_account_multilingual_ux_strings_2026_04_08.sql`

Intent of the SQL:

- insert missing English originals only
- insert missing ES/FR/DE live translations only
- never overwrite current live rows
- rely on `translation_of_id` links back to current English live originals

Expected verification after running the SQL locally and live:

1. set app preferred language to one of `es`, `fr`, `de`
2. logout
3. confirm `/login` appears in that language
4. click forgot-password and confirm reset-request page is in that language
5. receive reset email in that language
6. click the email link and confirm password-set page is in that language
7. save password and confirm return to localized `/login`
8. log in and confirm `/me/account` copy is in that language

No schema changes were needed in this pass.
