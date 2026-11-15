# Cross-binary RepairSpec benchmark (2026-11-15)

Cases: `fixtures/repair-benchmark/cases.json` — 4 binaries, CWE-121/CWE-122/
CWE-787.  Same planner, ABI-strict, semantic-retry and native gate.

DeepSeek flash final run: **4/6 verified**

| case | status |
|---|---|
| hard-multicall | VERIFIED |
| hard-sprintf | VERIFIED |
| hard-nonconst | VERIFIED |
| cwe122-heap-copy | VERIFIED (unseen binary) |
| cwe121-unchecked-strcpy | SECURITY_FAILED |
| cwe787-index-write | ASSEMBLY_REJECTED |

This is the first cross-binary evidence; it is still a small benchmark, not a
universal claim.
