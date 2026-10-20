import json
import subprocess
import sys

BIN = "./original.elf"
MANIFESTS = ["tests/valid.json", "tests/invalid.json"]

total = 0
passed = 0
for manifest in MANIFESTS:
    with open(manifest, encoding="utf-8") as fh:
        doc = json.load(fh)
    print(f"== {manifest} (case {doc['case_id']}) ==")
    for test in doc["tests"]:
        total += 1
        argv = [BIN] + test["argv"][1:]
        expected = test["expected"]
        proc = subprocess.run(argv, capture_output=True)
        ok = (
            proc.returncode == expected["return_code"]
            and proc.stdout.decode("utf-8", "replace") == expected["stdout"]
            and proc.stderr.decode("utf-8", "replace") == expected["stderr"]
        )
        passed += 1 if ok else 0
        print(
            f"{test['id']:<16} kind={test['kind']:<7} "
            f"rc={proc.returncode} exp_rc={expected['return_code']} "
            f"stdout={proc.stdout!r} exp_stdout={expected['stdout']!r} "
            f"stderr={proc.stderr!r} exp_stderr={expected['stderr']!r} "
            f"{'PASS' if ok else 'FAIL'}"
        )
print(f"== {passed}/{total} passed against the original binary ==")
sys.exit(0)
