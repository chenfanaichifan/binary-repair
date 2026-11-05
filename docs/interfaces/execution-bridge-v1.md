# Execution bridge v1 — bundle ingest contract

This is the host-side boundary between a guest executor and the controller.
The guest writes a bundle directory; the host adapter validates it before any
artifact is registered or any worker verdict is computed.

## Envelope (broker)

One JSON file per attempt in the inbox:

```json
{
  "job_id": "<id>",
  "run_id": "<id>",
  "attempt_id": "<id>",
  "route": "route_a",
  "bundle_path": "relative/path/to/bundle.json"
}
```

`bundle` may be inline instead of `bundle_path`. `bundle_path` must be a regular
file under the inbox directory; absolute paths, `..`, and symlinks are rejected.

## Bundle directory

```text
bundle.json
candidate.elf
audit.json
analysis/...
behavior-comparison.json
```

`bundle.json`:

```json
{
  "schema_version": 1,
  "route": "route_a",
  "candidate_sha256": "<64 lowercase hex>",
  "gates": {
    "V0": {"status": "passed", "artifacts": ["candidate.elf"]},
    "V1": {"status": "passed", "artifacts": ["audit.json"]},
    "V2": {"status": "not_run", "artifacts": []},
    "V3": {"status": "not_run", "artifacts": []},
    "V4": {"status": "not_run", "artifacts": []},
    "V5": {"status": "not_run", "artifacts": []}
  },
  "analysis": [{"role": "analysis_v3", "path": "analysis/v3.json"}],
  "comparison": "behavior-comparison.json"
}
```

## Reject list

The ingest adapter rejects without writing:

- `bundle.json` missing, non-object, wrong schema version, wrong route;
- candidate hash not 64 lowercase hex;
- unknown gate or unknown gate status;
- absolute artifact path, `..` escape, or symlink;
- missing artifact file;
- per-file size > 64 MiB or total > 256 MiB;
- a `passed` gate with no artifact;
- artifact path/destination collision with different bytes;
- wrong job/run/attempt/route binding;
- a different result bundle already at the attempt path (idempotent only for identical bytes).

## Idempotency

Re-ingesting the same bundle with unchanged bytes returns the existing artifact
ids and does not rewrite the attempt result. A conflicting existing artifact or
attempt bundle is rejected, never overwritten.

## Ownership

- Guest: writes bundle directory.
- M5: validates, registers artifacts, maps gates to artifact ids.
- M1: worker/controller transport.
- M4: independent re-hash and verdict review.

## Legacy INTERFACE-v1 compatibility

The ingest adapter also accepts the frozen 2026-10-29 package shape:

```text
handoff.json + SHA256SUMS + relative files
```

It validates that package with `scripts/check_handoff.py`, reads an optional
`result-bundle.json` for gate status/evidence, and registers all listed files.
If no `result-bundle.json` is present, gates default to `not_run`; the worker
then reports `inconclusive`, never success. This lets M3 continue producing the
old contract while the new `bundle.json` schema is adopted.
