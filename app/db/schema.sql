-- Minimal job store for the member-1 controller (first delivery).
-- Only the two tables the identity contract needs right now: jobs + artifacts.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    id                 TEXT PRIMARY KEY,
    original_sha256    TEXT NOT NULL,
    filename           TEXT NOT NULL,
    defect_description TEXT NOT NULL,
    phase              TEXT NOT NULL DEFAULT 'draft',
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id            TEXT PRIMARY KEY,
    job_id        TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    role          TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_job_id ON artifacts(job_id);
