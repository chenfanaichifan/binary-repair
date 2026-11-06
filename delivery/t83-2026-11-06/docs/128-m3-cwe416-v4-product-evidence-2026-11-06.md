# 128 — V4 goes through M1's adapter: `property_kind`, one writer, product file

- Date: 2026-11-06 (guest window 13:20–13:24 local)
- Owner: Member 3 (guest execution / evidence)
- Branch: `m3/cwe416-v3-noinput`
- Product code used: M1 `c41de41` — `tools/v4_harness_to_evidence.py`, `app/domain/v4.py`
- Evidence: `docs/handoffs/evidence/cwe416-v4-2026-11-06/`
  (`SHA256SUMS` `3b54623e…33d2`, 6 rows / 8 files)
- Gate status assigned here: **none**. V4 is submitted for M4's replay, not declared.

## 0. What changed since record 127

Record 127 said no `write_v4_evidence` existed anywhere. That was true of the
refs I could see at the time — M1's `origin/m1/t30-acceptance-ab-2026-11-05`
then pointed at `8d54a06`. It has since moved to `c41de41`, which lands the
whole typed V4 stack (`app/domain/v4.py`, `tools/v4_harness_to_evidence.py`,
tests). So the correct move is exactly the one taken here: **use M1's writer and
delete mine.**

## 1. Three edits

1. **`property_kind` is now an explicit output field.** `v4_harness.py` emits
   `"property_kind": "pointer-flow"`, and M1's adapter requires it —
   `from_v4_harness` does `data["property_kind"]`, so a harness that only
   describes the property in prose fails instead of being guessed at.
2. **The second writer is gone.** `v4_evidence.py` and its
   `write_v4_evidence` were deleted; the old `v4-evidence.json` shape was
   removed with them. `harness-output.json` is the measurement, and M1's
   `write_v4_evidence` is the only thing that writes product evidence.
3. **The product file was regenerated** by running M1's CLI unmodified against
   that measurement, from a detached worktree at `c41de41`.

## 2. The confirmation list

Read back through `app/domain/v4.py::validate_v4_evidence` at `c41de41`
(`02-adapter.txt` is the run):

| Asked for | In `v4-symbolic.json` |
|---|---|
| `property_kind="pointer-flow"` | `"property_kind": "pointer-flow"` |
| `forbidden_ranges` omitted / None | omitted — `model.forbidden_ranges` is `None` |
| `calibration` 1/1 | `cases=2 passed=1 failed=1` |
| `known_bad_rejected=True` | `true` (with `known_good=True`, `known_bad=True`) |
| empty-disjunction in `not_claimed` | present as its own entry |
| replay 2 runs identical | `runs=2 identical=true` |

Also, because the schema checks them: `exploration complete=True unexplored=[]`,
`solver queries=4 sat=1 unsat=1 unknown=0 timeouts=0`, `steps/max_steps 25/128`,
`scope=model`. And the binding is real — the same payload with a wrong candidate
hash is rejected with
`candidate hash 46d16e99… != 0000…`.

## 3. What the harness measures, unchanged

```
known_good  candidate 46d16e99…  holds     1 eval → unsat   11/64 steps
known_bad   original  c9c2632e…  violated  1 eval → sat     14/64 steps
```

The candidate's `unsat` remains the **empty-disjunction** case: five `nop`s
replaced `call free@plt`, nothing is freed on that path, so the disjunction over
freed pointers is empty. The witness says `free_calls: 0`. That sentence is in
the case `notes`, in `not_claimed`, and here — three places, because it is the
one number in this file that is easy to over-read.

## 4. Why this is still not a pass

- `state: "passed"` is the schema's field for a positive evidence claim. It is
  not a gate verdict, and M3 is not the one who assigns one: `docs/handoffs/62`
  §1 requires an independent verifier (M4) to replay the raw evidence, and the
  Lead to accept it. Until then V4 stays `not_run` wherever the gate is scored.
- **The 124 bundle is untouched** — its `v4-symbolic.json` stub, its
  `gate-index.json` (V4 `not_run`) and its 31/31 `SHA256SUMS` all stand. This
  artifact becomes consumable when a bundle carries it *and* claims V4 passed:
  at `c41de41`, `tools/route_bundle_ingest.py:344-364` validates it and
  downgrades to `unknown` if it does not validate. Placing it in a bundle is the
  bundle owner's step, not this one's.
- **T8.3 stays blocked.** One sample, one repair, one observation. No second
  defect class is described.

## 5. Handoff to M4

The replay inputs, all in `docs/handoffs/evidence/cwe416-v4-2026-11-06/`:

- `v4-symbolic.json` — the claim to verify.
- `harness-output.json` — the measurement behind it, so the adapter can be
  re-run without angr.
- `v4_harness.py` — the producer, for a fresh run from the candidate bytes.
- `01-run.txt`, `02-adapter.txt` — the two runs, untrimmed.

What a verifier needs to decide, in order: does the property match the contract's
`forbidden_behavior`; do the hooks over-approve; is the candidate-side `unsat`
only the empty-disjunction case (it is); and does a fresh run reproduce
`replay.evidence_sha256`.

## 6. Reproducing

```sh
FIX=~/cwe416-sync/kit/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput
/opt/angr-venv/bin/python v4_harness.py --candidate ~/cwe416-sync/candidate.elf \
    --original "$FIX/original.elf" --contract "$FIX/contract.json" --out harness-output.json

git worktree add --detach /tmp/wt-m1 c41de41
cd /tmp/wt-m1 && python tools/v4_harness_to_evidence.py \
    --input <dir>/harness-output.json --output <dir>/v4-symbolic.json
```
