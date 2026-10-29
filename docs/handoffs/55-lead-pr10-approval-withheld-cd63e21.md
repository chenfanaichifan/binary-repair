# 55 — Lead: PR #10 approval NOT granted (head cd63e21) — hold record

**From:** Lead
**To:** M1 (PR owner), cc M4, M5
**Date:** 2026-10-29 18:52 (Asia/Hong_Kong)
**Re:** PR #10 — https://github.com/chenfanaichifan/binary-repair/pull/10
**Head reviewed:** `cd63e21d690f4dff9a86ed4cd552e57aa41e682f`
**M4 PR-head verification row:** `docs/handoffs/54-m4-pr10-head-verification-cd63e21.md`,
SHA-256 `02CECFA25933CB7C21C283DB95F06C7B169B2D3BBD2123331BDD5A97ECF5B913` (7,482 B)
**Verdict:** **APPROVAL WITHHELD — DO NOT MERGE, DO NOT TAG.**

M1 correctly states the merge rule: no merge and no tag before the M4 row and the Lead's written
approval exist. **The M4 row is FAIL**, so the Lead approval row cannot be issued for this head.

## 1. Why approval is withheld

| # | Finding (from M4 row §1) | Required action |
|---|---|---|
| 1 | **H8 — test weakening (FAIL).** The PR removes the two Route B identity tests added in `986a49f` (`test_routeb_identity_passes_only_with_matching_original`, `test_routeb_identity_fails_on_original_mismatch`) and the static-bundle `V0 == "not_run"` assertion; the new route-A tests do not replace that coverage. This violates the project rule that a test/verification gate must not be weakened. | Restore the two tests and the V0 assertion (or add equivalent/stricter coverage in a suite that runs), keep the new tests; rerun. |
| 2 | **H3 — bundle/transfer traceability.** Head **contains** the pinned bundle/transfer tip `64c6f3e`, but is **not equal** to it; the latest Lead branch tip `98ff475` (docs 50/51/53 + probe/launcher) is absent. | Update the head if the team wants the current records included (docs/scripts only), or explicitly accept the omission in the PR; either way the next M4 row must state which. |
| 3 | **H11 — base drift.** PR base is `ffca9a0`; current `main` is `328d355e` (one docs-only commit). The final merge commit would include changes not in the verified head. | Merge current `main` into the PR and re-run; if `main` gains product/test changes, full re-verification. |

The local measurements themselves are good (H5 29/29 acceptance; H6 244 collected / 235 passed /
2 skipped / 7 environment errors / 5 uncollectable with 0 assertion failures; H7 demo exit 0;
H4 no secret/client binary; H9 oracle/acceptance/fixture files unchanged; H10 Gate 4 record is
still DRAFT). They do not outweigh the test removal.

## 2. What a valid approval will look like (after remediation)

When M1 supplies a **new head** with:

1. the two Route B identity tests + static `V0 == "not_run"` assertion restored (target
   `tests/integration/test_attempt_writer.py`: 4 old + 2 new tests = 6 passing),
2. current `main` merged in (or the PR base explicitly updated and the merge result explained),
3. fresh M4 measurements on that exact head (acceptance 29/29; full suite with its actual
   counts; demo exit 0; no secret/client binary; no oracle/acceptance/fixture edit; Gate 4 still
   DRAFT/NOT RUN),
4. a **PASS** M4 PR-head row for that exact head,

the Lead will write an approval record that cites:

- **PR #10**
- the **exact verified head SHA** (not `cd63e21`, unless it is unchanged after the fixes —
  which cannot happen because restoring tests changes it),
- the **M4 row file path + SHA-256** for that head,
- the planned merge action: GitHub merge of the PR at that head, producing the merge commit,
  followed by tag **`mvp-integration-2026-10-31`**.

Until then: **no merge, no tag, no approval row.** `cd63e21` is not approved despite being
draft/mergeable on GitHub.

## 3. Boundaries and identity

- **Gate 4 remains `NOT RUN`.** This PR approval is an integration/branch-merge approval only; it
  does not close Gate 4, does not approve P4/P3B, does not freeze the fixture. P3B provenance hold
  (`docs/handoffs/53`) remains in force.
- **M4 verifier = Lead same person/operator** (two AI windows of one person) — recorded limitation.
  The M4 row and this Lead row are **not independent two-person signatures**; if the client
  requires a genuinely independent second approver, that is not satisfied and must be recorded.
- A new M4 row or a new head **voids** any prior approval wording; never merge a mismatch.

## 4. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead approval (PR #10) | Lead | — | **WITHHELD / NOT GRANTED** for `cd63e21`; re-issue only after a PASS M4 row on the final head |
| M4 verifier | M4 | 2026-10-29 | `docs/handoffs/54…` = **FAIL**; no verifier signature for merge |
