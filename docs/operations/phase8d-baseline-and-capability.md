# Phase-8D baseline and capability universe (2026-11-17)

Status: D00/D01 design and deterministic registry. This document is a
mapping/evidence record, not a capability promotion.

## D00 - frozen Phase-8C baseline

The Phase-8D worktree is based on consolidation commit
`f1bb1f41eba1e0be61be09cea56091e8a03a9896`. The Phase-8C release commit
`4a7b2355ffc5225d013a777bc7d588abac58f944` (tree
`4bf501314b6469328d0256031990bfc402ce6677`) and the evidence tip
`ec503e4b1df53ad39fa836bd34d93a18564d78f9` are ancestors of this base.
Tests verify both ancestry facts with `git merge-base --is-ancestor`.

The consolidation preserved the commit objects but the original release
tag/evidence refs are no longer resolvable. Expected targets are recorded
explicitly:

| Ref | Annotated tag object | Expected target | Observed status |
|---|---|---|---|
| `release-2026-11-16-phase8c` | `b03a0a46...` | `4a7b2355...` | deleted/renamed by consolidation |
| `release-2026-11-16-phase8c-evidence` | `08cc3719...` | `ec503e4b...` | deleted/renamed by consolidation |
| `release/2026-11-16-phase8c-evidence` | n/a (branch) | `ec503e4b...` | deleted/renamed by consolidation |

The annotated tag objects themselves survive as unreachable objects and are
recoverable with `git fsck`; the refs are not resolvable.

Frozen-tree nightly gate evidence is present under
`artifacts/release-gate-2026-11-16-phase8c/`: mode `nightly`, 13/13 required
checks passed, 0 failed/skipped/unavailable, gate `ok=true`, frozen and release
SHA are `4a7b2355...`, and `mainline_unchanged=true` in the freeze record.

Hosted CI evidence:

- final-SHA CI: run `43748886046` success; Ubuntu verification
  `43748886289` success on `4a7b2355...` (recorded in the evidence addendum);
- claims also cites the earlier gated-code CI `43744573286` / Ubuntu
  `43744573230` on `f1ba37e...`; the two SHA layers are intentionally separate.

Phase-8B's two deterministic samples were reproduced independently on the
Phase-8C tree: 2/2 verified, candidates
`1bc66b2e...` (`stack-strcpy-x86_64`) and `93e27f2f...`
(`heap-capacity-x86_64`). The Phase-8C hidden benchmark has 8 aggregate
samples (6 runtime + 2 analysis-only), all executed, 0 independently verified,
0 false verified. Hidden material was not copied into this repository.

The D00 artifact is
`artifacts/phase8d-baseline-2026-11-17/baseline.json`. It also records the
Phase-8C public result: 32 samples, 24 runtime-oracle, 2 independently verified,
1 rejected/withdrawn, published `false_verified=0`.

## D01 - capability universe registry

The registry is a new Phase-8D artifact; the existing 20-dimension registry
and 240-cell coverage matrix are read-only inputs and are not rewritten.

### Units and states

The registry contains 297 explicit units:

- 20 dimension-summary units (D01-D20);
- 240 declared cell units, one per committed coverage-matrix cell;
- 32 Phase-8C public benchmark sample units;
- 2 aggregate-only hidden benchmark units (no hidden ids, paths or content);
- 3 read-only M2 analysis-prototype units.

Every unit has a state, denominator class, represented case count, dependency
ids and evidence references. The state vocabulary is:

`unknown | discovered | analysis_only | candidate_generated |
independently_verified | generalized | promoted | unsupported |
not_applicable | not_run | unmeasurable`

Legacy cell statuses are mapped conservatively:

- `supported` and `verified` -> `discovered`, not `independently_verified`;
  the legacy audit is not a Phase-8C independent-verifier binding;
- `non_goal` -> `not_applicable`;
- `unavailable` -> `unmeasurable`;
- `unknown` -> `unknown`.

Public samples use their committed runner result: verified -> 
`independently_verified`, a rejected candidate -> `candidate_generated`,
analysis-only/no-candidate -> `analysis_only`, unsupported -> `unsupported`.
The hidden aggregate is a single opaque runtime unit with represented cases 6
and a single analysis-only unit with represented cases 2; it never exposes
hidden identities.

### State transitions and promotion

The state machine is explicit in the registry. Illegal shortcuts are rejected
by tests: `analysis_only -> independently_verified`,
`candidate_generated -> promoted`, `independently_verified -> promoted`, and
`unknown -> independently_verified`. `promoted` is reachable only from
`generalized` and only through an external promotion gate. No current unit is
`generalized` or `promoted`; the registry has 0 of each.

### Legal coverage denominators

No denominator is invented and no `unknown` is counted as zero:

| Denomination | Legal denominator | Unit count | Observed states |
|---|---:|---:|---|
| Declared cells | 240 | 240 | 87 discovered, 129 not_applicable, 24 unmeasurable |
| Dimension summaries | 20 | 20 | 11 discovered, 2 not_applicable, 7 unknown |
| Public runtime oracle | 24 | 24 | 2 independently verified, 1 candidate_generated, 19 analysis_only, 2 unsupported |
| Public analysis-only | 8 | 8 | 8 analysis_only |
| Hidden runtime aggregate | 6 | 1 | 6 analysis_only (opaque aggregate) |
| Hidden analysis-only aggregate | 2 | 1 | 2 analysis_only |
| Read-only analysis prototypes | 3 | 3 | 3 analysis_only |

Rates are computed only when the legal denominator is non-zero. The public
runtime verified rate is 2/24 = 0.083333; the hidden runtime verified rate is
0/6 = 0.0 (a measured zero, not a capability claim). Zero-denominator rates are
`null`, never 0.

### Unknown space

The declared catalog has 7 unknown-level dimension units; all other units have
an evidence-bound state. The unenumerated space outside the catalog is
`unmeasurable`, with `outside_catalog_count=null` and
`outside_catalog_measured_fraction=null`. There is no sampling frame for that
space, so treating it as zero would be fabricated coverage.

### Reproduce

```bash
python scripts/build_phase8d_capability_universe.py --write
python scripts/build_phase8d_capability_universe.py --check
python -m pytest -q tests/test_phase8d_capability_universe.py
```

No capability promotion, hidden availability, or generalized repair claim is
made by this document or its artifacts.
