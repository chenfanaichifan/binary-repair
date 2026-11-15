# Phase-8 repair-readiness roadmap (2026-11-16)

Status: Phase-8A planning and foundation roadmap. Branch
`feature/phase8-repair-readiness` at `2bfa112`. This phase delivers
**readiness and verification infrastructure only**: contracts,
acceptance classes, a 30-item measured readiness audit, a ground-truth
benchmark manifest, and an independent-verifier MVP. It adds **no new
vulnerability-repair capability** and does **not** upgrade any `verified`
disposition.

Machine-readable phase flags:

    new_vulnerability_repair_capability_this_phase: false
    auto_upgrade_verified_this_phase: false
    hidden_benchmark_run_this_phase: false
    capability_graduation_this_phase: false

## 1. G01-G30 mapping to Phase 8A-8E

The 30 Phase-8 user requirements (G01-G30) are taken verbatim from the
readiness registry (`app/services/repair_readiness.py`); the phase banding
and measured status below come from the committed artifact
`artifacts/phase8-readiness-2026-11-16/readiness.json` (read-only source of
truth for this roadmap). The source registry keeps the bilingual user
titles; this ASCII document uses the English label for each verbatim id.

Phase bands:

| Phase | Band | G range | Items | This round |
|---|---|---|---|---|
| 8A | Discovery, knowledge and repair-readiness foundation | G01-G08 | 8 | readiness baseline + contracts + benchmark manifest + verifier MVP delivered (no capability added) |
| 8B | Analysis capabilities (cross-function, alias, integer/string/UAF) | G09-G18 | 10 | not implemented |
| 8C | Repair strategy registry, planner, candidate manager, application | G19-G22 | 4 | existing registry/planner/candidate measured; no new capability added |
| 8D | Verification, regression, autonomous experiments, acceptance-oracle audit | G23-G27 | 5 | independent verifier MVP only; no new semantic/regression capability |
| 8E | Evaluation, hidden benchmark, capability promotion governance | G28-G30 | 3 | hidden benchmark unavailable (hidden_available=false); no promotion run |

Measured status distribution across the 30 items (probe-derived, never a
capability claim):

| Status | Items |
|---|---|
| implemented | 13 |
| partial | 7 |
| missing | 5 |
| not_run | 1 |
| non_goal | 4 |
| total | 30 |

Full 30-item mapping. Blocker detail and next action for every item live
in `artifacts/phase8-readiness-2026-11-16/readiness.json` and
`docs/acceptance/phase8-readiness-2026-11-16.md`.

| id | English label | phase | priority | this-round status |
|---|---|---|---|---|
| G01 | Knowledge Source Scanner | 8A | P1 | partial |
| G02 | Dimension Discovery Engine | 8A | P1 | implemented |
| G03 | unknown-space tracking beyond 240 cells | 8A | P1 | partial |
| G04 | Combination Discovery | 8A | P2 | missing |
| G05 | Mutation-based Discovery | 8A | P2 | missing |
| G06 | Metamorphic Discovery | 8A | P2 | missing |
| G07 | Binary Corpus | 8A | P1 | implemented |
| G08 | deduplication/lineage for new findings vs old gaps | 8A | P1 | implemented |
| G09 | Cross-function Data-Flow | 8B | P0 | partial |
| G10 | Pointer Alias | 8B | P0 | non_goal |
| G11 | global variable/struct capacity inference | 8B | P0 | non_goal |
| G12 | Integer vulnerability analysis (range/overflow/truncation/signedness) | 8B | P0 | partial |
| G13 | String vulnerability analysis | 8B | P0 | implemented |
| G14 | UAF lifetime | 8B | P1 | non_goal |
| G15 | Indirect call analysis | 8B | P0 | partial |
| G16 | Path-sensitive analysis | 8B | P1 | missing |
| G17 | Concurrency vulnerability analysis | 8B | P1 | missing |
| G18 | more binary format/architecture coverage | 8B | P2 | non_goal |
| G19 | Repair Strategy Registry | 8C | P0 | implemented |
| G20 | Repair Planner | 8C | P0 | implemented |
| G21 | Candidate Manager | 8C | P1 | implemented |
| G22 | Patch Application Engine | 8C | P0 | implemented |
| G23 | Binary Integrity Verifier | 8D | P0 | implemented |
| G24 | Semantic Verifier | 8D | P0 | implemented |
| G25 | Regression Engine | 8D | P0 | implemented |
| G26 | Autonomous Experiment Engine | 8D | P1 | implemented |
| G27 | Acceptance Oracle Self-Audit | 8D | P1 | implemented |
| G28 | Multi-model Evaluation | 8E | P1 | partial |
| G29 | Hidden Benchmark | 8E | P2 | not_run |
| G30 | Capability Promotion Governance | 8E | P1 | partial |

