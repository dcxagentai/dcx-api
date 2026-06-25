-- CONTEXT:
-- Extends the first DCX Network slice so public feed posts can carry one private
-- app-visible image or audio attachment. The Contacts directory uses existing
-- user/profile/follow tables and does not need its own table.

BEGIN;

ALTER TABLE public.stephen_dcx_network_feed_posts
ADD COLUMN IF NOT EXISTS attachment_file_object_id bigint REFERENCES public.stephen_dcx_file_objects(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS attachment_kind text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS attachment_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_network_feed_posts_attachment_kind_check'
    ) THEN
        ALTER TABLE public.stephen_dcx_network_feed_posts
        ADD CONSTRAINT stephen_dcx_network_feed_posts_attachment_kind_check
        CHECK (attachment_kind IN ('', 'image', 'audio'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_network_feed_posts_attachment_consistency_check'
    ) THEN
        ALTER TABLE public.stephen_dcx_network_feed_posts
        ADD CONSTRAINT stephen_dcx_network_feed_posts_attachment_consistency_check
        CHECK (
            (attachment_file_object_id IS NULL AND attachment_kind = '')
            OR
            (attachment_file_object_id IS NOT NULL AND attachment_kind IN ('image', 'audio'))
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS stephen_dcx_network_feed_posts_attachment_file_object_idx
ON public.stephen_dcx_network_feed_posts(attachment_file_object_id)
WHERE attachment_file_object_id IS NOT NULL;

COMMIT;
