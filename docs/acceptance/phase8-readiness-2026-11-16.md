# Phase-8A repair readiness baseline (2026-11-16)

Read-only audit of the 30 Phase-8 user requirements (G01-G30) against the
current tree (generated_from_sha `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`).  The audit
probes files, modules/tests and committed evidence only.  It never runs repair,
providers/AI, a hidden benchmark or a PoC, and it makes **no new repair
capability claim and no verified-state upgrade**.  The machine-readable
artifact `artifacts/phase8-readiness-2026-11-16/readiness.json` is authoritative
for per-item evidence refs, blockers and next actions.

## 1. What is really implemented

Implemented means code probe + test probe (+ declared artifact/ground truth)
all hit.  Current implemented baseline (13/30):
G02, G07, G08, G13, G19, G20, G21, G22, G23, G24, G25, G26, G27.

- G02 dimension discovery registry (20 first-level dimensions, legacy-11 map,
  committed dimension-registry artifact);
- G07 local binary corpus builder/analyzer (+ committed corpus metadata);
- G08 unified GapRecord with deterministic ids/lineage (+ gap-registry
  artifact);
- G19 Repair Strategy Registry (STRATEGY_PROFILES / EVIDENCE_PROFILES);
- G20 Repair Planner (structured RepairSpec + planning artifact);
- G21 Candidate Manager (provider proposals are staged input, never results);
- G26 Autonomous Experiment Engine (reflection engine + bounded audit artifact);
- G27 Acceptance Oracle Self-Audit (A01-A08 / AM01-AM20 matcher + 43-case
  audit matrix + meta-audit).

All other capabilities below are partial, missing, not_run or explicit
non-goals; none of them is a repair capability added by this audit.

## 2. Which items exist only as contract/registry/documentation

Partial items whose current evidence is essentially registry/contract/document
only (no end-to-end capability): G03 (out-of-universe space tracked only as
`undiscovered_space=not_measurable`), G30 (repair states + JSON contracts only;
no audited promotion workflow).  G18/G10/G11/G14 are explicit claims non-goals,
not contracts.  In every partial case the blocker column names the missing
deliverable.

## 3. Code exists but no test

None of the 30 items is "code without test": every implemented item has a test
ref and every partial item with code also has a test probe hit (the gap is
capability/breadth or evidence, see blockers).  A future code-only addition
will be capped at partial by the audit's hard evidence rule.

## 4. Tests exist but no ground truth

- G21 (candidate manager): code + test boundary proof, ground truth not
  applicable (no binary outcome is claimed).
- G09/G12/G15 (partial analysis items): tests exist for the same-function /
  duplicated-range-check / direct-call subsets only; there is no cross-function,
  truncation/signedness or indirect-call ground truth yet.
- G13/G22/G23/G24/G25 are now implemented by the audit's code+test+artifact
  rule after the Lead corrected the stale committed
  `artifacts/coverage-closure-2026-11-14/SHA256SUMS` (see the correction note
  in the release report).  The independent verifier
  (`app/services/independent_verifier.py`, `scripts/verify_repair.py`,
  `tests/test_independent_verifier.py`) is still a hermetic self-test/contract
  MVP: it strengthens G23/G24 evidence but does not create a real
  repaired-binary verification run.  The Phase-8 benchmark records two engine
  claims withdrawn by this stricter verifier; no verified repair is claimed.
- External acceptance/behavioral evidence remains narrower than the items'
  full scope; see each item's blocker and the benchmark results.

## 5. Reusable repair capabilities

Existing reusable paths (no new capability added here): string
guard/copy repair (G13), strategy/evidence registry (G19), RepairSpec planner
(G20), candidate staging boundary (G21), deterministic writers for
x86/i386/arm64 and PE/Mach-O repair actions (G22), binary integrity + unified
semantic gate (G23/G24), PoC/regression runner (G25), acceptance oracle
(G27).  These are reusable only within their measured scope; the audit does
not upgrade any verified state.

## 6. What must be rebuilt / newly developed

Missing or partial items with no implementation path:
- discovery engines: G04 (combination), G05 (mutation), G06 (metamorphic);
- analysis depth: G09 (cross-function data-flow), G12 (general integer
  truncation/signedness), G15 (indirect calls), G16 (path-sensitive), G17
  (concurrency);
- knowledge/completeness: G01 (external knowledge corpus), G03
  (out-of-universe unknown inventory);
- evaluation/governance: G28 (multi-model 4/4), G30 (promotion workflow).
G29 (hidden benchmark) is externally unavailable and must stay not_run; the
hidden set must not be fabricated (the new benchmark builder keeps
`hidden_available=false` and `hidden_commitment_sha256=null`).

## 7. Highest priority (P0)

Remaining P0 work: G09 (cross-function data-flow), G12 (general integer
analysis), G15 (indirect calls); G10/G11 are explicit non-goals and G13/G22/
G23/G24/G25 are implemented to their measured probes.  The analysis foundation
(G09 -> G10/G11/G12/G16 -> G17) is the prerequisite for any new repair class;
the strategy/planner/application and verifier paths are present but remain
limited to their declared scope.

