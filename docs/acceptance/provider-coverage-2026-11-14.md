# Provider coverage - acceptance note (2026-11-14)

This note records the **provider dimension** of the acceptance claim honestly:
which providers/models have real 12-case benchmark evidence, what the verified
rate is (with 95% Wilson intervals), how the strict model-identity policy treats
served-model mismatches, and which capabilities are blocked/unavailable.

Machine-readable artifact: [`artifacts/provider-coverage-2026-11-14/summary.json`](../../artifacts/provider-coverage-2026-11-14/summary.json)
(with `README.md` and `SHA256SUMS` next to it). The artifact is **reproducible**:
[`scripts/build_provider_coverage.py`](../../scripts/build_provider_coverage.py)
re-derives it deterministically from the committed source artifacts (no provider
calls, no network, no git commands, no wall-clock timestamps). Every cited file
carries a SHA-256 and every source artifact's own `SHA256SUMS` is validated.

## Status (one line)

**2 providers completed 12-case benchmarks** (DeepSeek official: 2 models;
SiliconFlow China free tier: 2 Qwen models) - **1 provider blocked**
(SiliconFlow international: identity probes pass, benchmark calls HTTP 402
insufficient balance) - **1 provider referenced with no artifact**
(DashScope/Bailian, no key) - the **international 5-6 model matrix is NOT
satisfied**. Completing a benchmark is not a pass: the CN Qwen models are 0/12
verified.

## Evidence inventory

| provider | model | identity | status | cases | runs | AI verified | evidence |
|---|---|---|---|---|---|---|---|
| DeepSeek official | `deepseek-flash` | exact (`identity_ok=true`) | completed | 12 | 3 | 18/36 pooled (0.5) | `artifacts/multi-model-matrix-2026-11-14/` |
| DeepSeek official | `deepseek-v4-pro` | exact | completed | 12 | 3 | 18/36 pooled (0.5) | `artifacts/multi-model-matrix-2026-11-14/` |
| SiliconFlow CN | `Qwen/Qwen3-8B` | exact | completed | 12 | 1 | 0/12 | `artifacts/multi-model-matrix-cn-2026-11-14/` |
| SiliconFlow CN | `Qwen/Qwen2.5-7B-Instruct` | exact | completed | 12 | 1 | 0/12 | `artifacts/multi-model-matrix-cn-2026-11-14/` |
| SiliconFlow intl | `Qwen/Qwen3.8-27B` | probe exact | blocked (HTTP 402) | 0 | 0 | not executed | `artifacts/multi-model-matrix-intl-2026-11-14/` |
| SiliconFlow intl | `moonshotai/Kimi-K3.1-Pro` | probe exact | blocked (HTTP 402) | 0 | 0 | not executed | `artifacts/multi-model-matrix-intl-2026-11-14/` |
| SiliconFlow intl | `deepseek-ai/DeepSeek-V4.1-Flash` | probe exact | blocked (HTTP 402) | 0 | 0 | not executed | `artifacts/multi-model-matrix-intl-2026-11-14/` |
| SiliconFlow CN | `THUDM/GLM-Z1-9B-0414` | unknown | blocked (probe timeout) | 0 | 0 | not executed | probe record only |
| DeepSeek official | `deepseek-chat` | **mismatch** (served `deepseek-flash`) | served-model completed | 12 | 1 | 6/12 -> served model | `artifacts/provider-matrix-2026-11-14/` |
| DeepSeek official | `deepseek-chat` | **mismatch** | probe only | 0 | 0 | not executed | `artifacts/multi-model-probe-2026-11-14/` |
| DashScope/Bailian | `qwen-plus` | unknown | unavailable, no artifact | 0 | 0 | not executed | - |

## Model-identity policy

- A run is presented as **requested-model-identity verified** only when the
  provider response model equals the requested model (`identity_ok=true`) and
  the strict identity check (`BINARYREPAIR_STRICT_MODEL_IDENTITY=1`) passed.
- `identity_ok=false` runs **may be recorded but must not be presented as
  requested-model-identity verified**. Their verified-repair counts are
  attributed to the **served** model and carry a limitation note. In practice:
  `deepseek-chat` is provider-side aliased to `deepseek-flash`; the
  `provider-matrix` run's 6/12 verified repairs are attributed to
  `deepseek-flash`, and `deepseek-chat` is **not** counted as requested-model
  coverage or pooled into identity-verified statistics.
- No provider claim exists without a SHA-256-bound evidence artifact: every row
  in `summary.json` either cites files (verified by the test suite) or is marked
  `blocked_unavailable` / `unavailable_no_artifact`.

## Statistics (separate metrics, 95% Wilson intervals)

The artifact reports `statistics.deterministic_target_strict` (model-independent)
and `statistics.ai_target` (real provider runs) as **separate metrics**; they are
never combined into one score.

