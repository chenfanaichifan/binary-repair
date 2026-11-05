CREATE TABLE IF NOT EXISTS assistant_plans (
    id          TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    mode        TEXT NOT NULL,
    plan_json   TEXT NOT NULL,
    model       TEXT,
    usage_json  TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assistant_plans_job ON assistant_plans(job_id, created_at);
