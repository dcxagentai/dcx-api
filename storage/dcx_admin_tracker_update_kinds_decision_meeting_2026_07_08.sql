-- Allow the tracker activity log to distinguish decisions, concepts, and meetings.

ALTER TABLE public.stephen_dcx_admin_tracker_updates
DROP CONSTRAINT IF EXISTS stephen_dcx_admin_tracker_updates_kind_check;

ALTER TABLE public.stephen_dcx_admin_tracker_updates
ADD CONSTRAINT stephen_dcx_admin_tracker_updates_kind_check
CHECK (
    update_kind IN (
        'note',
        'progress',
        'blocker',
        'decision',
        'question',
        'action',
        'concept',
        'meeting'
    )
);
