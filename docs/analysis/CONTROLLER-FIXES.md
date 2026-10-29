# Controller Evidence Endpoint Fixes (DEFECT A and DEFECT B)

> **Later status (verified at `986a49f`; later commits are documentation-only):** this record was measured before the member-2
> GUI merge. Its 197/195 full-suite total is superseded by the current
> 238/229 result, and the "GUI HTTP-backend mode does not exist" gap noted in
> §5.2 was closed by the member-2 merge (`381e4ef`; live P0 17/17). The DEFECT A/B
> fixes themselves are present and independently verified in
> `docs/analysis/VERIFICATION.md`.

Measured record for task-6 on branch `integration/consolidation-2026-10-29`
(worktree `D:\BinaryRepair_Project`, not committed by this workstream).
Author: controller-fixer. All statements below are measured on this host unless
explicitly marked **not_run**.

Environment: Python 3.14.6 on Windows, pytest 9.1.1, FastAPI 0.141.1,
Starlette TestClient (httpx 0.28.1). No uploaded or repaired binary was built,
executed, or loaded anywhere in this work: the evidence paths only read SQLite
rows and JSON result bundles that `scripts/demo_e2e.py` labels as synthetic.

Files changed by this workstream:

| File | Change |
|---|---|
| `app/controller_api.py` | DEFECT A + DEFECT B fixes (placeholder removed, persisted rows served, honest verification vocabulary) |
| `tests/test_evidence_endpoint.py` | **new** file, 8 tests for the honest evidence contract |
| `tests/integration/test_controller_api.py` | one stale test updated (Lead-approved scope grant; placeholder assertions replaced, no test removed or relaxed) |
| `docs/analysis/CONTROLLER-FIXES.md` | this document |

`app/domain/acceptance.py` and `app/domain/outcomes.py` were **not edited** by
this workstream; the acceptance decision path is unchanged.

## 1. Defect A: static placeholder served as evidence

Before the fix, `app/controller_api.py` had a module-level function
`_obligations()` that returned a hard-coded dict: for both routes, `V0` was
always `{"result": "passed"}` and `V1`-`V5` were always
`{"result": "not_run"}`. It was returned unconditionally by:

- `GET /api/attempts/{attempt_id}/evidence`
- `GET /api/jobs/{job_id}/obligations`

This is exactly the "missing is not passing" violation in `AGENTS.md`: the
endpoint served `passed` without reading the `obligations` table. The real
per-attempt rows already existed (`app.services.jobs.list_obligations`) and the
job snapshot already used them; only these two endpoints were fake.

Measured before payload, attempt in a **queued** run with **no persisted
obligation rows at all** (abridged; capture:
`_scratch/controller_fixer/before_payloads.txt`):

```json
{
  "attempt_id": "1082fb55190b41cab59ef67e993b0c18",
  "outcome": null,
  "obligations": {
    "A": [
      {"id": "V0", "kind": "Identity and preconditions", "result": "passed",
       "scope": "controller job store",
       "reason": "Job record and original hash verified."},
      {"id": "V1", "kind": "Structure and placement", "result": "not_run", "...": "..."},
      {"id": "V2", "kind": "Interface and compatibility", "result": "not_run", "...": "..."},
      {"id": "V3", "kind": "Concrete behavior", "result": "not_run", "...": "..."},
      {"id": "V4", "kind": "Bounded symbolic security", "result": "not_run", "...": "..."},
      {"id": "V5", "kind": "Reproducibility", "result": "not_run", "...": "..."}
    ],
    "B": [ "... the same static V0 passed rows ..." ]
  }
}
```

Two things are wrong there: the attempt never ran a check, and the row is not
even in the database. The same static dict was also returned for a route whose
attempt *did* have persisted rows, so the endpoint's payload did not match the
`obligations` table (the persisted rows use `kind`/`required`/`result`/
`evidence_artifact_id`/`detail`, not `id`/`description`/`scope`/`reason`).

## 2. Fix A: serve persisted rows, never invent a `passed`

