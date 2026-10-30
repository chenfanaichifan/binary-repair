# 57 — Lead: PR #10 fix verified on branch, approval still withheld until head includes it

**From:** Lead
**To:** M1 (PR owner), cc M4, M5
**Date:** 2026-10-29 19:14 (Asia/Hong_Kong)
**Re:** PR #10 — https://github.com/chenfanaichifan/binary-repair/pull/10
**Fix verified by M4:** `691c7b21a70218c28ef9adc50900f3d4ee30a3c7` (branch
`origin/member-5/pr10-test-fix`, parent `cd63e21`)
**M4 fix-verification row:** `docs/handoffs/56-m4-pr10-test-fix-verification-691c7b2.md`,
SHA-256 `F4E7CFD56B491F786D237C0C926C2B6840F74F00AC1BC93EF0D653598E6829E9`
**Current PR head:** `ce40aaff03f8d371c80a8755aa17b36f5b37b2a4` — **does not contain the fix**
**Verdict: APPROVAL STILL WITHHELD — DO NOT MERGE, DO NOT TAG.**

## What is verified

- `691c7b2` restores both Route B identity tests and the static `V0 == "not_run"` assertion,
  keeps the Route A tests, adds no skip/xfail, and changes no production code.
- Targeted file: **6 passed** (with the host measurement helper; plain run hits the known
  `tmp_path` sandbox defect, not test failures).
- Acceptance: **29/29**. Full suite on the fix commit: **246 collected / 237 passed /
  2 skipped / 7 environment errors / 5 uncollectable / 0 assertion failures**. No secret/client
  binary; oracle/acceptance/fixture unchanged.

## Why approval is still withheld

The PR #10 head is still `ce40aaf` (merge of old `cd63e21` with main `cf2f46d`), and its
`tests/integration/test_attempt_writer.py` is still the weakened 4-test version. `691c7b2` is
not an ancestor of `ce40aaf`. M4's earlier FAIL row (`docs/handoffs/54`) therefore still applies
to the current PR head; a fix commit that is not in the PR cannot be approved.

Also, current remote `main` is `c9dd8d32` (two docs-only commits past `cf2f46d`), so the final
head must sync it.

## M1's required action

```bash
git fetch origin member-5/pr10-test-fix
git cherry-pick 691c7b2
git fetch origin main && git merge origin/main   # current main c9dd8d32
git push origin HEAD:integration/consolidation-final-2026-10-29
```

Then notify M4 with the new head SHA. M4 re-runs on that exact head (targeted 6/6, acceptance,
full suite, demo, secret scan, oracle/fixture diff, Gate-record check). **New head ⇒ previous
M4 row/approval wording is void.**

## What the eventual approval will cite

Only after a **PASS M4 PR-head row for the new exact head** exists, the Lead approval record will
cite: **PR #10**; the new **head SHA**; the **M4 row file + SHA-256** for that head; the planned
GitHub merge commit; and tag **`mvp-integration-2026-10-31`**.

## Boundaries

- **Gate 4 remains `NOT RUN`**; this is integration verification only, not a gate pass. P3B
  provenance hold (`docs/handoffs/53`) remains; Gate 5 `51` unsigned; fixture `NOT FROZEN`.
- **M4 verifier = Lead same person/operator** (two AI windows of one person): the M4 row and this
  Lead row are not independent two-person signatures; no independent-human-review claim.

## Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead approval (PR #10) | Lead | — | **WITHHELD**; re-issue only for a PASS M4 row on the new head |
| M4 verifier | M4 | 2026-10-29 | fix `691c7b2` PASS (`56`); PR head `ce40aaf` still FAIL/blocked |
