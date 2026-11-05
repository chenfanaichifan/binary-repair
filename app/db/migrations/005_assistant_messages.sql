ALTER TABLE assistant_plans ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE assistant_plans ADD COLUMN message_id TEXT;
CREATE INDEX IF NOT EXISTS idx_assistant_plans_version ON assistant_plans(job_id, version);
CREATE TABLE IF NOT EXISTS assistant_messages (
    id          TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    plan_id     TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assistant_messages_job ON assistant_messages(job_id, created_at);
ALTER TABLE model_calls ADD COLUMN assistant_plan_id TEXT;
