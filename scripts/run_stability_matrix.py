#!/usr/bin/env python3
"""Run independent repeated repair experiments and aggregate stability.

One subprocess/out-dir per model/case/repeat is used deliberately: the legacy
``--repeats`` flag keeps one chosen record, which is not sufficient for a
stability rate.  Live provider calls require BINARYREPAIR_LIVE_AI=1.

The runner never treats the generator gate as a final VERIFIED decision.  A
candidate is counted as verified only when the independent verifier returns
that status.  Subprocess timeouts, missing artifacts, planning failures and
verifier errors are kept in separate status buckets so infrastructure failures
do not look like model failures.
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

CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_NAME = "checkpoint.json"
NON_ELIGIBLE_STATUSES = {"ARTIFACT_MISSING", "VERIFIER_ERROR", "TIMEOUT"}


def _parse(spec: str) -> tuple[str, str]:
    provider, model = spec.split(":", 1)
    return provider.strip(), model.strip()


def _slug(spec: str) -> str:
    return spec.replace("/", "_").replace(":", "_")


def _planned_keys(models: list[str], case_ids: list[str], repeats: int) -> list[tuple]:
    return [(spec, case_id, run_index)
            for spec in models
            for case_id in case_ids
            for run_index in range(1, max(1, repeats) + 1)]


def _record_key(record: dict) -> tuple:
    return (str(record.get("spec") or ""),
            str(record.get("case_id") or ""),
            int(record.get("run") or 0))


def _finalize(record: dict, verification_status: str, *, completed: bool = True,
              error: str | None = None) -> dict:
    """Attach the terminal fields used by aggregation and checkpointing."""
    status = str(verification_status or "NOT_RUN")
    record["completed"] = bool(completed)
    record["verification_status"] = status
    record["verified"] = bool(completed and status == "verified")
    record["eligible"] = bool(completed and status not in NON_ELIGIBLE_STATUSES)
    if error:
        record["error"] = error
    if not completed:
        record["status"] = "timeout" if status == "TIMEOUT" else "error"
    else:
        record["status"] = "completed"
    return record


def _timeout_record(spec: str, provider: str, model: str, case_id: str,
                    run_index: int, args: argparse.Namespace,
                    exc: BaseException) -> dict:
    record = {
        "spec": spec, "provider": provider, "model": model,
        "case_id": case_id, "run": run_index,
        "experiment_id": args.experiment_id, "started": True,
        "returncode": None, "timeout_seconds": int(args.timeout),
        "stderr_tail": "",
    }
    return _finalize(record, "TIMEOUT", completed=False,
                     error=f"{type(exc).__name__}: {exc}")


def _verification_status(candidate: dict, record_case: dict,
                         bench_case: dict | None, out: Path) -> tuple[str, dict | None]:
    """Run the independent verifier and classify its outcome."""
    artifact = candidate.get("candidate_artifact")
    gate = str(candidate.get("gate") or "")
    repair_status = str(candidate.get("repair_status") or "")
    if artifact and bench_case is not None:
        try:
            verification = verify_case(out, record_case, bench_case)
        except Exception as exc:  # noqa: BLE001 - verifier failure is evidence
            return "VERIFIER_ERROR", {"error": f"{type(exc).__name__}: {exc}"}
        status = str(verification.get("status") or "NOT_RUN")
        return status, verification
    if gate == "plan_invalid" or repair_status == "PLAN_INVALID":
        return "PLAN_INVALID", None
    if gate == "no_candidate" or repair_status == "NO_CANDIDATE":
        return "NO_CANDIDATE", None
    return "ARTIFACT_MISSING", None


def _run_one(spec: str, case_id: str, run_index: int,
             args: argparse.Namespace, bench_case: dict | None = None) -> dict:
    provider, model = _parse(spec)
    out = args.out / _slug(spec) / case_id / f"run-{run_index}"
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
    record = {
        "spec": spec, "provider": provider, "model": model,
        "case_id": case_id, "run": run_index,
        "experiment_id": args.experiment_id, "started": True,
        "returncode": None, "stderr_tail": "",
    }
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        return _timeout_record(spec, provider, model, case_id, run_index, args, exc)
    record["returncode"] = proc.returncode
    record["stderr_tail"] = proc.stderr[-800:]
    try:
        summary_path = out / "summary.json"
        if not summary_path.is_file():
            return _finalize(record, "ARTIFACT_MISSING", completed=True,
                             error="summary.json missing after subprocess")
        summary = json.loads(summary_path.read_text())
        record_case = (summary.get("cases") or [{}])[0]
        candidate = record_case.get("candidate") or {}
        record.update({
            "gate": candidate.get("gate"),
            "repair_status": candidate.get("repair_status"),
            "attempts": len(record_case.get("ai_attempts") or []),
            "plan_status": ((record_case.get("ai_attempts") or [{}])[0]
                            .get("plan_status")),
            "candidate_sha256": candidate.get("candidate_sha256"),
            "candidate_artifact": candidate.get("candidate_artifact"),
        })
        verification_status, verification = _verification_status(
            candidate, record_case, bench_case, out)
        if verification is not None:
            record["verification"] = verification
        _finalize(record, verification_status, completed=True)
        manifest = {
            "schema_version": 2, "run_kind": "stability_run",
            "experiment_id": args.experiment_id,
            "profile": str(args.profile) if args.profile else None,
            "spec": spec, "model": model, "case_id": case_id,
            "run": run_index,
            "expected_runs": args.expected_runs,
            "candidate_artifact": record.get("candidate_artifact"),
            "candidate_sha256": record.get("candidate_sha256"),
            "generator_gate": record.get("gate"),
            "verification_status": record.get("verification_status"),
            "status": record.get("status"),
        }
        (out / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        ev = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "repair_evidence.py"),
             "build", "--run", str(out), "--out", str(out / "evidence")],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
        )
        record["evidence_ok"] = ev.returncode == 0
        return record
    except subprocess.TimeoutExpired as exc:
        return _timeout_record(spec, provider, model, case_id, run_index, args, exc)
    except Exception as exc:  # noqa: BLE001 - preserve a typed terminal record
        return _finalize(record, "VERIFIER_ERROR", completed=True,
                         error=f"{type(exc).__name__}: {exc}")


def _record_flag(record: dict, key: str, fallback: bool) -> bool:
    if key in record:
        return bool(record.get(key))
    return bool(fallback)


def _record_status(record: dict) -> str:
    explicit = record.get("verification_status")
    if explicit:
        return str(explicit)
    if record.get("verified"):
        return "verified"
    return str(record.get("repair_status") or record.get("status") or "NOT_RUN")


def aggregate(records: list[dict], expected_runs: int | None = None) -> dict:
    expected = len(records) if expected_runs is None else int(expected_runs)
    started = 0
    completed = 0
    eligible = 0
    verified = 0
    status_counts: dict[str, int] = {}
    for r in records:
        is_completed = _record_flag(r, "completed", r.get("status") == "completed")
        is_started = _record_flag(r, "started", is_completed)
        is_eligible = _record_flag(r, "eligible", is_completed)
        started += int(is_started)
        completed += int(is_completed)
        eligible += int(is_eligible)
        verified += int(bool(r.get("verified")))
        key = _record_status(r)
        status_counts[key] = status_counts.get(key, 0) + 1
    by_model: dict[str, dict] = {}
    by_case: dict[str, dict] = {}
    for r in records:
        model = str(r.get("spec") or "unknown")
        case = str(r.get("case_id") or "unknown")
        model_slot = by_model.setdefault(model, {"runs": 0, "verified": 0,
                                                  "eligible": 0, "failures": {},
                                                  "statuses": {}})
        model_slot["runs"] += 1
        model_slot["verified"] += int(bool(r.get("verified")))
        is_eligible = _record_flag(r, "eligible", r.get("status") == "completed")
        model_slot["eligible"] += int(is_eligible)
        status = _record_status(r)
        model_slot["statuses"][status] = model_slot["statuses"].get(status, 0) + 1
        if is_eligible and not r.get("verified"):
            failure = str(r.get("repair_status") or status or "UNKNOWN")
            model_slot["failures"][failure] = model_slot["failures"].get(failure, 0) + 1
        case_slot = by_case.setdefault(case, {"runs": 0, "verified": 0})
        case_slot["runs"] += 1
        case_slot["verified"] += int(bool(r.get("verified")))
    return {
        "schema_version": 1,
        "kind": "repair_stability",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expected_runs": expected,
        "started_runs": started,
        "completed_runs": completed,
        "eligible_runs": eligible,
        "runs": len(records),
        "verified_runs": verified,
        "status_counts": status_counts,
        "R_verified": (verified / eligible) if eligible else 0.0,
        "R_robustness": (verified / expected) if expected else 0.0,
        "per_model": by_model,
        "per_case": by_case,
    }


def _checkpoint_state(experiment_id: str, expected_runs: int,
                      records: list[dict]) -> dict:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "expected_runs": int(expected_runs),
        "records": records,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _write_checkpoint(out: Path, experiment_id: str, expected_runs: int,
                      records: list[dict]) -> Path:
    path = out / CHECKPOINT_NAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(_checkpoint_state(experiment_id, expected_runs, records),
                              indent=2) + "\n")
    tmp.replace(path)
    return path


def _load_checkpoint(out: Path, experiment_id: str) -> tuple[int | None, list[dict]]:
    path = out / CHECKPOINT_NAME
    if not path.is_file():
        return None, []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, []
    if data.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        return None, []
    if str(data.get("experiment_id") or "") != experiment_id:
        return None, []
    records = data.get("records")
    if not isinstance(records, list):
        return None, []
    try:
        expected = int(data["expected_runs"])
    except (KeyError, TypeError, ValueError):
        return None, []
    return expected, [r for r in records if isinstance(r, dict)]


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
    ap.add_argument("--resume", action="store_true",
                    help="resume from checkpoint.json for the same experiment id")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore an existing checkpoint and start over")
    args = ap.parse_args()
    if args.resume and args.fresh:
        print("--resume and --fresh are mutually exclusive", file=sys.stderr)
        return 2
    if os.environ.get("BINARYREPAIR_LIVE_AI") != "1":
        print("refusing live provider calls without BINARYREPAIR_LIVE_AI=1")
        return 2
    manifest = json.loads(args.cases.read_text())
    by_id = {str(item["id"]): item for item in manifest["cases"]}
    case_ids = list(by_id)
    if args.smoke:
        case_ids = case_ids[:1]
    args.out.mkdir(parents=True, exist_ok=True)
    keys = _planned_keys(args.models, case_ids, args.repeats)
    args.expected_runs = len(keys)
    records: list[dict] = []
    done: set[tuple] = set()
    if args.resume and not args.fresh:
        checkpoint_expected, existing = _load_checkpoint(args.out, args.experiment_id)
        if checkpoint_expected is not None:
            if checkpoint_expected != args.expected_runs:
                print("checkpoint expected_runs differs from this matrix; "
                      "use --fresh or a new experiment id", file=sys.stderr)
                return 2
            records = existing
            done = {_record_key(r) for r in records if r.get("completed")}
            print(json.dumps({"resume": True, "existing": len(records),
                              "already_completed": len(done)}), flush=True)
    for spec, case_id, run_index in keys:
        if (spec, case_id, run_index) in done:
            continue
        record = _run_one(spec, case_id, run_index, args, by_id.get(case_id))
        records.append(record)
        print(json.dumps({k: record.get(k) for k in
                          ("spec", "case_id", "run", "status",
                           "verification_status", "gate", "repair_status",
                           "evidence_ok")}), flush=True)
        _write_checkpoint(args.out, args.experiment_id, args.expected_runs, records)
    report = aggregate(records, args.expected_runs)
    report["records"] = records
    report["experiment_id"] = args.experiment_id
    (args.out / "stability.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Repair stability", "",
             f"- expected: {report['expected_runs']}",
             f"- started: {report['started_runs']}",
             f"- completed: {report['completed_runs']}",
             f"- eligible: {report['eligible_runs']}",
             f"- verified: {report['verified_runs']}",
             f"- R_verified: {report['R_verified']:.3f}",
             f"- R_robustness: {report['R_robustness']:.3f}",
             f"- statuses: `{json.dumps(report['status_counts'])}`", ""]
    (args.out / "README.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: report[k] for k in
                      ("expected_runs", "started_runs", "completed_runs",
                       "eligible_runs", "verified_runs", "R_verified")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
