BEGIN;

ALTER TABLE public.stephen_dcx_user_trade_interest_materials
ADD COLUMN IF NOT EXISTS sort_order INTEGER;

WITH ranked_user_materials AS (
    SELECT
        user_id,
        material_key,
        ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY created_at_ts_ms ASC, material_key ASC
        ) AS next_sort_order
    FROM public.stephen_dcx_user_trade_interest_materials
)
UPDATE public.stephen_dcx_user_trade_interest_materials AS user_material
SET sort_order = ranked_user_materials.next_sort_order
FROM ranked_user_materials
WHERE user_material.user_id = ranked_user_materials.user_id
  AND user_material.material_key = ranked_user_materials.material_key
  AND user_material.sort_order IS NULL;

ALTER TABLE public.stephen_dcx_user_trade_interest_materials
ALTER COLUMN sort_order SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_user_trade_interest_materials_sort_order_check'
    ) THEN
        ALTER TABLE public.stephen_dcx_user_trade_interest_materials
        ADD CONSTRAINT stephen_dcx_user_trade_interest_materials_sort_order_check
        CHECK (sort_order > 0);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_user_trade_interest_materials_user_sort_order_key
ON public.stephen_dcx_user_trade_interest_materials (user_id, sort_order);

COMMIT;
