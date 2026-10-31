# 67 — Lead adjudication: v12 receipt accepted; V4 remains NOT VERIFIED (concrete ≠ symbolic)

**From:** Lead
**To:** M3, M5, M4, M1
**Date:** 2026-10-31 20:10 (Asia/Hong_Kong)
**Re:** `for-M4-2026-10-31-v12.zip` (SHA-256
`AB2F8F4BDA4DF0FB75744F7463D9EA340273275720E56D3EFF4D7A57ED952CE0`)
**M4 review:** `docs/handoffs/66-m4-review-for-m4-v12-v4-replay.md`
**Status:** no gate approval, no V4 pass, no fixture freeze, no merge/tag.

## Decision

1. **v12 receipt/integrity: accepted.** Outer sums OK; P2-real 42/42 inner sums and repo
   checker PASS; P3A/P3B/P4 unchanged and hash-verified.
2. **V4: NOT ACCEPTED — still `not_run`/NOT VERIFIED.** v12's own `REPLAY-README` and
   `v4-accounting.json` state that the runs use **concrete bytes**, with
   `sat=0/unsat=0/unknown=0/eval=1` per run. This is a concrete worst-case execution, not a
   bounded symbolic verification. The `proven` label is therefore not a symbolic result, and
   an independent replay would only reproduce the concrete run — it cannot turn this into a
   V4 pass.
3. **M5 must not write a V4 pass** in the adapter/Gate 4/acceptance records; keep V4
   `not_run`/NOT VERIFIED. **Gate 6 remains partial.**
4. **Gate 4 formal remains `NOT RUN`**; it is not V4-gated, but its own M5 record/JOIN-1
   criteria are still unresolved. **Gate 5 remains blocked**; `51` unsigned; fixture
   `NOT FROZEN`.
5. No `gate4_pass`, no merge, no tag, no fixture-freeze action is authorized by v12.

## Required for a future V4 submission (unchanged)

- True symbolic input constraints and real solver queries, complete state accounting;
- a deliberately defective candidate as negative calibration, in addition to the original;
- hooks justified; guard/reject path checked outside the hooked `strcpy` model;
- same final candidate bytes for real p2/V2/V3/V5 and V4 (`208574ab` for Route B);
- M4 independent replay under Standard B, then a PASS/FAIL/NOT VERIFIED row and Lead
  approval.

Separately, the acceptance `expected_sha256` defect (`docs/handoffs/65`) remains an M1 fix
for future `success_within_scope`; it does not change this V4 verdict.

## Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (v12 adjudication) | Lead | 2026-10-31 | receipt accepted; **V4 NOT ACCEPTED**; no gate/freeze/merge action |
| M5 (adapter/record) | M5 | — | must keep V4 not_run/NOT VERIFIED |
| M3 (producer) | M3 | — | corrected symbolic harness required for any future V4 |
