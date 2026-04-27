Context
- Live app-message sends were storing message rows correctly, but newer rows could fail the Gemini analysis stage under transient provider 503 load.
- The live detail route had already been unblocked separately by adding the missing `stephen_dcx_file_objects.file_uuid` column in production.

What changed
- Added `apis/gemini/read_dcx_gemini_message_analysis_model_name.py` as the source of truth for message-analysis model selection.
- New precedence is:
  1. `GEMINI_MESSAGE_ANALYSIS_MODEL`
  2. `DCX_GEMINI_MESSAGE_ANALYSIS_MODEL`
  3. `MODEL_DCX_TEST`
  4. local fallback `gemini-2.5-flash`
- Updated Gemini analysis code to use that helper and updated tests accordingly.
- Updated failed-analysis persistence to keep the configured Gemini model name even when the LLM call fails, so the UI can still show which model was attempted.
- Added authenticated retry route:
  - `POST /users/me/messages/{message_id}/retry-analysis`
  - file: `routes/users/dcx_api_routes_users_me_messages_retry_analysis.py`
- Route re-runs `process_stored_dcx_contact_message_analysis(message_id=...)` for a user-owned message and returns the refreshed canonical detail payload.

Verification
- Focused backend tests passed:
  - Gemini model-name helper tests
  - Gemini structured analysis tests
  - app route tests including retry-analysis route

Operational note
- Code is backward compatible with the old env name, so live can deploy before Render env cleanup.
- Longer-term desired env naming direction is provider-first, so `GEMINI_MESSAGE_ANALYSIS_MODEL` should become the live canonical key.
