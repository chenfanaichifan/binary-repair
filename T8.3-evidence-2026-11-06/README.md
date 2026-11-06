# T8.3 evidence — CWE416 no-input, second sample

M3's side of T8.3: one public sample, one repair, one contract, the gate evidence
for everything except V4, and the producer evidence V4 needs. **T8.3 is not
complete and this bundle does not claim it is.** V4 stays `not_run` until M4
replays it and records its own verdict, and no `verified_by` value exists here.

## The sample, frozen

```
fixture:   fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/
           CWE-416, mechanism lifetime, heap, input_mode none

original   c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9
candidate  46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0
contract   8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b   (file)
           c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c   (canonical)

source     dsp-testing/samate-c-cpp @ 01e353daa3d28a4ce2ae68904cbcde5e03e3519d
           C/testcases/CWE416_Use_After_Free/CWE416_Use_After_Free__malloc_free_char_01.c
           original.c fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e
```

The mechanism is deliberately different from the first sample's: a *lifetime*
defect on the heap, not the bounds-check/stack case CWE121 covers. That is what
"second class" means here — one sample, not a family.

## The repair

Five bytes at file offset 4869 (`0x1305`, vaddr `0x401305`):

```
e8 e6 fd ff ff   call free@plt   ->   90 90 90 90 90
```

`contract.json#authorized_edits[0]` — drop the `free()` and accept the leak. No C
replacement, no code cave, no added bytes; `candidate/edit-manifest.json` records
`replacement_c: false`, `code_cave: false`, `bytes_added: 0`.

## Gates

| Gate | State | Counting | Evidence |
|---|---|---|---|
| V0 identity | passed | — | `gates/V0-identity.json` |
| V1 structure | passed | — | `gates/V1-structure.json` |
| V2 interface | passed | **5/5** | `gates/V2-interface.json` |
| V3 behaviour | passed | **1/1** | `gates/V3-behaviour.json`, control in `V3-control-original.json` |
| V4 symbolic | **not_run** | — | `gates/V4-not-run.json` → producer evidence in `v4/` |
| V5 reproducibility | passed | — | `gates/V5-reproducibility.json` |

`gates/gate-index.json` is the index over those six files, plus the hashes and the
one caveat that matters (below).

### V2 is a producer measurement, and says so

`gates/v2_interface.py` compares the two binaries with `readelf` on five
interface facts: the target symbol (present and unchanged), the dynamic symbol
table, `DT_NEEDED` and dynamic flags, the ELF entry point, and whether any new
dynamic import appeared. All five hold, hence 5/5.

Route B's `attempt_writer.py:219` still hardcodes `"V2": "not_run"`, so an attempt
assembled from a bundle reports `required_check_not_run` regardless of this file.
Recording 5/5 here records what was measured; wiring V2 into the executor is a
product change, not an evidence one, and it is not done here.

### V3 discriminates

Same runner, same `valid.json`: candidate `1/1`, unrepaired original `0/1`. A single
case that flips between the two binaries is the evidence; `1/1` alone only shows
the runner ran. `V3-control-original.json` is that control.

## V4, and why it is still not_run

`v4/harness-output.json` is the raw measurement from the guest
(`/opt/angr-venv/bin/python v4/v4_harness.py … --replay-runs 2`):

```
known_good  candidate  holds      eval=1 sat=0 unsat=1   11/64 steps
known_bad   original   violated   eval=1 sat=1 unsat=0   14/64 steps
replay 2 runs identical, digest cb2137a20d838e3f…cb14
property_kind pointer-flow, claimed_scope model, unknown=0 timeouts=0 complete=True
```

`v4/v4-symbolic.json` is the product evidence M1's adapter
(`tools/v4_harness_to_evidence.py`, `app/domain/v4.py` at `c41de41`) derives from
it, and it validates with hashes bound: `calibration 1/1`,
`known_bad_rejected=True`, `exploration complete`, `solver accounting complete`,
`claimed_scope model`, `forbidden_ranges None`, and the empty-disjunction
disclosure sitting in `not_claimed`. `logs/adapter.txt` is that run.

What it is not: a gate result. Per `docs/handoffs/62 §1` a producer does not
certify its own output. V4 leaves `not_run` when M4 replays the raw evidence and
writes its verdict — including `replay.verified_by="m4"`. M3 writes neither.

One honesty note carried in the evidence: the candidate's `unsat` is the
*empty-disjunction* case. Its `free()` is five `nop`s, so nothing is freed on that
path and the property question is unsatisfiable by construction. That is a real
answer to a real question, but it is not a constraint the solver worked for.

## Layout

```
fixture/     original.elf, original.c, contract.json, defect.json, tests/, support/
candidate/   candidate.elf, edit-manifest.json
v4/          v4_harness.py, harness-output.json, v4-symbolic.json
gates/       v2_interface.py, V0–V5 evidence, gate-index.json
guest/       add-m4-key.sh — installs M4's own public key; no private key here
logs/        selfcheck.txt, harness-run-1.txt, harness-run-2.txt, adapter.txt
SHA256SUMS   every file above
README.md    this file
```

`fixture/tests/SHA256SUMS` is the fixture's own manifest, carried unchanged from
the repository so the fixture can be checked independently of this bundle.

## Verify it

```sh
sha256sum -c SHA256SUMS
cd gates && python3 v2_interface.py --original ../fixture/original.elf \
    --candidate ../candidate/candidate.elf \
    --symbol CWE416_Use_After_Free__malloc_free_char_01_bad --out /tmp/v2.json
```

`v2_interface.py` exits 0 only if all five checks pass. On the guest, V4 is
reproduced with the command recorded in `logs/harness-run-1.txt`; the output file
should hash to `9c6eeda7…8ca8c` and its replay digest should start `cb2137a2`.

## Access

`m4verify@192.168.30.128:22` over VMnet8 IPv4 — non-root, no sudo, password
locked, public key only. The keypair is M4's: generate one, hand the public half
over, and M3 installs it with `guest/add-m4-key.sh`. This bundle contains no
private key for any account.

## What M3 did not do

- No `verified_by`, anywhere. Not in the JSON, not in the README, not in the log.
- No V4 pass. `gate-index.json` says `not_run` and points at what would change it.
- No claim that T8.3 is closed. It closes when M4 and the Lead say so.
- No second-class sample beyond this one. A family of samples is not implied.
