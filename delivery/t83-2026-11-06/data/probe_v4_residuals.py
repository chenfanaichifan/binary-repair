import copy
import json

from app.domain.v4 import from_v4_harness, validate_v4_evidence

d = json.load(open("../../v4-evidence.json"))

e = from_v4_harness(d)
print("converted property_kind:", e.property_kind, "forbidden_ranges:", e.forbidden_ranges)

m = e.model_dump()
m["property_kind"] = "memory-range"
m["forbidden_ranges"] = []
try:
    validate_v4_evidence(m)
    print("memory-range + empty ranges: ACCEPTED")
except Exception as exc:  # noqa: BLE001
    print("memory-range + empty ranges: REJECTED -", str(exc).splitlines()[0])

m2 = copy.deepcopy(m)
m2["property_kind"] = "pointer-flow"
try:
    validate_v4_evidence(m2)
    print("pointer-flow + empty ranges: ACCEPTED (explicit allowance)")
except Exception as exc:  # noqa: BLE001
    print("pointer-flow + empty ranges: REJECTED -", str(exc).splitlines()[0])

d2 = copy.deepcopy(d)
d2["not_claimed"] = [
    x for x in d2["not_claimed"]
    if not ("empty" in x.lower() and "disjunction" in x.lower())
]
e2 = from_v4_harness(d2)
print(
    "disclosure re-added:",
    any("empty" in x.lower() and "disjunction" in x.lower() for x in e2.not_claimed),
)

d3 = copy.deepcopy(d)
kb = [c for c in d3["cases"] if c.get("kind") == "known_bad"]
extra = copy.deepcopy(kb[0])
extra["id"] = "known_bad_holds"
extra["observed"] = "holds"
d3["cases"] = list(d3["cases"]) + [extra]
try:
    e3 = from_v4_harness(d3)
    print("one known-bad holds: ACCEPTED", e3.calibration)
except Exception as exc:  # noqa: BLE001
    print("one known-bad holds: REJECTED -", str(exc).splitlines()[0])
