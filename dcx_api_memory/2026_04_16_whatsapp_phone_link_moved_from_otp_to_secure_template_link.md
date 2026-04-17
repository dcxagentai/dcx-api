# 2026_04_16_whatsapp_phone_link_moved_from_otp_to_secure_template_link

This note records the first DCX WhatsApp phone-verification refactor from copy-paste OTP entry to a Meta template button carrying a secure app-domain link.

What changed:

- Added shared WhatsApp phone-link token helpers in:
  - `users/account_phone/dcx_whatsapp_phone_link_challenge_support.py`
- Added a new authenticated preparation capability:
  - `users/account_phone/prepare_authenticated_dcx_user_whatsapp_phone_link_delivery.py`
- Added a new token-consumption capability:
  - `users/account_phone/verify_dcx_whatsapp_phone_link_from_challenge_token.py`
- Added a Meta adapter for the approved positional URL-button template:
  - `apis/meta_whatsapp/send_dcx_whatsapp_verification_template_message.py`
- Added a new authenticated send route:
  - `POST /users/me/account-phone/request-whatsapp-verification-link`
- Added a new unauthenticated token verify route:
  - `POST /users/account-phone/verify-whatsapp-link`
- Updated the app account page to send/resend WhatsApp verification links instead of rendering an OTP entry field.
- Added a new app route/page:
  - `/:language_code/t/verify-whatsapp-phone`
  - This captures `#whatsapp_phone_link_token=...`, stores it in session storage, calls the API verification route, and then redirects onward.

Current template assumptions:

- Using the approved Meta template:
  - `dcx_agentic_verify_account`
- Current parameter usage:
  - body `{{1}}` => `"there"`
  - body `{{2}}` => normalized phone number
  - URL button `{{1}}` => localized app-path suffix carrying the fragment token
- Example final button URL shape:
  - `https://app.dcxagent.ai/en/t/verify-whatsapp-phone#whatsapp_phone_link_token=<opaque_token>`

Important implementation choices:

- Token is carried in the URL fragment, not query or path, to match the safer pattern already used for password/signup browser handoffs.
- Verification is token-only and does not require an authenticated session, so a WhatsApp click can still succeed from a browser that is not already signed in.
- The old OTP routes/files still exist in the repo for now, but the app root now includes only the new link-based routes.

Verification status from this session:

- Backend changed files passed `py_compile`.
- Frontend changed files passed `tsc -b`.
- Full `npm run build` from the desktop shell still hit the same sandbox-side `esbuild` spawn `EPERM` issue as earlier; this should still be rechecked from the user's normal shell.
- Direct repo-venv pytest from this shell still hit the same Windows access-denied process-spawn issue; the focused pytest run should be done from the user's normal shell.

Next recommended checks in the user's shell:

1. Backend focused pytest for:
   - signup/password/login/account-phone block
   - session/account-summary block if needed
2. Frontend:
   - `npm run build`
3. Local simulation:
   - trigger/send route without WhatsApp delivery if desired
   - manually open:
     - `http://localhost:5173/en/t/verify-whatsapp-phone#whatsapp_phone_link_token=<raw_token>`
4. Live end-to-end:
   - send the real template
   - click the WhatsApp button
   - confirm phone verifies and account summary reflects it
