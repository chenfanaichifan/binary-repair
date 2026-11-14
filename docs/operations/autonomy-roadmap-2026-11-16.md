# Autonomy foundation roadmap (2026-11-16)

Status: Phase-7 governance and foundation roadmap. Baseline mainline
`a8934fe`. This document maps the user's 15 Phase-7 items to stage,
dependencies, acceptance criteria, owner and this round's delivery status.

Machine-readable phase flags:

    new_vulnerability_repair_capability_this_phase: false
    auto_upgrade_verified_this_phase: false
    capability_graduation_this_phase: false
    self_hosted_lima_nightly_run_this_phase: false

## 1. Scope and hard boundary

This round builds **capability discovery, acceptance auditing, reflection,
unified audit, and contract/state vocabulary**. It does not add, extend or
upgrade any vulnerability-repair capability, and it does not promote any
disposition to `verified`.

Concretely:

* the L7 repair/semantics layer (cross-function data flow, integer/string/UAF
  matrices, repair planner, independent binary verifier) is unchanged and its
  four user items remain `not_started`;
* `app/services/repair_states.py` adds a canonical state *vocabulary* only: it
  never invents a repair path and rejects `verified -> release_eligible` unless
  both `evidence_ok` and `independence_ok` are true;
* the acceptance matcher fails closed; a match can only be `verified` when no
  mismatch class fires and evidence and independence are complete, and it never
  repairs anything;
* reflection records always carry `verified: false` and a capability decision
  limited to `analysis_only` / `candidate` / `not_run`;
* gap registry records are never auto-promoted (`no_auto_promotion: true`);
  candidates stay `candidate`;
* the frozen baseline and its release evidence (`fd6ca41` release worktree,
  `docs/release-2026-11-16.md`, `docs/release/CI-SIGNOFF-2026-11-15.md`) are
  preserved as-is; this phase does not rewrite or re-sign them.

## 2. User 15-item map

Status vocabulary: `implemented` / `partial` / `not_started`. Nothing below is
declared implemented unless it has a committed module and a machine-readable
artifact or test in this checkout.

| Item | User item | Stage | Dependencies | Acceptance criteria | Owner | This round |
|---|---|---|---|---|---|---|
| P0-01 | Freeze the existing `fd6ca41` baseline and protect release evidence | P0 / freeze | release worktree + phase-6 release evidence | baseline commit frozen; `docs/release-2026-11-16.md` and `docs/release/CI-SIGNOFF-2026-11-15.md` kept byte-identical; no phase-7 code path mutates release evidence | release-owner | implemented |
| P0-02 | Audit 240 cells across the old 11 dimensions and build old-to-new dimension mapping | P0 / audit | coverage matrix + claims registry | every old dimension enumerated; `OLD_11_DIMS`, `OLD_TO_NEW`, `NEW_TO_OLD` are bidirectional and covered by tests; artifact carries old/new mapping | universe | implemented |
| P0-03 | Build the 20 first-level capability dimension candidate registry | P0 / registry | P0-02 mapping | D01-D20 unique, each with title/status/owner/review_by/evidence_refs; `dimension_count=20`; `unknown_within_universe=0`; no fabricated counts | universe | implemented |
| P0-04 | Establish an unknown-outside-universe discovery mechanism | P0 / discovery | P0-03 registry + audit/gap workstream | seven discovery mechanisms registered; `run` mechanisms carry real evidence, `not_run` mechanisms carry explicit reasons; unknown space reported as `not_measurable` (never a fabricated number); out-of-universe set bounded by the 12 non-goals | gap-registry | partial |
| P0-05 | Migrate the 12 non-goal claims into the unified Gap Registry | P0 / registry | claims.json + gap schema | exactly 12 records with `discovery_source=claims_non_goal`, `status=non_goal`; unique ids; `no_auto_promotion=true`; registry validation clean | gap-registry | implemented |
| P0-06 | Build the 20-class acceptance mismatch registry | P0 / registry | acceptance dimensions | AM01-AM20 unique with code/severity/required_actions; A01-A08 dimensions map to mismatch ids; each class has at least one committed negative case | acceptance | implemented |
| P0-07 | Implement `AcceptanceModelMatcher` and negative testing | P0 / evaluation | P0-06 registry | pure fail-closed matcher; 43-case committed audit (39 negative cases, all 20 classes covered); recall=1.0 and precision=1.0; `--check` recomputes deterministically | acceptance | implemented |
| P0-08 | Establish requested/served model identity auditing | P0 / evaluation | P0-07 matcher | identity states `exact` / `alias` / `served-model-only` / `unknown` / `mismatch`; served-only can never be verified (AM09-AM12 negative cases); **boundary:** only the acceptance matcher enforces identity; provider matrix is not expanded this round | acceptance | partial |
| P1-09 | Cross-function data-flow and alias analysis capability | P1 / repair | L7 binary-semantics work | a cross-function/alias fixture family with a runtime oracle, failing on the current deterministic engine and passing only after a real capability exists | solver | not_started |
| P1-10 | Integer, string and UAF vulnerability test matrix | P1 / fixtures | PoC/regression oracle + L7 work | per-family fixtures (integer/string/UAF) with PoC, regression, behavior contract and reference fix; no case addition counted as capability | solver | not_started |
| P1-11 | Repair planner and candidate-patch state machine | P1 / repair | L7 work + P1-09/10 | a planner contract plus candidate generation whose states are enforced by the canonical machine; state vocabulary alone is not this item | solver | not_started |
| P1-12 | Independent binary integrity / semantic verifier | P1 / verification | L7 work + evidence contract | a verifier independent of patch generation that re-derives integrity/semantics from a fresh artifact copy and can reject a memory-safe but behavior-changing patch | oracle | not_started |
| P1-13 | Enable real CI and produce final-SHA run evidence | P1 / CI | CI workflows + frozen release SHA | real hosted CI run for the phase baseline (success, including `release-gate-hosted`); final-SHA rerun for this phase tracked with its own run id; self-hosted Lima nightly reported `not_run` with signoff, never claimed as CI | release-owner | partial |
| P1-14 | Reflection engine and automatic experiment planner | P1 / reflection | audit/gap artifacts | exactly 12 ordered questions (Q01-Q12) with answer/evidence/status; `verified` always false; decisions limited to analysis_only/candidate/not_run; plan status planned/cannot_plan with reasons; committed bundle regenerable and deterministic | reflection | implemented |
| P1-15 | Unified autonomous-repair audit entry point | P1 / audit | committed static checks | `scripts/autonomous_repair_audit.py` runs the committed static checks through one injectable-runner entry, aggregates JSON, marks missing inputs `not_run` and never fakes a pass; dynamic/Lima suites are not claimed | audit | implemented |

