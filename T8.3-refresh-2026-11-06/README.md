# T8.3 refresh — V0/V1/V5 measured again, and the wiring proposal

Two things that do not depend on anyone else, done while the sample waits for
M4's key.

1. **V0, V1 and V5 re-measured in this window** instead of carried from record 122.
   The sealed bundle `T8.3-evidence-2026-11-06/` keeps its bytes; this directory
   holds the fresh measurements and supersedes those three files *for provenance
   purposes only*. Two of them came back **byte-identical** to the copies in the
   bundle — same tool, same inputs, same bytes — and V0 differs only by the
   `measured_here` block that records this window's digests. A re-derivation that
   changes nothing is what "reproducible" is supposed to look like.
2. **`v2-v4-wiring-proposal.md`** — the next blocker is not evidence, it is that
   `attempt_writer.py` hardcodes V2 and V4 to `not_run`, so no bundle can reach
   `success_within_scope` no matter how good the evidence is. The proposal is
   small, keeps the "producer cannot self-certify" rule, and says what M3 will emit
   if the field names change.

## What was re-measured

Guest `lab@binrepair-vm`, 2026-11-06 17:40 local, on the bundle's own inputs:

```
rebuild twice   build.sh                c9c2632e…  c9c2632e…   both = original.elf
patch twice     patch_candidate.py      46d16e99…  46d16e99…   both = candidate.elf
V1 audit        audit_interface.py      pass: true  (37 sections, 14 relocations, 5 changed bytes)
V2 observation  audit_interface.py      pass: true  (unchanged from the 5/5 in the bundle)
```

| file | gate | result |
|---|---|---|
| `gates/V0-identity.json` | identity | passed — candidate is this original plus the recorded edit; both replays reproduce the shipped bytes |
| `gates/V1-structure.json` | structure | passed — same audit the bundle reports |
| `gates/V5-reproducibility.json` | reproducibility | passed — two rebuilds, two patch replays, all four equal to the shipped files |

`gates/V0-identity.json` gains a `measured_here` block with both digest lists, so a
reader can see this window produced them rather than trusting a restatement.

## One gap this run exposed

The sealed bundle's `fixture/` carries `original.elf`, `original.c`,
`contract.json`, `defect.json`, `tests/` and `support/` — but **not** `build.sh`,
`src.c` or `harness.c`. So V5 cannot be re-derived from the bundle alone; this run
had to pull those three files from `fixtures/public/CWE416_…_noinput/` first.

That is worth knowing before M4 tries: the bundle is enough to *replay the
harness* and to check V2/V3, but not to *rebuild the original*. If the Lead wants
the bundle self-sufficient for V5, the fix is three files and a new bundle
version — not a quiet edit to a published one.

## How to use this directory

```sh
# the files are drop-in replacements for provenance; the bundle is unchanged
diff <(python3 -m json.tool gates/V1-structure.json) \
     <(python3 -m json.tool ../T8.3-evidence-2026-11-06/gates/V1-structure.json) | head

# re-run the whole thing (needs the guest and gcc)
sh ../T8.3-evidence-2026-11-06/fixture/build.sh          # emits original.elf
python3 patch_candidate.py --original original.elf --out c.elf --report r.json
python3 audit_interface.py --original original.elf --candidate c.elf \
    --audit audit.json --interface v2.json --symbol CWE416_Use_After_Free__malloc_free_char_01_bad
python3 write_repro.py --fixture-original original.elf --rebuild-1 r1.elf \
    --rebuild-2 r2.elf --patch-1 p1.elf --patch-2 p2.elf --out repro.json
```

The three tools are the ones delivered with record 122
(`docs/handoffs/evidence/cwe416-candidate-2026-11-05/tools/`).

## What this does not change

- No gate verdict: V4 is still `not_run`, and nothing here touches
  `gates/gate-index.json` or `v4/`.
- No `verified_by` value anywhere.
- No new sample, no new class. T8.3 stays blocked until M4 replays and the Lead
  accepts.
