CONTEXT:
On 2026-07-09, production admin translation jobs failed after moving the translation provider
boundary to Gemini Interactions.

CAUSE:
- `requirements.txt` pinned `google-genai>=1.0,<2.0`.
- Render installed the 1.x SDK.
- Google rejected the legacy Interactions schema with HTTP 400:
  `The legacy Interactions API schema is no longer supported. Please upgrade your google-genai
  Python SDK to version >= 2.0.0`.

FIX:
- Updated `requirements.txt` to `google-genai>=2.0,<3.0`.

EXPECTED DEPLOY BEHAVIOR:
- Render should install the v2 SDK on the next backend deployment.
- Admin translation jobs should then use the current Interactions request schema already wired in
  `apis/gemini/translate_dcx_gemini_structured_admin_content.py`.

FOLLOW-UP:
- If Interactions still fails after dependency upgrade, inspect the v2 SDK response object shape
  first. The provider boundary currently reads `output_text` and falls back to `text`.
