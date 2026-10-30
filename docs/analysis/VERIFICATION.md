# Independent verification of the integrated BinaryRepair tree

**Verifier:** verifier (task-4, independent verification role)
**Date:** 2026-10-29 (Asia/Hong_Kong)
**Branch:** `integration/consolidation-2026-10-29`, HEAD `7b294ba`
**History verified:** `cc29158` (consolidation) + `381e4ef` (member-2 GUI merge) + `7b294ba` (merge of `merge/m2-main`)
**Follow-up re-verification:** HEAD `986a49f` (parent `7b294ba`) — see §7. The initial measurements below are from `7b294ba`; §1 items 6/7/16 and §6 carry the current `986a49f` counts.
**Environment:** Windows 11, Python 3.14.6, pytest 9.1.1, FastAPI 0.141.1, Starlette TestClient
**Write scope:** this file only (`docs/analysis/VERIFICATION.md`); no product code, test, or acceptance rule was edited.
**Scratch evidence:** commands log, JSON reports and helper scripts under `_scratch/verifier/` (git-ignored).

This document records what *I* re-ran and observed, independently of the reports written by
the other workstreams. Nothing below is copied from their output without re-measurement.
Every item is classified **PASS**, **FAIL**, or **NOT RUN**; anything that could not be executed
on this host is **NOT RUN**, never PASS.

---

## 1. Verdict table

