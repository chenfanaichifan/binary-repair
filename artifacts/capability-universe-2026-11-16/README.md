# Capability universe - 20 first-level dimensions (2026-11-16)

Generated deterministically by `scripts/build_universe_dimension_registry.py` from committed evidence.
No provider calls, no network, no git commands, no wall-clock timestamps.

- generated_at: `2026-11-14T00:00:00Z` (artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json#audit_date)
- registry digest: `7da89f2765a1b2103d9c78d81d95ab69da664ca275a625f153561cfeba9ca225`
- source digest: `0145428341dc59f7200d9f63a57ff2f0c9c54c6853e5cc2b82d5dfcb70f67d5a`

Artifact files: `dimension-registry.json` (machine-readable), `README.md` (this file), `SHA256SUMS` (covers both; never itself).

## What this artifact answers

1. The 20 first-level capability dimensions D01-D20 (user list, titles
   verbatim) with a documented old-11-dim mapping and per-dimension
   status/owner/review_by/evidence.
2. How all 240 universe cells map to the new dimensions: **240/240 mapped**, 0 unmapped.
3. Cell status counts recomputed from the cells and validated equal to
   the coverage matrix (verified / supported / non_goal / unavailable /
   unknown).
4. The 12 claims non-goals as explicit `out_of_universe_candidates`
   (sha-free but evidence-linked), and `unknown_within_universe = 0`.
5. `undiscovered_space = not_measurable`: the space outside the declared
   universe has no sampling frame here, so no number is fabricated.

## Cell mapping and counts

| metric | value |
|---|---|
| total universe cells | 240 |
| mapped cells | 240 |
| unmapped cells | 0 |
| unknown within universe | 0 |
| undiscovered space | `not_measurable` |
| verified cells | 36 |
| supported cells | 51 |
| non_goal cells | 129 |
| unavailable cells | 24 |
| unknown cells | 0 |
| counts match coverage matrix | True |

Mapping digest: `8c40fede137d907c38bc6911c6c07eb4f4c44da51bb346d35c76ce1b29bb4963`.

## Dimensions D01-D20

| id | title | status | owner | review_by | old-11 mapping | mapped cells |
|---|---|---|---|---|---|---|
| D01 | Binary formats | covered | universe | 2027-05-14 | `container`, `bits`, `endian` (full) | 240 |
| D02 | CPU architectures | covered | universe | 2027-05-14 | `arch`, `bits`, `endian` (full) | 240 |
| D03 | ABI and calling conventions | not_started | analysis | 2027-05-14 | (none) | 0 |
| D04 | Compiler ecosystems | not_started | analysis | 2027-05-14 | (none) | 0 |
| D05 | Vulnerability classes | covered | engine | 2027-05-14 | `sink_class` (full) | 240 |
| D06 | Memory safety | partial | engine | 2027-05-14 | `sink_class`, `destination_kind` (partial) | 240 |
| D07 | Arithmetic safety | non_goal | engine | 2027-05-14 | (none) | 0 |
| D08 | Control-flow safety | non_goal | engine | 2027-05-14 | (none) | 0 |
| D09 | Data-flow analysis | not_started | analysis | 2027-05-14 | (none) | 0 |
| D10 | Control-flow analysis | not_started | analysis | 2027-05-14 | (none) | 0 |
| D11 | Interprocedural analysis | not_started | analysis | 2027-05-14 | (none) | 0 |
| D12 | Binary structure | partial | universe | 2027-05-14 | `bits`, `endian` (partial) | 240 |
| D13 | Runtime environments | covered | runtime | 2027-05-14 | `runtime_tier` (full) | 240 |
| D14 | Exploitability assessment | not_started | analysis | 2027-05-14 | (none) | 0 |
| D15 | Repair strategies | covered | engine | 2027-02-14 | `strategy` (full) | 240 |
| D16 | Patch generation | partial | ai-path | 2027-05-14 | `strategy`, `evidence_profile` (partial) | 240 |
| D17 | Patch application | partial | pipeline | 2027-05-14 | `evidence_profile` (partial) | 240 |
| D18 | Semantic preservation | not_started | verification | 2027-05-14 | (none) | 0 |
| D19 | Verification | partial | verification | 2027-05-14 | `evidence_profile`, `proof_scope` (partial) | 240 |
| D20 | AI model intelligence | partial | ai-path | 2027-05-14 | `provider` (partial) | 240 |

Status counts: `covered`=5, `partial`=6, `non_goal`=2, `unavailable`=0, `not_started`=7.

## Old-11 -> new-D mapping

| old dimension | mapped to |
|---|---|
| `container` | D01 |
| `arch` | D02 |
| `bits` | D01, D02, D12 |
| `endian` | D01, D02, D12 |
| `sink_class` | D05, D06 |
| `strategy` | D15, D16 |
| `destination_kind` | D06 |
| `evidence_profile` | D16, D17, D19 |
| `runtime_tier` | D13 |
| `provider` | D20 |
| `proof_scope` | D19 |

Every old-11 dimension is mapped by at least one new dimension; D03, D04,
D07-D11, D14 and D18 have no old-registry mapping and are explicitly
`not_started`/`non_goal` with a status_reason (never silently inferred).

## Out-of-universe candidates (12 claims non-goals)

| candidate id | category | owner | review_by | matching cells |
|---|---|---|---|---|
| `EG-cases-target-not-analyzed` | engine_gap | target-scope | 2027-02-14 | 0 |
| `NG-ai-leaf-only::ai_assembly_repair` | non_goal | ai-path | 2027-05-14 | 19 |
| `NG-ai-leaf-only::ai_binary_repair` | non_goal | ai-path | 2027-05-14 | 18 |
| `NG-non-goal-1` | non_goal | engine | 2027-03-31 | 54 |
| `NG-non-goal-2` | non_goal | engine | 2027-05-14 | 0 |
| `NG-non-goal-3` | non_goal | lead | 2027-05-14 | 0 |
| `NG-non-goal-4` | non_goal | lead | 2027-05-14 | 0 |
| `NG-non-goal-5` | non_goal | runtime | 2027-05-14 | 0 |
| `RG-external-poc::<doc>::pe/arm64` | runtime_gap | runtime | 2027-05-14 | 0 |
| `RG-external-poc::<doc>::pe/i386` | runtime_gap | runtime | 2027-05-14 | 0 |
| `RG-external-poc::<doc>::pe/x86_64` | runtime_gap | runtime | 2027-05-14 | 0 |
| `RG-external-poc::<doc>::macho/x86_64` | runtime_gap | runtime | 2027-05-14 | 0 |

These 12 records are the explicit non-goals of `docs/status/claims.json`;
they are outside the measurable universe and are not capability claims.

## Assumptions (explicit, not silent)

- D01-D20 ids and titles are the user's authoritative Phase-7 list, relayed verbatim by the Lead; the builder validates title fidelity.
- The old-11-dim -> new-D mapping is the Lead-supplied mapping; dimensions with no old mapping are not silently inferred as covered and carry an explicit source_registries/old_11dim_mapping of [] / 'none'.
- Status assignment is analyst inference under the documented rules (covered/partial/non_goal/unavailable/not_started); every entry records a status_reason and evidence_refs.
- undiscovered_space is not_measurable: this tree has no external corpus sampling frame, so the unenumerated capability space cannot be counted; unknown_within_universe is 0 because all 240 declared cells are status-classified.
- No capability is claimed verified/non_goal by this artifact; it maps the universe and records explicit non-goals only.

## Validation

```bash
python scripts/build_universe_dimension_registry.py --check
python -m pytest -q tests/test_capability_dimensions.py tests/test_gap_registry_discovery.py
```

`--check` rebuilds the artifact in memory and compares
`dimension-registry.json`, `README.md` and `SHA256SUMS` byte-for-byte,
re-validates SHA256SUMS coverage, and exits 0 only on an exact match.

## Limitations

- This registry maps the declared universe; it does not prove new repair capability.
- 12 claims non-goals remain out of the measurable universe and are listed explicitly.
- 7 dimensions are not_started; 6 are partial; 2 are explicit non_goal dimensions.
- undiscovered_space is not_measurable; no unenumerated-space number is invented.
