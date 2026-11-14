# Provider coverage - machine-readable provider/model evidence (2026-11-14)

Generated deterministically by `scripts/build_provider_coverage.py` from the
committed source artifacts in this repository. No provider calls were made
to build it.

- generated_at: `2026-11-14T13:08:04Z` (artifacts/provider-matrix-2026-11-14/summary.json#generated_at;
  deterministic source-derived timestamp, not build wall clock)
- source digest: `df2f11b0b90864a8161c156493338f00888f9b5b8596f0e8a4301a4fc959bbe7`
- cited source files: 32

Artifact files: `summary.json` (machine-readable), `README.md` (this file),
`SHA256SUMS` (covers README.md and summary.json; never itself).

## What this artifact answers

1. Which provider/model pairs have real 12-case benchmark evidence, where
   that evidence lives (path + SHA-256), and the verified rate with a 95%
   Wilson confidence interval.
2. What the strict model-identity policy means for a run whose served model
   differs from the requested one (`identity_ok=false`).
3. Which provider-dimension requirements are satisfied and which are
   blocked/unavailable, with exact reasons - no fabricated success.
4. Separate deterministic and AI metrics: `deterministic_target_strict`
   (model-independent) is never combined with `ai_target` (provider run).

## Evidence rows

| # | provider | model requested | model served | identity_ok | status | cases | runs | AI verified | attributed to | source artifact |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | deepseek-official | `deepseek-flash` | `deepseek-flash` | True | identity_verified_completed | 12 | 3 | 6 | `deepseek-flash` | `artifacts/multi-model-matrix-2026-11-14` |
| 2 | deepseek-official | `deepseek-v4-pro` | `deepseek-v4-pro` | True | identity_verified_completed | 12 | 3 | 6 | `deepseek-v4-pro` | `artifacts/multi-model-matrix-2026-11-14` |
| 3 | siliconflow-cn | `Qwen/Qwen3-8B` | `Qwen/Qwen3-8B` | True | identity_verified_completed | 12 | 1 | 0 | `Qwen/Qwen3-8B` | `artifacts/multi-model-matrix-cn-2026-11-14` |
| 4 | siliconflow-cn | `Qwen/Qwen2.5-7B-Instruct` | `Qwen/Qwen2.5-7B-Instruct` | True | identity_verified_completed | 12 | 1 | 0 | `Qwen/Qwen2.5-7B-Instruct` | `artifacts/multi-model-matrix-cn-2026-11-14` |
| 5 | siliconflow-intl | `Qwen/Qwen3.8-27B` | `Qwen/Qwen3.8-27B` | True | blocked_unavailable | 0 | 0 | - | `-` | `artifacts/multi-model-matrix-intl-2026-11-14` |
| 6 | siliconflow-intl | `deepseek-ai/DeepSeek-V4.1-Flash` | `deepseek-ai/DeepSeek-V4.1-Flash` | True | blocked_unavailable | 0 | 0 | - | `-` | `artifacts/multi-model-matrix-intl-2026-11-14` |
| 7 | siliconflow-intl | `moonshotai/Kimi-K3.1-Pro` | `moonshotai/Kimi-K3.1-Pro` | True | blocked_unavailable | 0 | 0 | - | `-` | `artifacts/multi-model-matrix-intl-2026-11-14` |
| 8 | siliconflow-cn | `THUDM/GLM-Z1-9B-0414` | `None` | None | blocked_unavailable | 0 | 0 | - | `-` | `artifacts/multi-model-matrix-cn-2026-11-14` |
| 9 | deepseek-official | `deepseek-chat` | `deepseek-flash` | False | served_model_mismatch_completed | 12 | 1 | 6 | `deepseek-flash` | `artifacts/provider-matrix-2026-11-14` |
| 10 | deepseek-official | `deepseek-chat` | `deepseek-flash` | False | probe_only_identity_mismatch | 0 | 0 | - | `-` | `artifacts/multi-model-probe-2026-11-14` |
| 11 | dashscope | `qwen-plus` | `None` | None | unavailable_no_artifact | 0 | 0 | - | `-` | `(none)` |

Every row cites source files with SHA-256; each source artifact's own
`SHA256SUMS` is validated by the builder and by the test suite, which also
re-derives the row values from the cited artifacts.

## Statistics (AI target, Wilson 95% CI)

| provider | model | runs | cases/run | verified (pooled) | verified_rate | wilson_ci95 | inconclusive | identity |
|---|---|---|---|---|---|---|---|---|
| deepseek-official | `deepseek-flash` | 3 | 12 | 18 | 0.5000 | [0.3447, 0.6553] | 18 | verified |
| deepseek-official | `deepseek-v4-pro` | 3 | 12 | 18 | 0.5000 | [0.3447, 0.6553] | 18 | verified |
| siliconflow-cn | `Qwen/Qwen2.5-7B-Instruct` | 1 | 12 | 0 | 0.0000 | [0.0000, 0.2425] | 12 | verified |
| siliconflow-cn | `Qwen/Qwen3-8B` | 1 | 12 | 0 | 0.0000 | [0.0000, 0.2425] | 12 | verified |
| siliconflow-intl | `Qwen/Qwen3.8-27B` | 0 | 0 | 0 | 0.0000 | [0.0000, 1.0000] | 0 | blocked |
| siliconflow-intl | `deepseek-ai/DeepSeek-V4.1-Flash` | 0 | 0 | 0 | 0.0000 | [0.0000, 1.0000] | 0 | blocked |
| siliconflow-intl | `moonshotai/Kimi-K3.1-Pro` | 0 | 0 | 0 | 0.0000 | [0.0000, 1.0000] | 0 | blocked |
| siliconflow-cn | `THUDM/GLM-Z1-9B-0414` | 0 | 0 | 0 | 0.0000 | [0.0000, 1.0000] | 0 | blocked |
| deepseek-official | `deepseek-chat` | 1 | 12 | 6 | 0.5000 | [0.2538, 0.7462] | 6 | mismatch-served-only |
| deepseek-official | `deepseek-chat` | 0 | 0 | 0 | 0.0000 | [0.0000, 1.0000] | 0 | mismatch-served-only |
| dashscope | `qwen-plus` | 0 | 0 | 0 | 0.0000 | [0.0000, 1.0000] | 0 | n/a |

