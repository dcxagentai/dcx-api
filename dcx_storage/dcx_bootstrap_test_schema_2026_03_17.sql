-- CONTEXT:
-- This file is the fresh minimal Postgres schema used to prove the first local-to-production
-- plumbing path for the DCX MVP shell. It intentionally creates only one table and one stable
-- seeded message so the backend and three frontends can prove the roundtrip without depending on
-- the older alpha schema.

CREATE TABLE IF NOT EXISTS dcx_bootstrap_test_messages (
    id SERIAL PRIMARY KEY,
    message_key VARCHAR(100) UNIQUE NOT NULL,
    channel_type VARCHAR(50) NOT NULL,
    message_direction VARCHAR(20) NOT NULL,
    text_content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO dcx_bootstrap_test_messages (
    message_key,
    channel_type,
    message_direction,
    text_content
)
VALUES (
    'bootstrap_hello_world',
    'bootstrap',
    'system',
    'Hello from the fresh DCX bootstrap test schema.'
)
ON CONFLICT (message_key) DO UPDATE
SET
    channel_type = EXCLUDED.channel_type,
    message_direction = EXCLUDED.message_direction,
    text_content = EXCLUDED.text_content;
