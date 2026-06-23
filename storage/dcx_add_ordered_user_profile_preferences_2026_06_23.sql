-- CONTEXT:
-- Adds ordered user preference/badge tables for languages, timezones, and countries.
-- This keeps the existing preferred_* user columns for compatibility while giving the
-- app one normalized pattern for "first is primary, later rows are additional signals".
--
-- CONTRACT:
-- - Safe to rerun locally and live.
-- - Does not drop legacy stephen_dcx_users preferred_* or sidebar_clock_* columns.
-- - Backfills existing preferred language/timezone/sidebar clock values into join tables.
-- - Seeds a curated, global-enough timezone list with country flags for the MVP profile UX.

BEGIN;

ALTER TABLE public.stephen_dcx_timezones
ADD COLUMN IF NOT EXISTS country_id BIGINT REFERENCES public.stephen_dcx_countries(id);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_timezones_iana_name_key
ON public.stephen_dcx_timezones (iana_name);

CREATE TABLE IF NOT EXISTS public.stephen_dcx_user_languages (
    user_id BIGINT NOT NULL REFERENCES public.stephen_dcx_users(id) ON DELETE CASCADE,
    language_id BIGINT NOT NULL REFERENCES public.stephen_dcx_languages(id),
    sort_order INTEGER NOT NULL,
    created_at_ts_ms BIGINT NOT NULL DEFAULT ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint),
    updated_at_ts_ms BIGINT NOT NULL DEFAULT ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint),
    PRIMARY KEY (user_id, language_id),
    UNIQUE (user_id, sort_order),
    CONSTRAINT stephen_dcx_user_languages_sort_order_check CHECK (sort_order BETWEEN 1 AND 5)
);

CREATE TABLE IF NOT EXISTS public.stephen_dcx_user_timezones (
    user_id BIGINT NOT NULL REFERENCES public.stephen_dcx_users(id) ON DELETE CASCADE,
    timezone_id BIGINT NOT NULL REFERENCES public.stephen_dcx_timezones(id),
    sort_order INTEGER NOT NULL,
    created_at_ts_ms BIGINT NOT NULL DEFAULT ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint),
    updated_at_ts_ms BIGINT NOT NULL DEFAULT ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint),
    PRIMARY KEY (user_id, timezone_id),
    UNIQUE (user_id, sort_order),
    CONSTRAINT stephen_dcx_user_timezones_sort_order_check CHECK (sort_order BETWEEN 1 AND 3)
);

CREATE TABLE IF NOT EXISTS public.stephen_dcx_user_countries (
    user_id BIGINT NOT NULL REFERENCES public.stephen_dcx_users(id) ON DELETE CASCADE,
    country_id BIGINT NOT NULL REFERENCES public.stephen_dcx_countries(id),
    sort_order INTEGER NOT NULL,
    created_at_ts_ms BIGINT NOT NULL DEFAULT ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint),
    updated_at_ts_ms BIGINT NOT NULL DEFAULT ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint),
    PRIMARY KEY (user_id, country_id),
    UNIQUE (user_id, sort_order),
    CONSTRAINT stephen_dcx_user_countries_sort_order_check CHECK (sort_order BETWEEN 1 AND 25)
);

SELECT setval(
    pg_get_serial_sequence('public.stephen_dcx_timezones', 'id')::regclass,
    GREATEST((SELECT COALESCE(MAX(id), 0) + 1 FROM public.stephen_dcx_timezones), 1),
    FALSE
);

