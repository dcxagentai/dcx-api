CONTEXT:
On 2026-07-09, the first successful Gemini Interactions translation run produced native-script
slugs for Chinese, Hindi, Urdu, and Arabic, but Russian still returned a romanized slug.

OBSERVATION:
- The Russian translation job failed with
  `API_DCX_GEMINI_ADMIN_TRANSLATION_NATIVE_SCRIPT_SLUG_MISMATCH`.
- Gemini returned `politika-konfidentsialnosti-whatsapp`.
- The validator correctly rejected it because Russian page/category slugs should contain Cyrillic.

CHANGE:
- Prompt version advanced to `dcx_admin_structured_translation_2026_07_09_v8`.
- Added a concrete Russian slug example:
  `политика-конфиденциальности-whatsapp`.
- Added target-language-specific schema descriptions for native-script slug fields.
- Added retry feedback that explicitly says Russian slugs must use Cyrillic words, not romanized
  Latin-script words.

EXPECTED BEHAVIOR:
- Retrying translation for the WhatsApp privacy page should produce a Russian slug such as
  `политика-конфиденциальности-whatsapp`.
