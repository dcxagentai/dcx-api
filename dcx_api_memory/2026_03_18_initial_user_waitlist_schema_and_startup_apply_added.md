## Summary

This session added the first durable user-domain schema foundation for the DCX MVP backend.

The backend now has a dedicated initial schema SQL file plus a startup-applied schema capability that ensures the first four project-prefixed tables exist without seeding demo rows or deleting any existing data.

## What Was Added

New schema SQL file:
- `dcx_storage/dcx_initial_user_waitlist_schema_2026_03_18.sql`

New schema apply capability:
- `dcx_storage/dcx_apply_initial_user_waitlist_schema_to_configured_database.py`

New adjacent tests:
- `dcx_storage/dcx_apply_initial_user_waitlist_schema_to_configured_database_test.py`

Updated startup path:
- `dcx_api_app.py`

## Ensured Tables

The schema-init capability now ensures:

- `stephen_dcx_languages`
- `stephen_dcx_users`
- `stephen_dcx_user_auth_identities`
- `stephen_dcx_user_auth_challenges`

## Schema Conventions Applied

- all tables use project-prefixed names
- all tables use autoincrement integer primary keys
- `stephen_dcx_users` also has a stable external `user_uuid`
- all persistent time fields use unix epoch milliseconds in `BIGINT`
- all tables include:
  - `created_at_ts_ms`
  - `updated_at_ts_ms`
- a shared trigger function updates `updated_at_ts_ms` on row updates

## Startup Behavior

The FastAPI app now applies this initial schema at startup using:

- `apply_initial_user_waitlist_schema_to_configured_database()`

This is intentionally idempotent and should be safe on repeated local and Render startups.

## Scope Boundary

This change does not yet implement:

- signup API routes
- OTP generation
- OTP verification
- UI changes
- content translation tables

It only establishes the first durable user-domain schema foundation and the backend-side schema-init hook.

## Important Modeling Decisions Captured

- `account_status` is used instead of a narrower `waitlist_status`
- email is expected to be normalized before storage, not duplicated in a separate normalized DB column
- auth identities and auth challenges are separated from the core users table to support future login paths such as Google, X, Telegram, and WhatsApp
- language data is introduced early because later public content and email translation work will depend on it

## Next Likely Steps

1. implement backend capabilities for:
   - ensure-or-create user
   - ensure-or-create email auth identity
   - create or refresh email OTP challenge
   - verify OTP challenge
2. add API routes that project those capabilities cleanly
3. add the public landing page signup and OTP frontend flow
4. later tighten security and abuse prevention after the basic mechanics work
