# SiliconFlow account status (2026-11-14)

- International key (`.com`): valid identity probes, but full benchmark calls
  return HTTP 402 `{"code":30001,"message":"Sorry, your account balance is insufficient"}`.
  The international site has no permanent free LLM; small models are also paid.
- China key (`.cn`): valid; identity probes pass for `Qwen/Qwen3-8B` and
  `Qwen/Qwen2.5-7B-Instruct`; `THUDM/GLM-Z1-9B-0414` timed out on the probe.
  The two Qwen models are real free calls and are included in the 4-model matrix.
- Keys are not stored in this repository.

Matrix evidence: `artifacts/multi-model-matrix-cn-2026-11-14/`.
