-- Migration 004: Create users table and link api_keys
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Link api_keys to users
-- If there are existing keys, we might need a default user or handle NULL
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(user_id);

-- Add index for user_id in api_keys
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys (user_id);

-- Update RLS if applicable (referencing 002_rls_setup.sql logic)
-- Assuming we want to keep RLS based on user_id
