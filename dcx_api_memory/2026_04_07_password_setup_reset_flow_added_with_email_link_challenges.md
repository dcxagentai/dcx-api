Password setup/reset is now implemented on top of the existing shared auth/session model without adding new schema tables.

What was added:
- Reused `stephen_dcx_user_auth_challenges` for password links using:
  - `challenge_type = password_link`
  - `challenge_purpose = password_setup | password_reset`
- Added password-link helpers in `auth/password/`.
- Added password validation with current MVP rules:
  - minimum length 12
  - maximum length 200
  - confirmation must match
- Added completion capability that:
  - validates the one-time token
  - hashes the password with argon2id
  - upserts `stephen_dcx_user_password_credentials`
  - consumes the challenge row
  - revokes all active sessions for that user
- Added reset email draft/send path.
- Added routes:
  - `POST /auth/password/request-reset`
  - `POST /auth/password/complete-set`

Signup handoff:
- `POST /users/signup-email/verify-otp` now tries to create a password-setup link after OTP confirmation.
- On success the browser payload includes `data.next_step_url`.
- The public OTP form now redirects to that app-side password-set URL instead of going straight to the thank-you page when a setup URL is available.

Important UX/surface decisions:
- Password setup/reset UI lives on `dcx_app`, not `dcx_public` or `dcx_admin`.
- Admin forgot-password links hand off to the app reset page.
- Tokens are carried in the URL fragment and then normalized client-side into session storage before submit.

Email/template behavior:
- Reset email attempts to read live template key `transactional / auth_password_reset`.
- If the template does not exist yet, the backend falls back to a minimal inline English reset email so the flow is not blocked.

Verification completed:
- `pytest auth\password auth\session emails\transactional -q` -> `30 passed`
- `pytest dcx_api_app_test.py -q` -> `25 passed`

Known next step:
- Seed and manage a proper `auth_password_reset` live email template in `stephen_dcx_emails` so reset copy is fully admin-editable like the other transactional emails.
