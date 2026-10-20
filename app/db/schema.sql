-- Job store for the member-1 controller.
-- Identity/state tables for the §4.2 contract.

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

CREATE TABLE IF NOT EXISTS contracts (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    revision        INTEGER NOT NULL,
    input_sha256    TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    scope_sha256    TEXT NOT NULL,
    reviewer_label  TEXT NOT NULL,
    approved_at     TEXT NOT NULL,
    UNIQUE (job_id, revision)
);

CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    contract_id     TEXT NOT NULL REFERENCES contracts(id),
    idempotency_key TEXT NOT NULL,
    phase           TEXT NOT NULL DEFAULT 'queued',
    started_at      TEXT NOT NULL,
    UNIQUE (job_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_artifacts_job_id ON artifacts(job_id);
CREATE INDEX IF NOT EXISTS idx_contracts_job_id ON contracts(job_id);
CREATE INDEX IF NOT EXISTS idx_runs_job_id ON runs(job_id);
