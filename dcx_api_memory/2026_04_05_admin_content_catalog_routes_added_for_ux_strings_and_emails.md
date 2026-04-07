The first read-only admin content catalog routes are now in place for both UX strings and emails.

Files added:
- `routes/admin/dcx_api_routes_admin_support.py`
- `admin/content/ux_strings/read_dcx_admin_live_ux_strings_catalog.py`
- `admin/content/ux_strings/read_dcx_admin_live_ux_strings_catalog_test.py`
- `admin/content/emails/read_dcx_admin_live_emails_catalog.py`
- `admin/content/emails/read_dcx_admin_live_emails_catalog_test.py`
- `routes/admin/dcx_api_routes_admin_content_ux_strings_catalog.py`
- `routes/admin/dcx_api_routes_admin_content_emails_catalog.py`

Files updated:
- `routes/admin/dcx_api_routes_admin_users_list.py`
- `dcx_api_app.py`
- `dcx_api_app_test.py`

What this backend slice does:
- Adds `GET /admin/content/ux-strings/catalog`
- Adds `GET /admin/content/emails/catalog`
- Keeps both routes read-only and live-row-only
- Returns canonical wrappers shaped for the admin frontend to derive its own dropdown combinations locally
- Reuses one shared temporary local admin debug-identity helper so the same pre-auth behavior applies consistently across admin routes

Route behavior:
- all admin routes still accept temporary `?admin_user_id=<id>` only in `local` or `development`
- without that local debug id:
  - `401`
  - `API_DCX_ADMIN_AUTH_REQUIRED`
- outside local/development, the debug id path is rejected with:
  - `400`
  - `API_DCX_ADMIN_DEBUG_USER_ID_FORBIDDEN`

Catalog payload shape:
- UX strings catalog returns:
  - `ux_strings`
  - `total_live_row_count`
- each UX row includes:
  - stable ids
  - group/key
  - text
  - original/live flags
  - version/translation linkage ids
  - nested language object

- Emails catalog returns:
  - `emails`
  - `total_live_row_count`
- each email row includes:
  - stable ids
  - type/key
  - subject/body
  - original/live flags
  - version/translation linkage ids
  - nested language object

Why this shape was chosen:
- the datasets are still small enough to ship as one read-only live catalog per content type
- the frontend can keep dropdown state local without extra round-trips or URL state
- the same underlying schema model already handles originals, translations, and future versioning, so the read UI is mostly projection work now

Verification:
- focused backend result: `25 passed`
- includes:
  - users list capability tests
  - UX-strings catalog capability tests
  - emails catalog capability tests
  - app assembly / route tests

Next most natural backend step:
- keep these read routes stable
- add admin edit routes for UX strings and emails only after auth and role enforcement are ready
