CREATE TABLE IF NOT EXISTS stephen_dcx_ai_translation_jobs (
    id BIGSERIAL PRIMARY KEY,
    entity_kind TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    email_type TEXT NOT NULL DEFAULT '',
    source_language_id BIGINT NOT NULL REFERENCES stephen_dcx_languages (id) ON DELETE RESTRICT,
    target_language_id BIGINT NOT NULL REFERENCES stephen_dcx_languages (id) ON DELETE RESTRICT,
    source_row_id_snapshot BIGINT NOT NULL,
    target_row_id BIGINT,
    source_content_hash TEXT NOT NULL DEFAULT '',
    target_content_hash TEXT NOT NULL DEFAULT '',
    job_status TEXT NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    locked_at_ts_ms BIGINT,
    locked_by_worker TEXT,
    provider_name TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT '',
    prompt_version TEXT NOT NULL DEFAULT '',
    usage_event_id BIGINT REFERENCES stephen_dcx_llm_usage_events (id) ON DELETE SET NULL,
    last_error_code TEXT,
    last_error_detail TEXT,
    requested_by_user_id BIGINT REFERENCES stephen_dcx_users (id) ON DELETE SET NULL,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_ai_translation_jobs_entity_kind_chk
        CHECK (entity_kind IN ('content_page', 'content_page_category', 'email', 'newsletter')),
    CONSTRAINT stephen_dcx_ai_translation_jobs_status_chk
        CHECK (job_status IN ('queued', 'processing', 'completed', 'failed', 'cancelled', 'stale_source')),
    CONSTRAINT stephen_dcx_ai_translation_jobs_language_chk
        CHECK (source_language_id <> target_language_id)
);

CREATE INDEX IF NOT EXISTS stephen_dcx_ai_translation_jobs_claim_idx
ON stephen_dcx_ai_translation_jobs (job_status, available_at_ts_ms, id);

CREATE INDEX IF NOT EXISTS stephen_dcx_ai_translation_jobs_target_idx
ON stephen_dcx_ai_translation_jobs (entity_kind, target_row_id, created_at_ts_ms DESC);

CREATE INDEX IF NOT EXISTS stephen_dcx_ai_translation_jobs_source_idx
ON stephen_dcx_ai_translation_jobs (entity_kind, source_row_id_snapshot, created_at_ts_ms DESC);

CREATE INDEX IF NOT EXISTS stephen_dcx_ai_translation_jobs_entity_idx
ON stephen_dcx_ai_translation_jobs (entity_kind, entity_key, email_type, created_at_ts_ms DESC);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_ai_translation_jobs_one_active_uidx
ON stephen_dcx_ai_translation_jobs (entity_kind, entity_key, email_type, source_language_id, target_language_id)
WHERE job_status IN ('queued', 'processing');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'stephen_dcx_ai_translation_jobs_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_ai_translation_jobs_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_ai_translation_jobs
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;
