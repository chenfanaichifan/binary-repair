# Provider coverage — machine-readable provider/model evidence (2026-11-14)

Frozen release worktree: `/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/worktree-release-2026-11-14`
(branch `release/2026-11-14`, commit `725e7bb`). **No provider calls were made while
building this artifact**; it consolidates evidence that already exists in the tree,
with SHA-256 bindings to every cited file.

Artifact files: `summary.json` (machine-readable), `README.md` (this file),
`SHA256SUMS` (covers the two files above; never itself).

## What this artifact answers

1. Which provider/model pairs have **real 12-case benchmark evidence** in the
   frozen tree, and where that evidence lives (path + SHA-256).
2. What the **strict model-identity policy** means for a run whose served model
   differs from the requested one (`identity_ok=false`).
3. Which provider dimension requirements are **satisfied honestly** and which
   are **blocked/unavailable**, with exact reasons — no fabricated success.

## Evidence rows (from `summary.json`)

| # | provider | model requested | model served | identity_ok | status | cases | runs | AI verified | attributed to | source artifact |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | deepseek-official | `deepseek-flash` | `deepseek-flash` | true | identity_verified_completed | 12 | 3 | 6/12 each | `deepseek-flash` | `artifacts/multi-model-matrix-2026-11-14` |
| 2 | deepseek-official | `deepseek-v4-pro` | `deepseek-v4-pro` | true | identity_verified_completed | 12 | 3 | 6/12 each | `deepseek-v4-pro` | `artifacts/multi-model-matrix-2026-11-14` |
| 3 | siliconflow-cn | `Qwen/Qwen3-8B` | `Qwen/Qwen3-8B` | true | identity_verified_completed | 12 | 1 | 0/12 | `Qwen/Qwen3-8B` | `artifacts/multi-model-matrix-cn-2026-11-14` |
| 4 | siliconflow-cn | `Qwen/Qwen2.5-7B-Instruct` | `Qwen/Qwen2.5-7B-Instruct` | true | identity_verified_completed | 12 | 1 | 0/12 | `Qwen/Qwen2.5-7B-Instruct` | `artifacts/multi-model-matrix-cn-2026-11-14` |
| 5 | siliconflow-intl | `Qwen/Qwen3.8-27B` | (probe) | true (probe) | blocked_unavailable | 0 | 0 | — | — | `artifacts/multi-model-matrix-intl-2026-11-14` |
| 6 | siliconflow-intl | `moonshotai/Kimi-K3.1-Pro` | (probe) | true (probe) | blocked_unavailable | 0 | 0 | — | — | `artifacts/multi-model-matrix-intl-2026-11-14` |
| 7 | siliconflow-intl | `deepseek-ai/DeepSeek-V4.1-Flash` | (probe) | true (probe) | blocked_unavailable | 0 | 0 | — | — | `artifacts/multi-model-matrix-intl-2026-11-14` |
| 8 | siliconflow-cn | `THUDM/GLM-Z1-9B-0414` | — | unknown | blocked_unavailable | 0 | 0 | — | — | `artifacts/multi-model-matrix-cn-2026-11-14` (probe timeout) |
| 9 | deepseek-official | `deepseek-chat` | `deepseek-flash` | **false** | served_model_mismatch_completed | 12 | 1 | 6/12 | `deepseek-flash` | `artifacts/provider-matrix-2026-11-14` |
| 10 | deepseek-official | `deepseek-chat` (probe) | `deepseek-flash` | **false** | probe_only_identity_mismatch | 0 | 0 | — | — | `artifacts/multi-model-probe-2026-11-14` |
| 11 | dashscope | `qwen-plus` | — | unknown | unavailable_no_artifact | 0 | 0 | — | — | (none; referenced by docs only) |

All evidence rows carry `source.files[]` with a SHA-256 per file and a validated
`source.sha256sums` block (artifact `SHA256SUMS` paths, digest, and per-entry
verification). The test suite recomputes every digest from disk and fails if any
file is missing or changed.

## Identity policy (encoded in `summary.json.identity_policy`)

- A run is **requested-model-identity verified** only when `model_returned ==
  model_requested` (`identity_ok=true`) and the strict identity check
  (`BINARYREPAIR_STRICT_MODEL_IDENTITY=1`) passed. The strict check rejects
  mismatches; non-strict runs are recorded as served-model evidence only.
- `identity_ok=false` runs **may be recorded but must not be presented as
  requested-model-identity verified**. Their AI verified counts are attributed
  to the *served* model and carry an explicit limitation note (row 9 and 10
  above; `aggregate.served_model_only_completed_rows = 1`).
- Consequence: `deepseek-chat` (provider-side alias to `deepseek-flash`) is
  **not** counted towards requested-model coverage. Row 9's 6/12 verified
  repairs are attributed to the served model `deepseek-flash`, and row 1's
  explicit `deepseek-flash` runs remain the identity-verified evidence.

