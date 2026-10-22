# 10 — Decision record: V4 toolchain and guest isolation (reply to handoff 07)

**Recipient:** Member 3 (guest owner), Member 4 (verification), Member 5, team
**From:** Lead
**Date:** 2026-10-22
**Decision:** **Approve Option A (time-boxed install) and confirm the isolation preconditions.**
**Basis:** `07-v4-isolation-decision.md` (M4 recommendation, M3 disclosures); `AGENTS.md`
(snapshot instead of mutating shared state; no host execution; missing is not passing);
Tech Design §3 (jointly tested tool set).

---

## 1. Decision 1 — install the toolchain: APPROVED, Option A, time-boxed

Approved scope, in the guest:

| Group | Tools | Needed for |
|---|---|---|
| repair side | clang/LLVM, LIEF, Ghidra + JDK 21, Patcherex2 | gate 4 (Route B round trip), Route A analysis |
| verifier side | angr, Claripy, Z3 | V4 bounded symbolic security |

Use one jointly tested set (Tech Design §3): record OS/kernel, Python/JDK, Ghidra release,
backend commit, compiler flags, dependency lock, solver versions, and the guest image hash.

- **Owner:** Member 3.
- **Verifier:** Member 4 checks the recorded evidence and reports `installed_verified` or the
  exact failure; it does not accept "installed" without a version output and a smoke test.
- **Deadline:** **2026-10-23 18:00 Asia/Hong_Kong** (24 h from this record).
- **Success evidence:** for each tool, version output plus one smoke test that actually
  imports/exercises it; recorded in `docs_BinaryRepair/environment-baseline.md` or the
  existing VM profile.
- **Failure path:** if install or smoke test fails inside the box, record the exact command
  and error and report the failure **before** the deadline. The V4 obligation then stays
  `not_run` → `inconclusive` and the MVP cannot claim `success_within_scope`. Do not install
  from an unverified mirror, never execute the sample on the host, and never mark V4 passed
  without the solver producing evidence.
- The repair-side tools are required for gate 4 independently of V4; only the solver group
  is the part that can fall back to `unsupported`/`not_run`.

## 2. Decision 2 — isolation: CONFIRMED as a hard precondition for candidate execution

Before any candidate (Route A or Route B) executes in the guest, all three must hold:

1. a clean snapshot taken **after** the toolchain is frozen, used to reset between runs;
2. **job-time egress blocked** (no network while a job runs);
3. an **unprivileged execution user without passwordless sudo**.

Tracked, not hard-blocking: tools on a read-only mount separate from the job workspace; if
deferred, record the deferral. Member 3 executes, Member 4 verifies by evidence. Without all
three, a candidate run is not isolated: the result is not usable as acceptance evidence and
must be reported as `not_run`/`unsupported`, never as a pass. Host execution remains
forbidden in every case.

## 3. Implication for the fixture freeze

- The fixture stays **NOT FROZEN**. Gates 3–5 must be evidenced first (handoff 03 §3).
- **Static work can continue now**: gate 3 (Route A layout/feasibility audit under handoff
  09) and gate 5 planning do not need the isolation fix.
- **Gate 4 is an execution proof**: it starts only after the isolation preconditions hold
  and the repair-side tools are installed.
- The V3 oracle, `valid.json` / `invalid.json`, and the manifest set hash are **not** changed
  by this decision. Any fixture change still needs a new freeze.
- The 2026-10-21 freeze date has slipped. No new date is promised here; it is set when the
  gates 3–5 evidence exists.

## 4. What changes on the status board

| Item | Before | After this decision |
|---|---|---|
| Gate 4 (Route B round trip) | NOT RUN | **NOT RUN — environment work in progress** (owner M3, deadline above); not a repair result |
| V4 bounded symbolic | not run (no toolchain) | **toolchain install in progress**; still `not_run` until solver evidence exists |
| Gate 3 (Route A) | scope ruling pending | **NOT RUN, scope resolved** (handoff 09) — unchanged by this record |

## 5. Acceptance of this decision

- Lead: approved 2026-10-22 (Decision 1 = A, Decision 2 = confirmed).
- Member 4: recommendation quoted above; asked to verify the evidence when M3 reports.
- Member 3: accepts the deadline and owns the guest work; report before the deadline if it
  cannot be met, not after.

**Confirmation log.** 2026-10-22 — Decision 1 approved as Option A (time-boxed to
2026-10-23 18:00); Decision 2 confirmed as a hard precondition for any candidate execution;
fixture stays NOT FROZEN; the oracle and manifest are unchanged.

---

## 6. Status update — 2026-10-22 evening

Member 3 reports the `toolchain-v4-ready` snapshot is ready. This is **not accepted yet**:
Member 4 must still verify the version outputs, the smoke tests, and the image hash, and the
three isolation preconditions must be confirmed before any candidate run. Deadline unchanged
(2026-10-23 18:00). Gate 4 additionally waits on M5's `routeb/` scripts (handoff 09 §11.5).
