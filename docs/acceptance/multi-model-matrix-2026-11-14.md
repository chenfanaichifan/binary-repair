# Two-model DeepSeek hard-case matrix (2026-11-14)

Valid DeepSeek official credential; provider/model identity matched exactly.

| model | runs | baseline | AI verified | loop family | non-loop family |
|---|---:|---:|---:|---:|---:|
| `deepseek-flash` | 3 | 0/12 | **6/12** | **6/6** | **0/6** |
| `deepseek-v4-pro` | 3 | 0/12 | **6/12** | **6/6** | **0/6** |

All six runs stable at 6/12.  Native PoC/regression executed in the Linux
x86-64 VM.  Successes are the six inline-copy loop variants; CWE121,
multicall, sprintf, non-const, UAF and heap-canary all fail under the
leaf-only assembly path.  This tests model robustness, not new capability.

- Evidence: `artifacts/multi-model-matrix-2026-11-14/`
- Provider identity probe: `artifacts/deepseek-matrix-2026-11-14/`
- Key is never stored in these artifacts.

This is two models from one provider, not the recommended 4–6 model matrix;
it is also not an independent-sample confidence interval.
