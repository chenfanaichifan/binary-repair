# V4 harness package for Route A candidate 2a96b108

This is the harness, not a V4 result. Do not create a marker without running it.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install angr z3-solver
```

## Run

```bash
python v4_harness.py \
  --candidate candidate.elf \
  --original original.elf \
  --contract contract.json \
  --out v4-symbolic.raw.json \
  --replay-runs 2
```

The harness writes the typed V4 evidence and prints it. It performs two replay
runs and requires identical digests.

## Required binding

The final marker must bind:

```text
candidate_sha256 = 2a96b1083f23a0885ef6152dee39c48648d496a7a026e37ccfb31382c412970e
replay.verified_by = "m4"
```

If the harness schema does not carry `replay.verified_by`, add it only after
reviewing the two run digests; do not alter candidate/original/contract hashes.

## Files

```text
v4_harness.py
v4_evidence.py
app/domain/v4.py
tools/v4_harness_to_evidence.py
```

The adapter is optional; it maps old harness output to the product V4 schema.