`app/controller_api.py` changes:

- `_obligations()` is deleted. Nothing in the module can return a hard-coded
  check result any more.
- `GET /api/attempts/{attempt_id}/evidence` loads
  `jobs.list_obligations(attempt.id, data_dir=...)` and serves those rows
  verbatim under the attempt's own route group, plus a machine-readable flag:

  ```json
  "evidence": "persisted" | "not_persisted"
  ```

- `GET /api/jobs/{job_id}/obligations` returns the persisted rows of the
  **latest attempt per route** of the latest run (it selects the highest
  `sequence` for each route). With no run or no persisted rows it returns
  `{"A": [], "B": []}`.
- `GET /api/jobs/{job_id}` also carries `routes[A|B]["evidence"]` so a snapshot
  consumer can tell "no rows persisted" from "rows persisted".

Measured after payload, same queued attempt (capture:
`_scratch/controller_fixer/after_payloads.txt`):

```json
{
  "attempt_id": "2bc71c8ed9a64e2fb8cdbc576fb86692",
  "outcome": null,
  "evidence": "not_persisted",
  "obligations": {"A": [], "B": []}
}
```

Measured after payload, attempt whose worker persisted V0 `passed` and V1-V5
`not_run` (abridged; the rows are byte-for-byte the rows read directly from
SQLite):

```json
{
  "attempt_id": "821911ad717c4a3f9da4398916d6e660",
  "evidence": "persisted",
  "obligations": {
    "A": [
      {"kind": "behaviour", "required": true, "result": "not_run",
       "evidence_artifact_id": null, "detail": "SYNTHETIC: ... no binary ran."},
      {"kind": "identity", "required": true, "result": "passed",
       "evidence_artifact_id": "df00c913118e4c8bbb273520a7163f2f", "detail": "SYNTHETIC: ..."},
      {"kind": "interface", "required": true, "result": "not_run", "...": "..."},
      {"kind": "reproducibility", "required": true, "result": "not_run", "...": "..."},
      {"kind": "structure", "required": true, "result": "not_run", "...": "..."},
      {"kind": "symbolic", "required": true, "result": "not_run", "...": "..."}
    ],
    "B": []
  }
}
```

Backward compatibility decisions:

- The historical route-keyed shape (`obligations` is a mapping with keys `A`
  and `B`) is kept, because `scripts/demo_e2e.py` iterates
  `evidence["obligations"].values()`. For a single-attempt endpoint only the
  attempt's own group is populated; the other group is `[]`, not a placeholder.
- `GET /api/jobs/{job_id}/obligations` keeps its top-level key set exactly
  `{"A", "B"}`: the demo asserts `set(payload) == {"A", "B"}`, so a top-level
  flag key was rejected as a breaking change. Emptiness of both groups
  (`{"A": [], "B": []}`) is the documented machine-readable "nothing
  persisted" signal for that endpoint; the richer `evidence` flag exists on the
  per-attempt endpoint and in the job snapshot.
- All other existing fields are unchanged; new keys are additive.

## 3. Defect B: `verification: "unknown"` for mixed results

Before the fix, `_snapshot()` classified a route's persisted obligation results
with a set comparison that fell through to `"unknown"` whenever the results were
mixed, e.g. `{passed, not_run}` (V0 passed, V1-V5 not_run - the normal state of
the synthetic demo). `"unknown"` is not the acceptance engine's vocabulary and is
less precise than the engine's `inconclusive`.

The API route `verification` field is display vocabulary only; it is not an
acceptance decision. The acceptance decision stays in
`app/domain/acceptance.py` and is persisted in `attempts`/`runs`; the snapshot's
`outcome` field is copied from those persisted rows, not recomputed here.

New mapping in `app/controller_api.py::_verification_label`:

| Persisted results for the route | `verification` label |
|---|---|
| all `passed` | `passed` |
| all `not_run` | `not_run` |
| any `failed` | `failed` (a definite failure outranks missing evidence) |
| anything else (mixed `passed`/`not_run`, or `unknown`/`timed_out`) | `inconclusive` |
| no rows persisted | `not_run` + `evidence: "not_persisted"` |

