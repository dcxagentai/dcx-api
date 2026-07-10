CONTEXT:
On 2026-07-10, Japanese was added to the DCX language reference and admin AI translation prompt path.

CHANGE:
- Added `storage/dcx_add_japanese_language_2026_07_10.sql` to upsert active language code `ja`
  with English name `Japanese`, native name `Japanese` rendered by SQL Unicode escapes, `is_rtl = false`,
  and `is_default = false`.
- Updated `storage/dcx_seed_summer_marketing_reference_data_2026_06_23.sql` so fresh seeded
  environments include Japanese.
- Updated `apis/gemini/translate_dcx_gemini_structured_admin_content.py` prompt version to
  `dcx_admin_structured_translation_2026_07_10_v9`.
- Added Japanese to the native-script slug validation set, language profile map, schema description,
  prompt instructions, and slug examples.
- Added a unit test proving a romanized Japanese slug is rejected and retried into native Japanese text.

WHY:
- Japanese is strategically relevant for commodities, finance, and global market credibility.
- The translation workflow should treat Japanese like the other non-Latin/script-sensitive languages,
  not as a Latin transliteration target.

CHECKS:
- `.venv\Scripts\python.exe -m pytest apis\gemini\translate_dcx_gemini_structured_admin_content_test.py`
  passed: 10 tests.
