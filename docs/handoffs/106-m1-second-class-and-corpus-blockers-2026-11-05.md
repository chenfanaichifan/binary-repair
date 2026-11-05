# Second class blocked on corpus and ELF; intake now checks the site

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Branch: `integration/live-bridge-2026-11-03`
- Suite: `408 passed / 3 skipped / 0 failed`

## Decision recorded: CWE-787, not 416

`fixtures/public/CWE416_Use_After_Free__malloc_free_char_01` holds only
`defect.json`, `src.c` and `PROVENANCE.md` — no build, no ELF, no tests — so it
was never a candidate. The second class is an out-of-bounds **write**.

Distinctness is now checked on two axes, not just the CWE label:

| Axis | Field | Rule |
|---|---|---|
| class | `defect.json#cwe` | must differ from `--baseline-cwe` |
| mechanism | `defect.json#mechanism` | must differ from `baseline_mechanism` |
| site | `defect.json#bug_site` | must differ from `baseline_bug_site`; one of `stack`/`heap`/`global` |

A mechanism that merely re-uses CWE-121's bounded-copy guard is rejected by the
mechanism rule. `test_a_second_class_cannot_reuse_the_baseline_site`,
`test_declaring_a_baseline_site_requires_the_new_site`,
`test_a_bug_site_must_be_a_known_place` and
`test_a_heap_site_after_a_stack_baseline_is_accepted` pin it.

## Corpus: SARD 112 / Juliet v1.3 does not contain CWE-787

Downloaded the official archive and verified it before reading:

```
https://samate.nist.gov/SARD/downloads/test-suites/
  2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip
size    152,957,342
sha256  ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb
```

Contents: a single `C/` tree, 118 CWE directories, no `C++/` tree, and **no
CWE787 directory at all**. Out-of-bounds writes appear as

```
CWE121_Stack_Based_Buffer_Overflow
CWE122_Heap_Based_Buffer_Overflow
```

`CWE787` is a later CWE restructuring; the 2017 corpus never used that number.
So "pick a CWE-787 case from test suite 112" cannot be satisfied literally, and
I did not relabel a CWE-122 case as CWE-787 to make it look satisfied.

Two honest options, both needing a decision:

1. **Use `CWE122_Heap_Based_Buffer_Overflow` as the second class**, recording
   `cwe: "CWE-122"` and `cwe_parent: "CWE-787"`. It is a heap out-of-bounds
   write, it is in the named corpus, and it is reproducible byte-for-byte from
   SARD. The label differs from the task's.
2. **Fetch a standalone CWE-787 case from the SARD repository** (not test suite
   112), then pin its SARD item id, version and SHA-256. This matches the label
   but leaves the corpus the task named.

The mirror `dsp-testing/samate-c-cpp` was not used at all: it can only save
bandwidth, and the requirement was to compare against SARD bytes.

## ELF: this host cannot produce one

`build.sh` for the existing fixture needs `gcc 13.3.0` on x86-64 **Linux** and
writes `original.elf` (ELF64, `e_machine` 62). Available here:

| Tool | State |
|---|---|
| `gcc` / `clang` / `docker` | absent |
| w64devkit 16.2.0 gcc | present, but emits PE/COFF, not ELF |
| `wsl.exe` | present, **no distribution installed** |

So a committed `original.elf` cannot be built locally, and a fixture without it
fails intake (`missing_file: original.elf`). Producing the real artifact needs a
Linux builder: install a WSL distribution, run the build in a container on
another host, or let M4 build and commit it inside the guest.

I did not fabricate an ELF or reuse the CWE-121 binary.

## CWE-121: recorded as evidence-only, not backfilled

`fixtures/public/CWE121_src_char_declare_cpy_51b/build.json` already says
`reproduction.status: "unverified"` and marks `src.c`/`harness.c` as
`reconstructed from original.elf DWARF` / `from main() disassembly`. That means
the fixture is **ELF-derived**: the committed source is a reconstruction, not the
SARD original, so no source reconstruction path exists.

This is now the stated limitation rather than a gap to patch: the frozen fixture
stays as it is, and only the second class must be a complete intake with real
SARD sources.

## Env failure wording

`398/3/1` was recorded as "missing readelf/objdump". That is resolved on this
host (GNU binutils 2.47 in `D:\brtmp\toolchain`), and the branch now runs
`408 passed / 3 skipped / 0 failed`. CI still needs those two binaries; without
them the same test returns 7 and fails.

## Constraints held

T8.3 blocked, no merge to `main`, no tag, no live-success claim. The intake
changes are on `integration/live-bridge-2026-11-03`; there is no
`feature/live-bridge` branch in this repository, so that name was not invented.
