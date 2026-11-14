# Multi-model provider probe (2026-11-14)

Purpose: prove that the configured endpoint actually serves the requested
model.  No key, prompt or raw response is stored; exact `resp.model` identity is
mandatory for benchmark evidence.

## Result on this host

| request | returned model | status |
|---|---|---|
| `deepseek:deepseek-chat` | `deepseek-flash` | **identity_mismatch** |
| `deepseek:deepseek-flash` | `deepseek-flash` | ok |
| `siliconflow:Qwen/...` | — | **unconfigured: no SILICONFLOW_API_KEY** |
| `dashscope:qwen-plus` | — | **unconfigured: no DASHSCOPE_API_KEY** |

The old single model endpoint silently maps `deepseek-chat` to
`deepseek-flash`.  This is exactly the model-shrinkage risk P5; the strict
identity check now catches it and excludes it from benchmark evidence.

No real multi-model comparison can be run until a compliant provider key is
configured (SiliconFlow or DashScope/Bailian).  The provider layer and probe are
implemented and tested; only credentials are missing.

## Reproduce

```bash
SILICONFLOW_API_KEY=... BINARYREPAIR_PROVIDER=siliconflow \
  .venv/bin/python scripts/run_multi_model_matrix.py \
  --out artifacts/multi-model-probe-2026-11-14 \
  --models siliconflow:Qwen/Qwen3-8B siliconflow:deepseek-ai/DeepSeek-V3
```
