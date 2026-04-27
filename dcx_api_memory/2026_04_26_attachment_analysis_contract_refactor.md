## Context

We refactored the first Gemini contact-message analysis contract to stop asking every attachment for every possible field. The previous shape worked technically but was too broad and started to create unnecessary prompt/response noise once the Messages UI became more disciplined and human-readable.

## Schema change

Added a new schema migration file:

- `dcx_api/storage/dcx_add_file_object_attachment_summary_2026_04_26.sql`

This adds:

- `stephen_dcx_file_objects.analysis_summary_text TEXT NOT NULL DEFAULT ''`

The new field exists because attachment-level summary is now a first-class concept and should not be overloaded into `analysis_description_text`.

## New attachment contract

Attachment rules after this refactor:

- image:
  - `analysis_summary_text`
  - `analysis_description_text`
  - `context_within_message`
  - no transcription
  - no synthesis

- audio:
  - `analysis_summary_text`
  - `analysis_transcription_text`
  - `analysis_synthesis_text`
  - `context_within_message`
  - no description

- document:
  - `analysis_summary_text`
  - `analysis_synthesis_text`
  - `context_within_message`
  - no description
  - no transcription

All attachments still retain:

- detected language
- model / metadata / completed timestamp

## New message text rules

Message-level text analysis is now deterministic before the prompt is assembled:

- `<100 words`:
  - no message summary
  - no message synthesis

- `100+ words`:
  - request 1-3 sentence message summary

- `500+ words`:
  - request detailed message synthesis

This means Gemini is no longer asked to decide for itself whether the message deserves summary or synthesis.

## Prompt / response refactor

Updated:

- `dcx_api/apis/gemini/generate_dcx_gemini_structured_message_analysis.py`

Key changes:

- prompt version bumped to:
  - `dcx_contact_message_analysis_2026_04_26_v3`
- removed the unused `subject_analysis` and `text_body_analysis` response blocks
- added attachment `summary` to the schema
- tightened per-modality instructions:
  - images: description + summary + context
  - audio: transcription + summary + synthesis + context
  - documents: summary + synthesis + context
- enforced modality-specific blanking in normalization, so even if Gemini drifts, stored fields remain canonical

## Persistence / read-path changes

Updated:

- `dcx_api/messages/process_stored_dcx_contact_message_analysis.py`
- `dcx_api/messages/read_authenticated_dcx_user_contact_message_detail.py`

Key behavior changes:

- `stephen_dcx_contact_messages.derived_text_content` now stores actual message synthesis only
  - it no longer falls back to raw text
- `stephen_dcx_file_objects.analysis_summary_text` is now persisted for each attachment
- message-detail reads now include attachment `analysis_summary_text`

## App/UI alignment

Updated:

- `dcx_app/src/lib/read_dcx_app_authenticated_user_message_detail.ts`
- `dcx_app/src/components/dcx_app_messages_page.tsx`

Attachment analysis rendering now matches modality semantics:

- image cards:
  - Summary
  - Description
  - Context

- audio cards:
  - Summary
  - Synthesis
  - Transcription
  - Context

- document cards:
  - Summary
  - Synthesis
  - Context

Also updated the message-summary display threshold in the app from `200` words to `100` so the UI matches the backend prompting rule.

## Verification

Backend focused tests:

- `apis/gemini/generate_dcx_gemini_structured_message_analysis_test.py`
- `messages/read_authenticated_dcx_user_contact_message_detail_test.py`

Result:

- `8 passed`

Frontend:

- `npm run build` passed
- only the existing Vite large-chunk warning remains

## Follow-up

Once the SQL is applied locally and live, smoke test:

- short text-only message (<100 words)
- mid-length text (100-300 words)
- long text (500+ words)
- image-only message
- audio-only message
- document-only message
- mixed message with multiple attachment modalities

The key thing to verify is that empty/irrelevant fields now stay genuinely absent from the UI because the backend contract is narrower and cleaner.
