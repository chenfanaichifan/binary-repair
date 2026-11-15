# Phase-8B contract notes (patch plan, layout verification, benchmark authority)

Status: contract-layer notes for Phase-8B B3. They summarize the contracts the
independent verifier / runner exchange needs, derived from the B1 baseline
audit (`artifacts/phase8b-baseline-2026-11-16/`) and the B2 plans. They do not
implement verifier or pipeline behavior; task-35/task-36 consume these fields.

Boundary: this round is contract and acceptance governance only. No new repair
capability is claimed and no `verified` disposition is auto-promoted.

## 1. Contract inventory after B3

| Contract | Change |
|---|---|
| `contracts/patch-plan.schema.json` | new (13th contract) |
| `contracts/verification.schema.json` | compatible extension: optional `patch_plan_sha256`, `oracle_evidence`, `layout_evidence`; `layout-plan` check id; `target_scoped_associated` scope policy |
| `contracts/benchmark-sample.schema.json` | compatible extension: optional `authority` with `authorized_changes` |
| `contracts/acceptance.schema.json` | extended to AM01-AM28 (`mismatch_classes` minItems 20 / maxItems 28); AM01-AM24 pattern and semantics stay compatible |
| other 9 contracts | unchanged |

Validation: `python scripts/check_contract_schemas.py --check` runs 13 schema
self-checks, 13 valid + 13 invalid fixtures, committed-artifact integration,
cross-field semantics and a deterministic `SHA256SUMS` (39 entries = 13 schema
files + 26 fixtures). It passes with jsonschema and with the fallback validator.

## 2. Patch plan (`contracts/patch-plan.schema.json`)

Purpose: exchange the facts the deterministic pipeline actually produced so the
verifier can independently replay them instead of guessing from raw byte diffs
(V8B-03, V8B-06).

Required fields: `schema_version`=1, `candidate_id`, `target_sha256`,
`candidate_sha256`, `strategy`, `scope_policy`, `target_scope`, `operations`,
`cave`, `relocations`, `abi_blocks`, `oracle`, `limitations`. Optional identity
fields: `plan_id`, `generator_id`, `original_sha256`.

- `scope_policy` / `target_scope.policy`: `target_scoped`,
  `target_scoped_associated`, `whole_image`, `analysis_only`; both must agree.
- `operations[]`: `kind` in `write`/`insert`/`replace`; `original_offset`,
  `candidate_offset` (needed for insert/replace), `size`, `before_hex`,
  `after_hex`, optional `site_va`; `reason` in `reviewed_site`, `guard_cave`,
  `rodata_message`, `header_update`, `relocation`; optional
  `authorization_ref`.
- `cave` (or null): `va`, `size`, `executable`, `method`; required for
  `insert`/`guard_cave` operations and must be executable.
- `relocations[]` and `abi_blocks[]` carry derived relocation/ABI exchange.
- `oracle` (or null): `manifest_sha256`, `runner`, `tier`, optional `status`
  and `evidence_sha256`.

Checker-enforced cross-field rules: insert/replace need `candidate_offset`;
`write`/`replace` hex lengths equal `size`; `after_hex` always equals `size`;
insert has empty `before_hex`; operation kind `insert` or reason `guard_cave`
requires an executable cave; `target_scoped*` requires a `va`/`end` range and
reviewed operations must have `site_va` inside it; associated reasons require
an `authorization_ref`. `whole_image` verification eligibility is decided by the
verification contract, not by the plan.

## 3. Verification extension

The old required fields and `schema_version=1` are unchanged, so the committed
phase-8A verification sample keeps validating. New optional fields:

- `patch_plan_sha256`: digest of the exchanged plan.
- `oracle_evidence`: `manifest_sha256`, `runner`, `tier`,
  `status` (`executed`/`not_run`/`unavailable`), optional `evidence_sha256`,
  optional `expected` with `expected_original`/`expected_candidate`.
- `layout_evidence`: `patch_plan_sha256`, `replay_ok`, `changed_ranges[]`,
  `cave`, `associated_changes[]` (kind/offset/size/section/authorization_ref),
  optional `abi_blocks[]`.