Measured before/after (same synthetic mixed-results run through the real
worker, `GET /api/jobs/{job_id}`):

```text
before: "verification": "unknown",      "outcome": "inconclusive"
after:  "verification": "inconclusive", "outcome": "inconclusive"
```

A failed control (`V3 failed`, rest `not_run`) still renders
`"verification": "failed"` / `"outcome": "rejected"`, unchanged, which is why the
demo's second scenario output is unchanged apart from the honest label.

## 4. Tests

### 4.1 New file: `tests/test_evidence_endpoint.py` (8 tests)

The file drives the real `app.controller_api:app` with `TestClient` and seeds
state through the real service layer (`app.services.worker.run_once`,
`app.services.jobs`, `obligations.persist_obligations`). Bundles are labelled
SYNTHETIC in JSON; no binary is executed.

1. `test_evidence_serves_persisted_rows_verbatim` - for both attempts of a
   finished run, the evidence payload equals the rows read from SQLite
   (`jobs.list_obligations`), own route group populated, other group empty.
2. `test_evidence_is_empty_when_nothing_was_persisted` - queued attempt:
   `evidence == "not_persisted"`, `{"A": [], "B": []}`, no `passed` anywhere;
   same for the job-level endpoint and the snapshot.
3. `test_persisted_not_run_identity_is_not_reported_as_passed` - a persisted
   `V0 = not_run` is reported as `not_run`; the API does not upgrade it.
4. `test_mixed_results_use_inconclusive_not_unknown` - mixed results render
   `verification == "inconclusive"`, never `"unknown"`, never `"passed"`.
5. `test_definite_failure_outranks_missing_evidence` - `failed` row renders
   `failed` / `rejected`.
6. `test_job_obligations_reflect_latest_attempt_rows_per_route` - a second run's
   attempts replace the first run's rows in the job-level endpoint; stale rows
   do not leak.
7. `test_unknown_attempt_evidence_returns_404`.
8. `test_unknown_job_obligations_returns_404`.

### 4.2 Updated stale test in `tests/integration/test_controller_api.py`

`test_obligations_and_artifacts` was written against the removed placeholder and
asserted that a brand-new draft job (which has no attempts and no persisted
rows) receives a fake `V0 passed`. The Lead approved a scope grant to edit only
those assertions; no test was deleted, skipped, or xfailed, and every other
assertion in the file is untouched.

Old assertions (removed):

```python
assert data["A"][0]["id"] == "V0"
assert data["A"][0]["result"] == "passed"
assert data["A"][1]["result"] == "not_run"
```

New assertions (honest contract):

```python
# DEFECT-A fix, not a relaxation: the controller serves only persisted
# obligation rows, so a job with no attempts gets empty groups and must never
# invent a V0 "passed" placeholder.
assert data == {"A": [], "B": []}
assert "passed" not in obligations.text
assert not CJK.search(obligations.text)

# The same holds once attempts exist but the worker has persisted no rows.
_approve_current(client, job_id)
started = client.post(f"/api/jobs/{job_id}/start")
assert started.status_code == 202
queued = client.get(f"/api/jobs/{job_id}/obligations")
assert queued.status_code == 200
assert queued.json() == {"A": [], "B": []}
assert "passed" not in queued.text
```

Why this is not test weakening: the old assertions demanded fake evidence (a
`passed` with no database row and no checked property). The new assertions
demand the opposite and are stricter - they check the full group is empty and
that no `passed` substring appears, for both a draft job and a job whose
attempts exist but have no persisted rows. The "persisted rows verbatim" half of
the contract is asserted in `tests/test_evidence_endpoint.py` (items 1 and 6),
which runs in the same command.

### 4.3 Measured test counts

All runs from the repository root on this host.

Command A - combined run with the measurement helper (the target run):