Status summary: **implemented 8 / partial 3 / not_started 4**. The 4
`not_started` items (P1-09, P1-10, P1-11, P1-12) are exactly the
vulnerability-repair capability items; this is intentional.

## 3. Item evidence (status justification)

### P0-01 baseline freeze

* `fd6ca41` is the phase-6 frozen baseline; release evidence remains in
  `docs/release-2026-11-16.md`, `docs/release/CI-SIGNOFF-2026-11-15.md` and the
  frozen release worktree.
* This phase's branch starts at verified mainline `a8934fe` and adds only new
  files/scopes; no release record was rewritten.

### P0-02 / P0-03 capability universe

* `app/services/capability_dimensions.py`: `OLD_11_DIMS`, `OLD_TO_NEW`,
  `NEW_TO_OLD`, `DIMENSIONS` (D01-D20) with `STATUSES`
  (`covered` / `partial` / `non_goal` / `unavailable` / `not_started`).
* `scripts/build_universe_dimension_registry.py` emits
  `artifacts/capability-universe-2026-11-16/dimension-registry.json`:
  - `dimension_count = 20`, `unknown_within_universe = 0`
  - status split: covered 5, partial 6, non_goal 2, not_started 7
  - `mapped_cells = 240`, `out_of_universe_count = 12`
  - `undiscovered_space = "not_measurable"`
  - both old-to-new and new-to-old mappings are committed.

### P0-04 bounded unknown-outside-universe discovery

* `artifacts/gap-registry-2026-11-16/candidates.json`: 7 mechanisms,
  51 bounded candidates. `knowledge`, `failure_driven` and `differential` ran;
  `mutation`, `metamorphic`, `sample_based`, `knowledge_source_scan` did not
  run and carry explicit reasons.
* The round does not claim the universe was exhaustively discovered or that
  unknown space is zero. This is why the item is `partial`, not `implemented`.

### P0-05 unified gap registry

* `app/services/gap_registry.py` + `artifacts/gap-registry-2026-11-16/gaps.json`:
  64 unique records; `records_by_source.claims_non_goal = 12`;
  `records_by_status.non_goal = 12`; `no_auto_promotion = true`; validation ok.
* `contracts/gap.schema.json` matches the module fields (target object,
  experiment object, severity set including `info`, gap id pattern).

### P0-06 / P0-07 acceptance intelligence

