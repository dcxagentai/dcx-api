# 2026-04-24 Gemini Message Analysis First Pass

## Context

We moved the Messages pipeline from basic storage/derivation language toward the first real multimodal analysis pass.
The app, WhatsApp, and email surfaces were already successfully storing text plus image/audio/document attachments into the canonical message/file tables and R2. The next slice was to analyse each message as a whole while also writing useful per-file analysis back to the file objects.

## Schema State

The user applied the SQL locally and live before implementation continued.

Key additions:
- `stephen_dcx_contact_messages.analysis_status`
- `stephen_dcx_contact_messages.analysis_model_name`
- `stephen_dcx_contact_messages.analysis_metadata_json`
- `stephen_dcx_contact_messages.analysis_completed_at_ts_ms`
- `stephen_dcx_file_objects.analysis_status`
- `stephen_dcx_file_objects.analysis_description_text`
- `stephen_dcx_file_objects.analysis_transcription_text`
- `stephen_dcx_file_objects.analysis_synthesis_text`
- `stephen_dcx_file_objects.context_within_message`
- `stephen_dcx_file_objects.analysis_model_name`
- `stephen_dcx_file_objects.analysis_metadata_json`
- `stephen_dcx_file_objects.analysis_completed_at_ts_ms`
- `stephen_dcx_file_objects.detected_language_id`

The processing-job and analysis-run checks now allow:
- `job_type = analyze_message_content`
- `analysis_stage = message_analysis`

## Implementation

Added `apis/gemini/generate_dcx_gemini_structured_message_analysis.py`.

This provider wrapper:
- Uses `GEMINI_API_KEY`.
- Uses `DCX_GEMINI_MESSAGE_ANALYSIS_MODEL`, then `MODEL_DCX_TEST`, then `gemini-2.5-flash`.
- Sends one prompt plus all stored file bytes in one multimodal request for the current MVP file-size limits.
- Requests JSON output for:
  - message language
  - message summary
  - message text synthesis
  - subject analysis
  - text body analysis
  - per-attachment description/transcription/synthesis/context
- Has a no-key fallback so local/dev environments still complete without blocking the inbox.

Added `messages/process_stored_dcx_contact_message_analysis.py`.

This replaces the old immediate derivation processor in the new paths while preserving compatibility fields for the app:
- Claims one `analyze_message_content` job.
- Locks and marks the message/file objects as processing.
- Reads attachment bytes from R2.
- Calls the Gemini analysis provider, or injected test callable.
- Writes message-level analysis to `stephen_dcx_contact_messages`.
- Writes file-level analysis to `stephen_dcx_file_objects`.
- Writes one `stephen_dcx_contact_message_analysis_runs` trace row.
- Marks unresolved file objects `failed` if analysis fails after they were moved to `processing`.

Updated the app and inbound-envelope create paths to call the new analysis processor:
- `messages/create_authenticated_dcx_app_contact_message.py`
- `messages/ingest_dcx_contact_message_from_inbound_envelope.py`

Updated message read APIs to expose analysis fields:
- `messages/read_authenticated_dcx_user_contact_message_detail.py`
- `messages/read_authenticated_dcx_user_messages_inbox.py`

Updated app message types and inspector display so the right-hand panel shows:
- analysis status badge
- message summary
- attachments
- per-attachment description/transcription/synthesis/context when present
- raw text

The old `derived_text_content` and `derivation_status` columns remain populated for compatibility, but the UX and new pipeline should now think in analysis terms.

## Tests And Verification

Focused backend tests pass:

```text
18 passed in 0.42s
```

Command used:

```powershell
.\.venv\Scripts\python.exe -m pytest apis\gemini\generate_dcx_gemini_structured_message_analysis_test.py messages\create_authenticated_dcx_app_contact_message_test.py messages\read_authenticated_dcx_user_contact_message_detail_test.py messages\read_authenticated_dcx_user_messages_inbox_test.py messages\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py messages\process_dcx_resend_inbound_email_received_webhook_payload_test.py -q
```

App build passes:

```text
tsc -b && vite build
```

The normal Vite large chunk warning remains.

Full backend suite result at this point:

```text
294 passed, 7 failed
```

The seven failures were in older admin/auth/public areas, not in the message-analysis slice:
- public-site publish status tests
- local password URL test
- email placeholder syntax test
- public UX export test
- two admin publish route tests

## Notes For Next Step

Before investor demo:
- Ensure backend environment has `google-genai` installed from `requirements.txt`.
- Ensure live/prod env has `GEMINI_API_KEY` and optionally `DCX_GEMINI_MESSAGE_ANALYSIS_MODEL`.
- Smoke test app, WhatsApp, and email with mixed attachments and confirm:
  - message status becomes ready/completed
  - summary appears
  - file description/transcription/synthesis/context appear
  - analysis run row contains the prompt/run trace

Likely next refinement:
- If Gemini schema handling dislikes nullable JSON-schema unions in live smoke tests, switch nullable fields to string-only with empty string as the canonical unknown value for the provider response, while keeping DB language values nullable.
- Later, split large files into separate file-level analysis jobs followed by a message synthesis job.
