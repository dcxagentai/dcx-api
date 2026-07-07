-- CONTEXT:
-- Adds explicit Team membership for the admin tracker.
-- This is operational visibility, separate from admin/dev/shareholder permissions.

BEGIN;

ALTER TABLE public.stephen_dcx_users
ADD COLUMN IF NOT EXISTS is_tracker_team_member boolean NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS stephen_dcx_users_tracker_team_member_idx
ON public.stephen_dcx_users(is_tracker_team_member, updated_at_ts_ms DESC, id DESC);

COMMIT;
