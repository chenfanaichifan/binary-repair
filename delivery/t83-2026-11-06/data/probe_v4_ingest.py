import json

from app.domain.v4 import validate_v4_evidence

d = json.load(open("../../v4-evidence.json"))
try:
    validate_v4_evidence(d)
    print("ACCEPTED")
except Exception as exc:  # noqa: BLE001
    print(type(exc).__name__)
    print(str(exc)[:900])
