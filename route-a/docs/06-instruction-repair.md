# 06 — Instruction repair investigation

Work item 7. Status: ☐ not started

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

## Investigation log

| Date | Experiment | Result | Evidence file |
|---|---|---|---|
| | | | |

## Verdict

TBD — one of: feasible with strategy X / unsupported with reason / needs more
data. This is a feasibility statement, not a successful repair.