Pooled identity-verified AI-target evidence: 4 models, 8 runs, 96 cases, 36 verified, verified_rate=0.3750, wilson_ci95=[0.2847, 0.4749], inconclusive=60.

### Deterministic target-strict (model-independent, separate metric)

- source: `artifacts/provider-matrix-2026-11-14/per-case/*.json`
- cases: 12, verified: 0, verified_rate: 0.0000, wilson_ci95: [0.0000, 0.2425], inconclusive: 12
- expected-disposition matches: 12/12 (expected_match_rate 1.0000); target scope resolved: 12
- dispositions: `{"analysis_only": 12}`

## Identity policy

- A benchmark row may be presented as requested-model-identity verified only when the provider response model equals the requested model (identity_ok=true) and the strict identity check (BINARYREPAIR_STRICT_MODEL_IDENTITY=1) passed.
- identity_ok=false rows may be recorded as served-model evidence but must never be presented as requested-model-identity verified; every AI verified count is attributed to the served model and carries a limitation note.
- Consequence: `deepseek-chat` (provider-side alias to `deepseek-flash`)
  is not counted towards requested-model coverage. Its 6/12 verified
  repairs are attributed to the served model `deepseek-flash` and excluded
  from `ai_target.pooled_identity_verified`; the identity-verified model
  rows remain the explicit `deepseek-flash` runs.

## Aggregate

| metric | value |
|---|---|
| providers with artifact | 3 |
| providers completed 12-case | 2 (deepseek-official, siliconflow-cn) |
| providers blocked | 1 (siliconflow-intl) |
| providers referenced with no artifact | 1 |
| models completed 12-case | 4 |
| models blocked (row level) | 4 |
| identity-verified models | 4 (Qwen/Qwen2.5-7B-Instruct, Qwen/Qwen3-8B, deepseek-flash, deepseek-v4-pro) |
| identity-mismatch rows | 2 |
| served-model-only completed rows | 1 |

Requirements:

- `at_least_2_models_12case`: satisfied=True
- `at_least_2_providers_12case`: satisfied=True
- `five_model_international_matrix`: satisfied=False

### Not satisfied (explicit)

- international 5-6 model matrix: 3 SiliconFlow international models passed identity probes but every benchmark call returned HTTP 402 insufficient balance; no fifth provider key is available; 4 models completed, not 5-6

### Reconciliation with the phase-4 brief

- brief expected: providers_completed=1, providers_blocked=1
- observed: providers_completed=2, providers_blocked=1
- The frozen release tree also contains real SiliconFlow-CN 12-case benchmark evidence (artifacts/multi-model-matrix-cn-2026-11-14, 4-model matrix, LIMITATIONS section 22). Both CN Qwen models are identity-verified and completed 12 cases (0/12 verified), so two providers completed 12-case; only the international 5-model matrix is blocked. No overclaim: CN models produced zero verified candidates.

## Blocked / unavailable reasons

- siliconflow-cn: identity probe timed out (TimeoutError) (models: THUDM/GLM-Z1-9B-0414)
- siliconflow-intl: HTTP 402 insufficient account balance on full benchmark calls (models: Qwen/Qwen3.8-27B, deepseek-ai/DeepSeek-V4.1-Flash, moonshotai/Kimi-K3.1-Pro)
- dashscope: no DashScope/Bailian key configured; no artifact (models: qwen-plus)

## Cost and seed

- cost available: False (value=None); provider APIs expose token usage only; no price table configured
- seed available: False (value=None); the shared provider client (HttpJsonClient.chat_json) does not marshal a seed; no source artifact records one

## Next steps

- top up the SiliconFlow international account (or use a funded key) and rerun scripts/run_multi_model_matrix.py --benchmark for the three identity-probed models to reach 5-6 models
- or configure a DashScope/Bailian key and run the same 12-case benchmark
- then rerun the multi-provider matrix in CI (one provider/model per row, strict identity, Linux guest PoC) and replace blocked rows with completed rows
- do not present served-model evidence as requested-model identity evidence (deepseek-chat alias)

## Validation

```bash
python scripts/build_provider_coverage.py --check   # fresh build == committed artifact
python -m pytest -q tests/test_provider_matrix.py tests/test_provider_coverage_artifact.py
```

The artifact test suite is offline: it verifies the schema, the SHA-256 of
every cited file, each source artifact's own `SHA256SUMS`, the identity
policy, Wilson interval sanity, aggregate re-derivation, and that the
committed artifact matches a fresh deterministic build (`--check`).

## Limitations

- no provider calls were made for this artifact; it consolidates committed evidence only
- two SiliconFlow international models and GLM have no benchmark evidence (blocked), explicitly recorded
- CN Qwen models completed 12 cases with 0/12 verified: completing a benchmark is not a pass
- successful AI repairs remain loop-family only (6/6 loop, 0/6 non-loop) for every completed model
- the provider-matrix deepseek-chat run is served-model evidence (identity_ok=false) and is never counted as requested-model coverage
