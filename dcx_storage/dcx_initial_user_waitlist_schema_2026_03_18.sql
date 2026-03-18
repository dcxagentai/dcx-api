CREATE OR REPLACE FUNCTION stephen_dcx_set_updated_at_ts_ms()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS stephen_dcx_languages (
    id BIGSERIAL PRIMARY KEY,
    language_code TEXT NOT NULL UNIQUE,
    language_name_en TEXT NOT NULL,
    language_name_native TEXT NOT NULL,
    is_rtl BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT
);

CREATE TABLE IF NOT EXISTS stephen_dcx_users (
    id BIGSERIAL PRIMARY KEY,
    user_uuid UUID NOT NULL UNIQUE,
    primary_email TEXT NOT NULL UNIQUE,
    primary_email_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    primary_email_confirmed_at_ts_ms BIGINT,
    preferred_language_id BIGINT REFERENCES stephen_dcx_languages (id) ON DELETE SET NULL,
    account_status TEXT NOT NULL DEFAULT 'pending_email_verification',
    email_communication_preference TEXT NOT NULL DEFAULT 'announcements',
    last_seen_at_ts_ms BIGINT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT
);

CREATE TABLE IF NOT EXISTS stephen_dcx_user_auth_identities (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES stephen_dcx_users (id) ON DELETE CASCADE,
    provider_type TEXT NOT NULL,
    provider_subject TEXT NOT NULL,
    provider_email TEXT,
    provider_email_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    provider_display_name TEXT,
    provider_profile_handle TEXT,
    is_primary_identity BOOLEAN NOT NULL DEFAULT FALSE,
    is_login_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_authenticated_at_ts_ms BIGINT,
    linked_at_ts_ms BIGINT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    UNIQUE (provider_type, provider_subject)
);

CREATE TABLE IF NOT EXISTS stephen_dcx_user_auth_challenges (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES stephen_dcx_users (id) ON DELETE CASCADE,
    user_auth_identity_id BIGINT REFERENCES stephen_dcx_user_auth_identities (id) ON DELETE SET NULL,
    challenge_type TEXT NOT NULL,
    challenge_purpose TEXT NOT NULL,
    delivery_target TEXT NOT NULL,
    otp_hash TEXT NOT NULL,
    expires_at_ts_ms BIGINT NOT NULL,
    sent_at_ts_ms BIGINT,
    last_attempted_at_ts_ms BIGINT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempt_count INTEGER NOT NULL DEFAULT 5,
    resend_count INTEGER NOT NULL DEFAULT 0,
    last_resent_at_ts_ms BIGINT,
    consumed_at_ts_ms BIGINT,
    invalidated_at_ts_ms BIGINT,
    challenge_status TEXT NOT NULL DEFAULT 'pending',
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT
);

CREATE INDEX IF NOT EXISTS stephen_dcx_languages_is_default_idx
ON stephen_dcx_languages (is_default);

CREATE INDEX IF NOT EXISTS stephen_dcx_users_preferred_language_id_idx
ON stephen_dcx_users (preferred_language_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_users_account_status_idx
ON stephen_dcx_users (account_status);

CREATE INDEX IF NOT EXISTS stephen_dcx_user_auth_identities_user_id_idx
ON stephen_dcx_user_auth_identities (user_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_user_auth_identities_provider_email_idx
ON stephen_dcx_user_auth_identities (provider_email);

CREATE INDEX IF NOT EXISTS stephen_dcx_user_auth_challenges_user_id_idx
ON stephen_dcx_user_auth_challenges (user_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_user_auth_challenges_identity_id_idx
ON stephen_dcx_user_auth_challenges (user_auth_identity_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_user_auth_challenges_lookup_idx
ON stephen_dcx_user_auth_challenges (user_id, challenge_type, challenge_purpose, challenge_status);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'stephen_dcx_languages_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_languages_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_languages
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
        WHERE tgname = 'stephen_dcx_users_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_users_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_users
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
        WHERE tgname = 'stephen_dcx_user_auth_identities_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_user_auth_identities_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_user_auth_identities
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
        WHERE tgname = 'stephen_dcx_user_auth_challenges_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_user_auth_challenges_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_user_auth_challenges
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;
