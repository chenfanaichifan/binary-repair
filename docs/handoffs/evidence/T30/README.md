# T30 — CWE416 guest build and deterministic trigger (2026-11-05)

A second Juliet fixture, built inside the guest from a hash-pinned source, with
a trigger that reproduces the defect byte-for-byte.

**This adds CWE416 only.** T8.3 stays blocked; no repair candidate was produced
and no second sample type was invented.

## 1. The quadruple, resolved and verified

| Field | Value |
|---|---|
| Repo | `dsp-testing/samate-c-cpp` |
| Commit | `01e353daa3d28a4ce2ae68904cbcde5e03e3519d` (main HEAD; matches the declared `01e353d`) |
| Path | `C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c` |
| SHA-256 | `fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e` |

The declared hash was given truncated (`fa84a6bb…7f42e`); the file was downloaded
at that commit and its full SHA-256 matches both the declared prefix and suffix.
The path was **not** the bare filename in the task text — the file lives under
`C/testcases/CWE416_Use_After_Free/`, found by probing the commit rather than
assuming (the GitHub recursive-tree API response is truncated for this repo, so
a search there returns nothing even though the file exists).

`testcasesupport/` comes from the guest's Juliet 1.3 checkout, which was verified
byte-identical to the same paths in the declared commit
(`std_testcase.h` `a78aaf3a…b8d0`, `io.c` `50ace91d…299c`).

## 2. Why this fixture is deterministic in a way CWE121 was not

CWE121 needed an input to reach its defect, so determinism meant "same input →
same observation". CWE416 has no input at all: `bad()` mallocs 100 bytes, fills
them, frees the block, then reads it back through `printLine()`. Every run takes
the same path.

What is *not* automatically stable is the bytes read back. The freed chunk's
first word is tcache metadata carrying a heap address, so with ASLR on the output
changes every run. Measured, 10 consecutive runs with ASLR on:

```
10 distinct stdout values, e.g. 06e6030a, 0d25020a, 15ec0a, a05c010a …
```

With ASLR disabled for the process (`setarch -R`), 50 consecutive runs:

```
50x exit_code=0 stdout_hex=05040a stdout_len=3 stderr_len=0
```

`setarch -R` flips one personality bit for that process. It does not touch the
program or the allocator, so it cannot manufacture the defect — it only stops the
observation from drifting.

## 3. The defect is silent

| | Expected of a correct program | Measured on this build |
|---|---|---|
| exit code | 0 | **0** |
| stdout | 99 × `A` + `\n` (100 bytes) | **2 bytes of allocator residue + `\n` (3 bytes)** |
| stderr | empty | empty |

No crash, no error, unchanged exit status. Only the stdout bytes differ. That is
why the trigger records exact bytes rather than just the exit code: an exit-code
check would pass this binary.

## 4. A reproducibility defect found and fixed

The first rebuild produced a different hash than the first build
(`fc40085c…` vs `0a26a805…`). Cause: `-g` embeds `DW_AT_comp_dir` and the source
file names, so the same sources compiled with relative vs absolute paths give
different binaries. Measured three styles, two builds each:

| Style | SHA-256 | Stable within style |
|---|---|---|
| relative paths, cwd = source dir | `fc40085cb1d404506f8c241968614ed05e55ddbf780dec4b06b5b9d4679c87e0` | yes |
| absolute paths, same cwd | `0a26a80563973622a257ece4ec6ad5a3010d2d5167fd9d6569875dcc835a07ec` | yes |
| **relative + `-fdebug-prefix-map`/`-ffile-prefix-map`** | **`c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9`** | **yes** |

The adopted third style is also **location-independent**: building the same
sources in `/tmp/elsewhere` produced the identical hash. Without it, a build in a
differently-named directory would silently produce a different fixture — the
class of failure that record 65 was about.

This is a deliberate deviation from the CWE121 fixture's flag list, which omits
the two prefix-map flags. `build.json` records the complete flag string so
nothing is implied.

## 5. The compiler flagged the defect itself

`gcc -Wall` emits, at build time:

```
original.c:36:5: warning: pointer 'data' used after 'free' [-Wuse-after-free]
original.c:34:5: note: call to 'free' here
```

Recorded rather than suppressed: it is the first independent confirmation that
the fixture is vulnerable, before any trigger runs.

## 6. Files

| File | Content |
|---|---|
| `build.json` | Every input hash, flag, tool version, output hash, machine property, trigger observation, window identity |
| `build/original.c` | The unmodified case file (hash matches the quadruple) |
| `build/harness.c` | Evaluator-side entry point; calls `bad()` only |
| `build/build.sh` | Reproducible build recipe |
| `build/trigger.sh` | Deterministic trigger; `--repeat N` reports distinct observations |
| `build/original.elf` | The binary: 25344 bytes, `c9c2632e…23c9` |
| `readelf.txt` | `readelf -h -l -S -d -n` dump |
| `trigger-observation.txt` | Recorded runs: single, 50× determinism, 10× ASLR-on contrast |
| `isolation-reset.txt` | Isolation checks, window identity, reset status |
| `SHA256SUMS` | Hashes of the above |

## 7. Machine properties (measured from `readelf.txt`)

```
type        EXEC, non-PIE
entry       0x4011b0
Build ID    951731d93ab7aa9e2a94dc87fb8915b784dd693a
NX          enabled (GNU_STACK RW, no E)
RELRO       partial (GNU_RELRO present, no BIND_NOW)
canary      absent
NEEDED      libc.so.6
debug info  present, not stripped
```

## 8. Re-verify

```bash
# from this package
sha256sum -c SHA256SUMS                       # package integrity
python -c "import json;json.load(open('build.json'))"   # schema sanity

# in the guest, from build/
./build.sh                                    # must print c9c2632e…23c9
./trigger.sh                                  # must print exit_code=0 stdout_hex=05040a
./trigger.sh --repeat 50                      # must print one distinct line, 50x
```

## 9. Limits, stated plainly

- **The window was not baseline-clean.** It ran on working snapshot uid 14, not
  the baseline uid 11. Record 88 §3.1 asks for a baseline revert before a run;
  that was not done because uid 14 holds the un-archived T6.2 state. See
  `isolation-reset.txt` §2.
- **The reset half of the window is open.** The VM is still running with 12
  `.lck` directories; artifacts were copied out and hash-verified, but no power-off
  and no revert happened. See `isolation-reset.txt` §3.
- **Determinism is conditional on the environment recorded here** — same binary,
  same glibc 2.39, ASLR disabled. A different libc would change the tcache
  residue bytes, so `05040a` is an observation, not a universal constant.
- **No V4 symbolic check, no repair candidate, no result bundle.** The packaging
  constraints in the task (dual manifest, V0 candidate uniqueness) apply when the
  bundle is made, and were not exercised here.
