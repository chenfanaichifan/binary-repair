# Non-goal roadmap v2 (2026-11-15)

Machine-readable roadmap for the 12 accepted non-goal ids of the 2026-11-15
release phase. It is the successor of
`docs/acceptance/non-goal-roadmap-2026-11-14.md` and a companion to
`docs/acceptance/non-goals-2026-11-14.md`. It records intent, status and
dependencies only: it is not a capability claim.

The three views must agree 12/12:

- the measured audit `non_goal` id set (current artifacts:
  `artifacts/capability-gap-audit-2026-11-14/`),
- the `non_goals[].id` set in `docs/status/claims.json`,
- the `id` column of the roadmap table below.

`scripts/verify_coverage_gate.py` parses the backticked ids from the roadmap
table (`roadmap_sync`) and fails on any mismatch. Because of that parser
contract, only the 12 ids below appear as non-goal ids in this document: do not
add other roadmap ids to table cells or backticked code spans.

`roadmap_stage` mirrors `docs/status/claims.json` exactly and uses the closed set
`keep-non-goal` / `research` / `productize-next` / `runtime-fallback`.
`target_quarter` and `next_review` are 2027-02-14.

## Phase policy: governance only, no capability graduation

This phase changes governance artifacts only. It does not implement research
capabilities and it does not graduate any non-goal.

```text
no_capability_graduation_this_phase: true
phase: governance-only (2026-11-15)
roadmap_ids: 12
graduated_ids: 0
claims_moved_to_supported: 0
detected_non_goal_input_outcome: analysis_only | not_run | unsupported
verified_or_download_for_non_goal_inputs: false
```

A detected non-goal input keeps its declared enforcement: `analysis_only` (no
candidate), `not_run`/`inconclusive` (no success, no evidence hash), or
`unsupported` (no candidate). It is never `verified_patch` and never
downloadable. The `quarterly_review_status` column records this quarter's
planning state only: `not_started` means no work is scheduled this quarter;
`experiment_planned` means a bounded first experiment is planned to gather
evidence, not that a capability exists or that the id may graduate.

## Field contract

| column | meaning |
|---|---|
| `id` | exact measured audit / claims non-goal id (12/12 set) |
| `roadmap_stage` | `keep-non-goal` (out of product scope), `research` (evidence/feasibility required first), `productize-next` (planned for the next productization cycle), `runtime-fallback` (measured platform capability is unavailable; report unsupported/not_run with the probe reason) |
| `owning_area` | accountable area: `solver` (analyzer/templates/engine), `runtime` (runners/capability probes/execution), `oracle` (verification evidence/gate checks; a dependency for graduation), `process` (release/product scope, matrix/claims governance) |
| `first_experiment` | first concrete, bounded experiment that would produce evidence for this id (or an explicit "none scheduled" for a permanent non-goal) |
| `research_acceptance` | five-step evidence path required to move the id to supported: fixture -> runtime oracle -> evidence profile -> gate check -> claims |
| `target_quarter` | next quarterly decision target (2027-02-14) |
| `dependencies` | systems, evidence and registries the experiment depends on |
| `quarterly_review_status` | this quarter's planning state: `not_started` or `experiment_planned` (never a graduation signal) |
| `next_review` | next scheduled review date for this id (2027-02-14) |

## Roadmap table (12 ids)

