DCX API prohibited-content MVP firewall

Date: 2026-04-27

Summary
- Added a first prohibited-content moderation path to the existing Gemini message-analysis flow.
- This is intentionally a lightweight MVP implementation for demos and early client confidence, not a full legal/policy system.

Key implementation choices
- Reused the existing `generate_dcx_gemini_structured_message_analysis` call instead of adding a second moderation provider or job.
- Stored moderation results inside `stephen_dcx_contact_messages.analysis_metadata_json` rather than adding new schema columns.
- Preserved the message row for auditability and UX continuity.
- Redacted blocked message content and hid attachments/downloads when moderation returns prohibited.

Moderation codes
- `prohibited_children`
- `prohibited_sexually_explicit`
- `prohibited_exploitation_or_trafficking`
- `prohibited_drugs`
- `prohibited_weapons_explosives_conventional`
- `prohibited_weapons_nuclear_chemical`
- `prohibited_extremism_terrorism`
- `prohibited_organised_crime`
- `prohibited_fraud`
- `prohibited_sanctions`

Backend behavior
- Gemini structured output now returns:
  - `moderation_status`
  - `moderation_reason_summary`
  - `matched_prohibited_categories`
- When prohibited:
  - message row is kept
  - `message_subject`, `raw_text_content`, and `derived_text_content` are blanked
  - `analysis_summary_text` becomes `Message blocked for prohibited content.`
  - moderation metadata is written into `analysis_metadata_json`
  - attachment analysis text is blanked and attachment reads are blocked

Protected read surfaces
- `messages/read_authenticated_dcx_user_messages_inbox.py`
  - returns `analysis_metadata_json`
  - redacts prohibited message text and attachment summaries
- `messages/read_authenticated_dcx_user_contact_message_detail.py`
  - redacts prohibited message content
  - returns no attachments for prohibited messages
- `messages/read_authenticated_dcx_user_contact_message_attachment_stream.py`
  - denies attachment streaming for prohibited parent messages
- `messages/read_authenticated_dcx_user_file_object_stream_by_file_uuid.py`
  - also denies flat file access when parent message moderation metadata is prohibited

Tests run
- `apis/gemini/generate_dcx_gemini_structured_message_analysis_test.py`
- `messages/read_authenticated_dcx_user_messages_inbox_test.py`
- `messages/read_authenticated_dcx_user_contact_message_detail_test.py`
- `messages/read_authenticated_dcx_user_contact_message_attachment_stream_test.py`
- `messages/read_authenticated_dcx_user_file_object_stream_by_file_uuid_test.py`
- Result: 20 passed

Follow-up ideas
- Add a dedicated moderation status column set if/when we want queryability without reading JSON.
- Add a review/manual override workflow later.
- Decide later with legal/compliance whether prohibited raw content should be hard-deleted after classification rather than just redacted from user-facing reads.
