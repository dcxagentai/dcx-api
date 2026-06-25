BEGIN;

ALTER TABLE public.stephen_dcx_users
ADD COLUMN IF NOT EXISTS user_origin_key TEXT NOT NULL DEFAULT 'dcx_website';

ALTER TABLE public.stephen_dcx_users
ADD COLUMN IF NOT EXISTS user_origin_url TEXT NOT NULL DEFAULT '';

UPDATE public.stephen_dcx_users
SET user_origin_key = 'dcx_website'
WHERE user_origin_key IS NULL
   OR btrim(user_origin_key) = '';

UPDATE public.stephen_dcx_users
SET user_origin_url = ''
WHERE user_origin_url IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_users_user_origin_key_format_check'
    ) THEN
        ALTER TABLE public.stephen_dcx_users
        ADD CONSTRAINT stephen_dcx_users_user_origin_key_format_check
        CHECK (user_origin_key ~ '^[a-z0-9_]{2,80}$');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_users_user_origin_url_length_check'
    ) THEN
        ALTER TABLE public.stephen_dcx_users
        ADD CONSTRAINT stephen_dcx_users_user_origin_url_length_check
        CHECK (length(user_origin_url) <= 2048);
    END IF;
END $$;

COMMIT;
