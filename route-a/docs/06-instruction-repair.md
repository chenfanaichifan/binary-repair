# 06 — Instruction repair investigation

Work item 7. Status: **started — measured constraints recorded, no verdict**
(2026-10-20). Gates 3 and 5 are owned by Member 5 and have not run, so no
strategy is claimed feasible or infeasible yet.

## Purpose

Before the team commits to Route A, decide whether the vulnerable site can be
repaired by an instruction-level edit, and what evidence would support that.

Route A in the project definition: patch instructions in a copy of the original
binary; check encodings, placement, affected transfers; keep the original intact.

## Candidate strategies to investigate

Each strategy gets: feasibility verdict, required edits, risks, and the evidence
that would prove it works. Do not pick one before investigating the others.

### A. Guard before the copy

Insert a length check that jumps to a defined error path when the input is too
long.

- Feasible? TBD
- Space available at the site? TBD
- Redirect target for the error path? TBD

### B. Replace the unbounded copy with a bounded copy

Change the copy operation so it cannot exceed the destination buffer.

- Feasible? TBD
- Does an in-binary bounded routine exist (e.g. `strncpy`) and is it linkable
  through the existing PLT? TBD
- Semantics preserved on valid input (NUL termination, truncation rules)? TBD

### C. Redirect to added code

Place a small block of code in unused space and branch to it.

- Feasible? TBD
- Requirements: code cave or new section, entry jump, displaced bytes, stack
  alignment, `%rip`-relative operands TBD

## Constraints to respect

- Preserve existing protections (NX, RELRO, canary). If a protection cannot be
  preserved, the outcome is "unsupported".
- Never overwrite the original file; patch a copy.
- Record every changed byte region, added bytes, and any redirection.
- Instruction boundaries: a patch must not split an existing instruction.
- Unknown live registers/flags at the site ⇒ treat as unsupported until proven
  otherwise.

## Measured constraints for this fixture (2026-10-20, recorded — no verdict yet)

These come from `04-instruction-inspection.md` and `03-architecture.md`; they
narrow what a Route A candidate can do here. They are facts, not a feasibility
claim.

| Constraint | Value | Consequence |
|---|---|---|
| Patch site | `call strcpy@plt` at `0x401304`–`0x401308` (5 bytes) | a guard must be inserted before it, or the call redirected; the five bytes cannot be split |
| Free registers at the site | `rdi = &dest`, `rsi = data`, `rdx = data`, `rax = &dest`; `rcx`, `r8`–`r11` are caller-saved and unused | a guard can use `rcx`/`r8`–`r11` without spilling; `rdi`/`rsi` must still hold the arguments for the original call if it is kept |
| Branch reach | no conditional branches in the function; only the two `call`s | a guard needs one added conditional branch back to `0x401309` or forward to the epilogue `0x401316` |
| Executable space | executable `LOAD` segment ends at `0x4018e9`; highest code symbol (`printLine`) ends at `0x4013a6` | candidate cave is above `0x4013a6`, but its exact free size needs `readelf -S`, which is **not captured** |
| IBT / CET | `IBT: Enabled`; function starts with `endbr64` | an *indirect* branch into added code needs an `endbr64` landing pad; a direct `call`/`jmp` to a fixed address does not |
| Emitting the frozen stderr string | requires a data string plus a `fputs`/`fwrite`/`write` call, i.e. added data **and** added code | this is strategy C, not a minimal instruction change; whether it is inside Route A's scope is a **scope ruling for Member 4 + team lead**, recorded in `docs_BinaryRepair/04-member-3-oracle-freeze.md` §2.3 |

## Investigation log

| Date | Experiment | Result | Evidence file |
|---|---|---|---|
| 2026-10-20 | Frame and call-site measurement (`objdump`, `nm`, `gdb`) | patch site and free registers identified; no experiment performed | `fixtures/.../evidence/02-objdump-badsink.txt`, `04-gdb-crash-100.txt` |
| 2026-10-20 | Code-cave size probe | **not run** — needs `readelf -S` in the guest | — |
| 2026-10-21 (planned) | Gate 3 Route A feasibility, owner Member 5 | pending | — |
| 2026-10-21 (planned) | Gate 5 placement proof, owners Member 5 + Member 3 | pending | — |

## Verdict

TBD — one of: feasible with strategy X / unsupported with reason / needs more
data. This is a feasibility statement, not a successful repair.

Nothing in this page may be read as "Route A is feasible". The constraints above
only say what a candidate would have to work within; gates 3 and 5 are owned by
Member 5 and have not run.