| metric | cases | verified | verified_rate | wilson_ci95 | inconclusive |
|---|---|---|---|---|---|
| AI target, identity-verified models (4 models, 8 runs, pooled) | 96 | 36 | 0.375 | [0.284725, 0.474895] | 60 |
| AI target, `deepseek-flash` (3 runs pooled) | 36 | 18 | 0.5 | [0.344741, 0.655259] | 18 |
| AI target, `deepseek-v4-pro` (3 runs pooled) | 36 | 18 | 0.5 | [0.344741, 0.655259] | 18 |
| AI target, `Qwen/Qwen3-8B` (1 run) | 12 | 0 | 0.0 | [0.0, 0.242501] | 12 |
| AI target, `Qwen/Qwen2.5-7B-Instruct` (1 run) | 12 | 0 | 0.0 | [0.0, 0.242501] | 12 |
| AI target, served-model-only `deepseek-chat` -> `deepseek-flash` | 12 | 6 | 0.5 | [0.253778, 0.746222] | 6 |
| Deterministic target-strict (model-independent) | 12 | 0 | 0.0 | [0.0, 0.242501] | 12 |

Method: Wilson score interval at 95% confidence (z=1.96), pooled over all runs of
a model. `verified` = cases accepted by the native/emulated PoC+regression gate;
`inconclusive` = cases that produced no verified candidate (analysis_only /
rejected / no candidate / gate fail). n=0 (blocked/unavailable) uses the
uninformative interval [0.0, 1.0] and is never counted as a pass.

The deterministic target-strict measurement has `expected_matches=12/12`
(disposition matches `cases.json` `baseline_expected_target_strict`) but
`verified=0`: the hard cases are deliberately outside the deterministic
templates, so an expectation match is a benchmark-oracle consistency measure,
not a repair success.

## Aggregate and requirements

| metric | value | satisfied? |
|---|---|---|
| identity-verified models with 12-case evidence | 4 | `at_least_2_models_12case` = **yes** |
| providers completed 12-case | 2 (`deepseek-official`, `siliconflow-cn`) | `at_least_2_providers_12case` = **yes** |
| providers blocked | 1 (`siliconflow-intl`, HTTP 402) | - |
| international 5-6 model matrix | 4 completed; 3 intl blocked | `five_model_international_matrix` = **NO** |
| identity-mismatch rows recorded honestly | 2 | served-model-only policy = applied |
| cost / seed | unavailable (`available=false`, `value=null`) | - |

`aggregate.not_satisfied` explicitly records the international 5-6 model matrix
gap; it is not silently omitted.

### Reconciliation with the phase-4 brief

The phase-4 brief expected `providers_completed=1, providers_blocked=1` (based
on the international matrix and the single-provider `provider-matrix` run). The
repository also contains real SiliconFlow **China** 12-case evidence
(`artifacts/multi-model-matrix-cn-2026-11-14`: 2 DeepSeek + 2 free Qwen models,
12 cases each, exact identity probes, documented as the 4-model matrix in
`docs/acceptance/LIMITATIONS.md` section 22). Both Qwen models completed 12-case
benchmarks with real free-tier calls (0/12 verified - a capability result,
**not** a pass). The aggregate therefore reports **2 completed providers / 1
blocked provider**, encoded transparently in
`aggregate.brief_expectation_check`, and only the *international 5-6-model*
matrix remains blocked. No overclaim is made.

## Blocked / unavailable (exact reasons)

- **SiliconFlow international** - identity probes for all three requested models
  passed with exact `resp.model`, but every full benchmark call returned
  **HTTP 402** `{"code":30001,"message":"Sorry, your account balance is
  insufficient"}`. Blocked by account balance, not identity or code.
- **SiliconFlow CN `THUDM/GLM-Z1-9B-0414`** - identity probe timed out; no
  benchmark evidence; no fifth provider key is available.
- **DashScope/Bailian `qwen-plus`** - no key configured, no artifact; referenced
  by docs only.

## Next steps

1. Top up the SiliconFlow international account (or provide a funded key) and
   rerun `scripts/run_multi_model_matrix.py --benchmark` for the three
   identity-probed models; the runner refuses identity mismatches before
   benchmarking.
2. Or configure a DashScope/Bailian key and run the same 12-case matrix.
3. Re-run the multi-provider matrix in CI (one provider/model per row, strict
   identity, native PoC in the Linux guest) and replace blocked rows with
   completed rows; keep served-model-only attribution for any alias.
4. Only then claim a 5-6-model / 3-provider matrix in release docs.

## Reproducibility and validation

```bash
python scripts/build_provider_coverage.py            # deterministic rebuild
python scripts/build_provider_coverage.py --check    # fresh build == committed artifact
python -m pytest -q tests/test_provider_matrix.py tests/test_provider_coverage_artifact.py
```

`--check` rebuilds the artifact in memory and compares `summary.json`,
`README.md` and `SHA256SUMS` byte-for-byte with the committed artifact; it exits
0 only on an exact match and never writes files. `generated_at` is deterministic:
it is the latest `generated_at` recorded in a cited source artifact, not the
build clock, so a fresh build stays byte-identical.

`tests/test_provider_coverage_artifact.py` is offline (no network) and validates:
the release-gate schema contract, the SHA-256 of every cited file, each source
artifact's own `SHA256SUMS`, identity policy enforcement, Wilson interval math,
re-derivation of every evidence value from the cited artifacts, the
`not_satisfied`/blocked fields, builder determinism, and `--check` tamper
detection.

## Limitations

- No new provider experiment was run for this artifact; it consolidates
  committed evidence, not a fresh measurement.
- Completing 12 cases is not a pass: both CN Qwen models are 0/12 verified.
- Successful AI repairs remain loop-family only (6/6 loop, 0/6 non-loop) for
  every completed model; the provider dimension does not change that ceiling.
- The `deepseek-chat` run is served-model evidence only and is never counted as
  requested-model identity coverage.
