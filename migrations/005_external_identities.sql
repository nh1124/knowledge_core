-- Migration 005: Create external_identities table
CREATE TABLE IF NOT EXISTS external_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE NOT NULL,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(issuer, subject)
);

-- Index for fast lookup by external identity
CREATE INDEX IF NOT EXISTS idx_external_identities_lookup ON external_identities (issuer, subject);
