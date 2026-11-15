# Phase-8B B4/B8 verifier notes: layout-aware independent verification

Status: implementation notes for task-35 (B4/B8). Scope: `verification_semantics`
(pure plan replay/scope/ABI derivation), the independent verifier's layout-aware
checks, the `verify_repair.py` CLI (`--plan`, executed `--poc`) and tests. No
contracts, pipeline, benchmark, readiness, acceptance, CI, claims or release-gate
files were changed.

## 1. What the B1 baseline required

The B1 audit (`artifacts/phase8b-baseline-2026-11-16/`) reproduced two Phase-8A
verifier disagreements with the deterministic engine: a resized stack candidate
(cave + inserted bytes, candidate sha `1bc66b2e...`) and a same-size heap
candidate whose `.rodata` message alignment was an associated change outside the
declared action list (candidate sha `93e27f2f...`). Root causes V8B-01..V8B-07
were confirmed: CLI oracle not wired, resolved scope not exchanged, resized
candidates blanket-rejected, associated changes unmodelled, ABI evidence not
derived, no patch-plan contract, and no persisted candidate/plan/report.

The fix is evidence exchange plus fail-closed replay, not looser acceptance:

* a patch plan (`contracts/patch-plan.schema.json`) declares ordered operations,
  cave, relocations, ABI blocks, oracle metadata and limitations;
* the verifier replays the plan from the raw original bytes and requires exact
  candidate equality; undeclared raw differences still fail;
* associated changes are explicitly declared with an `authorization_ref` and
  section/bounds checks; `whole_image` is never verifiable in Phase-8B;
* ABI evidence is derived from declared blocks, exchanged metadata, a real
  symbol-backed function or guard-cave bytes; unavailable derivation is
  `not_run`, never a pass;
* the verifier executes `app.services.poc_runner.run_poc` itself (CLI `--poc`),
  validates runner/tier/sha/status, and records `oracle_evidence`.

## 2. Check semantics (all required unless noted)

| check | status meanings |
|---|---|
| identity | sha256/bytes agreement, candidate != original |
| container | re-parse agreement and metadata format/arch/bits/endian |
| layout-plan | plan replay equals candidate; required when a plan is supplied or the candidate is resized; absent plan on equal-size is `not_run` with `required=false` |
| action-replay | declared plan covers every changed byte; resized without a plan is `not_run` (no blanket rejection) |
| target-scope | reviewed site inside resolved target function; associated changes only for `target_scoped_associated` + `authorization_ref`; scope escapes fail; cave executable and redirected from the reviewed site; unresolved scope is `not_run` |
| abi | derived block/function (plan -> metadata -> symbol-backed function -> cave bytes) passes `repair.abi.check_block`; no derivable block is `not_run` |
| runtime-oracle | the verifier executes the real PoC runner (or an injected one in tests); declared-but-unexecuted oracle fails; sha/runner/tier/status and plan oracle metadata are cross-checked |
| evidence-completeness | generator/reference-only evidence is rejected; a declared but unexecuted oracle cannot verify |
| independence | generator id distinct from `independent-verifier/1`, generator verdict never read |

Decision rules: `rejected` if any required check failed; `not_run` if required
checks cannot run; `verified` only when every required check passed, independence
is ok, and an independent oracle passed. `layout_evidence`/`oracle_evidence` are
emitted when applicable and validated against the verification schema; a report
with layout evidence can only be `verified` when `replay_ok=true` and the
layout-plan check passed. `B1` stack integration reaches `verified`; the heap
candidate reaches `not_run` until the pipeline exchanges ABI block/function
evidence (the 16-byte site range is deliberately not guessed as a function).

## 3. CLI

```
python scripts/verify_repair.py --original PATH --candidate PATH \
    --metadata PATH [--plan PATH] [--poc PATH] [--json]
python scripts/verify_repair.py --selftest [--json]
```

`--plan` exchanges the patch plan; `--poc` is executed through the real
`poc_runner.run_poc` (no generator oracle evidence is read). Exit codes: `0`
verified/selftest pass, `1` rejected/inconclusive/tamper, `2` usage/unsupported
target/unavailable. `--selftest` is hermetic (synthetic bytes, injected
container/ABI/oracle stubs, no real binary) and now covers 19 cases including
valid resized plan, resized without plan, plan tamper, authorized/unauthorized
associated `.rodata` change, whole-image refusal, plan-oracle mismatch and ABI
fatal; every generated report is validated with jsonschema against
`contracts/verification.schema.json` (fallback when jsonschema is unavailable).

## 4. Verification

```
python -m pytest -q -p no:xdist tests/test_verification_semantics.py tests/test_independent_verifier.py
python scripts/verify_repair.py --selftest --json
python scripts/check_language_policy.py
```

The tests are offline: no network, no AI/provider, no native execution. Real B1
artifact bytes (`original.elf`/`candidate.bin`) are read-only fixtures for replay
and scope integration; the oracle in those tests is injected with recorded B1
facts. A real Lima/native oracle execution remains host-dependent and is never
fabricated in unit tests.

## 5. Limitations / next exchange

* Heap B1 candidate: layout/associated/scope checks now pass; `abi=not_run`
  because the stripped fixture has no symbol-backed function and the plan carries
  no `abi_blocks`. Pipeline/runner exchange of `abi_blocks`/function range is
  required before it can be verified; the verifier does not guess.
* `whole_image` plans are rejected in Phase-8B; no whole-image verified claim.
* Dynamic oracle evidence depends on the host runner; `not_run` is recorded
  truthfully rather than replaced with a fabricated pass.
* Contract `verification.schema.json` optional fields (`patch_plan_sha256`,
  `layout_evidence`, `oracle_evidence`) are consumed exactly; contracts remain
  legacy-owned and were not modified here.
