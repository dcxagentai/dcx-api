Messages App Text Intake First Vertical Slice

Date
- 2026-04-21

What shipped
- Committed the SQL migration file for the new contact-message intake tables under `storage/`.
- Registered the authenticated app Messages routes in `dcx_api_app.py`.
- Added route coverage in `dcx_api_app_test.py` for:
  - inbox read
  - message create
  - message detail read
- Kept the backend scope deliberately narrow for this first vertical slice:
  - authenticated app-originated text messages only
  - no WhatsApp webhook intake yet
  - no Resend inbound email yet
  - no attachments/media ingest yet
  - no trade/question classification yet

Important backend shape
- Canonical persistence already uses the new tables:
  - `stephen_dcx_contact_messages`
  - `stephen_dcx_contact_message_processing_jobs`
  - `stephen_dcx_contact_message_analysis_runs`
- The create capability:
  - writes the inbound app message
  - writes a derivation job row
  - runs the first derivation pass immediately
  - updates the message and job state
  - writes an analysis run row
- Derivation remains intentionally first-pass only:
  - normalize/clean text
  - synthesize summary
  - detect language when possible
  - no business-intent classification yet

Important implementation note
- `messages/create_authenticated_dcx_app_contact_message.py` needed an explicit `import psycopg2.extras` because the capability writes JSON fields via `psycopg2.extras.Json`.

Verification
- Focused backend pytest suite passed:
  - `dcx_api_app_test.py`
  - `messages/create_authenticated_dcx_app_contact_message_test.py`
  - `messages/derive_dcx_contact_message_text_and_language_with_llm_test.py`
  - `messages/read_authenticated_dcx_user_messages_inbox_test.py`
  - `messages/read_authenticated_dcx_user_contact_message_detail_test.py`

What comes next
- Wire the authenticated app surface to richer detail reads if we want attachment panels later.
- Add background-worker execution as a second step if derivation should move out of the request lifecycle.
- Add WhatsApp inbound webhook normalization on top of the same canonical tables.
- Add Resend inbound email webhook + content fetch on top of the same canonical tables.
- Add multimodal ingest:
  - images
  - audio
  - documents
- Only after that, add the next-stage classification layer:
  - trade candidate
  - reply candidate
  - market question
  - noise / other
