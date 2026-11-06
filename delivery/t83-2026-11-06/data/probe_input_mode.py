import copy
import json
import sys

from app.domain.contracts import SecurityContract

base = json.load(open("fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"))


def probe(label, body):
    try:
        c = SecurityContract.from_dict(body)
        print(f"{label}: LOADED hash={c.sha256()}")
        print(f"   invalid_input_response={c.invalid_input_response!r}")
        print(
            "   invalid_exit_code=%r invalid_stdout=%r invalid_stderr=%r"
            % (c.invalid_exit_code, c.invalid_stdout, c.invalid_stderr)
        )
    except Exception as e:
        print(f"{label}: {type(e).__name__}: {e}")


a = copy.deepcopy(base)
a["input_mode"] = "none"
probe("A add input_mode", a)

b = copy.deepcopy(base)
for k in ("invalid_exit_code", "invalid_input_response", "invalid_stderr", "invalid_stdout"):
    b.pop(k, None)
probe("B omit invalid_*", b)

c = copy.deepcopy(base)
c["invalid_input_response"] = "not applicable: the program takes no input"
c["invalid_exit_code"] = 0
c["invalid_stdout"] = ""
c["invalid_stderr"] = ""
probe("C sentinel invalid_*", c)
