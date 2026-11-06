import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "tests")
import test_fixture_intake as t

with tempfile.TemporaryDirectory() as d:
    root = Path(d) / "f2"
    t.build_no_input(root, valid_count=2)
    print("valid_count=2 findings:", [f.code for f in t.check_fixture(root)])

    root2 = Path(d) / "f3"
    t.build_no_input(root2)
    p = root2 / "contract.json"
    data = json.loads(p.read_text())
    data.pop("dest_capacity_bytes", None)
    p.write_text(json.dumps(data, sort_keys=True) + "\n")
    t.write_sums(root2)
    print(
        "missing dest_capacity_bytes findings:",
        [f.code for f in t.check_fixture(root2)],
    )
    out = Path("../../_m4-verify/contract-missing-cap.json")
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print("saved:", out.resolve())
