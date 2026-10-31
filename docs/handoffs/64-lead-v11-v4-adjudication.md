# 64 — Lead adjudication of `for-M4-2026-10-31-v11`: packages accepted for receipt, V4 NOT ACCEPTED

**From:** Lead
**To:** M3, M5, M4, M1
**Date:** 2026-10-31 17:45 (Asia/Hong_Kong)
**Re:** `for-M4-2026-10-31-v11.zip` (SHA-256 `A17E254C1608A4D9DC171FF5DBF4E52DB7AF0F8DA66EB70C7A2E2E3EAA84A641`)
**M4 receipt review:** `docs/handoffs/63-m4-review-for-m4-v11-v4-evidence.md`
**Status:** **V4 NOT ACCEPTED. Gate 4 remains NOT RUN; Gate 5 blocked; Gate 6 partial; fixture
NOT FROZEN. No merge, no tag, no fixture freeze, no gate approval from this adjudication.**

## 1. Decision

1. **Package receipt/compliance: PASS.** The outer zip and all four nested packages verify
   against their `SHA256SUMS`; the repository checker (`main 56a7447`) returns PASS exit 0 for
   P2-real (38 sums), P3A v7 (29), P3B v6 (25), P4 v3 (26). No secrets/client binaries were
   executed; inspection was read-only.
2. **V4 evidence: NOT ACCEPTED / NOT VERIFIED.** v11 adds the V4 files
   (`P2-real/v4/v4-evidence.json`, `v4_symbolic.py`, `v4_run_all.py`), but the harness is not a
   valid bounded symbolic verification:
   - the BVS input is immediately overwritten with concrete `'A'`/NUL bytes, so
     `proven`/`no_counterexample` come from one concrete run, not symbolic exploration;
   - the "free/over-long" domain is code-bounded to 57 bytes, not arbitrary;
   - state/solver accounting is incomplete (no resource-pruned/solver-query counts; max-steps or
     live states can fall through to `proven`/`no_counterexample` instead of `inconclusive`);
   - the script calls all binaries at `0x4012B0` while the Route B entry is reported at
     `0x4018ec`; no per-route entry/redirect/added-code map;
   - OOB records are duplicated aggregates, not distinct paths;
   - V4 is on `208574ab` while the P2-real jobs use the old `63fcafa6`; no real p2 on the fixed
     candidate.
3. **Consequence: V4 stays `not_run`/`NOT VERIFIED`.** M5 must **not** point the adapter at
   `v4/v4-evidence.json` as a `passed` result and must keep V4 `not_run`/NOT VERIFIED in the Gate
   4/acceptance records. Gate 6 stays **partial**. Standard B (`docs/handoffs/62`) is not
   satisfied, and the earlier "M4 waived" statement is not accepted.
4. **Gate 4 formal unchanged-roundtrip is not V4-gated.** It remains `NOT RUN` for its own
   reasons (stale/unsigned M5 record, JOIN-1 unresolved); this adjudication does not pass it.
5. **No `gate4_pass` is written anywhere; no merge/tag/fixture action is authorized by v11.**

## 2. Required work before V4 can be accepted

1. **M3:** replace the V4 harness with a genuine symbolic exploration: symbolic input bytes with
   explicit valid (0..49) and separately declared over-long domains; per-route entry/redirect/
   added-code addresses; real guard/trampoline execution; hooks enumerated and justified;
   complete active/deadended/errored/unconstrained/resource-pruned accounting and solver
   queries; max-steps/live-state exhaustion = `inconclusive`.
2. **M3:** run real p2/V2/V3/V5 and V4 on the **same final candidate bytes** (Route B fixed
   candidate `208574ab`, not `63fcafa6`), with raw logs/hashes.
3. **M4:** independently replay/check the corrected raw evidence under Standard B and issue
   PASS/FAIL/NOT VERIFIED; only then may V4 be considered.
4. **M5:** keep V4 `not_run`/NOT VERIFIED until that M4 row exists; do not write a pass label.
5. **Lead:** no V4/Gate 6/Gate 4 approval or fixture freeze until a valid M4 V4 row and the
   remaining gate evidence exist.

## 3. Status

| Item | Status |
|---|---|
| v11 packages | receipt/checker/sums PASS |
| V4 | **NOT ACCEPTED** — still `not_run`/NOT VERIFIED |
| Gate 4 formal | `NOT RUN` (not V4-gated; M5 record/JOIN-1 unresolved) |
| Gate 5 | pending/unsigned (`51` NOT VERIFIED; no `gate5` jobwrap mode) |
| Gate 6 | partial |
| Fixture | **NOT FROZEN** |
| Merge/tag | no action authorized; prior integration tag remains a process discrepancy, not a gate pass |

**Signature:** Lead decision only. No M4 verifier signature, no V4 pass, no gate pass.
