# Phase-8C quality audit (2026-11-16)

Mode: `public_only`; status: **ok_public_only**

| check | status | detail |
|---|---|---|
| public-count | pass | 32 samples |
| public-core-count | pass | core 28 |
| public-runtime-analysis | pass | 20 runtime / 8 analysis-only |
| public-split-counts | pass | {'dev': 18, 'validation': 14} |
| v1-migration | pass | 12/12 lossless |
| v2-contracts | pass | 4/4 |
| public-sums | pass | all corpus evidence hashes verify |
| contamination | pass | public contamination verdict clean |
| external | pass | status=not_run; no merge |
| hidden-leaks | pass | no hidden paths in public artifacts |

Public-only mode is CI-capable. Full mode requires the hidden root/commitment/results; missing inputs are `not_run`, never pass.

## Reproduce

```
python scripts/audit_phase8c_quality.py --public-only --write
python scripts/audit_phase8c_quality.py --public-only --check
python scripts/audit_phase8c_quality.py --full --hidden-root PATH --write
```
