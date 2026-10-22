# Gate 4 — Route B unchanged round trip: PASS

**Date:** 2026-10-22
**Run:** GitHub Actions `gate4-routeb-roundtrip`, run `39752557610`
(`https://github.com/chenfanaichifan/binary-repair/actions/runs/39752557610`)
**Result:** **6/6 behaviour-identical; gate4_pass = true.**
This is the unchanged round trip only — **not a repair**.

## 1. Identity

| Item | Value |
|---|---|
| Original | `fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf`, 26,792 B |
| Original SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Round-trip SHA-256 | `decdcdb821bfe4c41a070b0a23a2f6497f46a92f439cb02a1e4139a82cde954b` |
| Round-trip size | 26,792 B (same as original) |
| Function | `CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink` @ `0x4012b0`, 104 B |

## 2. Environment (recorded for V5)

```text
Linux 7.0.0-1017-azure x86_64 (ubuntu-24.04 runner)
JDK 21.0.12.1 (Temurin)
Ghidra 12.2 PUBLIC (2026-10-16 build)
Patcherex2 0.2.14
gcc 13.3.0
Python 3.12.3
```

The workflow installs `clang-15` and `ld.lld-15` symlinks for Patcherex2's compiler
backend, makes the ELF executable, and runs on a disposable GitHub-hosted runner.

## 3. Procedure

1. Ghidra headless export of `badSink`:
   `routeb/ghidra/export.sh ... <badSink> routeb/out/gate4`.
2. Normalize types/names into
   `routeb/experiment/samples/juliet_badSink.normalized.c`; the raw Ghidra output
   and `.meta.txt` are kept as evidence.
3. Patcherex2 `ModifyFunctionPatch` replaces the function with the **unchanged**
   normalized C; no behaviour edit.
4. `routeb/run_manifest_compare.py` runs the frozen 6-case manifest on the original
   and the round-trip binary and compares exit code, stdout and stderr byte-for-byte.

## 4. Result

| Case | Kind | Input | Original | Round trip | Same |
|---|---|---|---:|---|---|
| valid-empty | valid | 0 B | exit 0, `\n` | exit 0, `\n` | yes |
| valid-smallest | valid | 1 B | exit 0, `A\n` | exit 0, `A\n` | yes |
| valid-typical | valid | 10 B | exit 0, `A…\n` | exit 0, `A…\n` | yes |
| valid-maximum | valid | 49 B | exit 0, `A…\n` | exit 0, `A…\n` | yes |
| invalid-first | invalid | 50 B | exit 0, silent overflow | exit 0, silent overflow | yes |
| invalid-longer | invalid | 100 B | SIGSEGV (-11) | SIGSEGV (-11) | yes |

The original is **4/6** on the repaired oracle (the two invalid cases fail); the
round trip reproduces exactly that 4/6. That is the gate 4 criterion.

## 5. What this proves / does not prove

Proves:

- Ghidra export → normalization → Patcherex2 function replacement works on this
  real Juliet ELF;
- the round trip preserves exit code/stdout/stderr on all six frozen cases;
- the toolchain versions and runner profile are recorded for V5.

Does not prove:

- that an **edited** candidate repairs the defect (V3 repair is separate);
- Route A feasibility (gate 3 still needs a scope ruling);
- symbolic security (V4);
- behaviour outside the six frozen cases.

## 6. Evidence files

| File | Purpose |
|---|---|
| `routeb/out/gate4/manifest-compare.json` | machine-readable 6/6 result |
| `routeb/out/gate4/CWE121…badSink.c` | raw Ghidra output (evidence, never edited) |
| `routeb/out/gate4/CWE121…badSink.c.meta.txt` | entry/size/signature/callees |
| `routeb/out/gate4/roundtrip.elf` | patched ELF, SHA-256 `decdcd…` |
| `routeb/out/gate4/environment.txt` | OS/JDK/Ghidra/Patcherex2 versions |
| `routeb/out/gate4/ghidra.log`, `patcherex2.log`, `compare.log` | commands and diagnostics |
| `.github/workflows/gate4.yml` | reproducible run |

## 7. Reproduce

Push to `member-5/gate4-ci` (workflow trigger) or run the steps manually on a
disposable Ubuntu 24.04 VM with JDK21 + Ghidra 12.2 + Patcherex2. The workflow
force-pushes `gate4-results` with the evidence.
