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

## Update: CWE121 non-loop function-level closure (2026-11-14)

The CWE121 symbol gap was closed with a **model-generated guard/copy patch**
plus a reviewed syscall helper, without adding absent libc imports:

- Ghidra exports `badSink`; DeepSeek generates a length/check/copy guard using
  only `printLine` and a provided `br_fail()` helper.
- The helper is deterministic glue: x86-64 `write(2,...)` syscall for the exact
  stderr message and `exit(1)` syscall; no `fputs/exit/strlen/memset`.
- Patcherex2 replaces the function with
  `symbols={"printLine":0x401380}`.
- `poc_runner` on `fixtures/poc/cwe121.json`: **status=pass**, 2/2 PoC and
  4/4 regression.  Fixed SHA-256: `463a9758...`.

This is the first measured **non-loop** paradigm-A closure.  It is still one
function/fixture, and the syscall helper is reviewed glue, not model content.
Evidence: `artifacts/paradigm-a-cwe121-2026-11-14/`.

## Update: direct-callee context (P2) and stdout signature (P4)

- `scripts/export_with_callees.py` now exports target C/meta plus each direct
  callee (`printLine`, `strcpy` for CWE121) into a context JSON; evidence:
  `artifacts/callee-context-2026-11-14/`.
- `poc_runner` records an explicit `stdout_signature` (`matched`/`mismatch`/
  `not_applicable`) and `unified_verification` has a required
  `poc.native.stdout_signature` check.  Regression stdout comparison was already
  enforced; the new field makes the side-effect gate explicit and observable.
- The heap-canary partial candidate remains unverified because its short-input
  stdout regression failed.


## Update: 2026-11-14 international matrix attempt

SiliconFlow international identity probes passed for `Qwen/Qwen3.8-27B`,
`moonshotai/Kimi-K3.1-Pro`, and `deepseek-ai/DeepSeek-V4.1-Flash`, but every
full benchmark call returned HTTP 402 (account balance insufficient).  The two
DeepSeek official models completed natively at 6/12 each (loop 6/6, non-loop
0/6).  The 4-6 model matrix remains blocked by balance, not by model identity.
Evidence: `artifacts/multi-model-matrix-intl-2026-11-14/`.

The CWE121 `br_fail` mechanism is generalized in
`routeb/symbol_resolver.py`: existing calls, patch-defined calls, reviewed
write/exit syscall templates, and unresolved symbols (fail closed) are
classified before patching.  Evidence: `artifacts/symbol-resolver-2026-11-14/`.
