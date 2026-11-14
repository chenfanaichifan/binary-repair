# Paradigm A non-loop closure: CWE121 (2026-11-14)

Target: `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink`,
x86-64 Linux ELF.  This is a **non-loop function-level closure**, not a
whole-binary rewrite.

## Why this is different from the earlier failed attempt

`readelf -r` shows the target imports only `strcpy/puts/printf/fprintf/...`.
It has **no fputs, exit, strlen, strcpy?** (strcpy exists) — specifically no
`fputs`, `exit`, `strlen` or `memset`.  The earlier model C failed Patcherex2's
undefined-symbol check because it referenced those functions.

This experiment uses a **model-generated guard/copy patch** plus a reviewed
symbol-safe helper:

- length/copy: C loops;
- valid output: existing `printLine` symbol;
- invalid path: the model calls a provided `br_fail()` helper; the helper uses
  x86-64 `write(2,...)` (syscall 1) and `exit(1)` (syscall 60), so no missing
  libc imports are needed.
- Patcherex2 is given `symbols={"printLine": "0x401380"}` and replaces the
  function with `ModifyFunctionPatch`.

The helper is deterministic glue, not model content; the guard/copy logic is
the DeepSeek candidate.

## Pipeline

1. Ghidra 12.2 headless export + meta (raw C retained).
2. Normalize types/names.
3. DeepSeek `deepseek-flash` generates the candidate using only `printLine`
   and `br_fail`.
4. Append reviewed `br_fail` syscall helper + `printLine` declaration.
5. Patcherex2 0.2.14 `ModifyFunctionPatch` replaces the target function.
6. `poc_runner` runs `fixtures/poc/cwe121.json` natively in the Linux VM.

## Gate

`poc-evidence.json`: **status=pass**, 2 PoC + 4 regression cases.

- 51/101-byte inputs: candidate exit 1, exact stderr
  `ERROR: input exceeds destination capacity\n`, no stdout.
- 0/1/5/49-byte inputs: candidate stdout/exit match original (`a\n`, etc.).

Fixed SHA-256: `463a9758f9eb45a8d80d5af340ffd0861997b0ccaa5c5b6be41406616589636f`.

## Limits

- One non-loop function, one selected input family; not general A.
- The syscall helper is reviewed glue required by this target's import gap.
- No key/prompt/raw model response is stored.
