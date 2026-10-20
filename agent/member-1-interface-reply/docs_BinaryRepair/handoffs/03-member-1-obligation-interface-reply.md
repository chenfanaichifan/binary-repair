# Member 1 → Member 4: §4.1 Answers (4 Items)

**From:** Member 1 (job controller / identity & state slice)
**To:** Member 4 (verification slice)
**Date:** 2026-10-18
**Interface:** Accepted as-is — `Obligation` + `decide_attempt_outcome` + `Verdict`.
**Test status:** Integration tests still skipped — `app.services.jobs` is not on any branch yet; the real pass count is pending.

## 4.1.1 Obligation fields

**Agree — the four fields are sufficient.** Gate number, evidence id, and timestamps go in the database row or in `detail`; they will not be added to the dataclass.

## 4.1.2 Call shape

**Agree — direct call.** I will call the keyword-only `decide_attempt_outcome` directly. If I add a thin adapter in the jobs service, it will only map a job record to keyword arguments; it will contain no decision logic and no second `if all_passed:`.

## 4.1.3 `reviewed_scope_sha256`

**Store it in both rows; the `run` row wins for the decision.**

- The `contract` row holds the hash written at review/freeze time — the source.
- Run creation copies it into `run.reviewed_scope_sha256` and asserts equality in the same transaction.
- `decide_attempt_outcome` reads only the run row. The contract row is not read at decision time.
- A later contract re-review gets a new hash; existing runs keep their pinned value, so an old verdict is never rewritten.

## 4.1.4 `kind` list

**Agree with the V0–V5 list:** `identity` / `structure` / `interface` / `behaviour` / `symbolic` / `reproducibility`.

## Other

- Missing evidence → `NOT_RUN`, never dropped; an empty list → `inconclusive` is intentional.
- `Verdict` persisted verbatim: `outcome` / `reason` / `failing_obligation` / `detail`.
- Whole run via `decide_run_outcome(route_a=..., route_b=...)`; both routes must be `success_within_scope`.
- Real `candidate_sha256` / `expected_sha256`; no `None` shortcut.
- Question: is `reviewed_scope_sha256` opaque to the engine, or must it be computed from a canonical scope serialization? If the latter, send the format.

## 5. Test status

- Status: **pending** — not run, not passed.
- `app.services.jobs` is not on any branch yet, so the jobs-related integration tests remain skipped.
- I am not claiming a pass count for them. The last recorded unit-test result is 29 passed; the integration result is pending.
- Next step: push `app.services.jobs` with the §4.2 entry points, then ping Member 4 to rerun `python -m pytest tests/integration -q -p no:cacheprovider -rs` and report the real pass count. A skip is not a pass.
