# CWE416 — V4 producer output and the product evidence it maps to

- Date: 2026-11-06 (guest window 13:20–13:24 local)
- Owner: Member 3
- Candidate: `46d16e99…fcd0` (124); control: `original.elf` `c9c2632e…23c9`
- Contract: unchanged, `input_mode: none`, file `8a2b408c…e3c3b`
- Product code used to map and validate: M1 `c41de41` —
  `tools/v4_harness_to_evidence.py` + `app/domain/v4.py`

## 1. Two files, two owners

| File | Written by | Shape |
|---|---|---|
| `harness-output.json` | `v4_harness.py` (M3, this directory) | the measurement |
| `v4-symbolic.json` | `tools/v4_harness_to_evidence.py` (M1 `c41de41`) | the product `V4Evidence` |

The harness no longer carries an evidence schema of its own: `v4_evidence.py`
was deleted, and the only writer is M1's `write_v4_evidence`. The harness states
`property_kind` explicitly — `pointer-flow` — so the adapter never infers a
property kind from prose.

One byte-level note: `write_v4_evidence` uses `Path.write_text` without a
newline argument, so on this Windows host it emitted CRLF. The committed file is
the same document normalised to LF — what the same code produces on the Ubuntu
target — and it was re-validated after normalisation (`pointer-flow`, 1/1, hashes
bound) rather than assumed still good.

## 2. The property and the two answers

> There exists an execution on which a pointer passed to `free()` is later
> passed to `printLine()` — a freed block is read.

```
known_good  candidate 46d16e99…  expected holds     observed holds     1 eval → unsat   11/64 steps
known_bad   original  c9c2632e…  expected violated  observed violated  1 eval → sat     14/64 steps
```

## 3. The product evidence, as it now stands

```
property_kind        pointer-flow
forbidden_ranges     None            (omitted — legal only for pointer-flow)
calibration          cases=2 passed=1 failed=1  → 1/1
                     known_good=True known_bad=True known_bad_rejected=True
exploration          complete=True unexplored=[]
solver               queries=4 sat=1 unsat=1 unknown=0 timeouts=0
steps/max_steps      25/128
replay               runs=2 identical=True
scope / state        model / passed
not_claimed          contains the empty-disjunction caveat
```

`02-adapter.txt` is the run: `validate_v4_evidence` accepts the file with the
candidate and original hashes bound, and rejects the same payload when the
candidate hash is wrong — so the hash binding is not decorative.

## 4. The candidate's `unsat` is the empty-disjunction case

The repair replaced `call free@plt` with five `nop`s. On the candidate's single
path nothing is freed, the disjunction over freed pointers is empty, and the
question is unsatisfiable. That is a real answer, and `free_calls: 0` in the
witness is why.

It is not a solved constraint. The evidence says so in the case `notes`, and
`not_claimed` carries it as an entry of its own — the product schema requires
that disclosure for exactly this shape.

## 5. Hooks, and why each is allowed

Recorded in `harness-output.json#hooks`, one justification each; the product
file carries the five symbols. `printLine` is hooked **to observe its argument**
— the verdict is computed by comparing that argument with the pointers recorded
at `free()`. None of the hooks assumes the repair is safe.

## 6. What this does not do

- **It does not assign the gate.** `state: passed` is the schema's own field for
  a positive evidence claim; the gate label is not the producer's to assign.
  Standard `docs/handoffs/62` §1 requires M4 to replay the raw evidence and the
  Lead to accept it before V4 leaves `not_run`. This directory submits; it does
  not certify.
- **It does not touch the 124 bundle.** That bundle keeps its own
  `v4-symbolic.json` stub and `gate-index.json` with V4 `not_run`, plus its
  31/31 `SHA256SUMS`. To make this artifact consumable it has to be placed in a
  bundle whose gate row claims V4 passed — at `c41de41`,
  `tools/route_bundle_ingest.py:344-364` then validates it and downgrades to
  `unknown` if it does not validate. Moving it there is a bundle-owner step.
- **No second sample, no second defect class.** T8.3 stays blocked.

## 7. Reproducing

```sh
# 1. measurement, in the guest (angr lives in /opt/angr-venv)
FIX=~/cwe416-sync/kit/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput
/opt/angr-venv/bin/python v4_harness.py \
    --candidate ~/cwe416-sync/candidate.elf --original "$FIX/original.elf" \
    --contract "$FIX/contract.json" --out harness-output.json

# 2. mapping, with M1's code checked out at c41de41
git worktree add --detach /tmp/wt-m1 c41de41
cd /tmp/wt-m1 && python tools/v4_harness_to_evidence.py \
    --input  <this-dir>/harness-output.json \
    --output <this-dir>/v4-symbolic.json
```

The harness still runs both cases twice and refuses to publish differing
digests; it writes only when the replay agrees with itself. `01-run.txt` is that
run untrimmed, including angr's `Guessing call prototype` warnings.

## 8. Files

| File | What it is |
|---|---|
| `v4_harness.py` | the producer: hooks, exploration, accounting, replay, CLI |
| `harness-output.json` | its output — the measurement the adapter consumes |
| `v4-symbolic.json` | the product `V4Evidence`, written by M1's adapter |
| `01-run.txt` | the harness run behind `harness-output.json` |
| `02-adapter.txt` | the product validator accepting it, and rejecting a wrong hash |
