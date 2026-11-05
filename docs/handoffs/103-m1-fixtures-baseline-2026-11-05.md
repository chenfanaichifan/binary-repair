# Fixtures: baseline completed, CWE416 pinned, T8.3 still blocked

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Suite: `406 passed / 3 skipped / 0 failed` (was `398/3/1`)

## CWE121 baseline: intake passes, build not reproduced

`tools/fixture_intake.py --check fixtures/public/CWE121_src_char_declare_cpy_51b`
now returns `OK (1 warning(s))` and exit 0.

Added:

- `src.c` - the Juliet unit (`badSink` / `goodG2BSink`)
- `harness.c` - the evaluation `main`
- `build.sh` - offline, fail-closed, verifies its own output hash
- `build.json` - compiler, flags, argv, provenance, expected output hash
- `defect.json` - `CWE-121`, `mechanism: bounds-check`
- `tests/SHA256SUMS` - rewritten to cover every file relative to the fixture
  root, including `original.elf` (it previously listed only the two test JSONs,
  relative to `tests/`, so the binary was unhashed)

`src.c` and `harness.c` are **reconstructed from the committed ELF**, and both say
so in a header comment. The reconstruction is pinned by exact evidence:

| Evidence | Value |
|---|---|
| `DW_AT_producer` | `GNU C17 13.3.0 -mtune=generic -march=x86-64 -g -O0 -fno-stack-protector -fno-pie -fstack-clash-protection -fcf-protection -fasynchronous-unwind-tables` |
| `.comment` | `GCC: (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` |
| source path | `juliet-v1.3/C/testcases/CWE121_Stack_Based_Buffer_Overflow/s09/CWE121_..._cpy_51b.c` |
| `badSink` | `0x4012b0`, `char dest[50]` cleared to 50 bytes, `strcpy` at `0x401304`, `printLine(data)` (prints data, not dest) |
| `main` | `0x401256`, `fprintf(stderr, "usage: %s <input>\n", argv[0])`, `return 2` |
| `original.elf` sha256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |

The build is **not** reproduced: this host has no `gcc`/`clang`, and the Juliet
`testcasesupport` tree plus the original `harness.c` were not shipped. Rather than
claim a rebuild that never happened, `build.json#reproduction.status` is
`unverified` and intake prints:

```
warning  reproduction_unverified  build.json#reproduction  No toolchain was available ...
```

A warning is not a pass in disguise: `build.sh` exists, every prerequisite is
checked, and intake fails the moment someone marks the status `verified` while
`original.elf` disagrees with the recorded hash.

## CWE416: source and classification in, binary blocked

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/`:

- `src.c` - upstream Juliet `..._malloc_free_char_01.c`, licence verified
- `defect.json` - `CWE-416`, `mechanism: lifetime`, `baseline_mechanism: bounds-check`
- `PROVENANCE.md` - source, commit, licence, hash, and what is missing

Licence, from the mirror's `LICENSE`: NIST public domain, foreign rights under
CC0 1.0.

**Pin discrepancy, needs the Lead's answer.** The supplied pin `01e353d` does not
resolve in `arichardson/juliet-test-suite-c` (`GET /commits/01e353d` -> 422). The
fixture is pinned to the resolved head instead:

```
lead_provided_pin : 01e353d (unresolved)
resolved_pin      : f88433e3443648a17671398797a04ea1f8e1a274 (2025-03-27)
```

`src.c` upstream hash is `fa84a6bb...` (CRLF); the committed file is
`262dee1d...` after newline normalisation, and stripping `\r` reproduces it byte
for byte.

**Still missing**: `original.elf`, `build.sh`, `build.json`, `contract.json` and
`tests/`, which produce seven `missing_file` findings. Producing the ELF needs a compiler, which is
the guest path, so this is a sequencing conflict between step 2 (M1 fixture) and
step 3 (M3 guest build), not a decision to fake a binary.

## Intake changes

- `mechanism` is now required in `defect.json`; `baseline_mechanism` must differ
  from it, otherwise `not_a_distinct_class`. Two CWEs repaired the same way are
  the same exercise.
- `build.json#reproduction` is optional but validated: `status` is `verified` or
  `unverified`, `unverified` always carries a `reason` and always prints as a
  warning.
- Findings carry severity; only `error` fails the check, and `--list` shows
  `OK (n warning(s))` rather than collapsing warnings into a pass.

## readelf / objdump

The host has binutils in `D:\C++\Dev-Cpp\MinGW64\bin` (GNU 2.24.51, supports
`elf64-x86-64`), just not on `PATH`. `tests/conftest.py` now honours
`BINARYREPAIR_BINUTILS_DIR`, and with it set the suite is fully green. The previous
`398/3/1` was an environment gap, not a code failure.

## T8.3

Still **blocked**. What exists: a complete first-class fixture, a pinned
second-class source with a stated mechanism, and a checker that refuses partial
input. What does not exist: a second-class ELF and guest build, a contract and
test manifest for it, a second-class candidate with V0-V5 evidence, and M4's
independent verification.
