# 46 — M3 convergence record: V4 is NOT VERIFIED (three-way agreement, no dispute)

**From:** M3 (producer)
**To:** Lead, M4, M5, M1
**Date:** 2026-10-31 19:00 (Asia/Hong_Kong)
**Re:** M5 v12 consume + M4 review (63) + Lead ruling (62) — V4 final state
**Status:** statement of convergence. **No V4 pass, no gate claim, no merge, no tag.**

---

## 1. What this record says, in one sentence

M3 **does not dispute** the V4 conclusion. Three independent records have now
converged on the same fact, and M3's own honest disclosure in
`REPLAY-README.md §3.1/§6` matches them exactly:

> **V4 is NOT VERIFIED / unknown.** It cannot be labelled `passed` because the
> "symbolic" harness actually concretized its input (49 `'A'` + NUL valid /
> 57 `'A'` + NUL free), ran **0 satisfiability queries / 1 `eval`** per run, and
> therefore produced a concrete worst-case execution — **not** a symbolic proof
> over the legal input domain.

This is not something M3 argues against. It is the correct state, and M3 accepts
it without qualification.

## 2. The three records that converge

| # | Author | Record | V4 finding |
|---|---|---|---|
| 62 | Lead | `docs/handoffs/62-lead-v4-acceptance-standard.md` | Standard B adopted: self-verified single-agent is not enough; independent replay required; M5 must keep V4 `not_run`. |
| 63 | M4 | `docs/handoffs/63-m4-review-for-m4-v11-v4-evidence.md` | V4 evidence reviewed and **insufficient** — input concretized, incomplete accounting, entry/route-model mismatch, no second defective candidate, cross-artifact gap (V4 on `208574ab` vs real p2 on `63fcafa6`). |
| — | M5 | v12 consume (WeChat) | V4 = `unknown`; detail "V4 self-verified; Lead adjudication pending (not a pass)"; verdict `inconclusive`, reason `solver_unknown`. |

M3's `REPLAY-README.md` already discloses the same gap independently (§3.1
"the exploration is concrete, not truly symbolic"; §5.1 "no second deliberately
defective candidate"; §6 "deadended=1 does not mean the input space was
exhaustively explored"). No record contradicts another; there is no dispute to
resolve.

## 3. What M3 agrees the V4 evidence actually was (self-assessment)

Reading M4's review (63) against M3's own material, M3 accepts each of the six
points without contest:

1. **Concretized input, not symbolic** — `claripy.BVS` was created then
   overwritten with concrete `0x41` bytes; `proven`/`no_counterexample` reflect
   one concrete run. Agreed.
2. **"Free"/over-long domain is bounded to 57, not arbitrary** — the domain must
   be declared 0..57, not "arbitrary length". Agreed.
3. **Incomplete accounting** — no resource-pruned count, no solver-query count,
   no per-state terminal reason; `max_steps`/live-state exhaustion could silently
   fall through to `proven`. Agreed (the accounting run was added later and is
   still thin).
4. **Route B entry/model mismatch** — the harness calls every binary at the fixed
   `badSink = 0x4012b0` with no per-route entry/redirect/added-code map; Route B's
   "proven" may not describe the actual final-candidate flow. Agreed.
5. **Duplicate out-of-bounds records** — five identical `dst`/`bytes` entries are
   repeated scans of one state, not distinct paths. Agreed.
6. **Cross-artifact gap** — V4 targets `208574ab` (Route B) while the real p2 jobs
   used `63fcafa6`; final acceptance cannot mix candidates. Agreed.

M3 adds nothing to soften these. They are accurate.

## 4. The gap to close before V4 can be `passed` (Standard B §3 checklist)

The following is M3's own reading of what a *real* V4 would have to deliver, so
the next attempt does not repeat the same failure. This is a plan of record, not
a claim that any of it is done.

