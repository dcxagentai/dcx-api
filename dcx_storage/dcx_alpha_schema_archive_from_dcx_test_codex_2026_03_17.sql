-- CONTEXT:
-- This file archives the prior alpha-spike create-tables SQL that lived in the older dcx_test
-- workspace. It is preserved here for future reference before the MVP schema is rebuilt more
-- deliberately after the local-to-production plumbing is proven.
--
-- Source preserved from:
-- C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_test\dcx_test_codex\dcx_test_codex_storage\01_dcx_schema.sql

-- SCHEMA DEFINITION: Primary Tables for DCX Alpha Spike
-- ENCODING: UTF-8 assumed from database initialization.

-- Ensure we're in the right database (if run via command line)
-- \c dcx_agentic_alpha

-- 1. WAITLIST (Marketing)
CREATE TABLE IF NOT EXISTS dcx_marketing_waitlist (
    id SERIAL PRIMARY KEY,
    email_address VARCHAR(255) UNIQUE NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. LANGUAGES (For Context-Native Translation)
CREATE TABLE IF NOT EXISTS dcx_languages (
    id SERIAL PRIMARY KEY,
    lang_code VARCHAR(10) UNIQUE NOT NULL,
    lang_name VARCHAR(50) NOT NULL
);

-- 3. USERS (Semantically named 'dcx_users')
CREATE TABLE IF NOT EXISTS dcx_users (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(50) UNIQUE,
    email_address VARCHAR(255) UNIQUE,
    full_name VARCHAR(255),
    user_role VARCHAR(50) DEFAULT 'trader', -- 'trader', 'investor', 'admin'
    preferred_language VARCHAR(10) DEFAULT 'en' REFERENCES dcx_languages(lang_code),
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_contact_info CHECK (phone_number IS NOT NULL OR email_address IS NOT NULL)
);

-- 4. RAW MESSAGES (Semantically named 'dcx_raw_messages')
CREATE TABLE IF NOT EXISTS dcx_raw_messages (
    id SERIAL PRIMARY KEY,
    external_message_id VARCHAR(255) UNIQUE,
    dcx_sender_id INTEGER REFERENCES dcx_users(id),
    dcx_receiver_id INTEGER REFERENCES dcx_users(id),
    channel_type VARCHAR(50) NOT NULL,
    message_direction VARCHAR(20) NOT NULL,
    text_content TEXT,
    media_url VARCHAR(1024),
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. MESSAGE TRANSLATIONS
CREATE TABLE IF NOT EXISTS dcx_message_translations (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES dcx_raw_messages(id) ON DELETE CASCADE,
    lang_code VARCHAR(10) NOT NULL REFERENCES dcx_languages(lang_code) ON DELETE CASCADE,
    translated_text TEXT NOT NULL,
    UNIQUE (message_id, lang_code)
);

-- 6. COMMODITY DEALS (Semantically named 'dcx_commodity_deals')
CREATE TABLE IF NOT EXISTS dcx_commodity_deals (
    id SERIAL PRIMARY KEY,
    initiating_dcx_user_id INTEGER NOT NULL REFERENCES dcx_users(id),
    counterparty_dcx_user_id INTEGER REFERENCES dcx_users(id),
    deal_type VARCHAR(50) NOT NULL, -- 'bid', 'ask', 'unknown'
    commodity_type VARCHAR(255) NOT NULL, -- english canonical
    amount_value NUMERIC(15, 2),
    amount_unit VARCHAR(50),
    incoterm_type VARCHAR(50),
    location_port VARCHAR(255),
    proposed_price NUMERIC(15, 2),
    currency VARCHAR(10) DEFAULT 'USD',
    deal_status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. DEAL TRANSLATIONS
CREATE TABLE IF NOT EXISTS dcx_deal_translations (
    id SERIAL PRIMARY KEY,
    deal_id INTEGER NOT NULL REFERENCES dcx_commodity_deals(id) ON DELETE CASCADE,
    lang_code VARCHAR(10) NOT NULL REFERENCES dcx_languages(lang_code) ON DELETE CASCADE,
    translated_commodity_type VARCHAR(255) NOT NULL, -- e.g., 'Trigo'
    UNIQUE (deal_id, lang_code)
);

-- 8. OUTBOUND BROADCASTS
CREATE TABLE IF NOT EXISTS dcx_outbound_broadcasts (
    id SERIAL PRIMARY KEY,
    whatsapp_message_id VARCHAR(255) UNIQUE NOT NULL,
    deal_id INTEGER NOT NULL REFERENCES dcx_commodity_deals(id) ON DELETE CASCADE,
    receiver_dcx_user_id INTEGER NOT NULL REFERENCES dcx_users(id),
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_messages_sender ON dcx_raw_messages(dcx_sender_id);
CREATE INDEX idx_deals_initiator ON dcx_commodity_deals(initiating_dcx_user_id);
CREATE INDEX idx_deals_status ON dcx_commodity_deals(deal_status);
CREATE INDEX idx_msg_trans ON dcx_message_translations(message_id, lang_code);
CREATE INDEX idx_deal_trans ON dcx_deal_translations(deal_id, lang_code);
CREATE INDEX idx_broadcasts_message_id ON dcx_outbound_broadcasts(whatsapp_message_id);

-- 9. DEAL THREADS (Parallel Negotiations)
CREATE TABLE IF NOT EXISTS dcx_deal_threads (
    id SERIAL PRIMARY KEY,
    deal_id INTEGER NOT NULL REFERENCES dcx_commodity_deals(id) ON DELETE CASCADE,
    initiating_dcx_user_id INTEGER NOT NULL REFERENCES dcx_users(id),
    counterparty_dcx_user_id INTEGER NOT NULL REFERENCES dcx_users(id),
    thread_status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(deal_id, counterparty_dcx_user_id)
);
CREATE INDEX idx_deal_threads_deal ON dcx_deal_threads(deal_id);

-- 10. THREAD MESSAGES
CREATE TABLE IF NOT EXISTS dcx_thread_messages (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES dcx_deal_threads(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES dcx_raw_messages(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(thread_id, message_id)
);
CREATE INDEX idx_thread_messages_thread ON dcx_thread_messages(thread_id);
