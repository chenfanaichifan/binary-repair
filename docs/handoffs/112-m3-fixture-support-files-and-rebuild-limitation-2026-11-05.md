# 112 — Fixture support files delivered; rebuild limited to the recorded guest

**Owner:** M3 · **Date:** 2026-11-05 · **Status:** support files **added to the
working tree and hash-verified**; **rebuild remains `not_run`** — it can only
happen inside the recorded guest (snapshot 11 / `gate4-harness`). V0–V5 gate
labels are unchanged by this record. T8.3 stays **blocked**.

Numbering: `95`–`99` are taken by the VMer window, Route A behaviour, T7.3,
T6.2 and the M1 review; `93`/`94` live on the live-bridge line and are not in
this tree.

Renumbered from `100` on 2026-11-05: while this record sat uncommitted in the
M3 worktree, M1 filled `100`–`111` on the integration line with a different
`100` and `101`. Two records under one number is exactly the ambiguity a
handoff number exists to prevent, so this record moved to `112` rather than
keeping a number it no longer owns. No content changed in the move.

## 1. Executed vs proposed (read this before quoting anything below)

| Item | State |
|---|---|
| Copy support files into `fixtures/public/CWE121_src_char_declare_cpy_51b/` | **executed** |
| Recompute every hash and compare against the frozen `SHA256SUMS` record | **executed** — 24/24 match, 0 mismatch |
| Write a full 26-entry `SHA256SUMS` for the fixture root | **executed** |
| Download the Juliet v1.3 archive and verify its SHA-256 | **executed** — arrived byte-identical to `ada9d7e1…f38eb` |
| Add the unmodified case source and `testcasesupport/` to the fixture | **executed** — 4 files, hashes cross-checked against two independent records |
| Re-hash every packaged entry from inside the ZIP | **executed** — 26/26, 0 mismatch |
| Run `tests/v3_oracle.py` on the host (executes no binary) | **executed** — 24 tests OK |
| Build the fixture binary inside the guest | **not run** — host may not compile |
| Re-run the six-case trigger against a fresh build | **not run** |
| Produce a CWE416 candidate | **not run** — no Juliet corpus on this host (see §6) |

Nothing in this record is a gate result. It is packaging and provenance work.

## 2. What was missing, and what was added

The `v0multi` evidence bundle carried the two binaries and the analysis JSON,
but **no build inputs**. A reviewer receiving only that bundle cannot rebuild
`original.elf`, so the ELF hash could be confirmed but its origin could not.
That is the gap this record closes.

Added to `fixtures/public/CWE121_src_char_declare_cpy_51b/`:

| Path | Role |
|---|---|
| `build/build.sh` | The exact build command; requires `JULIET_ROOT` |
| `build/harness.c` | The argv harness (`main` calls the Juliet sink with `argv[1]` directly) |
| `build/run_manifest.py` | Runner that executes the six cases and prints byte-exact comparison |
| `provenance.md` | Full chain: suite archive SHA-256 → case file → build flags → ELF hash |
| `evidence/` (14 files) | Raw observation output from 2026-10-20; see §5 for what these are **not** |
| `tests/README.md` | Manifest semantics, capacity rule, per-case table, freeze rule |
| `tests/v3_oracle.py` | Pure judging layer for V3 — executes nothing |
| `tests/test_v3_oracle.py` | 24 unit tests for that judging layer |
| `source/CWE121_…_51b.c` | **The unmodified NIST case file** — the source reproduction gap |
| `source/testcasesupport/{io.c,std_testcase.h,std_testcase_io.h}` | **The support unit** — previously only reachable through an external checkout |
| `source/SHA256SUMS` | 4 entries binding the above |
| `build/build-from-source.sh` | Self-contained rebuild that uses `source/` and needs no `JULIET_ROOT` |
| `SHA256SUMS` (new, root) | **32 entries** covering the whole fixture |

Files that were **already present and deliberately untouched**:

