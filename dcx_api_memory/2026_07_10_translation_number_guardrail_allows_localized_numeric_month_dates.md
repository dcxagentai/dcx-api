CONTEXT:
Japanese and Vietnamese page translations failed the strict admin translation number guardrail
after Japanese was added as a core language. The source page used an English month-name date,
`16 June 2026`, while Gemini returned localized numeric-month date forms such as
`2026年6月16日` and `16 thang 6 nam 2026`.

DECISION:
Keep the strict number guardrail, but make it date-aware for English month-name source dates.
The validator now accepts a localized numeric month only when the translated field contains the
same calendar date. It still rejects a wrong numeric month and still compares all non-date
digit-bearing tokens normally.

IMPLEMENTATION:
- Prompt version bumped to `dcx_admin_structured_translation_2026_07_10_v10`.
- Number token extraction no longer merges arbitrary space-separated numbers such as `16 6 2026`
  into a single fake number.
- Date-aware validation removes matched source/target date spans before comparing the remaining
  number counters.
- Added regression tests for Vietnamese `16 thang 6 nam 2026`, Japanese `2026年6月16日`, and a
  wrong Japanese month rejection.

VERIFICATION:
`python -m pytest apis/gemini/translate_dcx_gemini_structured_admin_content_test.py` passed with
13 tests.
