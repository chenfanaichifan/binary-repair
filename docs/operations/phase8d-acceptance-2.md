# Phase-8D Acceptance 2.0 (D03)

Status: additive audit implementation. Historical AM01-AM28 artifacts and
claims are read-only inputs and are not rewritten.

## Scope

`app/services/acceptance_2.py` implements eight fail-closed acceptance layers
and a mutation campaign over an enriched task/evidence envelope:

- L0 input integrity: required sections, identity hashes, registry/benchmark
  version.
- L1 structural integrity: target identity, scope policy, and the rule that
  `analysis_only` can never be verified.
- L2 patch integrity: candidate identity, plan presence for layout changes,
  byte-exact replay, resolved target scope, associated-change authorization.
- L3 ABI/control flow: derived ABI blocks, resolved/allowed branch and call
  targets, executable cave when present.
- L4 vulnerability elimination: independently executed oracle, observed
  original vulnerability, candidate elimination, no generator self-verdict.
- L5 semantic preservation: executed bounded semantic cases, preservation
  result, no full-equivalence overclaim.
- L6 regression/robustness: regression and boundary cases, reproducible
  environment, minimum repeats.
- L7 evidence/independence/non-promotion: evidence ids/digests/modes,
  author/reviewer independence, not_run/inconclusive/analysis_only never
  promoted, claims stay in scope, canonical rule-registry digest.

A decision is `verified` only when every required rule passed and the registry
digest/version is canonical. Any failed required rule yields `rejected`;
missing evidence yields `not_run`; an explicit inconclusive state yields
`inconclusive`; analysis-only scope yields `analysis_only`. The last three are
never `verified`.

## Rule versioning and historical replay

The registry is versioned (`2.0.0`), carries a canonical digest, and records
its L0-L7 rules. `replay_historical` evaluates an old-version case as
`not_run` with `upgraded=false`; legacy AM01-AM28 facts are read from the
historical report for reference only. No historical case or claim is promoted
to the new registry.

## Mutation campaign

`scripts/audit_acceptance_2.py` builds a deterministic 18-case matrix and runs
14 mutations across rule, evidence, scope, oracle, layout, regression and state
families. The rule mutation disables a required rule and must be caught by the
registry-digest rule. Other mutations remove/tamper evidence, inflate scope,
remove the plan/ABI/regression, use a generator verdict, claim verified from
not_run/inconclusive/analysis_only, or use self review.

The report records `detection_rate`, `false_accepts`, per-mutation expected and
detected rules, False Accept/False Reject lists, and residual False Reject gaps.
A finite mutation campaign does not prove the rule set complete.

## Evidence artifact

`artifacts/phase8d-acceptance-2-2026-11-17/` contains:

- `report.json`: registry, layers, per-case results, mutation results,
  historical replay, honest gaps and limitations.
- `cases.json`: deterministic input matrix.
- `README.md`, `SHA256SUMS`.

`generated_at` is fixed to `2026-11-17T00:00:00Z`; the audit is offline and
deterministic. `--write`, `--check` and `--json` are provided. The artifact is
validated against `contracts/acceptance-2.schema.json` by the audit and tests.

## Measured result (reference worktree)

- Cases: 18; matched 18; False Accepts 0; False Rejects 0.
- Mutation campaign: 14/14 detected, detection rate 1.0, false accepts 0.
- Positive same-length/new-layout/cave cases verified.
- 2 not_run, 2 inconclusive, 1 analysis_only; none verified.
- Historical replay: not_run, upgraded=false.
- False Reject gaps documented: correct new layout without derivable ABI stays
  `not_run`; correct candidate with explicit inconclusive state stays
  `inconclusive`; whole-image semantic equivalence is not modelled as verified.

## Integration notes for Lead

- This change is additive; no existing acceptance model, AM01-AM28 registry,
  62-case artifact or claim was modified.
- The new contract is registered in `scripts/check_contract_schemas.py`
  (20 contracts total) with valid/invalid fixtures and SHA256SUMS; the audit
  also validates the report with jsonschema directly.
- The repository worktree also contains unrelated Phase-8D files; no file
  outside this D03 scope was edited.
