# Phase-8D final release evidence (2026-11-17)

This evidence-only branch records the final Phase-8D gate, CI and frozen
baseline facts. The gated mainline tree is unchanged.

- Phase-8D gated SHA: `996060d0b47374e9ad69e4fee5a3de4a11d164c1`
- gated tree: `fa13afd230d59efb76027847b2b70543cdec34f0`
- local frozen-tree nightly gate: **13/13 required checks passed**, 0 failed,
  0 skipped, 0 unavailable; `gate.ok=true`, `clean_tree=true`
- gate command used `--expected-mainline ignore --offline` because the public
  `workbench-v3` ref advanced during the gate. This is explicit: the gate is a
  local frozen-tree gate, not a simultaneous mainline-equality claim.
- `workbench-v3` at gate completion: `d37bfad81f39c2bfa3fc90babed7301d6244446d`;
  Z is an ancestor of d37 (`git merge-base --is-ancestor` verified). The
  mainline contains Phase-8D plus later provider/stability commits.
- final CI on Z: run `43905664704` (CI) success and run `43905664754`
  (Ubuntu verification) success.
- claims records the earlier docs commit CI `43900916188` / Ubuntu
  `43900916201` on `78edb972...`; Z is a docs/evidence-only commit after that.
  Both are real runs; the Z run above is the final-SHA CI and is recorded here.
- self-hosted Lima nightly: `not_run` (no self-hosted runner); the local
  nightly gate above is separate evidence. Signoff:
  `docs/operations/phase8c-ci-signoff.md`.

## Frozen Phase-8C baseline

- Phase-8C release object: `4a7b2355ffc5225d013a777bc7d588abac58f944`
- Phase-8C evidence object: `ec503e4b1df53ad39fa836bd34d93a18564d78f9`
- The original Phase-8C refs were removed by consolidation; Phase-8D adds
  frozen object tags `phase8d-frozen-phase8c-release` and
  `phase8d-frozen-phase8c-evidence`.
- D00 baseline artifact:
  `artifacts/phase8d-baseline-2026-11-17/baseline.json` (Phase-8C gate 13/13,
  CI 43748886046/43748886289, Phase-8B 2/2 reproduction).

## Final Phase-8D evidence

- capability universe: 297 units; 2 independently verified public fixture
  units; 0 generalized/promoted; outside-catalog unknown is unmeasurable/null.
- gap registry: 8 open audit gaps, none closed by code change alone.
- Acceptance 2.0: 18 cases, 14/14 declared mutations detected, 0 false accepts,
  0 false rejects in the declared fixtures, 2 not_run and 2 inconclusive
  cases retained.
- heap-malloc: deterministic candidate remains rejected; primary root causes
  `generator_plan_incorrect` and `abi_proof_insufficient`, contributing
  `verifier_rule_incorrect`; no verifier rule was relaxed.
- hidden lane: 6 runtime samples executed; first blocking stage
  `detection_missed` for 6/6; 0 candidates, 0 independently verified; only
  anonymous aggregate is published.
- external knowledge: CWE 5.0 snapshot, 984 entries, 232 mapped candidates,
  15 new relative to the recorded prior snapshot, 752 unmapped; no support
  claim.
- discovery: 4 compiler variants compared (2 engine differences, 2
  not_run/unsupported), 11/11 input mutations executed; additive mechanism
  registry has 3 integrated + 3 standalone mechanisms and sample_based remains
  not_run.
- hidden isolation: operational checks pass; same-UID/root readability remains
  an explicit limitation, not cryptographic isolation.
- promotion: 4/4 evaluated transitions denied; promoted_count=0.
- experiment bundle: 10 records, all `promotion_effect=none`.

## Limitations

- No capability promotion, hidden generalisation, arbitrary-binary repair,
  whole-program semantic equivalence, or second-compiler verification is
  claimed.
- The local gate ran with `--offline --expected-mainline ignore` because the
  public mainline advanced during the run; the gate's own 13/13 result is
  retained, but the simultaneous mainline-equality check was not available.
- Acceptance mutation coverage is finite; correct-but-new-layout False Reject
  remains incompletely measured.
- Hidden isolation remains operational, not cryptographic.
- Phase-8E/9-16 are not implemented.
