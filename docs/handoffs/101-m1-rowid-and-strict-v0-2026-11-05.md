# rowid ordering in canonical, a strict V0 binding, and the assistant row

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Head before this pass: `2c33c7c`
- Suite: `367 passed / 3 skipped / 1 failed` (host has no `readelf`/`objdump`)

## 1. `get_plan` ordering is in canonical

`d56ef1b` arrived through `65aeb01`; `canonical/m1-m5-integration` reads

```sql
SELECT * FROM assistant_plans WHERE job_id = ? ORDER BY rowid DESC LIMIT 1
```

and `test_get_plan_returns_latest_same_second` saves two plans inside one second
and requires the second one. The earlier `ORDER BY created_at DESC, id DESC`
sorted on a second-resolution timestamp with a random hex id, so which plan won
was a coin flip.

## 2. V0 keeps the candidate hash and no longer falls back

The merge kept `ids_by_name` plus the `candidate_sha256` comparison rather than
`ids[0]`. This pass closed the remaining hole:

```
chosen = ids[0]
if gate == "V0":
    matches = [id for name, id in ids_by_name.items()
               if sha256(file(name)) == manifest["candidate_sha256"]]
    if not matches:
        raise IngestError("gate V0 evidence does not contain the declared candidate ...")
    chosen = matches[0]
```

Before this, a V0 gate whose file list did not contain the candidate silently
bound itself to the first file. That is exactly the failure the hash check exists
to prevent, and it would have produced a `passed` V0 pointing at a decoy.

`test_v0_without_the_candidate_bytes_is_rejected` covers it.

The test fixture `_bundle()` used to declare `candidate_sha256 = "a" * 64` while
writing different bytes. That placeholder was only tolerated because the old code
fell back to `ids[0]`; it now takes the real digest, and four existing tests
depended on the fallback implicitly.

## 3. T8.1: the plan only appends a row

`test_plan_does_not_touch_a_running_job` sets up a real contract, approval and
run, then generates a plan and asserts:

| Table | Expectation |
|---|---|
| `assistant_plans` | +1 |
| `contracts` | unchanged |
| `runs` | unchanged |
| `attempts` | unchanged |
| `obligations` | unchanged |
| snapshot `phase` / `contract` / `run` / `verdict` | unchanged |

The existing draft-state test stays; this one proves the same isolation while a
run is queued, which is when a "helpful" plan would be most likely to write
something.

## 4. Status boundaries kept

- T6.0 baseline work continues; the guards listed in record 100 remain the
  acceptance gate for a re-cut.
- T8.2 is M5's; this branch does not change the planner seam.
- T8.3 is still blocked and is not recorded anywhere as complete.

## Open

- Push needs a token; `delivery/` is tracked locally but not yet fetched by
  anyone else.
- The `readelf`/`objdump` failure is environmental.
