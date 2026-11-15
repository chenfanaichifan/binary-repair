# Phase-8C baseline & hidden readiness audit (C1)

Read-only readiness audit for Phase-8C ground-truth v2 on `227f45b39d85a7cd95e8589beb07dcfc89cd22d7`. No production code/contracts/CI/claims/benchmark v1/release gate/Phase-8A-B artifacts were modified; no network/AI was used.

## Files

- `phase8c-baseline-audit.json` - machine-recorded baseline facts and the 10-question answers
- `phase8c-work-breakdown.json` - C1-C14 tasks, dependencies, write scopes, acceptance and blockers
- `phase8c-hidden-isolation-plan.md` - private root/threat model/commitment/public-aggregate design
- `phase8c-lima-coordination-plan.md` - limactl inventory + lock/lease design
- `phase8c-readiness.md` - verdict/blockers/warnings
- `reproduction/` - small JSON evidence from reproducing the two Phase-8B independently verified samples into a temp out (candidate/original bytes are not duplicated; committed evidence untouched)
- `SHA256SUMS` - covers all data/docs including `../../docs/acceptance/phase8c-baseline-audit.md`

## Commands

```
python scripts/audit_phase8c_readiness.py --write
python scripts/audit_phase8c_readiness.py --json
python scripts/audit_phase8c_readiness.py --check
pytest -q tests/test_phase8c_readiness.py
```

## Key facts

- v1 manifest: benchmark/phase8-v1/manifest.json sha256 `e7e7eca43518dc1b953faccead6f301f80eee4a59f1f0550dc8aad1bbd712052`, 12 samples, splits {'dev': 8, 'validation': 4}, hidden=False
- contracts: 13; checker exit 0
- guest: {'available': True, 'kind': 'lima', 'tier': 'emulated_run', 'tool': '/opt/homebrew/bin/limactl', 'instance': 'binaryrepair'}
- reproduction: reproduced
- tests collected: 2053 (duration not measured in C1)
