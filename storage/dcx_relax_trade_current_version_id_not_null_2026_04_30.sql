-- CONTEXT:
-- The Slice 1 trade-version model stores trade identity in stephen_dcx_trades and immutable
-- trade terms in stephen_dcx_trade_versions. current_version_id is a head pointer, not part of
-- identity. It must be nullable while a new trade identity row is inserted and its first version
-- row is created in the same transaction.

ALTER TABLE stephen_dcx_trades
ALTER COLUMN current_version_id DROP NOT NULL;
