First WhatsApp account-link backend slice added.

What is now in place:
- Meta WhatsApp OTP provider adapter:
  - `apis/meta_whatsapp/send_dcx_whatsapp_otp_template_message.py`
- Shared phone-link OTP support:
  - E.164 normalization
  - six-digit OTP normalization
  - OTP generation
  - OTP hashing with dedicated secret fallback
- Account-phone capabilities:
  - read active delivered pending WhatsApp link
  - prepare pending WhatsApp OTP delivery
  - mark provider delivery sent
  - verify WhatsApp OTP and promote confirmed phone into `stephen_dcx_users`
- Authenticated app routes:
  - `POST /users/me/account-phone/request-whatsapp-otp`
  - `POST /users/me/account-phone/verify-whatsapp-otp`
- Account summary now includes:
  - `pending_whatsapp_phone_link`

Important design choices:
- We do not write the candidate phone directly into the live confirmed user row.
- Pending phone-link state lives in `stephen_dcx_user_auth_challenges`.
- Only after OTP verification do we:
  - update `primary_phone_e164`
  - set `primary_phone_confirmed = true`
  - set `primary_phone_channel = 'whatsapp'`
  - insert/update one WhatsApp auth identity row
- Pending summary only exposes delivered challenges (`sent_at_ts_ms IS NOT NULL`) so the UI does not show an OTP state for failed sends.

Meta/ops assumptions:
- Current outbound send uses Meta Cloud API template send.
- Required env:
  - `META_WHATSAPP_TOKEN`
  - `META_PHONE_NUMBER_ID`
  - `META_WHATSAPP_OTP_TEMPLATE_NAME`
- Optional:
  - `META_WHATSAPP_OTP_TEMPLATE_LANGUAGE_CODE`
  - `META_API_VERSION`
- OTP hashing secret:
  - prefers `DCX_WHATSAPP_PHONE_OTP_SECRET`
  - falls back to `DCX_EMAIL_SIGNUP_OTP_SECRET`

Verification status:
- changed backend files `py_compile` clean
- no full pytest run completed from this shell because local environment still lacks working `psycopg2`/repo test execution outside the project venv

Next likely step:
- wire inbound WhatsApp webhook handshake and message persistence using this now-confirmed WhatsApp identity bridge
