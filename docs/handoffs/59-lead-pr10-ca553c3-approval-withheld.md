# 59 — Lead: PR #10 approval withheld for head `ca553c3` (p2 acceptance weakening)

**From:** Lead
**To:** M1 (PR owner), cc M4, M5
**Date:** 2026-10-29 19:45 (Asia/Hong_Kong)
**Re:** PR #10 — https://github.com/chenfanaichifan/binary-repair/pull/10
**Head reviewed:** `ca553c3d151144aa7488903491aed5a6b704fbec` (tag `m1-pr10-head-ca553c3`)
**Base:** `main f5c36f1` (current remote main at check)
**M4 row:** `docs/handoffs/58-m4-pr10-head-verification-ca553c3.md`,
SHA-256 `7CB570CEC5128542887995693BD76E773DA99A149B3E955FBD088362ED07360C`
**Verdict: APPROVAL WITHHELD — DO NOT MERGE, DO NOT TAG.**

## 1. What the new head fixed (acknowledged)

- Restored the two Route B identity tests and the static `V0 == "not_run"` assertion; kept the
  Route A tests; no skip/xfail; no production diff for that fix.
- Head includes main `f5c36f1`, latest Lead records (`06518b9`/`98ff475`) and the transfer bundle
  tip `64c6f3e`; PR base/tag/head are consistent.
- Targeted tests 6/6; acceptance 29/29; demo exit 0; local verifiable full suite 246 collected /
  237 passed / 2 skipped / 7 environment errors / 5 uncollectable / 0 assertion failures; no
  secret/client binary; oracle/acceptance/fixture unchanged; Gate 4 record still DRAFT.

## 2. Why approval is still withheld

**Hard blocker — H11: `tools/p2_acceptance.py` was weakened.**

- Removed the `VALID_OUTCOMES` membership check: now any non-`None` route outcome (e.g.
  `"passed"`) is accepted.
- Removed the old rejection of `success_within_scope` when all obligations are `not_run`;
  the new code explicitly `pass`es.
- `--synthetic` only labels the JSON summary; it does not enforce that synthetic data cannot be
  treated as a real p2/Gate 4 pass. No negative tests cover these behaviours.

Gate 4's required real p2 exit 0 depends on this tool. Weakening it would let a false Gate 4
condition pass; project rule: a test/acceptance gate must never be weakened.

**Unverified environment items (not passes):**

- M1 reports `252 collected / 249 passed / 2 skipped / 1 failed (Windows readelf)`; this host
  cannot collect the 13 ELF-dependent tests (capstone/elftools absent), so that failure is not
  independently verified. It must be classified as environment `not_run` with the exact nodeid
  and traceback, or run on Ubuntu with readelf present.
- `check_handoff.py --self-test` is reported PASS by M1; on this host it aborts in temp cleanup
  (`PermissionError [WinError 5]` sandbox defect), so it is `NOT VERIFIED` here. Provide the log
  from a host where cleanup works.

## 3. Required remediation (then a new head and fresh M4 row)

1. In `tools/p2_acceptance.py` restore:
   - `route.outcome` membership in the six valid outcomes;
   - rejection of `success_within_scope` + all obligations `not_run`;
   - `--synthetic` enforcement/labelling so synthetic data can never be cited as a real p2/Gate 4
     pass; real mode rejects synthetic/demo data.
2. Add negative tests for invalid outcome, success+all-not_run, and synthetic-vs-real separation
   in a suite that runs on the verification host.
3. Supply the exact readelf failure nodeid/traceback and checker self-test log (or run on Ubuntu).
4. Keep the `test_attempt_writer.py` restoration; push a new head; notify M4.

Only after a **PASS M4 row for the exact new head** may the Lead write approval citing: **PR #10**;
the new **head SHA**; the **M4 row file + SHA-256**; the planned GitHub merge commit; and tag
**`mvp-integration-2026-10-31`**. New head ⇒ previous rows/approval wording are void.

## 4. Boundaries

- **Gate 4 remains `NOT RUN`**; this is integration verification only. P3B provenance hold
  (`docs/handoffs/53`) remains; Gate 5 `51` unsigned; fixture `NOT FROZEN`.
- **M4 verifier = Lead same person/operator** (two AI windows of one person): the M4 row and this
  Lead row are not independent two-person signatures; no independent-human-review claim.

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead approval (PR #10) | Lead | — | **WITHHELD**; re-issue only after a PASS M4 row on the new head |
| M4 verifier | M4 | 2026-10-29 | head `ca553c3` = **FAIL** (`58`); fix/test restoration PASS, p2 tool weakening FAIL |
