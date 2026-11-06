# M1: T30 rebuilt around the upstream `original.c`

- Date: 2026-11-05
- Owner: M1 (host backend)
- Boundary: CWE-121 stays NOT VERIFIED; T8.3 blocked; no merge to `main`, no tag, no live success

## What changed

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01/`

| Before | After |
|---|---|
| `src.c` — synthetic, authored in this repo | `original.c` — verbatim SARD, sha256 `fa84a6bb…` |
| `build.sh` compiled `src.c harness.c` with `-DINCLUDEMAIN` | compiles `original.c harness.c support/io.c`, **no** `INCLUDEMAIN` |
| no support headers | `support/std_testcase.h`, `std_testcase_io.h`, `io.c` from Juliet `testcasesupport` |
| `build.json#source` said "authored-in-this-repository" | points at the upstream path and pins its sha256 |
| `contract.json` described the synthetic `badSink` | describes the upstream `CWE416_…_bad` |

The synthetic `src.c` was deleted, not renamed. A synthetic file cannot stand in
for the upstream case, and keeping it beside `original.c` would leave two
candidate sources with no way to tell which one produced a binary.

## Build recipe

```sh
gcc -mtune=generic -march=x86-64 -g -O0 \
    -fno-stack-protector -fno-pie \
    -fstack-clash-protection -fcf-protection -fasynchronous-unwind-tables \
    -ffile-prefix-map="$FIXTURE_ROOT"=. \
    -fmacro-prefix-map="$FIXTURE_ROOT"=. \
    -I support -no-pie \
    -o original.elf original.c harness.c support/io.c
```

Two deliberate choices:

- **No `-DINCLUDEMAIN`.** The upstream `main()` would run `good()` and `bad()`
  in one process, so the exit code could not distinguish the paths. `harness.c`
  supplies a fixed entry point instead: `<ignored>` runs the good path,
  `<ignored> --uaf` runs the bad path.
- **Prefix maps.** `-ffile-prefix-map` and `-fmacro-prefix-map` rewrite the
  checkout's absolute path to `.`, so `original.elf`'s DWARF does not embed
  `E:\deepwork…`. Without them the digest would change with the build directory,
  which makes `output.sha256` meaningless.

`harness.c` calls the upstream symbols
`CWE416_Use_After_Free__malloc_free_char_01_bad` / `..._good`, both of which are
non-static in the SARD file (only `goodG2B` / `goodB2G` are static).

## Not rebuilt: the digest stays null

`build.json#output.sha256` and both `tests/*.json#original_sha256` remain `null`.

The authoring host has **no ELF compiler**: `gcc`, `clang`, `x86_64-linux-gnu-gcc`
and `zig` are all absent, `wsl -l -v` lists no distribution, and the only gcc on
disk is w64devkit's, which produces PE/COFF. The CWE416 fixture has no ELF
anywhere under the working tree, and no variant binary was renamed to
`original.elf`.

Filling those fields needs a run of `build.sh` on a Linux x86-64 host with gcc.
The script prints the digest and refuses to overwrite a non-null mismatch, so the
first real build can be recorded without editing code.

`tests/SHA256SUMS` was deleted rather than left stale: it still listed the
removed synthetic `src.c`. It must be regenerated after `original.elf` exists,
because a sums file that does not cover the binary attests to nothing.

## Intake accepts either source name

`tools/fixture_intake.py` no longer hard-requires `src.c`. It now requires one of
`original.c` or `src.c`, reports `missing_file original.c` when neither exists,
and still flags an empty source. `build.sh`, `build.json`, `defect.json`,
`contract.json` and the test manifests remain mandatory.

Existing fixtures are unaffected: the CWE-122 fixture ships `src.c` and still
passes.

## State

| Item | Value |
|---|---|
| `original.c` sha256 | `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e` |
| intake on this fixture | 2 findings: `missing_file original.elf`, `missing_file tests/SHA256SUMS` |
| CWE-121 | NOT VERIFIED, unchanged |
| suite | 418 passed / 3 skipped / 0 failed (local) |

The two intake findings are the honest state of a fixture with no build, not a
regression. T8.3 remains blocked on the same missing artefact.
