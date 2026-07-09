# AI Translation Slug Prompt Tightened

## Summary
- Updated the Gemini structured admin translation prompt from `dcx_admin_structured_translation_2026_07_09_v4` to `dcx_admin_structured_translation_2026_07_09_v5`.
- Kept the existing JSON response shape unchanged for this pass.
- Made URL slug translation explicit:
  - slug fields are not technical identifiers to preserve
  - non-Latin target languages should use native Unicode/UTF-8 script
  - Latin-script slugs should be lowercase, hyphen-separated, and accent-stripped
  - source English slugs should not be returned unchanged unless genuinely identical
- Qualified the "already in target language" rule so it applies only to non-slug fields.

## Operational Notes
- This note captures the prompt-only experiment before adding deeper JSON-shape or validator changes.
- Existing rows will keep old slugs until a fresh translation job runs.
