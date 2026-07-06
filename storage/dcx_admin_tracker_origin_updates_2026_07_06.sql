-- CONTEXT:
-- Lets structured tracker work items remember the activity update they were created from.

BEGIN;

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ADD COLUMN IF NOT EXISTS origin_update_id bigint REFERENCES public.stephen_dcx_admin_tracker_updates(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS stephen_dcx_admin_tracker_work_items_origin_update_idx
ON public.stephen_dcx_admin_tracker_work_items(origin_update_id, id);

COMMIT;
