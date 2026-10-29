# 54 — M4 PR #10 head verification (cd63e21) — FAIL (approval withheld)

**From:** M4 (independent verifier)
**To:** M1, Lead, M5
**Date:** 2026-10-29 18:50 (Asia/Hong_Kong)
**Scope:** **PR-head integration verification only.** This is **not** Gate 4, not a Gate 5
signature, not a repair claim. Gate 4 remains `NOT RUN`; Gate 5 record `51` remains unsigned;
fixture `NOT FROZEN`.
**PR:** #10 — https://github.com/chenfanaichifan/binary-repair/pull/10
**Head verified:** `cd63e21d690f4dff9a86ed4cd552e57aa41e682f` (fetched from
`refs/pull/10/head`; **not** the old `73e8e7b` conclusion; `73e8e7b` is only a parent).
**Base at request:** `main ffca9a0`; current remote `main` is `328d355e` (see H11).
**Identity limitation (recorded):** the M4 verifier and the Lead are the same person/operator
(two AI windows of one person, analogous to VMer = M3). The M4 row and the Lead approval row are
**not independent two-person signatures**; no independent-human-review claim is made.

## 1. Result rows

| ID | Check | Observed | Verdict |
|---|---|---|---|
| H1 | PR head identity | `refs/pull/10/head` = `cd63e21d690f4dff9a86ed4cd552e57aa41e682f`; head commit parents `73e8e7b` + `ffca9a0` | **PASS** |
| H2 | ancestry / base | `ffca9a0` and `73e8e7b` are ancestors; merge-base with `main` = `ffca9a0` | **PASS** (base drift noted H11) |
| H3 | branch vs bundle/transfer tip | bundle/transfer tip `64c6f3e` **is an ancestor** of the head; head is **not equal** to it; latest lead branch tip `98ff475` (docs 50/51/53 + probe/launcher) is **not** included | **NOT VERIFIED** (contains, not equal) |
| H4 | no secret / client binary | no real key/token; only `.env.example` placeholder `sk-your-key-here`; no client binary; largest files are public screenshots (`00-landing.png` 1,316,803 B etc.) and the public M5 kit zip `dist/m5-delivery-2026-10-22.zip` (94,258 B) | **PASS** |
| H5 | acceptance unit suite (host, PR-head worktree) | `[pytest_rt_report] collected=29 passed=29 collection_errors=0 pytest_exitstatus=0`, exit 0 | **PASS** |
| H6 | full suite (host, helper) | `collected=244 error=7, passed=235, skipped=2 collection_errors=5 pytest_exitstatus=1`; 7 = Edge/DevTools e2e environment errors; 5 = capstone×3 + elftools×2 uncollectable (13 functions); **0 assertion failures** | **PASS** |
| H7 | demo `scripts/demo_e2e.py` | exit 0; `DEMO OK`; synthetic V1–V5 labelled, no real execution claimed | **PASS** |
| H8 | **test integrity / no weakening** | **FAIL** — two Route B identity tests from `986a49f` are missing, with no replacement coverage in the PR tree: `test_routeb_identity_passes_only_with_matching_original`, `test_routeb_identity_fails_on_original_mismatch`; the static-bundle test also lost its `assert payload["results"]["V0"] == "not_run"` line. Current file has 4 tests (generic, static, route-A map, route-A reject) instead of the 4 old tests; the two identity guards are simply gone. `tests/unit/test_attempt_from_bundle.py` / route-A adapter tests do **not** cover Route B identity. | **FAIL** |
| H9 | oracle/acceptance/fixture unchanged | `git diff --stat 986a49f cd63e21 -- tests/unit/test_acceptance.py tests/test_fixture_v3_manifest.py app/domain/acceptance.py app/domain/outcomes.py fixtures` = **empty** | **PASS** |
| H10 | Gate-claim honesty | `docs/route-b/23-gate4-record.md` is still DRAFT/NOT RUN; `docs/handoffs/evidence/` only README; P3B rejection doc present; no fake `GATE 4 APPROVED` | **PASS** |
| H11 | base drift | current remote `main` = `328d355e` (one docs-only commit since PR base `ffca9a0`: `docs/handoffs/41`, `44`, new `48-p4-cli-b-artifact-gap.md`). No product/test change in the delta, but the final merge commit would include it. | **NOT VERIFIED** for final-merge equivalence |

