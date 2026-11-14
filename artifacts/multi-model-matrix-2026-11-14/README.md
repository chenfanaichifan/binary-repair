# Multi-model hard-case matrix — valid DeepSeek key (2026-11-14)

Provider: DeepSeek official `https://api.deepseek.com/v1`.  Requested and
returned model identity matched exactly on every run; no key/prompt/raw
response is stored.

| model | runs | baseline | AI verified | loop family | non-loop family |
|---|---:|---:|---:|---:|---:|
| `deepseek-flash` | 3 | 0/12 | **6/12** | **6/6** | **0/6** |
| `deepseek-v4-pro` | 3 | 0/12 | **6/12** | **6/6** | **0/6** |

All six runs were stable at 6/12.  Native PoC/regression was executed in the
Linux x86-64 VM; candidate generation used the real provider on macOS.

## Per-case result (both models, all repeats)

| case | family | deterministic | AI |
|---|---|---|---|
| inline-byte-loop | loop | rejected | pass |
| hard-loop8 | loop | rejected | pass |
| hard-loop16 | loop | rejected | pass |
| hard-loop32 | loop | rejected | pass |
| hard-loop64 | loop | rejected | pass |
| hard-reverse | loop | rejected | pass |
| cwe121-unchecked-strcpy | semantic | analysis_only | no candidate |
| hard-multicall | multi-layer | rejected | fail/no candidate |
| hard-sprintf | multi-layer | rejected | no candidate |
| hard-nonconst | multi-layer | rejected | fail/no candidate |
| uaf-noinput | heap lifetime | analysis_only | no candidate |
| heap-canary | heap guard | rejected | fail/no candidate |

The result is **model-robust for the loop family only**.  Two models are not a
statistical population, and non-loop failures are model-independent while the
assembly path forbids external calls.  This is the P1 quick win: it verifies
robustness, not new capability.
