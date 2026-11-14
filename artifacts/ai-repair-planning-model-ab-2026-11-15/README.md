# RepairSpec model A/B (2026-11-15)

Same plan/assembly/ABI-strict pipeline, same three hard non-loop cases:

| model | verified | failure modes |
|---|---:|---|
| deepseek-flash | **3/3** | none |
| deepseek-v4-pro | 0/3 | hard-multicall: ABI fatal (rsp/callee-saved); hard-sprintf: empty/invalid plan; hard-nonconst: forbidden call target 0x0 |

This is the key current result: the **RepairSpec + ABI-strict + cave relocation**
pipeline can convert the capable model's output into verified repairs, while a
different model still fails with typed evidence. It is not "prompt-only" success
and not universal model capability.
