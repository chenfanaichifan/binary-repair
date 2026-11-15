# Phase-8C public benchmark evidence (2026-11-16)

- benchmark_id: `phase8c-public-v2`
- manifest_sha256: `d46f06bfef59ae7116d888ea2b5810fcf518a9d5c5a178a5cef73996fac72b78`
- generated_at: `2026-11-16T00:00:00Z` (inherited from the fixed manifest)
- samples: 32
- status counts: `{"blocked": 0, "executed": 30, "invalid": 0, "not_run": 0, "unsupported": 2}`
- independently verified: 2
- independent rejected: 1
- false_verified (published): 0
- false_verified (internal disagreements): 1
- deterministic claims withdrawn: 1
- repeats: 2 (stable across repeats: True; C1 flake policy records every attempt, it never claims unconditional stability)

## Layered metrics

| layer | eligible repair cases | detection rate | root-cause rate | localization rate | verified repair rate |
|---|---|---|---|---|---|
| overall | 24 | 0.1250 | 0.1250 | 0.1250 | 0.0833 |
| format:elf | 24 | 0.1250 | 0.1250 | 0.1250 | 0.0833 |
| format:macho | 0 | null | null | null | null |
| format:pe | 0 | null | null | null | null |
| arch:arm64 | 0 | null | null | null | null |
| arch:i386 | 0 | null | null | null | null |
| arch:x86_64 | 24 | 0.1250 | 0.1250 | 0.1250 | 0.0833 |

## Reproduce

```bash
python scripts/run_phase8c_benchmark.py
python scripts/run_phase8c_benchmark.py --check-artifact
```

## Limitations

- deterministic repair evidence only: no AI provider and no network is used by this runner.
- verified_count counts independent-verifier decisions only; the deterministic engine's own gate is never accepted as verification.
- single-run evidence is not an unconditional stability claim (C1 warning B-POST-REBASE-REPRODUCTION-FLAKY): repeated serialized runs and their attempt history must be recorded before claiming stability
- 1 deterministic verified claim(s) were rejected by the independent verifier and withdrawn from the published claim
- hidden aggregate present: counts only, committed under the hidden aggregate path; no per-sample hidden ids/paths/content are published
- single-run evidence is not an unconditional stability claim (C1 warning B-POST-REBASE-REPRODUCTION-FLAKY): repeated serialized runs and their attempt history must be recorded before claiming stability
- public artifacts contribute metadata evidence only: raw binary bytes are not duplicated here; the binary sha256 and committed fixture paths bind every sample.
