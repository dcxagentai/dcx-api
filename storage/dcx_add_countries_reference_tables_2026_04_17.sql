CREATE TABLE IF NOT EXISTS stephen_dcx_countries (
    id BIGSERIAL PRIMARY KEY,
    country_code_alpha2 TEXT NOT NULL UNIQUE,
    default_display_name TEXT NOT NULL,
    flag_asset_key TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 1000,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(epoch FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(epoch FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_countries_country_code_alpha2_format_chk
        CHECK (country_code_alpha2 ~ '^[A-Z]{2}$'),
    CONSTRAINT stephen_dcx_countries_flag_asset_key_format_chk
        CHECK (flag_asset_key ~ '^[a-z0-9_-]+$')
);

CREATE TABLE IF NOT EXISTS stephen_dcx_country_calling_codes (
    id BIGSERIAL PRIMARY KEY,
    country_id BIGINT NOT NULL REFERENCES stephen_dcx_countries(id) ON DELETE CASCADE,
    calling_code TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 1000,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(epoch FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(epoch FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_country_calling_codes_calling_code_format_chk
        CHECK (calling_code ~ '^\+[1-9][0-9]{0,3}$'),
    CONSTRAINT stephen_dcx_country_calling_codes_country_id_calling_code_key
        UNIQUE (country_id, calling_code)
);

CREATE INDEX IF NOT EXISTS stephen_dcx_countries_is_active_sort_order_idx
ON stephen_dcx_countries (is_active, sort_order, default_display_name);

CREATE INDEX IF NOT EXISTS stephen_dcx_country_calling_codes_country_id_active_idx
ON stephen_dcx_country_calling_codes (country_id, is_active, sort_order);

CREATE INDEX IF NOT EXISTS stephen_dcx_country_calling_codes_calling_code_idx
ON stephen_dcx_country_calling_codes (calling_code);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_country_calling_codes_one_primary_per_country_uidx
ON stephen_dcx_country_calling_codes (country_id)
WHERE is_primary = TRUE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'stephen_dcx_countries_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_countries_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_countries
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'stephen_dcx_country_calling_codes_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_country_calling_codes_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_country_calling_codes
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;

WITH country_seed(country_code_alpha2, default_display_name, flag_asset_key, sort_order) AS (
    VALUES
        ('ES', 'Spain', 'es', 10),
        ('GB', 'United Kingdom', 'gb', 20),
        ('FR', 'France', 'fr', 30),
        ('DE', 'Germany', 'de', 40),
        ('IT', 'Italy', 'it', 50),
        ('PT', 'Portugal', 'pt', 60),
        ('NL', 'Netherlands', 'nl', 70),
        ('BE', 'Belgium', 'be', 80),
        ('CH', 'Switzerland', 'ch', 90),
        ('AT', 'Austria', 'at', 100),
        ('IE', 'Ireland', 'ie', 110),
        ('DK', 'Denmark', 'dk', 120),
        ('SE', 'Sweden', 'se', 130),
        ('NO', 'Norway', 'no', 140),
        ('FI', 'Finland', 'fi', 150),
        ('PL', 'Poland', 'pl', 160),
        ('CZ', 'Czechia', 'cz', 170),
        ('SK', 'Slovakia', 'sk', 180),
        ('HU', 'Hungary', 'hu', 190),
        ('RO', 'Romania', 'ro', 200),
        ('BG', 'Bulgaria', 'bg', 210),
        ('GR', 'Greece', 'gr', 220),
        ('TR', 'Turkey', 'tr', 230),
        ('UA', 'Ukraine', 'ua', 240),
        ('US', 'United States', 'us', 250),
        ('CA', 'Canada', 'ca', 260),
        ('MX', 'Mexico', 'mx', 270),
        ('BR', 'Brazil', 'br', 280),
        ('AR', 'Argentina', 'ar', 290),
        ('CL', 'Chile', 'cl', 300),
        ('CO', 'Colombia', 'co', 310),
        ('PE', 'Peru', 'pe', 320),
        ('UY', 'Uruguay', 'uy', 330),
        ('PY', 'Paraguay', 'py', 340),
        ('BO', 'Bolivia', 'bo', 350),
        ('EC', 'Ecuador', 'ec', 360),
        ('VE', 'Venezuela', 've', 370),
        ('MA', 'Morocco', 'ma', 380),
        ('DZ', 'Algeria', 'dz', 390),
        ('TN', 'Tunisia', 'tn', 400),
        ('EG', 'Egypt', 'eg', 410),
        ('ZA', 'South Africa', 'za', 420),
        ('NG', 'Nigeria', 'ng', 430),
        ('GH', 'Ghana', 'gh', 440),
        ('KE', 'Kenya', 'ke', 450),
        ('TZ', 'Tanzania', 'tz', 460),
        ('ET', 'Ethiopia', 'et', 470),
        ('AE', 'United Arab Emirates', 'ae', 480),
        ('SA', 'Saudi Arabia', 'sa', 490),
        ('QA', 'Qatar', 'qa', 500),
        ('KW', 'Kuwait', 'kw', 510),
        ('BH', 'Bahrain', 'bh', 520),
        ('OM', 'Oman', 'om', 530),
        ('IL', 'Israel', 'il', 540),
        ('JO', 'Jordan', 'jo', 550),
        ('LB', 'Lebanon', 'lb', 560),
        ('IN', 'India', 'in', 570),
        ('PK', 'Pakistan', 'pk', 580),
        ('BD', 'Bangladesh', 'bd', 590),
        ('LK', 'Sri Lanka', 'lk', 600),
        ('NP', 'Nepal', 'np', 610),
        ('CN', 'China', 'cn', 620),
        ('HK', 'Hong Kong', 'hk', 630),
        ('TW', 'Taiwan', 'tw', 640),
        ('JP', 'Japan', 'jp', 650),
        ('KR', 'South Korea', 'kr', 660),
        ('SG', 'Singapore', 'sg', 670),
        ('MY', 'Malaysia', 'my', 680),
        ('TH', 'Thailand', 'th', 690),
        ('VN', 'Vietnam', 'vn', 700),
        ('ID', 'Indonesia', 'id', 710),
        ('PH', 'Philippines', 'ph', 720),
        ('AU', 'Australia', 'au', 730),
        ('NZ', 'New Zealand', 'nz', 740)
)
INSERT INTO stephen_dcx_countries (
    country_code_alpha2,
    default_display_name,
    flag_asset_key,
    sort_order
)
SELECT
    country_seed.country_code_alpha2,
    country_seed.default_display_name,
    country_seed.flag_asset_key,
    country_seed.sort_order
FROM country_seed
ON CONFLICT (country_code_alpha2) DO UPDATE
SET
    default_display_name = EXCLUDED.default_display_name,
    flag_asset_key = EXCLUDED.flag_asset_key,
    sort_order = EXCLUDED.sort_order,
    is_active = TRUE;

WITH calling_code_seed(country_code_alpha2, calling_code, is_primary, sort_order) AS (
    VALUES
        ('ES', '+34', TRUE, 10),
        ('GB', '+44', TRUE, 10),
        ('FR', '+33', TRUE, 10),
        ('DE', '+49', TRUE, 10),
        ('IT', '+39', TRUE, 10),
        ('PT', '+351', TRUE, 10),
        ('NL', '+31', TRUE, 10),
        ('BE', '+32', TRUE, 10),
        ('CH', '+41', TRUE, 10),
        ('AT', '+43', TRUE, 10),
        ('IE', '+353', TRUE, 10),
        ('DK', '+45', TRUE, 10),
        ('SE', '+46', TRUE, 10),
        ('NO', '+47', TRUE, 10),
        ('FI', '+358', TRUE, 10),
        ('PL', '+48', TRUE, 10),
        ('CZ', '+420', TRUE, 10),
        ('SK', '+421', TRUE, 10),
        ('HU', '+36', TRUE, 10),
        ('RO', '+40', TRUE, 10),
        ('BG', '+359', TRUE, 10),
        ('GR', '+30', TRUE, 10),
        ('TR', '+90', TRUE, 10),
        ('UA', '+380', TRUE, 10),
        ('US', '+1', TRUE, 10),
        ('CA', '+1', TRUE, 10),
        ('MX', '+52', TRUE, 10),
        ('BR', '+55', TRUE, 10),
        ('AR', '+54', TRUE, 10),
        ('CL', '+56', TRUE, 10),
        ('CO', '+57', TRUE, 10),
        ('PE', '+51', TRUE, 10),
        ('UY', '+598', TRUE, 10),
        ('PY', '+595', TRUE, 10),
        ('BO', '+591', TRUE, 10),
        ('EC', '+593', TRUE, 10),
        ('VE', '+58', TRUE, 10),
        ('MA', '+212', TRUE, 10),
        ('DZ', '+213', TRUE, 10),
        ('TN', '+216', TRUE, 10),
        ('EG', '+20', TRUE, 10),
        ('ZA', '+27', TRUE, 10),
        ('NG', '+234', TRUE, 10),
        ('GH', '+233', TRUE, 10),
        ('KE', '+254', TRUE, 10),
        ('TZ', '+255', TRUE, 10),
        ('ET', '+251', TRUE, 10),
        ('AE', '+971', TRUE, 10),
        ('SA', '+966', TRUE, 10),
        ('QA', '+974', TRUE, 10),
        ('KW', '+965', TRUE, 10),
        ('BH', '+973', TRUE, 10),
        ('OM', '+968', TRUE, 10),
        ('IL', '+972', TRUE, 10),
        ('JO', '+962', TRUE, 10),
        ('LB', '+961', TRUE, 10),
        ('IN', '+91', TRUE, 10),
        ('PK', '+92', TRUE, 10),
        ('BD', '+880', TRUE, 10),
        ('LK', '+94', TRUE, 10),
        ('NP', '+977', TRUE, 10),
        ('CN', '+86', TRUE, 10),
        ('HK', '+852', TRUE, 10),
        ('TW', '+886', TRUE, 10),
        ('JP', '+81', TRUE, 10),
        ('KR', '+82', TRUE, 10),
        ('SG', '+65', TRUE, 10),
        ('MY', '+60', TRUE, 10),
        ('TH', '+66', TRUE, 10),
        ('VN', '+84', TRUE, 10),
        ('ID', '+62', TRUE, 10),
        ('PH', '+63', TRUE, 10),
        ('AU', '+61', TRUE, 10),
        ('NZ', '+64', TRUE, 10)
)
INSERT INTO stephen_dcx_country_calling_codes (
    country_id,
    calling_code,
    is_primary,
    sort_order
)
SELECT
    country.id,
    calling_code_seed.calling_code,
    calling_code_seed.is_primary,
    calling_code_seed.sort_order
FROM calling_code_seed
INNER JOIN stephen_dcx_countries AS country
  ON country.country_code_alpha2 = calling_code_seed.country_code_alpha2
ON CONFLICT (country_id, calling_code) DO UPDATE
SET
    is_primary = EXCLUDED.is_primary,
    sort_order = EXCLUDED.sort_order,
    is_active = TRUE;
