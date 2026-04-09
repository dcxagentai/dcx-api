Translated content pages were failing to autosave because the page save capability still required a same-language live category row, while the CMS currently only seeds the English category row. Detail reads had already been given an original-category fallback, but saves and publishes had not.

Fix applied:
- `save_dcx_admin_live_content_page_row_version.py`
  - category validation now accepts either:
    - a same-language live category row, or
    - the live original category row
  - this matches the actual MVP content model where page translations can exist before category translations do
- `create_dcx_admin_content_page_translation.py`
  - new translated page rows now start as:
    - `publication_status = 'draft'`
    - `published_at_ts_ms = null`
  - instead of inheriting the source row's published state

Tests added/updated:
- `create_dcx_admin_content_page_translation_test.py`
  - now asserts translated pages are created as draft rows with no published timestamp
- `save_dcx_admin_live_content_page_row_version_test.py`
  - verifies translated pages can save successfully when only the original category row exists

Verification run:
- `admin/content/pages/create_dcx_admin_content_page_translation_test.py`
- `admin/content/pages/save_dcx_admin_live_content_page_row_version_test.py`
- `dcx_api_app_test.py`

All passed after the fix.
