The admin multilingual CMS pattern is now backed by real create-translation routes for transactional emails and UX strings, not just pages, categories, and newsletters.

Backend changes:
- Added `admin/content/emails/create_dcx_admin_email_translation.py` plus a focused test file. This creates the first live translation row for an existing transactional email, copies the source subject/body, preserves the immutable version/translation model, and uses an advisory lock keyed by email identity + target language to serialize competing create attempts.
- Added `admin/content/ux_strings/create_dcx_admin_ux_string_translation.py` plus a focused test file. This does the same for UX strings, cloning the source text into a first target-language row and linking it back to the original through `translation_of_id`.
- Added route boundaries:
  - `routes/admin/dcx_api_routes_admin_content_email_create_translation.py`
  - `routes/admin/dcx_api_routes_admin_content_ux_string_create_translation.py`
- Registered both new routers in `dcx_api_app.py`.

Why this matters:
- The admin frontend now has a real backend path for "create missing language row" on transactional emails and UX strings, which brings them into parity with the page/category/newsletter editor experience.
- This keeps the multilingual editing story consistent across the CMS instead of having some entities be switch-only and others be fully translation-aware.

Checks:
- `python -m py_compile` passed for the touched API files.
