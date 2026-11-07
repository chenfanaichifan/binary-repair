#!/usr/bin/env python3
"""Execute one Route A candidate under the guest executor's isolation.

No-input only in v1: the candidate receives no argv and empty stdin. The
collector consumes the emitted manifest-repaired.json as V3 behaviour evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True, type=Path)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--tests-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract.get("input_mode") != "none":
        raise SystemExit("run_candidate v1 only supports input_mode=none")
    valid = json.loads((args.tests_dir / "valid.json").read_text(encoding="utf-8"))
    cases = valid.get("tests") or []
    if not isinstance(cases, list) or len(cases) != 1:
        raise SystemExit("no-input Route A requires exactly one valid case")

    case = cases[0]
    expected = case.get("expected") or {}
    try:
        completed = subprocess.run(
            [str(args.candidate.resolve())],
            input=b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        completed = None
    actual_stdout = b"" if completed is None else completed.stdout
    actual_stderr = b"" if completed is None else completed.stderr
    actual_rc = None if completed is None else completed.returncode
    expected_stdout = str(expected.get("stdout", "")).encode("utf-8")
    expected_stderr = str(expected.get("stderr", "")).encode("utf-8")
    expected_rc = expected.get("return_code")
    ok = (
        completed is not None
        and actual_rc == expected_rc
        and actual_stdout == expected_stdout
        and actual_stderr == expected_stderr
    )
    payload = {
        "schema_version": 1,
        "route": "route_a",
        "input_mode": "none",
        "candidate_sha256": sha(args.candidate),
        "candidate_size": args.candidate.stat().st_size,
        "repaired_pass": ok,
        "passed": 1 if ok else 0,
        "total": 1,
        "cases": [
            {
                "id": str(case.get("id", "valid-no-input")),
                "ok": ok,
                "exit_code": actual_rc,
                "stdout_sha256": hashlib.sha256(actual_stdout).hexdigest(),
                "stdout_bytes": len(actual_stdout),
                "stderr_sha256": hashlib.sha256(actual_stderr).hexdigest(),
                "stderr_bytes": len(actual_stderr),
            }
        ],
        "limits": ["single no-input case; behaviour evidence only"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
