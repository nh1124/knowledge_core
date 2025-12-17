-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enum types
CREATE TYPE memory_type_enum AS ENUM ('fact', 'state', 'episode');
CREATE TYPE scope_enum AS ENUM ('global', 'agent');
CREATE TYPE input_channel_enum AS ENUM ('chat', 'manual', 'api', 'import');
CREATE TYPE audit_action_enum AS ENUM ('create', 'update', 'delete', 'restore', 'confirm', 'reject');
CREATE TYPE actor_type_enum AS ENUM ('system', 'user', 'admin');

-- Main memories table
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),
    memory_type memory_type_enum NOT NULL,
    tags TEXT[] DEFAULT '{}',
    scope scope_enum DEFAULT 'global',
    agent_id TEXT,
    importance SMALLINT DEFAULT 3 CHECK (importance >= 1 AND importance <= 5),
    confidence REAL DEFAULT 0.7 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    related_entities JSONB,
    source TEXT,
    input_channel input_channel_enum,
    content_hash TEXT,
    
    -- Lifecycle columns
    event_time TIMESTAMP WITH TIME ZONE,
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_to TIMESTAMP WITH TIME ZONE,
    last_accessed TIMESTAMP WITH TIME ZONE,
    supersedes_id UUID REFERENCES memories(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit logs table
CREATE TABLE memory_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    action audit_action_enum NOT NULL,
    actor_type actor_type_enum DEFAULT 'system',
    diff JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
-- 1. Vector search index (HNSW for cosine similarity)
CREATE INDEX idx_memories_embedding ON memories 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 2. GIN indexes for array/JSONB columns
CREATE INDEX idx_memories_tags ON memories USING GIN (tags);
CREATE INDEX idx_memories_related_entities ON memories USING GIN (related_entities);

-- 3. Composite index for scope filtering
CREATE INDEX idx_memories_user_scope ON memories (user_id, scope, agent_id);

-- 4. Unique constraint for deduplication
CREATE UNIQUE INDEX idx_memories_content_hash_unique 
ON memories (user_id, scope, COALESCE(agent_id, ''), content_hash) 
WHERE content_hash IS NOT NULL;

-- 5. Time-based filtering
CREATE INDEX idx_memories_valid_from ON memories (valid_from);
CREATE INDEX idx_memories_event_time ON memories (event_time);

-- 6. Audit log index
CREATE INDEX idx_audit_logs_memory_id ON memory_audit_logs (memory_id);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_memories_updated_at
    BEFORE UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
