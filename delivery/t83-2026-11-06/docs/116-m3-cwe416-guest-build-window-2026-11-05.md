# 116 — CWE416 in the guest: the committed recipe does not link, the sample itself is stable

Date: 2026-11-05
Author: M3 (guest build / evidence)
Window: `revertToSnapshot gate4-harness` (uid 11) → cold boot 21:24 → build → measured

Numbering note: `100`–`111` are M1's on the integration line; `112`–`115` are M3's
on `member-3/t62-host-safe`. This record is `116` so that the two branches can
merge without a collision.

Nothing here writes to `fixtures/`, `tools/`, `app/`, or any interface contract.
The fixture's bytes are exactly as `integration/live-bridge-2026-11-03` has them.

**Reclassified 2026-11-05 (record 118 §7): this record is a build/trigger
diagnostic, and is NOT a T8.3 fixture.** The `src.c` measured below is
team-authored, so it cannot carry the second-defect-class obligation no matter
how clean its measurements are. Specific consequences:

- `original.variant.elf` is not shipped and must never be ingested — it differs
  from `build.json#argv` in two ways (no `harness.c`, plus prefix-map flags) and
  cannot stand in for the artefact that argv describes.
- That fixture's `build.json#output.sha256` stays `null`.
- Nothing here relieves T8.3.

The root cause of the link failure is resolved in record 118 §1: the upstream
`original.c` guards its `main` with `#ifdef INCLUDEMAIN` (line 91) and the T30
gcc line does not define it, while this fixture's `src.c` had an unguarded
`main` at line 90. It is a defect in the authored file, not in the toolchain or
the window.

---

## 0. What actually happened

| Step | Result |
|---|---|
| Revert to snapshot uid 11 `gate4-harness` | done, `snapshot.current = "11"` |
| Cold boot, confirm a reset rather than a resumed session | done, see §1 |
| `sh build.sh` as committed | **exit 1 — the recipe cannot link** |
| Locate the cause | `main` defined in both `src.c:90` and `harness.c:20` |
| Build the minimal variant (`src.c` alone), run the 4 + 2 matrix | 4 MATCH / 2 DIFF, as designed |
| Repeat the trigger 150× | no divergence |
| ASan build of the same source | `heap-use-after-free`, `src.c:72` |
| Test digest portability | path-bound without a prefix map, portable with one |
| Fill `build.json#output.sha256` | **not done**, and §8 says why |

Evidence, including the built binary, is in
`docs/handoffs/evidence/cwe416-build-2026-11-05/` with its own `08-SHA256SUMS`
(8/8 verified after transfer to this host).

---

## 1. The window was a reset, and here is the proof

Reverting is easy to claim and easy to get wrong, so the differences are recorded
rather than asserted:

| Observation | Resumed session (uid 14) | Reset window (uid 11) |
|---|---|---|
| `.vmsd snapshot.current` | `14` (`t15-t6-work`) | `11` (`gate4-harness`) |
| `system boot` | 2026-11-05 17:38 | 2026-11-05 21:24 |
| `$HOME` contents | `Binary_Repair`, `routeb-fix`, `suite`, `.venv`, … | `D`, `evaluator`, `repair-input`, `route-a` |

The third row is the one that matters: a resumed session would still show the
directories the previous run created. Their absence, together with a boot time
two minutes old, is what makes this a reset and not a continuation.

`01-isolation.txt` also records `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`,
`GNU ld 2.42`, kernel `6.8.0-147-generic`, and `gcc`'s own SHA-256
`1b99826121ae6682…`, so the compiler is pinned rather than named.

---

## 2. The committed recipe fails, and the failure is structural

```
$ sh build.sh
/usr/bin/ld: /tmp/cc5lnhqY.o: in function `main':
harness.c:21: multiple definition of `main';
  /tmp/cciQn9Xh.o:src.c:91: first defined here
collect2: error: ld returned 1 exit status
```

Both translation units export a global `main`:

```
$ gcc -c src.c && nm src.o | grep -w main
00000000000001dc T main
$ gcc -c harness.c && nm harness.o | grep -w main
0000000000000000 T main
```

`build.json#argv` asks for `gcc … -o original.elf src.c harness.c`, so as written
the recipe has never been able to produce `original.elf`. `build.json#output.sha256`
being `null` is not the only reason it is unset; the command itself does not link.

This is exactly the class of defect that stays invisible while nobody has a
compiler: the fixture was reviewed, hashed and intaken, and its one build step
raises a linker error the first time it is executed.

---