| id | roadmap_stage | owning_area | first_experiment | research_acceptance | target_quarter | dependencies | quarterly_review_status | next_review |
|---|---|---|---|---|---|---|---|---|
| `EG-cases-target-not-analyzed` | productize-next | solver | Run the target-strict benchmark baseline on the sprintf hard case with an explicit target and a prototype format-aware sink template; record analysis_only as the current baseline. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: checked-in sprintf fixture; emulated/guest oracle shows original fails and candidate passes; format-aware strict-template profile; required target/gate checks pass; claims/baseline flip to verified for that family. | 2027-02-14 | hard-case fixtures, target-strict benchmark baseline, unified gate profile registry | experiment_planned | 2027-02-14 |
| `NG-ai-leaf-only::ai_assembly_repair` | keep-non-goal | solver | Probe one non-loop assembly leaf block that uses a single import stub and record whether the deterministic structural validator plus whitelist can accept it; no further work scheduled while the stage stays keep-non-goal. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: leaf block fixture with import/stub resolution; native PoC/regression oracle; PoC evidence profile; unified gate check; claims move the id to supported only after all four pass. | 2027-02-14 | AI assembly validator, call whitelist, unified gate, PoC/regression runner | not_started | 2027-02-14 |
| `NG-ai-leaf-only::ai_binary_repair` | keep-non-goal | solver | Probe one non-leaf binary-direct block through the deterministic structural validator and record the rejection reason; no further work scheduled while the stage stays keep-non-goal. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: machine-code leaf-block fixture; native PoC/regression oracle; PoC evidence profile; unified gate check; claims move the id to supported only after all four pass. | 2027-02-14 | AI binary validator, unified gate, PoC/regression runner | not_started | 2027-02-14 |
| `NG-non-goal-1` | research | solver | Build a two-function fixture where the caller allocates the destination and the callee holds a direct copy sink, plus a pointer+offset alias variant; record analysis_only for cross-function/offset alias capacity inference as the baseline. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: cross-function and offset-alias fixtures; runtime oracle proves the inferred capacity and still catches over-estimation; declared capacity evidence profile; required gate check; claims narrow the non-goal to the remaining unrecoverable subset. | 2027-02-14 | capacity analyzer, direct copy sink model, runtime oracle, evidence profile, claims mapping | experiment_planned | 2027-02-14 |
| `NG-non-goal-2` | research | solver | Prototype a format-aware sprintf sink template on the smallest sprintf fixture and record whether a deterministic candidate plus oracle evidence can pass the gate; UAF and loop families are untouched in this experiment. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: per-class sprintf/UAF/integer-loop fixtures; runtime oracle per class; declared profile per class; required gate check per class; claims move only the graduated class to supported. | 2027-02-14 | per-class fixtures, deterministic templates, runtime oracle, evidence profiles | experiment_planned | 2027-02-14 |
| `NG-non-goal-3` | keep-non-goal | process | If the release scope reopens this id: decode one arm32 guard fixture and measure writer/gate-cell feasibility; none scheduled while the stage stays keep-non-goal. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: new-architecture fixture; runtime cell capability probe; writer evidence profile; container/gate cell check; claims add the measured cells to the supported universe. | 2027-02-14 | container/writer backend, repair matrix cell, capability contract, claims governance | not_started | 2027-02-14 |
| `NG-non-goal-4` | keep-non-goal | process | If the release scope reopens this id: parse one fat Mach-O and one 32-bit Mach-O fixture to scope container handling; none scheduled while the stage stays keep-non-goal. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: fat/32-bit Mach-O fixtures; runtime capability matrix; reparse/writer evidence profile; gate cell check; claims add the measured cells to the supported universe. | 2027-02-14 | Mach-O parser/rewriter, repair matrix cell, capability contract, claims governance | not_started | 2027-02-14 |
| `NG-non-goal-5` | runtime-fallback | runtime | Run the runtime capability probe for Windows and non-Mach-O macOS native execution on a capable host and record tier plus explicit reason; on this host it must stay unsupported/not_run. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: native-runner acceptance fixture; measured native runtime oracle; native evidence profile; gate check for the native tier; claims move the id to supported only where the probe reports availability. | 2027-02-14 | runtime capability probe, native runner, unified gate profile | not_started | 2027-02-14 |
| `RG-external-poc::<doc>::pe/arm64` | runtime-fallback | runtime | Run the runtime capability probe for PE/arm64 with external PoC enabled and capture poc_available plus reason; no PE PoC replay is claimed until the probe reports availability. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: PE/arm64 PoC fixture; external-PoC runtime oracle; external-PoC evidence profile; unified gate check; claims move the id to supported only after measured availability. | 2027-02-14 | runtime capability probe, external-PoC runner, PoC evidence profile | not_started | 2027-02-14 |
| `RG-external-poc::<doc>::pe/i386` | runtime-fallback | runtime | Run the runtime capability probe for PE/i386 with external PoC enabled and capture poc_available plus reason; no PE PoC replay is claimed until the probe reports availability. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: PE/i386 PoC fixture; external-PoC runtime oracle; external-PoC evidence profile; unified gate check; claims move the id to supported only after measured availability. | 2027-02-14 | runtime capability probe, external-PoC runner, PoC evidence profile | not_started | 2027-02-14 |
| `RG-external-poc::<doc>::pe/x86_64` | runtime-fallback | runtime | Run the runtime capability probe for PE/x86_64 with external PoC enabled and capture poc_available plus reason; no PE PoC replay is claimed until the probe reports availability. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: PE/x86_64 PoC fixture; external-PoC runtime oracle; external-PoC evidence profile; unified gate check; claims move the id to supported only after measured availability. | 2027-02-14 | runtime capability probe, external-PoC runner, PoC evidence profile | not_started | 2027-02-14 |
| `RG-external-poc::<doc>::macho/x86_64` | runtime-fallback | runtime | Run the runtime capability probe for Mach-O x86_64 with external PoC enabled on a matching macOS x86_64 host (or Rosetta); on an arm64 host it must record unavailable with the host-arch reason and stay not_run. | fixture -> runtime oracle -> evidence profile -> gate check -> claims: Mach-O x86_64 PoC fixture; measured native/emulated oracle; external-PoC evidence profile; unified gate check; claims move the id to supported only on hosts where the probe reports poc_available. | 2027-02-14 | runtime capability probe, native/guest runner, host-dependent claim handling, PoC evidence profile | not_started | 2027-02-14 |