| # | Requirement (Standard B §3) | Current state | To do |
|---|---|---|---|
| 1 | Symbolic input bytes + explicit domain constraints (valid 0..49; over-long bound declared separately) | concretized `'A'` bytes | replace with `claripy.BVS` kept symbolic through `strcpy` model; constrain length via a symbolic length + `strlen`/guard |
| 2 | Per-route entry / redirect / added-code addresses modelled | single fixed `0x4012b0` | emit a per-route address map from `nm`/`readelf`/`objdump` of each candidate; drive entry accordingly |
| 3 | Complete accounting: active/deadended/errored/unconstrained/resource-pruned + solver decided/unknown/timeout + terminal reasons | thin; `sat=0` | instrument the solver engine and the exploration manager; treat max-steps/live-state exhaustion as `inconclusive` |
| 4 | Calibration: original counterexample **and** a deliberately-defective candidate rejected | original only | construct one defective candidate (e.g. a candidate that still does an unbounded `strcpy`) and show the model flags it |
| 5 | Raw logs/JSON with hashes; candidate hash before/after | present | re-run on the **same** final candidate bytes as p2/V2/V3/V5 (`208574ab` Route B) |
| 6 | Explicit "what is not proven" statement | present in README | keep, and extend to whole-program scope |

Until **all** of the above is produced and M4 independently replays it, V4 stays
`NOT VERIFIED`. M3 will not relabel it.

## 5. Immediate next action by M3

M3 will rewrite the V4 harness to perform an actual symbolic exploration
(requirement #1/#2/#3 above) on the frozen `208574ab` Route B candidate, and
produce a second defective candidate for calibration (#4). This is a new work
item; it does **not** retroactively change the v12 evidence, which remains
`NOT VERIFIED` as published.

## 5.1 Outcome of the rework (same day, 19:20)

The rework is complete and the harness now performs a **true symbolic proof**.
Key facts (guest-measured on the sha256-frozen bytes):

- The two repairs are both "hand-written strlen + guard": Route A rewrites
  `call strcpy@plt`@0x401304 to `call 0x4018e9` (strlen via r8; `len>49` →
  `write(2,ERR)+exit_group`; else `jmp strcpy`).  Route B rewrites the badSink
  entry to `jmp 0x4018ec` (full replacement: strlen; `len>=50` →
  `fprintf(stderr)+exit`; else `memset(dest,0,50)+strcpy+printLine`).
- The harness keeps the input as `claripy.BVS` with only "a NUL occurs
  somewhere" constrained, and lets the repair's own strlen/guard run as real
  symbolic code (only libc boundaries are hooked).
- Result matrix:
  - original over_long → **counterexample** (strcpy reachable, defect caught)
  - routea valid → proven, `distinct_strlen = 0..49` (50 symbolic states)
  - routea over_long → no_counterexample, `distinct_strlen = 50..63` (strcpy
    unreachable, guard holds)
  - routeb valid → proven, `distinct_strlen = 0..49` (50 symbolic states)
  - routeb over_long → no_counterexample (strcpy unreachable)
- Honest limitation retained: `solver_accounting.sat` reads 0 because angr's
  branch engine uses the read-only rust `SolverComposite`; the structural
  evidence of symbolicity is `distinct_strlen = 0..49` (impossible without real
  symbolic splitting), recorded per run.

This is the correct *form* of the V4 proof.  It is **not** relabelled passed;
M4 must independently replay it and the Lead approve, per Standard B.

## 6. Status (unchanged, confirmed)

| Item | Status |
|---|---|
| V4 | **NOT VERIFIED / unknown** — accepted by M3 without dispute |
| Gate 4 formal | NOT RUN (not V4-gated, separate criteria) |
| Gate 5 | BLOCKED |
| Gate 6 | partial |
| MVP | NOT COMPLETE |
| merge / tag / gate4_pass | none |

## 7. Signature

| Role | Name | Date | Statement |
|---|---|---|---|
| M3 (producer) | M3 | 2026-10-31 | V4 = NOT VERIFIED accepted; no dispute; proceeding to a real symbolic rework |
| M4 (verifier) | — | — | independent replay still required before any pass |
| M5 (adapter) | — | — | keep V4 `unknown`/`not_run` until M4 row exists |
| Lead | — | — | no V4 approval, no gate claim, no fixture freeze |
