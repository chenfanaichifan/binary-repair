# Route A attempt input schema (for `app.services.attempt_writer --input`)

M1's worker consumes a per-attempt JSON written by
`python -m app.services.attempt_writer --input <file> --route route_a --out "$BINARYREPAIR_RESULT_PATH"`.
M3 should produce `<file>` from the real Route A result bundle.

## Input JSON (generic mode)

```json
{
  "candidate_sha256": "<64 lowercase hex>",
  "results": {
    "V0": "passed",
    "V1": "unknown",
    "V2": "not_run",
    "V3": "passed",
    "V4": "not_run",
    "V5": "not_run"
  },
  "evidence": {
    "V0": "route_a/candidate.elf",
    "V1": "route_a/audit.json",
    "V3": "evidence/v3/formal-run.json"
  },
  "details": {
    "V1": "LIEF structural view incomplete (load_segments/gnu_stack empty, nx=null)",
    "V3": "six cases 6/6; candidate before/after identical (c4a159...)"
  }
}
```

- `candidate_sha256` must be the Route A candidate hash (for the real gate-3
  run: `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82`).
- `results` values **must use M4's CheckResult vocabulary**:
  `passed | failed | not_run | unknown | timed_out`.
  Do not put `inconclusive`, `unsupported`, `pass` or `fail` here.
- `evidence` / `details` are optional maps keyed by `V0..V5`; strings only.
- Do not add an `outcome` field; the acceptance engine decides it.

## Mapping from the real gate-3 bundle

| Gate | Real evidence | `results` value |
|---|---|---|
| V0 | original/candidate hashes match | `passed` |
| V1 | LIEF structural view incomplete | `unknown` (or `not_run` if unavailable) |
| V2 | interface evidence missing | `not_run` |
| V3 | six cases 6/6; candidate before/after both c4a159 | `passed` (only with formal-run.json) |
| V4 | symbolic evidence missing | `not_run` |
| V5 | replay evidence missing | `not_run` |

## Worker-side invocation

```powershell
# in the controller worktree; worker passes the IDs/result path env vars
python -m app.services.attempt_writer --input routea-attempt-input.json --route route_a --out "$env:BINARYREPAIR_RESULT_PATH"
```

or wrap it as `BINARYREPAIR_ATTEMPT_CMD`.

## Acceptance

After both routes have attempt bundles, `python -m app.services.worker --data-dir var --once`
calls `evaluate_run`; the run becomes `finished` with a verdict. Then:

```powershell
python tools/p2_acceptance.py --worker-command "<python> -m app.services.worker --data-dir <abs> --once"
```

must pass (snapshot obligations + verdict consistent; GUI renders the same value).
