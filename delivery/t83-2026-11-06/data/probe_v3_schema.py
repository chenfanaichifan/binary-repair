import json

from app.domain.contracts import SecurityContract

BASE = dict(
    schema_version=3,
    input_mode="none",
    target_entry="bad",
    target_signature="void bad(void)",
    valid_domain="no program input",
    valid_behavior="prints the correct string",
    forbidden_behavior="read after free",
    dest_capacity_bytes=50,
    capacity_includes_terminator=True,
    authorized_edits=(),
    allowed_calls=(),
    environment_assumptions=(),
)

print("== A: v3 none minimal ==")
c = SecurityContract(**BASE)
d = c.to_dict()
print("keys:", sorted(d))
print(
    "rejection-ish keys present:",
    [k for k in d if k.startswith("invalid_") or k == "max_valid_input_bytes"],
)
print("input_mode:", d.get("input_mode"))
print("round-trip hash stable:", SecurityContract.from_dict(d).sha256() == c.sha256())
print("hash:", c.sha256())

print("\n== B: v3 none sentinel values ==")
for field, value in [
    ("invalid_input_response", ""),
    ("invalid_exit_code", 0),
    ("invalid_stdout", ""),
    ("invalid_stderr", ""),
    ("max_valid_input_bytes", 0),
]:
    body = dict(BASE)
    body[field] = value
    try:
        SecurityContract(**body)
        print(f"{field}={value!r}: ACCEPTED (bad)")
    except Exception as e:
        print(f"{field}={value!r}: rejected ({e})")

print("\n== C: v3 none from_dict with null rejection field ==")
body = c.to_dict()
body["invalid_input_response"] = None
try:
    SecurityContract.from_dict(body)
    print("null invalid_input_response: ACCEPTED (note)")
except Exception as e:
    print("null invalid_input_response: rejected", e)

print("\n== D: v3 argv missing rejection fields ==")
body = dict(BASE)
body["input_mode"] = "argv"
for k in (
    "invalid_input_response",
    "max_valid_input_bytes",
    "invalid_exit_code",
    "invalid_stdout",
    "invalid_stderr",
):
    body.pop(k, None)
try:
    SecurityContract(**body)
    print("v3 argv missing: ACCEPTED (bad)")
except Exception as e:
    print("v3 argv missing: rejected", e)

print("\n== E: v2 + input_mode ==")
p = "../canonical/fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"
v2 = json.load(open(p))
v2["input_mode"] = "none"
try:
    SecurityContract.from_dict(v2)
    print("v2+input_mode: ACCEPTED (bad)")
except Exception as e:
    print("v2+input_mode: rejected", e)

print("\n== F: CWE121 v2 hash ==")
v2 = json.load(open(p))
print(SecurityContract.from_dict(v2).sha256())