```powershell
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch/controller_fixer/pytest_report_combined2.json"
$env:RT_TMP_ROOT="_scratch/controller_fixer/pytest_tmp_shim_combined2"
python -m pytest tests/test_evidence_endpoint.py tests/integration/test_controller_api.py `
  -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
```

Observed **before** updating the stale integration assertions:
`collected=19 passed=18 failed=1 collection_errors=0 pytest_exitstatus=1`
(the one failure was `test_obligations_and_artifacts`, `IndexError` at
`data["A"][0]` - the removed placeholder).
Observed **after**: `collected=19 passed=19 failed=0 collection_errors=0
pytest_exitstatus=0`, console `...................  [100%]`.

Command B - plain pytest with the pre-created basetemp (reported honestly):

```powershell
New-Item -ItemType Directory -Force -Path pytest_tmp_cf3 | Out-Null
python -m pytest tests/test_evidence_endpoint.py tests/integration/test_controller_api.py `
  --basetemp=pytest_tmp_cf3 -p no:cacheprovider -q
```

Observed: `EEEEEEEEEEEEEEEEEEE  [100%]`, exit code **1**. All 19 items error
during setup because `tmp_path` cannot create its directory once the sandbox
makes the pre-created basetemp unreadable; pytest then aborts in
`_pytest.tmpdir.cleanup_dead_symlinks` with
`PermissionError: [WinError 5] ... pytest_tmp_cf3`. Listing `pytest_tmp_cf3`
from the same shell afterwards also returns access denied - the known
Windows/DSH sandbox defect documented in `docs/analysis/RUNTIME-VERIFICATION.md`
section 6.2, not a test result. No assertion is reached in that run, so no
failure is hidden.

Command C - new file alone with the helper:
`collected=8 passed=8, collection_errors=0`, exit 0.

Command D - full suite with the helper (regression check):

```powershell
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch/controller_fixer/pytest_report_full.json"
$env:RT_TMP_ROOT="_scratch/controller_fixer/pytest_tmp_shim_full"
python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
```

Observed: `collected=197 passed=195 skipped=2 collection_errors=5
pytest_exitstatus=1`. The two skips are the pre-existing fixture-dependent tests
in `tests/test_fixture_v3_manifest.py` (not touched here; a skip is not a pass).
The 5 collection errors are the known missing-dependency modules
(`capstone` x4, `elftools` x1); those 13 test functions remain **not_run**.
Compared with the pre-fix measurement in `docs/analysis/RUNTIME-VERIFICATION.md`
(`collected=189 passed=187 skipped=2 collection_errors=5`), the delta is exactly
the 8 added tests and there is no new failure.

### 4.4 Demo verification

`python scripts/demo_e2e.py` still exits **0** after the fix (before the fix the
same script exited 0 too). The only visible output change is the honest label:

```text
scenario honest-wiring: ... route_a verification=inconclusive   (was: unknown)
scenario failed-check-control: ... route_a verification=failed   (unchanged)
```

The evidence endpoint was then cross-checked against the demo's persisted rows
with `_scratch/controller_fixer/verify_demo_evidence.py --data-dir
_scratch/runtime_verification/e2e_20261029_044721`: 4/4 attempts and 2/2 jobs
PASS (`checked=6 failures=0`). Example rows: for the demo attempts
`10db8cdd48a442e2bec63a07d36e6ba9`, `74a3d1ff003e449c9a6af1f404929866`,
`4b6843ed9a1f4bb6b0df2beea804fed1`, `1c6502bc01084235b5e26945d50f5f77` the
`evidence` payload equals the SQLite `obligations` rows exactly, and the snapshot
labels are `inconclusive` (job `8368277e...`) and `failed` (job `5234cfe0...`).

## 5. Remaining gaps (reported, not silently changed)

