-- Migration 006: API Key refactor and per-user Gemini key
-- Add gemini_api_key to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS gemini_api_key TEXT;

-- Make client_id optional in api_keys table
ALTER TABLE api_keys ALTER COLUMN client_id DROP NOT NULL;

-- Add index for user_id on api_keys if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
