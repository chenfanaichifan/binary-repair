# Phase-8D final mainline evidence (2026-11-17)

This evidence-only branch records the final mainline gate and CI for the
Phase-8D release. The gated tree is unchanged.

- final gated SHA: `d37bfad81f39c2bfa3fc90babed7301d6244446d`
- final gated tree: `2708ad28b44aac4abb8ead991fdd7cf192d77596`
- local frozen-tree nightly gate: **13/13 required checks passed**, 0 failed,
  0 skipped, 0 unavailable
- mainline policy: `require`; `origin/workbench-v3` at start/end was
  `d37bfad...`; `mainline_unchanged=true`
- final CI: run `43907137267` (CI) success; run `43907136876` (Ubuntu
  verification) success on `d37bfad...`
- Phase-8D integration SHA: `996060d0b47374e9ad69e4fee5a3de4a11d164c1`
  (ancestor of d37); its own CI/Ubuntu runs `43905664704` / `43905664754`
  also succeeded. The later d37 commits are provider/stability work; the
  final mainline gate above includes them.
- Phase-8D release tag: `release-2026-11-17-phase8d` on `996060d...`;
  this final mainline tag is `release-2026-11-17-phase8d-final`.

## Frozen baselines

- Phase-8C release object `4a7b2355ffc5225d013a777bc7d588abac58f944`,
  evidence object `ec503e4b1df53ad39fa836bd34d93a18564d78f9`.
- Frozen Phase-8C tags: `phase8d-frozen-phase8c-release`,
  `phase8d-frozen-phase8c-evidence`.
- D00 baseline: `artifacts/phase8d-baseline-2026-11-17/baseline.json`.
- Earlier Phase-8D side-branch evidence: `release/2026-11-17-phase8d-evidence`
  (`bdd3f840...`), gate bundle `artifacts/release-gate-2026-11-17-phase8d/`.

## Phase-8D measured results (no promotion)

- capability universe: 297 units; 2 independently verified public fixture
  units; 0 generalized; 0 promoted; outside-catalog unknown is
  unmeasurable/null.
- gap registry: 8 open audit gaps; none closed by code change alone.
- Acceptance 2.0: 18 cases; 14/14 declared mutations detected; 0 false
  accepts; 0 false rejects in declared fixtures; 2 not_run, 2 inconclusive.
- heap-malloc: candidate remains rejected; primary
  `generator_plan_incorrect` and `abi_proof_insufficient`; contributing
  `verifier_rule_incorrect`; no verifier rule relaxed.
- hidden lane: 6 runtime samples executed; first blocking stage
  `detection_missed` for 6/6; 0 candidates; 0 independently verified; only
  anonymous aggregate published.
- external knowledge: CWE 5.0 snapshot, 984 entries, 232 mapped candidates,
  15 new, 752 unmapped; no support claim.
- discovery: 4 compiler variants compared, 2 engine differences, 2
  not_run/unsupported; 11/11 input mutations executed; sample_based remains
  not_run.
- hidden isolation: operational checks pass; same-UID/root readability remains
  a limitation; not cryptographic isolation.
- promotion gate: 4/4 evaluated transitions denied; promoted_count=0.
- experiment bundle: 10 records, all `promotion_effect=none`.

## Claims/refs note

`docs/status/claims.json` on d37 records the earlier gated code CI
`43900916188` / Ubuntu `43900916201` on `78edb972...`; the Z and d37 runs above
are later real runs. This addendum is the final-SHA CI/gate record and does not
transfer an old run between SHAs.

## Limitations

- No capability promotion, hidden generalisation, arbitrary-binary repair,
  whole-program semantic equivalence, or second-compiler verification.
- Acceptance mutation coverage is finite; correct-new-layout False Reject is
  incompletely measured.
- Hidden isolation is operational, not cryptographic.
- Self-hosted Lima nightly is not_run; the local frozen-tree nightly gate is
  separate.
- Phase-8E/9-16 are not implemented.
