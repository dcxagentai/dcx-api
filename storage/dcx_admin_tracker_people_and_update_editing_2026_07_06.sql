-- CONTEXT:
-- Adds lightweight accountability to the admin tracker:
-- optional item assignees and editor tracking for activity updates.

BEGIN;

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ADD COLUMN IF NOT EXISTS assigned_to_user_id bigint REFERENCES public.stephen_dcx_users(id) ON DELETE SET NULL;

ALTER TABLE public.stephen_dcx_admin_tracker_updates
ADD COLUMN IF NOT EXISTS updated_by_user_id bigint REFERENCES public.stephen_dcx_users(id) ON DELETE SET NULL;

UPDATE public.stephen_dcx_admin_tracker_updates
SET updated_by_user_id = author_user_id
WHERE updated_by_user_id IS NULL;

CREATE INDEX IF NOT EXISTS stephen_dcx_admin_tracker_work_items_assigned_to_idx
ON public.stephen_dcx_admin_tracker_work_items(assigned_to_user_id, item_status, updated_at_ts_ms DESC, id DESC);

CREATE INDEX IF NOT EXISTS stephen_dcx_admin_tracker_updates_updated_by_idx
ON public.stephen_dcx_admin_tracker_updates(updated_by_user_id, updated_at_ts_ms DESC, id DESC);

COMMIT;
