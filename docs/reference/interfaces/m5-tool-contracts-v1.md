# M5 tool contracts v1 — run_case, read_evidence, apply_candidate

Status: draft contract, no new executor. Each tool is a thin wrapper around an
existing acceptance/route-B entry point.

Common rules:

```text
schema_version: 1
all timeouts are integer milliseconds, hard-capped by the caller
all mutating calls require idempotency_key
all returns include a stable top-level status and sha256 bindings
no tool executes a binary except run_case, which delegates to the existing runner
```

## 1. run_case

Wraps the existing P2 / Route B manifest runner; it does not add an executor.

Request:

```json
{
  "schema_version": 1,
  "case_id": "valid-no-input",
  "binary_path": "artifacts/candidate.elf",
  "contract_path": "fixtures/.../contract.json",
  "input_mode": "none",
  "argv": ["./original"],
  "stdin_literal": null,
  "stdin_artifact": null,
  "timeout_ms": 10000,
  "idempotency_key": "job:attempt:case:run"
}
```

Response:

```json
{
  "schema_version": 1,
  "case_id": "valid-no-input",
  "status": "passed",
  "exit_code": 0,
  "timed_out": false,
  "stdout_sha256": "...",
  "stderr_sha256": "...",
  "stdout_bytes": 100,
  "stderr_bytes": 0,
  "duration_ms": 12,
  "evidence_path": "evidence/valid-no-input.json",
  "idempotency_key": "..."
}
```

Status: `passed | failed | timeout | error | skipped`.

Timeout: caller supplies `timeout_ms`; wrapper must not exceed the caller cap and
must set `timed_out=true` on expiry. A timeout is never `passed`.

Idempotency: same `idempotency_key` + same inputs returns the same evidence path;
different inputs with the same key returns `409 idempotency_conflict`.

Errors: `invalid_request`, `binary_not_found`, `contract_invalid`, `timeout`,
`runner_error`.

## 2. read_evidence

Wraps `GET /api/attempts/{id}/evidence` / the persisted obligation rows.

Request:

```json
{
  "schema_version": 1,
  "job_id": "job-id",
  "attempt_id": "attempt-id",
  "include_artifact_bytes": false,
  "timeout_ms": 5000
}
```

Response:

```json
{
  "schema_version": 1,
  "status": "ok",
  "attempt_id": "...",
  "run_id": "...",
  "route": "route_b",
  "evidence": "persisted",
  "gates": [
    {"gate": "V3", "kind": "behaviour", "required": true, "result": "passed"}
  ],
  "v3": {
    "gate": "V3",
    "valid": {"passed": 1, "total": 1},
    "invalid": {"passed": 0, "total": 0},
    "invalid_applicable": false
  },
  "obligations": {"A": [], "B": []},
  "sha256": "..."
}
```

Status: `ok | not_found | not_persisted | error`.

Timeout: read-only, bounded by `timeout_ms`; no retry of a partially read body.

Idempotency: read-only, naturally idempotent; same request must not mutate rows.

Errors: `not_found`, `invalid_request`, `timeout`, `backend_error`.

## 3. apply_candidate

Wraps the existing bundle ingest / attempt writer; it does not build or execute.

Request:

```json
{
  "schema_version": 1,
  "job_id": "job-id",
  "artifact_id": "artifact-id",
  "candidate_sha256": "64-hex",
  "dry_run": false,
  "idempotency_key": "job:attempt:apply:candidate"
}
```

Response:

```json
{
  "schema_version": 1,
  "status": "applied",
  "job_id": "...",
  "attempt_id": "...",
  "candidate_sha256": "...",
  "previous_candidate_sha256": null,
  "bundle_path": "var/jobs/.../bundle.json",
  "rejected_reason": null,
  "idempotency_key": "..."
}
```

Status: `applied | rejected | no_op | conflict | error`.

Timeout: default 5000 ms; ingest must fail closed on timeout, not write a partial
bundle.

Idempotency: same key + same candidate hash returns `no_op`; same key + different
candidate returns `conflict`; never overwrite an existing candidate silently.

Errors: `candidate_hash_mismatch`, `artifact_not_found`, `bundle_invalid`,
`conflict`, `timeout`, `backend_error`.

## 4. Mapping to existing code

| Tool | Existing entry point |
|---|---|
| `run_case` | `routeb/run_manifest_repaired.py` / `routeb/run_manifest_compare.py` |
| `read_evidence` | `GET /api/attempts/{id}/evidence`, `app/services/jobs.list_obligations` |
| `apply_candidate` | `tools/route_bundle_ingest.py`, `app/services/attempt_writer.py` |

No new execution engine, no new gate, no gate override.
