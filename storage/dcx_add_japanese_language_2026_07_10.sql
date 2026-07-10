-- CONTEXT:
-- Adds Japanese as an active DCX language for the admin/app/public translation rollout.
-- This is intentionally language-reference-only: UX string translation can follow later and
-- current surfaces should fall back to English where Japanese UX copy does not yet exist.

BEGIN;

INSERT INTO stephen_dcx_languages (
    language_code,
    language_name_en,
    language_name_native,
    is_rtl,
    is_active,
    is_default
)
VALUES (
    'ja',
    'Japanese',
    U&'\65E5\672C\8A9E',
    FALSE,
    TRUE,
    FALSE
)
ON CONFLICT (language_code) DO UPDATE
SET
    language_name_en = EXCLUDED.language_name_en,
    language_name_native = EXCLUDED.language_name_native,
    is_rtl = EXCLUDED.is_rtl,
    is_active = TRUE,
    is_default = EXCLUDED.is_default,
    updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint);

COMMIT;
