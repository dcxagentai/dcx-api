ALTER TABLE public.stephen_dcx_users
ADD COLUMN IF NOT EXISTS public_display_name text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS public_handle text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS public_identity_mode text NOT NULL DEFAULT 'display_name';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_users_public_identity_mode_check'
    ) THEN
        ALTER TABLE public.stephen_dcx_users
        ADD CONSTRAINT stephen_dcx_users_public_identity_mode_check
        CHECK (public_identity_mode IN ('display_name', 'handle', 'anonymous'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_users_public_handle_lower_key
ON public.stephen_dcx_users ((lower(public_handle)))
WHERE public_handle <> '';
