CONTEXT:
On 2026-07-09, the admin AI translation provider boundary was moved from Gemini Generate
Content to Gemini Interactions for structured CMS/email translations.

CHANGE:
- `apis/gemini/translate_dcx_gemini_structured_admin_content.py` now calls
  `client.interactions.create(...)` with `response_format` set to
  `mime_type=application/json` and a generated response schema for the exact target language
  and source field names.
- Prompt version advanced to `dcx_admin_structured_translation_2026_07_09_v7`.
- The existing JSON parsing, exact field-name validation, placeholder/URL/commercial token
  checks, and number guardrails remain in place after the provider response.
- Native-script slug validation was added for `page_slug` and `category_slug` in Arabic,
  Hindi, Urdu, Chinese, and Russian so romanized slug responses become retryable validation
  failures.

WHY:
- Gemini's Interactions API is the forward path for structured responses.
- API-level JSON shape control reduces malformed output risk.
- Schema alone does not enforce DCX business semantics such as native-script slugs, so backend
  validation still owns those guarantees.

VERIFICATION:
- Ran:
  `.venv\Scripts\python.exe -m pytest apis\gemini\translate_dcx_gemini_structured_admin_content_test.py admin\translations\process_due_dcx_admin_ai_translation_jobs_test.py`
- Result: 11 passed.
