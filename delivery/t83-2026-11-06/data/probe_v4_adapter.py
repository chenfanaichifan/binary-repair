import json

from app.domain.v4 import from_v4_harness, validate_v4_evidence

d = json.load(open("../../v4-evidence.json"))
e = from_v4_harness(d)
print("claimed_scope:", e.claimed_scope)
print("calibration:", e.calibration)
print("exploration:", e.exploration_accounting)
print("solver:", e.solver_accounting)
print("replay:", e.replay)
print("forbidden_ranges:", e.forbidden_ranges)
print(
    "empty-disjunction in not_claimed:",
    any("empty" in x.lower() and "disjunction" in x.lower() for x in e.not_claimed),
)
print(
    "binary-level exclusion:",
    any("binary-level" in x.lower() for x in e.not_claimed),
)
again = validate_v4_evidence(
    e.model_dump(),
    candidate_sha256=e.candidate_sha256,
    original_sha256=e.original_sha256,
)
print("revalidate:", again.state)
