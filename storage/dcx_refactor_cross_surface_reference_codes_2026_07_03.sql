BEGIN;

UPDATE public.stephen_dcx_trade_threads
SET
    thread_reference_code = 'TC' || id::text,
    updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
WHERE thread_reference_code IS DISTINCT FROM ('TC' || id::text);

ALTER TABLE public.stephen_dcx_outbound_interaction_routes
ADD COLUMN IF NOT EXISTS updated_at_ts_ms bigint;

UPDATE public.stephen_dcx_outbound_interaction_routes
SET updated_at_ts_ms = COALESCE(
    updated_at_ts_ms,
    created_at_ts_ms,
    ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
)
WHERE updated_at_ts_ms IS NULL;

ALTER TABLE public.stephen_dcx_outbound_interaction_routes
ALTER COLUMN updated_at_ts_ms SET DEFAULT ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint);

ALTER TABLE public.stephen_dcx_outbound_interaction_routes
ALTER COLUMN updated_at_ts_ms SET NOT NULL;

UPDATE public.stephen_dcx_outbound_interaction_routes
SET
    route_reference_code = 'TC' || substring(route_reference_code from 2),
    updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
WHERE route_reference_code ~ '^C[0-9]+$';

ALTER TABLE public.stephen_dcx_network_dm_threads
ADD COLUMN IF NOT EXISTS thread_reference_code text;

UPDATE public.stephen_dcx_network_dm_threads
SET
    thread_reference_code = 'DM' || id::text,
    updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
WHERE thread_reference_code IS NULL
   OR btrim(thread_reference_code) = ''
   OR thread_reference_code IS DISTINCT FROM ('DM' || id::text);

ALTER TABLE public.stephen_dcx_network_dm_threads
ALTER COLUMN thread_reference_code SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_network_dm_threads_reference_code_key
ON public.stephen_dcx_network_dm_threads(lower(thread_reference_code));

ALTER TABLE public.stephen_dcx_network_feed_posts
ADD COLUMN IF NOT EXISTS public_reference_code text;

UPDATE public.stephen_dcx_network_feed_posts
SET
    public_reference_code = 'P' || id::text,
    updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
WHERE public_reference_code IS NULL
   OR btrim(public_reference_code) = ''
   OR public_reference_code IS DISTINCT FROM ('P' || id::text);

ALTER TABLE public.stephen_dcx_network_feed_posts
ALTER COLUMN public_reference_code SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_network_feed_posts_reference_code_key
ON public.stephen_dcx_network_feed_posts(lower(public_reference_code));

COMMIT;
