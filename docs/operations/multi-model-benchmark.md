# Multi-model matrix: key → probe → benchmark → interpretation

Status 2026-11-14: provider layer, strict model-identity check and matrix runner
are implemented.  The authoring host has **no SiliconFlow/百炼 key**, so no
real multi-model benchmark result exists yet.  This document is the executable
checklist for the operator who has a key.

## 1. Apply a compliant key (do not commit it)

```bash
# SiliconFlow
export BINARYREPAIR_PROVIDER=siliconflow
export SILICONFLOW_API_KEY='...'
export BINARYREPAIR_ASSISTANT_MODEL='Qwen/Qwen3-32B'

# or Alibaba Cloud Bailian / DashScope
export BINARYREPAIR_PROVIDER=dashscope
export DASHSCOPE_API_KEY='...'
export BINARYREPAIR_ASSISTANT_MODEL='qwen-plus'

export BINARYREPAIR_STRICT_MODEL_IDENTITY=1
```

`.env` is accepted but must stay git-ignored.  Keys are never written to
evidence, prompts, logs or the repository.

Recommended matrix (use provider-supported IDs; verify via `/v1/models` or the
provider console):

| tier | examples |
|---|---|
| flagship | Qwen3-Max / DeepSeek-V4-Pro / GLM-5 / Kimi-K3 |
| light | DeepSeek-V4-Flash / Qwen-Flash |
| open | Qwen/Qwen3-8B, Qwen/Qwen3-32B, DeepSeek-R1 |

Avoid a single small model as the whole matrix: a 6/6 loop result from an 8B
model is not the same evidence as flagship behavior.

## 2. Probe model identity first

```bash
python scripts/run_multi_model_matrix.py \
  --out artifacts/multi-model-probe-$(date +%Y%m%d) \
  --models siliconflow:Qwen/Qwen3-32B \
           siliconflow:deepseek-ai/DeepSeek-V4-Flash \
           dashscope:qwen-plus
```

Expected: every record `status=ok`, `model_returned` exactly equals
`model_requested`.  Any `identity_mismatch` is excluded, never averaged.
No key → `unconfigured`, exit 2, no fabricated rows.

## 3. Run the 12-case hard benchmark per model

The native PoC/regression runner is Linux-only for ELF x86-64.  On macOS,
either run the whole command inside a Linux (amd64) container/VM with outbound
network, or generate candidates on macOS and evaluate them in the Linux VM.

```bash
python scripts/run_multi_model_matrix.py \
  --out artifacts/multi-model-matrix-$(date +%Y%m%d) \
  --models siliconflow:Qwen/Qwen3-32B \
           siliconflow:deepseek-ai/DeepSeek-V4-Flash \
  --benchmark --contract-level full
```

Each model gets an isolated `benchmarks/<provider>-<model>/summary.json`;
the aggregate stores baseline/AI/increment and the subprocess evidence.  The
runner refuses identity-mismatched models before benchmarking.

## 4. Interpret honestly

Expected pattern from the single-family result:

- loop family: model-dependent 0–6/6; this tests **robustness**, not new
  capability;
- CWE121/multicall/sprintf/nonconst/UAF/heap: **0 for every model** while the
  assembly path is leaf-only and forbids external calls; switching model does
  not remove that ceiling;
- report exact model identity, token/latency, repeats and Wilson confidence
  intervals; cases are not independent, so label them case-clustered;
- any model with `identity_mismatch` is a failed provider, not a 0 score.

## 5. Current blocker

No SILICONFLOW_API_KEY / DASHSCOPE_API_KEY is configured on this host.  The
existing DeepSeek endpoint ignores the model parameter and always returns
`deepseek-flash`; the probe flags `deepseek-chat → deepseek-flash` as
`identity_mismatch` and the evidence excludes it.  Provide a compliant key in
the environment (or `.env`) and rerun section 2–3; no code changes are needed.

## 6. What this cannot fix

Multi-model tests answer "is the loop-family result robust across models?" They
do not extend the non-loop families.  Only the independent paradigm-A route
(decompile C → LLM patch → binary-aware recompile) can remove the leaf-only
external-call ceiling.