## 3. What was measured instead — stated as a variant, not as the fixture

Smallest variant that still exercises the sample: `src.c` alone. Its own `main`
already implements the `--uaf` dispatch:

```c
if (argc > 2 && strcmp(argv[2], "--uaf") == 0) { badSink(argv[1]); }
else                                          { goodSink(argv[1]); }
```

Flags are the committed flags plus a prefix map (§6). Result: `EXEC` non-PIE
x86-64, entry `0x401190`, 20,040 B, `f1019618f0a6180b…`.

Matrix against that binary:

| case | kind | rc | stdout |
|---|---|---|---|
| `valid-empty` | valid | 0 | `"\n"` — MATCH |
| `valid-one` | valid | 0 | `"a\n"` — MATCH |
| `valid-max49` | valid | 0 | 49×`m` + `\n` — MATCH |
| `valid-spaces` | valid | 0 | `"two words\n"` — MATCH |
| `invalid-first` | invalid | 0 | 49×`X` + `\n` — DIFF |
| `invalid-longer` | invalid | 0 | 49×`X` + `\n` — DIFF |

**4 MATCH / 2 DIFF is the expected shape, not a regression.** `tests/invalid.json`
records the post-repair expectation. The original prints the reuse sentinel
instead of the input, which is the defect becoming observable.

Two honest caveats about the matrix:

1. Both invalid cases produce byte-identical output, because `badSink` fills the
   reused block with `X` regardless of input. The pair still discriminates a
   repair, since the expected strings differ, but it is not two independent
   probes of the same path.
2. `harness.c` carried the `MAX_INPUT_BYTES 4096` guard and the `argc > 3` usage
   branch. The variant has neither, so on this binary the contract's
   `valid_domain` ("length 0..4096") is not enforced — it is only true of inputs
   the caller chooses. That is a second reason §8 prefers fix B over fix A.

---

## 4. Trigger stability: 150 runs, no divergence

| Case | Runs | Distinct stdout digests |
|---|---|---|
| `./original 1234567 --uaf` | 50 | 1 |
| `./original use-after-free --uaf` | 50 | 1 |
| `./original 1234567` | 50 | 1 |

The output is deterministic by construction: `badSink` allocates a same-size
block and writes `X` into it, so the stale read sees sentinels rather than
whatever the allocator happened to leave. `06-stability.txt` holds the buckets.

That determinism is a property of the harness technique, not of the language.
`PROVENANCE.md` already says as much, and it is why the next section matters.

---

## 5. ASan confirms a real read after free

An ASan build of the same source:

```
ERROR: AddressSanitizer: heap-use-after-free ... READ of size 2
    #0 fputs
    #1 printLine  src.c:43
    #2 badSink    src.c:72
    #3 main       src.c:97
0x506000000020 is located 0 bytes inside of 50-byte region
```

The good path exits 0 and clean under the same build. So the `X` output is a
symptom of a genuine use-after-free, not of `printLine` printing something odd.
`07-asan.txt`.

---

## 6. The digest was bound to the build directory, and that is now measured

`-g` without `-fdebug-prefix-map` records `DW_AT_comp_dir`. Same source, same
flags, same compiler, two directories:

| Directory | Digest | Size |
|---|---|---|
| `~/cwe416/run-b` | `20a58ba5b453db68…` | 20,064 B |
| `~/cwe416/run-c` | `0927df3e9d44526e…` | 20,064 B |

With `-fdebug-prefix-map=$PWD=. -ffile-prefix-map=$PWD=.` both agree at
`f1019618f0a6180b…` (20,040 B).

This was a prediction in record `115`; it is now a measurement. A digest recorded
without the map is a statement about a directory, not about a source file, and
`build.json` currently invites exactly that mistake by pinning flags and asking
for one digest.

---

## 7. `testcasesupport/io.c` and `std_testcase.h`: not needed here

The question was whether the rebuild needs the Juliet support files. For this
fixture: **no**.

```
src.c      #include <stdio.h> <stdlib.h> <string.h>
harness.c  #include <stdio.h> <string.h>
```

Neither file includes `std_testcase.h`, and the sample does not come from the
corpus, so the build needs only `gcc` and the two sources. The corollary is worth
stating plainly: **this fixture is not "rebuildable only in the recorded guest."**
Any machine with gcc 13.3 and these bytes can rebuild it, once the recipe links
and carries a prefix map. What the recorded guest buys is a *clean* window, not
the ability to build at all.

Where the support files do matter:

