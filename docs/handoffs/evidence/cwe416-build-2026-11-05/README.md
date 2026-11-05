# CWE416 build and trigger, measured inside the guest

Built on 2026-11-05 in the `binrepair-vm` guest, cold-booted from snapshot uid 11
(`gate4-harness`) after a `revertToSnapshot`, so the window is a reset and not a
resumed session. `01-isolation.txt` is the fingerprint taken inside that window.

## Read this before using the binary

`original.variant.elf` is **not** the artefact `build.json#argv` describes.
The committed recipe does not link:

```
/usr/bin/ld: harness.c:21: multiple definition of `main';
              src.c:91: first defined here
collect2: error: ld returned 1 exit status
```

`src.c` defines `main` at line 90 and `harness.c` defines `main` at line 20; both
objects export `T main`, so `gcc src.c harness.c` cannot produce a binary. The
full log and the per-object `nm` output are in `02-committed-recipe-failure.txt`.
Nothing was edited to paper over this — the fixture is not mine to change.

What was built instead is the smallest variant that still exercises the sample:
`src.c` alone, because its own `main` already implements the `--uaf` dispatch the
matrix needs. The flags are the committed flags plus a prefix map:

```
gcc -mtune=generic -march=x86-64 -g -O0 \
    -fno-stack-protector -fno-pie \
    -fstack-clash-protection -fcf-protection -fasynchronous-unwind-tables \
    -no-pie -fdebug-prefix-map=$PWD=. -ffile-prefix-map=$PWD=. \
    -o original.variant.elf src.c
```

`original.variant.elf` = 20,040 B, SHA-256
`f1019618f0a6180b7fff28821ad6cff72d2477fd093cbddfa81d486bff5a5ff0`, `EXEC`
non-PIE x86-64, entry `0x401190`.

## Why the prefix map is not optional

The committed flags carry `-g` and no prefix map, so `DW_AT_comp_dir` records the
build directory and the digest follows it. Measured here, same source, same
compiler, same flags, two directories:

| Build directory | Digest |
|---|---|
| `~/cwe416/run-b` | `20a58ba5b453db68…` |
| `~/cwe416/run-c` | `0927df3e9d44526e…` |

Both are 20,064 B. With `-fdebug-prefix-map`/`-ffile-prefix-map` the same two
builds agree at `f1019618f0a6180b…`, which is the value recorded above. A digest
taken without the map is a statement about a directory, not about a source file.
`03-recipes-and-digests.txt` has the raw numbers.

## Matrix: 4 / 6, and the 2 are the point

| case | kind | rc | stdout | verdict |
|---|---|---|---|---|
| `valid-empty` | valid | 0 | `"\n"` | MATCH |
| `valid-one` | valid | 0 | `"a\n"` | MATCH |
| `valid-max49` | valid | 0 | 49×`m` + `\n` | MATCH |
| `valid-spaces` | valid | 0 | `"two words\n"` | MATCH |
| `invalid-first` | invalid | 0 | 49×`X` + `\n` | DIFF |
| `invalid-longer` | invalid | 0 | 49×`X` + `\n` | DIFF |

The two DIFF rows are not a fault in the harness. `tests/invalid.json` records the
**post-repair** expectation, so the original is supposed to disagree; what it
prints is the reuse sentinel written over the freed block. That is the defect
made observable, which is what the sample exists to do.

One consequence worth knowing: both invalid cases produce identical bytes, so the
pair does not discriminate on input length the way two independent probes would.
It still discriminates a repair, because the expected strings differ.

## Trigger stability

150 runs, no divergence: 50×`1234567 --uaf`, 50×`use-after-free --uaf`,
50×`1234567`, each bucket collapsing to one digest
(`06-stability.txt`). The output is deterministic because the harness writes `X`
into the reused block rather than relying on whatever the allocator left there.

## The defect is real, not a printing trick

An ASan build of the same source reports

```
ERROR: AddressSanitizer: heap-use-after-free ... READ of size 2
    #1 printLine  src.c:43
    #2 badSink    src.c:72
```

while the good path exits clean under the same build (`07-asan.txt`). So the
sentinel output is a symptom of a genuine read after `free`, not an artefact of
`printLine`.

## What is deliberately absent

- `build.json#output.sha256` is untouched. Filling it with `f1019618…` would bind a
  recipe that differs from `build.json#argv` in two ways (no `harness.c`, plus a
  prefix map), and that is the kind of quiet substitution this project keeps
  catching.
- No `candidate`, no V0–V5, no gate conclusion. There is no repaired binary and no
  buildable original from the committed recipe, so every gate stays `not_run`.
- The fixture directory itself was not modified.

## Files

| File | What it is |
|---|---|
| `01-isolation.txt` | guest fingerprint in the reset window |
| `02-committed-recipe-failure.txt` | `sh build.sh` verbatim, exit 1, duplicate `main` |
| `03-recipes-and-digests.txt` | digests per build, with and without prefix map |
| `04-readelf.txt` | ELF header, segments, symbols of the variant build |
| `05-matrix.txt` | the 4 + 2 table above |
| `06-stability.txt` | 150-run digest collapse |
| `07-asan.txt` | heap-use-after-free report and the clean good path |
| `08-SHA256SUMS` | digests for every file in this directory |
| `original.variant.elf` | the variant build; **not** `build.json`'s artefact |
| `matrix.py` | runner that produced `05-matrix.txt`, kept so M4 can re-run it |
| `collect.sh` | the script that produced `01`–`08` inside the guest |

`08-SHA256SUMS` covers all eleven entries except itself. `collect.sh` expects the
fixture under `~/cwe416/run-a` (as `build.sh` left it) and the variant builds
under `run-b` / `run-c`; it is recorded as the provenance of these transcripts,
not as a one-command rerun.
