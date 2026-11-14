# 4-model matrix (2026-11-14)

Configuration:
- 2 DeepSeek official models (`deepseek-flash`, `deepseek-v4-pro`);
- 2 SiliconFlow China free models (`Qwen/Qwen3-8B`, `Qwen/Qwen2.5-7B-Instruct`),
  base URL `https://api.siliconflow.cn/v1`;
- native PoC/regression in the Linux VM; strict model identity.

| model | baseline | AI verified | loop | non-loop |
|---|---:|---:|---:|---:|
| deepseek-flash | 0/12 | 6/12 | 6/6 | 0/6 |
| deepseek-v4-pro | 0/12 | 6/12 | 6/6 | 0/6 |
| Qwen/Qwen3-8B | 0/12 | 0/12 | 0/6 | 0/6 |
| Qwen/Qwen2.5-7B-Instruct | 0/12 | 0/12 | 0/6 | 0/6 |

Identity probes passed for all four models.  Qwen CN models are real free calls
(no balance error) but produced no verified candidate; this is model-capability
data, not a fabricated failure.  This completes a **4-model real matrix** and
does not change the non-loop 0/6 conclusion.

The earlier attempt to combine all four in one invocation omitted the DeepSeek
key in the feature worktree; the successful DeepSeek half is retained under
`benchmarks/` after the key-loaded rerun.
