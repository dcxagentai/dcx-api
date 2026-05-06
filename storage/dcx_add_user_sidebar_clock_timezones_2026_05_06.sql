ALTER TABLE public.stephen_dcx_users
ADD COLUMN IF NOT EXISTS sidebar_clock_timezone_id_1 BIGINT REFERENCES public.stephen_dcx_timezones(id),
ADD COLUMN IF NOT EXISTS sidebar_clock_timezone_id_2 BIGINT REFERENCES public.stephen_dcx_timezones(id);

CREATE INDEX IF NOT EXISTS stephen_dcx_users_sidebar_clock_timezone_id_1_idx
ON public.stephen_dcx_users(sidebar_clock_timezone_id_1);

CREATE INDEX IF NOT EXISTS stephen_dcx_users_sidebar_clock_timezone_id_2_idx
ON public.stephen_dcx_users(sidebar_clock_timezone_id_2);
