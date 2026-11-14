# Coverage-closure acceptance evidence (2026-11-14, safe-default policy)

End-to-end acceptance for the two repaired classes plus the phase-2
target-scope ownership proof.  Raw output: `acceptance.json`, produced by
`capture_acceptance.py` (run from the repo root with `.venv/bin/python`; the
real PoC differentials execute in the Lima VM `binaryrepair`).

## Safe-default policy (phase 3)

- Whole-image repair is opt-in: the capacity/heap product paths below pass
  `allow_whole_image=True` and the packets record `scope.target_policy=whole_image`;
  without a target and without that opt-in the same fixture/manifest returns
  **analysis_only**, no candidate and no download (`target_policy=analysis_only`).
- The ownership path (`target="heap_bad"`) keeps `target_policy=target_scoped`
  and a required `patch.target_scope` check; a wrong target fails closed.

## Capacity-check rewrite (marcx) — profile `native_poc_rewrite`

- review API `POST /api/binary/repair-review` with `poc_manifest` + `allow_whole_image=1`:
  HTTP 200, `decision.success=true`, `success_within_scope`, 21/21 required
  checks passed, profile `native_poc_rewrite`, tier `emulated_run`;
- patched sha256 `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`;
- pipeline with manifest + opt-in: `verified_patch` (`whole_image`); without manifest:
  `not_verified`/`inconclusive`, no candidate.

## Heap-destination guard — profile `native_poc`

- fixture `fixtures/hard-cases/vuln-heap-malloc-x86_64.elf`
  (`0f65a2d2...`); with real `heap-malloc.json`: `verified_patch`, 19/19
  checks, `poc_status=pass`, candidate
  `ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73`;
- safe-default control (no target/opt-in): analysis_only, no candidate.

## Target-scoped ownership proof (phase-2 P0)

- `repair_any(heap fixture, target="heap_bad", require_target=True,
  poc_manifest=heap-malloc.json)` => `verified_patch`, candidate
  `ea222605...`, 20/20 checks with required `patch.target_scope=passed`
  (`target=heap_bad scope=[0x401130,0x40116c) actions=1`), scope carried in
  `packet.scope.target` and hashed into `report_sha256`;
- wrong target control `target="main"` (no patchable sink inside): analysis_only,
  no candidate, no download;
- `--require-target` without a target => `unsupported` (strict mode).

## Reproduce

```bash
.venv/bin/python artifacts/coverage-closure-2026-11-14/capture_acceptance.py
.venv/bin/python scripts/repair_binary.py fixtures/hard-cases/vuln-heap-malloc-x86_64.elf /tmp/heap.fixed \
  --target heap_bad --require-target --poc fixtures/poc/heap-malloc.json --json
.venv/bin/python -m pytest -q tests/test_capacity_repair.py tests/test_binary_pipeline_capacity.py \
  tests/test_repair_heap.py tests/test_code_cave.py tests/test_gate_profiles.py \
  tests/test_target_scope.py tests/test_legacy_manifest_gate.py tests/test_runtime_capabilities.py \
  tests/test_binary_review_api.py
```

The missing-evidence controls are part of the script: every path must stay
`not_verified`/inconclusive with no candidate when its manifest is absent, and a
wrong/absent target must fail closed without a whole-image candidate.  The
deterministic gate remains the only acceptance authority.
