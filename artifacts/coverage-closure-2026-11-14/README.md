# Coverage-closure acceptance evidence (2026-11-14)

Two acceptance paths were re-run end-to-end after the capability-gap audit and
the capacity/heap integration.  Raw output: `acceptance.json` (produced by
`capture_acceptance.py`, run from the repo root with `.venv/bin/python`).

## Capacity-check rewrite (marcx) — reviewed profile `native_poc_rewrite`

- review API `POST /api/binary/repair-review` with `poc_manifest`:
  HTTP 200, `decision.success=true`, outcome `success_within_scope`, 21/21
  required checks passed, 0 not_run, profile `native_poc_rewrite`, tier
  `emulated_run`;
- patched sha256 `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`;
- pipeline with manifest: `verified_patch`, `strategy=capacity`,
  `mode=capacity-check`, `poc_status=pass`;
- pipeline without manifest: `not_verified`/`inconclusive`, no candidate
  (`fail-closed`).

## Heap-destination guard — profile `native_poc`

- fixture `fixtures/hard-cases/vuln-heap-malloc-x86_64.elf`
  (`0f65a2d2ffe1ebf91f717d5edc78928cb8ee219e3f73e623b256f87bdcc4381f`);
- with real `fixtures/poc/heap-malloc.json`: `verified_patch`, 19/19 checks,
  `poc_status=pass`, candidate sha256
  `ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73`;
- without manifest: `not_verified`/`inconclusive`, no candidate.

## Reproduce

```bash
.venv/bin/python artifacts/coverage-closure-2026-11-14/capture_acceptance.py
.venv/bin/python -m pytest -q tests/test_capacity_repair.py \
  tests/test_binary_pipeline_capacity.py tests/test_repair_heap.py \
  tests/test_code_cave.py tests/test_gate_profiles.py tests/test_binary_review_api.py
```

The missing-evidence controls are part of the script: both paths must stay
`not_verified`/inconclusive and must not offer a candidate when the manifest is
absent.  The deterministic gate remains the only acceptance authority; the AI
review path is not involved in these runs.

Self-discovery audit (separate, bounded, no network):
`artifacts/capability-gap-audit-2026-11-14/` (66 gap rows: 51 closed, 3 open,
1 mitigated, 11 non-goal, 0 high-severity open).
