# Decision request: V4 toolchain and guest isolation

**From:** Member 4 (verification)
**To:** Lead and team
**Date:** 2026-10-20
**Why now:** These two items block F4 acceptance and candidate execution. Neither member 4 nor
member 3 can resolve them alone; they need a team decision.

---

## Decision 1: install the V4 verification toolchain?

**Current state (measured by member 3).** The Ubuntu 24.04 guest has **no angr / Claripy / Z3,
no LIEF, no clang, and no Ghidra/JDK**. Capstone and pyelftools are present but only
import-tested.

**Impact.** V4 (bounded symbolic security) is a core F4 acceptance obligation. Without the
toolchain:

- no candidate can be checked for the out-of-bounds write property;
- gate 6 can only be satisfied by concrete crash evidence, not by symbolic detection;
- the MVP cannot honestly claim F4.

**Options.**

| Option | What it means | Cost / risk |
|---|---|---|
| **A. Install now** | member 3 installs angr/Claripy/Z3/LIEF/clang/Ghidra in the guest, then smoke-tests | Guest has NAT; setup time; possible dependency conflicts (angr/Z3 versions) |
| **B. Record `unsupported`** | V4 is marked `unsupported` with the missing-backend reason | F4 cannot be shown; MVP acceptance is partial; honest but weak |

**Recommendation: A, time-boxed to today.** If installation or the smoke test fails, fall back
to B and record the failure reason — do not leave V4 silently pending.

## Decision 2: fix guest isolation before running any candidate?

**Disclosed by member 3 (not hidden):**

1. the `lab` user has passwordless sudo — jobs are not unprivileged;
2. outbound NAT is reachable — no per-job egress block;
3. the resize deleted the only snapshot — **no disposable reset point**;
4. tools are not on a read-only mount separate from the job workspace.

**Impact.** These do not block fixture construction, but they block executing a candidate.
AGENTS.md and the Tech Design require unprivileged execution, no network during a job, and
snapshot reset. Running a candidate under the current conditions would make any "isolated
execution" claim false.

**Minimum fix before the first candidate enters the guest:**

- take a clean snapshot after the toolchain is frozen;
- block job-time egress;
- run the job as an unprivileged user (no passwordless sudo);
- read-only tool mount (can follow, but must be recorded if not done).

**Recommendation: treat these three as a hard precondition for candidate execution.** Fixture
construction can continue, and the fixture can freeze, but no candidate run happens until the
snapshot, egress block, and unprivileged user exist.

## What we need from you

1. **Approve or reject Decision 1**, and name the owner and deadline.
2. **Confirm Decision 2** is a precondition for candidate execution (not for the fixture freeze).
3. **State the implication for the 2026-10-21 fixture freeze** if either decision slips.
