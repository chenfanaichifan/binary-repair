# attempt_writer generic input schema

`python -m app.services.attempt_writer --input <json>` accepts one **attempt**
map and writes the worker bundle at `--out` / `BINARYREPAIR_RESULT_PATH`.

This is a mapping layer only. It never computes an outcome; the worker's
`orchestration.evaluate_attempt/evaluate_run` remains the decision point.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `results` | object `V0..V5 -> string` | yes | CheckResult values: `passed`, `failed`, `not_run`, `unknown`, `timed_out` |
| `candidate_sha256` | 64-char lowercase/hex string | yes* | Final candidate ELF hash; *may be supplied with `--candidate-sha256` |
| `route` | `route_a` or `route_b` | no | If present, must match `--route` |
| `evidence` | object `V1..V5 -> artifact id` | no | Already-registered artifact IDs |
| `evidence_files` | object `V1..V5 -> path` | no | Files to register as artifacts; relative to the input JSON directory |
| `details` | object `V1..V5 -> string` | no | Human-readable check detail |

Rules:

- `results` must contain V0–V5 keys for the intended gates; missing gates are
  treated as `not_run` by orchestration.
- `passed` on V1–V5 requires evidence (`evidence` or `evidence_files`); otherwise
  the worker rejects the bundle at `persist_obligations`.
- V0 may omit evidence; the worker uses the job's original artifact.
- `evidence` IDs win over `evidence_files` for the same gate.
- `evidence_files` paths: absolute path, or relative to the directory containing
  the input JSON. Files are copied under `<data>/jobs/<job>/artifacts/` and the
  DB stores a relative path; absolute host paths are not stored.
- Do not put `outcome`, `reason`, or `decision` in this file. The worker decides.

## Minimal example

`routea-attempt.json`:

```json
{
  "route": "route_a",
  "candidate_sha256": "c4a1590000000000000000000000000000000000000000000000000000000000",
  "results": {
    "V0": "passed",
    "V1": "passed",
    "V2": "passed",
    "V3": "passed",
    "V4": "not_run",
    "V5": "not_run"
  },
  "evidence_files": {
    "V1": "evidence/readelf.txt",
    "V2": "evidence/compat.log",
    "V3": "evidence/manifest-compare.json"
  },
  "details": {
    "V4": "symbolic budget not available in this run"
  }
}
```

Command:

```bash
python -m app.services.attempt_writer \
  --input routea-attempt.json \
  --route route_a \
  --data-dir var \
  --job-id "$BINARYREPAIR_JOB_ID" \
  --attempt-id "$BINARYREPAIR_ATTEMPT_ID" \
  --out "$BINARYREPAIR_RESULT_PATH"
```

## Is a `result-bundle.json` directly usable?

**Usually no.** A result bundle normally contains file paths, evidence lists,
`pass/fail`, and possibly an outcome. Convert it with a thin map:

1. copy `candidate_sha256` from the candidate ELF hash;
2. map evidence result `pass -> passed`, `fail -> failed`, `not_run -> not_run`;
3. put evidence paths under `evidence_files` (or pre-register and use `evidence`);
4. drop any `outcome` field;
5. keep `details` if present.

The worker/writer never accepts a precomputed outcome. `decision.json` is an M3
evidence artifact, not a controller verdict.
