-- CONTEXT:
-- Slice 1 trade UX now exposes a single visible trade state while preserving the
-- existing two-column storage model underneath trade identity/version rows.
--
-- Run this after dcx_add_message_workflow_trade_and_topic_tables_2026_04_28.sql
-- and dcx_add_trade_identity_and_trade_versions_2026_04_29.sql.

UPDATE stephen_dcx_trades
SET
    trade_status = CASE WHEN trade_status = 'watching' THEN 'draft' ELSE trade_status END,
    current_trade_status = CASE WHEN current_trade_status = 'watching' THEN 'draft' ELSE current_trade_status END;

UPDATE stephen_dcx_trade_versions
SET trade_status = 'draft'
WHERE trade_status = 'watching';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trades_trade_confirmation_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trades
        DROP CONSTRAINT stephen_dcx_trades_trade_confirmation_status_check;
    END IF;

    ALTER TABLE stephen_dcx_trades
    ADD CONSTRAINT stephen_dcx_trades_trade_confirmation_status_check
    CHECK (
        trade_confirmation_status IN (
            'draft',
            'needs_more_detail',
            'pending_confirmation',
            'confirmed',
            'under_revision',
            'rejected'
        )
    );

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trades_trade_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trades
        DROP CONSTRAINT stephen_dcx_trades_trade_status_check;
    END IF;

    ALTER TABLE stephen_dcx_trades
    ADD CONSTRAINT stephen_dcx_trades_trade_status_check
    CHECK (trade_status IN ('draft', 'open', 'archived'));

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trade_versions_trade_confirmation_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trade_versions
        DROP CONSTRAINT stephen_dcx_trade_versions_trade_confirmation_status_check;
    END IF;

    ALTER TABLE stephen_dcx_trade_versions
    ADD CONSTRAINT stephen_dcx_trade_versions_trade_confirmation_status_check
    CHECK (
        trade_confirmation_status IN (
            'draft',
            'needs_more_detail',
            'pending_confirmation',
            'confirmed',
            'under_revision',
            'rejected'
        )
    );

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'stephen_dcx_trade_versions_trade_status_check'
    ) THEN
        ALTER TABLE stephen_dcx_trade_versions
        DROP CONSTRAINT stephen_dcx_trade_versions_trade_status_check;
    END IF;

    ALTER TABLE stephen_dcx_trade_versions
    ADD CONSTRAINT stephen_dcx_trade_versions_trade_status_check
    CHECK (trade_status IN ('draft', 'open', 'archived'));
END $$;
