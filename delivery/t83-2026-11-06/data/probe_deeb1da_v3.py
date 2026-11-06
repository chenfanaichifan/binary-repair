import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
CWE121 = ROOT / "fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"

BASE = {
    "schema_version": 3,
    "input_mode": "none",
    "target_entry": "demo",
    "target_signature": "void demo(void)",
    "valid_domain": "no program input",
    "valid_behavior": "exit 0 and print OK",
    "forbidden_behavior": "read after free",
    "dest_capacity_bytes": 50,
    "capacity_includes_terminator": True,
    "authorized_edits": [],
    "allowed_calls": [],
    "environment_assumptions": [],
    "required_obligations": [
        "behaviour",
        "identity",
        "interface",
        "reproducibility",
        "structure",
        "symbolic",
    ],
}


def run_cli(tmp: Path, contract: dict) -> subprocess.CompletedProcess:
    cpath = tmp / "contract.json"
    cpath.write_text(json.dumps(contract), encoding="utf-8")
    tests = tmp / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "valid.json").write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "id": "valid-only",
                        "kind": "valid",
                        "argv": ["./original"],
                        "expected": {"return_code": 0, "stdout": "OK\n", "stderr": ""},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    cand = tmp / "candidate.sh"
    cand.write_text("#!/bin/sh\nprintf 'OK\\n'\nexit 0\n", encoding="utf-8")
    cand.chmod(0o755)
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "routeb/run_manifest_repaired.py"),
            "--binary",
            str(cand),
            "--tests",
            str(tests),
            "--out",
            str(tmp / "manifest-repaired.json"),
            "--contract",
            str(cpath),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


with tempfile.TemporaryDirectory() as d:
    root = Path(d)

    print("== v3 none, valid ==")
    tmp = root / "valid"
    tmp.mkdir()
    r = run_cli(tmp, BASE)
    print("rc:", r.returncode)
    print("stdout:", r.stdout.strip())
    if r.returncode == 0:
        art = json.loads((tmp / "manifest-repaired.json").read_text())
        print("artifact valid:", art.get("valid"), "invalid:", art.get("invalid"), "total:", art.get("total"))

    print("\n== v3 none + sentinel ==")
    bad = dict(BASE)
    bad["invalid_input_response"] = "not applicable"
    tmp2 = root / "sentinel"
    tmp2.mkdir()
    r2 = run_cli(tmp2, bad)
    print("rc:", r2.returncode)
    print("stderr:", (r2.stderr.strip().splitlines() or [""])[-1])
    print("artifact exists:", (tmp2 / "manifest-repaired.json").exists())

print("\n== CWE121 hash via shared loader ==")
sys.path.insert(0, str(ROOT))
from routeb.contract_mode import load_contract  # noqa: E402

c = load_contract(CWE121)
print(c.sha256(), c.sha256() == "24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37")
