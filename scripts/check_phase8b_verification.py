#!/usr/bin/env python3
"""Validate the committed Phase-8B real-verification evidence artifact.

The Phase-8B benchmark runner writes per-candidate evidence (original/candidate
bytes, patch plan, verifier report) plus a SHA256SUMS file.  This checker is a
read-only release/evidence probe: it verifies that the committed results claim
at least the requested number of independently verified candidates, that every
such claim is internally consistent (decision=verified, executed oracle, layout
replay, ABI block, verifier identity), and that ``false_verified`` is zero.

It never executes a binary, calls a model, or writes repository files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "artifacts" / "phase8b-benchmark-2026-11-16" / "results.json"
SAMPLES = ROOT / "artifacts" / "phase8b-benchmark-2026-11-16" / "samples"
REQUIRED_FILES = (
    "original.bin",
    "candidate.bin",
    "outcome.json",
    "metadata.json",
    "plan.json",
    "verifier-report.json",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_sums(directory: Path) -> tuple[dict[str, str], list[str]]:
    problems: list[str] = []
    path = directory / "SHA256SUMS"
    entries: dict[str, str] = {}
    if not path.is_file():
        return entries, [f"missing {path}"]
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            problems.append(f"SHA256SUMS line {line_no} is malformed")
            continue
        digest, relative = parts[0].lower(), parts[1].strip()
        target = (directory / relative).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            problems.append(f"SHA256SUMS line {line_no} escapes the artifact directory")
            continue
        if not target.is_file():
            problems.append(f"SHA256SUMS references missing file: {relative}")
        elif _sha256_file(target) != digest:
            problems.append(f"SHA256SUMS digest mismatch: {relative}")
        entries[relative] = digest
    return entries, problems


def check(path: Path = RESULTS, *, min_real: int = 1) -> dict[str, Any]:
    result: dict[str, Any] = {
        "kind": "phase8b_verification_evidence_check",
        "results": str(path),
        "ok": False,
        "violations": [],
        "verified_samples": [],
        "real_verification_count": 0,
        "false_verified": None,
        "not_run": [],
    }
    if not path.is_file():
        result["not_run"] = [f"missing results artifact: {path}"]
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result["violations"].append(f"results unreadable: {type(exc).__name__}: {exc}")
        return result
    if payload.get("kind") != "repair_benchmark_results":
        result["violations"].append(f"unexpected results kind: {payload.get('kind')!r}")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    false_verified = summary.get("false_verified")
    result["false_verified"] = false_verified
    if false_verified != 0:
        result["violations"].append(f"false_verified must be 0, got {false_verified!r}")
    if summary.get("independently_verified") != sum(
            1 for row in rows if row.get("independently_verified") is True):
        result["violations"].append(
            "summary.independently_verified does not match verified rows")
    for row in rows:
        if row.get("independently_verified") is not True:
            continue
        sid = str(row.get("sample_id"))
        result["real_verification_count"] += 1
        result["verified_samples"].append(sid)
        sample_dir = SAMPLES / sid
        for name in REQUIRED_FILES:
            if not (sample_dir / name).is_file():
                result["violations"].append(f"{sid}: missing {name}")
        if row.get("verifier_decision") != "verified":
            result["violations"].append(f"{sid}: verifier_decision is not verified")
        if row.get("oracle_status") != "pass":
            result["violations"].append(f"{sid}: oracle_status is not pass")
        if row.get("layout_status") != "passed":
            result["violations"].append(f"{sid}: layout_status is not passed")
        if row.get("real_verification") is not True:
            result["violations"].append(f"{sid}: real_verification flag is not true")
        if not isinstance(row.get("patch_plan_sha256"), str) or len(
                row["patch_plan_sha256"]) != 64:
            result["violations"].append(f"{sid}: patch_plan_sha256 is missing")
        if not isinstance(row.get("verifier_id"), str) or not row["verifier_id"]:
            result["violations"].append(f"{sid}: verifier_id is missing")
        if not row.get("abi_blocks"):
            result["violations"].append(f"{sid}: no ABI evidence block recorded")
        report_path = sample_dir / "verifier-report.json"
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                result["violations"].append(
                    f"{sid}: verifier report unreadable: {type(exc).__name__}: {exc}")
            else:
                if report.get("decision") != "verified":
                    result["violations"].append(
                        f"{sid}: saved verifier report is not verified")
                if report.get("independence", {}).get("ok") is not True:
                    result["violations"].append(
                        f"{sid}: saved verifier report independence is not ok")
    if result["real_verification_count"] < min_real:
        result["not_run"] = [
            f"only {result['real_verification_count']} independently verified "
            f"sample(s); at least {min_real} required"]
        result["violations"].append(
            f"real verification count {result['real_verification_count']} < {min_real}")
    _, sums_problems = _parse_sums(SAMPLES.parent)
    result["violations"].extend(sums_problems)
    result["ok"] = not result["violations"] and not result["not_run"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="check committed Phase-8B verification evidence")
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--min-real", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.results, min_real=args.min_real)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    if report["ok"]:
        return 0
    return 2 if report["not_run"] and not any(
        item for item in report["violations"] if "real verification count" not in item
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