## 2. What Phase 8A delivered this round

Foundation deliverables, all machine-checkable:

1. **Contracts (12 total, 6 new).**
   - New: `contracts/binary-target.schema.json`,
     `contracts/vulnerability-finding.schema.json`,
     `contracts/root-cause.schema.json`,
     `contracts/verification.schema.json`,
     `contracts/benchmark-sample.schema.json`,
     `contracts/patch-candidate.schema.json`.
   - Existing six phase-7 contracts keep their field semantics; the
     acceptance contract extends AM01-AM20 with AM21-AM24.
   - Validator: `python scripts/check_contract_schemas.py --check`
     (schema self-checks, 12 valid + 12 invalid fixtures, committed
     artifact integration, deterministic `SHA256SUMS`, jsonschema and
     the documented fallback validator).
2. **Acceptance governance AM21-AM24.**
   - AM21 `repair_scope_mismatch`, AM22 `semantic_scope_mismatch`,
     AM23 `oracle_quality_insufficient`, AM24
     `benchmark_version_mismatch` added to
     `app/services/acceptance_models.py`; AM01-AM20 ids and semantics
     unchanged.
   - Committed audit matrix: **52 cases** (9 positive, 43 negative),
     **24/24** AM classes covered, recall 1.0, precision 1.0; all
     AM01-AM20 cases remain green.
   - Artifact: `artifacts/acceptance-model-audit-2026-11-16/`.
3. **Meta-audit 26 to 28 scenarios.**
   - Added `acceptance_oracle_self_report_masquerade` and
     `benchmark_version_mismatch`; recall/precision stay 1.0;
     `MIN_SCENARIOS` is 28.
4. **Readiness baseline (peer deliverable, same phase).**
   - `app/services/repair_readiness.py`,
     `scripts/audit_repair_readiness.py`,
     `artifacts/phase8-readiness-2026-11-16/`,
     `docs/acceptance/phase8-readiness-2026-11-16.md`.
   - 30/30 items carry `capability_claim: false`;
     `capability_claims=[]`; hidden benchmark `not_run`.
5. **Ground-truth benchmark v1 manifest (peer deliverable).**
   - `benchmark/phase8-v1/manifest.json` with 12 committed samples and
     `hidden_available=false`; its samples validate against this phase's
     `benchmark-sample.schema.json` through the contract checker.
6. **Independent verifier MVP (peer deliverable).**
   - `app/services/independent_verifier.py` + `scripts/verify_repair.py`;
     the report shape is the committed `verification.schema.json`,
     validated by `--selftest` and by schema cross-field semantics.

## 3. Phase 8B-8E are NOT implemented this round

This is a foundation round. The analysis, repair-engine and evaluation
capabilities in 8B-8E remain at the measured
`partial`/`missing`/`not_run`/`non_goal` status shown above: no new
vulnerability-analysis or repair capability was implemented and no disposition
was promoted; the new readiness/benchmark/verifier pieces are measurement-only
infrastructure. In particular:

* 8B (G09-G18): analysis stays same-function/leaf-only; pointer alias,
  global/struct capacity, UAF and extra format/arch remain explicit
  non-goals or missing;
* 8C (G19-G22): existing strategy registry/planner/candidate manager are
  measured as-is; no new patch capability was added;
* 8D (G23-G27): only the independent-verifier MVP and the committed
  acceptance-oracle audit exist; semantic verification, regression engine
  and autonomous experiments are not newly built;
* 8E (G28-G30): hidden benchmark stays `hidden_available=false`, provider
  coverage stays at the measured 2/4, and capability-promotion governance
  has no end-to-end workflow.

