# behavior-comparison v1 — M5 decision

Date: 2026-11-08  
Status: proposed for v1.1.2, not part of v1.1.1.

## Decision

Upgrade `GET /api/jobs/{id}/comparison` to a field-level schema **for the
artifact payload only**. The endpoint status remains additive:

```text
not_provided | available | invalid
```

`invalid` must render as unavailable; it is never a pass.

## Schema

```json
{
  "schema_version": 1,
  "original_sha256": "<64 lowercase hex>",
  "candidate_sha256": "<64 lowercase hex>",
  "scope": "behavior_only",
  "cases": [
    {
      "id": "case-1",
      "kind": "known_good",
      "input_sha256": "<64 hex or null>",
      "original": {
        "returncode": 0,
        "stdout_sha256": "<64 hex>",
        "stderr_sha256": "<64 hex>",
        "timed_out": false
      },
      "candidate": {
        "returncode": 0,
        "stdout_sha256": "<64 hex>",
        "stderr_sha256": "<64 hex>",
        "timed_out": false
      },
      "verdict": "same",
      "detail": ""
    }
  ],
  "summary": {
    "total": 1,
    "same": 1,
    "different": 0,
    "not_run": 0,
    "unknown": 0
  },
  "not_claimed": [
    "not a repair verdict",
    "same is not acceptance evidence",
    "different is not a failure verdict by itself"
  ]
}
```

## Field rules

```text
schema_version       required, exactly 1
original_sha256      required, 64 hex, must match job original
candidate_sha256     required, 64 hex, must match artifact candidate
scope                required, exactly "behavior_only"
cases                required, 1..N
case.id              required non-empty string, unique
case.kind            required: known_good | known_bad | valid | invalid | unknown
case.input_sha256    required, 64 hex or null
case.original        required object
case.candidate       required object
returncode           required int or null
stdout_sha256        required 64 hex or null
stderr_sha256        required 64 hex or null
timed_out            required bool
case.verdict         required: same | different | not_run | unknown
case.detail          required string, may be empty
summary              required; counts must equal cases
summary.total        == len(cases)
summary.same + different + not_run + unknown == total
not_claimed          required non-empty list
```

## Missing / invalid semantics

```text
artifact absent
  -> status=not_provided, comparison=null, UI: unavailable

artifact bytes missing / hash mismatch
  -> status=invalid, comparison=null, UI: unavailable

invalid JSON / schema violation / count mismatch / duplicate case id
  -> status=invalid, comparison=null, UI: unavailable

missing required case field
  -> invalid whole artifact; do not infer values

case.verdict=not_run
  -> original/candidate may have null outputs; still not a pass

case.verdict=same or different
  -> both outputs must be complete; hashes required
  -> otherwise invalid

different
  -> behavioral divergence only; not a failure verdict

same
  -> behavioral equality only; not acceptance evidence
```

## UI rules

```text
status=not_provided -> "未提供"
status=invalid      -> "不可用"
status=available    -> show per-case counts, never "通过"
same/different/not_run/unknown are displayed verbatim
no field may be rendered as "修复成功"
```

## Compatibility

`v1.1.1` keeps the old parsed-JSON behavior. M2 may implement the UI against
this draft now; M5 will add validation and M1 will expose `invalid` before
v1.1.2.
