# 235 — P0 Route A trust boundary landed

- Date: 2026-11-19
- Owner: Lead
- Status: **landed on a local branch; not merged, not pushed, not an acceptance record**
- Baseline: `612510dbdff5b71b39fe9fb82ae8ec6ef8e38abb` (`origin/release/v1.2.1-candidate-2026-11-11`)
- Branch: `p0/routea-trust-boundary-2026-11-13`
- Commit: `a2fe5d1e573b688fc5bf3ad65791e48efc46c799` (parent `612510d`)

## 1. What was landed

The working-tree implementation described in record 234 is now committed on a
local branch: 15 files, +2,470 / −56 lines.

| File | Change |
|---|---|
| `app/domain/route_a_evidence.py` | new Route A host validator + host-record writer/re-validator |
| `app/services/attempt_driver.py` | canonical `.routea` staging path; exit 3 evidence gap; no generic fallback |
| `app/services/attempt_writer.py` | `--routea-bundle` mode, host records and artifact registration |
| `app/services/obligations.py` | V0 candidate binding and Route A record re-validation; missing/invalid evidence downgraded |
| `app/services/orchestration.py` | per-gate detail for evidence-gap verdicts |
| `app/services/worker.py` | exit 3 -> `inconclusive / required_check_not_run` |
| `tools/routea_bundle_to_attempt.py` | recorded path under the job store, V0 selects `candidate.elf`, documented test/preview only |
| `tests/routea_fixtures.py` | new synthetic bundle builders (no execution) |
| `tests/test_route_a_evidence.py` | new per-gate positive/negative tests (16) |
| `tests/integration/test_routea_trust_boundary.py` | new end-to-end boundary tests (5) |
| affected tests | `test_attempt_driver`, `test_attempt_writer`, `test_worker`, `test_evidence_envelope` updated |
| `docs/handoffs/234-p0-routea-trust-boundary-2026-11-13.md` | the design record |

## 2. Authoritative patch

The patch now derives from the commit, not from the working tree:

```text
git diff 612510d..a2fe5d1
.tmp/p0-routea-release/.tmp/p0-routea-a2fe5d1.patch
size      120,144 B
sha256    8ac627c9e09bbfff1c1a7dbfb2d884ee1a013bce0baebe0ba942e1934a5530db
```

Record 234 §8 cites the earlier patch `438bf795…` (119,615 B). That file was
generated before the last edit of record 234 itself (the §5 self-containment
block and the §8 hash were added afterwards), so it no longer reverse-applies
exactly; the commit-derived patch above supersedes it. The historical hash is
kept here only so the two artefacts are not confused.

## 3. Verification re-run on the landed tree (2026-11-19)

All runs used the host measurement workaround (`-p no:tmpdir -p
pytest_rt_report`, `RT_TMP_ROOT` under the workspace, absolute long-path root
for the integration cases). No test was skipped or weakened.

```text
py_compile <7 changed modules>                                    -> exit 0
pytest <4 new + 3 affected files>                                 -> 49 passed, 1 skipped, 0 failed
pytest tests/ --ignore=tests/e2e                                  -> 751 collected
                                                                     730 passed, 13 skipped, 8 failed
```

The 8 failures are the known `tests/test_guest_executor.py` `PermissionError`
failures raised inside `tempfile.TemporaryDirectory()` teardown under the DSH
sandbox; they are the same failures recorded in record 234 and they do not
touch the changed modules.

Fresh-baseline self-containment (detached worktree at `612510d`):

```text
git apply --check .tmp/p0-routea-a2fe5d1.patch   -> exit 0
git apply .tmp/p0-routea-a2fe5d1.patch           -> exit 0
py_compile <7 changed modules>                   -> exit 0
pytest <new + driver tests>                      -> 28 passed, 0 failed
```

## 4. Guest window state (opened by the owner from the desktop, 2026-11-19)

Read-only inventory over SSH (`lab@192.168.30.128`):

```text
guest      Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic, boot_id 2504a5a5-8fcd-44d7-8524-c0e8cc2899fe
isolation  /usr/local/sbin/jobwrap-executor sha256 85be8aef…2f60 (record 152 binary)
executor   /opt/binrepair/executor-repo workers/route_a/worker.py 3d53ec25…
           workers/executor/run_job.py 9abd59e3…  (2026-11-12 redeploy)
           no workers/route_a/run_candidate.py
tools      /opt/angr-venv: python 3.12.3, angr 10.0.4.post1, pyelftools 0.33, z3 5.1.0.0
           system python: pyelftools 0.33, LIEF 1.0.0
accounts   runner uid 1003, m4verify uid 1004
disk       23 G free, 7.8 GiB RAM
```

Two divergences matter for the re-run and must be reconciled before a bundle is
called reproducible:

1. the installed executor tree no longer matches snapshot
   `p1-prewindow-20261107` / repo manifest `2fe3c4ae…` (already recorded on
   2026-11-12); a new baseline snapshot and record remain a team decision.
2. the installed `run_job.py` already writes `evidence/v3/manifest-repaired.json`,
   while the release branch still writes `out/manifest-repaired.json` (record
   234 §6.5). A guest run from the current tree would therefore collect V3, but
   the same run is not reproducible from the release branch until that wiring
   difference is resolved.

## 5. What this landing does and does not change

- It makes the P0 boundary reviewable, testable and applicable from a commit.
- No production gate, acceptance record, fixture, DB, or guest file is changed.
- No push, no merge to `main` or to `release/v1.2.1-candidate-2026-11-11`.
- The Route A re-run still needs the open guest window and the known fixes
  (guest worker contract-hash parity, V5 replay envelope; see record 234 §6).
