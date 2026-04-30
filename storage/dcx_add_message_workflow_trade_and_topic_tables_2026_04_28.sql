-- CONTEXT:
-- Adds the first workflow-routing schema on top of the canonical contact-message model.
-- This slice projects one stored inbound message into workflow items, trade candidates,
-- and market-topic seeds without introducing any new external providers.

ALTER TABLE stephen_dcx_contact_messages
ADD COLUMN IF NOT EXISTS workflow_classification_status text NOT NULL DEFAULT 'not_started',
ADD COLUMN IF NOT EXISTS primary_workflow_kind text,
ADD COLUMN IF NOT EXISTS contains_trade_items boolean NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS contains_market_topic_items boolean NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS contains_other_items boolean NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS workflow_reason_summary text NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS workflow_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS workflow_completed_at_ts_ms bigint;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_contact_messages_workflow_classification_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_contact_messages
        ADD CONSTRAINT stephen_dcx_contact_messages_workflow_classification_status_check
        CHECK (
            workflow_classification_status IN ('not_started', 'partial', 'completed', 'failed')
        );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_contact_messages_primary_workflow_kind_check'
    ) THEN
        ALTER TABLE stephen_dcx_contact_messages
        ADD CONSTRAINT stephen_dcx_contact_messages_primary_workflow_kind_check
        CHECK (
            primary_workflow_kind IS NULL
            OR primary_workflow_kind IN ('trade', 'market_topic', 'other')
        );
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS stephen_dcx_message_workflow_items (
    id bigserial PRIMARY KEY,
    message_id bigint NOT NULL REFERENCES stephen_dcx_contact_messages(id) ON DELETE CASCADE,
    item_index integer NOT NULL,
    item_kind text NOT NULL,
    item_status text NOT NULL DEFAULT 'identified',
    item_title text NOT NULL DEFAULT '',
    item_summary_text text NOT NULL DEFAULT '',
    source_excerpt_text text NOT NULL DEFAULT '',
    referenced_attachment_ids_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence_label text NOT NULL DEFAULT '',
    workflow_item_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint,
    updated_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_message_workflow_items_message_id_item_index_key
ON stephen_dcx_message_workflow_items(message_id, item_index);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_message_workflow_items_item_kind_check'
    ) THEN
        ALTER TABLE stephen_dcx_message_workflow_items
        ADD CONSTRAINT stephen_dcx_message_workflow_items_item_kind_check
        CHECK (item_kind IN ('trade', 'market_topic', 'other'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_message_workflow_items_item_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_message_workflow_items
        ADD CONSTRAINT stephen_dcx_message_workflow_items_item_status_check
        CHECK (item_status IN ('identified', 'projected', 'failed', 'ignored'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS stephen_dcx_trades (
    id bigserial PRIMARY KEY,
    source_message_id bigint NOT NULL REFERENCES stephen_dcx_contact_messages(id) ON DELETE CASCADE,
    source_workflow_item_id bigint NOT NULL REFERENCES stephen_dcx_message_workflow_items(id) ON DELETE CASCADE,
    initiating_user_id bigint REFERENCES stephen_dcx_users(id) ON DELETE SET NULL,
    initiating_contact_method_id bigint REFERENCES stephen_dcx_users_contact_methods(id) ON DELETE SET NULL,
    source_channel_type text NOT NULL DEFAULT '',
    source_language_id bigint REFERENCES stephen_dcx_languages(id) ON DELETE SET NULL,
    trade_projection_status text NOT NULL DEFAULT 'completed',
    trade_confirmation_status text NOT NULL DEFAULT 'pending_confirmation',
    trade_status text NOT NULL DEFAULT 'draft',
    raw_trade_side_text text NOT NULL DEFAULT '',
    raw_material_text text NOT NULL DEFAULT '',
    raw_quantity_text text NOT NULL DEFAULT '',
    raw_price_text text NOT NULL DEFAULT '',
    raw_origin_text text NOT NULL DEFAULT '',
    raw_destination_text text NOT NULL DEFAULT '',
    raw_shipping_method_text text NOT NULL DEFAULT '',
    raw_incoterm_text text NOT NULL DEFAULT '',
    raw_delivery_window_text text NOT NULL DEFAULT '',
    raw_quality_text text NOT NULL DEFAULT '',
    raw_payment_terms_text text NOT NULL DEFAULT '',
    raw_counterparty_scope_text text NOT NULL DEFAULT '',
    normalized_trade_side text NOT NULL DEFAULT '',
    normalized_material_name text NOT NULL DEFAULT '',
    normalized_quantity_value numeric,
    normalized_quantity_unit text NOT NULL DEFAULT '',
    normalized_price_mode text NOT NULL DEFAULT '',
    normalized_price_value numeric,
    normalized_price_unit_basis text NOT NULL DEFAULT '',
    normalized_currency_code text NOT NULL DEFAULT '',
    normalized_total_price_value numeric,
    normalized_origin_location text NOT NULL DEFAULT '',
    normalized_destination_location text NOT NULL DEFAULT '',
    normalized_shipping_method text NOT NULL DEFAULT '',
    normalized_incoterm_code text NOT NULL DEFAULT '',
    normalized_delivery_window_start_text text NOT NULL DEFAULT '',
    normalized_delivery_window_end_text text NOT NULL DEFAULT '',
    normalized_quality_summary_text text NOT NULL DEFAULT '',
    normalized_payment_terms_summary_text text NOT NULL DEFAULT '',
    trade_summary_text text NOT NULL DEFAULT '',
    trade_extraction_notes_text text NOT NULL DEFAULT '',
    missing_required_fields_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    trade_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint,
    updated_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_trades_source_workflow_item_id_key
ON stephen_dcx_trades(source_workflow_item_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trades_trade_projection_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trades
        ADD CONSTRAINT stephen_dcx_trades_trade_projection_status_check
        CHECK (trade_projection_status IN ('completed', 'failed'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trades_trade_confirmation_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trades
        ADD CONSTRAINT stephen_dcx_trades_trade_confirmation_status_check
        CHECK (
            trade_confirmation_status IN ('draft', 'pending_confirmation', 'needs_more_detail', 'confirmed', 'under_revision', 'rejected')
        );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trades_trade_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trades
        ADD CONSTRAINT stephen_dcx_trades_trade_status_check
        CHECK (trade_status IN ('draft', 'open', 'archived'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS stephen_dcx_market_topics (
    id bigserial PRIMARY KEY,
    source_message_id bigint NOT NULL REFERENCES stephen_dcx_contact_messages(id) ON DELETE CASCADE,
    source_workflow_item_id bigint NOT NULL REFERENCES stephen_dcx_message_workflow_items(id) ON DELETE CASCADE,
    initiating_user_id bigint REFERENCES stephen_dcx_users(id) ON DELETE SET NULL,
    initiating_contact_method_id bigint REFERENCES stephen_dcx_users_contact_methods(id) ON DELETE SET NULL,
    topic_status text NOT NULL DEFAULT 'open',
    topic_title text NOT NULL DEFAULT '',
    topic_summary_text text NOT NULL DEFAULT '',
    topic_scope_text text NOT NULL DEFAULT '',
    topic_tags_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    topic_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint,
    updated_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_market_topics_source_workflow_item_id_key
ON stephen_dcx_market_topics(source_workflow_item_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_market_topics_topic_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_market_topics
        ADD CONSTRAINT stephen_dcx_market_topics_topic_status_check
        CHECK (topic_status IN ('open', 'archived'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS stephen_dcx_market_topic_turns (
    id bigserial PRIMARY KEY,
    market_topic_id bigint NOT NULL REFERENCES stephen_dcx_market_topics(id) ON DELETE CASCADE,
    turn_role text NOT NULL,
    source_message_id bigint REFERENCES stephen_dcx_contact_messages(id) ON DELETE SET NULL,
    turn_text text NOT NULL DEFAULT '',
    turn_metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint,
    updated_at_ts_ms bigint NOT NULL DEFAULT (floor(extract(epoch from clock_timestamp()) * 1000))::bigint
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_market_topic_turns_turn_role_check'
    ) THEN
        ALTER TABLE stephen_dcx_market_topic_turns
        ADD CONSTRAINT stephen_dcx_market_topic_turns_turn_role_check
        CHECK (turn_role IN ('user', 'assistant', 'system'));
    END IF;
END $$;
