CONTEXT:
Added the first backend slice for the DCX admin Tracker.

WHAT CHANGED:
- Added `storage/dcx_add_admin_tracker_2026_07_04.sql`.
- Added tracker capabilities under `admin/tracker/`:
  - read catalog
  - save work item
  - create update
- Added admin routes:
  - `GET /admin/tracker/catalog`
  - `POST /admin/tracker/work-items/save`
  - `POST /admin/tracker/work-items/{work_item_id}/updates/create`
- Wired the routes into `dcx_api_app.py`.
- Centralized admin-access role logic in `read_dcx_user_role_may_access_admin`.
- Broadened admin-capable roles to include:
  - admin
  - dev
  - shareholder/shareholders
  - investor/investors

MODEL:
- `stephen_dcx_admin_tracker_work_items` stores the nested map.
- `stephen_dcx_admin_tracker_updates` stores the activity log attached to work items.
- The first version intentionally avoids owners, target dates, tags, and health fields.

VERIFICATION:
- Bundled Python compile check passed:
  - `python -m compileall admin\tracker routes\admin\dcx_api_routes_admin_tracker_catalog.py routes\admin\dcx_api_routes_admin_tracker_work_item_save.py routes\admin\dcx_api_routes_admin_tracker_update_create.py auth dcx_api_app.py`

NOTES:
- The migration was added but not applied to any database in this session.
- Tracker updates are append-only in the UI for now; work items can be edited in place.
