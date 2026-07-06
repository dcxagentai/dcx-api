-- CONTEXT:
-- Adds soft archive support for tracker work items.

BEGIN;

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ADD COLUMN IF NOT EXISTS is_archived boolean NOT NULL DEFAULT FALSE;

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ADD COLUMN IF NOT EXISTS archived_by_user_id bigint REFERENCES public.stephen_dcx_users(id) ON DELETE SET NULL;

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ADD COLUMN IF NOT EXISTS archived_at_ts_ms bigint;

CREATE INDEX IF NOT EXISTS stephen_dcx_admin_tracker_work_items_archive_idx
ON public.stephen_dcx_admin_tracker_work_items(is_archived, updated_at_ts_ms DESC, id DESC);

COMMIT;
