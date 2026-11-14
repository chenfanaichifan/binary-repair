# Provider coverage — acceptance note (2026-11-14)

Frozen release worktree (`release/2026-11-14`, commit `725e7bb`, path
`worktree-release-2026-11-14`). This note records the **provider dimension** of
the acceptance claim honestly: which models have real 12-case benchmark
evidence, which providers completed, and which are blocked/unavailable.

Machine-readable artifact: [`artifacts/provider-coverage-2026-11-14/summary.json`](../../artifacts/provider-coverage-2026-11-14/summary.json)
(with `README.md` and `SHA256SUMS` next to it). No provider calls were made to
build the artifact; it consolidates evidence already in the frozen tree with
SHA-256 bindings, and the test suite re-derives every cited digest and value.

## Status (one line)

**2 providers completed 12-case benchmarks** (DeepSeek official: 2 models;
SiliconFlow China free tier: 2 Qwen models) · **1 provider blocked**
(SiliconFlow international: identity probes pass, benchmark calls HTTP 402
insufficient balance) · **1 provider referenced with no artifact**
(DashScope/Bailian, no key) · the **5–6-model international matrix is NOT
satisfied**; completing a benchmark is not a pass (CN Qwen models are 0/12
verified).

## Evidence inventory

| provider | model | identity | status | cases | runs | AI verified | evidence |
|---|---|---|---|---|---|---|---|
| DeepSeek official | `deepseek-flash` | exact (`identity_ok=true`) | completed | 12 | 3 | 6/12 each | `artifacts/multi-model-matrix-2026-11-14/` |
| DeepSeek official | `deepseek-v4-pro` | exact | completed | 12 | 3 | 6/12 each | `artifacts/multi-model-matrix-2026-11-14/` |
| SiliconFlow CN | `Qwen/Qwen3-8B` | exact | completed | 12 | 1 | 0/12 | `artifacts/multi-model-matrix-cn-2026-11-14/` |
| SiliconFlow CN | `Qwen/Qwen2.5-7B-Instruct` | exact | completed | 12 | 1 | 0/12 | `artifacts/multi-model-matrix-cn-2026-11-14/` |
| SiliconFlow intl | `Qwen/Qwen3.8-27B` | probe exact | blocked (HTTP 402) | 0 | 0 | — | `artifacts/multi-model-matrix-intl-2026-11-14/` |
| SiliconFlow intl | `moonshotai/Kimi-K3.1-Pro` | probe exact | blocked (HTTP 402) | 0 | 0 | — | `artifacts/multi-model-matrix-intl-2026-11-14/` |
| SiliconFlow intl | `deepseek-ai/DeepSeek-V4.1-Flash` | probe exact | blocked (HTTP 402) | 0 | 0 | — | `artifacts/multi-model-matrix-intl-2026-11-14/` |
| SiliconFlow CN | `THUDM/GLM-Z1-9B-0414` | unknown | blocked (probe timeout) | 0 | 0 | — | probe record only |
| DeepSeek official | `deepseek-chat` | **mismatch** (served `deepseek-flash`) | served-model completed | 12 | 1 | 6/12 → served model | `artifacts/provider-matrix-2026-11-14/` |
| DeepSeek official | `deepseek-chat` | **mismatch** | probe only | 0 | 0 | — | `artifacts/multi-model-probe-2026-11-14/` |
| DashScope/Bailian | `qwen-plus` | unknown | unavailable, no artifact | 0 | 0 | — | — |

## Model-identity policy

- A run is presented as **requested-model-identity verified** only when the
  provider response model equals the requested model (`identity_ok=true`) and
  the strict identity check (`BINARYREPAIR_STRICT_MODEL_IDENTITY=1`) passed.
- `identity_ok=false` runs **may be recorded but must not be presented as
  requested-model-identity verified**. Their verified-repair counts are
  attributed to the **served** model and carry a limitation note. In practice:
  `deepseek-chat` is provider-side aliased to `deepseek-flash`; the
  `provider-matrix` run's 6/12 verified repairs are attributed to
  `deepseek-flash` and `deepseek-chat` is **not** counted as requested-model
  coverage.
- No provider claim exists without a SHA-256-bound evidence artifact: every row
  in `summary.json` either cites files (verified by the test suite) or is marked
  `blocked_unavailable` / `unavailable_no_artifact`.

## Aggregate and requirements

| metric | value | satisfied? |
|---|---|---|
| identity-verified models with 12-case evidence | 4 | `at_least_2_models_12case` = **yes** |
| providers completed 12-case | 2 (`deepseek-official`, `siliconflow-cn`) | `at_least_2_providers_12case` = **yes** |
| providers blocked | 1 (`siliconflow-intl`, HTTP 402) | — |
| 5–6-model international matrix | 4 completed; 3 intl blocked | `five_model_international_matrix` = **NO** |
| identity-mismatch rows recorded honestly | 2 | served-model-only policy = applied |
| identity policy applied | — | **yes** |

### Reconciliation with the phase-4 brief

The phase-4 brief expected `providers_completed=1, providers_blocked=1` (based
on the international matrix and the single-provider `provider-matrix` run).
While building this artifact, the SiliconFlow **China** evidence was located in
the frozen tree (`artifacts/multi-model-matrix-cn-2026-11-14`: 2 DeepSeek + 2
free Qwen models, 12 cases each, exact identity probes, documented as the
4-model matrix in `docs/acceptance/LIMITATIONS.md` §22). Both Qwen models
completed 12-case benchmarks with real free-tier calls (0/12 verified — a
capability result, **not** a pass). The aggregate therefore reports **2
completed providers / 1 blocked provider**, encoded transparently in
`aggregate.brief_expectation_check`, and only the *international 5–6-model*
matrix remains blocked. No overclaim is made.

## Blocked / unavailable (exact reasons)

- **SiliconFlow international** — identity probes for all three requested models
  passed with exact `resp.model`, but every full benchmark call returned
  **HTTP 402** `{"code":30001,"message":"Sorry, your account balance is
  insufficient"}`. Blocked by account balance, not identity or code.
- **SiliconFlow CN `THUDM/GLM-Z1-9B-0414`** — identity probe timed out; no
  benchmark evidence; no fifth provider key is available.
- **DashScope/Bailian `qwen-plus`** — no key configured, no artifact; referenced
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
4. Only then claim a 5–6-model / 3-provider matrix in release docs.

## Validation

Run from the frozen worktree root with the main worktree's venv:

```bash
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python \
  -m pytest -q tests/test_provider_matrix.py tests/test_provider_coverage_artifact.py
```

`tests/test_provider_coverage_artifact.py` validates the artifact schema, the
SHA-256 of every cited file, each source artifact's own `SHA256SUMS`, the
identity policy (mismatch never presented as identity-verified), honest
blocked/unavailable rows, aggregate re-derivation from rows, the transparent
brief reconciliation, and the absence of any provider claim without an
artifact. It is offline and makes no provider calls.

## Limitations

- No new provider experiment was run for this artifact; it is a consolidation of
  frozen evidence, not a fresh measurement.
- Completing 12 cases is not a pass: both CN Qwen models are 0/12 verified.
- Successful AI repairs remain loop-family only (6/6 loop, 0/6 non-loop) for
  every completed model; the provider dimension does not change that ceiling.
- The `deepseek-chat` run is served-model evidence only and is never counted as
  requested-model identity coverage.
