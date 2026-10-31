# 69 — M4 receipt review: `for-M4-V4-z3-2026-10-31.zip` — genuine z3 symbolic model, independent replay still pending

**From:** M4 (independent verifier)
**To:** Lead, M3, M5
**Date:** 2026-10-31 20:35 (Asia/Hong_Kong)
**Source:** `D:\电脑管家迁移文件\微信聊天记录搬家\xwechat_files\wxid_046thzahte0q12_d93a\temp\RWTemp\2026-10\329ab3e3ac2040fc381635ebd18dcb3c\for-M4-V4-z3-2026-10-31.zip`
**Outer SHA-256:** `32097EA3AC19E6EEEF8CD4B4E6B768793009B3A8DCCEE9AC4F16775354A0F27A`
(35,033 B; read-only; no model/binary executed on this host — host has no z3 and symbolic analysis belongs to the guest)
**Status:** receipt review only. **No V4 pass, no Gate 4/6 pass, no freeze/merge/tag.**
Standard B (`docs/handoffs/62`) remains in force.

## 1. Receipt / integrity — PASS

- Outer `SHA256SUMS`: all 6 entries recomputed OK (`README.md`, `original.elf`,
  `routea-candidate.elf`, `routeb-candidate.elf`, `v4-result.json`, `v4_model.py`).
- Candidate hashes independently recomputed and match the frozen facts:
  original `aa428157…8393`, Route A `c4a159…aa82`, Route B fixed `208574ab…6717`.
- The package is self-contained: model script + result JSON + the three candidate bytes.

## 2. What is new — this is genuinely symbolic, unlike v11/v12

`v4_model.py` is a pure-z3, byte-level model (no angr engine):

- symbolic `data : Int → BV8` plus symbolic length `L`, constrained
  `data[L] == 0` and `data[i] != 0` for `0 ≤ i < L`;
- domain `L ∈ [0, 64]`, dest capacity 50 (including NUL), valid domain `0..49`;
- property queried as `guard_pass(L) AND overflow(L≥50)`;
- exact solver accounting for every `check()`: counts, sat/unsat/unknown, time, seed;
- same-frozen-candidate hash check at startup (mismatch refuses to run);
- **negative calibration included**: a deliberately defective guard (`len > 50` instead of
  `len > 49`) must be SAT; the original must be SAT; routea/routeb must be UNSAT.

`v4-result.json` reports (reported, not yet replayed by M4):

| candidate | verdict | solver accounting |
|---|---|---|
| original | **sat** (strlen 64 counterexample) | 1 check, sat=1 |
| routea `c4a159` | **unsat** | 1 check, unsat=1 |
| routeb `208574ab` | **unsat** | 1 check, unsat=1 |
| defective (off-by-one) | **sat** (strlen 50) | 1 check, sat=1 |

This fixes the concrete-input/0-SAT defect of v11/v12. It is real z3 symbolic evidence over the
declared bounded model.

## 3. Remaining limitations — why V4 is still NOT VERIFIED

1. **It is a hand-coded function-level guard model, not symbolic execution of the candidate
   binary.** The guard formulas (`L≤49` / `L<50`) and the `strcpy` write model are written by the
   producer from disassembly; the model does not read/execute candidate instructions. An
   independent verifier must check the guard thresholds and control flow against the actual
   candidate bytes (Route A redirect `0x401304→0x4018e9`; Route B entry/`0x4018ec`; invalid path
   exits before `strcpy`) before trusting UNSAT.
2. **Bound 64 only.** Inputs beyond strlen 64 are not covered; the README says this. The
   acceptance claim must state "within bound 64".
3. **Hooks/assumptions**: `strcpy` is the only modeled dest write; `printLine`/`fprintf` are
   read-only; `exit(1)` leaves badSink. These must be checked for both candidates (including
   `memset(dest,0,50)` in Route B, which is within dest and not modeled).
4. **Single-agent/self-verified**: z3 run and result JSON are produced by M3. Standard B requires
   an independent replay (same model source, frozen candidate bytes, same solver/version) and,
   ideally, a model-fidelity check. M4 cannot run z3 on this host (no z3 module; symbolic
   analysis belongs to the guest) and has no guest console in this session, so replay is
   **pending**.
5. Pre-existing Gate facts: Gate 4 formal remains `NOT RUN`; M5 Gate 4 record is DRAFT with M4/
   Lead rows blank; Gate 5 blocked; V4 is not a Gate 4 formal criterion but remains the
   acceptance-ladder gap.

**V4 verdict: NOT VERIFIED (pending independent replay + model-fidelity check).** This package
is materially closer to V4 than v11/v12 and is the right raw material; it is not yet a pass.

## 4. Replay plan for M4 (guest; no host execution)

- Guest with z3 5.1.0 / angr venv (M3 reports); verify `v4_model.py` hash `…` against this package.
- Re-run `python v4_model.py` in a copy of the package; compare `v4-result.json` (including
  solver accounting) byte-for-byte or field-by-field; candidate hashes must match.
- Independently disassemble/read `badSink`/redirect/cave for both candidates and verify the
  guard formula and exit-before-strcpy claim in the model; record commands/output.
- Only then fill M4 V4 row PASS/FAIL/NOT VERIFIED; if model fidelity or replay fails → NOT
  VERIFIED/FAIL, never pass.

## 5. Status

| Item | Status |
|---|---|
| v4-z3 package receipt | PASS |
| V4 | **NOT VERIFIED** — true z3 model, independent replay/model fidelity pending |
| Gate 4 formal | `NOT RUN` (unchanged; not V4-gated) |
| Gate 5 | `BLOCKED`; `51` unsigned |
| Gate 6 | partial |
| Fixture | **NOT FROZEN** |
| Merge/tag | no action; no `gate4_pass` |

**Signature:** M4 receipt review only; no V4/Gate signature.
