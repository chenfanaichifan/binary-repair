#!/usr/bin/env python3
"""Run the frozen manifest against two ELFs and compare behaviour byte-for-byte.

Gate 4 (unchanged Route B round trip) passes only when all six cases produce the
same exit code, stdout and stderr on the original and the patched binary. The
original is expected to be 4/6 (the two invalid cases fail); the patched
unchanged binary must reproduce exactly that 4/6.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def run(elf: Path, arg: str) -> dict:
    try:
        p = subprocess.run(
            [str(elf), arg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
        )
        return {
            "returncode": p.returncode,
            "stdout_hex": p.stdout.hex(),
            "stderr_hex": p.stderr.hex(),
        }
    except subprocess.TimeoutExpired as exc:
        return {"timeout": True, "stdout_hex": (exc.stdout or b"").hex(),
                "stderr_hex": (exc.stderr or b"").hex(), "returncode": None}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(original: Path, patched: Path, tests: Path) -> dict:
    cases = []
    for name in ("valid.json", "invalid.json"):
        data = json.loads((tests / name).read_text(encoding="utf-8"))
        rows = data.get("tests") or []
        if not rows:
            raise ValueError(f"{name} contains no frozen cases")
        for case in rows:
            cases.append((name, case))
    if not cases:
        raise ValueError("no frozen cases")

    rows = []
    original_ok = True
    for name, case in cases:
        arg = case["argv"][1]
        before = run(original, arg)
        after = run(patched, arg)
        expected = case["expected"]
        # A timeout/None exit is inconclusive, never "same".
        complete = (
            before.get("timeout") is not True and after.get("timeout") is not True
            and before.get("returncode") is not None and after.get("returncode") is not None
        )
        # The original must exhibit the frozen pre-repair behaviour.  In
        # particular the invalid cases must NOT already match the repaired
        # expected result; otherwise a matching crash could pass a round trip.
        if case.get("kind") == "valid":
            case_original_ok = (
                before.get("returncode") == expected["return_code"]
                and before.get("stdout_hex") == expected["stdout"].encode().hex()
            )
        else:
            case_original_ok = not (
                before.get("returncode") == expected["return_code"]
                and before.get("stdout_hex") == expected["stdout"].encode().hex()
                and before.get("stderr_hex") == expected["stderr"].encode().hex()
            )
        original_ok = original_ok and case_original_ok
        same = complete and before == after
        rows.append({
            "manifest": name, "id": case["id"], "kind": case["kind"],
            "input_len": len(arg.encode()), "original": before, "patched": after,
            "complete": complete, "original_ok": case_original_ok, "same": same,
        })
    passed = sum(1 for row in rows if row["same"] and row["complete"] and row["original_ok"])
    return {
        "original_sha256": sha256(original), "patched_sha256": sha256(patched),
        "original_size": original.stat().st_size, "patched_size": patched.stat().st_size,
        "cases": rows, "same_count": passed, "total": len(rows),
        "original_ok": original_ok,
        "gate4_pass": bool(rows) and original_ok and passed == len(rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--patched", type=Path, required=True)
    ap.add_argument("--tests", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        result = compare(args.original, args.patched, args.tests)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"run_manifest_compare: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in
                      ("same_count", "total", "gate4_pass",
                       "original_sha256", "patched_sha256")}, indent=2))
    return 0 if result["gate4_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
