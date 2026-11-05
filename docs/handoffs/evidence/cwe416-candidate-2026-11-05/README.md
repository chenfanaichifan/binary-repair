# CWE416 no-input — repair candidate and V0–V5 evidence

- Date: 2026-11-05 (guest window 23:15–23:20 local, `run-log.txt` starts at `15:19:08Z`)
- Owner: Member 3 (guest execution / evidence)
- Fixture: `fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/`
  at `584b912` — **unchanged by this pass**, contract included
- Candidate: `candidate.elf`, `46d16e99…fcd0`, 25,344 bytes
- Original: `c9c2632e…23c9`, 25,344 bytes
- Result: **V3 1/1 valid, invalid not applicable**; V4 **not_run**; T8.3 **blocked**

This directory is a Route B bundle, not a report: `routeb/attempt_writer.py`
reads `original.elf`, `candidate.elf`, `edit-manifest.json`, `audit.json`,
`manifest-repaired.json` and `reproducibility.json` from here without a mapping
step. `routeb-verifier.txt` shows that call, and `gate-index.json` is the
V0–V5 index over the same files.

Record 121 said a candidate is not the fixture author's job. That was true of
the fixture pass; this pass asked for one explicitly, so the boundary moved by
instruction. `fixtures/` is still untouched.

## 1. The candidate is a five-byte edit

`contract.json#authorized_edits[0]` allows "drop the `free()` and accept the
leak". The other option — moving the read ahead of `free()` — needs new
instructions, so it changes more than it has to. This takes the first option:

| | |
|---|---|
| site | `CWE416_Use_After_Free__malloc_free_char_01_bad`, vaddr `0x401305` |
| file offset | `4869` (`0x1305`) |
| before | `e8 e6 fd ff ff` — `call 4010f0 <free@plt>` |
| after | `90 90 90 90 90` — five `nop` |
| bytes changed | **5**, all inside one recorded interval |
| size delta | **0** — no byte added, no code cave, no C replacement |

Nothing else moves: entry `0x4011b0`, 37 sections, 14 relocations, program
headers and section layout identical on both sides (`audit.json`). The 100-byte
block stays allocated, so `printLine()` reads the block it was given instead of
whatever `free()` wrote into it.

The trade is a 100-byte leak at process exit. That is inside the contract's
authorised edit, and it is the reason the fix is one instruction rather than a
relocated read.

## 2. V0–V5

| Gate | File | Result | What was measured |
|---|---|---|---|
| V0 identity | `v0-identity.json` | **passed** | candidate was built from this `original.elf`; `c9c2632e…` equals `tests/valid.json#original_sha256` |
| V1 structure | `audit.json` | **passed** | same size, same entry, no W+X segment, all changed bytes inside the interval, headers and section layout unchanged |
| V2 interface | `v2-interface.json` | **not_run** | a static observation only — see §4 |
| V3 behaviour | `manifest-repaired.json` | **passed** | `input_mode: none`, valid **1/1**, `passed=1 total=1`, `invalid: not_applicable` |
| V4 symbolic | `v4-symbolic.json` | **not_run** | no symbolic engine ran — see §4 |
| V5 reproducibility | `reproducibility.json` | **passed** | source rebuilt twice to `c9c2632e…`, patch replayed twice to `46d16e99…` |

Supporting files: `edit-manifest.json` (Route B schema 2, including the edit and
the runtime manifest), `patch-report.json` (raw patch output), `environment.json`
(toolchain), `independent-views/` (readelf and objdump dumps of the candidate),
`run-log.txt` (the whole window), `repeat-runs.txt` (five runs of each binary
under default ASLR), `00-window-host.txt` (hypervisor side), `tools/` (the five
scripts that produced all of it).

## 3. V3, and the control that makes it mean something

`routeb/run_manifest_repaired.py --contract fixtures/…/contract.json` loads the
contract through `SecurityContract` (the v3 schema), not by reading the JSON
field, so the mode is `none` because the schema says so:

