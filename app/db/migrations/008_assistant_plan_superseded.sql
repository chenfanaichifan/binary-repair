ALTER TABLE assistant_plans ADD COLUMN superseded_by TEXT;
ALTER TABLE model_calls ADD COLUMN job_id TEXT;
ALTER TABLE model_calls ADD COLUMN plan_id TEXT;
