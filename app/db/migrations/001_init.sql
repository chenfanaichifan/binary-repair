-- BinaryRepair MVP — initial SQLite schema (migration 001).
--
-- Scope: one operator, one machine, short transactions. Everything is text
-- (UUID ids, UTC ISO-8601 timestamps, lowercase 64-hex SHA-256) so records are
-- portable and diffable.
--
-- Ownership: the schema workstream defines and reviews this file; the job
-- controller applies it at startup and is the only writer.
--
-- Invariants encoded here (not just in application code):
--   * every contract belongs to a job; every run references a contract of the same job
--   * one idempotency key can start at most one run
--   * attempts are unique per (run, route, sequence)
--   * outcomes and obligation results use the PRD vocabulary only
--   * a "pass" obligation must reference evidence, except where explicitly allowed
--   * JSON columns are valid JSON
--   * costs are non-negative; NULL means "unavailable", never zero

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Jobs and reviewed contracts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    original_sha256  TEXT NOT NULL
                     CHECK (length(original_sha256) = 64
                            AND original_sha256 NOT GLOB '*[^0-9a-f]*'),
    fixture_id       TEXT,
    classification   TEXT NOT NULL DEFAULT 'public'
                     CHECK (classification IN ('public', 'client_authorized', 'synthetic')),
    created_at       TEXT NOT NULL,
    phase            TEXT NOT NULL
                     CHECK (phase IN ('draft', 'screening', 'awaiting_review', 'queued',
                                      'analyzing', 'generating', 'applying', 'roundtrip',
                                      'validating', 'finished', 'cancelled')),
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0, 1))
);

CREATE TABLE IF NOT EXISTS contracts (
    id             TEXT PRIMARY KEY,
    job_id         TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    revision       INTEGER NOT NULL CHECK (revision >= 1),
    body_json      TEXT NOT NULL CHECK (json_valid(body_json)),
    sha256         TEXT NOT NULL
                   CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    approved_at    TEXT,
    reviewer_label TEXT,
    UNIQUE (job_id, revision),
    UNIQUE (job_id, id),
    -- approval is atomic: either both fields are present or neither is
    CHECK ((approved_at IS NULL) = (reviewer_label IS NULL))
);

