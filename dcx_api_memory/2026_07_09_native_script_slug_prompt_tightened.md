# Native Script Slug Prompt Tightened

## Summary
- Updated the structured admin translation prompt from `dcx_admin_structured_translation_2026_07_09_v5` to `dcx_admin_structured_translation_2026_07_09_v6`.
- Tightened slug instructions so Arabic, Hindi, Urdu, Chinese, and Russian slug fields must use native script for generic translatable words.
- Explicitly disallowed pinyin and romanized Hindi/Urdu/Arabic/Russian in slug fields.
- Kept room for brand/company/product names to remain in their usual written form while requiring generic words such as privacy and policy to be translated into the target language/script.
- Replaced the Hindi slug example containing Latin `url` with a fully Devanagari example.

## Operational Notes
- This is still a prompt-only change. If Gemini continues returning romanized slugs for native-script languages, the next robust step is a validator that rejects ASCII-only slug fields for configured native-script target languages.
