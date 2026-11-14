# Path A call whitelist and paradigm A loop closure (2026-11-14)

## Path A: selective call whitelist

Only target-mode assembly packets expose calls already made by the original
function (PLT/internal symbols plus exact executable direct targets).  The
validator accepts exactly those direct targets and still rejects indirect
calls, syscalls and arbitrary symbols.  Standard `asm_roundtrip` remains
leaf-only.

Result on 12 cases, native PoC in the Linux VM:

| model | baseline | AI verified | loop | non-loop |
|---|---:|---:|---:|---:|
| deepseek-flash | 0/12 | 6/12 | 6/6 | 0/6 |
| deepseek-v4-pro | 0/12 | 6/12 | 6/6 | 0/6 |

The whitelist did **not** lift verified non-loop success.  `heap-canary` gave a
partial signal: the candidate passed the security PoC but failed the short
input stdout regression (early exit), so it is unverified.  CWE121 candidates
became injectable after resolving calls through a new PT_LOAD cave, but failed
native behavior.  Evidence:
`artifacts/path-a-call-whitelist-2026-11-14/`.

## Paradigm A: minimal function-level loop closure

Target: `routeb/fixture` `copy_name`, x86-64 Linux ELF.

1. Ghidra 12.2 headless C export + normalization.
2. DeepSeek `deepseek-flash` generated a guard patch.
3. Patcherex2 0.2.14 `ModifyFunctionPatch` recompiled/replaced the function
   (clang 18 / lld 18 exposed as clang-15 / ld.lld-15).
4. Existing six-case behavioral oracle:

| gate | result |
|---|---|
| unchanged normalized C roundtrip vs original | **PASS 6/6** |
| LLM-patched C fixed gate | **PASS 6/6** |

This proves the function-level Ghidra→C→LLM→recompile→replace→PoC chain on one
loop fixture.  It is **not** a non-loop or whole-binary repair claim; extending
it to real non-loop functions is the next capability step.

Evidence: `artifacts/paradigm-a-loop-2026-11-14/`.

## Remaining gap

A non-loop A trial on CWE121 reached Patcherex2 but the patched C required
libc symbols not present in the target's imports (`fputs`, `exit`, `strlen`)
and the binary lacks stderr/exit stubs; this is a concrete import/PLT/stub
problem, not a blocked gate.  Handle it by call-graph-aware symbol/stub
generation or a richer external-call resolver before claiming non-loop A.
