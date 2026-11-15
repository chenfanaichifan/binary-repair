# Phase-8C baseline & hidden readiness audit (C1)

Read-only readiness audit for Phase-8C ground-truth v2 on `910e4f7b8361dca25bb765a34cc603afff2e11f3`. No production code/contracts/CI/claims/benchmark v1/release gate/Phase-8A-B artifacts were modified; no network/AI was used.

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
- contracts: 17; checker exit 0
- guest: {'available': True, 'kind': 'lima', 'tier': 'emulated_run', 'tool': '/opt/homebrew/bin/limactl', 'instance': 'binaryrepair'}
- reproduction: reproduced (stability: one_off_flake_not_reproduced_in_two_serialized_repeats)
- runtime repeats: 2 serialized, stable=True, results sha=a477ea3cbea062c03f3ee91b8fdd779ecf70f6bbb6e119a37e19fd881e688b4a
- hidden aggregate: {'sample_count': 8, 'runtime': 6, 'analysis_only': 2, 'executed': 8, 'verified_count': 0, 'false_verified': 0, 'aggregate_only': True}
- tests collected: 2232 (duration not measured in C1)