`checks[]` accepts the new `layout-plan` check id. Cross-field rules enforced by
the checker:

1. `decision=verified` still requires `independence.ok=true`,
   `generator_evidence_excluded=true`, at least one passed independent check and
   no required failed/not_run check.
2. When `layout_evidence` is present and the decision is `verified`: replay must
   be declared successful, a `layout-plan` check must be passed, a passed
   independent oracle check must exist, and every associated change must carry
   an `authorization_ref`.
3. `oracle_evidence.status=executed` requires a runnable tier and an
   `evidence_sha256`; a `not_run`/`unavailable` oracle can never accompany a
   `verified` decision.

## 4. Benchmark sample authority

`contracts/benchmark-sample.schema.json` keeps all old required fields, so the
12 committed phase-8A samples validate unchanged. New optional `authority`:
`scope_policy` plus `authorized_changes[]` with `kind`
(`rodata_message`/`header_update`/`relocation`), `reason`,
`authorization_ref`, and a locator (`file_offset`+`size` or `va`+`end`), optional
`section`. Semantics: a `target_scoped_associated` sample must declare at least
one authorized change; every authorized change needs an authorization reference
and a locator.

## 5. Acceptance AM25-AM28 (B3)

Added to `app/services/acceptance_models.py`; AM01-AM24 ids/semantics are
unchanged. The committed audit matrix is now 62 cases (9 positive, 53
negative), covers 28/28 classes, recall 1.0/precision 1.0.

- AM25 `candidate_layout_mismatch`: exchange plan/layout mismatch (missing
  layout, replay not successful, candidate sha mismatch, missing operation
  range, cave/relocation mismatch).
- AM26 `unauthorized_associated_change`: associated change without
  authorization reference or outside the authorized range.
- AM27 `abi_evidence_incomplete`: executable modification without derivable
  ABI evidence (missing/indifferent block, non-derived evidence).
- AM28 `oracle_metadata_incomplete`: missing runner/tier/manifest sha/expected
  fields or a non-executed oracle.

Meta-audit is now 30 scenarios (adds layout replay mismatch and unauthorized
associated change masquerades); recall/precision stay 1.0.

## 6. Verification commands

    .venv/bin/python scripts/check_contract_schemas.py --check
    .venv/bin/python scripts/check_contract_schemas.py --no-jsonschema --check
    .venv/bin/python scripts/audit_acceptance_models.py --write
    .venv/bin/python scripts/audit_acceptance_models.py --check
    .venv/bin/python scripts/meta_audit.py --json
    .venv/bin/python -m pytest -q tests/test_contract_schemas.py tests/test_acceptance_models.py tests/test_meta_audit.py
    .venv/bin/python scripts/check_language_policy.py

## 7. Acceptance contract alignment (resolved)

`contracts/acceptance.schema.json` now encodes the AM01-AM28 registry:

- `mismatch_classes` accepts 20-28 classes; the id pattern and the
  `dimensions[].mismatch_ids` / `match_result.mismatches` patterns accept
  `AM28` and reject `AM29`;
- the committed 24-class `acceptance.valid.json` fixture remains valid, so
  legacy AM01-AM24 fixtures keep passing unchanged;
- contract tests prove a payload built from the runtime
  `ACCEPTANCE_DIMENSIONS`/`MISMATCH_RULES` (full AM01-AM28) validates against
  the schema, and that the legacy 24-class fixture still validates.

Residual note: `scripts/check_contract_schemas.py` keeps its committed-fixture
semantic assertion for the legacy 24-class sample, so the fixture file stays a
stable legacy conformance sample; schema-level representation of AM25-AM28 is
complete. Expanding the conformance fixture to 28 classes is optional future
work and does not change the runtime acceptance engine.

## 8. Other open items (outside this task's write scope)
- Verifier/pipeline behavior changes are task-35/task-36 scope: plan replay,
  oracle injection, derived ABI, layout scope rules, persisted artifacts.
- Dynamic oracle/ABI results remain host-dependent and must be reported as
  not_run when unavailable; no contract here allows faking a pass.