WITH timezone_seed(iana_name, display_label, region_label, country_code_alpha2, sort_order) AS (
    VALUES
        ('Europe/London', '(UTC+0/+1) London', 'Europe', 'GB', 10),
        ('Europe/Lisbon', '(UTC+0/+1) Lisbon', 'Europe', 'PT', 20),
        ('Europe/Madrid', '(UTC+1/+2) Madrid', 'Europe', 'ES', 30),
        ('Europe/Paris', '(UTC+1/+2) Paris', 'Europe', 'FR', 40),
        ('Europe/Berlin', '(UTC+1/+2) Berlin', 'Europe', 'DE', 50),
        ('Europe/Amsterdam', '(UTC+1/+2) Amsterdam', 'Europe', 'NL', 60),
        ('Europe/Zurich', '(UTC+1/+2) Zurich', 'Europe', 'CH', 70),
        ('Europe/Warsaw', '(UTC+1/+2) Warsaw', 'Europe', 'PL', 80),
        ('Europe/Istanbul', '(UTC+3) Istanbul', 'Europe / Middle East', 'TR', 90),
        ('Europe/Moscow', '(UTC+3) Moscow', 'Europe / Middle East', 'RU', 100),
        ('Asia/Dubai', '(UTC+4) Dubai', 'Middle East / West Asia', 'AE', 110),
        ('Asia/Riyadh', '(UTC+3) Riyadh', 'Middle East / West Asia', 'SA', 120),
        ('Asia/Qatar', '(UTC+3) Doha', 'Middle East / West Asia', 'QA', 130),
        ('Asia/Tehran', '(UTC+3:30) Tehran', 'Middle East / West Asia', 'IR', 140),
        ('Asia/Karachi', '(UTC+5) Karachi', 'South Asia', 'PK', 150),
        ('Asia/Kolkata', '(UTC+5:30) Mumbai', 'South Asia', 'IN', 160),
        ('Asia/Dhaka', '(UTC+6) Dhaka', 'South Asia', 'BD', 170),
        ('Asia/Almaty', '(UTC+5) Almaty', 'Central Asia', 'KZ', 180),
        ('Africa/Casablanca', '(UTC+0/+1) Casablanca', 'Africa', 'MA', 190),
        ('Africa/Cairo', '(UTC+2/+3) Cairo', 'Africa', 'EG', 200),
        ('Africa/Johannesburg', '(UTC+2) Johannesburg', 'Africa', 'ZA', 210),
        ('Africa/Lagos', '(UTC+1) Lagos', 'Africa', 'NG', 220),
        ('Africa/Nairobi', '(UTC+3) Nairobi', 'Africa', 'KE', 230),
        ('Africa/Abidjan', '(UTC+0) Abidjan', 'Africa', 'CI', 240),
        ('Africa/Accra', '(UTC+0) Accra', 'Africa', 'GH', 250),
        ('Africa/Dakar', '(UTC+0) Dakar', 'Africa', 'SN', 260),
        ('America/New_York', '(UTC-5/-4) New York', 'North America', 'US', 270),
        ('America/Chicago', '(UTC-6/-5) Chicago', 'North America', 'US', 280),
        ('America/Denver', '(UTC-7/-6) Denver', 'North America', 'US', 290),
        ('America/Los_Angeles', '(UTC-8/-7) Los Angeles', 'North America', 'US', 300),
        ('America/Toronto', '(UTC-5/-4) Toronto', 'North America', 'CA', 310),
        ('America/Mexico_City', '(UTC-6) Mexico City', 'North America', 'MX', 320),
        ('America/Panama', '(UTC-5) Panama', 'Latin America', 'PA', 330),
        ('America/Bogota', '(UTC-5) Bogota', 'Latin America', 'CO', 340),
        ('America/Lima', '(UTC-5) Lima', 'Latin America', 'PE', 350),
        ('America/Santiago', '(UTC-4/-3) Santiago', 'Latin America', 'CL', 360),
        ('America/Argentina/Buenos_Aires', '(UTC-3) Buenos Aires', 'Latin America', 'AR', 370),
        ('America/Sao_Paulo', '(UTC-3) Sao Paulo', 'Latin America', 'BR', 380),
        ('America/Caracas', '(UTC-4) Caracas', 'Latin America', 'VE', 390),
        ('America/Montevideo', '(UTC-3) Montevideo', 'Latin America', 'UY', 400),
        ('Asia/Bangkok', '(UTC+7) Bangkok', 'Asia Pacific', 'TH', 410),
        ('Asia/Jakarta', '(UTC+7) Jakarta', 'Asia Pacific', 'ID', 420),
        ('Asia/Singapore', '(UTC+8) Singapore', 'Asia Pacific', 'SG', 430),
        ('Asia/Shanghai', '(UTC+8) Shanghai', 'Asia Pacific', 'CN', 440),
        ('Asia/Hong_Kong', '(UTC+8) Hong Kong', 'Asia Pacific', 'HK', 450),
        ('Asia/Taipei', '(UTC+8) Taipei', 'Asia Pacific', 'TW', 460),
        ('Asia/Tokyo', '(UTC+9) Tokyo', 'Asia Pacific', 'JP', 470),
        ('Asia/Seoul', '(UTC+9) Seoul', 'Asia Pacific', 'KR', 480),
        ('Asia/Ho_Chi_Minh', '(UTC+7) Ho Chi Minh City', 'Asia Pacific', 'VN', 490),
        ('Asia/Manila', '(UTC+8) Manila', 'Asia Pacific', 'PH', 500),
        ('Australia/Perth', '(UTC+8) Perth', 'Asia Pacific', 'AU', 510),
        ('Australia/Sydney', '(UTC+10/+11) Sydney', 'Asia Pacific', 'AU', 520),
        ('Pacific/Auckland', '(UTC+12/+13) Auckland', 'Asia Pacific', 'NZ', 530),
        ('Pacific/Honolulu', '(UTC-10) Honolulu', 'Pacific', 'US', 540),
        ('Pacific/Fiji', '(UTC+12/+13) Fiji', 'Pacific', 'FJ', 550)
),
country_rows AS (
    SELECT id, country_code_alpha2
    FROM public.stephen_dcx_countries
)
UPDATE public.stephen_dcx_timezones AS existing_timezone
SET
    display_label = timezone_seed.display_label,
    region_label = timezone_seed.region_label,
    sort_order = timezone_seed.sort_order,
    is_active = TRUE,
    country_id = country_rows.id,
    updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