All 30 items carry `capability_claim: false`. A future phase must
explicitly authorize any capability item and satisfy its probe/test/
ground-truth requirements before a status or `verified` disposition
changes.

## 4. Contracts and fail-closed rules

* `verification.schema.json`: `decision=verified` requires
  `independence.ok=true`, `independence.generator_evidence_excluded=true`,
  at least one passed independent oracle check and no required
  failed/not-run check; the checker enforces this beyond JSON Schema.
* `benchmark-sample.schema.json`: `hidden_available` is `const false`; an
  `analysis_only` expectation may not claim a runtime oracle; a
  `function`/`whole_program` expectation needs at least one independent
  oracle kind.
* `patch-candidate.schema.json` has no `release_eligible` state: a
  candidate can at most be `verified` by independent verification, and
  `verified` requires an independent-oracle plan and a trusted model
  identity; it can never auto-promote.
* `binary-target`/`vulnerability-finding`/`root-cause` bind identity,
  finding scope/location/sink and root-cause evidence to digests; missing
  evidence stays explicit instead of being invented.
* `acceptance.schema.json` extends the registry to AM01-AM24 and keeps
  `verified` gated by complete evidence and independence.

## 5. Evidence index

Committed artifacts produced or extended by Phase 8A:

    contracts/ (12 schemas)
    artifacts/contract-fixtures-2026-11-16/ (12 valid + 12 invalid + SHA256SUMS)
    artifacts/acceptance-model-audit-2026-11-16/ (52 cases, report, README, SHA256SUMS)
    artifacts/phase8-readiness-2026-11-16/ (30-item readiness audit)
    benchmark/phase8-v1/manifest.json (12 benchmark samples)
    app/services/independent_verifier.py + scripts/verify_repair.py
    scripts/check_contract_schemas.py, scripts/audit_acceptance_models.py, scripts/meta_audit.py

Reproduce (offline, no network, no AI):

    .venv/bin/python scripts/check_contract_schemas.py --check
    .venv/bin/python scripts/check_contract_schemas.py --no-jsonschema --check
    .venv/bin/python scripts/audit_acceptance_models.py --write
    .venv/bin/python scripts/audit_acceptance_models.py --check
    .venv/bin/python scripts/meta_audit.py --json
    .venv/bin/python scripts/verify_repair.py --selftest
    .venv/bin/python -m pytest -q tests/test_contract_schemas.py tests/test_acceptance_models.py tests/test_meta_audit.py

Expected at roadmap time: contract checker green (12/12 schemas, 12/12
valid, 12/12 invalid; committed artifacts 20 dimensions/64 gaps/91
reflection records + 12 benchmark samples validated, verification report
explicit not_run until committed); acceptance matrix green (52 cases,
24/24 classes, recall/precision 1.0); meta-audit green (28 scenarios);
verifier selftest green; language policy PASS.

## 6. Backlog and acceptance criteria

| Backlog | Phase | Next deliverable | Acceptance to close |
|---|---|---|---|
| B01 | 8B | cross-function data-flow + pointer alias analysis with fixtures | independent oracle on a cross-function family; same-function limits removed only with evidence |
| B02 | 8B | integer/string/UAF analysis and fixture matrices | per-family PoC/regression/reference fix; no case counted without capability |
| B03 | 8C | repair planner extension + candidate promotion workflow | planner outputs validate against contracts; no auto-promotion |
| B04 | 8D | semantic verifier + regression engine beyond the MVP | independent verifier rejects memory-safe but behavior-changing patches |
| B05 | 8E | multi-model and hidden benchmark execution under governance | real provider matrix; hidden benchmark stays unavailable until committed |

## 7. Governance

1. G01-G30 ids/titles are authoritative and must not be renumbered,
   merged or silently dropped; readiness status is probe-derived.
2. No new repair capability may be claimed without probes, tests and
   independent verification; readiness status never implies capability.
3. `verified` requires the deterministic gate plus evidence and
   independence; contracts and the independent verifier may reject but
   never promote.
4. Hidden benchmark samples stay `hidden_available=false`; the public
   manifest may carry a commitment hash but never fabricated results.
5. Hosted CI, local frozen-tree evidence and the self-hosted Lima nightly
   remain separate evidence layers; this document claims no CI run.
