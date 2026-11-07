# M5 tool contracts v2 — corrections after M2 review 96

Status: Gate 2a document revision. This supersedes `m5-tool-contracts-v1.md`.
It does not claim the adapters exist. Gate 2b (adapter implementation + sample
mapping test) remains open.

## 0. Acceptance of M2 review 96

M5 accepts all three P0 findings:

1. `run_case` must dispatch by `input_mode`: `none` -> `run_manifest_compare.py`,
   `argv` -> `run_manifest_repaired.py`; no-input must not require
   `tests/invalid.json`.
2. `run_case` must not expose fake `argv`, `stdin_literal` or `stdin_artifact`
   parameters; v2 rejects them with `invalid_request`.
3. `apply_candidate` is renamed `ingest_bundle`, because creating a run/attempt
   and assembling a bundle is a separate layer that does not exist yet.
4. `read_evidence` must expose `input_mode`; `invalid_applicable` is legacy only.
5. `read_evidence` must not claim a `sha256` the endpoint does not return.

## 1. Accepted findings

M2 review 96 is correct on all three tools:

```text
run_case       v1 was not a thin wrapper; it invented argv/stdin/timeout/return fields
read_evidence  v1 lacked input_mode and claimed a sha256 the endpoint does not return
apply_candidate v1 described an application layer that does not exist
```

The mapping to existing commands was therefore rejected.

## 2. run_case v2

`run_case` is a dispatch adapter, not an executor.

Request:

```json
{
  "schema_version": 2,
  "case_id": "valid-no-input",
  "binary_path": "artifacts/candidate.elf",
  "contract_path": "fixtures/.../contract.json",
  "tests_dir": "fixtures/.../tests",
  "input_mode": "none",
  "timeout_ms": 10000,
  "idempotency_key": "job:attempt:case"
}
```

Explicitly unsupported in v2:

```text
argv: []              -> invalid_request, use input_mode=argv and tests/valid.json
stdin_literal         -> invalid_request, no runner support
stdin_artifact        -> invalid_request, no runner support
```

Dispatch:

| input_mode | existing runner |
|---|---|
| `none` + `original_path` | `routeb/run_manifest_compare.py` (byte comparison) |
| `none` without `original_path` | `routeb/run_manifest_repaired.py` (native no-input path) |
| `argv` | `routeb/run_manifest_repaired.py` (`valid.json` + `invalid.json`) |
| `stdin` | `invalid_request` in v2 |

Return:

```json
{
  "schema_version": 2,
  "case_id": "valid-no-input",
  "status": "passed|failed|timeout|invalid_request|error",
  "repaired_pass": true,
  "passed": 1,
  "total": 1,
  "cases": [
    {"id": "valid-no-input", "kind": "valid", "ok": true,
     "returncode": 0, "stdout_hex": "...", "stderr_hex": "..."}
  ],
  "edge": {"timeout": false, "invalid_applicable": false},
  "evidence_path": "evidence/valid-no-input.json",
  "idempotency_key": "..."
}
```

Mapping:

```text
repaired_pass=true and all ok -> status=passed
any ok=false                 -> status=failed
timeout=true                 -> status=timeout
manifest/contract error      -> status=invalid_request
```

Timeout: caller supplies `timeout_ms`; adapter must pass it to the runner and may
not use the runner's hard-coded 15 s silently. A timeout is never passed.

Idempotency: same key + same inputs returns the same `evidence_path`; different
inputs returns `409 idempotency_conflict`.

## 3. read_evidence v2

Request:

```json
{
  "schema_version": 2,
  "job_id": "job-id",
  "attempt_id": "attempt-id",
  "timeout_ms": 5000
}
```

Response:

