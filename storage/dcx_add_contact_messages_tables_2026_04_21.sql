CREATE SEQUENCE IF NOT EXISTS stephen_dcx_contact_message_provider_events_id_seq;
CREATE SEQUENCE IF NOT EXISTS stephen_dcx_contact_messages_id_seq;
CREATE SEQUENCE IF NOT EXISTS stephen_dcx_file_objects_id_seq;
CREATE SEQUENCE IF NOT EXISTS stephen_dcx_contact_message_attachments_id_seq;
CREATE SEQUENCE IF NOT EXISTS stephen_dcx_contact_message_processing_jobs_id_seq;
CREATE SEQUENCE IF NOT EXISTS stephen_dcx_contact_message_analysis_runs_id_seq;

CREATE TABLE IF NOT EXISTS stephen_dcx_contact_message_provider_events (
    id BIGINT NOT NULL DEFAULT nextval('stephen_dcx_contact_message_provider_events_id_seq'::regclass),
    user_id BIGINT REFERENCES stephen_dcx_users (id) ON DELETE SET NULL,
    contact_method_id BIGINT REFERENCES stephen_dcx_users_contact_methods (id) ON DELETE SET NULL,
    provider_type TEXT NOT NULL,
    channel_type TEXT NOT NULL,
    provider_event_type TEXT NOT NULL DEFAULT '',
    provider_event_id TEXT,
    provider_message_id TEXT,
    provider_sender_handle TEXT,
    provider_recipient_handle TEXT,
    event_direction TEXT NOT NULL DEFAULT 'inbound',
    payload_hash TEXT,
    raw_event_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    signature_verified BOOLEAN NOT NULL DEFAULT FALSE,
    processing_status TEXT NOT NULL DEFAULT 'received',
    event_received_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    event_processed_at_ts_ms BIGINT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_contact_message_provider_events_pkey PRIMARY KEY (id),
    CONSTRAINT stephen_dcx_contact_message_provider_events_provider_type_chk
        CHECK (provider_type IN ('meta_whatsapp', 'resend_inbound', 'dcx_app')),
    CONSTRAINT stephen_dcx_contact_message_provider_events_channel_type_chk
        CHECK (channel_type IN ('whatsapp', 'email', 'app')),
    CONSTRAINT stephen_dcx_contact_message_provider_events_direction_chk
        CHECK (event_direction IN ('inbound', 'outbound')),
    CONSTRAINT stephen_dcx_contact_message_provider_events_processing_status_chk
        CHECK (processing_status IN ('received', 'processing', 'processed', 'ignored', 'failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_contact_message_provider_events_provider_event_uidx
ON stephen_dcx_contact_message_provider_events (provider_type, provider_event_id)
WHERE provider_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_provider_events_provider_message_id_idx
ON stephen_dcx_contact_message_provider_events (provider_type, provider_message_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_provider_events_payload_hash_idx
ON stephen_dcx_contact_message_provider_events (payload_hash)
WHERE payload_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_provider_events_user_id_idx
ON stephen_dcx_contact_message_provider_events (user_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_provider_events_contact_method_id_idx
ON stephen_dcx_contact_message_provider_events (contact_method_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_provider_events_received_status_idx
ON stephen_dcx_contact_message_provider_events (event_received_at_ts_ms, processing_status);

CREATE TABLE IF NOT EXISTS stephen_dcx_contact_messages (
    id BIGINT NOT NULL DEFAULT nextval('stephen_dcx_contact_messages_id_seq'::regclass),
    user_id BIGINT REFERENCES stephen_dcx_users (id) ON DELETE SET NULL,
    contact_method_id BIGINT REFERENCES stephen_dcx_users_contact_methods (id) ON DELETE SET NULL,
    provider_event_id BIGINT REFERENCES stephen_dcx_contact_message_provider_events (id) ON DELETE SET NULL,
    channel_type TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    message_direction TEXT NOT NULL,
    message_format TEXT NOT NULL,
    external_message_id TEXT,
    source_handle_normalized TEXT,
    target_handle_normalized TEXT,
    message_subject TEXT NOT NULL DEFAULT '',
    raw_text_content TEXT NOT NULL DEFAULT '',
    derived_text_content TEXT NOT NULL DEFAULT '',
    analysis_summary_text TEXT NOT NULL DEFAULT '',
    message_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_language_id BIGINT REFERENCES stephen_dcx_languages (id) ON DELETE SET NULL,
    processing_status TEXT NOT NULL DEFAULT 'received',
    derivation_status TEXT NOT NULL DEFAULT 'not_required',
    visible_to_user BOOLEAN NOT NULL DEFAULT TRUE,
    in_reply_to_message_id BIGINT REFERENCES stephen_dcx_contact_messages (id) ON DELETE SET NULL,
    received_at_ts_ms BIGINT,
    sent_at_ts_ms BIGINT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_contact_messages_pkey PRIMARY KEY (id),
    CONSTRAINT stephen_dcx_contact_messages_channel_type_chk
        CHECK (channel_type IN ('whatsapp', 'email', 'app')),
    CONSTRAINT stephen_dcx_contact_messages_provider_type_chk
        CHECK (provider_type IN ('meta_whatsapp', 'resend_inbound', 'dcx_app')),
    CONSTRAINT stephen_dcx_contact_messages_direction_chk
        CHECK (message_direction IN ('inbound', 'outbound')),
    CONSTRAINT stephen_dcx_contact_messages_format_chk
        CHECK (message_format IN ('text', 'image', 'audio', 'document', 'mixed', 'system')),
    CONSTRAINT stephen_dcx_contact_messages_processing_status_chk
        CHECK (processing_status IN ('received', 'queued', 'processing', 'ready', 'failed')),
    CONSTRAINT stephen_dcx_contact_messages_derivation_status_chk
        CHECK (derivation_status IN ('not_required', 'pending', 'completed', 'failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_contact_messages_external_message_uidx
ON stephen_dcx_contact_messages (provider_type, external_message_id, message_direction)
WHERE external_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_messages_user_id_idx
ON stephen_dcx_contact_messages (user_id, created_at_ts_ms);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_messages_contact_method_id_idx
ON stephen_dcx_contact_messages (contact_method_id, created_at_ts_ms);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_messages_provider_event_id_idx
ON stephen_dcx_contact_messages (provider_event_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_messages_channel_status_idx
ON stephen_dcx_contact_messages (channel_type, processing_status, created_at_ts_ms);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_messages_visible_to_user_idx
ON stephen_dcx_contact_messages (visible_to_user, created_at_ts_ms);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_messages_detected_language_id_idx
ON stephen_dcx_contact_messages (detected_language_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_messages_in_reply_to_idx
ON stephen_dcx_contact_messages (in_reply_to_message_id);

CREATE TABLE IF NOT EXISTS stephen_dcx_file_objects (
    id BIGINT NOT NULL DEFAULT nextval('stephen_dcx_file_objects_id_seq'::regclass),
    file_uuid UUID,
    owner_user_id BIGINT REFERENCES stephen_dcx_users (id) ON DELETE SET NULL,
    storage_provider TEXT NOT NULL DEFAULT 'cloudflare_r2',
    bucket_alias TEXT NOT NULL,
    object_key TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    file_size_bytes BIGINT,
    original_filename TEXT NOT NULL DEFAULT '',
    file_kind TEXT NOT NULL,
    source_channel_type TEXT NOT NULL,
    source_provider_type TEXT NOT NULL,
    file_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_private BOOLEAN NOT NULL DEFAULT TRUE,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_file_objects_pkey PRIMARY KEY (id),
    CONSTRAINT stephen_dcx_file_objects_file_uuid_key UNIQUE (file_uuid),
    CONSTRAINT stephen_dcx_file_objects_storage_provider_chk
        CHECK (storage_provider IN ('cloudflare_r2')),
    CONSTRAINT stephen_dcx_file_objects_file_kind_chk
        CHECK (file_kind IN ('image', 'audio', 'document', 'other')),
    CONSTRAINT stephen_dcx_file_objects_source_channel_type_chk
        CHECK (source_channel_type IN ('whatsapp', 'email', 'app')),
    CONSTRAINT stephen_dcx_file_objects_source_provider_type_chk
        CHECK (source_provider_type IN ('meta_whatsapp', 'resend_inbound', 'dcx_app'))
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_file_objects_storage_object_uidx
ON stephen_dcx_file_objects (storage_provider, bucket_alias, object_key);

CREATE INDEX IF NOT EXISTS stephen_dcx_file_objects_owner_user_id_idx
ON stephen_dcx_file_objects (owner_user_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_file_objects_file_kind_idx
ON stephen_dcx_file_objects (file_kind, created_at_ts_ms);

CREATE TABLE IF NOT EXISTS stephen_dcx_contact_message_attachments (
    id BIGINT NOT NULL DEFAULT nextval('stephen_dcx_contact_message_attachments_id_seq'::regclass),
    message_id BIGINT NOT NULL REFERENCES stephen_dcx_contact_messages (id) ON DELETE CASCADE,
    file_object_id BIGINT NOT NULL REFERENCES stephen_dcx_file_objects (id) ON DELETE CASCADE,
    attachment_role TEXT NOT NULL DEFAULT 'primary_media',
    provider_media_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 1,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_contact_message_attachments_pkey PRIMARY KEY (id),
    CONSTRAINT stephen_dcx_contact_message_attachments_role_chk
        CHECK (attachment_role IN ('primary_media', 'secondary_media', 'thumbnail', 'derived_artifact'))
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_contact_message_attachments_message_file_uidx
ON stephen_dcx_contact_message_attachments (message_id, file_object_id);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_contact_message_attachments_provider_media_uidx
ON stephen_dcx_contact_message_attachments (message_id, provider_media_id)
WHERE provider_media_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_attachments_message_id_idx
ON stephen_dcx_contact_message_attachments (message_id, sort_order);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_attachments_file_object_id_idx
ON stephen_dcx_contact_message_attachments (file_object_id);

CREATE TABLE IF NOT EXISTS stephen_dcx_contact_message_processing_jobs (
    id BIGINT NOT NULL DEFAULT nextval('stephen_dcx_contact_message_processing_jobs_id_seq'::regclass),
    message_id BIGINT NOT NULL REFERENCES stephen_dcx_contact_messages (id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    job_status TEXT NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    locked_at_ts_ms BIGINT,
    locked_by_worker TEXT,
    last_error_code TEXT,
    last_error_detail TEXT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_contact_message_processing_jobs_pkey PRIMARY KEY (id),
    CONSTRAINT stephen_dcx_contact_message_processing_jobs_type_chk
        CHECK (job_type IN ('derive_message_content')),
    CONSTRAINT stephen_dcx_contact_message_processing_jobs_status_chk
        CHECK (job_status IN ('queued', 'processing', 'completed', 'failed', 'cancelled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_contact_message_processing_jobs_one_active_uidx
ON stephen_dcx_contact_message_processing_jobs (message_id, job_type)
WHERE job_status IN ('queued', 'processing');

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_processing_jobs_claim_idx
ON stephen_dcx_contact_message_processing_jobs (job_status, available_at_ts_ms);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_processing_jobs_message_id_idx
ON stephen_dcx_contact_message_processing_jobs (message_id);

CREATE TABLE IF NOT EXISTS stephen_dcx_contact_message_analysis_runs (
    id BIGINT NOT NULL DEFAULT nextval('stephen_dcx_contact_message_analysis_runs_id_seq'::regclass),
    message_id BIGINT NOT NULL REFERENCES stephen_dcx_contact_messages (id) ON DELETE CASCADE,
    analysis_stage TEXT NOT NULL,
    model_name TEXT NOT NULL DEFAULT '',
    input_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_text TEXT NOT NULL DEFAULT '',
    output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_status TEXT NOT NULL DEFAULT 'started',
    error_code TEXT,
    started_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    completed_at_ts_ms BIGINT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_contact_message_analysis_runs_pkey PRIMARY KEY (id),
    CONSTRAINT stephen_dcx_contact_message_analysis_runs_stage_chk
        CHECK (analysis_stage IN ('message_derivation')),
    CONSTRAINT stephen_dcx_contact_message_analysis_runs_status_chk
        CHECK (run_status IN ('started', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_analysis_runs_message_id_idx
ON stephen_dcx_contact_message_analysis_runs (message_id, started_at_ts_ms);

CREATE INDEX IF NOT EXISTS stephen_dcx_contact_message_analysis_runs_stage_idx
ON stephen_dcx_contact_message_analysis_runs (analysis_stage, run_status);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'stephen_dcx_contact_message_provider_events_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_contact_message_provider_events_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_contact_message_provider_events
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
        WHERE tgname = 'stephen_dcx_contact_messages_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_contact_messages_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_contact_messages
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
        WHERE tgname = 'stephen_dcx_file_objects_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_file_objects_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_file_objects
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
        WHERE tgname = 'stephen_dcx_contact_message_attachments_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_contact_message_attachments_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_contact_message_attachments
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
        WHERE tgname = 'stephen_dcx_contact_message_processing_jobs_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_contact_message_processing_jobs_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_contact_message_processing_jobs
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
        WHERE tgname = 'stephen_dcx_contact_message_analysis_runs_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_contact_message_analysis_runs_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_contact_message_analysis_runs
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;
