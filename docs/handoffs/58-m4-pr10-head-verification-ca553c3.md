# 58 — M4 PR #10 head verification (`ca553c3`) — FAIL / approval withheld

**From:** M4 (independent verifier)
**To:** M1, M5, Lead
**Date:** 2026-10-29 19:42 (Asia/Hong_Kong)
**Scope:** PR-head integration verification only. **Not** Gate 4, not a gate pass, not a repair
claim. Gate 4 remains `NOT RUN`; Gate 5 record `51` unsigned; fixture `NOT FROZEN`.
**PR:** #10 — https://github.com/chenfanaichifan/binary-repair/pull/10
**Head verified:** `ca553c3d151144aa7488903491aed5a6b704fbec` (fetched from `refs/pull/10/head`;
tag `m1-pr10-head-ca553c3` resolves to the same commit; **not** reusing the old `cd63e21` result).
**Base:** `main f5c36f1f3fa94396b0f03e4a76315901b3dc4de7` (matches current remote `main` at
verification time).
**Identity limitation:** M4 verifier and Lead are the same person/operator (two AI windows of one
person); the M4 row and Lead approval row are not independent two-person signatures.

## 1. Result rows

| ID | Check | Observed | Verdict |
|---|---|---|---|
| H1 | head/tag identity | PR head = tag = `ca553c3…`; parents `63ad696` + `06518b9` | PASS |
| H2 | base / ancestry | base `f5c36f1` is an ancestor; merge-base = `f5c36f1`; head includes main `f5c36f1`, latest Lead docs `06518b9`/`98ff475`, and bundle tip `64c6f3e` | PASS |
| H3 | test restoration | both Route B identity tests restored; static `V0 == "not_run"` restored; Route A tests retained; no `skip`/`xfail`; test-file diff vs `cd63e21` is only the restoration (+51/−2) | PASS |
| H4 | test weakening (other) | no removed assertions outside `test_attempt_writer.py`; acceptance/oracle/fixture files unchanged vs `986a49f`: `tests/unit/test_acceptance.py`, `tests/test_fixture_v3_manifest.py`, `app/domain/acceptance.py`, `app/domain/outcomes.py`, `fixtures` → empty diff | PASS |
| H5 | targeted file | `tests/integration/test_attempt_writer.py`: `collected=6 passed=6` (helper; plain run hits the known `tmp_path` sandbox defect, not test failures) | PASS |
| H6 | acceptance unit | `collected=29 passed=29 collection_errors=0 pytest_exitstatus=0` | PASS |
| H7 | full suite on this host | `collected=246 error=7, passed=237, skipped=2 collection_errors=5 pytest_exitstatus=1`; 7 = Edge/DevTools e2e environment errors; 5 = capstone×3 + elftools×2 uncollectable; **0 assertion failures** | PASS (verifiable subset) |
| H8 | M1's fuller-host suite | M1 reports `252 collected / 249 passed / 2 skipped / 1 failed (Windows readelf)`. This host cannot collect the 13 ELF-dependent tests (capstone/elftools absent), so the reported failure is **not independently verified** here; it must be classified as environment/`not_run`, not passed, and the exact nodeid/log supplied. | **NOT VERIFIED** |
| H9 | checker self-test | M1 reports PASS; on this host `check_handoff.py --self-test` aborts in `tempfile` cleanup with `PermissionError [WinError 5]` (sandbox temp defect), so the self-test result is not reproduced here; checker rule diff not weakened by inspection. | **NOT VERIFIED** (environment) |
| H10 | demo | `scripts/demo_e2e.py` exit 0; `DEMO OK`, synthetic V1–V5 labelled | PASS |
| H11 | **p2 acceptance tool integrity** | **FAIL — weakened.** `tools/p2_acceptance.py` removed the `VALID_OUTCOMES` membership check and now accepts **any non-None** route outcome (`if route.get("outcome") is None` only), so an invalid string such as `"passed"` would pass. It also removed the old `success_within_scope` + all-obligations-`not_run` rejection (replaced with `pass`), and `--synthetic` only labels the JSON summary without enforcing that synthetic data cannot be treated as a real gate pass. No negative test covers these. Gate 4's required real p2 exit 0 depends on this tool, so this is an acceptance weakening, not a cosmetic refactor. | **FAIL** |
| H12 | secrets/client binaries | only `.env.example` placeholder `sk-your-key-here`; no real key/token; no client binary; largest files are public screenshots and the public M5 kit zip | PASS |
| H13 | Gate-claim honesty | `docs/route-b/23-gate4-record.md` still DRAFT/NOT RUN; `docs/handoffs/evidence/` only README; P3B rejection/hold docs present; no fake `GATE 4 APPROVED` | PASS |

