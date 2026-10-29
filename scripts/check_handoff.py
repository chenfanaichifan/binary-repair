"""Validate a producer -> consumer handoff package.

Why this exists
---------------
The team lost time because "I sent it" / "I never got it" could not be settled
without reading chat history. A handoff is now a directory with a machine-checked
manifest, and BOTH sides run this same checker. PASS or FAIL is the answer; the
command output is the evidence, not either person's recollection.

Package layout (interface_version 1)
------------------------------------
    <package>/
      handoff.json          required, schema below
      SHA256SUMS            required, "sha256sum" format, covers every file
                            except itself, sorted bytewise by path (LC_ALL=C)
      README.md             optional human note
      <evidence files...>   every evidence file must be listed in handoff.json

handoff.json
------------
    {
      "id": "m3-2026-10-30-gate4",
      "from": "M3",
      "to": "M5",
      "task": "T3.1",
      "status": "delivered" | "verified" | "failed" | "blocked",
      "interface_version": 1,
      "created_at": "2026-10-30T10:00:00+08:00",
      "deadline": "2026-10-30T18:00:00+08:00",
      "artifacts": [
        {"path": "logs/run.log", "sha256": "<64 hex>", "role": "guest run log"}
      ],
      "commands": ["cmd that produced the evidence"],
      "expected": ["expected observation"],
      "observed": ["observed observation"],
      "requested_action": "what the consumer must do next",
      "notes": "free text, optional"
    }

Rules enforced
--------------
* required keys, types and status vocabulary;
* interface_version == 1;
* every artifact path is relative, stays inside the package, exists, and its
  sha256 matches;
* every evidence file in the package is listed in `artifacts`;
* SHA256SUMS exists, parses as "<64 hex>  <path>", covers every file except
  itself, matches the files on disk, and is sorted bytewise by path;
* `status == "blocked"` requires a non-empty `notes` and may have no artifacts;
  every other status requires at least one artifact.

Usage
-----
    python scripts/check_handoff.py <package-dir>
    python scripts/check_handoff.py <package-dir> --expect-from M3 --expect-to M5
    python scripts/check_handoff.py <package-dir> --json

Exit code 0 = PASS, 1 = FAIL (every failure is printed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

INTERFACE_VERSION = 1
STATUSES = {"delivered", "verified", "failed", "blocked"}
REQUIRED_STR = ("id", "from", "to", "task", "created_at", "deadline", "requested_action")
REQUIRED_LIST = ("commands", "expected", "observed")
METADATA_FILES = {"handoff.json", "SHA256SUMS", "README.md"}
SUM_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path_text: str, package: Path) -> tuple[Path | None, str | None]:
    if not isinstance(path_text, str) or not path_text:
        return None, "artifact path is not a non-empty string"
    candidate = Path(path_text)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, f"artifact path must be relative and inside the package: {path_text}"
    resolved = (package / candidate).resolve()
    try:
        resolved.relative_to(package.resolve())
    except ValueError:
        return None, f"artifact path escapes the package: {path_text}"
    return resolved, None


def check_package(
    package: Path,
    *,
    expect_from: str | None = None,
    expect_to: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    summary: dict[str, Any] = {
        "id": "",
        "task": "",
        "from": "",
        "to": "",
        "status": "",
        "artifacts": 0,
        "sums": 0,
        "interface_version": None,
    }

    if not package.is_dir():
        return [f"package directory not found: {package}"], summary

    handoff_path = package / "handoff.json"
    if not handoff_path.is_file():
        return ["missing handoff.json"], summary
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"handoff.json is not valid JSON: {exc}"], summary
    if not isinstance(handoff, dict):
        return ["handoff.json must be an object"], summary

    for key in REQUIRED_STR:
        if not isinstance(handoff.get(key), str) or not handoff.get(key).strip():
            errors.append(f"handoff.json: required non-empty string missing: {key}")
    for key in REQUIRED_LIST:
        value = handoff.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            errors.append(f"handoff.json: required non-empty list of strings missing: {key}")
    if handoff.get("interface_version") != INTERFACE_VERSION:
        errors.append(
            f"handoff.json: interface_version must be {INTERFACE_VERSION}, "
            f"got {handoff.get('interface_version')!r}"
        )
    status = handoff.get("status")
    if status not in STATUSES:
        errors.append(f"handoff.json: status must be one of {sorted(STATUSES)}, got {status!r}")

    if expect_from and handoff.get("from") != expect_from:
        errors.append(f"handoff.json: from={handoff.get('from')!r}, expected {expect_from!r}")
    if expect_to and handoff.get("to") != expect_to:
        errors.append(f"handoff.json: to={handoff.get('to')!r}, expected {expect_to!r}")

    summary.update(
        {
            "id": handoff.get("id", ""),
            "task": handoff.get("task", ""),
            "from": handoff.get("from", ""),
            "to": handoff.get("to", ""),
            "status": status if isinstance(status, str) else "",
            "interface_version": handoff.get("interface_version"),
        }
    )

    artifacts_raw = handoff.get("artifacts")
    if not isinstance(artifacts_raw, list):
        errors.append("handoff.json: artifacts must be a list")
        artifacts_raw = []
    if status != "blocked" and not artifacts_raw:
        errors.append("handoff.json: at least one artifact is required unless status is blocked")
    if status == "blocked" and not str(handoff.get("notes") or "").strip():
        errors.append("handoff.json: status blocked requires non-empty notes")

    listed: dict[str, str] = {}
    for index, item in enumerate(artifacts_raw):
        if not isinstance(item, dict):
            errors.append(f"handoff.json: artifacts[{index}] must be an object")
            continue
        role = item.get("role")
        if not isinstance(role, str) or not role.strip():
            errors.append(f"handoff.json: artifacts[{index}].role must be a non-empty string")
        raw_path = item.get("path")
        checksum = item.get("sha256")
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            errors.append(f"handoff.json: artifacts[{index}].sha256 must be a lowercase hex digest")
            continue
        resolved, path_error = _safe_relative(raw_path, package)
        if path_error:
            errors.append(f"handoff.json: artifacts[{index}]: {path_error}")
            continue
        assert resolved is not None
        if not resolved.is_file():
            errors.append(f"artifact file does not exist: {raw_path}")
            continue
        actual = sha256_file(resolved)
        if actual != checksum:
            errors.append(f"artifact hash mismatch: {raw_path} expected {checksum} actual {actual}")
            continue
        if raw_path in listed:
            errors.append(f"artifact listed twice: {raw_path}")
            continue
        listed[raw_path] = checksum

    sums_path = package / "SHA256SUMS"
    sums_rows: dict[str, str] = {}
    if not sums_path.is_file():
        errors.append("missing SHA256SUMS")
    else:
        try:
            sums_lines = sums_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"cannot read SHA256SUMS: {exc}")
            sums_lines = []
        for line_number, line in enumerate(sums_lines, 1):
            if not line.strip():
                continue
            match = SUM_LINE.match(line)
            if not match:
                errors.append(f"SHA256SUMS:{line_number}: expected '<64 hex>  <path>', got {line!r}")
                continue
            digest, raw_path = match.group(1), match.group(2)
            if raw_path in sums_rows:
                errors.append(f"SHA256SUMS: duplicate path {raw_path}")
            sums_rows[raw_path] = digest
        expected_order = sorted(sums_rows, key=lambda value: value.encode("utf-8"))
        if list(sums_rows) != expected_order:
            errors.append("SHA256SUMS is not sorted bytewise by path (LC_ALL=C)")
        for raw_path, expected in sums_rows.items():
            resolved, path_error = _safe_relative(raw_path, package)
            if path_error:
                errors.append(f"SHA256SUMS: {path_error}")
                continue
            assert resolved is not None
            if not resolved.is_file():
                errors.append(f"SHA256SUMS lists a missing file: {raw_path}")
                continue
            actual = sha256_file(resolved)
            if actual != expected:
                errors.append(f"SHA256SUMS hash mismatch: {raw_path} expected {expected} actual {actual}")
        summary["sums"] = len(sums_rows)

    files_on_disk = {
        str(path.relative_to(package)).replace("\\", "/")
        for path in package.rglob("*")
        if path.is_file()
    }
    coverage_files = files_on_disk - {"SHA256SUMS"}
    covered = set(sums_rows)
    missing_from_sums = sorted(coverage_files - covered)
    for raw_path in missing_from_sums:
        errors.append(f"file not covered by SHA256SUMS: {raw_path}")
    extra_sums = sorted(covered - coverage_files)
    for raw_path in extra_sums:
        errors.append(f"SHA256SUMS lists a file that is not in the package: {raw_path}")
    evidence_files = files_on_disk - METADATA_FILES
    for raw_path in sorted(evidence_files - set(listed)):
        errors.append(f"evidence file not listed in handoff.json artifacts: {raw_path}")
    summary["artifacts"] = len(listed)
    return errors, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/check_handoff.py")
    parser.add_argument("package", type=Path, help="handoff package directory")
    parser.add_argument("--expect-from", default=None)
    parser.add_argument("--expect-to", default=None)
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)

    errors, summary = check_package(
        args.package,
        expect_from=args.expect_from,
        expect_to=args.expect_to,
    )
    if args.json:
        print(json.dumps({"pass": not errors, "errors": errors, "summary": summary}, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"FAIL  {error}")
        print(
            f"FAIL  handoff {summary['id']!r} task={summary['task']!r} "
            f"from={summary['from']!r} to={summary['to']!r} errors={len(errors)}"
        )
    else:
        print(
            f"PASS  handoff {summary['id']!r} task={summary['task']!r} "
            f"from={summary['from']!r} to={summary['to']!r} "
            f"artifacts={summary['artifacts']} sums={summary['sums']} "
            f"interface={summary['interface_version']}"
        )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
