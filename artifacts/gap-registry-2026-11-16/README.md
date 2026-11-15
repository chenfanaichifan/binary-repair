# Capability gap registry and discovery (2026-11-16)

Generated deterministically by `scripts/discover_capability_gaps.py` from
committed evidence. No provider calls, no network, no git commands, no
wall-clock timestamps.

- generated_at: `2026-11-14T00:00:00Z` (artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json#audit_date)
- source digest: `d3fc008b6b933e3f32c0ed5af84bf40bcd8a59b5823de93ca4aea022f7a80d86`
- records: 64 (base 13 + discovery candidates 51)
- validation: ok=True unique_ids=64

Artifact files: `gaps.json` (full unified registry), `candidates.json`
(discovery mechanisms + candidates), `README.md` (this file),
`SHA256SUMS` (covers all three; never itself).

## Mechanisms

| mechanism | status | candidates | reason / run evidence |
|---|---|---|---|
| knowledge | run | 15 | run: dimension_count=20, non_covered_dimensions=15, registry_digest=7da89f2765a1b2103d9c78d81d95ab69da664ca275a625f153561cfeba9ca225, mapped_cells=240 |
| failure_driven | run | 31 | run: command=scripts/check_universe_methodology.py --json, ok=True, cell_count=240, status_counts={'non_goal': 129, 'supported': 87, 'unavailable': 24}, unknown=0, unexplained_cell_count=0, open_failures=0, dynamic_unverified |
| differential | run | 5 | run: command=scripts/check_capability_contract.py --json, ok=True, host={'machine': 'arm64', 'platform': 'darwin'}, cell_count=8, negative_checks=5, failed_negative_checks=0, divergent_or_poc_missing_cells=5 |
| mutation | not_run | 0 | no mutation engine/corpus is implemented in this tree; fabricating a mutation corpus would be invented evidence, so the mechanism is not run |
| metamorphic | not_run | 0 | no metamorphic-relation engine exists in this tree (no oracle-pair generator); the mechanism is not run instead of fabricating candidates |
| sample_based | not_run | 0 | no sampled capability corpus is provisioned in this environment (no sampling frame exists), so sample-based discovery is not run |
| knowledge_source_scan | not_run | 0 | no external knowledge corpus/advisory feed is provisioned in this environment; external-source scanning is out of scope and not faked |

Rules: the three RUN mechanisms really execute (universe registry build /
committed universe-methodology checker / committed capability-contract
checker) and must produce at least one candidate; the four NOT_RUN
mechanisms carry an explicit reason and produce none. A missing adapter,
a silent no-op or a schema violation makes `--check` exit 1.

## Registry composition

| discovery_source | records |
|---|---|
| `claims_non_goal` | 12 |
| `differential` | 5 |
| `failure_driven` | 32 |
| `knowledge` | 15 |

| status | records |
|---|---|
| `candidate` | 51 |
| `non_goal` | 12 |
| `resolved` | 1 |

The 12 `claims_non_goal` records are the explicit non-goals migrated from
`docs/status/claims.json`; the single `failure_driven` resolved record is
the mitigated `RG-runtime-evidence::elf/x86_64/64/little::native_run`
platform gap from the committed coverage audit. All discovery candidates
keep `status="candidate"` - none is auto-promoted to verified/non_goal/
resolved.

## Candidate list

| gap_id | source | category | target | plan |
|---|---|---|---|---|
| `GAP-DIFF-034E4F2DBA5F` | differential | platform_capability_differential | pe/x86_64 | `EXP-DIFF-PE-X86-64` |
| `GAP-DIFF-48734D7F8B17` | differential | platform_capability_differential | macho/x86_64 | `EXP-DIFF-MACHO-X86-64` |
| `GAP-DIFF-552CB23EC176` | differential | platform_capability_differential | elf/x86_64 | `EXP-DIFF-ELF-X86-64` |
| `GAP-DIFF-588259E9D4A2` | differential | platform_capability_differential | pe/i386 | `EXP-DIFF-PE-I386` |
| `GAP-DIFF-D96AB1937BEC` | differential | platform_capability_differential | pe/arm64 | `EXP-DIFF-PE-ARM64` |
| `GAP-FAIL-CASE-CWE121-UNCHECKED-STRCPY` | failure_driven | case_target_analysis_failure | cwe121-unchecked-strcpy | `EXP-FAIL-CASE-CWE121-UNCHECKED-STRCPY` |
| `GAP-FAIL-CASE-HARD-LOOP16` | failure_driven | case_target_analysis_failure | hard-loop16 | `EXP-FAIL-CASE-HARD-LOOP16` |
| `GAP-FAIL-CASE-HARD-LOOP32` | failure_driven | case_target_analysis_failure | hard-loop32 | `EXP-FAIL-CASE-HARD-LOOP32` |
| `GAP-FAIL-CASE-HARD-LOOP64` | failure_driven | case_target_analysis_failure | hard-loop64 | `EXP-FAIL-CASE-HARD-LOOP64` |
| `GAP-FAIL-CASE-HARD-LOOP8` | failure_driven | case_target_analysis_failure | hard-loop8 | `EXP-FAIL-CASE-HARD-LOOP8` |
| `GAP-FAIL-CASE-HARD-MULTICALL` | failure_driven | case_target_analysis_failure | hard-multicall | `EXP-FAIL-CASE-HARD-MULTICALL` |
| `GAP-FAIL-CASE-HARD-NONCONST` | failure_driven | case_target_analysis_failure | hard-nonconst | `EXP-FAIL-CASE-HARD-NONCONST` |
| `GAP-FAIL-CASE-HARD-REVERSE` | failure_driven | case_target_analysis_failure | hard-reverse | `EXP-FAIL-CASE-HARD-REVERSE` |
| `GAP-FAIL-CASE-HARD-SPRINTF` | failure_driven | case_target_analysis_failure | hard-sprintf | `EXP-FAIL-CASE-HARD-SPRINTF` |
| `GAP-FAIL-CASE-HEAP-CANARY` | failure_driven | case_target_analysis_failure | heap-canary | `EXP-FAIL-CASE-HEAP-CANARY` |
| `GAP-FAIL-CASE-INLINE-BYTE-LOOP` | failure_driven | case_target_analysis_failure | inline-byte-loop | `EXP-FAIL-CASE-INLINE-BYTE-LOOP` |
| `GAP-FAIL-CASE-UAF-NOINPUT` | failure_driven | case_target_analysis_failure | uaf-noinput | `EXP-FAIL-CASE-UAF-NOINPUT` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-CELL` | failure_driven | audit_meta_mismatch_regression | gate_cell | `EXP-FAIL-META-GATE-CELL` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-CELL-TIER` | failure_driven | audit_meta_mismatch_regression | gate_cell_tier | `EXP-FAIL-META-GATE-CELL-TIER` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-LEGACY-POC` | failure_driven | audit_meta_mismatch_regression | gate_legacy_poc | `EXP-FAIL-META-GATE-LEGACY-POC` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-LEGACY-PROFILE` | failure_driven | audit_meta_mismatch_regression | gate_legacy_profile | `EXP-FAIL-META-GATE-LEGACY-PROFILE` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-NO-INPUT` | failure_driven | audit_meta_mismatch_regression | gate_no_input | `EXP-FAIL-META-GATE-NO-INPUT` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-POC-UNAVAILABLE` | failure_driven | audit_meta_mismatch_regression | gate_poc_unavailable | `EXP-FAIL-META-GATE-POC-UNAVAILABLE` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-CHECKS` | failure_driven | audit_meta_mismatch_regression | gate_profile_checks | `EXP-FAIL-META-GATE-PROFILE-CHECKS` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILE-ENFORCEMENT` | failure_driven | audit_meta_mismatch_regression | gate_profile_enforcement | `EXP-FAIL-META-GATE-PROFILE-ENFORCEMENT` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-PROFILES` | failure_driven | audit_meta_mismatch_regression | gate_profiles | `EXP-FAIL-META-GATE-PROFILES` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-REWRITE` | failure_driven | audit_meta_mismatch_regression | gate_rewrite | `EXP-FAIL-META-GATE-REWRITE` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-SATISFIABILITY` | failure_driven | audit_meta_mismatch_regression | gate_satisfiability | `EXP-FAIL-META-GATE-SATISFIABILITY` |
| `GAP-FAIL-META-GATE-MISMATCH-GATE-SCENARIO-EXECUTION` | failure_driven | audit_meta_mismatch_regression | gate_scenario_execution | `EXP-FAIL-META-GATE-SCENARIO-EXECUTION` |
| `GAP-FAIL-META-GATE-MISMATCH-MANIFESTS` | failure_driven | audit_meta_mismatch_regression | manifests | `EXP-FAIL-META-MANIFESTS` |
| `GAP-FAIL-META-GATE-MISMATCH-MODULE-READINESS` | failure_driven | audit_meta_mismatch_regression | module_readiness | `EXP-FAIL-META-MODULE-READINESS` |
| `GAP-FAIL-META-GATE-MISMATCH-SAFE-DEFAULT` | failure_driven | audit_meta_mismatch_regression | safe_default | `EXP-FAIL-META-SAFE-DEFAULT` |
| `GAP-FAIL-META-MATRIX-CLAIM-MISMATCH-CASES-BASELINE` | failure_driven | audit_meta_mismatch_regression | cases_baseline | `EXP-FAIL-META-CASES-BASELINE` |
| `GAP-FAIL-META-MATRIX-CLAIM-MISMATCH-CLAIMS-DOCS` | failure_driven | audit_meta_mismatch_regression | claims_docs | `EXP-FAIL-META-CLAIMS-DOCS` |
| `GAP-FAIL-META-MATRIX-CLAIM-MISMATCH-MATRIX-COVERAGE` | failure_driven | audit_meta_mismatch_regression | matrix_coverage | `EXP-FAIL-META-MATRIX-COVERAGE` |
| `GAP-FAIL-META-MATRIX-CLAIM-MISMATCH-RUNTIME-VOCABULARY` | failure_driven | audit_meta_mismatch_regression | runtime_vocabulary | `EXP-FAIL-META-RUNTIME-VOCABULARY` |
| `GAP-KNOW-0046331D4CF9` | knowledge | universe_dimension_gap | D10 | `EXP-KNOW-D10` |
| `GAP-KNOW-0144E364AE88` | knowledge | universe_dimension_gap | D16 | `EXP-KNOW-D16` |
| `GAP-KNOW-0733D101CD78` | knowledge | universe_dimension_gap | D09 | `EXP-KNOW-D09` |
| `GAP-KNOW-131698DB89CE` | knowledge | universe_dimension_gap | D08 | cannot_plan: explicit non-goal dimension: no repair experiment is planned; only claim/enforce |
| `GAP-KNOW-19F9BAE43B4F` | knowledge | universe_dimension_gap | D11 | `EXP-KNOW-D11` |
| `GAP-KNOW-2449225E53BC` | knowledge | universe_dimension_gap | D03 | `EXP-KNOW-D03` |
| `GAP-KNOW-4E20E505D6BE` | knowledge | universe_dimension_gap | D19 | `EXP-KNOW-D19` |
| `GAP-KNOW-8CFA10A33EE8` | knowledge | universe_dimension_gap | D14 | `EXP-KNOW-D14` |
| `GAP-KNOW-A9FDABBC6B98` | knowledge | universe_dimension_gap | D07 | cannot_plan: explicit non-goal dimension: no repair experiment is planned; only claim/enforce |
| `GAP-KNOW-DA25B80E6306` | knowledge | universe_dimension_gap | D12 | `EXP-KNOW-D12` |
| `GAP-KNOW-DF96FDBC59A0` | knowledge | universe_dimension_gap | D04 | `EXP-KNOW-D04` |
| `GAP-KNOW-E5E00D03D52A` | knowledge | universe_dimension_gap | D17 | `EXP-KNOW-D17` |
| `GAP-KNOW-E9D869738D70` | knowledge | universe_dimension_gap | D20 | `EXP-KNOW-D20` |
| `GAP-KNOW-F5925DDEA69C` | knowledge | universe_dimension_gap | D18 | `EXP-KNOW-D18` |
| `GAP-KNOW-F94C650CD01B` | knowledge | universe_dimension_gap | D06 | `EXP-KNOW-D06` |

## Assumptions / limitations

- Candidates are discovery leads, not verified capability claims; the
  deterministic gate remains the only acceptance authority.
- `failure_driven` re-runs the committed universe checker (0 open / 0
  dynamic-unverified failures remain) and mines the committed audit's
  closed/mitigated meta-mismatch records and unanalyzed target cases.
- `differential` re-runs the committed capability-contract checker and
  records declared-vs-measured platform divergences on this host.
- `mutation`/`metamorphic`/`sample_based`/`knowledge_source_scan` are
  not_run with explicit reasons; no corpus/engine is fabricated.
- Re-running on the same host is byte-identical; cross-host differential
  candidates intentionally record the measured host.

## Validation

```bash
python scripts/discover_capability_gaps.py --check
python -m pytest -q tests/test_capability_dimensions.py tests/test_gap_registry_discovery.py
```

`--check` rebuilds the artifact in memory, compares all three data files
byte-for-byte, re-validates SHA256SUMS coverage and the GapRecord schema,
and exits 1 on any mismatch or silent discovery gap.
