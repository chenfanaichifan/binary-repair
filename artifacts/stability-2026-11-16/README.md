# Repeated repair stability (2026-11-16)

36 independent runs: 2 models x 6 cases x 3 repeats.  Each run used its own
process/out dir and evidence bundle; candidates/hashes are recorded in the
per-run manifests (large binary copies are intentionally not duplicated).

| model | verified |
|---|---:|
| deepseek-flash | 12/18 |
| deepseek-v4-pro | 7/18 |
| **total** | **19/36** |

Per-case stability:
- cwe122-heap-copy 6/6
- cwe787-index-write 6/6
- hard-nonconst 3/6
- hard-multicall 2/6
- hard-sprintf 2/6
- cwe121-unchecked-strcpy 0/6

This is a real stochastic result, not a claim of deterministic success.
