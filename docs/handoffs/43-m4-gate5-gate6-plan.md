# 43 — M4 Gate 5 Route A runtime and Gate 6 / V4 calibration plan

**From:** Member 4 (independent verifier; Route A half of Gate 5 per handoff 13 §2, ratified)
**To:** Lead, Member 3 (guest/VMer), Member 5 (Gate 4 DRI, Route B half of Gate 5)
**Date:** 2026-10-29 (Asia/Hong_Kong)
**Status:** **PLAN ONLY — nothing executed.** Gate 5 stays **pending** with its Route A runtime
half `not_run`; Gate 6 stays **partial** (concrete crash accepted, symbolic half pending V4).
No gate status changes, no candidate executed, no fixture movement.
**Basis:** `docs/handoffs/41` §4 (M4 allocation), `BOARD.md`, handoff 13 §2 (Route A half of
Gate 5 is M4's), handoff 22 §6 (static placement facts), `docs/route-b/06` (Gate 6 concrete
evidence), `docs/route-b/07` and `09`/`14` (Route A placement / Gate 4), handoff 17 Appendix A
(V4 calibration plan), handoff 10 (isolation preconditions), Tech Design §V4.
**Independence:** M4 does not produce Gate 5 or Gate 6 evidence from M3's conclusions. The
guest executes; M4 verifies with its own hashes/probes and reports `PASS` / `FAIL` /
`NOT VERIFIED` (Gate 5) or `inconclusive` (V4) — never "probably".

## 1. What is already recorded, and what is missing

| Item | State now | Source |
|---|---|---|
| Gate 5 Route A **static** placement proof | recorded: one changed `PT_LOAD` (`p_filesz`/`p_memsz` `0x8e9`→`0x1000`, page-congruent, no overlap), redirect to `0x4018e9`, cave `0x4018e9–0x401fff` beyond original file-backed end, no new import/reloc/GOT/PLT, no W+X, `GNU_STACK` NX / `GNU_RELRO` unchanged | handoff 22 §6 |
| Gate 5 Route A **runtime** placement proof | **not_run** — no guest probe by M4 on the final candidate | BOARD; this plan |
| Route A real candidate for Gate 5 | **not delivered** — expected in `P3A` (M3) | 41 §3 |
| Gate 6 concrete crash | **accepted partial** — 100×`A` → SIGSEGV at `ret 0x401317`, 5/5 deterministic | docs/route-b/06 |
| Gate 6 symbolic (V4) | **pending** — angr/Z3 install reported earlier, but no completed bounded exploration and no guest access from this workspace; the 50-step smoke (`active=0`, `deadend=1`) is `inconclusive`, not a pass | handoff 10 §6, 17 Appendix A |
| Final repaired candidates | none exist; V4 on final candidates cannot run before Gate 4/5 produce them | MEMORY / README honest state |

Static facts are inputs, not Gate 5 evidence. A CI or static substitute is never a runtime pass.

## 2. Gate 5 — Route A runtime placement proof (M4 + M3 guest)

**Question:** on the **final Route A candidate bytes** that P3A delivers, is the added code
actually mapped executable, byte-identical to the file, entered at runtime, and safe for the
original control flow, under the three isolation preconditions — verified by M4, not inferred
from M3's logs?

**Preconditions (all required):**

1. `P4` delivered and its guest session/VMer path confirmed (T3.0 access record is still
   missing on the BOARD); the guest snapshot is reverted and disposable.
2. `P3A` delivered and checker-`PASS`; its `result-bundle.json` names the candidate hash and
   the edit manifest; the candidate is a separate copy (original untouched).
3. A session window with: uid 1003, `CapEff=0`, `NoNewPrivs=1`, no egress, evaluator
   unreadable, root-started wrapper, gdb available, writable work dir.
4. M4 keeps its own copies and hashes first; producer artifacts are read-only.

**Steps (in the guest via M3/VMer; M4 observes/verifies):**

1. Recompute candidate + original + manifest hashes from bytes; require original
   `aa428157…8393`, candidate hash stable across the two P3A builds (or the deviation recorded
   and reviewed), candidate hash before = after every run.
2. Re-measure the static placement from bytes (independent byte diff, program headers,
   section/relocation/import view): only the authorized intervals changed; one `PT_LOAD`
   extension; page congruence; no overlap; `< file size`; `p_memsz ≥ p_filesz`; no W+X; no new
   import/GOT/PLT/relocation; cave range referenced by no section/symbol/relocation/unwind/FDE.
3. Runtime probe on the candidate under the isolation controls:
   - `info proc mappings` shows one `r-xp` range covering the cave page;
   - memory at the cave range equals the candidate file bytes (dump + `cmp`, SHA-256 both);
   - break at the call site and the cave entry; the cave entry executes and decodes as the
     manifest's added bytes; valid path returns to the original return point; no crash before
     the cave entry.
