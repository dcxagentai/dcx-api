CREATE TABLE IF NOT EXISTS stephen_dcx_emails_sends (
    id BIGSERIAL PRIMARY KEY,
    source_email_id BIGINT NOT NULL REFERENCES stephen_dcx_emails (id) ON DELETE RESTRICT,
    email_key_snapshot TEXT NOT NULL,
    send_status TEXT NOT NULL DEFAULT 'scheduled',
    send_audience_type TEXT NOT NULL DEFAULT 'announcements',
    scheduled_send_at_ts_ms BIGINT NOT NULL,
    send_started_at_ts_ms BIGINT,
    send_completed_at_ts_ms BIGINT,
    cancelled_at_ts_ms BIGINT,
    created_by_user_id BIGINT REFERENCES stephen_dcx_users (id) ON DELETE SET NULL,
    updated_by_user_id BIGINT REFERENCES stephen_dcx_users (id) ON DELETE SET NULL,
    send_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_emails_sends_status_chk
        CHECK (send_status IN ('scheduled', 'sending', 'sent', 'cancelled', 'failed')),
    CONSTRAINT stephen_dcx_emails_sends_audience_chk
        CHECK (send_audience_type IN ('announcements'))
);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_source_email_id_idx
ON stephen_dcx_emails_sends (source_email_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_email_key_snapshot_idx
ON stephen_dcx_emails_sends (email_key_snapshot);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_status_idx
ON stephen_dcx_emails_sends (send_status);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_scheduled_send_at_idx
ON stephen_dcx_emails_sends (scheduled_send_at_ts_ms);

CREATE TABLE IF NOT EXISTS stephen_dcx_emails_sends_recipients (
    id BIGSERIAL PRIMARY KEY,
    email_send_id BIGINT NOT NULL REFERENCES stephen_dcx_emails_sends (id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES stephen_dcx_users (id) ON DELETE CASCADE,
    resolved_email_id BIGINT NOT NULL REFERENCES stephen_dcx_emails (id) ON DELETE RESTRICT,
    recipient_email_snapshot TEXT NOT NULL,
    recipient_language_id_snapshot BIGINT REFERENCES stephen_dcx_languages (id) ON DELETE SET NULL,
    resolved_language_id_snapshot BIGINT REFERENCES stephen_dcx_languages (id) ON DELETE SET NULL,
    email_communication_preference_snapshot TEXT NOT NULL,
    delivery_decision TEXT NOT NULL,
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    provider_message_id TEXT,
    sent_at_ts_ms BIGINT,
    failed_at_ts_ms BIGINT,
    failure_reason TEXT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    CONSTRAINT stephen_dcx_emails_sends_recipients_decision_chk
        CHECK (delivery_decision IN ('send', 'skip_preference', 'skip_missing_email', 'skip_unconfirmed_email', 'skip_other')),
    CONSTRAINT stephen_dcx_emails_sends_recipients_status_chk
        CHECK (delivery_status IN ('pending', 'sent', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_recipients_email_send_id_idx
ON stephen_dcx_emails_sends_recipients (email_send_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_recipients_user_id_idx
ON stephen_dcx_emails_sends_recipients (user_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_recipients_delivery_status_idx
ON stephen_dcx_emails_sends_recipients (delivery_status);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_emails_sends_recipients_one_user_per_send_idx
ON stephen_dcx_emails_sends_recipients (email_send_id, user_id);

CREATE TABLE IF NOT EXISTS stephen_dcx_emails_sends_links (
    id BIGSERIAL PRIMARY KEY,
    email_send_id BIGINT NOT NULL REFERENCES stephen_dcx_emails_sends (id) ON DELETE CASCADE,
    resolved_email_id BIGINT NOT NULL REFERENCES stephen_dcx_emails (id) ON DELETE RESTRICT,
    original_url TEXT NOT NULL,
    tracking_token TEXT NOT NULL,
    link_label TEXT NOT NULL DEFAULT '',
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    UNIQUE (tracking_token)
);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_links_email_send_id_idx
ON stephen_dcx_emails_sends_links (email_send_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_links_resolved_email_id_idx
ON stephen_dcx_emails_sends_links (resolved_email_id);

CREATE TABLE IF NOT EXISTS stephen_dcx_emails_sends_link_clicks (
    id BIGSERIAL PRIMARY KEY,
    email_send_id BIGINT NOT NULL REFERENCES stephen_dcx_emails_sends (id) ON DELETE CASCADE,
    email_send_recipient_id BIGINT REFERENCES stephen_dcx_emails_sends_recipients (id) ON DELETE SET NULL,
    email_send_link_id BIGINT NOT NULL REFERENCES stephen_dcx_emails_sends_links (id) ON DELETE CASCADE,
    clicked_at_ts_ms BIGINT NOT NULL,
    request_ip TEXT,
    request_user_agent TEXT,
    created_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT,
    updated_at_ts_ms BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT
);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_link_clicks_email_send_id_idx
ON stephen_dcx_emails_sends_link_clicks (email_send_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_link_clicks_recipient_id_idx
ON stephen_dcx_emails_sends_link_clicks (email_send_recipient_id);

CREATE INDEX IF NOT EXISTS stephen_dcx_emails_sends_link_clicks_link_id_idx
ON stephen_dcx_emails_sends_link_clicks (email_send_link_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'stephen_dcx_emails_sends_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_emails_sends_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_emails_sends
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
        WHERE tgname = 'stephen_dcx_emails_sends_recipients_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_emails_sends_recipients_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_emails_sends_recipients
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
        WHERE tgname = 'stephen_dcx_emails_sends_links_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_emails_sends_links_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_emails_sends_links
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
        WHERE tgname = 'stephen_dcx_emails_sends_link_clicks_set_updated_at_ts_ms'
    ) THEN
        CREATE TRIGGER stephen_dcx_emails_sends_link_clicks_set_updated_at_ts_ms
        BEFORE UPDATE ON stephen_dcx_emails_sends_link_clicks
        FOR EACH ROW
        EXECUTE FUNCTION stephen_dcx_set_updated_at_ts_ms();
    END IF;
END
$$;
