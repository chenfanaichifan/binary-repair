# P23 smoke test (2026-11-16)

One independent run was used to validate the stability harness against the
frozen P21 profile. The run executed a real provider call, saved its summary,
and the independent verifier reported `PLAN_INVALID`; the run is eligible but
not VERIFIED. This is smoke plumbing, not the 60-run matrix.
