# 44 — Answer to M1: branch location, measured evidence, and the transfer package

**From:** Lead
**To:** M1 (main owner)
**Date:** 2026-10-29
**Re:** M1's six questions about `integration/consolidation-2026-10-29`
**Status:** all six answered below with commands and observed output. This is the only handoff M1 needs; do not ask M4 for branch contents — M4 does not own the transfer.

## 0. Why M1 cannot see the branch

The branch **was never pushed**. It exists only in the Lead's local clone at
`D:\BinaryRepair_Project`; this environment has no working push credentials
(`git remote -v` points at `https://github.com/chenfanaichifan/binary-repair.git`,
but no push was attempted, and an external push needs the Lead's explicit
approval). So "remote and local both absent" is expected, not a failure.

The fix is the **transfer package** described in §1: a full git bundle + a tree zip,
with SHA-256 sums. M1 imports the bundle, pushes, and opens the PR.

## 1. Q1 — Where is the branch?

| Field | Value |
|---|---|
| Local repo | `D:\BinaryRepair_Project` (Lead's checkout) |
| Branch | `integration/consolidation-2026-10-29` |
| HEAD at final measurement | see `git log -1` after import; the verified test state is `86f78af` and the only later commits are docs-only (`e0d70be`, `2c0e3c4`, `86f78af` is M4 docs+helper, `079a917` Gate 3 record restore, plus this document) |
| Remote | none — never pushed |
| Transfer bundle | `delivery/integration-consolidation-2026-10-29-<head>.bundle` (full history, self-contained) |
| Tree zip fallback | `delivery/integration-consolidation-2026-10-29-<head>-tree.zip` |
| Evidence/log package | `delivery/m1-evidence/` |
| One-file transfer | `delivery/m1-transfer-2026-10-29.zip` + `.sha256` |

Import (exact commands; run in M1's clone):

```powershell
git bundle verify D:\path\to\integration-consolidation-2026-10-29-<head>.bundle
git fetch D:\path\to\integration-consolidation-2026-10-29-<head>.bundle `
  refs/heads/integration/consolidation-2026-10-29:refs/heads/integration/consolidation-2026-10-29
git switch integration/consolidation-2026-10-29
git log --oneline -1
git push -u origin integration/consolidation-2026-10-29
```

If the bundle path fetch is awkward on M1's host, use the tree zip: extract it
outside the repo, then `git add`/commit is **not** the right path — the zip is only a
read-only fallback for inspection. The bundle is the transfer format for git history.

**Hash of each artifact:** `delivery/m1-evidence/SHA256SUMS` (also copied into the
transfer zip). Compare with `Get-FileHash <file> -Algorithm SHA256` before use.

## 2. Q2 — Where do 238 / 229 / 2 / 7 / 5 come from?

**Commit measured:** `86f78af` (`integration/consolidation-2026-10-29`). Product code and
the test suite are unchanged by the later commits (they add docs, a Gate 3 record, and
the M4 verification helper). If a later docs-only commit changes `HEAD`, the number is
still produced by the same tree.

**Environment (measured):**

```text
OS: Microsoft Windows [Version 10.0.26300.9711] (Windows 11, AMD64)
Python: 3.14.6 (MSC v.1944 64-bit)
pytest: 9.1.1
fastapi 0.141.1, starlette 1.6.0, uvicorn 0.52.4, jinja2 3.1.6,
httpx 0.28.1, pydantic 2.13.5, jsonschema 4.26.0, python-multipart 0.0.32
capstone: absent; pyelftools/elftools: absent; lief: absent
```

**`pytest --collect-only` tail (plain, no helper):**

```text
ERROR tests/test_routea_cave.py
ERROR tests/test_routea_manifest.py
ERROR tests/test_routea_worker.py
ERROR tests/test_routeb_attempt_writer.py
ERROR tests/test_routeb_executor.py
!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!!!
```

Exit code 2, 0 tests run — five modules cannot even be imported (see Q3).

**`pytest -q` summary:** on this Windows/DSH sandbox a plain run **cannot print a
summary line** because pytest's own `tmp_path` fixture becomes unreadable after the
first test (`PermissionError [WinError 5]`), and pytest then crashes in
`_pytest.tmpdir.cleanup_dead_symlinks` during session finish. That is an environment
defect, not a test failure. Measured two ways:

| Run | Command | Observed |
|---|---|---|
| plain, no helper | `python -m pytest tests/ --basetemp=<pre-created> -p no:cacheprovider -q --continue-on-collection-errors` | 238 progress markers: **167 passed / 2 skipped / 69 environment errors / 0 failed**; no summary line; exit 1 |
| measurement helper | `PYTHONPATH=scripts python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors` | `[pytest_rt_report] collected=238 error=7, passed=229, skipped=2 collection_errors=5 pytest_exitstatus=1` |

Why the two runs differ: the helper only replaces the broken `tmp_path` fixture with a
writable per-test directory and tolerates the session-finish crash. It does not skip,
reorder, xfail, or rewrite any test. The plain run proves the same 238 items either pass
or fail on the environment error; **there are 0 assertion failures in both runs**. The
independent verifier (`docs/analysis/VERIFICATION.md`) reproduced the same numbers and
audited the helper.

Full raw logs: `delivery/m1-evidence/logs/collect_only.txt`,
`pytest_plain_continue.txt`, `pytest_helper_console.txt`, `pytest_report.json`.

## 3. Q3 — The 7 environment errors and the 5 uncollectable modules

**7 errors — all in `tests/e2e/test_gui_journey.py`, all the same cause**
(`RuntimeError: Edge DevTools endpoint did not become ready`, `tests/e2e/cdp.py:138`):

```text
tests/e2e/test_gui_journey.py::test_cancel_keeps_evidence
tests/e2e/test_gui_journey.py::test_full_journey_setup_to_export
tests/e2e/test_gui_journey.py::test_http_mode_uses_the_real_controller
tests/e2e/test_gui_journey.py::test_landing_hero_leads_to_workbench
tests/e2e/test_gui_journey.py::test_local_mode_is_honest
tests/e2e/test_gui_journey.py::test_refresh_keeps_state_and_shows_unfinished_stages
tests/e2e/test_gui_journey.py::test_setup_wizard_has_two_choice_pages
```

They need a desktop with Microsoft Edge / an available DevTools endpoint; this sandbox
cannot start one, so they are `not_run`, not failures of the GUI.

**5 uncollectable modules (13 test functions, all `not_run`):**

```text
tests/test_routea_cave.py      ModuleNotFoundError: No module named 'capstone'
tests/test_routea_manifest.py  ModuleNotFoundError: No module named 'capstone'
tests/test_routea_worker.py    ModuleNotFoundError: No module named 'capstone'
tests/test_routeb_attempt_writer.py  ModuleNotFoundError: No module named 'elftools'
tests/test_routeb_executor.py        ModuleNotFoundError: No module named 'elftools'
```

`capstone` is imported by `routea/cave.py`; `elftools` by `routeb/executor.py`. They
need `capstone`/`pyelftools` for Python 3.14; neither is installed here and pip is
unusable in this sandbox. On the Ubuntu target they are expected to run; that is still
`not_run` on this host.

Raw: `delivery/m1-evidence/logs/e2e_error_names.txt`, `uncollectable.txt`.

## 4. Q4 — demo, P0, P2 raw commands and outputs

All logs are in `delivery/m1-evidence/logs/` and hashed in `SHA256SUMS`. All were run
at `86f78af`; none executes an uploaded or repaired binary (the demo only reads/hashes
the public fixture; P0/P2 post a 25-byte synthetic payload).

**Demo (exit 0):**

```text
python scripts/demo_e2e.py
-> exit 0; "DEMO OK: synthetic attempt data exercised the real controller, database,
   worker and deterministic acceptance path end to end."
-> fixture sha256 aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393
-> contract scope sha256 24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37
-> scenario 1: inconclusive / required_check_not_run
-> scenario 2: rejected / regression_failed
```

**P0 (live GUI `http` mode + real controller, exit 0, 17/17 PASS):**

```text
python tools/p0_acceptance.py --gui http://127.0.0.1:18802 `
  --controller http://127.0.0.1:18801 --token <local-session-token>
-> P0 ACCEPTANCE PASSED (17 PASS lines, exit 0)
```

**P2 (exit 2 BLOCKED — the honest current state):**

```text
python tools/p2_acceptance.py --gui http://127.0.0.1:18802 `
  --controller http://127.0.0.1:18801 --token <local-session-token> --timeout 5
-> BLOCKED  pipeline did not finish: phase='queued'. The worker may be running, but it
   needs a result bundle per attempt (written by the external executor /
   BINARYREPAIR_ATTEMPT_CMD) ...
-> exit 2
```

Full: `logs/demo_e2e.txt`, `logs/p0_acceptance.txt`, `logs/p2_acceptance.txt`,
`logs/controller_server.log`, `logs/gui_server.log`. Both servers were stopped; no
listener remained on 18801/18802.

## 5. Q5 — Are `contracts.body_json` (DB v2) and the V3 manifest line endings closed?

**Yes, both are closed on this branch.** Reproduced at `86f78af` with the helper:

| Issue | Fix commit on the branch | Test file | Observed |
|---|---|---|---|
| DB v2 `contracts.body_json` (002 migration over the v1 baseline) | `b0ee69b` — `feat(db): apply v1 baseline + 002 AI tables with fail-closed guards` | `tests/test_db_v2.py` (8 tests) | `collected=8 passed=8 collection_errors=0` exit 0 |
| V3 manifest hashes / line endings | `d493f74` — `chore: clean repository layout and pin fixture bytes` (adds `.gitattributes` byte pinning) | `tests/test_fixture_v3_manifest.py` (8 tests) | `collected=8 passed=6, skipped=2` exit 0; the 2 skips are the runtime/guest V3 tests ("ELF execution requires Linux") |

DB test names (all pass): `test_init_creates_baseline_and_ai_tables`,
`test_reinit_is_idempotent`, `test_idempotency_is_per_job`,
`test_attempt_uniqueness_and_obligation_vocabulary`,
`test_legacy_001_is_rejected_before_ddl`, `test_duplicate_artifacts_fail_and_list_rows`,
`test_artifact_media_type_default`, `test_acceptance_verdict_fields_persist_verbatim`.

Manifest test names (6 pass, 2 skip): `test_manifest_identity`,
`test_valid_cases_are_preserved`, `test_invalid_cases_take_the_reviewed_error_path`,
`test_contract_matches_the_manifest_boundary`, `test_manifest_file_hashes_are_frozen`,
`test_manifest_set_hash_is_frozen_and_order_independent`, and the two skipped runtime
tests `test_original_is_v0_on_invalid_inputs_if_binary_present`,
`test_repaired_candidate_matches_v3_if_provided`.

Logs: `logs/db_v2_only.txt`, `logs/manifest_only.txt`, `logs/db_v2_and_manifest.txt`.

## 6. Q6 — Which member slices does the branch contain?

Branch history (merge parents verified):

```text
origin/main                        4107836  (base)
  └─ cc29158  (M4 acceptance + governance + controller evidence fix)
  └─ 381e4ef  merge of M2 (parents: 036328d member2-backend-adapter + 4107836)
       └─ 7b294ba  merge of cc29158 + 381e4ef
            └─ 986a49f, 497a689, c5081f8, ab3f1ed, 2c0e3c4, e0d70be,
               86f78af (M4 checklist/plan/verifier helper), 079a917 (Gate 3 record)
```

| Slice | Source ref | What is included | State |
|---|---|---|---|
| **M1** controller/API/services/DB | `origin/main` `4107836` | `app/controller_api.py`, `app/services/*`, `app/db/*`, `app/main.py` pre-merge base | included in base |
| **M2** GUI/controller adapter | `origin/member2-backend-adapter` `036328d`, merged as `381e4ef` | 66 files, +7635/−504: `app/backend.py`, `app/main.py` GUI, templates/static, launchers, `tools/p0_acceptance.py`, `tools/p2_acceptance.py`, `tests/e2e/`, screenshots | included |
| **M4** acceptance + verification | `member-4-verification` `9c6e1f7` via `cc29158`, plus `86f78af` | `tests/unit/test_acceptance.py` (29), AGENTS/MEMORY/REVIEW-CHECKLIST, `agent_docs/`, `docs_BinaryRepair/` (41 files), `docs/analysis/`, acceptance fixes, Gate 4 checklist/plan + `scripts/m4_verify_gate4.py` | included |
| **M5** contract, Route A/B kit, schemas | `origin/main` `4107836` | canonical contract `24bfe568…4e37`, `routea/`, `routeb/`, `schemas/`, `dist/m5-routeb-kit-*`, `docs/route-b/` | included (base) |
| **M3** fixture, oracle, Route A evidence | `origin/main` `4107836` (plus docs from M4 branch) | `fixtures/public/CWE121_src_char_declare_cpy_51b/` (ELF, contract, frozen tests), `routea/out/*` static evidence, Gate-3/6 handoff notes | included (base) |
| **Gate 3 record** | `member-4-verification` `9c6e1f7`, blob `45357e70…`, restored in `079a917` | `docs/route-a/gate3-record.md`, sha256 **`0b3b51e4…f2da`** (canonical approved record) | included |
| M3 guest evidence packages (`P4/P3A/P3B`) | not yet produced | — | **not in branch** (by design; producer task T3.0-T3.3) |
| Gate 4 record | not yet produced | — | **not in branch** (M5 task T5.3) |

**Not included:** live guest run outputs, the v2 evidence bundle zip (local `delivery/`,
git-ignored), and any Gate 4/5/6 record. Those become available only after M3/M5
deliver their packages; until then Gate 4 is `NOT RUN` and the real pipeline is
`BLOCKED (exit 2)`.

## 7. M1's next actions (no ping-pong)

1. Copy the transfer package, verify `SHA256SUMS` (`Get-FileHash`), and `git bundle verify`.
2. Fetch the branch, push it, open the PR (commands in §1). The PR description can quote
   §2–§5 of this file.
3. Reply with **exactly three things**: bundle SHA-256 you verified, `git log --oneline -1`
   after import, and the PR URL. No re-questions: every number in this file has a log in
   the package.
4. If a number does **not** reproduce on M1's host, reply with the exact command and the
   observed output (not "please confirm") — then the Lead attaches the diff to the same
   evidence package. A mismatch is handled as a new measured fact, not as a discussion.
