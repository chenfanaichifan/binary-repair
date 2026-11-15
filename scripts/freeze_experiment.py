#!/usr/bin/env python3
"""Freeze one experiment baseline into a hashed profile.

The profile is used by the 60-run matrix; it intentionally refuses a dirty
working tree so later results cannot silently mix code revisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _test_count(path: Path) -> dict:
    if not path.is_file():
        return {"status": "unavailable"}
    root = ET.parse(path).getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    return {k: suite.get(k) for k in ("tests", "failures", "errors", "skipped", "time")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--profile-id", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--junit", type=Path,
                    default=ROOT / "artifacts/binary-universal-v5-2026-11-13/macos-junit.xml")
    args = ap.parse_args()
    if _git("status", "--porcelain"):
        print("freeze refused: working tree is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    files = {
        "benchmark": ROOT / "fixtures/repair-benchmark/cases.json",
        "verifier_module": ROOT / "app/services/independent_verifier.py",
        "verification_semantics": ROOT / "app/services/verification_semantics.py",
        "patch_plan_schema": ROOT / "contracts/patch-plan.schema.json",
        "verification_schema": ROOT / "contracts/verification.schema.json",
        "repairspec_module": ROOT / "app/services/repair_spec.py",
        "p16r3_verification": ROOT / "artifacts/independent-verification-p16r3-2026-11-16/verification.json",
    }
    profile = {
        "schema_version": 1,
        "profile_id": args.profile_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": commit,
        "verifier_profile": "P16R3_PLAN_AWARE",
        "authorization_profile": "STATIC_REFERENCE_ONLY",
        "semantic_trace": "NOT_RUN",
        "fuzzing": "NOT_RUN",
        "models": args.models,
        "hashes": {name: _sha(path) for name, path in files.items() if path.is_file()},
        "missing_inputs": [name for name, path in files.items() if not path.is_file()],
        "tests": _test_count(args.junit),
        "case_ids": [c["id"] for c in json.loads(files["benchmark"].read_text())["cases"]],
        "notes": ["P16-R3 strict plan-aware profile; not a policy-issued authorization profile"],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    lines = ["# Frozen experiment profile", "",
             f"- profile: `{args.profile_id}`",
             f"- source commit: `{commit}`",
             f"- verifier profile: `P16R3_PLAN_AWARE`",
             "- authorization profile: `STATIC_REFERENCE_ONLY`",
             f"- tests: `{profile['tests']}`", ""]
    (args.out / "README.md").write_text("\n".join(lines) + "\n")
    sums = [f"{_sha(p)}  {p.name}" for p in sorted(args.out.iterdir())
            if p.is_file() and p.name != "SHA256SUMS"]
    (args.out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(json.dumps({"out": str(args.out), "commit": commit, "tests": profile["tests"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
