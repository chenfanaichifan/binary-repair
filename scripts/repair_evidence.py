#!/usr/bin/env python3
"""Build/check a versioned repair evidence bundle from a benchmark run.

The bundle is intentionally derived from immutable run outputs: summary,
per-case candidate binaries and the run manifest.  It contains hashes and
statuses, never provider keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text())


def build(run_dir: Path, out_dir: Path) -> dict[str, Any]:
    summary = _json(run_dir / "summary.json")
    manifest_path = run_dir / "run-manifest.json"
    manifest = _json(manifest_path) if manifest_path.is_file() else {}
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for record in summary.get("cases") or []:
        case = record.get("case") or {}
        candidate = record.get("candidate") or {}
        artifact = candidate.get("candidate_artifact")
        copied = None
        if artifact:
            src = Path(artifact)
            if not src.is_absolute():
                src = run_dir / artifact
            if src.is_file():
                destination = out_dir / "candidates" / f"{case.get('id', 'unknown')}.bin"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, destination)
                copied = str(destination.relative_to(out_dir))
        cases.append({
            "case_id": case.get("id"),
            "input_sha256": record.get("input_sha256"),
            "gate": candidate.get("gate"),
            "repair_status": candidate.get("repair_status"),
            "candidate_sha256": candidate.get("candidate_sha256"),
            "candidate_file": copied,
            "native_failure": candidate.get("native_failure"),
            "plan_status": (record.get("ai_attempts") or [{}])[0].get("plan_status")
            if record.get("ai_attempts") else None,
            "attempts": len(record.get("ai_attempts") or []),
        })
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "kind": "repair_evidence",
        "source_run": str(run_dir),
        "provided_at": summary.get("provider"),
        "provider_metadata": summary.get("provider_metadata"),
        "funnel": summary.get("funnel"),
        "ai_verified": summary.get("ai_verified"),
        "reference_note": "reference fixes are separate and are not AI evidence",
        "manifest": manifest,
        "cases": cases,
        "hashes": {
            "summary.json": _sha(run_dir / "summary.json"),
            **({"run-manifest.json": _sha(manifest_path)} if manifest_path.is_file() else {}),
        },
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    sums = [f"{_sha(p)}  {p.relative_to(out_dir)}"
            for p in sorted(out_dir.rglob("*")) if p.is_file() and p.name != "SHA256SUMS"]
    (out_dir / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    return metadata


def check(bundle: Path) -> list[str]:
    issues: list[str] = []
    metadata_path = bundle / "metadata.json"
    if not metadata_path.is_file():
        return ["missing metadata.json"]
    metadata = _json(metadata_path)
    if metadata.get("schema_version") != SCHEMA_VERSION:
        issues.append("unsupported schema_version")
    for line in (bundle / "SHA256SUMS").read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            issues.append(f"bad SHA256SUMS line: {line!r}")
            continue
        digest, name = parts
        target = bundle / name
        if not target.is_file():
            issues.append(f"missing {name}")
        elif _sha(target) != digest:
            issues.append(f"hash mismatch {name}")
    for relative, digest in (metadata.get("hashes") or {}).items():
        if not (bundle / relative).is_file():
            # source summary is intentionally not copied; only metadata integrity
            continue
        if _sha(bundle / relative) != digest:
            issues.append(f"source hash mismatch {relative}")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--run", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("check")
    c.add_argument("--bundle", type=Path, required=True)
    args = ap.parse_args()
    if args.command == "build":
        metadata = build(args.run, args.out)
        print(json.dumps({"out": str(args.out), "cases": len(metadata["cases"])}))
        return 0
    issues = check(args.bundle)
    print(json.dumps({"ok": not issues, "issues": issues}))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