Stage counts: `keep-non-goal` 4, `research` 2, `productize-next` 1,
`runtime-fallback` 5 = **12** ids. Quarterly status counts:
`experiment_planned` 3, `not_started` 9 = **12** ids.

## Governance

### Quarterly review cadence

1. Quarterly reviews run on 2027-02-14, 2027-05-14, 2027-08-14 and
   2027-11-14; the next review for every id is **2027-02-14**
   (`next_review` above). A review may be held earlier but never later than the
   claims `review_by` date.
2. Before each review the audit owner re-runs
   `scripts/audit_capability_coverage.py` and `scripts/verify_coverage_gate.py`
   (static mode in CI, local mode for release). The `roadmap_sync` check must
   report 12/12: measured audit ids == `docs/status/claims.json` `non_goals`
   ids == this table `id` column. Any mismatch blocks release; it is reported,
   never hidden by editing this document or the claims set.
3. For every id the `owning_area` presents the `first_experiment` outcome
   against `research_acceptance`, or states explicitly that no evidence was
   produced. The review updates `quarterly_review_status` (`not_started` ->
   `experiment_planned` once a bounded experiment is scheduled), re-affirms the
   stage, advances it, records `runtime-fallback` as permanent with the measured
   capability reason, or graduates the id through the path below.
4. The release owner updates `docs/status/claims.json` and this document in the
   same change, then re-runs the coverage gate so the three views stay aligned.
   Editing documentation never changes gateway behaviour.

### Graduation path (all five required, in order)

An id moves from non-goal to supported only when every step exists and is
evidence-linked. The 2026-11-15 phase does none of these (governance only):

1. **Fixture** - a checked-in deterministic fixture (original bytes, expected
   behaviour and the PoC/regression input where applicable) that exercises the
   exact family.
2. **Runtime oracle** - measured execution evidence for that fixture
   (native/emulated/guest/PoC). The runtime capability probe must report the
   required tier available with an explicit reason; unavailable evidence stays
   `not_run` and is never faked.
3. **Evidence profile** - the declared acceptance evidence model for the new
   capability is registered (evidence sources plus required checks); oracles are
   never mixed (stack/emulated evidence never verifies non-stack destinations;
   non-stack and PoC-requiring repairs use the external-PoC profile).
4. **Gate check** - the unified verification gate emits and enforces the
   declared required check; a tampered, absent or mismatched packet stays
   rejected/inconclusive. The legacy stack/emulated gate keeps its fail-closed
   manifest behaviour and never judges manifest-bearing requests.
5. **Claims** - only after steps 1-4 pass, the release owner moves the id out
   of `non_goals` (or marks it supported), the audit re-measures it as
   supported, this table row and `docs/acceptance/non-goals-2026-11-14.md` move
   to the supported inventory with evidence links, and the coverage gate
   accepts the measured state.

### Fail-closed rules

A detected non-goal input must never produce `verified_patch` or a download:

1. The claims `enforcement` value is binding: `unsupported` -> unsupported
   outcome and no candidate; `analysis_only` -> no candidate and no download;
   `not_run`/`inconclusive` -> no success, no evidence hash and no download;
   `no verified` -> `verified_patch` is never emitted.
2. Missing runtime/oracle evidence becomes `not_run`/`inconclusive`, never a
   fabricated pass and never a repair failure that hides the gap.
3. A candidate is downloadable only after a deterministic gate
   `success_within_scope` with every required check passed and a complete
   evidence hash; a static-only opt-in candidate stays explicitly unverified.
4. Manifest-bearing requests never use the legacy stack/emulated gate; manifest
   evidence routes only to the unified evidence-profile gate.
5. Capability-limited inputs (PE external PoC, Mach-O x86_64 external PoC on an
   arm64 host, 32-bit Mach-O) report `unavailable`/`not_run` with the measured
   probe reason; they are never simulated.
6. The acceptance-invariant engine and the release gate treat any violation as
   a release blocker; this document and the claims list are the roadmap of
   record, not a permission to claim a capability. The phase flag
   `no_capability_graduation_this_phase=true` above must stay true until a
   later phase records graduation evidence for a specific id.