## Aggregate (`summary.json.aggregate`)

| metric | value |
|---|---|
| providers with artifact | 3 (`deepseek-official`, `siliconflow-intl`, `siliconflow-cn`) |
| providers completed 12-case | **2** (`deepseek-official`, `siliconflow-cn`) |
| providers blocked | **1** (`siliconflow-intl`, HTTP 402) |
| providers referenced with no artifact | 1 (`dashscope`) |
| models completed 12-case | **4** |
| models blocked | 4 row-level entries (3 intl + 1 CN probe timeout) |
| identity-verified models | 4 (`deepseek-flash`, `deepseek-v4-pro`, `Qwen/Qwen3-8B`, `Qwen/Qwen2.5-7B-Instruct`) |
| identity-mismatch rows | 2 (1 probe-only, 1 served-model 12-case) |
| served-model-only completed rows | 1 |
| `at_least_2_models_12case` | **satisfied** (4 models) |
| `at_least_2_providers_12case` | **satisfied** (DeepSeek official + SiliconFlow CN) |
| `five_model_international_matrix` | **NOT satisfied** (4/5-6; intl blocked) |

### Reconciliation with the phase-4 brief (transparent exception)

The phase-4 brief expected `providers_completed=1, providers_blocked=1`, based on
the international matrix and the single-provider `provider-matrix` run. While
building this artifact, real **SiliconFlow China** evidence was located in the
frozen tree (`artifacts/multi-model-matrix-cn-2026-11-14`: 2 DeepSeek + 2 free
Qwen models, 12 cases each, exact identity probes, documented as the 4-model
matrix in `docs/acceptance/LIMITATIONS.md` §22). Both Qwen models completed the
12-case benchmark with real free-tier calls (0/12 verified, i.e. a capability
result, not a pass). Therefore the machine aggregate reports **2 completed
providers / 1 blocked provider**, and only the *5–6-model international matrix*
remains blocked. No overclaim is made: the CN models produced zero verified
candidates, and the `deepseek-chat` mismatch row is excluded from
requested-model identity evidence.

## Blocked / unavailable reasons (exact)

- **siliconflow-intl** (`Qwen/Qwen3.8-27B`, `moonshotai/Kimi-K3.1-Pro`,
  `deepseek-ai/DeepSeek-V4.1-Flash`): identity probes passed with exact
  `resp.model`, but every full benchmark call returned **HTTP 402**
  `{"code":30001,"message":"Sorry, your account balance is insufficient"}`.
  Blocked by account balance, not by code or identity. No benchmark result was
  produced.
- **siliconflow-cn / `THUDM/GLM-Z1-9B-0414`**: identity probe timed out
  (`TimeoutError`); no benchmark evidence exists.
- **dashscope / `qwen-plus`**: no DashScope/Bailian key is configured; the
  provider is referenced by docs only and no artifact exists.

## Next steps to reach the full multi-provider matrix

1. Top up the SiliconFlow international account (or supply a funded key): rerun
   `scripts/run_multi_model_matrix.py --benchmark` for the three identity-probed
   models; the runner refuses identity mismatches before benchmarking.
2. Or configure a DashScope/Bailian key and run the same 12-case benchmark.
3. Re-run the matrix in CI (one provider/model per row, strict identity, native
   PoC in the Linux guest) and replace the blocked rows of this artifact with
   completed rows; keep the served-model-only policy for any alias.
4. Only then may docs claim a 5–6-model / 3-provider matrix. Do not present
   served-model evidence as requested-model identity evidence.

## Validation

```bash
# run from the frozen worktree root; the venv lives in the main worktree
/Users/huageorge/Desktop/AI驱动的二进制漏洞自动修复与正确性验证/binary-repair-gui/.venv/bin/python \
  -m pytest -q tests/test_provider_matrix.py tests/test_provider_coverage_artifact.py
```

The coverage test verifies the schema, that every cited SHA-256 matches the file
on disk, that each source artifact's own `SHA256SUMS` still validates, that
identity-mismatch rows are never presented as identity-verified, that no
provider claim exists without an evidence artifact, and that the aggregate
counts are re-derived from the rows (no overclaim).

## Limitations

- No provider calls were made for this artifact; it is a consolidation of frozen
  evidence, with hashes, not a new experiment.
- Completing a 12-case benchmark is not a pass: both CN Qwen models are 0/12
  verified.
- Successful AI repairs remain **loop-family only** (6/6 loop, 0/6 non-loop) for
  every completed model; this artifact does not change that.
- `deepseek-chat` is provider-side aliased to `deepseek-flash`; that run is
  served-model evidence only and is never counted as requested-model coverage.
