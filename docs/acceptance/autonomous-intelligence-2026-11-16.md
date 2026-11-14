# Autonomous intelligence foundation (2026-11-16)

Status: phase-7 foundation. This round adds **capability discovery, acceptance
auditing, reflection and unified audit infrastructure only**. It does **not**
add a new vulnerability-repair capability and does **not** upgrade any
`verified` disposition. Every reflection record in this round carries
`verified: false`, and a `candidate` is a bounded experiment proposal, never a
verified patch.

## 1. What this round changed

| Area | Delivered this round | Boundary |
|---|---|---|
| Acceptance intelligence | `app/services/acceptance_models.py` + `scripts/audit_acceptance_models.py`: A01-A08 dimensions, AM01-AM20 mismatch registry, `AcceptanceModelMatcher`, 43-case committed audit (negative case per mismatch class), recall/precision 1.0, fail-closed model-identity rules | evaluation/audit only; it cannot promote a repair |
| Capability universe | 240 measured cells mapped to a 20-dimension candidate registry; old 11-dimension mapping; `unknown_within_universe=0`; unknown-outside-universe is bounded and explicit | `undiscovered_space="not_measurable"`; the round does not claim the universe is exhaustively discovered |
| Gap registry / discovery | 12 researched non-goals migrated to a unified gap registry; six discovery mechanisms; failure-driven candidates stay `candidate`, never auto-promoted | six mechanisms are not all implemented; `not_run` mechanisms carry reasons |
| Reflection engine | `app/services/reflection_engine.py`: 12-question contract + experiment planner; classifications `capability/evaluation/infrastructure/knowledge/unknown`; decisions `analysis_only/candidate/not_run`; `verified` always `false` | never repairs, never verifies, never promotes |
| Unified audit | `scripts/autonomous_repair_audit.py`: subprocess orchestration of the static committed checks with an injectable runner, aggregate JSON and optional evidence bundle | static only; dynamic/Lima suites are not run by this entry |
| CI | `test`/`coverage-gate` governance checks plus three phase-7 static `--check` steps (acceptance-model audit, capability-gap discovery, reflection contract) | no CI run is claimed here; missing scripts/inputs are explicit `not_run`, never faked |

## 2. Seven-layer architecture (current state)

| Layer | Component | This round |
|---|---|---|
| L1 acceptance model | acceptance dimensions + mismatch registry + matcher + committed audit | implemented (evaluation layer) |
| L2 capability universe | 240 cells, 20-dimension candidate registry, 11->20 mapping, bounded unknown-outside-universe | implemented for discovery; undiscovered space not measurable |
| L3 gap registry | unified gap records, 12 non-goal migration, six discovery mechanisms | implemented by the parallel gap-registry workstream; failure-driven candidates remain candidates |
| L4 reflection | 12 questions + experiment planner + classification | implemented (this task) |
| L5 unified audit | `autonomous_repair_audit.py` static orchestration + evidence bundle | implemented (this task) |
| L6 contracts / state machine | canonical repair/capability states, six JSON contracts | parallel phase-7 workstream; not claimed as complete here |
| L7 binary semantics / repair | cross-function data-flow, integer/string/UAF matrices, repair planner, independent binary verifier | **unchanged / not started this round** |

The boundary is explicit: L1-L5 are analysis/discovery/audit foundations. L7
repair capability was not extended in this round, and no module here can raise a
disposition to `verified`.

## 3. Six discovery mechanisms

| Mechanism | Status | Evidence/limitation |
|---|---|---|
| knowledge (universe vs claims/audit) | implemented (parallel gap-registry workstream) | 12 non-goals + registry mapping; no fabricated gaps |
| failure-driven (open/dynamic/meta mismatches) | implemented (parallel workstream) | consumes committed audit artifacts; candidates stay `candidate` |
| differential (capability-contract negative checks) | partial | tied to `scripts/check_capability_contract.py`; not re-run by the reflection engine |
| mutation / metamorphic | not_run | no mutation corpus in this checkout; explicit reason, never pretended |
| sample-based | not_run | no external sample corpus; explicit reason |
| knowledge-source scan | not_run | no external corpus; explicit reason |

