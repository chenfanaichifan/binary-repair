# Provenance: CWE416_Use_After_Free__malloc_free_char_01

## What this sample is

A synthetic, self-contained C program written for this repository. No upstream
source was copied. The only CWE it contains on purpose is CWE-416 (use of a
heap block after `free`).

The Juliet mirror the Lead pinned (`arichardson/juliet-test-suite-c`,
commit `01e353d`) does not resolve there (HTTP 422), so the upstream Julie
sample could not be fetched and its terms could not be stated honestly for
bytes we did not have. Rather than label reconstructed text as upstream, this
sample declares itself synthetic.

- author: M1 (host backend), acting through an AI agent
- date: 2026-11-05
- licence: Apache-2.0, the project licence. There is no third-party grant to
  reproduce here because there is no third-party code.

## Why `original.elf` is absent

`build.sh` is the recipe; the binary it produces is `original.elf`. It is not
committed in this change because the authoring host has no guest compiler
(`gcc` is not installed) and this sample must not be hand-built. M3/VMer builds
it on the guest from exactly `build.sh`, and the resulting digest goes into
`build.json#output.sha256`.

Until then `tools/fixture_intake.py --check` reports one finding
(`missing_file original.elf`) and exits 1. That is the intended state: the
fixture is content-complete but unbuilt, and the checker must not call that
passing.

## The defect, and how it is observed

`goodSink` reads the buffer and then frees it. `badSink` frees first and then
reads it; that ordering is the defect. The harness selects the defect path with
`--uaf` so a caller does not have to infer it from data.

Reading freed memory is not reliably visible in stdout, because glibc usually
leaves the bytes in place after `free`. `badSink` therefore requests a block of
the same size immediately after the free. glibc serves that request from the
tcache LIFO for the size class, so the stale pointer sees the sentinel bytes
`'X'` instead of the original text, and the two behaviours become
distinguishable by output alone.

This is an observation technique, not a guarantee of the language or of the
allocator:

- a different allocator (musl, a hardened build, a different tcache shape) may
  not reuse the block, and the original could then print the original text too;
- where ASan, valgrind or MTE is available, that report is the authority and
  wins over this technique.

`invalid.json` therefore states the *repaired* behaviour (print the input) and
does not claim that the unmodified binary always differs in output on every
allocator.

## Files

| File | Purpose |
|---|---|
| `src.c` | the sample: `duplicate`, `goodSink`, `badSink`, `main` |
| `harness.c` | fixed command line and the `--uaf` selector |
| `build.sh` | offline, fail-closed build recipe |
| `build.json` | compiler, flags, argv, source, expected output digest, `network:false` |
| `defect.json` | class `CWE-416` and the invalid case that triggers it |
| `contract.json` | obligations, forbidden behaviour, valid domain, repair boundaries |
| `tests/valid.json` | four valid cases |
| `tests/invalid.json` | two defect-path cases |
| `tests/SHA256SUMS` | every file above, relative to this directory |

## Scope limits

`duplicate` clamps the copy to `DEST_CAPACITY - 1`, so this sample cannot also
overflow the heap block. CWE-121 remains the baseline class; T8.3 needs a
second class and this fixture is it.
