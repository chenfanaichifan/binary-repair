# Hook audit — what the V4 model replaces, and what that could hide

The harness hooks five libc symbols. A verifier's first question about any
symbolic result is "did the hooks assume the answer?", so this file takes each
hook apart: what it replaces, which direction it approximates, what it could hide,
and why it cannot hide *this* defect.

Everything below is read off `v4/v4_harness.py` (sha256 `986688bc…b863e`) and
`v4/harness-output.json`, not from memory. The five symbols are exactly the
contract's `allowed_calls`: `exit, free, malloc, memset, printLine`
(`check_mapping.py` check 4 asserts that equality, so a hook appearing later
without a contract change fails the check).

## The five, one at a time

| hook | replaced by | direction | what it could hide |
|---|---|---|---|
| `malloc` | a fresh symbolic 64-bit value, constrained `≠0`, `%16==0`, `≥0x10000`, `<0x7FFF_0000_0000` | **over**-approximates the address space | nothing about this property; it *widens* what is explored |
| `memset` | returns `dest`, writes nothing | **under**-approximates memory contents | any property about the printed bytes |
| `free` | records the pointer, increments `free_calls`, returns `0` | **under**-approximates the allocator | double free, reuse, allocator failure — none of which this property asks about |
| `printLine` | observes the argument, returns `0` | **under**-approximates the callee | a defect that only shows in the printed bytes, or after a `strlen` walk |
| `exit` | terminates the state with code 0 | **under**-approximates the exit path | a defect signalled only by an exit code |

### malloc — the analysis quantifies over addresses, deliberately

Concretely modelling the allocator would pin one address and leave nothing to
quantify over: with no inputs and one path, a concrete address would make the
whole question decidable by a single run, which is V3's job, not V4's. Returning a
constrained symbolic value is the over-approximation that makes the question
meaningful.

It cannot manufacture a violation: the witness is *the same symbolic variable*
appearing at `free()` and later at `printLine()`, which is satisfiable regardless
of which concrete address is chosen. The address constraints narrow the domain for
realism (alignment, non-null), they do not create the equality.

One consequence worth naming: `addr != 0` makes the malloc-failure branch
unreachable, so the `exit()` path inside the null guard is never taken in the
model. That is a *tightening*, and it is why the `exit` hook is mostly defensive.

### memset — a no-op, and the reason it is acceptable

The property is about which pointer reaches `printLine()`, not about what the
block contains. Writing 99 bytes at a symbolic address would add state for no
gain. The cost is explicit: **this model cannot see a data-value defect.** If the
defect were "prints the wrong bytes from a live buffer", this harness would report
`holds` and be wrong — which is why `not_claimed` says the result is about the
target function's pointer flow and nothing else.

### free — recorded, not modelled

`free` appends its argument to `state.globals["freed_pointers"]` and returns. No
tcache, no coalescing, no double-free detection. Modelling the allocator would
import `environment_assumptions` from the contract (glibc tcache writes
next/key into the chunk) into the model as *assumptions*, and the point of V4 is
to reason about the program, not to re-derive an allocator.

The risk this creates is the one that matters: if `free` were not recorded, the
freed list would always be empty and every case would be `unsat` — a harness that
silently answers "no violation" forever. That failure mode is exactly what the
negative control catches, and it is why `known_bad` must be `violated` for the run
to count.

### printLine — observation only, and no verdict of its own

The hook compares nothing. It hands the argument to the harness, which asks the
solver whether that symbolic value equals any recorded freed pointer. Two things
follow: the hook cannot approve a repair, and its stub removes the `strlen` loop
from the exploration (the real `printLine` walks the buffer until a NUL, which for
a freed block stops after three bytes of tcache residue — a detail V3 observes on
the real binary, not something this model needs).

**Discrepancy, documented rather than patched.** The `HOOKS` entry for `printLine`
says "the state is terminated after the observation". The code does not do that —
it returns `0` and execution continues until the function returns. The effect is
*more* coverage, not less: a second `printLine` on the same path would also be
observed. The sentence is wrong about the mechanism and harmless about the
result. It is left in place because the file's digest is what records 128, 129 and
133 vouch for; changing a comment to fix a sentence would invalidate three
delivered records.

### exit — so that a guard is not mistaken for exploration

Without the hook, `exit()` would jump to an address angr cannot resolve, and the
state would land in `errored` or `unconstrained`. `complete=True` would then be
false, or worse, `unexplored` would quietly absorb it. Terminating the state keeps
"complete" honest.

The approximation is that the exit code is forced to `0`. For this fixture the
only `exit()` is the malloc-null guard, which the address constraints make
unreachable; and exit codes are V3's question (it checks `return_code: 0` against
the real binary), not V4's.

## What would invalidate this audit

- A hook added without the contract's `allowed_calls` changing — check 4 catches
  it, and `v4/harness-output.json#hooks` is the record.
- `free` recording being dropped or short-circuited — the negative control would
  flip to `holds`, which is visible as `known_bad.observed != "violated"`.
- `printLine` returning a verdict itself, or the comparison moving inside the
  hook — code change, not detectable from the output; read `_observe_print`.
- The property being widened to data values while `memset` stays a no-op. Then the
  model would answer a question it cannot see, and the audit above stops applying.

## How to re-check it without reading all of this

```sh
python3 ../T8.3-supplement-2026-11-06/check_mapping.py \
    --bundle ../T8.3-evidence-2026-11-06      # 9/9, exits 0
```

Nine field-level checks, of which four are about the hooks and the property they
serve: `hooks == allowed_calls`, `property_kind == pointer-flow`, `known_good`
holds on `unsat`, `known_bad` violated on `sat`. The prose above explains why
those four are sufficient; the script is what makes the claim falsifiable.