| Path | SHA-256 (must not change) | Verified |
|---|---|---|
| `original.elf` | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` | **unchanged** |
| `tests/valid.json` | `17b2ee399db5ef43ba14978c497d71dc45d28aaa685ff90a60baaabc6f221e76` | **unchanged** |
| `tests/invalid.json` | `d493f370a37b25f910eb72cb6f9202856e46be0e42e76922db38a30769f8190d` | **unchanged** |
| `tests/SHA256SUMS` | (two flat entries) | **unchanged** — the ingest-bound file |
| `contract.json` | `15f6b492…` | **unchanged** |

`tests/SHA256SUMS` was left in its original two-line flat form on purpose. M5
ingested that file; rewriting it to an `tests/`-prefixed form would change bytes
that an accepted bundle already binds. The new root-level `SHA256SUMS` is
additive and is the one to use for whole-fixture verification.

### 2a. A latent defect this round exposed

Before the support files landed, `.gitattributes` marked only
`fixtures/public/**/tests/*.json` as byte-exact. The tree now contains
`evidence/*.txt` and `build/*`, which were **not** covered, so a fresh Windows
checkout could apply EOL conversion and make the new `SHA256SUMS` fail wholesale
— a verification failure that says nothing about the fixture.

Fixed by opting the whole tree out of text handling:

```gitattributes
fixtures/public/** -text
```

Verified with `git check-attr text` on `evidence/01-provenance.txt`,
`build/build.sh`, `tests/v3_oracle.py`, `provenance.md` and `tests/valid.json`:
all five report **`unset`**. Recorded here because it is the kind of defect that
only shows up on someone else's machine, months later.

This was not hypothetical. The NIST case file and `io.c` are stored **CRLF**:

| File | CRLF | bare LF |
|---|---:|---:|
| `source/CWE121_…_51b.c` | 50 | 0 |
| `source/testcasesupport/io.c` | 211 | 0 |

`8387d646…343b` is the hash **of the CRLF bytes**. Any normalising checkout would
have changed 261 line endings and made the source hash unverifiable.

### 2b. Where the source files came from, and why the chain closes

The archive was downloaded to the path `provenance.md` already names:

| Property | Value |
|---|---|
| URL | `https://samate.nist.gov/SARD/downloads/test-suites/2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip` |
| Local path | `~/evaluator/downloads/juliet-v1.3.zip` |
| Size | 152,957,342 B |
| SHA-256 | `ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb` — **matches the value frozen in `provenance.md`** |
| Entries | 106,316, top level `C/` |

Four files were extracted and each hash was checked against a record written
**before** this round:

| File | Size | SHA-256 | Record it matches |
|---|---:|---|---|
| `CWE121_…_51b.c` | 1,434 B | `8387d646…343b` | `provenance.md` (2026-10-20) |
| `io.c` | 5,429 B | `50ace91d…299c` | T30 `build.json` (2026-11-05, from the guest checkout) |
| `std_testcase.h` | 4,004 B | `a78aaf3a…b8d0` | T30 `build.json` (same) |
| `std_testcase_io.h` | 1,457 B | `6459df50…6fb6` | no prior record — first one is `source/SHA256SUMS` |

The first matches a record from the CWE121 line; the next two match T30's
records, which came from the **guest's own checkout**. Two independent chains
agreeing is what makes this a provenance fix rather than just a file copy.

Dependency closure was checked, not assumed: `std_testcase.h` includes
`std_testcase_io.h` (line 124) and `io.c` includes `std_testcase.h`. The
`<io.h>` at `std_testcase.h:54` is inside the Windows branch and is not used on
Linux. So `source/` is complete for this build and needs no other file.

### 2c. `build-from-source.sh` deliberately does not promise `aa428157…8393`

The new script compiles from `source/` with the **same flag list** as
`build/build.sh`, differing only in where the sources come from. It will not
necessarily reproduce the frozen ELF, and the header says so:

`-g` records `DW_AT_comp_dir` and the source paths handed to gcc. T30 measured
this on the CWE416 fixture — identical sources, three path styles, three
different-but-internally-stable hashes (`fc40085c…`, `0a26a805…`, `c9c2632e…`).
The path style used on 2026-10-20 was never recorded, so no recipe can claim
`aa428157…8393`.

What the script does guarantee: inputs are hash-checked before compiling (it
exits 1 on a case-source mismatch), the recipe is fixed in the file, and repeated
runs with that recipe are comparable to each other.

Treat its output as an equivalent-behaviour rebuild. Before using it for
anything, confirm the boundary on it: 49 × `A` exits 0, 50 × `A` still overruns.

## 3. Test-matrix status: already 4 valid + 2 invalid

The requested matrix shape is already satisfied by the frozen manifests — no
new cases were invented:

| File | Count | Case ids |
|---|---:|---|
| `tests/valid.json` | 4 | `valid-empty`, `valid-smallest`, `valid-typical`, `valid-maximum` |
| `tests/invalid.json` | 2 | `invalid-first`, `invalid-longer` |

Both files still hash to the values frozen on 2026-10-20, so the matrix did not
drift when the support files were added. A 4/6 score against `original.elf` is
the expected V0 shape; per `tests/README.md` it is **not** Gate 6 and **not** a
passing V3.

## 4. Why the `v0multi` bundle was not rebuilt

`dist/P3B-execution-bridge-2026-11-05-v0multi.zip` is
`5e6535868bbe92a611145cfdc34dcae05c9bf06fd46e03f5497588db3f2892c8`
(26,960 B, 15 flat entries). M5 ingested that exact byte stream and M4 received
it for task-24. Re-zipping it with support files would produce a second hash for
the same evidence set, which is the hash-fork failure already paid for once on
this project.

So the support files ship as a **separate, additive artifact** under `dist/`.
It is not a replacement for `v0multi`, it carries no gate conclusion, and it
must not be ingested as a result bundle.

Two builds of this artifact exist, because the fixture gained `source/` after the
first one was cut. **v2 supersedes v1**; v1 is listed only so a hash someone
already copied is not orphaned.

| | v1 | **v2 (use this)** |
|---|---|---|
| File | `…-2026-11-05.zip` | `…-2026-11-05-v2.zip` |
| Size | 39,658 B | **47,475 B** |
| SHA-256 | `e407a6ec…cec6` | `1069aa79bda7e407f5fc7eaac2ff043fec0e061cc369fa8e73f7502f22e4fd58` |
| Entries | 27 | **33** |
| `SHA256SUMS` coverage | 26 | **32** |
| Contains `source/` | no | **yes** |
| Magic | `PK\x03\x04` | `PK\x03\x04` |

v1 is incomplete for a rebuild: it carries the build recipe but not the case
source, so `build-from-source.sh` could not run from it. Nothing had ingested v1
when v2 was cut, so no evidence chain was broken by the supersession.

Checks run on **v2** before recording it:

| Check | Result |
|---|---|
| ZIP magic bytes | `PK\x03\x04` |
| Every entry re-hashed **from inside the archive** against `SHA256SUMS` | **32 checked, 0 mismatch** |
| Entry count = `SHA256SUMS` entries + 1 (the sums file itself) | 33 = 32 + 1 |
| `tests/v3_oracle.py` unit suite | **24 tests, OK** |
| `test_manifest_pair_matches_contract` | **passes** — the frozen manifests agree with `contract.json`'s capacity rule |

`v0multi` (`5e653586…92c8`) and this package (`1069aa79…fd58`) are two artifacts
with two purposes. Citing one where the other belongs is a provenance error.

### 4a. No new result bundle this round, and that is deliberate

The standing packaging rules still apply to any future result bundle: a dual
manifest, and a V0 set whose `candidate_sha256` matches **exactly one** file. This
round produced no result bundle because there is nothing new to bundle:

- no new candidate — the CWE416 repair candidate is blocked on the contract
  question in record 101, and the CWE121 candidate `208574ab…6717` is unchanged;
- re-packaging the same candidate again would create a second hash for one
  evidence set, which is the failure mode `v0multi` was created to stop repeating.

The support-files package is a different artifact class: it carries build inputs,
not analysis results, and it must never be ingested as a result bundle.

## 5. `evidence/` is observation output, not a gate verdict

The 14 files under `evidence/` are raw terminal output captured on 2026-10-20:
`readelf`, `checksec`, `objdump`, `gdb`, the boundary run, the manifest run.
Several carry gate-ish names (`07-gate6-crash-evidence.txt`,
`02-checksec.txt`). They are **measurements**, and a measurement file is not a
`passed` label:

- no file in `evidence/` states a gate result;
- V4 stays `not_run` at binary level — nothing here is symbolic;
- Gate 6 partial status is unchanged; a crash under `gdb` demonstrates the
  violation exists, it does not demonstrate a detector.

Anyone citing `evidence/` as gate proof should cite the record that owns the
verdict instead.

## 6. Rebuild is possible only in the recorded guest

This is the limitation to keep, and it changed shape this round rather than
disappearing.

The **corpus** part is resolved: the archive is now at
`~/evaluator/downloads/juliet-v1.3.zip` with the frozen hash, and `source/`
carries the case file and support unit inside the fixture, so a rebuild no longer
depends on an external checkout's directory layout.

The **execution** part is untouched: `AGENTS.md` forbids compiling or running a
binary on the host, and this host has no compiler at all (`gcc` and `cc` both
absent). So the build still has to happen in the guest.

Consequently the rebuild must run in the guest the fixture was measured in:

| Property | Recorded value |
|---|---|
| Snapshot | **11** (`gate4-harness`) — same baseline used by `docs/handoffs/95` and `docs/handoffs/96` |
| Guest OS | Ubuntu 24.04.5 LTS, x86_64, kernel 6.8.0-147-generic |
| Compiler | gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| Flags | `-O0 -g -fno-stack-protector -fno-pie -no-pie -Wall` |
| Expected output | 26,792 B, SHA-256 `aa428157…8393`, Build ID `a39b24de7d9fba70a130a90a7d79fa4a3a8c85ce` |

A clean-evidence rebuild would have to follow the window discipline from
`docs/handoffs/95` §3 — one window, one build, no reuse:

```text
1. VM powered off; record .vmsd snapshot.current
2. revertToSnapshot 11                       # gate4-harness
3. boot; record id -u, uname -a, gcc --version
4. JULIET_ROOT=<juliet> bash build/build.sh ./original.elf
5. sha256sum ./original.elf                   # must equal aa428157…8393
6. python3 build/run_manifest.py              # must print 4/6 against original
7. shutdown clean; confirm no .lck under the VM directory
8. revertToSnapshot 11 again                  # leave the guest clean
```

Step 5 is the whole point: a rebuild that produces a different hash is a
different binary and invalidates every approval bound to `aa428157…8393`.
Step 6 is the trigger re-measurement — 50 × `A` must still exit 0 with a silent
1-byte overrun and 100 × `A` must still die with SIGSEGV (`rc=139` or `-11`).

**None of steps 1–8 was executed by me.** The host has no guest channel and no
corpus, so this section is a proposed procedure, exactly like everything in
`agent_docs/`. Until someone runs it in the guest, the honest statement about a
rebuilt binary is `not_run`, and the shipped `original.elf` remains bound to its
2026-10-20 build only.

If the team decides the rebuild is not worth a window, that is a legitimate
choice — but then the limitation must travel with the fixture: *origin verified
by provenance chain, not by reproduction.*

## 7. CWE416: the corpus block is gone; the real block is elsewhere

Steps 1 and 2 of the previous version of this section are now closed:

- **The corpus is here.** `C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c`
  is in the archive, 3,198 B, SHA-256 `fa84a6bb…7f42e` — **identical to the value
  T30 recorded** after fetching the same file from `dsp-testing/samate-c-cpp` at
  commit `01e353d`. Two independent sources agree, so T30's provenance is
  stronger than it claimed, and a future rebuild does not need GitHub at all.
- **A member is selected and built.** T30 already did it, in the guest, with a
  deterministic trigger.

What remains is not a file problem and not a corpus problem. It is that the
contract schema, the Route A patch generator and the V3 oracle are all built on
an **input-boundary** defect shape, and a use-after-free has no input boundary.
Writing a `contract.json` for it would mean filling four `invalid_*` fields that
describe a rejection path CWE416 does not have, and `routea/cave.py` would then
inject a diagnostic message into a program that is supposed to print `A`s.

That analysis, with file and line evidence and three ways forward, is record
**101**. Summary of the options: extend the schema and Route A (`repair_kind`
discriminator), keep CWE416 as a trigger-only fixture with a 2-case matrix, or
pick an input-boundary class for the second sample — `CWE122`, `CWE124`, `CWE126`
and `CWE127` are all present in this archive (118 CWE families total), so option
three needs no new provenance work.

A team-authored CWE416 fixture would still **not** satisfy T8.3:
`fixtures/public/README.md` admits team-built samples, but a self-built binary is
not a *public* sample. That has not changed.

## 8. What this record does not establish

- No binary was rebuilt, executed, or otherwise touched in this round.
- No gate label moved: V4 remains `not_run` at binary level, T8.3 remains
  `blocked`, the fixture is not re-frozen.
- Hash equality proves **identity**, not correctness — `aa428157…8393` matching
  says the bytes are the same, not that the build is reproducible from the
  shipped inputs. Only a guest rebuild in §6 could say that.
- One sample supports no claim about a population; nothing here generalises to
  other Juliet members or other CWE classes.
