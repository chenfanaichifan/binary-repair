# Phase-8B B5/B6/B7: pipeline patch plan, plan-aware gate and real independent verification (2026-11-16)

This note records the Phase-8B implementation and the real verification result for
the two Phase-8A benchmark disagreements. It is evidence documentation, not a
release claim: only the two samples below were independently verified, within the
declared target scope, with an executed external PoC oracle.

## 1. Why the plan exists

The B1 baseline (`artifacts/phase8b-baseline-2026-11-16/`) showed the two
disagreements were evidence-exchange gaps, not observed candidate defects:

* the stack guard candidate is resized by a cave/`PT_LOAD` append and a call
  redirect; the verifier received no resolved scope, no plan and no ABI block;
* the capacity candidate has an associated `.rodata` message rewrite outside
  `report.actions`; the pipeline gate checked only `report.actions` and the
  verifier recomputed the raw diff without any associated-change channel.

The patch plan (`contracts/patch-plan.schema.json`) is the structural exchange
contract between the pipeline and the independent verifier.

## 2. Pipeline implementation (`app/services/binary_pipeline.py`)

`finish_candidate` now builds `report.patch_plan` for immediate/guard/capacity/AI
candidates from the actual original/candidate bytes:

* `target_sha256` / `candidate_sha256` bind the plan to the exact bytes;
* `target_scope` is the resolved producer scope (`resolve_function_scope` for a
  symbol/function, or the explicit `va`/`end` range) with
  `scope_policy=target_scoped_associated` when associated metadata/cave changes
  are declared;
* operations replay the candidate exactly:
  * equal-size candidates: contiguous byte writes (`reviewed_site`,
    `header_update`, `rodata_message`, `relocation`), e.g. the capacity rewrite
    (offset 8409, 16 bytes) and the associated `.rodata` message write
    (offset 538624, 49-byte action, 12 changed bytes) with a hash-bound
    `authorization_ref`;
  * guard candidates: ELF header/program-header writes + the reviewed-site
    call redirect (full 5-byte `E8 rel32` instruction, site VA from the engine
    action) + one declared insertion for the appended `PT_LOAD`/cave region.
    The latest plan for the stack sample is 9 operations (7 header updates,
    1 reviewed-site redirect, 1 3926-byte insert) with an executable cave
    (`va=0x10cb000,size=38,method=new-pt-load`);
* `cave` is derived from the candidate's new executable segment (ELF PT_LOAD,
  PE section or Mach-O segment); non-executable/unmapped caves fail the gate;
* `abi_blocks` are derived from the real function range and the candidate bytes:
  stack = 44-byte `vuln_copy` block, heap = 2864-byte reviewed function range from
  the capacity analysis function starts (the fixture is stripped, so the range is
  the reviewed containing function, not a symbol guess); the evidence sha256 is
  computed over the candidate bytes;
* `oracle` records the PoC manifest digest, runner and tier;
* plans are validated against `contracts/patch-plan.schema.json` (jsonschema);
  an invalid plan is not emitted (old gate path, no layout verification claim).

`report.patch_plan` and the plan are passed to `unified_verification.build`.

## 3. Plan-aware unified gate (`app/services/unified_verification.py`)

When a plan is present, the existing `patch.rewrite` and `patch.target_scope`
checks are extended (no new release-gate required check; no-plan behavior and
check ids are unchanged):

* `patch.rewrite` replays the plan deterministically against the original bytes
  and requires byte equality with the candidate, so every raw-diff byte must be
  declared (undeclared bytes fail); cave executable mapping is checked in the
  candidate container; associated reasons require an `authorization_ref`;
  tampered plans fail;
* `patch.target_scope` requires reviewed-site operations inside the resolved
  `[va,end)` and only allows associated changes (rodata/header/relocation/cave)
  under `target_scoped_associated` with an authorization reference.

The pipeline gate for both samples passes these checks (`layout_status=passed`).

## 4. Runner exchange and evidence (`scripts/run_repair_benchmark.py`)

For each executed sample the runner builds exchanged metadata with:

* resolved target scope (`va`/`end`/`name` from the pipeline report),
* the patch plan (oracle hash rewritten to the supplied manifest file digest for
  the verifier),
* actions + message actions, ABI block derived from the plan function range,
* capacity `.rodata` authorization records for the heap sample,
* the PoC manifest path and a real `run_poc` callback.

It prefers the module API (`app/services/independent_verifier.py`), which now
accepts `patch_plan`, and uses the CLI only when it supports `--plan` and
executes the oracle. Every sample directory under
`artifacts/phase8b-benchmark-2026-11-16/samples/<sample_id>/` persists
`original.bin`, `candidate.bin`, `outcome.json`, `metadata.json`, `plan.json` and
`verifier-report.json`; `SHA256SUMS` covers all of them. `results.json` adds
`patch_plan_sha256`, `verifier_id`, `oracle_status`, `layout_status`,
`real_verification` and the ABI block list per sample; `false_verified` is 0 and
`not_run` is never relabelled as verified.

## 5. Real result (reference host, darwin/arm64 + Lima guest)

Command: `python scripts/run_repair_benchmark.py --verifier auto` (deterministic
engine, no AI, no network; independent verifier module; PoC oracle executed via
`run_poc`/limactl).

| sample | deterministic | independent verifier | verified |
|---|---|---|---|
| stack-strcpy-x86_64 | verified_patch | verified (identity/container/layout-plan/action-replay/target-scope/ABI/runtime-oracle/evidence/independence all passed) | yes |
| heap-capacity-x86_64 | verified_patch | verified (same checks; ABI from plan `reviewed-function` 2864-byte range) | yes |
| other 10 samples | analysis-only / no candidate | not_run (no candidate to verify) | no |

Summary: 12 samples, 12 executed, 0 not_run, 2 candidate-produced, 2 integrity-ok,
2 deterministic-verified, **2 independently verified**, **false_verified 0**,
`verification_disagreements=0`.

The independent verifier reports for both samples show
`runtime-oracle=passed` with `runner=limactl`, `tier=emulated_run` and the
external PoC manifest in `oracle_evidence`; the `layout-plan` and `abi` checks
pass from the exchanged plan.

## 6. Commands and checks

```
python -m pytest -q tests/test_binary_pipeline_plan.py \
  tests/test_ground_truth_benchmark.py tests/test_binary_pipeline_v5.py \
  tests/test_binary_pipeline_capacity.py tests/test_binary_verification.py
python scripts/run_repair_benchmark.py --verifier auto
python scripts/run_repair_benchmark.py --verifier auto --json
python scripts/check_language_policy.py
python scripts/build_ground_truth_benchmark.py --check
```

## 7. Limitations

* Only the two samples above are independently verified. The other 10 samples
  are analysis-only/no-candidate (`independent_verified=not_run`), not failures.
* The heap ABI block uses the reviewed capacity analysis function range because
  the fixture is stripped; it is a real containing function range, not a
  symbol-backed function.
* The stack cave/segment layout is specific to the current deterministic writer
  (`new-pt-load`); plans are regenerated from candidate bytes and are not
  hand-written.
* Plan replay is a structural/byte-level contract; it does not prove semantic
  equivalence of the repaired function beyond the declared target scope.
* The Phase-8A artifact (`artifacts/phase8-benchmark-2026-11-16/`) is left
  unchanged; the Phase-8B artifact is new.