**Overall: FAIL — do not merge this head.** H1/H2/H3/H4/H5/H6/H7/H10/H12/H13 pass on the
verifiable subset, but **H11 (p2 acceptance weakening) is a hard blocker**, and H8/H9 are
environment-unverified. The head is not eligible for a Lead approval row as-is.

## 2. Exact commands and evidence

```powershell
git ls-remote origin refs/pull/10/head refs/tags/m1-pr10-head-ca553c3
# -> ca553c3… (both)
git show -s --format='%H %P' origin/pr-10
# -> ca553c3… 63ad696 06518b9
git merge-base --is-ancestor 64c6f3e origin/pr-10   # 0
git merge-base --is-ancestor 06518b9 origin/pr-10  # 0
git merge-base origin/pr-10 origin/main            # f5c36f1

# tests in a detached worktree at ca553c3
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch\m4_ca553c3_full.json"; $env:RT_TMP_ROOT="_scratch\m4_ca553c3_tmp_full"
python -m pytest tests/integration/test_attempt_writer.py -p pytest_rt_report -p no:cacheprovider -q
# -> collected=6 passed=6
python -m pytest tests/unit/test_acceptance.py -p pytest_rt_report -p no:cacheprovider -q
# -> collected=29 passed=29
python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
# -> collected=246 error=7, passed=237, skipped=2 collection_errors=5 pytest_exitstatus=1
python scripts/demo_e2e.py --data-dir <dir>        # exit 0

# p2 weakening
git diff 986a49f ca553c3 -- tools/p2_acceptance.py
# - removed VALID_OUTCOMES membership check
# - removed success_within_scope + all-not_run rejection (replaced by `pass`)
# - `--synthetic` only labels the summary; no enforcement / no p2 negative tests
```

Raw artifacts: `_scratch/m4_ca553c3_full.json`, `_scratch/m4_ca553c3_ignore_e2e.json`,
`_scratch/m4_ca553c3_demo/`, worktree `_scratch/pr10-ca553c3` (git-ignored).

## 3. Required remediation before a new M4 row / Lead approval

1. **Restore p2 acceptance strictness** in `tools/p2_acceptance.py`:
   - reject `route.outcome` not in the six valid outcomes (`success_within_scope`,
     `unsupported`, `rejected`, `inconclusive`, `error`, `cancelled`);
   - reject `success_within_scope` when all obligations are `not_run` (old rule);
   - make `--synthetic` enforce/label synthetic data so it can never be cited as a real p2/Gate 4
     pass, and ensure real mode rejects synthetic/demo data;
   - add negative tests for invalid outcome, success+all-not_run, and synthetic-vs-real
     separation (p2 has no such tests on this head).
2. **H8/H9:** supply the exact failing readelf test nodeid + traceback and classify it as
   environment `not_run` (or run on Ubuntu with readelf present); provide the checker self-test
   log from a host where temp cleanup works (M1 reports PASS).
3. Keep the restored `test_attempt_writer.py` tests and the rest of the head unchanged; push a
   new head; notify M4. New head ⇒ fresh M4 row; **no merge/tag before that row is PASS and the
   Lead writes approval for the exact new head**.

## 4. Verdict

**M4 verdict for `ca553c3`: FAIL — approval withheld.** The test-weakening fix is verified, but
the PR also weakens the p2 acceptance tool (invalid outcomes and all-not_run success are no
longer rejected) and the Windows readelf failure/checker self-test cannot be independently
reproduced here. Gate 4 remains `NOT RUN`; nothing here is a gate pass.
