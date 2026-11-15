# Phase-8A repair readiness baseline (2026-11-16)

Read-only evidence audit of the 30 Phase-8 user requirements (G01-G30). It does not run repair, providers, benchmarks or PoCs, and it claims no new repair capability and upgrades no verified state.

- generated_from_sha: `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`
- total items: **30**
- status counts: implemented=13, partial=7, missing=5, not_run=1, non_goal=4

| id | title | phase | priority | status | code | test | artifact | ground truth | blocker |
|---|---|---|---|---|---|---|---|---|---|
| G01 | External Knowledge Source Scanner | 8A | P1 | partial | yes | yes | no | present | external NVD corpus is not provisioned; the knowledge_source_scan discovery mechanism is declared not_run in this tree |
| G02 | Dimension Discovery Engine | 8A | P1 | implemented | yes | yes | yes | present | - |
| G03 | Unknown-space tracking beyond 240 cells | 8A | P1 | partial | yes | yes | yes | present | space outside the 240 measured cells is only tracked as undiscovered_space=not_measurable; no enumerated unknown inventory |
| G04 | Cross-capability Combination Discovery | 8A | P2 | missing | no | no | no | not_applicable | no combination-discovery engine exists; the gap registry only has single-mechanism adapters |
| G05 | Mutation-based Discovery | 8A | P2 | missing | no | no | no | not_applicable | mutation discovery is declared NOT RUN: no mutation engine/corpus exists in this tree |
| G06 | Metamorphic Discovery | 8A | P2 | missing | no | no | no | not_applicable | metamorphic discovery is declared NOT RUN: no relation engine exists in this tree |
| G07 | External Binary Corpus | 8A | P1 | implemented | yes | yes | no | present | - |
| G08 | Deduplication and lineage for findings vs old gaps | 8A | P1 | implemented | yes | yes | yes | present | - |
| G09 | Cross-function Data-Flow | 8B | P0 | partial | yes | yes | no | not_applicable | analyzer scope is same-function only: cross-function allocations and argument flows fail closed and are not tracked |
| G10 | Pointer Alias | 8B | P0 | non_goal | yes | yes | no | not_applicable | explicit claims non-goal; no repair capability is claimed |
| G11 | Global variable / struct capacity inference | 8B | P0 | non_goal | yes | yes | no | not_applicable | explicit claims non-goal; no repair capability is claimed |
| G12 | Integer vulnerability analysis (range/overflow/truncation/signedness) | 8B | P0 | partial | yes | yes | no | not_applicable | only the duplicated-range-check capacity rewrite is deterministic; general truncation/signedness analysis has no path |
| G13 | String vulnerability analysis | 8B | P0 | implemented | yes | yes | yes | present | - |
| G14 | UAF lifetime | 8B | P1 | non_goal | no | no | no | not_applicable | explicit claims non-goal; no repair capability is claimed |
| G15 | Indirect call analysis | 8B | P0 | partial | yes | yes | no | not_applicable | only direct calls already made by the target are resolvable; indirect calls are explicitly forbidden, not analyzed |
| G16 | Path-sensitive analysis | 8B | P1 | missing | no | no | no | not_applicable | no path-sensitive analysis module exists; the analyzer is linear basic-block based |
| G17 | Concurrency vulnerability analysis | 8B | P1 | missing | no | no | no | not_applicable | no concurrency/race analysis module exists in this tree |
| G18 | More binary format/architecture coverage | 8B | P2 | non_goal | yes | yes | no | present | explicit claims non-goal; no repair capability is claimed |
| G19 | Repair Strategy Registry | 8C | P0 | implemented | yes | yes | no | present | - |
| G20 | Repair Planner | 8C | P0 | implemented | yes | yes | yes | present | - |
| G21 | Candidate Manager | 8C | P1 | implemented | yes | yes | no | not_applicable | - |
| G22 | Patch Application Engine | 8C | P0 | implemented | yes | yes | yes | present | - |
| G23 | Binary Integrity Verifier | 8D | P0 | implemented | yes | yes | yes | present | - |
| G24 | Semantic Verifier | 8D | P0 | implemented | yes | yes | yes | present | - |
| G25 | Regression Engine | 8D | P0 | implemented | yes | yes | yes | present | - |
| G26 | Autonomous Experiment Engine | 8D | P1 | implemented | yes | yes | yes | present | - |
| G27 | Acceptance Oracle Self-Audit | 8D | P1 | implemented | yes | yes | yes | present | - |
| G28 | Multi-model Evaluation | 8E | P1 | partial | yes | yes | yes | present | only 2 of 4 target providers have real recorded evidence; the other slots are not measured |
| G29 | Hidden Benchmark | 8E | P2 | not_run | yes | yes | no | not_applicable | hidden benchmark unavailable (hidden_available=false); the registry must never fabricate a hidden run |
| G30 | Capability Promotion Governance | 8E | P1 | partial | yes | yes | no | present | only the state machine and JSON contracts exist; an end-to-end promotion workflow with independent review is not audited |

Hard evidence rule: implemented requires code probe + test probe (+ artifact/ground truth when declared); contract/registry/documentation only caps an item at partial; absent evidence is missing; an unavailable external capability is not_run; the 12 claims non-goals are non_goal.

Regenerate with `python scripts/audit_repair_readiness.py --write`; verify with `--check` (deterministic recomputation + SHA256SUMS).
