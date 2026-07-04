-- CONTEXT:
-- Second tracker storage pass. Work items can now belong to multiple functional pillars
-- while the existing single pillar column remains as the primary/backwards-compatible value.

BEGIN;

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ADD COLUMN IF NOT EXISTS pillars text[];

UPDATE public.stephen_dcx_admin_tracker_work_items
SET pillars = ARRAY[pillar]::text[]
WHERE pillars IS NULL OR cardinality(pillars) = 0;

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ALTER COLUMN pillars SET DEFAULT ARRAY['building']::text[];

ALTER TABLE public.stephen_dcx_admin_tracker_work_items
ALTER COLUMN pillars SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_admin_tracker_work_items_pillars_check'
    ) THEN
        ALTER TABLE public.stephen_dcx_admin_tracker_work_items
        ADD CONSTRAINT stephen_dcx_admin_tracker_work_items_pillars_check
        CHECK (
            cardinality(pillars) > 0
            AND pillars <@ ARRAY['legibility', 'investors', 'building', 'customers', 'other']::text[]
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS stephen_dcx_admin_tracker_work_items_pillars_gin_idx
ON public.stephen_dcx_admin_tracker_work_items
USING GIN (pillars);

COMMIT;
