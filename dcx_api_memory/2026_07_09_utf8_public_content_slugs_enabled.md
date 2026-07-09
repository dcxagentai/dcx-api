# UTF-8 Public Content Slugs Enabled

## Summary
- Updated `build_dcx_slugified_text_identifier` so DCX content slugs preserve Unicode letters, marks, and numbers instead of collapsing non-ASCII scripts to `item`.
- Added AI translation of `page_slug` and `category_slug` fields by including them in the structured translation source payload.
- Updated the Gemini admin translation prompt to ask for native-language URL path segments for slug fields.
- Changed AI translation storage so translated page/category rows store normalized UTF-8 slugs, with automatic `-2`, `-3`, etc. suffixes when another live row already uses the same slug scope.
- Added original page slug to the admin AI translation source hash, so slug changes make existing translations stale and force a fresh translation job.

## Verification
- `.\.venv\Scripts\python.exe -m pytest content\shared\build_dcx_slugified_text_identifier_test.py admin\translations\store_dcx_admin_ai_translation_result_test.py admin\content\pages\read_dcx_admin_live_content_page_detail_test.py admin\content\pages\publish_dcx_admin_content_page_translated_drafts_test.py admin\translations\process_due_dcx_admin_ai_translation_jobs_test.py`
- Result: 11 passed.

## Operational Notes
- Existing translated pages with English slugs will not magically change until they are retranslated or manually edited.
- Old queued translation jobs whose source hash was generated before slug fields were included can become `stale_source`; pressing Translate again creates fresh jobs with the new slug-aware hash.
- Internal `page_key`/`category_key` identities remain stable identifiers; public URL slugs can now be native UTF-8 text per language.
