# Phase-8D experiment and evidence bundle

Deterministic D08 binding of the Phase-8D experiments. The bundle does not
re-run experiments and does not change capability states. Every record has
`promotion_effect: none`; `verified_true_count=0`, `capability_promotion=false`.

- `experiments.json` — experiment records with evidence paths and SHA-256
- `SHA256SUMS` — artifact integrity

Regenerate and check:

```bash
.venv/bin/python scripts/build_phase8d_experiment_bundle.py --write
.venv/bin/python scripts/build_phase8d_experiment_bundle.py --check
```
