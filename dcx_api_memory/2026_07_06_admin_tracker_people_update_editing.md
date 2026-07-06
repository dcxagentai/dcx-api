# Admin tracker people and update editing

Added tracker backend support on 2026-07-06:

- New migration: `storage/dcx_admin_tracker_people_and_update_editing_2026_07_06.sql`.
- Work items now support optional `assigned_to_user_id`.
- Activity updates now support `updated_by_user_id`; existing update rows are backfilled from `author_user_id`.
- Catalog reads include assignee/editor primary emails and an `assignable_users` list for the admin UI.
- Work-item save accepts `assigned_to_user_id`.
- New update-save capability and route: `POST /admin/tracker/updates/save`, preserving the original author while recording the latest editor.
- New migration: `storage/dcx_admin_tracker_origin_updates_2026_07_06.sql`.
- Work items now support nullable `origin_update_id`, so a structured item can record the activity update that generated it.
- New migration: `storage/dcx_admin_tracker_archive_2026_07_06.sql`.
- Work items now support soft archive metadata through `is_archived`, `archived_by_user_id`, and `archived_at_ts_ms`.
- New archive/restore route: `POST /admin/tracker/work-items/archive`.

Fresh installs also include the new columns in `storage/dcx_add_admin_tracker_2026_07_04.sql`.
