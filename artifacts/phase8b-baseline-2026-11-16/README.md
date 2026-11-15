# Phase-8B B1/B2 verifier disagreement baseline (2026-11-16)

Read-only reproduction of the two Phase-8A benchmark disagreements (`stack-strcpy-x86_64`, `heap-capacity-x86_64`) using the deterministic `repair_any` engine and the current independent verifier (module API + CLI). No AI, no network, no production-code change.

- base_sha: `bd9cbf63c395dfa98cb16845bee3f817805adaf5`
- manifest: `benchmark/phase8-v1/manifest.json` (sha256 `fd3b80a61c9bae963794220f2b6d546db6048e736f7a3d2dd41b184a4ef855a9`)
- benchmark results: `artifacts/phase8-benchmark-2026-11-16/results.json` (sha256 `cdf7420c4b808c0e26c3cc19996cbced5d0b7e640f97f4b3b2045d6b6cffa0f4`)
- candidate bytes are evidence-only outputs of the deterministic engine; they are not executed outside the sandbox and are not a correctness or verified claim.

## Samples

| sample | candidate sha256 | matches benchmark | CLI decision | module+oracle decision | classified issue |
|---|---|---|---|---|---|
| stack-strcpy-x86_64 | `1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4` | yes | rejected | rejected | target-scope exchange missing (symbol not resolved); resized cave candidate rejected by rewrite-only action replay; ABI and patch-plan evidence missing; oracle CLI wiring missing |
| heap-capacity-x86_64 | `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2` | yes | rejected | rejected | associated .rodata message action is not exchanged/modeled; verifier target-scope rejects the raw-diff action even though the pipeline gate only checked report.actions; ABI and patch-plan evidence missing; oracle CLI wiring missing |

## Gap registry (V8B-01..V8B-07)

| id | title | severity | measured |
|---|---|---|---|
| V8B-01 | Oracle exchange: runner CLI --poc is not injected as run_poc | critical | {"cli_runtime_oracle": "not_run", "module_with_run_poc_runtime_oracle": "passed"} |
| V8B-02 | Resolved target scope is not exchanged (symbol not turned into va/end) | critical | {"heap_target_scope": "failed (associated change, separate gap)", "stack_after_resolved_scope_exchange": "passed", "stack_baseline_target_scope": "not_run"} |
| V8B-03 | Resized/cave candidates are rejected by rewrite-only action replay | critical | {"heap_action_replay": "passed", "heap_candidate_resized": false, "stack_action_replay": "failed", "stack_candidate_resized": true} |
| V8B-04 | Associated .rodata message action is not modeled; gate target-scope only sees report.actions | high | {"capacity_message_actions": 1, "pipeline_actions": 1, "pipeline_gate": "success_within_scope", "raw_diff_actions": 2, "verifier_target_scope": "failed"} |
| V8B-05 | ABI evidence is not derived or exchanged | high | {"baseline_abi": "not_run", "derived_abi_block": "produced from resolved code range"} |
| V8B-06 | Patch-plan contract is missing | high | {"patch_plan_contract": "absent", "verifier_plan_check": "absent"} |
| V8B-07 | Runner does not save/exchange candidate bytes, plan or verifier report | high | {"artifact_files": ["results.json", "README.md", "SHA256SUMS"], "candidate_saved": false, "plan_saved": false, "verifier_report_saved": false} |

## Files

- `phase8b-baseline-audit.json` - full measured baseline (inputs, hashes, outcome, actions, scope, oracle, verifier results, root causes)
- `phase8b-verifier-gap-registry.json` - V8B-01..V8B-07 with evidence, required fixes and acceptance criteria
- `disagreement-*/` - original/candidate bytes, outcome/metadata/verifier report and a read-only `reproduce.sh`
- `../../docs/acceptance/phase8b-disagreement-analysis.md` - decision analysis (hypotheses A/B/C, experiments, candidate vs verifier vs exchange responsibilities)
- `../../docs/operations/phase8b-implementation-plan.md` - B2 implementation plan
- `../../docs/operations/phase8b-test-plan.md` - B2 test plan

`SHA256SUMS` covers every data file in this directory and the three analysis/plan docs (docs entries are relative, `../../docs/...`).
