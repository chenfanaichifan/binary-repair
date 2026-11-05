#!/usr/bin/env python3
"""Run the frozen manifest against a repaired candidate and check expectations.

Two shapes are supported:

* ``argv`` / ``stdin``: the historical 4-valid + 2-invalid matrix. Each case
  supplies the program argument and optional stdin.
* ``none``: exactly one valid case, no ``invalid.json``, no argument and no
  stdin. The invalid category is **not applicable**, not a failure and not a
  zero-row pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from routeb.contract_mode import load_contract_mode  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            "returncode": None,
            "stdout_hex": (exc.stdout or b"").hex(),
            "stderr_hex": (exc.stderr or b"").hex(),
        }


def _expected(case: dict) -> dict:
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise ValueError(f"case {case.get('id')!r} has no expected object")
    return expected


def _matches(got: dict, expected: dict) -> bool:
    return (
        got.get("returncode") == expected["return_code"]
        and got.get("stdout_hex") == expected["stdout"].encode().hex()
        and got.get("stderr_hex") == expected["stderr"].encode().hex()
    )


def run_manifest(binary: Path, tests: Path, *, input_mode: str = "argv") -> dict:
    if input_mode not in {"argv", "stdin", "none"}:
        raise ValueError(f"unsupported input_mode: {input_mode!r}")

    if input_mode == "none":
        invalid = tests / "invalid.json"
        if invalid.exists():
            raise ValueError(
                "input_mode none must not ship tests/invalid.json; "
                "an empty file is still a placeholder"
            )
        valid = tests / "valid.json"
        if not valid.is_file():
            raise ValueError("input_mode none requires tests/valid.json")
        data = json.loads(valid.read_text(encoding="utf-8"))
        cases = data.get("tests") if isinstance(data, dict) else None
        if not isinstance(cases, list) or len(cases) != 1:
            raise ValueError("input_mode none requires exactly 1 valid case")
        case = cases[0]
        if case.get("kind") != "valid":
            raise ValueError("input_mode none's single case must be kind 'valid'")
        argv = case.get("argv") or []
        if len(argv) != 1:
            raise ValueError(
                "input_mode none invokes the binary with no arguments; "
                "argv must contain only the program name"
            )
        if case.get("stdin_literal") is not None or case.get("stdin_artifact") is not None:
            raise ValueError("input_mode none must not supply stdin")
        expected = _expected(case)
        got = run(binary)
        ok = _matches(got, expected)
        row = {
            "manifest": "valid.json",
            "id": case.get("id"),
            "kind": "valid",
            "input_len": 0,
            "expected": expected,
            "got": got,
            "ok": ok,
        }
        return {
            "binary": str(binary),
            "binary_sha256": sha256(binary),
            "input_mode": "none",
            "invalid": "not_applicable",
            "valid": "1/1" if ok else "0/1",
            "cases": [row],
            "passed": 1 if ok else 0,
            "total": 1,
            "repaired_pass": ok,
        }

    rows = []
    for name in ("valid.json", "invalid.json"):
        path = tests / name
        if not path.is_file():
            raise ValueError(f"missing {name} for input_mode {input_mode}")
        data = json.loads(path.read_text(encoding="utf-8"))
        cases = data.get("tests") if isinstance(data, dict) else None
        if not isinstance(cases, list) or not cases:
            raise ValueError(f"{name} contains no frozen cases")
        for case in cases:
            argv = case.get("argv") or []
            if len(argv) < 2:
                raise ValueError(f"case {case.get('id')!r} has no program argument")
            stdin_text = case.get("stdin_literal") if input_mode == "stdin" else None
            arg = argv[1]
            got = run(binary, arg, stdin_text=stdin_text)
            expected = _expected(case)
            ok = _matches(got, expected)
            rows.append(
                {
                    "manifest": name,
                    "id": case.get("id"),
                    "kind": case.get("kind"),
                    "input_len": len(arg.encode()),
                    "expected": expected,
                    "got": got,
                    "ok": ok,
                }
            )

    passed = sum(1 for row in rows if row["ok"])
    return {
        "binary": str(binary),
        "binary_sha256": sha256(binary),
        "input_mode": input_mode,
        "invalid": "measured",
        "cases": rows,
        "passed": passed,
        "total": len(rows),
        "repaired_pass": passed == len(rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--tests", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--input-mode", choices=("argv", "stdin", "none"), default=None)
    ap.add_argument("--contract", type=Path)
    args = ap.parse_args()

    try:
        mode = args.input_mode or "argv"
        if args.contract is not None:
            mode = load_contract_mode(args.contract)
        result = run_manifest(args.binary, args.tests, input_mode=mode)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"run_manifest_repaired: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "input_mode": result["input_mode"],
                "invalid": result["invalid"],
                "passed": result["passed"],
                "total": result["total"],
                "repaired_pass": result["repaired_pass"],
                "binary_sha256": result["binary_sha256"],
            },
            indent=2,
        )
    )
    return 0 if result["repaired_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