```json
{
  "schema_version": 2,
  "status": "ok|not_found|not_persisted|error",
  "attempt_id": "...",
  "run_id": "...",
  "route": "route_b",
  "evidence": "persisted|not_persisted",
  "input_mode": "none|argv|stdin",
  "gates": [
    {"gate": "V3", "kind": "behaviour", "required": true,
     "result": "passed", "detail": "..."}
  ],
  "v3": {
    "gate": "V3",
    "kind": "behaviour",
    "result": "passed",
    "input_mode": "none",
    "valid": {"passed": 1, "total": 1},
    "invalid": {"passed": 0, "total": 0},
    "invalid_applicable": false,
    "legacy_invalid_applicable": true
  },
  "obligations": {"A": [], "B": []}
}
```

Changes from v1:

```text
input_mode is required
invalid_applicable is retained only as a legacy alias
v3.kind/result are explicit
sha256 is removed; the endpoint does not return it and v2 does not invent one
```

Status mapping:

```text
HTTP 200 + evidence=persisted -> ok
HTTP 200 + evidence=not_persisted -> not_persisted
HTTP 404 -> not_found
other -> error
```

## 4. apply_candidate v2 — includes the missing pre-layer

M2 is right that the previous `apply_candidate` described an application layer
that did not exist. v2 keeps the name `apply_candidate` and makes the pre-layer
explicit; `ingest_bundle` is the internal step, not the public tool.

Request:

```json
{
  "schema_version": 2,
  "job_id": "job-id",
  "run_id": "run-id-or-null",
  "attempt_id": "attempt-id-or-null",
  "route": "route_b",
  "candidate_path": "artifacts/candidate.elf",
  "candidate_sha256": "64-hex-assertion",
  "contract_revision": 1,
  "manifest_sha256": "64-hex",
  "bundle_path": "var/jobs/.../bundle",
  "no_trigger": false,
  "dry_run": false,
  "idempotency_key": "job:attempt:apply"
}
```

Preconditions and steps:

```text
1. job exists; contract revision is approved.
2. if run_id is null, create/reuse run by idempotency_key.
3. if attempt_id is null, create/reuse the route_b attempt.
4. assemble the bundle from candidate_path + evidence.
5. candidate_sha256 is an assertion: compare it with bundle V0 evidence and
   manifest["candidate_sha256"]; mismatch -> candidate_hash_mismatch.
6. call route_bundle_ingest / existing writer.
```

The tool does not build or execute the candidate. It only creates the run/attempt
metadata, assembles the bundle, and delegates to the existing ingest.

Return:

```json
{
  "schema_version": 2,
  "status": "applied|no_op|conflict|rejected|error",
  "job_id": "...",
  "run_id": "...",
  "attempt_id": "...",
  "bundle_path": "...",
  "candidate_sha256": "...",
  "previous_candidate_sha256": null,
  "evidence_artifact_ids": [],
  "rejected_reason": null,
  "idempotency_key": "..."
}
```

Status:

```text
same key + same candidate/bundle -> no_op
same key + different candidate/bundle -> conflict
candidate hash mismatch -> rejected + candidate_hash_mismatch
timeout/partial write -> error, no bundle committed
```

## 5. Gate split

Gate 2a: this document revision only. No code claim. [本机]

Gate 2b: adapter code plus sample mapping tests:

```text
run_case none/argv dispatch
read_evidence input_mode/status mapping
ingest_bundle idempotency and hash assertion
```

Gate 2b is not complete until tests run against real evidence JSON and a no-input
runner output. [M1 机 + M5 本机]

## 6. Non-claims

```text
No new executor.
No Gate 2 freeze until 2b.
No T8.3 gate change.
No verified_by.
```


## 7. Gate 2b implementation note

`tools/mcp_tool_adapters.py` now implements the first two adapters:

```text
run_case       none/argv dispatch, no fake stdin/argv parameters
read_evidence  input_mode, status mapping, no invented sha256
apply_candidate dry_run + candidate hash assertion
```

`apply_candidate` still returns `pre_layer_required` when `run_id`/`attempt_id`
are missing; creating them is the remaining Gate 2b work. The adapter is not a
claim that Gate 2b is accepted.
