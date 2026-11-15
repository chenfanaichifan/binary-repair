# P23 60-run matrix: partial execution (2026-11-16)

The full 60-run live matrix was started against the frozen P21 profile, but was
stopped during the first case because the live-provider latency made the
planned 60 runs impractical in the current execution window. One completed
run is retained:

- model: deepseek-flash
- case: hard-multicall
- result: PLAN_INVALID (eligible, not VERIFIED)

This directory is explicitly a partial run set, not a 60-run result. The
runner and smoke test are validated; the full matrix must be resumed as a new
experiment ID without rewriting this record.
