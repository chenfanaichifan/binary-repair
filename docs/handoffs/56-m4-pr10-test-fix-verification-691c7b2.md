# 56 — M4 re-verification of the PR #10 test fix (`691c7b2`)

**From:** M4 (independent verifier)
**To:** M1, M5, Lead
**Date:** 2026-10-29 19:12 (Asia/Hong_Kong)
**Scope:** re-verification of M5's test-restoration commit **only**. This is not a PR approval,
not Gate 4, not a repair/gate claim. Gate 4 remains `NOT RUN`; Gate 5 `51` unsigned; fixture
`NOT FROZEN`.
**Fix commit:** `691c7b21a70218c28ef9adc50900f3d4ee30a3c7` (`origin/member-5/pr10-test-fix`,
parent `cd63e21`)
**PR #10 head at verification time:** `ce40aaff03f8d371c80a8755aa17b36f5b37b2a4` — **does not
contain `691c7b2`** (verified: `git merge-base --is-ancestor 691c7b2 ce40aaf` = 1). The PR head
only merged main `cf2f46d`; the fix is still on M5's branch.
**Identity limitation (recorded):** M4 verifier and Lead are the same person/operator (two AI
windows of one person); the M4 row and Lead row are not independent two-person signatures.

## 1. Fix-commit verification (PASS)

| Check | Observed | Verdict |
|---|---|---|
| diff scope | `git diff --stat cd63e21 691c7b2` = `docs/handoffs/49-pr10-test-fix.md` (+21) and `tests/integration/test_attempt_writer.py` (+53/−2); **no `app/`, `routea/`, `routeb/`, `binaryrepair_ai/`, `scripts/`, `tools/`, `schemas/`, `fixtures/` change** | PASS |
| identity test 1 restored | `test_routeb_identity_passes_only_with_matching_original` present; asserts V0 `passed` for matching original | PASS |
| identity test 2 restored | `test_routeb_identity_fails_on_original_mismatch` present; asserts V0 `failed` for mismatch | PASS |
| static V0 assertion restored | `assert payload["results"]["V0"] == "not_run"` back in `test_routeb_bundle_maps_static_audit_without_runtime_pass` | PASS |
| Route A tests retained | `test_routea_bundle_maps_gates_and_registers_evidence`, `test_routea_bundle_rejects_passed_without_evidence` still present | PASS |
| no skip/xfail | `git grep -n -E 'pytest\.skip|xfail|skipif' 691c7b2 -- tests/integration/test_attempt_writer.py` = empty | PASS |
| targeted file | `collected=6 passed=6 collection_errors=0 pytest_exitstatus=0`, exit 0 (helper on this host; plain run hits the known `tmp_path` sandbox defect, not test failures) | PASS |
| acceptance unit | `collected=29 passed=29 collection_errors=0 pytest_exitstatus=0`, exit 0 | PASS |
| full suite | `collected=246 error=7, passed=237, skipped=2 collection_errors=5 pytest_exitstatus=1`; 7 = Edge/DevTools e2e environment errors; 5 = capstone×3 + elftools×2 uncollectable; **0 assertion failures** | PASS |
| production behaviour | no production diff, so the restored tests run against the same `app/services/attempt_writer.py` as `cd63e21`; both identity tests pass | PASS |

**Fix-commit verdict: PASS.** The test weakening is repaired on `691c7b2`.

## 2. PR #10 head status (still FAIL / blocked)

- `refs/pull/10/head` = `ce40aaff03f8d371c80a8755aa17b36f5b37b2a4` (also
  `integration/consolidation-final-2026-10-29`); it is a merge of `cd63e21` with main `cf2f46d`.
- Its `tests/integration/test_attempt_writer.py` still has the weakened 4-test state; `691c7b2`
  is not an ancestor. Therefore the earlier M4 row (`docs/handoffs/54`, FAIL) **still applies to
  the current PR head**, and Lead approval remains withheld (`docs/handoffs/55`).
- Current remote `main` = `c9dd8d32` (two docs-only commits past `cf2f46d`:
  `docs(m5): accept P3B v3 partial and witness P4 native manifest`, `docs(witness): update P3B
  v3/P4 witness observations`). The PR head is also missing those.

## 3. Required next step (M1)

1. `git fetch origin member-5/pr10-test-fix`
2. `git cherry-pick 691c7b2` onto the current PR head
3. `git fetch origin main && git merge origin/main` (latest `c9dd8d32`, docs-only at this moment)
4. Push the resulting head to `HEAD:integration/consolidation-final-2026-10-29` (updates PR #10)
5. Notify M4 with the new head SHA.

M4 will then re-run on that exact head: targeted 6/6, acceptance 29/29, full suite counts (expected
246 collected / 237 passed / 2 skipped / 7 environment errors / 5 uncollectable, 0 assertion
failures), demo exit 0, secret/client scan, oracle/acceptance/fixture diff, and Gate-claim check.
Only after that may M4 issue a PR-head PASS row; only then may the Lead write approval citing
PR #10, the exact new head, the M4 row file/hash, the merge commit and tag
`mvp-integration-2026-10-31`.

## 4. Verdict

**Fix commit `691c7b2`: PASS. PR #10 head `ce40aaf`: still FAIL/blocked — fix not integrated.
No merge, no tag, no approval.**
