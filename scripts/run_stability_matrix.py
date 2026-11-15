#!/usr/bin/env python3
"""Run independent repeated repair experiments and aggregate stability.

One subprocess/out-dir per model/case/repeat is used deliberately: the legacy
``--repeats`` flag keeps one chosen record, which is not sufficient for a
stability rate.  Live provider calls require BINARYREPAIR_LIVE_AI=1.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from verify_repair_benchmark import verify_case  # noqa: E402


def _parse(spec: str) -> tuple[str, str]:
    provider, model = spec.split(":", 1)
    return provider.strip(), model.strip()


def _run_one(spec: str, case_id: str, run_index: int,
             args: argparse.Namespace, case: dict | None = None) -> dict:
    provider, model = _parse(spec)
    slug = (provider + "-" + model).replace("/", "_").replace(":", "_")
    out = args.out / slug / case_id / f"run-{run_index}"
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["BINARYREPAIR_PROVIDER"] = provider
    env["BINARYREPAIR_ASSISTANT_MODEL"] = model
    env["BINARYREPAIR_STRICT_MODEL_IDENTITY"] = "1"
    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_hard_benchmark.py"),
        "--out", str(out), "--cases", str(args.cases), "--client", "real",
        "--allow-calls", "--repair-plan", "--abi-strict", "--semantic-retry",
        "--max-repair-rounds", str(args.max_repair_rounds), "--repeats", "1",
        "--case", case_id,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                          text=True, timeout=args.timeout)
    record = {
        "spec": spec, "provider": provider, "model": model,
        "case_id": case_id, "run": run_index, "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-800:], "experiment_id": args.experiment_id,
    }
    try:
        summary = json.loads((out / "summary.json").read_text())
        case = (summary.get("cases") or [{}])[0]
        candidate = case.get("candidate") or {}
        record.update({
            "status": "completed",
            "gate": candidate.get("gate"),
            "repair_status": candidate.get("repair_status"),
            "attempts": len(case.get("ai_attempts") or []),
            "plan_status": ((case.get("ai_attempts") or [{}])[0]
                            .get("plan_status")),
            "candidate_sha256": candidate.get("candidate_sha256"),
            "candidate_artifact": candidate.get("candidate_artifact"),
        })
        verification_status = "NOT_RUN"
        if case is not None:
            verification = verify_case(out, case, case)
            verification_status = str(verification.get("status") or "NOT_RUN")
            if (not candidate.get("candidate_artifact")
                    and str(candidate.get("gate")) == "no_candidate"):
                verification_status = "NO_CANDIDATE"
            record["verification_status"] = verification_status
            record["verification"] = verification
        record["verified"] = verification_status == "verified"
        manifest = {
            "schema_version": 2, "run_kind": "stability_run",
            "experiment_id": args.experiment_id,
            "profile": str(args.profile) if args.profile else None,
            "spec": spec, "model": model, "case_id": case_id,
            "run": run_index,
            "candidate_artifact": record.get("candidate_artifact"),
            "candidate_sha256": record.get("candidate_sha256"),
            "generator_gate": record.get("gate"),
            "verification_status": record.get("verification_status"),
            "status": record.get("status"),
        }
        (out / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # populate independent evidence bundle
        ev = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "repair_evidence.py"),
             "build", "--run", str(out), "--out", str(out / "evidence")],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
        )
        record["evidence_ok"] = ev.returncode == 0
    except Exception as exc:  # noqa: BLE001
        record.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
    return record


def aggregate(records: list[dict]) -> dict:
    eligible = [r for r in records if r.get("status") == "completed"]
    verified = [r for r in eligible if r.get("verified")]
    status_counts: dict[str, int] = {}
    for r in records:
        key = str(r.get("verification_status") or "NOT_RUN")
        status_counts[key] = status_counts.get(key, 0) + 1
    by_model: dict[str, dict] = {}
    by_case: dict[str, dict] = {}
    for r in records:
        model = r["spec"]
        slot = by_model.setdefault(model, {"runs": 0, "verified": 0,
                                           "eligible": 0, "failures": {}})
        slot["runs"] += 1
        if r.get("status") == "completed":
            slot["eligible"] += 1
            if r.get("verified"):
                slot["verified"] += 1
            else:
                key = str(r.get("repair_status") or "UNKNOWN")
                slot["failures"][key] = slot["failures"].get(key, 0) + 1
        case_slot = by_case.setdefault(r["case_id"], {"runs": 0, "verified": 0})
        case_slot["runs"] += 1
        case_slot["verified"] += int(bool(r.get("verified")))
    return {
        "schema_version": 1,
        "kind": "repair_stability",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": len(records),
        "eligible_runs": len(eligible),
        "verified_runs": len(verified),
        "status_counts": status_counts,
        "R_verified": (len(verified) / len(eligible)) if eligible else 0.0,
        "R_robustness": (len(verified) / len(records)) if records else 0.0,
        "per_model": by_model,
        "per_case": by_case,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--cases", type=Path,
                    default=ROOT / "fixtures" / "repair-benchmark" / "cases.json")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--max-repair-rounds", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--experiment-id", default="p18-60")
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if os.environ.get("BINARYREPAIR_LIVE_AI") != "1":
        print("refusing live provider calls without BINARYREPAIR_LIVE_AI=1")
        return 2
    manifest = json.loads(args.cases.read_text())
    by_id = {str(item["id"]): item for item in manifest["cases"]}
    case_ids = list(by_id)
    if args.smoke:
        case_ids = case_ids[:1]
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for spec in args.models:
        for case_id in case_ids:
            for run_index in range(1, max(1, args.repeats) + 1):
                record = _run_one(spec, case_id, run_index, args, by_id.get(case_id))
                records.append(record)
                print(json.dumps({k: record.get(k) for k in
                                  ("spec", "case_id", "run", "status", "gate",
                                   "repair_status", "evidence_ok")}),
                      flush=True)
    report = aggregate(records)
    report["records"] = records
    (args.out / "stability.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Repair stability", "",
             f"- runs: {report['runs']}",
             f"- eligible: {report['eligible_runs']}",
             f"- verified: {report['verified_runs']}",
             f"- R_verified: {report['R_verified']:.3f}",
             f"- R_robustness: {report['R_robustness']:.3f}",
             f"- statuses: `{json.dumps(report['status_counts'])}`", ""]
    (args.out / "README.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: report[k] for k in
                      ("runs", "eligible_runs", "verified_runs", "R_verified")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
