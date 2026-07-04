CONTEXT:
Second backend tracker storage/API pass for multi-pillar work items.

WHAT CHANGED:
- Added migration `storage/dcx_admin_tracker_multi_pillar_2026_07_04.sql`.
- Added `pillars text[]` to `stephen_dcx_admin_tracker_work_items`.
- Backfills `pillars` from the existing single `pillar` value.
- Keeps `pillar` as the primary/backwards-compatible pillar.
- Save route now accepts both `pillar` and `pillars`.
- Save capability validates all selected pillars and writes both `pillar` and `pillars`.
- Catalog read now returns both `pillar` and `pillars`.

COMPATIBILITY:
- Stored level value remains `battle`; the admin frontend displays it as Challenge.
- Stored status value remains `active`; the admin frontend displays it as In progress.
- `current_state` remains in storage/API for compatibility, but the admin no longer shows it as a work-item paragraph.

VERIFICATION:
- Bundled Python compileall passed for tracker backend files.
