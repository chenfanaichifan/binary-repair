# Release 2026-11-15-autonomy: phase-7 autonomy foundation + frozen-tree gate

This release adds the **autonomy foundation**: acceptance intelligence, a
20-dimension capability universe registry, a unified gap registry with
discovery mechanisms, an evidence-backed reflection/experiment engine, canonical
repair states and six JSON contracts, and a unified autonomous audit entry.

It deliberately does **not** add or upgrade any vulnerability-repair capability:
no new repair path, no elevation of any candidate to `verified`, and no
automatic capability promotion. See
`docs/operations/autonomy-roadmap-2026-11-16.md` for the 15-item backlog status
(8 implemented / 3 partial / 4 not_started).

## Frozen release identity

- frozen mainline SHA: `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`
- git tree: `65a9df826cd775135a54e1ff3a68c346f72acfc0`
- mainline pinned: start `2bfa112591614aa39d4d6b55ad9bb962b9718e7c` / end
  `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`, `mainline_unchanged=True`
- clean tree at gate start: `True`

## Local frozen-tree nightly gate (authoritative host measurement)

- command: `release_freeze.py --mode nightly --sha 2bfa112591614aa39d4d6b55ad9bb962b9718e7c` wrapping
  `release_gate.py --nightly --release-sha 2bfa112591614aa39d4d6b55ad9bb962b9718e7c --json
  --evidence-out artifacts/release-gate-2026-11-15-autonomy/gate.json`
- result: **exit 0, 13/13
  required checks passed, violations=[]**, gate elapsed
  1092.1s, frozen_sha == release_sha
- checks: release-tree-identity; static coverage gate (open=[], dynamic=6
  visible/allowed in static mode); claims/measurement diff (mitigated residual
  `['RG-runtime-evidence::elf/x86_64/64/little::native_run']` printed); acceptance contract
  (capacity=1/heap=1/target_scoped=1/controls=2); local coverage gate
  (open=[], dynamic=0, universe unknown=0, 240 cells); meta-audit (26
  scenarios, recall/precision 1.0); acceptance invariants (9 packets);
  universe-unknown-zero (240 cells, unknown=0); provenance-complete
  (builder=local-frozen-tree, guest available, 9 acceptance subjects);
  provider matrix (12 cases); provider coverage (11 rows, 2 providers/4
  models); nightly real-Lima capture (rows=11 providers_completed_12case=2 models_completed_12case=4 identity_policy=True statistics=True cost_available=False seed_available=False); full pytest
  (906.3s serial). Lima `limactl version 2.3.0` with VM
  config digest `ec70b504451fc3dc1b6d6f915ae9d80b4dfd4ce1e0a5e14ebeb574d9c3d22b2a`.

## Real GitHub-hosted CI on the frozen SHA

- `CI` run 43637263062 -> **success**: `test`, `coverage-gate`,
  `release-gate-pr`, `browser-e2e`, `release-gate-hosted` (portable PR gate +
  full non-browser pytest, evidence artifact) all success; self-hosted
  `release-nightly-gate` and `release-drift` skipped (inert/schedule).
- `Ubuntu verification` run 43637263068 -> **success** (full non-browser suite,
  1842 passed earlier in the phase; final run green).
- Self-hosted Lima nightly: **not_run** (no runner provisioned; signoff
  `docs/release/CI-SIGNOFF-2026-11-15.md`), never claimed as CI. See
  `ci-run.json`.

## Autonomy foundation evidence (all committed on this SHA)

- Acceptance intelligence: A01-A08 dimensions, AM01-AM20 mismatch registry,
  43-case deterministic audit matrix, 20/20 classes detected, recall=precision
  1.0; served-model-only/unknown/mismatch can never verify; meta-audit 26.
- Capability universe: exact D01-D20 registry, 240/240 cells mapped,
  12 claims non-goals as bounded out-of-universe candidates,
  unknown-within-universe=0, `undiscovered_space="not_measurable"` (no invented
  number).
- Gap registry/discovery: 64 records (12 non-goals migrated + 1 mitigated +
  51 candidates); mechanisms knowledge/failure-driven/differential run,
  mutation/metamorphic/sample-based/knowledge-source-scan explicit
  `not_run`; candidates can never auto-promote.
- Reflection/experiment: 12-question contract, 91 records (12 candidates,
  73 analysis_only, 6 not_run), `verified_true_count=0`, infrastructure
  failures cannot become capability gaps.
- Contracts: 6 JSON Schemas validated against fixtures and committed artifacts
  (20/20 dimensions, 64/64 gaps, 91/91 reflections); canonical repair state
  machine with evidence+independence gates.
- Unified audit: `autonomous_repair_audit.py --mode full` 7/7 passed.

## Evidence layers (do not conflate)

1. local frozen-tree nightly gate: host-specific measurement for this SHA;
2. GitHub-hosted portable CI: real CI runs above, PR layer + full test suite;
3. self-hosted Lima nightly: not_run;
4. browser: local macOS evidence plus hosted `browser-e2e` success; Linux skip
   is not a pass.

## Remaining gaps (explicit, not release defects)

- 4 backlog items not started: cross-function data-flow/alias analysis,
  integer/string/UAF vulnerability matrix, Repair Planner/candidate state
  machine beyond vocabulary, independent Binary Integrity/Semantic Verifier.
  No repair capability claim is made for them.
- P0-04 partial: out-of-universe discovery is bounded by the 12 migrated
  non-goals; undiscovered space is not measurable.
- P0-08 partial: identity audit is in the acceptance matcher; provider matrix
  remains 2 providers/4 models, international matrix not_satisfied.
- self-hosted Lima nightly not_run; platform limits (32-bit Mach-O, PE external
  PoC, Rosetta function-level only) unchanged.
- Any later mainline commit invalidates this frozen evidence; re-freeze and
  re-gate before claiming it.

## Verification addendum

- `verify_provenance.py --dir artifacts/release-gate-2026-11-15-autonomy` -> PASS
- `verify_evidence_branch.py --gated-sha 2bfa112 --evidence-ref HEAD` -> PASS
  (gated SHA ancestor of mainline; gate/freeze SHA pinned; only evidence/docs
  paths changed) - recorded before the tag push; the tag/drift verification is
  repeated after the tags are published.
- `release_drift_check.py --tag release-2026-11-15-autonomy` is run after tag
  publication; pre-tag resolution failure is expected and not evidence.
