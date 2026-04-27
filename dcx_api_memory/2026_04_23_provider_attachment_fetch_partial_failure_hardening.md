CONTEXT:
This note records the provider-side hardening pass done after the app surface upload route was fixed
and local app multimedia smoke tests succeeded.

PROBLEM:
- App uploads were now robust, but the provider adapters were still more brittle than the shared
  ingest/store layer beneath them.
- In both WhatsApp and Resend inbound email, attachment/media bytes were fetched before canonical
  ingest.
- A single provider fetch failure could abort the entire inbound message before
  `ingest_dcx_contact_message_from_inbound_envelope` had a chance to store the message and preserve
  the successfully retrieved attachments.

WHAT CHANGED:
- Resend attachment fetching now has a richer helper result:
  - `attachment_inputs`
  - `skipped_attachment_reads`
- The legacy `read_dcx_resend_received_email_attachment_inputs` function still returns the plain
  list for compatibility, but it now delegates to the richer fetch-result helper.
- Resend inbound processing now accepts either:
  - the older list-only attachment result, or
  - the richer dict result
- Resend skipped attachment fetches are now recorded into message metadata under:
  - `resend_skipped_attachment_reads`
- WhatsApp inbound processing now catches per-attachment media fetch failures, keeps the successful
  attachments, and records skipped fetches into message metadata under:
  - `meta_skipped_attachment_reads`

WHY:
- One bad provider attachment should not prevent an otherwise valid inbound message from appearing in
  the DCX Messages inbox.
- This keeps provider behavior better aligned with the shared ingest layer, which already tolerates
  per-attachment store failures and records skip information.

FILES CHANGED:
- `apis/resend/read_dcx_resend_received_email_attachment_inputs.py`
- `apis/resend/read_dcx_resend_received_email_attachment_inputs_test.py`
- `messages/process_dcx_resend_inbound_email_received_webhook_payload.py`
- `messages/process_dcx_resend_inbound_email_received_webhook_payload_test.py`
- `messages/process_dcx_meta_whatsapp_inbound_webhook_payload.py`
- `messages/process_dcx_meta_whatsapp_inbound_webhook_payload_test.py`

VERIFICATION:
- Focused tests:
  `.\\.venv\\Scripts\\python.exe -m pytest apis\\resend\\read_dcx_resend_received_email_attachment_inputs_test.py messages\\process_dcx_resend_inbound_email_received_webhook_payload_test.py messages\\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py -q`
- Result: `8 passed in 0.43s`
- Broader backend message/file tests:
  `.\\.venv\\Scripts\\python.exe -m pytest dcx_api_app_test.py apis\\resend\\read_dcx_resend_received_email_attachment_inputs_test.py messages\\store_dcx_contact_message_attachment_file_object_test.py messages\\create_authenticated_dcx_app_contact_message_test.py messages\\read_authenticated_dcx_user_contact_message_detail_test.py messages\\read_authenticated_dcx_user_file_object_stream_by_file_uuid_test.py messages\\read_authenticated_dcx_user_contact_message_attachment_stream_test.py messages\\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py messages\\process_dcx_resend_inbound_email_received_webhook_payload_test.py -q`
- Result: `59 passed in 1.26s`

NEXT STEP:
- Re-run inbound email smoke tests with:
  - one image attachment
  - one PDF attachment
  - multiple mixed supported attachments
  - one deliberately awkward attachment case to confirm the new partial-failure behavior
