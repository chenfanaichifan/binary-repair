# Paradigm A minimal loop: Ghidra C → LLM patch → Patcherex2 → PoC gate

Date 2026-11-14.  This is a **function-level replacement** proof on the
`routeb/fixture` `copy_name` target, not a whole-binary rewrite and not a
non-loop repair claim.

## Pipeline

1. Build a non-PIE x86-64 Linux ELF from `routeb/fixture/vuln.c`.
2. Ghidra 12.2 headless export of `copy_name` (raw C + meta).
3. Normalize only types/names; no semantic edits (`copy_name.normalized.c`).
4. DeepSeek `deepseek-flash` generates `copy_name.model.c` with the reviewed
   contract (capacity 16, invalid inputs return -1 without writes).
5. Patcherex2 0.2.14 `ModifyFunctionPatch` recompiles and replaces the function
   in the ELF; clang 18 / lld 18 are exposed as clang-15 / ld.lld-15 shims.
6. The existing `routeb/verify.py` oracle is the only acceptance authority.

## Result

| gate | cases | result | artifact |
|---|---:|---|---|
| unchanged C roundtrip vs original | 6/6 | **PASS** | `roundtrip.elf`, `roundtrip-verify.json` |
| LLM-patched C fixed gate | 6/6 | **PASS** | `fixed.elf`, `fixed-verify.json` |

Fixed behavior for 16/17-byte input: `ret=-1`, `guard=ok`, exit 0; valid inputs
preserve copy/return/guard behavior.  Original fixture reproduces guard
corruption on 16/17-byte inputs.

## Limits

- Single function, single fixture, x86-64 Linux ELF only.
- Roundtrip checks the fixture's six-case oracle, not general equivalence.
- This loop target is already repairable by the assembly path; the purpose is
  to prove the C-recompile/function-replacement **chain**, not to extend the
  non-loop success set.
- Patcherex2/angr unicorn backend warning is recorded; patching and oracle
  execution succeeded without it.
- No key, prompt or raw model response is stored.