When a mechanism is `not_run`, the reason is recorded; a missing mechanism is
never reported as "no gap found".

## 4. Reflection: the 12-question contract

Each reflection record contains exactly these questions (in order), each with
`answer`, `evidence` and `status` in `{answered, unknown}`. An `unknown` answer
must explain itself; a question is never omitted.

| # | Question | What "answered" means |
|---|---|---|
| Q01 | What was expected? | expected behavior recorded |
| Q02 | What was observed? | observed behavior recorded |
| Q03 | What evidence supports the observation? | machine-readable evidence (artifact/cell/gap/contract pointers) |
| Q04 | Is the evidence sufficient to classify the failure? | evidence exists; classification explicit |
| Q05 | Is this an infrastructure/environment failure? | infrastructure markers present/absent |
| Q06 | Is the observed miss explained by a capability gap? | capability hypothesis supported by evidence, still only a hypothesis |
| Q07 | Which capability, cell or strategy is implicated? | capability/cell pointer exists |
| Q08 | What is the root-cause hypothesis? | hypothesis stated for a classified failure |
| Q09 | What is the smallest falsifiable experiment? | planned only for an evidenced capability hypothesis |
| Q10 | What acceptance criteria and independent verification apply? | planned experiment acceptance criteria |
| Q11 | What regression checks protect existing evidence? | planned regression checks |
| Q12 | What is the safe capability decision and review owner? | always answered: decision + owner |

Decision rules:

- `verified` is always `false`.
- `capability_decision` is only `analysis_only`, `candidate` or `not_run`.
- No machine-readable evidence means `not_run`; a candidate is forbidden.
- An infrastructure/environment failure is classified `infrastructure`, its
  decision is `not_run`, and it is never converted into a capability gap.
- `candidate` is allowed only for an evidenced capability hypothesis with a
  `planned` experiment (concrete samples, acceptance criteria, independent
  verification, regression checks).
- Missing or unreadable input artifacts are recorded as explicit `not_run`
  entries with reasons; the tool exits `2` rather than inventing data.

## 5. Inputs and current evidence state

The reflection runner reads committed artifacts only (no network, no LLM):

| Input | Purpose | Current checkout |
|---|---|---|
| `artifacts/gap-registry-2026-11-16/candidates.json` | failure-driven candidates from the gap registry | produced by the parallel gap-registry workstream; when absent the reflection bundle records an explicit `not_run` entry |
| `artifacts/acceptance-model-audit-2026-11-16/report.json` | acceptance mismatch evidence (43 committed cases) | read; evaluation reflections (analysis_only) |
| `artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json` | measured capability gaps/unknowns | read; open/dynamic/mitigated gaps reflected (runtime gaps become infrastructure/not_run) |

Generated bundle: `artifacts/autonomous-reflection-2026-11-16/`
(`reflection.json`, `README.md`, `SHA256SUMS`). In the current checkout the
bundle contains **91 records** (12 capability candidates, 73 analysis_only,
6 not_run), failure types capability 12 / evaluation 58 / infrastructure 6 /
knowledge 15, with `verified_true_count=0`; all three inputs were readable, so
`--check` exits `0` and there are no `not_run` input entries. The 12 candidates
are bounded experiment proposals only (never verified patches); missing inputs
would instead be explicit `not_run` entries with exit `2`.

## 6. Safety boundaries

- No new repair capability; no promotion to `verified`; no automatic
  `release_eligible`.
- Only three capability decisions (`analysis_only`, `candidate`, `not_run`);
  `candidate` is an experiment proposal, never a patch verdict.
- Infrastructure failures are never capability gaps; unevidenced failures are
  `not_run`.
- The reflection engine is deterministic and offline; the audit entry only
  orchestrates committed static checks (injectable runner; no 10-minute suites
  in tests).
- Missing inputs/scripts are explicit `not_run` with reasons. CI steps are only
  added for scripts that exist; no CI run is claimed here.
- The reflection bundle is analysis evidence, not release evidence; release
  decisions still go through the frozen-tree release gate and its evidence
  chain.

## 7. User backlog mapping (15 items, this round)

