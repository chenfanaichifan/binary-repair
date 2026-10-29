# Run consumer / worker

`app/services/worker.py` consumes queued runs, persists V0-V5 obligations, calls
the acceptance engine, and writes attempt/run verdicts. It **does not execute
binaries**; an external executor supplies one result bundle per attempt.

## Command

```bash
python -m app.services.worker --data-dir var --once
```

Polling worker (independent process, not a controller background task):

```bash
python -m app.services.worker --data-dir var --poll 2
```

Environment:

```text
BINARYREPAIR_DATA_DIR=var
BINARYREPAIR_ATTEMPT_CMD=/path/to/executor   # optional; no shell expansion
```

If `BINARYREPAIR_ATTEMPT_CMD` is set, the worker runs it with:

```text
BINARYREPAIR_JOB_ID, BINARYREPAIR_RUN_ID, BINARYREPAIR_ATTEMPT_ID,
BINARYREPAIR_ROUTE, BINARYREPAIR_RESULT_PATH
```

The command must write the result bundle to `BINARYREPAIR_RESULT_PATH`. If the
bundle already exists, the command is not invoked.

## Result bundle

Path:

```text
<data-dir>/jobs/<job>/runs/<run>/attempts/<attempt_id>.json
```

Schema:

```json
{
  "route": "route_a",
  "candidate_sha256": "<64 hex>",
  "results": {"V0": "passed", "V1": "not_run", "...": "not_run"},
  "evidence": {"V1": "<artifact id>"},
  "details": {"V1": "why"}
}
```

Rules:

- missing bundle → run stays queued; the worker reports it;
- `passed` on V1–V5 requires `evidence` pointing at an artifact of the same job;
- V0 may omit evidence and uses the job's original artifact;
- no `passed` is invented; a missing check is `not_run`.

## Writes

- `obligations`: one row per V0–V5 via `app/services/obligations.py`;
- `attempts`: `phase`, `outcome`, `reason`, `failing_obligation`, `detail`;
- `runs`: `outcome`, `reason`, `failing_obligation`, `detail`, `finished_at`;
- files: `runs/<run>/attempts/<attempt>/verdict.json`,
  `jobs/<job>/run-verdict.json`.

`evaluate_run` is called only when both `route_a` and `route_b` verdicts exist.
A cancelled job is not overwritten with `finished`.

## Attempt writer / executor adapter

`python -m app.services.attempt_writer` writes the worker bundle from an executor
result:

```bash
# generic Route A adapter result
python -m app.services.attempt_writer \
  --input routea-result.json --route route_a \
  --out "$BINARYREPAIR_RESULT_PATH"

# Route B static bundle (V0/V1 from static audit; V3 only with manifest-compare)
python -m app.services.attempt_writer \
  --routeb-bundle /path/to/routeb-bundle \
  --data-dir var --job-id "$BINARYREPAIR_JOB_ID" \
  --attempt-id "$BINARYREPAIR_ATTEMPT_ID" \
  --out "$BINARYREPAIR_RESULT_PATH"
```

A wrapper script can be used directly as
`BINARYREPAIR_ATTEMPT_CMD=/path/to/write_attempt.sh`; the worker supplies the
`BINARYREPAIR_JOB_ID/RUN_ID/ATTEMPT_ID/ROUTE/RESULT_PATH` environment.

## Idempotency

`POST /api/jobs/{id}/runs` with an existing `(job_id, idempotency_key)` returns
the existing run only when `contract_id` and `manifest_sha256` match. A different
contract/manifest with the same key returns **409**.

## Snapshot

`GET /api/jobs/{id}` now reads the latest run's attempts and obligations:

- `verdict`: run-level `outcome/reason/failing_obligation/detail`;
- `run`: run id/phase/manifest/reviewed_scope;
- `routes.A/B`: real `phase`, `outcome`, `outcome_reason`, `verdict`, `obligations`,
  and stage states from the attempt phase.

Before any run exists, `routes` remains the initial placeholder. After the worker
finishes, the snapshot reflects the persisted attempt/run verdicts.
