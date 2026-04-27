CONTEXT:
- The DCX app/message slice is live-smoke-testing well enough that remaining work is now operational clarity and UX truthfulness rather than basic plumbing.
- Gemini message analysis had already been moved to the provider-first env name `GEMINI_MESSAGE_ANALYSIS_MODEL`, but the backend still accepted older aliases and a local default fallback.

WHAT CHANGED:
- `read_dcx_gemini_message_analysis_model_name.py` now reads only `GEMINI_MESSAGE_ANALYSIS_MODEL`.
- The helper now raises `RuntimeError("API_DCX_GEMINI_MESSAGE_ANALYSIS_MODEL_NOT_CONFIGURED")` if the env is missing instead of silently falling back to:
  - `DCX_GEMINI_MESSAGE_ANALYSIS_MODEL`
  - `MODEL_DCX_TEST`
  - `gemini-2.5-flash`
- The focused helper tests were updated to match the new strict contract.
- Existing Gemini structured-analysis tests were kept green by ensuring the missing-API-key fallback test still sets a model env explicitly.

WHY:
- The team wants the message-analysis model configuration to fail loudly and quickly if it is wrong in live or local environments.
- By removing hidden fallbacks, misconfiguration becomes visible immediately instead of being masked by stale defaults.

VERIFICATION:
- Focused pytest run passed:
  - `read_dcx_gemini_message_analysis_model_name_test.py`
  - `generate_dcx_gemini_structured_message_analysis_test.py`

OPERATIONAL NOTE:
- Live and local environments should now use only `GEMINI_MESSAGE_ANALYSIS_MODEL`.
- If that env is missing, analysis should fail clearly rather than drifting onto a hidden fallback model.
