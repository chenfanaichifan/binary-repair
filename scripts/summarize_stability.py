#!/usr/bin/env python3
"""Summarize a stability matrix without mixing artifact failures with AI runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def summarize(stability: dict) -> dict:
    records = stability.get("records") or []
    statuses: dict[str, int] = {}
    per_model: dict[str, dict] = {}
    per_case: dict[str, dict] = {}
    for record in records:
        model = str(record.get("spec") or "unknown")
        case = str(record.get("case_id") or "unknown")
        status = str(record.get("verification_status") or "NOT_RUN")
        statuses[status] = statuses.get(status, 0) + 1
        for bucket, key in ((per_model, model), (per_case, case)):
            slot = bucket.setdefault(key, {"runs": 0, "verified": 0, "statuses": {}})
            slot["runs"] += 1
            slot["verified"] += int(status == "verified")
            slot["statuses"][status] = slot["statuses"].get(status, 0) + 1
    eligible = sum(1 for r in records if r.get("status") == "completed")
    verified = sum(1 for r in records if r.get("verified"))
    return {
        "schema_version": 1,
        "kind": "stability_summary",
        "planned_runs": len(records),
        "eligible_runs": eligible,
        "verified_runs": verified,
        "R_verified": (verified / eligible) if eligible else 0.0,
        "R_robustness": (verified / len(records)) if records else 0.0,
        "status_counts": statuses,
        "per_model": per_model,
        "per_case": per_case,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stability", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    data = json.loads(args.stability.read_text())
    summary = summarize(data)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Stability summary", "",
             f"- planned: {summary['planned_runs']}",
             f"- eligible: {summary['eligible_runs']}",
             f"- verified: {summary['verified_runs']}",
             f"- R_verified: {summary['R_verified']:.3f}",
             f"- R_robustness: {summary['R_robustness']:.3f}",
             f"- statuses: `{json.dumps(summary['status_counts'])}`", ""]
    (args.out / "README.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: summary[k] for k in
                      ("planned_runs", "eligible_runs", "verified_runs",
                       "R_verified", "status_counts")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