4. Six frozen cases on the final candidate under the same session; record per-case
   rc/stdout/stderr rows. (These are placement/behaviour evidence for Gate 5; they are not
   V3 acceptance.)
5. Verdict per item: `PASS` / `FAIL` / `NOT VERIFIED`; if the guest session is unavailable or
   outside the isolation controls, the runtime item is `NOT VERIFIED` and Gate 5 stays pending —
   **not** "pass with a note".

**Evidence custody:** raw outputs under `var/jobs/m4-gate5/<run-id>/` (git-ignored); a committed
record (path `docs/handoffs/44-m4-gate5-runtime-record.md`, created only when the run exists)
citing filenames + SHA-256 and the evidence-manifest hash. M4 fills the verifier row; the Lead
approves; M4 never approves its own run.

**Coordination with M3:** when P4/P3A exist, publish an envelope
`docs/handoffs/45-m4-to-m3-guest-session.md` (same 10-line shape as `35`) requesting one bounded
guest window and naming: snapshot/chain manifest, revert requirement, uid/caps/egress controls,
gdb/readelf paths, writable work dir, expected duration, and "no host execution". No chat-only
request; if the window is unavailable, publish the blocked record and keep Gate 5 pending.

## 3. Gate 6 / V4 — bounded symbolic calibration (guest with angr/Claripy/Z3)

**Question:** does a bounded symbolic exploration on the original (and later on the final
candidates) find the out-of-bounds write, with complete accounting inside an explicit model,
domain, and budget?

**Calibration first (known-unsafe inputs):**

1. Load `original.elf` in angr with the recorded harness entry (`0x401256`) and sink
   (`0x4012b0`), `argv[1]` symbolic, stack/argv set up explicitly; record the angr/Z3 versions,
   base address, and model assumptions.
2. Calibrate on the known unsafe 50-byte and 100-byte inputs: the exploration must reach the
   OOB write to `dest`/the saved return slot and record the concrete path/counterexample.
3. If calibration does not find the known bug within budget, the result is `inconclusive`; no
   property claim is made.

**Bounded property run (only after calibration):**

- Define the input domain explicitly (e.g. length 0–128 bytes, covering the frozen 49/50/100
  boundaries), the property (no write outside `dest`/the contract's forbidden range on any
  explored path; required safe termination where the contract demands it), and the budget
  (address/step cap, wall-clock cap, solver timeout, single core). Record the budget in the
  result.
- Record exploration accounting: `active`, `deadend`, `found`, solver calls, time, and any
  unresolved states. A completed bounded exploration with a recorded property result is V4
  evidence; it is **not** V3 acceptance and not a repair proof.
- **`inconclusive`** for: solver `unknown`, timeout, incomplete exploration, missing model
  coverage, or tool failure. Gate 6 then stays **partial**; never report "safe" or "passed".
- Any result is per-binary/per-model, not a general security claim.

**Current limitation:** this workspace has no guest console and no final candidate; V4 remains
`not_run`. The earlier smoke test stays `inconclusive` and is not cited as detection.

**Evidence custody:** raw logs/JSON under `var/jobs/m4-gate6/<run-id>/`; committed record
`docs/handoffs/46-m4-gate6-v4-record.md` only at run time; hashes and budget recorded; Gate 6
status changes only on a completed exploration (Lead decision).

## 4. Timeline and next actions

| Date | Action | Owner |
|---|---|---|
| 2026-10-30 | Deliver P4/P3A/P3B; M4 reviews packages read-only (checker + A–D of checklist 42) | M3 → M4 |
| 2026-10-31 12:00–18:00 | JOIN-1 Gate 4 verification (42); if a guest window exists, schedule Gate 5 probe immediately after | M4 |
| 2026-11-01 | Gate 5 Route A runtime probe record or a `NOT VERIFIED` blocked record | M4 + M3 |
| after Gate 4/5 | V4 calibration + bounded run on final candidates; `inconclusive` if not complete; Gate 6 stays partial | M4 + M3 |

## 5. Blockers (current, concrete)

1. **No guest/VMer access from this workspace** — M4 cannot run the runtime probe or the
   symbolic calibration here; host execution is prohibited.
2. **P4/P3A not delivered** — `docs/handoffs/evidence/` contains only `README.md` (measured
   2026-10-29); no final Route A candidate exists for Gate 5.
3. **No V4 exploration completed** — the reported smoke is `inconclusive`; no angr/Z3 run
   result exists in the repo.

None of these changes a gate label: Gate 5 remains pending/`not_run`, Gate 6 remains `partial`,
fixture remains `NOT FROZEN`.

**Signature block (blank by design; filled only when a run exists):**

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier / Route A Gate 5 | M4 | — | — (none; plan only) |
| M4 Gate 6 / V4 | M4 | — | — (none; plan only) |