* `app/services/acceptance_models.py`: `ACCEPTANCE_DIMENSIONS` (A01-A08),
  `MISMATCH_RULES` (AM01-AM20), `MODEL_IDENTITY_STATUSES`, pure matcher output
  `{decision, mismatches, required_actions, verified, residual_risk, reasons}`.
* `scripts/audit_acceptance_models.py --check`: OK; committed report has 43
  cases (39 negative), all 20 classes covered, recall 1.0 / precision 1.0.

### P0-08 request/served identity (partial)

* Identity statuses and AM09-AM12 negative cases are enforced by the matcher.
* The provider comparison matrix and external-model coverage are **not**
  expanded this round; identity auditing is only as wide as the acceptance
  evidence supplied. Hence `partial`.

### P1-14 reflection

* `app/services/reflection_engine.py`: 12-question contract, failure types
  `capability` / `evaluation` / `infrastructure` / `knowledge` / `unknown`,
  decisions `analysis_only` / `candidate` / `not_run`, plan
  `planned` / `cannot_plan`, `verified=False` by construction.
* `scripts/run_autonomous_reflection.py` and
  `artifacts/autonomous-reflection-2026-11-16/` hold the committed bundle.
* Verified at roadmap time: `run_autonomous_reflection.py --check` exits 0
  (91 records, 12 candidate records, 0 `verified_true`, 0 contract violations);
  the bundle is deterministic and regenerable. Reflection still cannot repair
  or verify anything.

### P1-15 unified audit

* `scripts/autonomous_repair_audit.py` exposes one static audit entry
  (`--mode full|static`, `--json`, optional `--evidence-out`) over the
  committed static checks; missing inputs become `not_run`, never fake passes.
* Verified at roadmap time: `--mode static --json` exits 0 with `ok: true`;
  the `universe-methodology`, `autonomous-reflection` and
  `coverage-gate-static` checks all pass. Dynamic/Lima suites are not run by
  this static entry and are not claimed.

### P1-13 CI (partial)

* Real hosted CI exists for the release line and includes the
  `release-gate-hosted` job (see `docs/release-2026-11-16.md`).
* This phase adds static `--check` governance steps (acceptance-model audit,
  capability-gap discovery, reflection contract) as documented in
  `docs/acceptance/autonomous-intelligence-2026-11-16.md`.
* Final-SHA run evidence for this phase is tracked separately when the phase
  SHA is frozen; the self-hosted Lima nightly remains `not_run` per
  `docs/release/CI-SIGNOFF-2026-11-15.md`.

## 4. Explicit non-claims

* No new vulnerability-repair capability: P1-09, P1-10, P1-11 and P1-12 stay
  `not_started`; no repair family or engine path was added or widened.
* No automatic `verified` upgrade: the matcher, reflection engine and gap
  registry cannot promote a disposition; `verified` still requires evidence and
  independence through the deterministic gate.
* No whole-program/arbitrary-binary claim: scope and non-goals are unchanged.
* No external-model expansion: provider matrix and model access are unchanged;
  `served-model-only` is still rejected.
* No CI run is claimed by this document, and no `not_run` check is reported as
  passed. Hosted CI evidence and local frozen-tree evidence stay separate.
* No fabricated discovery numbers: unknown-outside-universe space is
  `not_measurable`, not zero.

## 5. Backlog (not started or partial)

| Backlog id | Item | Depends on | Next concrete deliverable | Acceptance to close it |
|---|---|---|---|---|
| B-01 | P1-09 cross-function data flow / alias analysis | L7 binary semantics; P1-10 fixtures | analysis prototype on cross-function/alias fixtures, integrated behind the deterministic gate | fixture family that current engine fails is repaired and independently verified; capability shown by cases, not prose |
| B-02 | P1-10 integer/string/UAF matrices | PoC oracle + behavior contract | family fixtures with PoC/regression/reference fix for integer, string and UAF bugs | each family has >=1 independent case with oracle; no case counted before capability exists |
| B-03 | P1-11 repair planner + candidate patch state machine | P1-09/10; `repair_states.py` vocabulary already available | planner contract producing planned candidates; states enforced by the canonical machine | planner output always validates against the state machine; illegal transitions unrepresentable |
| B-04 | P1-12 independent binary integrity / semantic verifier | evidence contract; behavior diff | verifier that re-derives integrity/semantics from a fresh artifact copy | rejects a memory-safe but behavior-changing patch; independent of patch generation |
| B-05 | P0-04 discovery breadth | mutation/metamorphic/sample-based/knowledge-source corpora | implement at least one additional runnable discovery mechanism with evidence | `not_run` count decreases and candidates have machine evidence; unknown space still honestly bounded |
| B-06 | P0-08 provider identity breadth | provider matrix expansion (separate authorization) | identity audit over a broader requested/served model matrix | served-model-only never verified across the wider matrix |
| B-07 | P1-13 phase final-SHA CI evidence | frozen phase SHA; CI workflows | hosted CI run for the phase SHA + local frozen-tree gate record | real run id recorded; self-hosted nightly either provisioned or still explicitly `not_run` |