```
input_mode: none   invalid: not_applicable   valid: 1/1
passed: 1   total: 1   repaired_pass: true
binary_sha256: 46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0
```

The same runner and the same manifest pointed at the **unrepaired** original
gives `valid: 0/1`, `passed=0`, `repaired_pass=false`, exit 1
(`manifest-repaired-original.json`). One case that flips between the two
binaries is the whole evidence value here; without the control, `1/1` on a
single case would only say the runner ran.

Determinism, stated exactly:

- the repaired binary prints 100 bytes — 99 `A` then `\n` — with ASLR on or off,
  because it no longer reads allocator metadata;
- the original prints allocator residue through `printLine()`, so the byte
  count depends on where the heap landed. With ASLR off that is the frozen
  `05040a` in `defect.json`; the control run had ASLR on and recorded `4ba2020a`.
  Both are residue; neither is the 100-byte string.

`repeat-runs.txt` is five runs of each under default ASLR: five identical output
hashes for the candidate, five different residues for the original. That is the
difference between a repair and a coincidence.

`invalid: not_applicable` is not `0/0` and not `0/2`. There is no `invalid.json`
in the fixture and no invalid row in the manifest; the runner refuses one if it
appears. The one valid case is the entire input domain of a function that takes
no arguments and reads no stdin.

## 4. What is deliberately not claimed

**V2 is `not_run`.** The directory carries `v2-interface.json`, but it is marked
`"scored": false`: it records that the target symbol, the dynamic symbol table,
`NEEDED` and the entry point are unchanged, and nothing more. Route B's
`attempt_writer` maps V2 to `not_run` because no interface check is implemented
there, and inventing a verdict from a symbol diff would be exactly the kind of
upgrade this repository avoids.

**V4 is `not_run` and stays that way.** No symbolic or bounded-model engine ran.
`v4-symbolic.json` records `claimed_scope: null`. A replay result is `replay`
scope; calling it binary-level would be false, and calling it model-level would
be worse.

**This is not a verdict.** `contract.json#required_obligations` still lists
`symbolic`, so an attempt assembled from this bundle is
`REQUIRED_CHECK_NOT_RUN` → `inconclusive`, not `pass`. That is the acceptance
engine's call to make on the evidence, not this directory's to pre-empt.

**T8.3 stays blocked.** No second defect class and no second sample is described
here. One repair of one sample is not evidence that a class is covered.

## 5. Re-running it

```sh
# inputs: the fixture, routeb/run_manifest_repaired.py, routeb/contract_mode.py,
# app/domain/contracts.py, and the five scripts in tools/
# layout: $KIT/fixtures/public/<fixture>, $KIT/routeb/, $KIT/app/, $KIT/tools/
# in the gate4-harness guest (uid 11), as uid 1000:
sh "$KIT/tools/run_all.sh" 2>&1 | tee ~/run-log.txt
```

Two things that cost a run to learn:

- the fixture ships `original.elf` mode `100644`; the runner needs it
  executable. `run_all.sh` copies then `chmod 755`. Without it every case is
  `Permission denied` and the exit code is 126, which looks like a failed case.
- `sha256sum -c SHA256SUMS` must be run from this directory. The listing holds
  the files except itself and `bundle-sha256.txt`, and `bundle-sha256.txt` is
  `sha256(SHA256SUMS)` so a package can be checked from outside without
  self-reference.

## 6. The first attempt failed on a permission bit

The first run died at step 5 with `setarch: failed to execute ./original.elf:
Permission denied` (exit 126) and `runner exit=2`: the fixture ships
`original.elf` as mode `100644`, and both `cp` and `tar` keep it that way, so the
copy was not executable. Note that this fails at the *runner*, not at the case —
`[Errno 13] Permission denied` in `run_manifest_repaired` reads like a missing
file if you only glance at it.

The script was fixed (`chmod 755` after each copy) and the window re-run from an
empty `work/` and `bundle/`. This directory holds that second run only;
`run-log.txt` is clean end to end. The failure is written down here instead of
being shipped as a partial log, because the trap is worth more than the
transcript of it.
