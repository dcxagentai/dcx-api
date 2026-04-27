## 2026-04-22 Messages Multimedia First Pass Across App, Email, and WhatsApp

### Context
- The prior slice already proved text-only intake locally through the three initial channels:
  - app
  - inbound email via Resend
  - inbound WhatsApp via Meta
- This pass extends the same canonical message system to preserve raw attachments in Cloudflare R2 and surface them in the app `Messages` UI.

### What Changed
- Added shared R2 helpers for the canonical backend path:
  - `files/build_dcx_r2_s3_client.py`
  - `files/read_dcx_r2_bucket_name_for_alias.py`
- Added one shared attachment store capability:
  - `messages/store_dcx_contact_message_attachment_file_object.py`
- Added one shared message-format helper so mixed text-plus-file messages stay consistent:
  - `messages/read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds.py`
- Extended authenticated app message create flow to accept:
  - text only
  - attachments only
  - mixed text + attachments
- Extended canonical provider ingest to persist supported attachments for:
  - Resend inbound email
  - Meta WhatsApp inbound media
- Added one authenticated attachment read route for the app:
  - `GET /users/me/messages/{message_id}/attachments/{attachment_id}/file`
- Extended message detail reads to include attachment metadata and route paths.

### Current Product Shape
- One file-size limit for now:
  - `5 MB`
  - configurable via `DCX_CONTACT_MESSAGE_ATTACHMENT_MAX_BYTES`
- First accepted file families:
  - images: `jpg`, `jpeg`, `png`, `webp`
  - audio: `mp3`, `ogg`, `wav`, `m4a/mp4 audio`
  - documents: `pdf`, `docx`, `pptx`
- Explicitly not supported yet:
  - video
  - spreadsheets
  - legacy `doc` / `ppt`

### Shared Flow
- App uploads now create attachment rows directly from the app route.
- Resend inbound email now tries to fetch attachment inputs from the receiving attachments API and passes them into the same canonical ingest function.
- Meta WhatsApp inbound media messages now download media bytes by media id and pass them into the same canonical ingest function.
- All three channels now converge on:
  - `stephen_dcx_contact_messages`
  - `stephen_dcx_file_objects`
  - `stephen_dcx_contact_message_attachments`

### UX Outcome
- The app Messages detail pane now reads the real detail endpoint and shows:
  - raw text
  - derived text
  - summary
  - attachments list
  - image preview
  - audio player
  - open-attachment link for documents or other supported files

### Important Limits Of This Pass
- No OCR, transcription, document synthesis, or richer LLM processing yet.
- Attachment-only messages still fall through the existing no-text derivation path, so the summary is still the fallback text until the later LLM slice lands.
- Provider attachment retrieval is implemented, but deeper live provider verification for non-text media still needs real-world smoke tests.

### Verification
- Focused backend suite passed:
  - `44 passed`
- App production build passed:
  - `npm run build`

### Next Likely Step
- Real LLM attachment derivation:
  - image description / OCR
  - audio transcript
  - document extraction / synthesis
- Then message-type classification and routing into Trades / Questions / Other.