| Case | Needs `testcasesupport`? | Status |
|---|---|---|
| `CWE416_Use_After_Free__malloc_free_char_01` (this, synthetic) | no | — |
| `CWE121_src_char_declare_cpy_51b` (upstream Juliet) | yes | added on `member-3/t62-host-safe` (`472b26e`): `source/` with the case plus `io.c`, `std_testcase.h`, `std_testcase_io.h`; **not yet on the integration line** |
| T30 upstream CWE-416 build (`evidence/T30`) | yes | rebuild needs the Juliet corpus; this host now has it at `~/evaluator/downloads/juliet-v1.3.zip`, SHA-256 `ada9d7e1…f38eb`, verified against `provenance.md`. T30 keeps its `original.elf`, so it is complete evidence, only not self-contained |

If a self-contained T30 rebuild is wanted, the four support files can be added
under `evidence/T30/build/` exactly as they were added for CWE121. I did not do
it in this round because it changes a directory whose `SHA256SUMS` and
`build.json` are already cited, and the CWE416 work below is the blocking item.

---

## 8. Why `build.json#output.sha256` is still null

Filling it with `f1019618…` would bind a recipe that differs from
`build.json#argv` in two ways — `harness.c` dropped, prefix map added. That is a
silent substitution of one artefact for another, which is the failure mode this
project has already paid for once (`357207ae…` / `e1cbaeb…`). So it stays null
until the fixture owner chooses a fix.

Two fixes, both small, both the fixture owner's call:

**Fix A — drop `harness.c` from the recipe.** One line in `build.json#argv` and
one in `build.sh`. Cheapest. Cost: loses the 4096-byte guard and the `argc > 3`
usage branch, so the contract's `valid_domain` stops being enforced by the binary.

**Fix B — remove `main` from `src.c`** (keep it a library: `duplicate`,
`badSink`, `goodSink`) and let `harness.c` own the entry point. Costs a source
edit, keeps the guard, and matches the intent that `harness.c` exists "so the
sink is reachable from a fixed command line". This is the one I would take.

Either fix needs, in order:

1. `-fdebug-prefix-map=$(pwd)=. -ffile-prefix-map=$(pwd)=.` added to
   `build.json#flags`, `build.json#argv` and `build.sh`.
2. A build in the guest, recorded with `01-isolation`-style fingerprint.
3. `build.json#output.sha256` set to the measured value.
4. `tests/valid.json` and `tests/invalid.json`: `original_sha256` set to the same
   value (both are `null` today).
5. `tests/SHA256SUMS` regenerated, because the edit changes `src.c` or `build.sh`.

Until that happens this fixture has no legitimate `original.elf`, so:

| Gate | State |
|---|---|
| V0–V5 | `not_run` — no buildable original from the committed recipe |
| candidate | none — no repair exists and the contract is not loadable (record `113`) |
| 4 valid + 2 invalid | present in the fixture, unchanged by me; measured only against the variant |
| T8.3 | still `blocked`; no second public sample was invented |

The variant binary is shipped as `original.variant.elf` on purpose. Naming it
`original.elf` would make it droppable into the fixture and indistinguishable
from the artefact the recipe is supposed to produce.

---

## 9. Inventory

`docs/handoffs/evidence/cwe416-build-2026-11-05/`

| File | SHA-256 (first 16) |
|---|---|
| `01-isolation.txt` | `000b6c9a268c3535` |
| `02-committed-recipe-failure.txt` | `cd60a309e539fc30` |
| `03-recipes-and-digests.txt` | `6adf05279363ae95` |
| `04-readelf.txt` | `d7b5702fcd8d8731` |
| `05-matrix.txt` | `c508d543eda1f8c9` |
| `06-stability.txt` | `bffbfab49ef68c76` |
| `07-asan.txt` | `a31cd47ee4eece73` |
| `08-SHA256SUMS` | covers the other ten |
| `original.variant.elf` | `f1019618f0a6180b` |
| `matrix.py` | `39e2434f10a4877a` |
| `collect.sh` | `8fa837a8b24582a7` |
| `README.md` | `86663112d01e8732` |

The eight text artefacts were verified 8/8 on this host after `scp` from the
guest, before being committed; the two scripts were added afterwards and the
manifest regenerated to eleven entries.

`collect.sh` is the exact script that produced `01`–`08` inside the guest;
`matrix.py` is the runner behind `05-matrix.txt`. Both are included so M4 can
re-run the collection instead of trusting the transcripts — the same reason the
CWE121 fixture ships its oracle rather than only its verdicts.