## 6. Contracts and state vocabulary (this round's engineering plumbing)

Six JSON contracts under `contracts/` are authored from the module contracts and
validated by `scripts/check_contract_schemas.py`:

| Contract | Purpose | Aligned with |
|---|---|---|
| `capability.schema.json` | one D01-D20 capability dimension record | `capability_dimensions.py` / universe registry artifact |
| `gap.schema.json` | unified GapRecord | `gap_registry.py` records |
| `acceptance.schema.json` | A01-A08 + AM01-AM20 registry and matcher result | `acceptance_models.py` |
| `repair.schema.json` | canonical repair attempt state record | `repair_states.py` state machine |
| `evidence.schema.json` | digest/tree/artifact/runner/guest binding | evidence layer (Lead-specified fields) |
| `reflection.schema.json` | 12-question reflection record, `verified=false` | `reflection_engine.py` |

Verification: `scripts/check_contract_schemas.py --check` validates schema
structure, 6 valid fixtures (must pass), 6 invalid fixtures (must be rejected),
cross-field semantics and the deterministic `SHA256SUMS`; `jsonschema` is used
when available and the documented minimal fallback otherwise.

## 7. Evidence index and reproduction commands

Recorded artifacts (paths are repository-relative):

    artifacts/capability-universe-2026-11-16/dimension-registry.json
    artifacts/gap-registry-2026-11-16/gaps.json
    artifacts/gap-registry-2026-11-16/candidates.json
    artifacts/acceptance-model-audit-2026-11-16/report.json
    artifacts/autonomous-reflection-2026-11-16/reflection.json
    artifacts/contract-fixtures-2026-11-16/SHA256SUMS
    contracts/*.schema.json
    app/services/repair_states.py
    scripts/check_contract_schemas.py

Reproduction commands (offline, no network):

    .venv/bin/python scripts/check_contract_schemas.py --check
    .venv/bin/python scripts/check_contract_schemas.py --no-jsonschema --check
    .venv/bin/python scripts/audit_acceptance_models.py --check
    .venv/bin/python scripts/check_universe_methodology.py --check
    .venv/bin/python scripts/run_autonomous_reflection.py --check
    .venv/bin/python scripts/autonomous_repair_audit.py --mode static --json
    .venv/bin/python -m pytest -q tests/test_repair_states.py tests/test_contract_schemas.py

Expected at roadmap time: all commands green - contract checker (6/6 valid,
6/6 invalid, SUMS verified), acceptance audit, universe methodology, reflection
bundle (`--check`, 91 records / 0 `verified_true`), and the unified static
audit (`ok: true`). Any later red result must be recorded here as a real
integration issue, never hidden.

State-vocabulary record (this round, SHA-256 of the committed files):

    81ef57d119be19f1df4ca1866c94c9ea2bcd03ab965187496d69781b7069ed59  app/services/repair_states.py
    57e3dcb5a7ad61a2afb41f331e44df49d13505cc8d390e84e0120f30d0f477a0  scripts/check_contract_schemas.py
    47af250bd1cbc771d601cdee93c65b79d6da4d604c7011817d60d852a58c08a5  artifacts/contract-fixtures-2026-11-16/SHA256SUMS

## 8. Governance and maintenance rules

1. A status in this roadmap is evidence-backed: `implemented` requires a
   committed module plus artifact or test; otherwise the item is `partial` or
   `not_started`. A later round must not upgrade status by prose.
2. `repair_states.py` remains the single source of truth for repair states and
   transitions. Other modules must map into it, not invent states.
3. Contracts are versioned (`schema_version` 1) and validated by
   `scripts/check_contract_schemas.py --check`; contract changes require
   fixtures + SUMS regeneration and re-alignment with the module owning the
   contract.
4. No automatic promotion: `verified` requires the deterministic gate plus
   evidence and independence; reflection `verified` is always false; gap
   candidates and non-goals never auto-promote.
5. Keep CI evidence layers separate: hosted CI evidence, local frozen-tree
   evidence, and the self-hosted Lima nightly (`not_run` until provisioned) are
   never conflated.
6. Backlog items B-01..B-07 are the only authorized route to new repair
   capability; starting them requires a new phase decision that explicitly
   withdraws the "no new vulnerability-repair capability" boundary.