1. **Approval-check asymmetry between `/api/jobs/{id}/start` and
   `/api/jobs/{id}/runs`** (audit section 8, item 5). `/start` re-validates the
   `meta.json` approval revision/hash against the persisted contract row;
   `/runs` only checks that a persisted contract row exists for the requested
   revision and does not re-check approval freshness itself. Both reject a
   never-approved job with 409 (measured in the demo), but `/runs` is the weaker
   check. This workstream did **not** change it: it is a security/contract
   semantics decision owned by the team, not an evidence-display fix. Suggested
   follow-up: have `/runs` call the same freshness validation helper as `/start`.
2. **GUI HTTP-backend mode does not exist in this worktree** (audit section 8,
   item 2): `app/main.py` is the demo-only app backed by `app/demo.py`, so no
   browser GUI consumes these endpoints yet. The payload shape was therefore
   kept conservative (route-keyed `obligations`, additive `evidence` key). The
   member-2 GUI adapter merge (task-5) will be the first real GUI consumer and
   should be tested against this contract.
3. **No top-level `evidence` flag on `GET /api/jobs/{id}/obligations`.** Adding
   one breaks the existing demo assertion `set(payload) == {"A", "B"}`; the
   documented signal there is "both groups are empty". A future versioned API
   revision could carry the flag explicitly.
4. **`verification` is a derived display summary, not a decision.** It is
   computed from persisted rows only and never feeds `app/domain/acceptance.py`.
   Any result value not covered by the mapping falls back to `inconclusive`,
   which is the conservative/honest display.
5. **Real V1-V5 evidence still does not exist.** These endpoints are now honest
   but they can only ever show `not_run` until the guest executor writes real
   obligation rows: guest execution, Route A/B candidate generation, V4 symbolic
   verification and V5 independent replay all remain **not_run** on this host.
6. **Five test modules remain uncollectable** on this host (missing
   `capstone`/`pyelftools`): `test_routea_cave.py`, `test_routea_manifest.py`,
   `test_routea_worker.py`, `test_routeb_attempt_writer.py`,
   `test_routeb_executor.py`. They are **not_run**, never passed.
7. `_route_key()` maps any route that is not `route_a` to `B`; the database
   `CHECK` constraint currently makes that unreachable, but a future route name
   would need an explicit mapping.

## 6. Reproduction commands (exact)

```powershell
# 1. before/after payload capture (real controller, labelled synthetic bundles)
python _scratch/controller_fixer/probe_payloads.py --label before
python _scratch/controller_fixer/probe_payloads.py --label after

# 2. new + updated tests, measurement helper
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch/controller_fixer/pytest_report_combined2.json"
$env:RT_TMP_ROOT="_scratch/controller_fixer/pytest_tmp_shim_combined2"
python -m pytest tests/test_evidence_endpoint.py tests/integration/test_controller_api.py `
  -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors

# 3. plain pytest, honest sandbox result (errors, not passes)
New-Item -ItemType Directory -Force -Path pytest_tmp_cf3 | Out-Null
python -m pytest tests/test_evidence_endpoint.py tests/integration/test_controller_api.py `
  --basetemp=pytest_tmp_cf3 -p no:cacheprovider -q

# 4. full suite, measurement helper
$env:RT_REPORT_PATH="_scratch/controller_fixer/pytest_report_full.json"
$env:RT_TMP_ROOT="_scratch/controller_fixer/pytest_tmp_shim_full"
python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors

# 5. end-to-end demo (exit code must be 0) and its evidence cross-check
python scripts/demo_e2e.py
python _scratch/controller_fixer/verify_demo_evidence.py `
  --data-dir _scratch/runtime_verification/e2e_20261029_044721
```

Raw console transcripts and JSON reports are kept under
`_scratch/controller_fixer/` (scratch runtime artifacts, not source):
`before_payloads.txt`, `after_payloads.txt`, `pytest_new_plugin.txt`,
`pytest_combined.txt`, `pytest_combined2.txt`, `pytest_combined_plain_out.txt`,
`pytest_combined_plain_err.txt`, `pytest_full.txt`,
`pytest_report_new.json`, `pytest_report_combined2.json`,
`pytest_report_full.json`, `demo_after_fix.txt`,
`verify_demo_evidence.txt`.
