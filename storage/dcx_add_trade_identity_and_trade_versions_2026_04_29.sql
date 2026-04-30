-- CONTEXT:
-- Splits the first Slice 1 trade-candidate persistence model into:
-- 1) a stable trade identity anchor in stephen_dcx_trades
-- 2) immutable trade-term versions in stephen_dcx_trade_versions
-- This keeps trade ids stable for links, routes, and future attached objects while letting
-- trade terms evolve as append-only versions.

ALTER TABLE stephen_dcx_trades
ADD COLUMN IF NOT EXISTS trade_key text,
ADD COLUMN IF NOT EXISTS source_message_id_initial bigint REFERENCES stephen_dcx_contact_messages(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS source_workflow_item_id_initial bigint REFERENCES stephen_dcx_message_workflow_items(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS current_version_id bigint,
ADD COLUMN IF NOT EXISTS current_trade_projection_status text NOT NULL DEFAULT 'completed',
ADD COLUMN IF NOT EXISTS current_trade_confirmation_status text NOT NULL DEFAULT 'pending_confirmation',
ADD COLUMN IF NOT EXISTS current_trade_status text NOT NULL DEFAULT 'draft';

UPDATE stephen_dcx_trades
SET
    trade_key = COALESCE(NULLIF(trade_key, ''), 'trade_' || id::text),
    source_message_id_initial = COALESCE(source_message_id_initial, source_message_id),
    source_workflow_item_id_initial = COALESCE(source_workflow_item_id_initial, source_workflow_item_id),
    current_trade_projection_status = COALESCE(NULLIF(current_trade_projection_status, ''), trade_projection_status),
    current_trade_confirmation_status = COALESCE(NULLIF(current_trade_confirmation_status, ''), trade_confirmation_status),
    current_trade_status = COALESCE(NULLIF(current_trade_status, ''), trade_status)
WHERE
    trade_key IS NULL
    OR trade_key = ''
    OR source_message_id_initial IS NULL
    OR source_workflow_item_id_initial IS NULL;

ALTER TABLE stephen_dcx_trades
ALTER COLUMN trade_key SET NOT NULL,
ALTER COLUMN source_message_id_initial SET NOT NULL,
ALTER COLUMN source_workflow_item_id_initial SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_trades_trade_key_key
ON stephen_dcx_trades(trade_key);

CREATE TABLE IF NOT EXISTS stephen_dcx_trade_versions (
    id bigserial PRIMARY KEY,
    trade_id bigint NOT NULL REFERENCES stephen_dcx_trades(id) ON DELETE CASCADE,
    source_message_id bigint NOT NULL REFERENCES stephen_dcx_contact_messages(id) ON DELETE CASCADE,
    source_workflow_item_id bigint NOT NULL REFERENCES stephen_dcx_message_workflow_items(id) ON DELETE CASCADE,
    source_channel_type text NOT NULL DEFAULT '',
    source_language_id bigint REFERENCES stephen_dcx_languages(id) ON DELETE SET NULL,
    version_number integer NOT NULL DEFAULT 1,
    is_live boolean NOT NULL DEFAULT TRUE,
    version_of_id bigint REFERENCES stephen_dcx_trade_versions(id) ON DELETE SET NULL,
    version_source_type text NOT NULL DEFAULT 'llm_projection',
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

CREATE INDEX IF NOT EXISTS stephen_dcx_trade_versions_trade_id_idx
ON stephen_dcx_trade_versions(trade_id, version_number DESC, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_trade_versions_trade_id_version_number_key
ON stephen_dcx_trade_versions(trade_id, version_number);

CREATE UNIQUE INDEX IF NOT EXISTS stephen_dcx_trade_versions_live_trade_id_key
ON stephen_dcx_trade_versions(trade_id)
WHERE is_live = TRUE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trade_versions_trade_projection_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trade_versions
        ADD CONSTRAINT stephen_dcx_trade_versions_trade_projection_status_check
        CHECK (trade_projection_status IN ('completed', 'failed'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trade_versions_trade_confirmation_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trade_versions
        ADD CONSTRAINT stephen_dcx_trade_versions_trade_confirmation_status_check
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
        WHERE conname = 'stephen_dcx_trade_versions_trade_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trade_versions
        ADD CONSTRAINT stephen_dcx_trade_versions_trade_status_check
        CHECK (trade_status IN ('draft', 'open', 'archived'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trade_versions_version_source_type_check'
    ) THEN
        ALTER TABLE stephen_dcx_trade_versions
        ADD CONSTRAINT stephen_dcx_trade_versions_version_source_type_check
        CHECK (
            version_source_type IN ('llm_projection', 'user_edit', 'user_confirm', 'user_reject')
        );
    END IF;
END $$;

INSERT INTO stephen_dcx_trade_versions (
    trade_id,
    source_message_id,
    source_workflow_item_id,
    source_channel_type,
    source_language_id,
    version_number,
    is_live,
    version_of_id,
    version_source_type,
    trade_projection_status,
    trade_confirmation_status,
    trade_status,
    raw_trade_side_text,
    raw_material_text,
    raw_quantity_text,
    raw_price_text,
    raw_origin_text,
    raw_destination_text,
    raw_shipping_method_text,
    raw_incoterm_text,
    raw_delivery_window_text,
    raw_quality_text,
    raw_payment_terms_text,
    raw_counterparty_scope_text,
    normalized_trade_side,
    normalized_material_name,
    normalized_quantity_value,
    normalized_quantity_unit,
    normalized_price_mode,
    normalized_price_value,
    normalized_price_unit_basis,
    normalized_currency_code,
    normalized_total_price_value,
    normalized_origin_location,
    normalized_destination_location,
    normalized_shipping_method,
    normalized_incoterm_code,
    normalized_delivery_window_start_text,
    normalized_delivery_window_end_text,
    normalized_quality_summary_text,
    normalized_payment_terms_summary_text,
    trade_summary_text,
    trade_extraction_notes_text,
    missing_required_fields_json,
    trade_metadata_json,
    created_at_ts_ms,
    updated_at_ts_ms
)
SELECT
    trade.id,
    trade.source_message_id_initial,
    trade.source_workflow_item_id_initial,
    trade.source_channel_type,
    trade.source_language_id,
    1,
    TRUE,
    NULL,
    'llm_projection',
    trade.trade_projection_status,
    trade.trade_confirmation_status,
    trade.trade_status,
    trade.raw_trade_side_text,
    trade.raw_material_text,
    trade.raw_quantity_text,
    trade.raw_price_text,
    trade.raw_origin_text,
    trade.raw_destination_text,
    trade.raw_shipping_method_text,
    trade.raw_incoterm_text,
    trade.raw_delivery_window_text,
    trade.raw_quality_text,
    trade.raw_payment_terms_text,
    trade.raw_counterparty_scope_text,
    trade.normalized_trade_side,
    trade.normalized_material_name,
    trade.normalized_quantity_value,
    trade.normalized_quantity_unit,
    trade.normalized_price_mode,
    trade.normalized_price_value,
    trade.normalized_price_unit_basis,
    trade.normalized_currency_code,
    trade.normalized_total_price_value,
    trade.normalized_origin_location,
    trade.normalized_destination_location,
    trade.normalized_shipping_method,
    trade.normalized_incoterm_code,
    trade.normalized_delivery_window_start_text,
    trade.normalized_delivery_window_end_text,
    trade.normalized_quality_summary_text,
    trade.normalized_payment_terms_summary_text,
    trade.trade_summary_text,
    trade.trade_extraction_notes_text,
    trade.missing_required_fields_json,
    trade.trade_metadata_json,
    trade.created_at_ts_ms,
    trade.updated_at_ts_ms
FROM stephen_dcx_trades trade
WHERE NOT EXISTS (
    SELECT 1
    FROM stephen_dcx_trade_versions version
    WHERE version.trade_id = trade.id
);

UPDATE stephen_dcx_trades trade
SET
    current_version_id = version.id,
    current_trade_projection_status = version.trade_projection_status,
    current_trade_confirmation_status = version.trade_confirmation_status,
    current_trade_status = version.trade_status
FROM stephen_dcx_trade_versions version
WHERE version.trade_id = trade.id
  AND version.is_live = TRUE
  AND (
      trade.current_version_id IS NULL
      OR trade.current_version_id <> version.id
  );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trades_current_version_id_fkey'
    ) THEN
        ALTER TABLE stephen_dcx_trades
        ADD CONSTRAINT stephen_dcx_trades_current_version_id_fkey
        FOREIGN KEY (current_version_id)
        REFERENCES stephen_dcx_trade_versions(id)
        ON DELETE SET NULL;
    END IF;
END $$;

ALTER TABLE stephen_dcx_trades
ALTER COLUMN current_version_id DROP NOT NULL;
