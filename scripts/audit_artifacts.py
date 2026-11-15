#!/usr/bin/env python3
"""Audit benchmark artifacts without inventing or replacing historical runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _find_summary(runs: list[Path], case_id: str) -> dict | None:
    for run_dir in runs:
        summary = run_dir / "summary.json"
        if not summary.is_file():
            continue
        try:
            data = json.loads(summary.read_text())
        except json.JSONDecodeError:
            continue
        for record in data.get("cases") or []:
            if str((record.get("case") or {}).get("id")) == case_id:
                return {"run_dir": run_dir, "record": record}
    return None


def audit_case(case: dict, runs: list[Path], verifier_case: dict | None) -> dict:
    original = ROOT / case["binary"]
    poc = ROOT / case["poc"]
    found = _find_summary(runs, case["id"]) if runs else None
    candidate = None
    if found:
        artifact = (found["record"].get("candidate") or {}).get("candidate_artifact")
        if artifact:
            candidate = Path(artifact)
            if not candidate.is_absolute():
                candidate = found["run_dir"] / candidate
    status = "ARTIFACT_MISSING_CONFIRMED"
    reason = "no selected run summary"
    if not original.is_file():
        reason = "original ELF missing"
    elif not poc.is_file():
        reason = "PoC manifest missing"
    elif candidate is not None and candidate.is_file():
        status = "RECOVERED_HISTORICAL"
        reason = "candidate from original run record"
    elif found:
        status = "ARTIFACT_MISSING_CONFIRMED"
        reason = "run record exists but candidate artifact is missing"
    verified = (verifier_case or {}).get("decision")
    return {
        "case_id": case["id"],
        "status": status,
        "reason": reason,
        "original": {"path": str(original), "sha256": _sha(original)},
        "poc": {"path": str(poc), "sha256": _sha(poc)},
        "candidate": {"path": str(candidate) if candidate else None,
                      "sha256": _sha(candidate) if candidate and candidate.is_file() else None},
        "run_dir": str(found["run_dir"]) if found else None,
        "independent_verification": verified,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--runs", nargs="*", type=Path, default=[])
    ap.add_argument("--verification", type=Path)
    args = ap.parse_args()
    manifest = json.loads(args.cases.read_text())
    verification = {}
    if args.verification and args.verification.is_file():
        for item in json.loads(args.verification.read_text()).get("cases") or []:
            verification[str(item.get("case_id"))] = item
    records = [audit_case(case, args.runs, verification.get(str(case["id"])))
               for case in manifest["cases"]]
    args.out.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "kind": "artifact_audit", "cases": records}
    (args.out / "audit.json").write_text(json.dumps(payload, indent=2) + "\n")
    counts = {}
    for item in records:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    lines = ["# Artifact audit", "", f"- cases: {len(records)}", f"- status: `{counts}`", ""]
    (args.out / "README.md").write_text("\n".join(lines) + "\n")
    sums = [f"{_sha(p)}  {p.name}" for p in sorted(args.out.iterdir())
            if p.is_file() and p.name != "SHA256SUMS"]
    (args.out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(json.dumps({"out": str(args.out), "cases": len(records), "status": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
