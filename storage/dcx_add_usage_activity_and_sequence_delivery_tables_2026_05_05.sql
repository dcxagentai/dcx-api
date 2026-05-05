CREATE TABLE IF NOT EXISTS stephen_dcx_llm_usage_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES stephen_dcx_users (id) ON DELETE CASCADE,
    provider_name TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    usage_source_kind TEXT NOT NULL DEFAULT '',
    usage_source_id BIGINT,
    prompt_token_count INTEGER NOT NULL DEFAULT 0,
    candidates_token_count INTEGER NOT NULL DEFAULT 0,
    total_token_count INTEGER NOT NULL DEFAULT 0,
    usage_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT
);

CREATE INDEX IF NOT EXISTS stephen_dcx_llm_usage_events_user_created_idx
ON stephen_dcx_llm_usage_events (user_id, created_at_ts_ms DESC);

CREATE INDEX IF NOT EXISTS stephen_dcx_llm_usage_events_source_idx
ON stephen_dcx_llm_usage_events (usage_source_kind, usage_source_id);

CREATE TABLE IF NOT EXISTS stephen_dcx_user_activity_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES stephen_dcx_users (id) ON DELETE CASCADE,
    actor_user_id BIGINT REFERENCES stephen_dcx_users (id) ON DELETE SET NULL,
    activity_kind TEXT NOT NULL,
    surface TEXT NOT NULL DEFAULT '',
    entity_kind TEXT NOT NULL DEFAULT '',
    entity_id BIGINT,
    event_status TEXT NOT NULL DEFAULT 'completed',
    activity_summary TEXT NOT NULL DEFAULT '',
    activity_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT
);

CREATE INDEX IF NOT EXISTS stephen_dcx_user_activity_events_user_created_idx
ON stephen_dcx_user_activity_events (user_id, created_at_ts_ms DESC);

CREATE INDEX IF NOT EXISTS stephen_dcx_user_activity_events_kind_created_idx
ON stephen_dcx_user_activity_events (activity_kind, created_at_ts_ms DESC);

CREATE TABLE IF NOT EXISTS stephen_dcx_email_sequence_enrollments (
    id BIGSERIAL PRIMARY KEY,
    sequence_id BIGINT NOT NULL REFERENCES stephen_dcx_emails_sequences (id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES stephen_dcx_users (id) ON DELETE CASCADE,
    enrollment_status TEXT NOT NULL DEFAULT 'active',
    current_step_order INTEGER NOT NULL DEFAULT 0,
    started_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    completed_at_ts_ms BIGINT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_email_sequence_enrollments_status_chk
        CHECK (enrollment_status IN ('active', 'completed', 'paused', 'cancelled', 'failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_email_sequence_enrollments_one_active_user_idx
ON stephen_dcx_email_sequence_enrollments (sequence_id, user_id)
WHERE enrollment_status = 'active';

CREATE INDEX IF NOT EXISTS stephen_dcx_email_sequence_enrollments_status_idx
ON stephen_dcx_email_sequence_enrollments (enrollment_status, sequence_id);

CREATE TABLE IF NOT EXISTS stephen_dcx_email_sequence_step_deliveries (
    id BIGSERIAL PRIMARY KEY,
    enrollment_id BIGINT NOT NULL REFERENCES stephen_dcx_email_sequence_enrollments (id) ON DELETE CASCADE,
    sequence_id BIGINT NOT NULL REFERENCES stephen_dcx_emails_sequences (id) ON DELETE CASCADE,
    sequence_step_id BIGINT NOT NULL REFERENCES stephen_dcx_emails_sequence_steps (id) ON DELETE CASCADE,
    email_send_id BIGINT REFERENCES stephen_dcx_emails_sends (id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL REFERENCES stephen_dcx_users (id) ON DELETE CASCADE,
    scheduled_send_at_ts_ms BIGINT NOT NULL,
    delivery_status TEXT NOT NULL DEFAULT 'scheduled',
    provider_message_id TEXT,
    delivery_error TEXT,
    delivery_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_email_sequence_step_deliveries_status_chk
        CHECK (delivery_status IN ('scheduled', 'sending', 'sent', 'failed', 'skipped', 'cancelled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_email_sequence_step_deliveries_one_step_idx
ON stephen_dcx_email_sequence_step_deliveries (enrollment_id, sequence_step_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_email_sequence_step_deliveries_due_idx
ON stephen_dcx_email_sequence_step_deliveries (delivery_status, scheduled_send_at_ts_ms);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'stephen_dcx_email_sequence_enrollments_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_email_sequence_enrollments_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_email_sequence_enrollments
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'stephen_dcx_email_sequence_step_deliveries_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_email_sequence_step_deliveries_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_email_sequence_step_deliveries
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;
