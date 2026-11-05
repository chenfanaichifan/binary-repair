#!/usr/bin/env python3
"""Run a fixture's valid/invalid matrix against a built binary and print a table.

Usage: matrix.py <fixture-dir> [binary-name]

Reads tests/valid.json and tests/invalid.json, substitutes the binary name for
argv[0], executes each case with an exact argv list (no shell), and compares
return code, stdout and stderr with the recorded expectation.  Bytes are
compared exactly; on a mismatch both sides are shown escaped.
"""
import json
import os
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: matrix.py <fixture-dir> [binary-name]", file=sys.stderr)
        return 2
    root = sys.argv[1]
    binary = sys.argv[2] if len(sys.argv) > 2 else "original.elf"
    os.chdir(root)

    rows = []
    for name in ("tests/valid.json", "tests/invalid.json"):
        doc = json.load(open(name, encoding="utf-8"))
        for case in doc["tests"]:
            binary_path = os.path.join(os.getcwd(), binary)
            argv = [binary_path] + list(case["argv"][1:])
            proc = subprocess.run(argv, capture_output=True)
            out = proc.stdout.decode("utf-8", "backslashreplace")
            err = proc.stderr.decode("utf-8", "backslashreplace")
            exp = case["expected"]
            ok = (
                proc.returncode == exp["return_code"]
                and out == exp["stdout"]
                and err == exp["stderr"]
            )
            rows.append([case["id"], case["kind"], proc.returncode, out, err, "MATCH" if ok else "DIFF"])

    head = "%-17s %-9s %4s  %-30s %-14s %s" % ("case", "kind", "rc", "stdout", "stderr", "verdict")
    print(head)
    print("-" * len(head))
    for case_id, kind, rc, out, err, verdict in rows:
        print("%-17s %-9s %4d  %-30s %-14s %s"
              % (case_id, kind, rc, repr(out), repr(err), verdict))
    matched = sum(1 for r in rows if r[5] == "MATCH")
    print()
    print("MATCH %d / %d" % (matched, len(rows)))
    return 0 if matched == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