FROM timezone_seed
LEFT JOIN country_rows
  ON country_rows.country_code_alpha2 = timezone_seed.country_code_alpha2
WHERE existing_timezone.iana_name = timezone_seed.iana_name;

SELECT setval(
    pg_get_serial_sequence('public.stephen_dcx_timezones', 'id')::regclass,
    GREATEST((SELECT COALESCE(MAX(id), 0) + 1 FROM public.stephen_dcx_timezones), 1),
    FALSE
);

WITH timezone_seed(iana_name, display_label, region_label, country_code_alpha2, sort_order) AS (
    VALUES
        ('Europe/London', '(UTC+0/+1) London', 'Europe', 'GB', 10),
        ('Europe/Lisbon', '(UTC+0/+1) Lisbon', 'Europe', 'PT', 20),
        ('Europe/Madrid', '(UTC+1/+2) Madrid', 'Europe', 'ES', 30),
        ('Europe/Paris', '(UTC+1/+2) Paris', 'Europe', 'FR', 40),
        ('Europe/Berlin', '(UTC+1/+2) Berlin', 'Europe', 'DE', 50),
        ('Europe/Amsterdam', '(UTC+1/+2) Amsterdam', 'Europe', 'NL', 60),
        ('Europe/Zurich', '(UTC+1/+2) Zurich', 'Europe', 'CH', 70),
        ('Europe/Warsaw', '(UTC+1/+2) Warsaw', 'Europe', 'PL', 80),
        ('Europe/Istanbul', '(UTC+3) Istanbul', 'Europe / Middle East', 'TR', 90),
        ('Europe/Moscow', '(UTC+3) Moscow', 'Europe / Middle East', 'RU', 100),
        ('Asia/Dubai', '(UTC+4) Dubai', 'Middle East / West Asia', 'AE', 110),
        ('Asia/Riyadh', '(UTC+3) Riyadh', 'Middle East / West Asia', 'SA', 120),
        ('Asia/Qatar', '(UTC+3) Doha', 'Middle East / West Asia', 'QA', 130),
        ('Asia/Tehran', '(UTC+3:30) Tehran', 'Middle East / West Asia', 'IR', 140),
        ('Asia/Karachi', '(UTC+5) Karachi', 'South Asia', 'PK', 150),
        ('Asia/Kolkata', '(UTC+5:30) Mumbai', 'South Asia', 'IN', 160),
        ('Asia/Dhaka', '(UTC+6) Dhaka', 'South Asia', 'BD', 170),
        ('Asia/Almaty', '(UTC+5) Almaty', 'Central Asia', 'KZ', 180),
        ('Africa/Casablanca', '(UTC+0/+1) Casablanca', 'Africa', 'MA', 190),
        ('Africa/Cairo', '(UTC+2/+3) Cairo', 'Africa', 'EG', 200),
        ('Africa/Johannesburg', '(UTC+2) Johannesburg', 'Africa', 'ZA', 210),
        ('Africa/Lagos', '(UTC+1) Lagos', 'Africa', 'NG', 220),
        ('Africa/Nairobi', '(UTC+3) Nairobi', 'Africa', 'KE', 230),
        ('Africa/Abidjan', '(UTC+0) Abidjan', 'Africa', 'CI', 240),
        ('Africa/Accra', '(UTC+0) Accra', 'Africa', 'GH', 250),
        ('Africa/Dakar', '(UTC+0) Dakar', 'Africa', 'SN', 260),
        ('America/New_York', '(UTC-5/-4) New York', 'North America', 'US', 270),
        ('America/Chicago', '(UTC-6/-5) Chicago', 'North America', 'US', 280),
        ('America/Denver', '(UTC-7/-6) Denver', 'North America', 'US', 290),
        ('America/Los_Angeles', '(UTC-8/-7) Los Angeles', 'North America', 'US', 300),
        ('America/Toronto', '(UTC-5/-4) Toronto', 'North America', 'CA', 310),
        ('America/Mexico_City', '(UTC-6) Mexico City', 'North America', 'MX', 320),
        ('America/Panama', '(UTC-5) Panama', 'Latin America', 'PA', 330),
        ('America/Bogota', '(UTC-5) Bogota', 'Latin America', 'CO', 340),
        ('America/Lima', '(UTC-5) Lima', 'Latin America', 'PE', 350),
        ('America/Santiago', '(UTC-4/-3) Santiago', 'Latin America', 'CL', 360),
        ('America/Argentina/Buenos_Aires', '(UTC-3) Buenos Aires', 'Latin America', 'AR', 370),
        ('America/Sao_Paulo', '(UTC-3) Sao Paulo', 'Latin America', 'BR', 380),
        ('America/Caracas', '(UTC-4) Caracas', 'Latin America', 'VE', 390),
        ('America/Montevideo', '(UTC-3) Montevideo', 'Latin America', 'UY', 400),
        ('Asia/Bangkok', '(UTC+7) Bangkok', 'Asia Pacific', 'TH', 410),
        ('Asia/Jakarta', '(UTC+7) Jakarta', 'Asia Pacific', 'ID', 420),
        ('Asia/Singapore', '(UTC+8) Singapore', 'Asia Pacific', 'SG', 430),
        ('Asia/Shanghai', '(UTC+8) Shanghai', 'Asia Pacific', 'CN', 440),
        ('Asia/Hong_Kong', '(UTC+8) Hong Kong', 'Asia Pacific', 'HK', 450),
        ('Asia/Taipei', '(UTC+8) Taipei', 'Asia Pacific', 'TW', 460),
        ('Asia/Tokyo', '(UTC+9) Tokyo', 'Asia Pacific', 'JP', 470),
        ('Asia/Seoul', '(UTC+9) Seoul', 'Asia Pacific', 'KR', 480),
        ('Asia/Ho_Chi_Minh', '(UTC+7) Ho Chi Minh City', 'Asia Pacific', 'VN', 490),
        ('Asia/Manila', '(UTC+8) Manila', 'Asia Pacific', 'PH', 500),
        ('Australia/Perth', '(UTC+8) Perth', 'Asia Pacific', 'AU', 510),
        ('Australia/Sydney', '(UTC+10/+11) Sydney', 'Asia Pacific', 'AU', 520),
        ('Pacific/Auckland', '(UTC+12/+13) Auckland', 'Asia Pacific', 'NZ', 530),
        ('Pacific/Honolulu', '(UTC-10) Honolulu', 'Pacific', 'US', 540),
        ('Pacific/Fiji', '(UTC+12/+13) Fiji', 'Pacific', 'FJ', 550)
),
country_rows AS (
    SELECT id, country_code_alpha2
    FROM public.stephen_dcx_countries
),
missing_timezones AS (
    SELECT
        timezone_seed.iana_name,
        timezone_seed.display_label,
        timezone_seed.region_label,
        timezone_seed.sort_order,
        country_rows.id AS country_id,
        ROW_NUMBER() OVER (ORDER BY timezone_seed.sort_order ASC, timezone_seed.iana_name ASC) AS insert_rank
    FROM timezone_seed
    LEFT JOIN country_rows
      ON country_rows.country_code_alpha2 = timezone_seed.country_code_alpha2
    WHERE NOT EXISTS (
        SELECT 1
        FROM public.stephen_dcx_timezones AS existing_timezone
        WHERE existing_timezone.iana_name = timezone_seed.iana_name
    )
),
current_timezone_max_id AS (
    SELECT COALESCE(MAX(id), 0) AS max_id
    FROM public.stephen_dcx_timezones
)
INSERT INTO public.stephen_dcx_timezones (
    id,
    iana_name,
    display_label,
    region_label,
    sort_order,
    is_active,
    country_id
)
SELECT
    current_timezone_max_id.max_id + missing_timezones.insert_rank,
    missing_timezones.iana_name,
    missing_timezones.display_label,
    missing_timezones.region_label,
    missing_timezones.sort_order,
    TRUE,
    missing_timezones.country_id
