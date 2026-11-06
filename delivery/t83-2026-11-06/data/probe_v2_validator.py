import json
import sys

sys.path.insert(0, ".")

from app.domain.interface import (  # noqa: E402
    InterfaceCheckError,
    check_interface,
    validate_interface_report,
)

E = (
    "../../_m4-verify/124/M3-124-cwe416-candidate-handoff-2026-11-05/"
    "evidence/cwe416-candidate-2026-11-05"
)
TARGET = "CWE416_Use_After_Free__malloc_free_char_01_bad"

r = check_interface(f"{E}/original.elf", f"{E}/candidate.elf", TARGET)
print("scored:", r["state"], r["score"])
try:
    validate_interface_report(
        r,
        candidate_sha256=r["candidate_sha256"],
        original_sha256=r["original_sha256"],
        target_entry=TARGET,
    )
    print("scored report: ACCEPTED")
except InterfaceCheckError as exc:
    print("scored report: REJECTED", exc)

obs = json.load(open(f"{E}/v2-interface.json"))
try:
    validate_interface_report(obs)
    print("observation: ACCEPTED")
except InterfaceCheckError as exc:
    print("observation: REJECTED", exc)
