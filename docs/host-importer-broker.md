# Host importer / broker

The controller does not execute binaries. Host-side evidence arrives as result
bundles; these tools place them into the controller store atomically and trigger
the worker.

## Single import

```bash
python tools/host_importer.py \
  --data-dir var \
  --job-id <job> --run-id <run> --attempt-id <attempt> \
  --route route_a \
  --bundle /path/to/result.json
```

The bundle is written to:

```text
<data>/jobs/<job>/runs/<run>/attempts/<attempt>.json
```

Behaviour:

- validates the attempt belongs to the run, the run belongs to the job, and the
  route matches the persisted attempt;
- validates the bundle JSON shape (candidate + results);
- writes with a temp file + `os.replace`, so readers never see a partial file;
- idempotent when the existing bytes are identical;
- refuses to overwrite different existing bytes;
- triggers `app.services.worker.run_once()` by default; pass `--no-trigger` to
  import only.

## Inbox broker

```bash
python tools/host_broker.py \
  --data-dir var \
  --inbox var/inbox \
  --once
```

Drop one JSON envelope per attempt:

```json
{
  "job_id": "...",
  "run_id": "...",
  "attempt_id": "...",
  "route": "route_a",
  "bundle": {
    "route": "route_a",
    "candidate_sha256": "<64 hex>",
    "results": {"V0": "not_run", "V1": "not_run"}
  }
}
```

Or use a sibling file:

```json
{"job_id": "...", "run_id": "...", "attempt_id": "...",
 "route": "route_a", "bundle_path": "bundle.json"}
```

Each successful envelope moves to `inbox/processed/`; a rejected envelope moves
to `inbox/failed/` with `<name>.error.txt`. The worker is triggered once per
batch. `--once` exits `1` if any envelope failed.

## Guarantees

- **Atomic:** no partial bundle at the controller path.
- **Idempotent:** identical bytes are accepted without rewrite.
- **Fail closed:** wrong job/run/attempt/route, malformed JSON, or a conflicting
  existing bundle writes nothing.
- **No fake verdict:** the worker still computes V0–V5 and the verdict; the
  importer only moves bytes.
- **No shell:** both tools are Python; they do not execute uploaded binaries.

## Tests

```text
python -m pytest -q tests/integration/test_host_broker.py
# 2 passed
```
