#!/usr/bin/env python3
"""Run the frozen manifest against two ELFs and compare behaviour byte-for-byte.

Gate 4 (unchanged Route B round trip) passes only when every frozen case
produces the same exit code, stdout and stderr on the original and the patched
binary. The historical argv/stdin matrix is 4 valid + 2 invalid; the original
is expected to fail the invalid cases. A no-input sample has exactly one valid
case and no invalid manifest; its invalid category is not applicable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def run(elf: Path, arg: str | None = None, *, stdin_text: str | None = None) -> dict:
    command = [str(elf)] + ([arg] if arg is not None else [])
    try:
        p = subprocess.run(
            command,
            input=stdin_text.encode() if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        return {
            "returncode": p.returncode,
            "stdout_hex": p.stdout.hex(),
            "stderr_hex": p.stderr.hex(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "timeout": True,
            "stdout_hex": (exc.stdout or b"").hex(),
            "stderr_hex": (exc.stderr or b"").hex(),
            "returncode": None,
        }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract_mode(contract: Path) -> str:
    data = json.loads(contract.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contract must be a JSON object")
    mode = data.get("input_mode", "argv")
    if data.get("schema_version") == 3 and mode not in {"argv", "stdin", "none"}:
        raise ValueError(f"unsupported input_mode: {mode!r}")
    return mode


def _no_input_compare(original: Path, patched: Path, tests: Path) -> dict:
    if (tests / "invalid.json").exists():
        raise ValueError(
            "input_mode none must not ship tests/invalid.json; "
            "an empty file is still a placeholder"
        )
    data = json.loads((tests / "valid.json").read_text(encoding="utf-8"))
    cases = data.get("tests") if isinstance(data, dict) else None
    if not isinstance(cases, list) or len(cases) != 1:
        raise ValueError("input_mode none requires exactly 1 valid case")
    case = cases[0]
    if case.get("kind") != "valid":
        raise ValueError("input_mode none's single case must be kind 'valid'")
    argv = case.get("argv") or []
    if len(argv) != 1:
        raise ValueError("input_mode none invokes the binary with no arguments")
    if case.get("stdin_literal") is not None or case.get("stdin_artifact") is not None:
        raise ValueError("input_mode none must not supply stdin")
    before = run(original)
    after = run(patched)
    complete = (
        before.get("timeout") is not True
        and after.get("timeout") is not True
        and before.get("returncode") is not None
        and after.get("returncode") is not None
    )
    same = complete and before == after
    return {
        "original_sha256": sha256(original),
        "patched_sha256": sha256(patched),
        "original_size": original.stat().st_size,
        "patched_size": patched.stat().st_size,
        "input_mode": "none",
        "invalid": "not_applicable",
        "cases": [
            {
                "manifest": "valid.json",
                "id": case.get("id"),
                "kind": "valid",
                "input_len": 0,
                "original": before,
                "patched": after,
                "complete": complete,
                "original_ok": True,
                "same": same,
            }
        ],
        "same_count": 1 if same else 0,
        "total": 1,
        "original_ok": True,
        "gate4_pass": same,
    }


def compare(
    original: Path, patched: Path, tests: Path, *, input_mode: str = "argv"
) -> dict:
    if input_mode not in {"argv", "stdin", "none"}:
        raise ValueError(f"unsupported input_mode: {input_mode!r}")
    if input_mode == "none":
        return _no_input_compare(original, patched, tests)

    cases = []
    for name in ("valid.json", "invalid.json"):
        path = tests / name
        if not path.is_file():
            raise ValueError(f"missing {name} for input_mode {input_mode}")
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("tests") or []
        for case in rows:
            cases.append((name, case))
    if not cases:
        raise ValueError("no frozen cases")

    rows = []
    original_ok = True
    for name, case in cases:
        argv = case.get("argv") or []
        if len(argv) < 2:
            raise ValueError(f"case {case.get('id')!r} has no program argument")
        arg = argv[1]
        stdin_text = case.get("stdin_literal") if input_mode == "stdin" else None
        if input_mode == "stdin":
            before = run(original, arg, stdin_text=stdin_text)
            after = run(patched, arg, stdin_text=stdin_text)
        else:
            before = run(original, arg)
            after = run(patched, arg)
        expected = case["expected"]
        # A timeout/None exit is inconclusive, never "same".
        complete = (
            before.get("timeout") is not True
            and after.get("timeout") is not True
            and before.get("returncode") is not None
            and after.get("returncode") is not None
        )
        # The original must exhibit the frozen pre-repair behaviour. In
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
        rows.append(
            {
                "manifest": name,
                "id": case["id"],
                "kind": case["kind"],
                "input_len": len(arg.encode()),
                "original": before,
                "patched": after,
                "complete": complete,
                "original_ok": case_original_ok,
                "same": same,
            }
        )
    passed = sum(1 for row in rows if row["same"] and row["complete"] and row["original_ok"])
    return {
        "original_sha256": sha256(original),
        "patched_sha256": sha256(patched),
        "original_size": original.stat().st_size,
        "patched_size": patched.stat().st_size,
        "input_mode": input_mode,
        "invalid": "measured",
        "cases": rows,
        "same_count": passed,
        "total": len(rows),
        "original_ok": original_ok,
        "gate4_pass": bool(rows) and original_ok and passed == len(rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--patched", type=Path, required=True)
    ap.add_argument("--tests", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--input-mode", choices=("argv", "stdin", "none"), default=None)
    ap.add_argument("--contract", type=Path)
    args = ap.parse_args()

    mode = args.input_mode or "argv"
    if args.contract is not None:
        mode = _contract_mode(args.contract)

    try:
        result = compare(args.original, args.patched, args.tests, input_mode=mode)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"run_manifest_compare: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "input_mode": result["input_mode"],
                "invalid": result["invalid"],
                "same_count": result["same_count"],
                "total": result["total"],
                "gate4_pass": result["gate4_pass"],
                "original_sha256": result["original_sha256"],
                "patched_sha256": result["patched_sha256"],
            },
            indent=2,
        )
    )
    return 0 if result["gate4_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
