-- Enable Row Level Security (RLS) on memories table
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;

-- Create policy to allow users to see/edit only their own data
-- Note: In a real app, this would use authenticated user ID from Supabase/Auth
-- For this microservice, we assume the application layer enforces user_id, 
-- but we can add policies based on current_setting if needed.
-- Since this is a standalone PostgreSQL, we'll keep it simple for now and 
-- just ensure all queries are filtered by user_id in the app layer.

DROP POLICY IF EXISTS user_isolation_policy ON memories;
CREATE POLICY user_isolation_policy ON memories
    USING (user_id::text = current_setting('app.current_user_id', true));

-- Audit logs should also have RLS
ALTER TABLE memory_audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_isolation_policy ON memory_audit_logs
    USING (EXISTS (
        SELECT 1 FROM memories 
        WHERE memories.id = memory_audit_logs.memory_id 
        AND memories.user_id::text = current_setting('app.current_user_id', true)
    ));