## 8. Dependency order

1. Knowledge/corpus: G01 -> G02 -> G03; G07 feeds G05/G06/G29.
2. Discovery/dedup: G01/G07 -> G08 -> G05/G06; G02 -> G04 -> G05.
3. Analysis: G09 -> G10/G11/G12/G16 -> G17; G13 independently.
4. Repair engine: G19 -> G20 -> G21 -> G22.
5. Verification/autonomy: G22 -> G23 -> G24 -> G25 -> G26 -> G27.
6. Evaluation/governance: G27 -> G28 -> G29; G27/G28 -> G30.

## 9. Status table (authoritative artifact: readiness.json)

| id | title | phase | priority | status | blocker |
|---|---|---|---|---|---|
| G01 | External Knowledge Source Scanner | 8A | P1 | partial | external NVD corpus is not provisioned; the knowledge_source_scan discovery mechanism is declared not_run in this tree |
| G02 | Dimension Discovery Engine | 8A | P1 | implemented | - |
| G03 | Unknown-space tracking beyond 240 cells | 8A | P1 | partial | space outside the 240 measured cells is only tracked as undiscovered_space=not_measurable; no enumerated unknown inventory |
| G04 | Cross-capability Combination Discovery | 8A | P2 | missing | no combination-discovery engine exists; the gap registry only has single-mechanism adapters |
| G05 | Mutation-based Discovery | 8A | P2 | missing | mutation discovery is declared NOT RUN: no mutation engine/corpus exists in this tree |
| G06 | Metamorphic Discovery | 8A | P2 | missing | metamorphic discovery is declared NOT RUN: no relation engine exists in this tree |
| G07 | External Binary Corpus | 8A | P1 | implemented | - |
| G08 | Deduplication and lineage for findings vs old gaps | 8A | P1 | implemented | - |
| G09 | Cross-function Data-Flow | 8B | P0 | partial | analyzer scope is same-function only: cross-function allocations and argument flows fail closed and are not tracked |
| G10 | Pointer Alias | 8B | P0 | non_goal | explicit claims non-goal; no repair capability is claimed |
| G11 | Global variable / struct capacity inference | 8B | P0 | non_goal | explicit claims non-goal; no repair capability is claimed |
| G12 | Integer vulnerability analysis (range/overflow/truncation/signedness) | 8B | P0 | partial | only the duplicated-range-check capacity rewrite is deterministic; general truncation/signedness analysis has no path |
| G13 | String vulnerability analysis | 8B | P0 | implemented | - |
| G14 | UAF lifetime | 8B | P1 | non_goal | explicit claims non-goal; no repair capability is claimed |
| G15 | Indirect call analysis | 8B | P0 | partial | only direct calls already made by the target are resolvable; indirect calls are explicitly forbidden, not analyzed |
| G16 | Path-sensitive analysis | 8B | P1 | missing | no path-sensitive analysis module exists; the analyzer is linear basic-block based |
| G17 | Concurrency vulnerability analysis | 8B | P1 | missing | no concurrency/race analysis module exists in this tree |
| G18 | More binary format/architecture coverage | 8B | P2 | non_goal | explicit claims non-goal; no repair capability is claimed |
| G19 | Repair Strategy Registry | 8C | P0 | implemented | - |
| G20 | Repair Planner | 8C | P0 | implemented | - |
| G21 | Candidate Manager | 8C | P1 | implemented | - |
| G22 | Patch Application Engine | 8C | P0 | implemented | - |
| G23 | Binary Integrity Verifier | 8D | P0 | implemented | - |
| G24 | Semantic Verifier | 8D | P0 | implemented | - |
| G25 | Regression Engine | 8D | P0 | implemented | - |
| G26 | Autonomous Experiment Engine | 8D | P1 | implemented | - |
| G27 | Acceptance Oracle Self-Audit | 8D | P1 | implemented | - |
| G28 | Multi-model Evaluation | 8E | P1 | partial | only 2 of 4 target providers have real recorded evidence; the other slots are not measured |
| G29 | Hidden Benchmark | 8E | P2 | not_run | hidden benchmark unavailable (hidden_available=false); the registry must never fabricate a hidden run |
| G30 | Capability Promotion Governance | 8E | P1 | partial | only the state machine and JSON contracts exist; an end-to-end promotion workflow with independent review is not audited |

## 10. Honesty statement

This round **adds no new repair capability and does not upgrade any `verified`
state**.  30/30 items are classified only by the read-only probes above; every
item carries `capability_claim: false`, a blocker (except clean implemented
items) and a concrete next action.  The audit is deterministic and regenerable:
`python scripts/audit_repair_readiness.py --write` then `--check`.

Phase-8 integration note: peers have already landed
`scripts/verify_repair.py`, `app/services/independent_verifier.py`,
`scripts/build_ground_truth_benchmark.py`, six new contracts and the
`benchmark/phase8-v1` manifest (with `hidden_available=false`); this baseline
references them at run time.  If further peer files land after this generation,
the Lead must re-run `--write` so readiness.json/README.md/docs reflect the final
tree (the committed `--check` otherwise fails closed).
