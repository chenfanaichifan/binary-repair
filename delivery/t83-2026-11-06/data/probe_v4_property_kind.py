import copy
import json

from app.domain.v4 import from_v4_harness

base = json.load(open("../../v4-evidence.json"))


def check(label, data):
    try:
        e = from_v4_harness(data)
        print(f"{label}: ACCEPTED (kind={e.property_kind}, ranges={e.forbidden_ranges})")
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: REJECTED - {str(exc).splitlines()[0]}")


check("missing property_kind", copy.deepcopy(base))

d = copy.deepcopy(base)
d["property_kind"] = "pointer-flow"
check("pointer-flow + empty ranges", d)

d = copy.deepcopy(base)
d["property_kind"] = "memory-range"
check("memory-range + empty ranges", d)

d = copy.deepcopy(base)
d["property_kind"] = "memory-range"
d["property_text"] = "a pointer passed to free is later passed to printLine"
check("text says pointer + memory-range + empty", d)

d = copy.deepcopy(base)
d["property_kind"] = "pointer-flow"
d["property_text"] = "a heap block is read after release"
check("text omits pointer + pointer-flow + empty", d)
