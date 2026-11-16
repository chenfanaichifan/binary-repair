# Phase-8D experiment and evidence bundle (D08)

Status: deterministic evidence binding. No experiment changes a capability
state and no capability is promoted.

The bundle is `artifacts/phase8d-experiments-2026-11-17/experiments.json`.
It binds ten Phase-8D workstream records (D00-D07, D09-D10) to their committed
artifacts by SHA-256. Every record has `promotion_effect: none`; the summary has
`verified_true_count=0`, `capability_promotion=false`, and
`false_verified_observed=0`.

D08 itself is the bundle, so it is not a separate experiment record. The bundle
records hypotheses, methods, results and limitations without re-running the
underlying experiments; it is a provenance layer, not independent verification.

Reproduce:

```bash
.venv/bin/python scripts/build_phase8d_experiment_bundle.py --write
.venv/bin/python scripts/build_phase8d_experiment_bundle.py --check
.venv/bin/python -m pytest -q tests/test_phase8d_experiment_bundle.py
```

Contract: `contracts/phase8d-experiment-bundle.schema.json` (registered in the
contract checker with valid/invalid fixtures).