| # | Item | Verdict | Evidence (measured by me) |
|---|---|---|---|
| 1 | Branch/HEAD/history `cc29158`, `381e4ef`, `7b294ba`; `origin/main` (`4107836`) is an ancestor | **PASS** | `git rev-parse HEAD` = `7b294ba…`; `git log` shows all three; `git merge-base --is-ancestor origin/main HEAD` exit 0 |
| 2 | Working tree has no uncommitted product-code changes | **PASS** | `git status --porcelain` prints nothing (only two sandbox `Permission denied` warnings for unreadable `.audit-main/.pt-int/`, `.pytest-tmp/`); `.write-probe.tmp` is ignored |
| 3 | No file from `origin/main` deleted or lost in `app tests routea routeb binaryrepair_ai schemas fixtures` | **PASS** | `git diff --name-status origin/main -- <paths>` = 45 entries, **0 deletions**; `git ls-tree` comparison lists no main file missing at HEAD; full `git diff --name-status origin/main -- .` also has no `D` entry |
| 4 | No committed/pushed secrets (`.env`, API keys, tokens) | **PASS** | `git ls-files` has no `.env`/credential/key file; HEAD-tree grep for `sk-…`/`BEGIN … PRIVATE KEY` finds nothing; full `git diff origin/main -- .` scan for key/token patterns finds nothing. `.env.example` is a placeholder only, `var/` is untracked (0 tracked files) |
| 5 | Acceptance unit suite: 29 passed | **PASS** | `python -m pytest tests/unit/test_acceptance.py -p pytest_rt_report -p no:cacheprovider -q` → `collected=29 passed=29` exit 0; plain run with pre-created `--basetemp` also 29 passed exit 0 |
| 6 | Full suite measured state: **238 collected / 229 passed / 2 skipped / 7 errors / 5 uncollectable** (at follow-up HEAD `986a49f`; the initial `7b294ba` measurement was 236/227 — delta = the 2 new attempt-writer identity tests, see §7) | **PASS** | helper run → `collected=238 passed=229 error=7 skipped=2 collection_errors=5 pytest_exitstatus=1`; the 7 errors are exactly `tests/e2e/test_gui_journey.py`; the 2 skips are the V3-manifest tests; 5 collection errors are `capstone`×3 / `elftools`×2 and contain **13** test functions (verified by counting `def test_`) |
| 7 | The Windows `tmp_path` failure is reported honestly, not hidden | **PASS** | plain `python -m pytest tests/ --basetemp=<pre-created> -p no:cacheprovider -q` → `Interrupted: 5 errors during collection` exit 2, 0 tests (re-measured at `986a49f`); with `--continue-on-collection-errors` (no helper) the progress line shows **238 markers: 167 passed / 69 err / 2 skip / 0 failed**. Of those 69 errors, 62 are `PermissionError [WinError 5]` at `tmp_path` fixture setup and the other 7 are the known browser-e2e environment errors; pytest also still crashes in `_pytest.tmpdir.cleanup_dead_symlinks` at session finish (no summary, exit 1). No `F` marker anywhere. (Initial `7b294ba`: 236 markers, 167/67/2.) |
| 8 | Tests not weakened; no skip/xfail hides a failure; no second success rule | **PASS** | see §3. The only changed existing test (`tests/integration/test_controller_api.py::test_obligations_and_artifacts`) replaces the old *placeholder-asserting* lines with stricter "empty groups, no `passed`" assertions; the other modified tests (M2 merge) only add session/CSRF plumbing and more assertions; repository-wide grep finds **no** `xfail`; the two skips are real V3 environment skips; the acceptance decision exists only in `app/domain/acceptance.py` (byte-identical to the member-4 branch), templates/`app/status.py` only render persisted verdicts |
| 9 | Demo `python scripts/demo_e2e.py` exits 0 with the expected printed evidence | **PASS** | exit 0; fixture sha256 `aa428157…8393`; scope sha256 `24bfe568…4e37`; scenario 1 `inconclusive / required_check_not_run`, scenario 2 `rejected / regression_failed`; only obligation reported `passed` is V0 `identity`, supplied by the clearly labelled synthetic bundle; every V1–V5 absent check prints `not_run` (or the deliberate synthetic `failed` control); 12 persisted obligation rows per scenario; synthetic label present in every attempt bundle and in the printed "REAL vs SYNTHETIC" section |
| 10 | Fixture bytes and contract scope hash match the documented values | **PASS** | independent recomputation (own canonical JSON implementation) → contract `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37`; fixture ELF 26,792 B `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393`; both equal the demo/README values |
| 11 | Controller evidence endpoints serve **persisted** obligation rows; no static `V0 passed`; empty payload contains no `passed` | **PASS** | independent TestClient script against the demo data dir: `/api/jobs/{id}/obligations` returns the 6 SQLite rows per route for both scenarios, byte-equal to the `obligations` table; `/api/attempts/{id}/evidence` returns `evidence: persisted` with the same rows (other route group `[]`); a fresh job and a queued-but-unwritten attempt return `{"A": [], "B": []}` / `not_persisted` with the substring `passed` absent; `_obligations()` no longer exists in `app/controller_api.py` |
| 12 | `import app.main` works | **PASS** | `python -c "import app.main"` exit 0 (18 routes) |
| 13 | App boots under uvicorn on a free port (not 8123); `/healthz` and the three screens render | **PASS** | GUI `app.main:app` on `127.0.0.1:8802` (http backend, controller on `127.0.0.1:8801`): `/healthz` 200 `{"ok":true,"backend":"http",…}`; authenticated `/jobs/new`, `/jobs/{id}`, `/jobs/{id}/evidence` all 200, no demo banner, token not echoed; unknown job 404; unauthenticated requests 401. Servers stopped and ports confirmed released (no LISTENING sockets) |
| 14 | M2 merge claim: `tools/p0_acceptance.py` 17/17 against live GUI `http` mode + canonical controller | **PASS** | live run → 17/17 `PASS`, `P0 ACCEPTANCE PASSED`, exit 0 (`job=7497c7f8…`, phase queued→cancelled, cancelled page shows the Chinese "cancelled" label and is not labelled success) |
| 15 | README claim: `tools/p2_acceptance.py` exits `2 BLOCKED` while no result bundle reaches the worker | **PASS** | live run → `BLOCKED  pipeline did not finish: phase='queued'`, exit 2 |
| 16 | README's measured full-suite numbers (238/229/2/7/5 at follow-up HEAD `986a49f`) | **PASS** | reproduced exactly (§1 item 6; §7 re-measured the same command at `986a49f`) |
| 17 | README attribution: "These are the only verified test numbers; they come from `docs/analysis/RUNTIME-VERIFICATION.md` and `docs/analysis/CONTROLLER-FIXES.md`" | **FAIL at `7b294ba`; FIXED in `986a49f`** | neither document contains 236/227. They report `189/187/2/5` and `197/195/2/5` respectively (details §4, D1). The README numbers were correct, the cited provenance false. **Follow-up:** the README now points at this file (§7) |
| 18 | `docs/analysis/RUNTIME-VERIFICATION.md`: 189/187 attributed to commit `4107836`, and current-defect claims | **FAIL at `7b294ba`; FIXED in `986a49f`** | a clean archive of `origin/main` `4107836` collects **160** tests (158 passed / 2 skipped with the helper; 117/2/41 plain). The 189 figure includes 29 acceptance tests that were only *staged* at measurement time; the document never said so. Its §7/§8 claims that GUI `http` mode and the persisted-evidence endpoint do not exist were false at HEAD (details §4, D2/D3). **Follow-up:** a dated pre-merge note was added at the top of the document (§7) |
| 19 | `docs/analysis/CONTROLLER-FIXES.md`: endpoint fix content and its own measured counts | **PASS for the fix / FAIL for HEAD-current wording — FIXED in `986a49f`** | the fix is real and verified (§1 item 11); its 19/19 combined run reproduces; but its §5.2 "GUI HTTP-backend mode does not exist in this worktree" and its 197/195 total were stale at HEAD (details §4, D4). **Follow-up:** a dated note marks both superseded (§7) |
| 20 | `docs/analysis/M2-MERGE-REPORT.md` measured numbers | **PASS (as the merge-commit measurement)** | its 192-item subset at HEAD → `collected=192 passed=190 skipped=2` exit 0 (reproduced by excluding the three suites added after `381e4ef`); merge commit parents `036328d`+`4107836` confirmed; 17/17 P0, P2 `2 BLOCKED`, 7 e2e errors all confirmed |
| 21 | `docs/analysis/ROOT-CAUSE-ANALYSIS.md` verifiable facts | **PASS (historical facts) / stale for HEAD totals — FIXED in `986a49f`** | "0 commits 2026-10-23…10-28" confirmed (0); missing tools/modules confirmed; "clean main 160 executed / 117 passed / 2 skipped / 41 errored" reproduced exactly on an archive of `4107836`; its consolidated-tree totals (189/146/41) were historical (analysis window 12:34–12:55) and stale at HEAD (details §4, D6). **Follow-up:** a dated later-status note was added (§7) |
| 22 | `MEMORY.md` byte-identity claims (acceptance engine, `docs_BinaryRepair/` 41 files, `agent_docs/` copies) | **PASS** | `git diff member-4-verification -- app/domain/acceptance.py app/domain/outcomes.py tests/unit/test_acceptance.py` = 0 lines; `docs_BinaryRepair` = 41 files and 0-line diff vs `member-4-verification`; all four `agent_docs/*.md` SHA-256 equal their `agent/` counterparts |
| 23 | README fixture-manifest hash claims (`valid.json 17b2ee39…`, `invalid.json d493f370…`) and `.gitattributes` byte pinning | **PASS** | measured hashes match exactly; `.gitattributes` marks `fixtures/public/**/tests/*.json` as `-text`; the 6 passing `test_fixture_v3_manifest` tests confirm the manifest-set hash |
| 24 | README tag/layout claims (`docs_BinaryRepair/` 41 files, `agent/` frozen archive, tag `archive/2026-10-22/pre-cleanup`) | **PASS** | tag resolves (`e9091b0e…`); files/directories present; `agent/` untouched by this task |
| 25 | README quick start (`.venv` + `pip install`, `start.ps1` on 8123, stable session token in `var/session.token`) | **NOT RUN** | `pip` is unusable on this host and the reserved `8123` port must not be used; the app was instead booted with `BINARYREPAIR_SESSION_TOKEN` on a free port. Code inspection of `start.ps1` shows the described behaviour, but the launcher was not executed |
| 26 | README claim "`python -m pytest -q tests/e2e` … skips with a clear message when Edge is not installed" | **NOT RUN** | the skip path requires Edge to be absent; in this sandbox the 7 journeys fail at DevTools setup (reported honestly as errors, matching README's measured section). The skip branch was not exercised |
| 27 | Gate 3 approval record (`docs_BinaryRepair/handoffs/33-gate3-approved.md`, record hash `0b3b51e4…`) | **NOT RUN** | the handoff exists and states the approval; the canonical `docs/route-a/gate3-record.md`, the v2 evidence bundle and the raw guest evidence are not part of this tree (`delivery/` is local/ignored), so the gate evidence itself was not re-verified. README explicitly says it was not re-measured — that part is honest |
| 28 | Real repair, guest execution, Route A/B candidate generation, V1–V5 real checks, V4 symbolic, V5 replay, formal Gate 4/5/6 | **NOT RUN** | forbidden/unsupported on this host and not available; every document that touches these items in this tree labels them `not_run`/`NOT RUN`. No evidence of a repaired binary exists in the tree |
| 29 | Real DeepSeek provider call | **NOT RUN** | no API key used; not required for this verification and deliberately not attempted |
| 30 | `app/db/migrate.py` idempotency (claimed by `RUNTIME-VERIFICATION.md`) | **PASS** | two consecutive `python -m app.db.migrate --db _scratch/verifier/migrate_probe` runs both exit 0 with schema versions `[1, 2, 3]`; `schema_migrations` = `[(1,'base'),(2,'002_ai_tables'),(3,'003_acceptance_verdict')]` |

---

## 2. Exact commands and observed results

All commands ran from `D:\BinaryRepair_Project` unless stated. Full logs are under
`_scratch/verifier/`. The §2.1 numbers are the initial `7b294ba` run; §7 re-ran the same commands
at follow-up HEAD `986a49f` (full suite 238/229 — the delta is the 2 new attempt-writer tests).

### 2.1 Tests

```powershell
# 1) acceptance unit suite, measurement helper
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch\verifier\report_unit.json"
$env:RT_TMP_ROOT="_scratch\verifier\tmp_unit"
python -m pytest tests/unit/test_acceptance.py -p pytest_rt_report -p no:cacheprovider -q
# -> collected=29 passed=29 collection_errors=0 pytest_exitstatus=0   (exit 0)

# 2) full suite, measurement helper
$env:RT_REPORT_PATH="_scratch\verifier\report_full.json"
$env:RT_TMP_ROOT="_scratch\verifier\tmp_full"
python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
# -> collected=236 passed=227 error=7 skipped=2 collection_errors=5 pytest_exitstatus=1
#    7 errors = tests/e2e/test_gui_journey.py (7 journeys, Edge/DevTools cannot start in this sandbox)
#    2 skips  = tests/test_fixture_v3_manifest.py::{test_original_is_v0_..., test_repaired_candidate_...}
#    5 collection errors = test_routea_cave/test_routea_manifest/test_routea_worker (capstone),
#                          test_routeb_attempt_writer/test_routeb_executor (elftools); 13 functions

# follow-up HEAD 986a49f, same command:
# -> collected=238 passed=229 error=7 skipped=2 collection_errors=5 pytest_exitstatus=1  (see §7)

# 3) plain pytest with a pre-created basetemp (no helper): honest environment failure
python -m pytest tests/ --basetemp=_scratch\verifier\basetemp_plain4 -p no:cacheprovider -q
# -> "Interrupted: 5 errors during collection", exit 2, 0 tests run  (re-measured at 986a49f: same)

python -m pytest tests/ --basetemp=_scratch\verifier\basetemp_plain3 `
  -p no:cacheprovider -q --continue-on-collection-errors
# -> 236 progress markers: 167 passed, 67 error, 2 skip, 0 failed
#    (of the 67 errors: 60 PermissionError [WinError 5] inside pytest tmp_path setup,
#    7 the known browser-e2e environment errors); then a crash in
#    _pytest.tmpdir.cleanup_dead_symlinks at session finish (no summary line, exit 1)
# follow-up HEAD 986a49f, same command: 238 markers -> 167 passed / 69 error / 2 skip / 0 failed
```

Cross-checks used to attribute the numbers in the other documents (all run by me):

```powershell
# M2-MERGE-REPORT subset: exclude the suites added after 381e4ef
$env:PYTHONPATH="scripts"
python -m pytest tests/ --ignore=tests/e2e --ignore=tests/unit/test_acceptance.py `
  --ignore=tests/test_evidence_endpoint.py --ignore=tests/test_routea_cave.py `
  --ignore=tests/test_routea_manifest.py --ignore=tests/test_routea_worker.py `
  --ignore=tests/test_routeb_attempt_writer.py --ignore=tests/test_routeb_executor.py `
  -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
# -> collected=192 passed=190 skipped=2 collection_errors=0 pytest_exitstatus=0  (exit 0)

# CONTROLLER-FIXES combined run
python -m pytest tests/test_evidence_endpoint.py tests/integration/test_controller_api.py `
  -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
# -> collected=19 passed=19 collection_errors=0 pytest_exitstatus=0  (exit 0)

# clean origin/main 4107836 (git archive -> _scratch\verifier\main_archive, pytest.ini anchored)
# helper run:   collected=160 passed=158 skipped=2 collection_errors=5
# plain run:    160 executed -> 117 passed / 2 skipped / 41 errored / 0 failed
# clean member-4-verification 9c6e1f7: 40 collected -> 40 passed (+1 module-level
#   skipped module in junit accounting = the 41/40/1 figure in ROOT-CAUSE-ANALYSIS)
```

Note on the `pytest_rt_report` helper: it is a measurement-only plugin
(`scripts/pytest_rt_report.py`). It provides a per-test writable `tmp_path` and tolerates the
sandbox teardown error. It does not skip, reorder, xfail, or rewrite any test and it never
turns a failure into a pass: the plain runs above show the same tests either pass or fail with
`PermissionError`, never with an assertion failure. The additional passes (60 at `7b294ba`:
227 vs 167; 62 at `986a49f`: 229 vs 167) are exactly the tests whose only problem was the broken
temporary directory.

### 2.2 Demo

```powershell
python scripts/demo_e2e.py --data-dir _scratch\verifier\demo_run1
# -> exit 0; "DEMO OK"
# fixture ELF bytes: 26792
# fixture sha256: aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
# approve -> scope_sha256=24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
# scenario honest-wiring:       run outcome=inconclusive reason=required_check_not_run
#                               failing obligation=structure; verification=inconclusive
# scenario failed-check-control: run outcome=rejected    reason=regression_failed
#                               failing obligation=behaviour; verification=failed
# persisted: run phase=finished attempts=2 obligation_rows=12 (each scenario)
# stored original bytes sha256=aa428157... (equals fixture)
```

Independent reading of the produced bundles confirmed `"synthetic": true` and the
`SYNTHETIC result bundle written by scripts/demo_e2e.py …` label in all four attempt bundles.
The only `passed` value is V0 `identity`, which is the synthetic bundle's own V0 result and is
labelled as such; no V1–V5 absent check is reported `passed`, and the two acceptance outcomes
come from `app/domain/acceptance.py`.

### 2.3 Controller evidence endpoints (independent script)

`_scratch/verifier/check_endpoints.py` (TestClient, `BINARYREPAIR_DATA_DIR` = the demo data dir)
→ 63 assertions, `FAILS=0`:

* both demo scenarios: 6 persisted obligation rows per route, API rows equal the SQLite
  `obligations` rows for both attempts, `evidence: persisted`, other route group `[]`,
  synthetic label preserved in `detail`;
* a fresh job and a queued job with attempts but no worker run: `{"A": []}`, `{"B": []}`,
  `evidence: not_persisted`, `outcome: null`, and no `passed` substring in the payload;
* the old 2-row static placeholder shape is absent.

### 2.4 GUI / controller boot, three screens, P0 and P2

```powershell
# controller
$env:BINARYREPAIR_DATA_DIR="_scratch\verifier\controller_data"
python -m uvicorn app.controller_api:app --host 127.0.0.1 --port 8801   # background job
# GUI in http mode
$env:BINARYREPAIR_SESSION_TOKEN="verifier-session-token-abc123"
$env:BINARYREPAIR_BACKEND="http"
$env:BINARYREPAIR_API_BASE="http://127.0.0.1:8801"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8802             # background job
# /healthz 200 on both; three screens 200; session gate 401 unauthenticated; unknown job 404
python tools/p0_acceptance.py --gui http://127.0.0.1:8802 `
  --controller http://127.0.0.1:8801 --token verifier-session-token-abc123
# -> 17/17 PASS, "P0 ACCEPTANCE PASSED", exit 0
python tools/p2_acceptance.py --gui http://127.0.0.1:8802 `
  --controller http://127.0.0.1:8801 --token verifier-session-token-abc123 --timeout 5
# -> "BLOCKED  pipeline did not finish: phase='queued'", exit 2
```

Both servers were stopped afterwards. A first `job_kill` left the two uvicorn child processes
orphaned on the ports; I re-ran `netstat -ano`, identified the owning PIDs (17172, 8960),
stopped them, and confirmed there is no `LISTENING` socket on 8801/8802 afterwards. This is
recorded because it is a small operational trap for the next verifier (the background-job
wrapper is killed, the Python child is not).

No uploaded or repaired binary was executed at any point: the demo reads and hashes the
26,792-byte fixture; P0/P2 upload a 25-byte synthetic, non-executable payload
(`b"\x7fELF P0 acceptance sample"` / `b"\x7fELF P2 acceptance sample"`).

### 2.5 Git and secrets

```powershell
git status --porcelain=v1                 # empty (only sandbox warnings for unreadable dirs)
git rev-parse HEAD                        # 7b294baac0505883e6f030fcd4c9f059687f5776
git rev-parse cc29158 381e4ef             # cc291589…, 381e4ef1…
git merge-base --is-ancestor origin/main HEAD   # exit 0
git diff --name-status origin/main -- app tests routea routeb binaryrepair_ai schemas fixtures
# -> 45 file entries, statuses A/M only, 0 D; no main file missing
git diff --name-status origin/main -- .   # no D entries anywhere
git branch --show-current                 # integration/consolidation-2026-10-29
```

Secrets: no tracked `.env`/credential/key/private-key file; no key-shaped string in the
HEAD tree or in `git diff origin/main -- .`; `var/` has 0 tracked files; `.env.example`
contains only placeholders (`sk-your-key-here`).

---

## 3. Test-integrity audit (item 1 of the task)

* `tests/unit/test_acceptance.py` is a negative-first suite (26 test functions, one
  parametrised ×4 = 29 items). It asserts that required `not_run`/`unknown`/`timed_out` ⇒
  `inconclusive`, failures ⇒ `rejected`, empty/optional-only evidence ⇒ not success,
  and that both routes are required for run success. No skip/xfail in the file; no assertion
  was relaxed. It is byte-identical to `member-4-verification`.
* The acceptance engine `app/domain/acceptance.py` and `app/domain/outcomes.py` are
  byte-identical to the member-4 branch (0-line diff) — the consolidation did not change a
  decision rule.
* `tests/test_evidence_endpoint.py` (new, 8 tests) genuinely drives the real FastAPI app and
  seeds state through the real worker; it asserts persisted rows are returned verbatim, that a
  queued attempt is `not_persisted` with no `passed`, that mixed results render
  `inconclusive` (never `unknown`/`passed`), and that a definite `failed` row outranks missing
  evidence. All 8 pass.
* The Lead-approved change to `tests/integration/test_controller_api.py::test_obligations_and_artifacts`
  removes three lines that *demanded the bug* (`data["A"][0]["id"] == "V0"`,
  `data["A"][0]["result"] == "passed"`, `data["A"][1]["result"] == "not_run"`) and replaces them
  with stricter assertions: the whole payload must be `{"A": [], "B": []}`, the text must not
  contain `passed`, and the same must hold after a job is approved and started but the worker
  has persisted nothing. This is a strengthening, not a relaxation: the old lines asserted
  fabricated evidence that the fix removed; the persisted-rows-positive case is covered by the
  8 new evidence tests. Only that one hunk changed in the file.
* The two other modified test files (`tests/test_smoke.py`, `tests/test_language_policy.py`)
  were adapted to the session/CSRF gate by the M2 merge; the diff adds approvals/CSRF and extra
  assertions (landing page, pre-approval 409, no-demo-banner) and removes no assertion.
* Repo-wide search: no `pytest.mark.xfail`/`pytest.xfail`. Skips exist only in
  `tests/e2e/conftest.py` (Edge missing — not triggered here, journeys error instead),
  `tests/integration/test_identity_state.py` (`importorskip` — not triggered, module exists),
  and `tests/test_fixture_v3_manifest.py` (2 runtime/guest skips). None of them masks a failure
  in this environment: with the helper the only non-passes are the 7 e2e environment errors.
* Decision placement: the only code path that turns obligation results into an outcome is
  `app/domain/acceptance.py` (`decide_attempt_outcome`/`decide_run_outcome`); `app/status.py`
  only maps the persisted verdict for display; templates read controller values; the old static
  placeholder `controller_api._obligations()` is deleted.

---

## 4. Discrepancies found (expected vs observed)

Follow-up status: all nine items (D1-D9) were addressed in commit `986a49f`; the per-item
classification and evidence are in §7. The paragraphs below preserve the initial `7b294ba`
findings.

**D1 — README attributes its numbers to documents that do not contain them.**
Expected (README lines 175–176): "These are the only verified test numbers; they come from
`docs/analysis/RUNTIME-VERIFICATION.md` and `docs/analysis/CONTROLLER-FIXES.md`."
Observed: `RUNTIME-VERIFICATION.md` §6.3 → `collected=189 passed=187 skipped=2
collection_errors=5`; `CONTROLLER-FIXES.md` §4.3(D) → `collected=197 passed=195 skipped=2
collection_errors=5`; `M2-MERGE-REPORT.md` → 192/190/2. None mentions 236 or 227. The README
numbers themselves are correct at HEAD (I reproduced them). **Severity: medium** (misleading
provenance, not a wrong measurement).

**D2 — `RUNTIME-VERIFICATION.md` attributes 189/187 to commit `4107836`.**
Expected for a clean `4107836`: 160 collected (158 passed / 2 skipped with the helper; 117
passed / 2 skipped / 41 errored in the plain run).
Observed: the document's header says "Commit `4107836`" and §6.4 says "Measured on this
worktree at commit `4107836`: `collected=189 passed=187`". The extra 29 items are
`tests/unit/test_acceptance.py`, which at that moment was **staged but uncommitted** (it was
committed later in `cc29158`); the document never discloses that. **Severity: medium**
(not reproducible from the stated commit; the worktree, not the commit, was measured).

**D3 — `RUNTIME-VERIFICATION.md` lists two defects that no longer exist at HEAD as current.**
Expected at HEAD: GUI `http` mode exists (`app/backend.py` `HttpBackend`) and works (P0 17/17);
`GET /api/attempts/{id}/evidence` serves persisted rows (`evidence: persisted|not_persisted`)
and `_obligations()` is gone.
Observed in the document: §7 line 605 "GUI in HTTP-backend mode … not implemented in
`app/main.py`"; §8 item 2 "The GUI's HTTP-backend mode does not exist in code … `app/main.py`
is a demo-only app (`DEMO = True`)"; §8 item 3 "`GET /api/attempts/{id}/evidence` does not
serve persisted evidence … returns `_obligations()`, a static placeholder". **Severity:
medium** — these were true at the earlier tree state but the file is committed next to a README
that claims the opposite; a reader cannot tell which is current.

**D4 — `CONTROLLER-FIXES.md` is a pre-merge snapshot labelled like a current record.**
Expected at HEAD: its 197/195 total is superseded by 236/227/2/7; HTTP GUI mode exists.
Observed: §4.3(D) `collected=197`; §5.2 "GUI HTTP-backend mode does not exist in this
worktree". The document is explicit that task-6 did not commit and measured before the M2
merge, so this is honest-as-history but stale-as-status. **Severity: low/medium.**

**D5 — A demo-script comment states the opposite of the shipped controller.**
Expected at HEAD: the canonical evidence endpoint serves persisted rows.
Observed: `scripts/demo_e2e.py` (in the `scenario_record["attempt_evidence"][route]["note"]`
field, lines ~401–405) says: "The canonical `/api/attempts/{id}/evidence` endpoint currently
returns static placeholder V0-V5 rows from `controller_api._obligations()`; the persisted
per-attempt rows are visible in `GET /api/jobs/{id}`." At HEAD `_obligations()` does not exist
and the endpoint serves the persisted rows (independently verified). The note is not printed by
the demo, so the console evidence stays correct, but the source contradicts README line 42 and
`CONTROLLER-FIXES.md`. **Severity: low** (documentation/comment defect).

**D6 — `ROOT-CAUSE-ANALYSIS.md` status and totals are historical, not HEAD.**
Expected at HEAD: 236 executed items (167 passed / 2 skipped / 67 errored in a plain run;
227 passed with the helper); the consolidation and the controller fix are committed.
Observed: §4.4 table and Appendix A record 189 executed / 146 passed / 41 errored for the
"consolidated worktree", and §5 contains "no commits yet" / "in progress" statuses. The file is
explicitly time-stamped (analysis window 12:34–12:55) and its individual historical facts that
I could reproduce are correct — e.g. 0 commits 2026-10-23…28, missing `clang`/`gcc`/`java`/
`ghidra`/`readelf`/`objdump`, missing `capstone`/`elftools`/`lief`/`angr`/`z3`, and clean-main
160/117/2/41 exactly. **Severity: low** (dated analysis, but a reader at HEAD must not use its
totals).

**D7 — `MEMORY.md` consolidation entry totals are stale at HEAD.**
Expected at HEAD: 236 items, 167 passed / 67 errored plain; 227 passed with the helper.
Observed: `MEMORY.md` line 7 says 189 items → 146 passed / 2 skipped / 41 errored. The same
line's other claims are accurate (29 passed plain; `Interrupted: 5 errors`, exit 2, 0 tests;
no `F` markers; 6 passed + 2 skipped for `test_fixture_v3_manifest.py`). **Severity: low**
(historical measurement; file is "current state" but describes the pre-M2-merge tree).

**D8 — Residual honesty risk in `app/services/attempt_writer.py` (not a test failure).**
Expected per its docstring ("without inventing a pass") and per `docs/route-b/22`: V0 identity
is `passed` only when the bundle's original hash matches the job record (as
`routeb/attempt_writer.py` does: `identity = manifest.get("original_sha256") == job.original_sha256`).
Observed: `app/services/attempt_writer.py::_routeb` sets `"V0": "passed"` unconditionally
(line 129) whenever `candidate.elf` exists; it computes and records the candidate hash but does
not compare the original hash to the job/original, and at the time of this finding the passing
test `tests/integration/test_attempt_writer.py::test_routeb_bundle_maps_static_audit_without_runtime_pass`
asserted only V1/V3, not V0. This is an evidence-producer, not the acceptance engine (the engine
still aggregates, and V1–V5 real checks are `not_run`), so it does not invalidate the demo or
the tests, but an executor adapter could hand a `passed` V0 to the worker for an unverified
candidate. **Severity: medium — recommend a follow-up (compare the original hash or leave V0
`not_run`).** **Follow-up `986a49f`: FIXED** — `_routeb` now sets `V0: passed` only when the
bundle declares an original hash matching the job record (and, when declared, a candidate hash
matching `candidate.elf`); no identity evidence → `not_run`, mismatch → `failed`. The
static-bundle test now also asserts `V0 == not_run` and two identity tests were added.
Before/after evidence: §7.

**D9 — `M2-MERGE-REPORT.md` misstates the acceptance-tool payload size.**
Expected: `tools/p0_acceptance.py` and `tools/p2_acceptance.py` each define
`PAYLOAD = b"\x7fELF P0/P2 acceptance sample"`, which is **25** bytes. Observed in the report's
§5 note: "P0/P2 only post a 19-byte synthetic payload to the controller." The safety conclusion
(no ELF execution) is still correct; only the byte count is wrong. **Severity: low.**

No other false statement was found in the audited documents. In particular the README's
"no repair verified", `not_run` ledger, Gate 3/4 status, `docs_BinaryRepair/` 41-file count,
fixture hashes, and the demo/endpoint/test claims all match measurement.

---

## 5. Which claims I could not verify (NOT RUN ledger)

These remain **NOT RUN** for this verification, regardless of what the tree says:

| Item | Why it is not run |
|---|---|
| Execution of the original or any repaired binary on a guest | No guest/broker access from this host; host execution is forbidden by the project safety boundary |
| Route A candidate generation (capstone/LIEF) and Route A/B build | `capstone`, `lief`, `pyelftools` absent; pip unusable; the 5 ELF test modules are uncollectable |
| Real V1 structure / V2 interface / V3 behaviour / V4 symbolic / V5 replay checks | No candidate exists and no executable environment exists |
| Formal Gate 4 (Route B), Gate 5 runtime, Gate 6 | The v2 evidence bundle and canonical `docs/route-a/gate3-record.md` are not in this tree; guest execution unavailable |
| Gate 3 approval re-verification | Only the handoff summary is present; the raw bundle (`delivery/`, ignored) and the guest outputs are not part of the commit |
| Browser e2e journeys (`tests/e2e`) | Edge DevTools endpoint cannot start in this sandbox → 7 environment errors, reported as `not_run` |
| README quick start / launcher scripts | `pip` unusable, reserved port 8123 not used; launcher not executed |
| e2e "skip when Edge is not installed" path | Edge is installed (or at least the skip branch was not reached); journeys error instead |
| Real DeepSeek provider call | No API key used; not required for this task |
| Any claim that the CWE-121 fixture has been repaired or verified | No such claim is substantiated anywhere and none can be made |

Additional environment limitation reproduced by hand, and consistent with the team's
description: on this Windows/DSH sandbox pytest's own `tmp_path` machinery breaks after the
first directory (`PermissionError [WinError 5]`, then a crash in
`_pytest.tmpdir.cleanup_dead_symlinks` at session finish). That is an environment defect, not a
test result; it is why the measurement helper is needed for a clean summary.

---

## 6. Conclusion

At HEAD `7b294ba` the integrated tree **is runnable and honest on labelled synthetic data**:
import, boot, the three GUI screens, the controller HTTP API, the SQLite schema, the real
worker/orchestration path, the persisted evidence endpoints, the deterministic acceptance
engine, the demo, P0 (17/17) and the test suite (236 items: 227 passed / 2 genuine skips /
7 environment errors / 13 uncollectable functions) all behave as the README's measured section
describes. No product-code change, test weakening, deleted `main` file or committed secret was
found. The acceptance suite (29 tests) passes, and the one Lead-approved assertion change is a
strengthening, not a relaxation. Re-measured at follow-up `986a49f`: **238 items / 229 passed**
(the +2 are the new attempt-writer identity tests) — see §7.

At the initial HEAD the main verification failures were **documentation freshness**, not product
behaviour: README's provenance sentence was false (D1); `RUNTIME-VERIFICATION.md` attributed a
staged-worktree count to a clean commit and listed two already-fixed defects as current
(D2/D3); `CONTROLLER-FIXES.md` and `ROOT-CAUSE-ANALYSIS.md`/`MEMORY.md` carried pre-M2/pre-commit
numbers as if current (D4/D6/D7); one demo-script comment was stale (D5); and one residual code
risk was recorded (D8). All nine (D1-D9) were addressed in follow-up commit `986a49f`; two
low-severity labelling nits remain (N1 commit labels, N2 MEMORY plain-run error count — §7.5), and
neither changes a product claim or a measured result.

**Real repair verification remains `not_run`.** Nothing in this tree is evidence that the
CWE-121 stack overflow has been fixed; the demo and all passing tests exercise synthetic or
static data only.

---

## 7. Follow-up verification (commit `986a49f`)

**Re-measured 2026-10-29 (Asia/Hong_Kong), after the Lead's follow-up commit.**
HEAD `986a49f8328b3ee63e8bfb8e20a25368fdb89948`, parent `7b294ba` (verified with
`git rev-parse 986a49f^`). This section supersedes §1 items 6/7/16 and §6 where they quote the
initial `7b294ba` numbers.

### 7.1 What the commit contains (inspected, not trusted)

`git show 986a49f --stat` → 10 files changed, +537/−8:

| File | Change |
|---|---|
| `app/services/attempt_writer.py` | the only product-code change: `_routeb` V0 identity gating |
| `tests/integration/test_attempt_writer.py` | +69 lines: 2 new identity tests + a `V0 == not_run` assertion in the static-bundle test |
| `README.md`, `MEMORY.md` | D1 provenance and D7 current totals |
| `docs/analysis/RUNTIME-VERIFICATION.md`, `CONTROLLER-FIXES.md`, `ROOT-CAUSE-ANALYSIS.md` | D2/D3/D4/D6 dated later-status notes |
| `docs/analysis/M2-MERGE-REPORT.md` | D9 payload size 19 → 25 bytes |
| `scripts/demo_e2e.py` | D5 stale comment corrected |
| `docs/analysis/VERIFICATION.md` | this initial report committed (381 lines) |

No controller/GUI/acceptance/domain code changed, so the GUI/API/P0/P2/evidence-endpoint
results in §1 are not invalidated by this commit (the diff proves those paths are untouched);
their code paths were additionally exercised again by the re-run demo (§7.3).

### 7.2 D8 fix: before/after measured behaviour

**Before (`7b294ba`):** `app/services/attempt_writer.py::_routeb` initialised `"V0": "passed"`
for every bundle that contained `candidate.elf` (old line 129), with no comparison to the job
record.

**After (`986a49f`):** `_routeb` reads `edit-manifest.json` (`original_sha256`,
`candidate_sha256`) or a bundled `original.elf`, looks up the job's recorded `original_sha256`,
and maps V0 as follows (all rows measured by me):

| Bundle condition | V0 result | `details.V0` |
|---|---|---|
| no identity evidence (static bundle: `candidate.elf` + `audit.json` only) | `not_run` | "identity not confirmed: bundle provides no original hash" |
| declared original == job original, declared candidate == `candidate.elf` | `passed` | "original … matches the job record" |
| declared original != job original | `failed` | "original … does not match job …" |
| declared candidate hash != `candidate.elf` bytes | `failed` | "candidate.elf hash does not match edit-manifest.json" |
| bundled `original.elf` == job original (no manifest) | `passed` | original-match detail |
| bundled `original.elf` != job original | `failed` | original-mismatch detail |
| invalid `edit-manifest.json` + matching `original.elf` | `not_run` (conservative) | missing identity |

Commands and evidence:

```powershell
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch\verifier\followup_attempt_writer.json"
$env:RT_TMP_ROOT="_scratch\verifier\followup_tmp_aw"
python -m pytest tests/integration/test_attempt_writer.py -p pytest_rt_report `
  -p no:cacheprovider -q --continue-on-collection-errors
# -> collected=4 passed=4 collection_errors=0 pytest_exitstatus=0   (exit 0)

python _scratch\verifier\probe_d8_v0.py
# -> 9/9 checks PASS: the three V0 cases above plus the candidate-mismatch, bundled-original,
#    invalid-manifest and V1-unchanged checks; own jobs/bundles, not the repository tests
```

Real `routeb/executor.py` manifests contain both `original_sha256` and `candidate_sha256`
(lines 236-237), so the candidate-hash binding is live for real bundles, not only for tests.

### 7.3 Re-measured tests and demo at `986a49f`

| Measurement | Initial `7b294ba` | Follow-up `986a49f` | Delta |
|---|---|---|---|
| `tests/unit/test_acceptance.py` | 29 passed | **29 passed** | 0 |
| full suite (helper) | 236 collected / 227 passed / 2 skipped / 7 errors / 5 uncollectable | **238 collected / 229 passed / 2 skipped / 7 errors / 5 uncollectable** | +2 collected / +2 passed = exactly the two new attempt-writer identity tests (confirmed in the report JSON) |
| plain full run (no helper, `--continue-on-collection-errors`) | 236 markers: 167 passed / 67 err / 2 skip / 0 failed | **238 markers: 167 passed / 69 err / 2 skip / 0 failed** (62 `tmp_path` + 7 e2e errors) | +2 errors: the new tests also hit the sandbox `tmp_path` defect |
| plain full run (`--basetemp`, no continue) | Interrupted: 5 collection errors, exit 2, 0 tests | **same: 5 collection errors, exit 2, 0 tests** | 0 |
| `python scripts/demo_e2e.py` | exit 0 | **exit 0** — same fixture `aa428157…8393`, scope `24bfe568…4e37`, `inconclusive/required_check_not_run` + `rejected/regression_failed`, 12 obligation rows/scenario | 0 |

Helper summary at `986a49f`: `collected=238 passed=229 error=7 skipped=2 collection_errors=5
pytest_exitstatus=1`. The 7 errors are the 7 `tests/e2e/test_gui_journey.py` journeys; the 2
skips are the V3-manifest tests; the 5 collection errors are unchanged (`capstone`×3,
`elftools`×2, 13 functions).

Artifacts: `_scratch/verifier/followup_full.json`, `followup_full.log`,
`followup_plain_continue.log`, `followup_unit.json`, `followup_attempt_writer.json`,
`probe_d8_v0.py` + `.log`, `demo_followup.log`.

### 7.4 Per-discrepancy status at `986a49f`

| Item | Status | Evidence |
|---|---|---|
| D1 README provenance | **FIXED** | README:175-177 now says the numbers were measured on this tree and independently re-measured in `docs/analysis/VERIFICATION.md` (§1 items 6-7); no attribution to RUNTIME-VERIFICATION/CONTROLLER-FIXES remains (the §1 item 17 row quotes the historical wording only) |
| D2 RUNTIME 189/187 attributed to `4107836` | **FIXED (annotated)** | dated "Later status" note at the top of the document states the 189/187 run included staged `tests/unit/test_acceptance.py` and is not reproducible from `4107836` alone — exactly the initial finding |
| D3 RUNTIME current-defect claims | **FIXED (annotated)** | same note says the §7/§8 defects (no GUI `http` mode, static evidence placeholder) were fixed later by `381e4ef`/`cc29158`; the body stays as the labelled historical snapshot |
| D4 CONTROLLER-FIXES pre-merge status | **FIXED (annotated)** | dated note marks 197/195 superseded by 238/229 and the GUI-`http` gap closed by `381e4ef`; the DEFECT A/B fix itself remains independently verified |
| D5 demo-script comment | **FIXED** | `scripts/demo_e2e.py` note now says the endpoint "serves the persisted per-attempt obligation rows (`evidence: persisted`) and returns an empty group with `evidence: not_persisted`" — matches the measured behaviour |
| D6 ROOT-CAUSE historical totals | **FIXED (annotated)** | dated note labels 189/146/41 historical and states the current totals 238/229/2/7/5 |
| D7 MEMORY stale totals | **FIXED** | new "Final consolidation state" entry quotes 238/229/2/7/5 and explicitly marks the 189/146/41 entry **superseded** (verified text), with two low-severity nits below (N1, N2) |
| D8 attempt-writer V0 | **FIXED (verified)** | code + 4/4 tests + independent 9/9 probe (§7.2) |
| D9 M2 report 19-byte payload | **FIXED** | line now says 25-byte payload; both tool constants measure 25 bytes |

### 7.5 New (low-severity) issues found while re-verifying

**N1 — the commit label is one commit behind the quoted counts.** README:175-176,
`MEMORY.md:7`, and the "Later status (HEAD `7b294ba`)" notes in `RUNTIME-VERIFICATION.md`,
`CONTROLLER-FIXES.md` and `ROOT-CAUSE-ANALYSIS.md` label the 238/229 totals as HEAD `7b294ba`.
Those totals require the two new tests from `986a49f`: I measured **236/227 at `7b294ba`** and
**238/229 at `986a49f`**. The numbers are correct for the current tree; only the commit label
should say `986a49f` (or "follow-up commit"). This is the same class of commit-attribution issue
as D2 — worth a one-line correction, not a product problem.

**N2 — MEMORY's plain-run figures are stale at `986a49f`.** `MEMORY.md:7` says the plain
`--basetemp` run "yields 167 pass / 67 environment errors / 2 skip". At `986a49f` I measure
**167 passed / 69 environment errors / 2 skip / 0 failed** (the two new tests also error on the
sandbox `tmp_path` defect; 238 markers). The helper-run totals and the "0 failures" conclusion
are correct.

**Residual observations (not failures).** (a) The D3/D4/D6 notes correctly make the bodies
honest-as-historical but do not remove the old text; that is acceptable while the notes stay at
the top. (b) `_routeb`'s candidate-hash cross-check is applied only when `edit-manifest.json`
declares `candidate_sha256`; a manifest without it can still pass V0 on the original-hash match
alone — conservative (it can never turn a mismatch into a pass), and real executor manifests do
declare it. (c) A missing job record maps V0 to `not_run` rather than an error; honest, but an
executor adapter would report identity as `not_run` for a nonexistent job.

### 7.6 Updated conclusion at `986a49f`

The tree remains **runnable and honest on labelled synthetic data**, and the follow-up fixed the
one product-code honesty risk (D8) without weakening any test: the suite moved exactly by the two
added tests (**238 collected / 229 passed / 2 skipped / 7 environment errors / 5 uncollectable**),
the unit acceptance suite is still **29/29**, the demo still exits 0 with the same evidence, and
`app.services.attempt_writer` now requires bundle-declared identity matching the job record before
it can write `V0: passed` (no evidence → `not_run`, mismatch → `failed`).

All nine initial discrepancies (D1-D9) are addressed. Two low-severity labelling/figure nits
remain (N1 commit labels, N2 MEMORY plain-run error count); neither changes a product claim, a
test result, or a verdict. The PASS/FAIL status of the original 30 items is otherwise unchanged,
and all **NOT RUN** items in §5 remain not run: guest execution, real Route A/B builds,
V1-V5/V4/V5 real checks, formal Gate 4/5/6, Gate 3 raw-evidence re-verification, browser e2e,
quick-start launcher, real DeepSeek call. **No repaired binary exists or was verified anywhere in
this tree.**
