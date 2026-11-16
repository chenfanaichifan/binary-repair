# Phase-8D: Open-world discovery and Acceptance 2.0

Status: **implementation and evidence delivered; no capability promotion**.
Base integration commit: `f1bb1f41eba1e0be61be09cea56091e8a03a9896`.
Phase-8C frozen release: `4a7b2355ffc5225d013a777bc7d588abac58f944`
(object still resolves; the original refs were removed during consolidation and
are recorded in the D00 baseline artifact; new frozen tags preserve the objects).

This phase builds measurement and governance around known capability gaps. It
does not add a vulnerability-repair capability, does not promote any capability,
and does not establish hidden generalisation.

## What was delivered

| Workstream | Deliverable | Honest result |
|---|---|---|
| D00 | Phase-8C baseline record and frozen object tags | release/tree/evidence/gate/CI facts recorded; original refs removed by consolidation |
| D01 | 297-unit capability universe with explicit states and legal denominators | 2 independently verified public units, 0 generalized, 0 promoted; outside-catalog unknown is explicitly unmeasurable with null count |
| D02 | Additive Phase-8D gap registry | 8/8 audit gaps recorded as open with evidence/lineage/proposed experiments |
| D03 | Acceptance 2.0 L0-L7 + mutation campaign | 14/14 declared mutations detected; 0 false accepts; 2 inconclusive and 2 not_run remain explicit |
| D04 | heap-malloc ABI root-cause analysis | primary `generator_plan_incorrect` plus `abi_proof_insufficient`; candidate remains rejected |
| D05 | hidden stage attribution | 6/6 runtime samples executed; first blocking stage `detection_missed` for 6/6; 0 candidates, 0 verified |
| D06 | CWE 5.0/Schema 8.0 external snapshot | 984 entries parsed, 232 capability candidates, 15 new ids; no support claim |
| D07 | metamorphic/input-mutation discovery + additive mechanism registry | 4 compiler variants compared (2 engine differences, 2 not_run), 11/11 mutations executed; sample_based remains not_run |
| D08 | experiment/evidence bundle | 10 bounded experiment records, all `promotion_effect=none` |
| D09 | hidden isolation audit | operational checks pass; same-UID/root isolation remains a documented limitation |
| D10 | promotion gate | 4/4 evaluated Phase-8C transitions denied; 0 promotions |

## D01 capability denominators

- Declared dimensions: 20.
- Declared cells: 240.
- Capability units: 297 (20 dimensions + 240 cells + 32 public samples + 2
  hidden aggregate-only units + 3 read-only analysis prototypes).
- State distribution: discovered 98, not_applicable 131, unmeasurable 24,
  unknown 7, independently_verified 2, candidate_generated 1, analysis_only 32,
  unsupported 2, generalized 0, promoted 0, not_run 0.
- Public runtime eligible denominator: 24, with 2 independently verified
  fixtures and rate `2/24 = 0.0833`.
- Hidden runtime denominator: 6, with 0 independently verified and rate `0/6`.
- Outside-catalog unknown count is `null`; it is not zero.

## D04 root cause

The deterministic heap-malloc candidate redirects the vulnerable call to an
injected executable cave. The candidate's cave ABI check is ok, but the
generator's plan declares the pre-existing function range as
`abi_blocks[0]` and binds ABI evidence to that function instead of the injected
cave. The independent verifier also has a conservative static limitation around
RIP-relative GOT/PLT calls and tail calls. Root causes are recorded as
`generator_plan_incorrect` (primary), `abi_proof_insufficient` (primary) and
`verifier_rule_incorrect` (contributing). No verifier rule was relaxed; the
candidate remains unverified.

## D05 hidden failure attribution

The private lane was executed; only anonymous counts are public. All six runtime
samples execute and reach recovery/parsing, but the engine reports
`detection.not_observed` for all six, so `detection_missed` is the first blocking
stage. This is a measurement result, not a hidden generalisation claim. No
hidden sample id, path, bytes or raw report is in the public aggregate.

## D06/D07 discovery results

The external scanner is versioned and offline by default. It parses CWE 5.0
entries from a committed normalized snapshot, records schema/version drift, maps
232 entries to capability groups, and marks the remaining 752 unmapped. The
earlier audit's approximate 16 new entries is not asserted: the measured count is
15 relative to the recorded prior snapshot.

The metamorphic run compares four same-source compiler variants and records two
engine differences and two not_run/unsupported outcomes; 11/11 input mutations
execute through the real guest oracle. The additive mechanism registry reports
6/7 mechanisms with real evidence (3 integrated, 3 standalone); sample-based
discovery remains not_run.

## D10 promotion

The promotion gate evaluates public verified, hidden analysis-only, withdrawn
heap-malloc and hidden zero-candidate states. Every attempted transition is
denied by missing evidence: no hidden verified sample, no holdout/generalization
evidence, no independent approval, and one withdrawn internal claim. No
capability is promoted.

## Limitations

- This phase does not prove arbitrary-binary repair or semantic equivalence.
- Acceptance mutation coverage is finite; correct-but-new-layout False Reject
  remains incompletely measured.
- Hidden isolation is operational, not cryptographic; same-UID/root readers can
  read the private root.
- The D04 candidate remains rejected; the generator plan/ABI evidence issue is
  not yet fixed.
- hidden generalisation, cross-compiler support, whole-program proof and
  Phase-8E/9-16 are not claimed.