FROM missing_timezones
CROSS JOIN current_timezone_max_id
ON CONFLICT (iana_name) DO NOTHING;

SELECT setval(
    pg_get_serial_sequence('public.stephen_dcx_timezones', 'id')::regclass,
    GREATEST((SELECT COALESCE(MAX(id), 0) + 1 FROM public.stephen_dcx_timezones), 1),
    FALSE
);

WITH current_user_languages AS (
    SELECT
        id AS user_id,
        preferred_language_id AS language_id,
        1 AS sort_order
    FROM public.stephen_dcx_users
    WHERE preferred_language_id IS NOT NULL
)
INSERT INTO public.stephen_dcx_user_languages (
    user_id,
    language_id,
    sort_order
)
SELECT
    user_id,
    language_id,
    sort_order
FROM current_user_languages
ON CONFLICT (user_id, language_id) DO NOTHING;

WITH current_user_timezones AS (
    SELECT id AS user_id, preferred_timezone_id AS timezone_id, 1 AS sort_order
    FROM public.stephen_dcx_users
    WHERE preferred_timezone_id IS NOT NULL
    UNION ALL
    SELECT id AS user_id, sidebar_clock_timezone_id_1 AS timezone_id, 2 AS sort_order
    FROM public.stephen_dcx_users
    WHERE sidebar_clock_timezone_id_1 IS NOT NULL
    UNION ALL
    SELECT id AS user_id, sidebar_clock_timezone_id_2 AS timezone_id, 3 AS sort_order
    FROM public.stephen_dcx_users
    WHERE sidebar_clock_timezone_id_2 IS NOT NULL
),
deduped_user_timezones AS (
    SELECT
        user_id,
        timezone_id,
        MIN(sort_order) AS sort_order
    FROM current_user_timezones
    GROUP BY user_id, timezone_id
),
ranked_user_timezones AS (
    SELECT
        user_id,
        timezone_id,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY sort_order ASC, timezone_id ASC) AS sort_order
    FROM deduped_user_timezones
)
INSERT INTO public.stephen_dcx_user_timezones (
    user_id,
    timezone_id,
    sort_order
)
SELECT
    user_id,
    timezone_id,
    sort_order
FROM ranked_user_timezones
WHERE sort_order <= 3
ON CONFLICT (user_id, timezone_id) DO NOTHING;

COMMIT;
