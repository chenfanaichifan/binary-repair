# Provenance — CWE416 no-input fixture

## What the sample is

The SARD case `CWE416_Use_After_Free__malloc_free_char_01.c`, compiled
**unmodified**, plus an evaluator-side harness that calls only the flawed
function.

| File | SHA-256 | Origin |
|---|---|---|
| `original.c` | `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e` | SARD case, byte-identical |
| `src.c` | `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e` | same bytes as `original.c`; intake alias, see below |
| `harness.c` | `cef8f533765f3f9184377bf72e32792f6a4128080da8467cb478340a679c63a9` | team-authored entry point |
| `support/io.c` | `50ace91d0f9cd9f281d5d8ff3a9ca879ee2779d737030ae84e8e4be3df5b299c` | Juliet 1.3 `C/testcasesupport` |
| `support/std_testcase.h` | `a78aaf3a54a6210260ad70123c09c3c283c6edf7808b6244205e00b8f2d9b8d0` | Juliet 1.3 `C/testcasesupport` |
| `support/std_testcase_io.h` | `6459df50d22697bb61619e2effd688ebb98915db25f7eb1bdbb767f888066fb6` | Juliet 1.3 `C/testcasesupport` |
| `original.elf` | `c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9` | built from the above, 25,344 bytes |

Case source, exact:

```
repo    dsp-testing/samate-c-cpp
commit  01e353daa3d28a4ce2ae68904cbcde5e03e3519d
path    C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c
```

The three support files are byte-identical to the same paths in that archive at
that commit. They are shipped here so the fixture builds without a Juliet
checkout; a build that reaches for `$HOME/evaluator/src/juliet-v1.3` is not
reproducible by anyone else.

## Two names for one source

`original.c` is the file the recipe compiles: it is spelled that way on the gcc
line in `build.sh` and `build.json#argv`, `defect.json#source.path` names the
upstream case that produced it, and `-g` wrote that name into the committed
binary. Renaming it and rebuilding would fork a second ELF hash for one sample,
which records 118 and 119 both refuse to do, so the name stays.

`src.c` is a **byte-identical alias** with the same SHA-256, added because
`tools/fixture_intake.py` hardcodes `src.c` in `REQUIRED_FILES` and stops at
`missing_file` before it looks at anything else. It is not a second source: the
build never reads it, and `tests/SHA256SUMS` binds both names to
`fa84a6bb…f42e`, so an edit to either one fails the manifest instead of drifting
quietly. Nothing about the artefact, the recipe or the upstream bytes changes.

If M1 makes the intake take the source name from `build.json#argv` (or accepts
`original.c`), delete `src.c` and its `tests/SHA256SUMS` line; no other file
needs to move.

## How `original.elf` was built

Inside the baseline guest (snapshot uid 11, `gate4-harness`), 2026-11-05:

```sh
JULIET_ROOT= sh build.sh        # support/ is resolved from the fixture itself
  exit=0
  sha256=c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
  size=25344
```

The compiler line is the T30 recipe unchanged: `-O0 -g -fno-stack-protector
-fno-pie -no-pie -Wall` plus the two prefix-map pairs. The maps are what make
the digest depend on the code and the flags rather than on the directory the
tree sits in; measured in that window, the same sources without them hashed
`fc40085c…87e0` (relative) and `0a26a805…07ec` (absolute).

The build emits `original.c:36:5: warning: pointer 'data' used after 'free'
[-Wuse-after-free]` with the matching `note: call to 'free' here` at line 34.
That warning is the defect; it is recorded, not suppressed.

## Observation of the unmodified original

```
setarch -R ./original.elf
  exit 0, stdout 05 04 0a (3 bytes), stderr empty     5 runs, 5 identical
./original.elf   (ASLR on)
  0402010a / 45fc020a / 576d010a                      3 runs, 3 different
```

A correct program prints the 100 bytes it allocated. The original prints three
bytes of allocator residue and still exits 0, so the defect is invisible in the
exit status.

## What is deliberately absent

- **No `tests/invalid.json`.** `input_mode: none`: the entry point takes no
  arguments, reads no stdin, and the use-after-free is unconditional. There is
  no input to reject, so there is no invalid case to write. Zero is the honest
  count, not a gap.
- **No `max_valid_input_bytes`, `invalid_exit_code`, `invalid_stdout`,
  `invalid_stderr`, `invalid_input_response`.** All five describe an input
  rejection path this sample does not have. The contract is the v3 no-input
  shape (`schema_version: 3`), where they are not merely empty but absent; the
  model rejects sentinels. See record 120.