**Overall: FAIL — do not merge this head as-is.** H1/H2/H4–H7/H9/H10 pass; **H8 is a test
weakening** (removing M4's Route B identity negative/positive guards) and H3/H11 are unresolved
traceability items. The head is not eligible for a Lead approval row until H8 is fixed and a new
head is re-verified.

## 2. Exact commands and evidence

```powershell
# head + base
git ls-remote origin refs/pull/10/head            # cd63e21…
git fetch origin refs/pull/10/head:refs/remotes/origin/pr-10
git show -s --format='%H %P' origin/pr-10          # cd63e21… 73e8e7b ffca9a0

# ancestry / bundle tip
git merge-base --is-ancestor 64c6f3e origin/pr-10  # 0 (contains bundle tip)
git merge-base --is-ancestor 98ff475 origin/pr-10  # 1 (latest lead docs not included)

# tests (worktree at cd63e21, helper)
$env:PYTHONPATH="scripts"
$env:RT_REPORT_PATH="_scratch\m4_pr10_full.json"; $env:RT_TMP_ROOT="_scratch\m4_pr10_tmp_full"
python -m pytest tests/ -p pytest_rt_report -p no:cacheprovider -q --continue-on-collection-errors
# -> collected=244 error=7, passed=235, skipped=2 collection_errors=5 pytest_exitstatus=1
python -m pytest tests/unit/test_acceptance.py -p pytest_rt_report -p no:cacheprovider -q
# -> collected=29 passed=29 collection_errors=0 pytest_exitstatus=0
python scripts/demo_e2e.py --data-dir <dir>        # exit 0, DEMO OK

# test-integrity finding
git show cd63e21:tests/integration/test_attempt_writer.py | Select-String '^def test_'
# -> generic, routeb_static, routea_map, routea_reject  (2 identity tests gone)
git diff 986a49f cd63e21 -- tests/integration/test_attempt_writer.py
# -> removes test_routeb_identity_passes_only_with_matching_original,
#    test_routeb_identity_fails_on_original_mismatch, and the static V0==not_run assertion

# secrets / client binaries
git grep -I -n -E 'sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{30,}|BEGIN [A-Z ]*PRIVATE KEY|DEEPSEEK_API_KEY[=:]' cd63e21 -- .
# -> only .env.example: DEEPSEEK_API_KEY=sk-your-key-here (placeholder)
```

Raw local run artifacts: `_scratch/m4_pr10_full.json`, `_scratch/m4_pr10_acceptance.json`,
`_scratch/m4_pr10_demo/`, worktree `_scratch/pr10-cd63e21` (all git-ignored; hashes recorded in
the run logs).

## 3. Required remediation before a new M4 row / Lead approval

1. **Restore the two Route B identity tests** in `tests/integration/test_attempt_writer.py`
   (`test_routeb_identity_passes_only_with_matching_original`,
   `test_routeb_identity_fails_on_original_mismatch`) and the static test's
   `V0 == "not_run"` assertion, **or** add equivalent (or stricter) coverage in a suite that
   runs on the verification host. New route-A tests do not replace Route B identity coverage.
2. Keep the new route-A/reporting tests; target `tests/integration/test_attempt_writer.py`
   with at least the four old tests plus the two new ones (6 tests) all passing.
3. Update the PR head (and merge current `main` `328d355e`, whose delta is docs-only) so the
   verified head is the final head; if `main` gains product/test changes, re-verify.
4. Optionally include the latest Lead branch tip `98ff475` (docs 50/51/53 + probe/launcher) so
   the repo records are current; it does not change product/test content.
5. Re-run H5–H7 on the new head and request a fresh M4 row; **no merge/tag before that row is
   PASS and the Lead writes approval for the exact head**.

## 4. M4 row statement

**M4 verdict for `cd63e21`: FAIL — approval withheld.** The local test/demo measurements pass,
but the PR removes identity test coverage that the project explicitly forbids weakening, and it
is not the final head (main has advanced). M4 has **not** signed a PR verification row and has
**not** approved the merge or the `mvp-integration-2026-10-31` tag.