Status vocabulary: `implemented` = landed with committed evidence in this round;
`partial` = usable but bounded/not complete; `not_started` = explicitly out of
this round. The 15 items are rendered in ASCII English per the repository docs
policy; their ids, order and meaning follow the user backlog exactly.

| # | Backlog item | Status | Note |
|---|---|---|---|
| 1 | P0-01 Freeze the existing `fd6ca41` baseline and protect the existing release evidence | implemented | release evidence/tag exists on the frozen baseline and is protected by the phase-0 freeze; this round's work is on `feature/autonomy-foundation` (verified mainline `a8934fe`) |
| 2 | P0-02 Audit the current 240 cells across the 11 dimensions and establish the old-to-new dimension mapping | implemented | 240 cells audited; old 11-dimension mapping recorded in the 20-dimension registry |
| 3 | P0-03 Build a candidate registry of the 20 first-class capability dimensions | implemented | candidate registry with per-dimension status/owner/evidence; `unknown_within_universe=0` |
| 4 | P0-04 Build an unknown-outside-universe discovery mechanism | partial | evidence-driven candidates come from the 12 researched non-goals plus bounded declarations; `undiscovered_space="not_measurable"`; the round does not claim exhaustive discovery |
| 5 | P0-05 Migrate the 12 non-goal items into the unified Gap Registry | implemented | 12 non-goal records migrated by the parallel gap-registry workstream; 51 candidates are consumed by reflection and are never auto-promoted |
| 6 | P0-06 Build the 20-class Acceptance Mismatch Registry | implemented | AM01-AM20 registry with severity/required actions; committed audit `artifacts/acceptance-model-audit-2026-11-16/` |
| 7 | P0-07 Implement AcceptanceModelMatcher and its negative tests | implemented | matcher + 43 committed cases incl. one negative per mismatch class; recall/precision 1.0; `--check` passes |
| 8 | P0-08 Build requested/served model identity auditing | partial | acceptance matcher covers requested/served/unknown/mismatch identity states; provider-side evidence remains the existing 2/4 case coverage; no new provider calls in this round |
| 9 | P1-09 Build cross-function data-flow and alias-analysis capability | not_started | no cross-function/alias analysis was added; explicit backlog |
| 10 | P1-10 Build the integer/string/UAF vulnerability test matrices | not_started | no new vulnerability-class test matrix; explicit backlog |
| 11 | P1-11 Build the Repair Planner and candidate-patch state machine | not_started | no repair-planner capability claimed (contract/state-machine scaffolding is a parallel workstream and does not by itself add repair ability) |
| 12 | P1-12 Build an independent Binary Integrity / Semantic Verifier | not_started | no independent binary verifier added; explicit backlog |
| 13 | P1-13 Enable real CI and produce final-SHA run evidence | partial | a real GitHub-hosted CI run exists on `a8934fe` (portable layer) plus the local nightly gate; this round's new code re-runs CI, but the self-hosted Lima nightly remains `not_run` (no runner provisioned) and is never claimed |
| 14 | P1-14 Build the Reflection Engine and automatic experiment planner | implemented | 12-question contract + deterministic experiment planner; `verified` always false; only `analysis_only/candidate/not_run` |
| 15 | P1-15 Build the Autonomous Repair Audit unified entry point | implemented | `scripts/autonomous_repair_audit.py` static orchestration with injected-runner tests, aggregate JSON and optional evidence bundle |

Remaining backlog after this round: P1-09, P1-10, P1-11, P1-12
(`not_started`); P0-04 and P0-08 (`partial`); self-hosted Lima nightly
`not_run`; international provider matrix `not_satisfied`; platform limits
documented in `docs/acceptance/platform-limits-2026-11-15.md`.

## 8. Verification commands

```bash
.venv/bin/python -m pytest -q -p no:xdist tests/test_reflection_engine.py tests/test_autonomous_repair_audit.py
.venv/bin/python scripts/run_autonomous_reflection.py --check --json
.venv/bin/python scripts/audit_acceptance_models.py --check
.venv/bin/python scripts/autonomous_repair_audit.py --mode static --json
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

Exit codes: `0` pass, `1` a contract/evidence violation, `2` a required input or
script is missing (explicit `not_run`; nothing is fabricated).
