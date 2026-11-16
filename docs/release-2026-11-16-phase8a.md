# Release 2026-11-16-phase8a: repair readiness foundation

Phase-8A is a measurement and verification foundation, not a new
vulnerability-repair capability.  It adds a 30-item measured readiness audit, a
ground-truth benchmark manifest and deterministic runner, an independent
verifier MVP, six new JSON contracts, four new acceptance mismatch classes, and
non-gating shadow checks.  No `verified` state is upgraded.

## Frozen release identity

- base phase-7 mainline: `2bfa112591614aa39d4d6b55ad9bb962b9718e7c`
- phase-8A feature commits: `3ec09b1` (foundation), `c1be712` (readiness
  shallow-checkout compatibility), `be9d10a` (reflection regeneration)
- integrated operator commits included on the gated tree: `ca6f5d8`
  (P5-P9 features), `2cad986` (CI full-history checkout), `bd9cbf6` (P5-P9
  validation docs)
- **frozen / gated SHA: `bd9cbf63c395dfa98cb16845bee3f817805adaf5`**
- git tree: `c3edf88bb465b937bb1f3abba908e571d2a4f8b0`
- branch at gate: `feature/phase8-repair-readiness`, clean tree
- `release_freeze`: requested == frozen == release SHA, **mainline unchanged
  during the gate** (`bd9cbf6` start/end), exit 0.

## Local frozen-tree nightly gate (authoritative host measurement)

`release_freeze.py --mode nightly --sha bd9cbf6 --evidence-dir /tmp/...` ->
**13/13 required checks passed, violations=[]**, gate elapsed 834.5 s, full
pytest 703.0 s, real Lima capture 39.4 s, provenance builder
`local-frozen-tree`, guest available, `limactl 2.3.0`.

Checks: release-tree-identity; static coverage gate (open=[], dynamic=6
visible/allowed in static mode); claims/measurement diff (gap 62, open=[],
mitigated residual `RG-runtime-evidence...`, claims non-goals=12);
acceptance contract; local coverage gate (open=[], dynamic=0, universe
unknown=0, 240 cells); meta-audit (28 scenarios, 1.0/1.0); acceptance
invariants (9 packets, 12 limitations); universe-unknown-zero; provenance
complete; provider matrix (12 cases); provider coverage (11 rows, 2
providers/4 models, identity policy, statistics, cost/seed unavailable);
real Lima capture; full pytest.

## Real GitHub-hosted CI on the frozen SHA

- `CI` run 43687651314 -> **success**: test, coverage-gate (including the new
  non-gating Phase-8 readiness/benchmark-manifest/verifier-selftest shadow
  steps), release-gate-pr, browser-e2e, and portable release-gate-hosted all
  success; self-hosted nightly and release-drift skipped/inert.
- `Ubuntu verification` run 43687651300 -> **success**.
- self-hosted Lima nightly: **not_run** (no runner provisioned; signoff
  `docs/release/CI-SIGNOFF-2026-11-15.md`), never claimed as CI.
- Details: `ci-run.json`.

## Phase-8A evidence

- **Readiness audit** (`artifacts/phase8-readiness-2026-11-16/`, 30 G01-G30
  items): measured **13 implemented / 7 partial / 5 missing / 1 not_run /
  4 non_goal**, `capability_claims=[]`.  Implemented means code+test(+artifact)
  probe evidence, not a capability promotion; G29 hidden benchmark is
  `not_run` (`hidden_available=false`).  Every item carries evidence refs,
  blocker, next action and `capability_claim:false`.
- **Ground-truth benchmark v1** (`benchmark/phase8-v1/manifest.json`): 12 real
  fixture samples (dev 8 / validation 4), hashes/PoC/oracle/reference-fix
  validated, no hidden split fabricated.  Deterministic runner results
  (`artifacts/phase8-benchmark-2026-11-16/results.json`, independent verifier
  auto-discovered): 12 executed, detected 4, candidate produced 2, deterministic
  claims 2, independent verified **0**, false-verified **0**, 2 deterministic
  claims **withdrawn** after the independent verifier rejected resized/cave
  candidates.  This is an honest engine/verifier semantic gap, not a pass.
- **Independent verifier MVP** (`app/services/independent_verifier.py`,
  `scripts/verify_repair.py`): 8 required checks recomputed from raw bytes
  (identity, container, action replay, target scope, ABI, independent oracle,
  evidence completeness, independence); generator verdicts are never read and
  generator evidence is excluded; decisions are fail-closed; hermetic selftest
  11/11 schema-validated.  The committed
  `artifacts/phase8-verification-2026-11-16/report.json` is an explicitly
  labelled schema-conformance sample with decision `rejected`, not repair
  evidence.
- **Contracts**: 12 total (six new: binary-target, vulnerability-finding,
  root-cause, verification, benchmark-sample, patch-candidate), 12 valid + 12
  invalid fixtures, committed-artifact integration (20 dims/64 gaps/95
  reflections/12 benchmark samples/verification sample validated).
- **Acceptance**: AM21-AM24 added (repair-scope, semantic-scope,
  oracle-quality, benchmark-version), matrix 52 cases, 24/24 classes,
  recall/precision 1.0; meta-audit 28 scenarios.
- **Unified audit**: `autonomous_repair_audit.py --mode full` = 7 required + 3
  advisory shadow checks passed, `not_run=[]`; shadow checks never count as
  pass and never change the 7-required exit semantics.
- **Integration correction**: the committed coverage-closure
  `acceptance.json` checksum was stale; only the `SHA256SUMS` line was corrected
  to the actual committed bytes (no acceptance content changed).  Universe,
  gap, reflection and provider artifacts were regenerated when their inputs
  changed.

## Mainline intermediate bundle caveat

The mainline tree also contains an earlier intermediate
`artifacts/release-gate-2026-11-16-phase8a/` bundle committed while integrating
operator features; it is a historical checkpoint for `3ec09b1`, not this
release.  The authoritative bundle for the frozen `bd9cbf6` tree is on
`release/2026-11-16-phase8a-evidence` (tag
`release-2026-11-16-phase8a-evidence`) and is bound by its SHA256SUMS and the
release tag `release-2026-11-16-phase8a`.

## Explicit non-claims and remaining work

No new vulnerability-repair capability is claimed; no verified state or
capability promotion occurred; no independent verification of a real repaired
binary was achieved; no hidden benchmark/generalization is claimed.  The
remaining Phase-8B/8C/8D work is listed in
`docs/operations/phase8-roadmap-2026-11-16.md`: interprocedural data-flow/
alias/lifetime, integer/string/UAF analysis, repair strategy planner/candidate
lifecycle, semantic verifier beyond the MVP, external knowledge/mutation/
metamorphic discovery, and a real hidden benchmark.  Self-hosted Lima nightly
and the international provider matrix remain `not_run`/unsatisfied.

Any later mainline commit invalidates this frozen evidence; re-freeze and
re-gate before citing it.
