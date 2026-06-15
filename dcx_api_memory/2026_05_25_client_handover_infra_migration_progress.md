# 2026-05-25 Client Handover Infrastructure Migration Progress

## Context

DCX is in the client handover phase. The working plan is to move live infrastructure from the developer accounts to the client accounts while keeping service continuity. The code remains the same across the dev and client repositories; the migration changes account ownership, environment variables, DNS, storage, and service endpoints.

## Completed Today

- Confirmed the four repos can be pushed from the new local machine to both the original dev GitHub remotes and the new client GitHub remotes.
- Created and populated the client Render PostgreSQL database from the production dump.
- Verified production and client database shape and row counts matched after restore.
- Pointed the current dev Render API at the client PostgreSQL database, then verified login, app reads, and new message processing wrote to the client database.
- Created the client Render API service from the client GitHub repo.
- Copied API environment variables to the client service and updated DB variables to the neutral DB_* names.
- Created client Cloudflare Pages projects for dcx-public, dcx-app, and dcx-admin.
- Built and deployed the three client frontends to temporary pages.dev URLs.
- Added temporary CORS allowed origins for the three client pages.dev URLs.
- Added temporary auth-cookie settings for cross-site pages.dev to onrender.com testing: SameSite=None, secure cookie, no fixed cookie domain.
- Verified app login works against the client API and client database on the temporary client Pages/App stack.
- Verified app reads existing user data, trades, attachments, and R2-backed file content through the client API.
- Created the client Cloudflare R2 bucket dcx-app-files.
- Copied the 41 existing app-file objects from the dev R2 bucket to the client R2 bucket with rclone, preserving object keys.
- Verified client R2 now contains 41 objects and 25,062,832 bytes / 23.902 MiB.
- Updated the client Render API R2 env vars to point at the client R2 account/bucket.

## Important Implementation Details

- Database object references store R2 file identity by bucket_alias plus object_key.
- For bucket_alias = app, the backend resolves the actual bucket from DCX_R2_APP_BUCKET_NAME.
- Because the R2 object keys were copied unchanged, no database rewrite was needed for migrated attachments.
- The important client R2 bucket name is dcx-app-files.
- dcx-public-files can exist for symmetry, but the app attachment migration depended on dcx-app-files.
- The temporary client API URL is https://dcx-api-k01h.onrender.com.
- Temporary client Pages URLs used during setup:
  - public: https://44653f9a.dcx-public-4yj.pages.dev
  - app: https://dcx-app-4fx.pages.dev
  - admin: https://dcx-admin-q6f.pages.dev

## Code Changes Made During Migration

- dcx_api DB config was refactored from PROMPTEO_DB_* env names to neutral DB_* names.
- dcx_app now supports VITE_ADMIN_BASE_URL so temporary pages.dev cross-surface links do not derive admin.pages.dev.
- dcx_admin now trims and ignores blank VITE_APP_BASE_URL values before falling back.

## Known Remaining Issue

App login works on the temporary client stack, but direct admin login still fails from the temporary admin Pages URL. The app-to-admin link now points to the correct client admin Pages URL, but the admin surface does not yet recognize or carry the existing app session and direct admin login still reports Failed to fetch.

Next useful diagnostic: perform one admin login attempt and check the client Render API logs for OPTIONS /auth/login/password and POST /auth/login/password.

- If no log appears, the admin frontend build is still not calling the client API.
- If OPTIONS fails, revisit allowed origins.
- If POST succeeds but /auth/session returns 401, revisit cookie behavior for the admin origin.
- If POST returns an error status, inspect the response payload/auth route.

## Next Migration Steps

- Point the current dev Render API at the client R2 bucket as well, mirroring the earlier client Postgres cutover, so any new uploads during the remainder of transfer land in the client account.
- Retest existing attachments and one new upload after the dev API R2 env cutover.
- Finish diagnosing temporary admin login.
- Move DNS into the client Cloudflare account and attach final custom domains to Pages/API.
- Move Resend sender domain into the client Resend account after DNS is ready.
- Recreate or move the Cloudflare Worker cron for email jobs.
- Later: migrate or reattach Meta WhatsApp and Twilio integrations.

## Security Note

Do not store raw API keys, database passwords, R2 secrets, Resend secrets, or webhook tokens in this memory note. Secrets were handled in service dashboards and local scratch/reference material during setup and should be rotated as appropriate after handover.