-- ---------------------------------------------------------------------------
-- Runs and attempts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS runs (
    id               TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    contract_id      TEXT NOT NULL,
    manifest_sha256  TEXT NOT NULL
                     CHECK (length(manifest_sha256) = 64
                            AND manifest_sha256 NOT GLOB '*[^0-9a-f]*'),
    idempotency_key  TEXT NOT NULL UNIQUE,
    phase            TEXT NOT NULL
                     CHECK (phase IN ('draft', 'screening', 'awaiting_review', 'queued',
                                      'analyzing', 'generating', 'applying', 'roundtrip',
                                      'validating', 'finished', 'cancelled')),
    outcome          TEXT
                     CHECK (outcome IS NULL OR outcome IN
                            ('success_within_scope', 'unsupported', 'rejected',
                             'inconclusive', 'error', 'cancelled')),
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    -- the contract must belong to the same job
    FOREIGN KEY (job_id, contract_id) REFERENCES contracts(job_id, id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id                TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    route             TEXT NOT NULL CHECK (route IN ('route_a', 'route_b')),
    sequence          INTEGER NOT NULL CHECK (sequence >= 1),
    candidate_sha256  TEXT
                      CHECK (candidate_sha256 IS NULL
                             OR (length(candidate_sha256) = 64
                                 AND candidate_sha256 NOT GLOB '*[^0-9a-f]*')),
    phase             TEXT NOT NULL
                      CHECK (phase IN ('draft', 'screening', 'awaiting_review', 'queued',
                                       'analyzing', 'generating', 'applying', 'roundtrip',
                                       'validating', 'finished', 'cancelled')),
    outcome           TEXT
                      CHECK (outcome IS NULL OR outcome IN
                             ('success_within_scope', 'unsupported', 'rejected',
                              'inconclusive', 'error', 'cancelled')),
    reason_code       TEXT,
    UNIQUE (run_id, route, sequence)
);

-- ---------------------------------------------------------------------------
-- Artifacts, obligations, events
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS artifacts (
    id            TEXT PRIMARY KEY,
    job_id        TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    attempt_id    TEXT REFERENCES attempts(id) ON DELETE SET NULL,
    relative_path TEXT NOT NULL,
    sha256        TEXT NOT NULL
                  CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    size_bytes    INTEGER NOT NULL CHECK (size_bytes >= 0),
    media_type    TEXT NOT NULL,
    role          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE (job_id, relative_path)
);

CREATE TABLE IF NOT EXISTS obligations (
    id                   TEXT PRIMARY KEY,
    attempt_id           TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    kind                 TEXT NOT NULL,
    required             INTEGER NOT NULL CHECK (required IN (0, 1)),
    result               TEXT NOT NULL
                         CHECK (result IN ('pass', 'fail', 'unknown', 'not_run',
                                           'unsupported', 'skipped')),
    scope_sha256         TEXT
                         CHECK (scope_sha256 IS NULL
                                OR (length(scope_sha256) = 64
                                    AND scope_sha256 NOT GLOB '*[^0-9a-f]*')),
    evidence_artifact_id TEXT REFERENCES artifacts(id),
    -- a passing obligation must point at evidence; not_run/unknown cannot pretend
    CHECK (result <> 'pass' OR evidence_artifact_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS events (
    sequence     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    attempt_id   TEXT REFERENCES attempts(id) ON DELETE SET NULL,
    timestamp    TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload_json))
);

-- ---------------------------------------------------------------------------
-- AI usage
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS model_calls (
    id                 TEXT PRIMARY KEY,
    attempt_id         TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    request_id         TEXT NOT NULL,
    provider           TEXT NOT NULL DEFAULT 'deepseek',
    model              TEXT NOT NULL,
    model_returned     TEXT,
    prompt_sha256      TEXT NOT NULL
                       CHECK (length(prompt_sha256) = 64
                              AND prompt_sha256 NOT GLOB '*[^0-9a-f]*'),
    response_sha256    TEXT
                       CHECK (response_sha256 IS NULL
                              OR (length(response_sha256) = 64
                                  AND response_sha256 NOT GLOB '*[^0-9a-f]*')),
    status             TEXT NOT NULL CHECK (length(status) > 0),
    usage_json         TEXT CHECK (usage_json IS NULL OR json_valid(usage_json)),
    estimated_cost_usd REAL CHECK (estimated_cost_usd IS NULL OR estimated_cost_usd >= 0),
    latency_ms         INTEGER NOT NULL DEFAULT 0 CHECK (latency_ms >= 0),
    attempts           INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    thinking           INTEGER NOT NULL DEFAULT 0 CHECK (thinking IN (0, 1)),
    created_at         TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Indexes and reporting views
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_jobs_created_at       ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_contracts_job         ON contracts(job_id, revision);
CREATE INDEX IF NOT EXISTS idx_runs_job              ON runs(job_id, started_at);
CREATE INDEX IF NOT EXISTS idx_attempts_run_route    ON attempts(run_id, route);
CREATE INDEX IF NOT EXISTS idx_artifacts_job         ON artifacts(job_id);
CREATE INDEX IF NOT EXISTS idx_obligations_attempt   ON obligations(attempt_id);
CREATE INDEX IF NOT EXISTS idx_events_run_seq        ON events(run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_model_calls_attempt   ON model_calls(attempt_id);
CREATE INDEX IF NOT EXISTS idx_model_calls_status    ON model_calls(status);

-- Per-job AI usage. Unknown cost is counted separately so the GUI can show
-- "unavailable" instead of silently displaying zero.
CREATE VIEW IF NOT EXISTS job_ai_usage AS
SELECT
    r.job_id                                          AS job_id,
    COUNT(m.id)                                       AS call_count,
    SUM(CASE WHEN m.estimated_cost_usd IS NULL
             THEN 1 ELSE 0 END)                       AS unknown_cost_calls,
    COALESCE(SUM(m.estimated_cost_usd), 0.0)          AS known_cost_usd,
    SUM(CASE WHEN m.status = 'accepted_for_validation'
             THEN 1 ELSE 0 END)                       AS accepted_candidates
FROM model_calls m
JOIN attempts a ON a.id = m.attempt_id
JOIN runs r     ON r.id = a.run_id
GROUP BY r.job_id;
