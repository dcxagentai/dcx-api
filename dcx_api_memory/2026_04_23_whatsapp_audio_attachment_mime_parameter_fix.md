CONTEXT:
This note records the local multimedia ingest fix made after WhatsApp image and PDF attachments
successfully stored in R2, but WhatsApp audio created only a message row with no attachment.

WHAT HAPPENED:
- WhatsApp image plus caption successfully flowed from Meta webhook to R2 and then to the app preview.
- WhatsApp PDF successfully flowed from Meta webhook to R2 and then appeared as a document attachment.
- WhatsApp audio created a canonical `stephen_dcx_contact_messages` row with `message_format = audio`,
  but no `stephen_dcx_contact_message_attachments` row and no R2 object.

ROOT CAUSE:
- WhatsApp voice/audio payloads can use MIME parameters, commonly `audio/ogg; codecs=opus`.
- The shared attachment validator accepted exact `audio/ogg` but did not strip MIME parameters.
- Because inbound envelope ingest intentionally skips unsupported attachment storage without failing
  the whole message, the message row was stored but the audio file was skipped.

CHANGE MADE:
- `messages/store_dcx_contact_message_attachment_file_object.py` now normalizes content types by
  stripping MIME parameters before supported-format validation.
- The same validator also accepts common first-pass audio MIME variants: `audio/ogg`,
  `application/ogg`, `audio/mpeg`, `audio/mp3`, `audio/wav`, `audio/x-wav`, `audio/mp4`,
  `audio/x-m4a`, `audio/aac`, `audio/aacp`, and `audio/amr`.
- A regression test now proves `audio/ogg; codecs=opus` stores as canonical `audio/ogg`.

VERIFICATION:
- Ran:
  `.\\.venv\\Scripts\\python.exe -m pytest messages\\store_dcx_contact_message_attachment_file_object_test.py messages\\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py -q`
- Result:
  `6 passed in 0.40s`

WHAT COMES NEXT:
- Restart the local backend and resend a WhatsApp voice note/audio message.
- Expected result: message row plus one flat opaque R2 object key in the app bucket, app detail
  shows an audio attachment card, and the browser audio control can play the stored private
  attachment.
