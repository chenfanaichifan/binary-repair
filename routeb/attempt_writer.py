#!/usr/bin/env python3
"""Map a Route B static bundle to the worker's per-attempt JSON.

The worker contract is::

    <data>/jobs/<job>/runs/<run>/attempts/<attempt>.json

This adapter never invents a ``passed`` result. It maps only what the bundle
actually measured:

* V0 identity: original hash matches the job and the candidate exists;
* V1 structure: the bundle's static audit passed;
* V3 behaviour: only when the bundle contains a passing runtime manifest;
* V5 reproducibility: only when the bundle contains a measured, pass build-twice;
* V2/V4 and any absent runtime check: ``not_run``.

The static bundle alone therefore yields ``inconclusive``; it is not Gate 4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.connection import connect
from app.services import jobs

GATES = ("V0", "V1", "V2", "V3", "V4", "V5")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _verify_bundle(bundle: Path) -> dict[str, Any]:
    manifest_path = bundle / "edit-manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"missing {manifest_path}")
    manifest = _read_json(manifest_path)
    if manifest.get("route") != "route_b":
        raise ValueError("bundle edit-manifest.json is not route_b")
    candidate = bundle / "candidate.elf"
    original = bundle / "original.elf"
    if not candidate.exists() or not original.exists():
        raise ValueError("bundle must contain candidate.elf and original.elf")
    if _sha(candidate) != manifest.get("candidate_sha256"):
        raise ValueError("candidate.elf hash does not match edit-manifest.json")
    if _sha(original) != manifest.get("original_sha256"):
        raise ValueError("original.elf hash does not match edit-manifest.json")
    return manifest


def _artifact(
    *,
    data_dir: Path,
    job_id: str,
    attempt_id: str,
    bundle: Path,
    filename: str,
    role: str = "evidence",
) -> str:
    """Copy one bundle file under the job evidence dir and register it."""
    source = bundle / filename
    if not source.exists():
        raise ValueError(f"missing bundle file: {source}")
    relative = Path("jobs") / job_id / "evidence" / attempt_id / filename
    destination = data_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    digest = _sha(destination)
    size = destination.stat().st_size
    media = "application/json" if filename.endswith(".json") else "application/octet-stream"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    connection = connect(data_dir)
    try:
        with connection:
            existing = connection.execute(
                "SELECT id FROM artifacts WHERE job_id = ? AND relative_path = ?",
                (job_id, relative.as_posix()),
            ).fetchone()
            if existing is not None:
                artifact_id = str(existing["id"])
                connection.execute(
                    "UPDATE artifacts SET sha256 = ?, size_bytes = ?, media_type = ?, "
                    "attempt_id = ? WHERE id = ?",
                    (digest, size, media, attempt_id, artifact_id),
                )
            else:
                artifact_id = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO artifacts "
                    "(id, job_id, attempt_id, relative_path, sha256, size_bytes, media_type, role, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (artifact_id, job_id, attempt_id, relative.as_posix(),
                     digest, size, media, role, now),
                )
    finally:
        connection.close()
    return artifact_id


def _runtime_state(bundle: Path) -> tuple[str, Path | None]:
    compare = bundle / "manifest-compare.json"
    repaired = bundle / "manifest-repaired.json"
    if compare.exists():
        payload = _read_json(compare)
        return ("passed" if payload.get("gate4_pass") is True else "failed"), compare
    if repaired.exists():
        payload = _read_json(repaired)
        return ("passed" if payload.get("repaired_pass") is True else "failed"), repaired
    return "not_run", None


def _v4_review(path: Path | None, candidate: str) -> tuple[str, str]:
    if path is None or not path.exists():
        return "not_run", "symbolic check not run"
    data = _read_json(path)
    runs = data.get("runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        return "not_run", "V4 evidence has no runs"
    matching = [r for r in runs if isinstance(r, dict) and r.get("sha256") == candidate]
    if not matching:
        return "not_run", "V4 evidence has no run for this candidate"
    valid = [r for r in matching if r.get("valid_domain") is True]
    free = [r for r in matching if r.get("valid_domain") is False]
    if not valid or not free:
        return "not_run", "V4 evidence lacks valid/free-domain runs"
    if any(r.get("timed_out") is True for r in matching):
        return "unknown", "V4 timed out; pending adjudication"
    if any(r.get("verdict") == "counterexample" for r in matching):
        return "failed", "V4 counterexample"
    if all(r.get("verdict") == "proven" for r in valid) and all(
            r.get("verdict") == "no_counterexample" for r in free):
        return "unknown", "V4 self-verified; Lead adjudication pending (not a pass)"
    return "unknown", "V4 verdict not conclusive"


def _interface_state(bundle: Path, manifest: dict[str, Any]) -> tuple[str, Path | None, str]:
    """Read M3's optional v2-routeb-fixed.json; fail closed on identity mismatch."""
    path = bundle / "v2-routeb-fixed.json"
    if not path.exists():
        return "not_run", None, "interface evidence missing"
    data = _read_json(path)
    hashes = data.get("hashes") or {}
    declared = hashes.get("candidate_sha256")
    candidate = manifest.get("candidate_sha256")
    if declared and declared != candidate:
        raise ValueError(f"v2-routeb-fixed candidate {declared} does not match {candidate}")
    checks = data.get("checks") or {}
    failures = data.get("failures") or []
    passed = bool(checks) and all(value is True for value in checks.values()) and not failures
    return ("passed" if passed else "failed"), path, (
        "V2 interface passed" if passed else f"V2 interface failures: {failures}"
    )


def _repro_state(bundle: Path) -> tuple[str, Path | None]:
    path = bundle / "reproducibility.json"
    if not path.exists():
        return "not_run", None
    payload = _read_json(path)
    if payload.get("state") != "measured":
        return "not_run", path
    return ("passed" if payload.get("pass") is True else "failed"), path


def write_attempt(
    *,
    bundle: Path,
    data_dir: Path,
    job_id: str,
    run_id: str,
    attempt_id: str,
    v4_evidence: Path | None = None,
) -> dict[str, Any]:
    manifest = _verify_bundle(bundle)
    job = jobs.get_job(job_id, data_dir=data_dir)
    run = jobs.get_run(run_id, data_dir=data_dir)
    attempt = jobs.get_attempt(attempt_id, data_dir=data_dir)
    if job is None or run is None or attempt is None:
        raise ValueError("job/run/attempt not found")
    if run.job_id != job_id or attempt.run_id != run_id:
        raise ValueError("job/run/attempt do not belong together")
    if attempt.route != "route_b":
        raise ValueError(f"attempt {attempt_id} is {attempt.route}, not route_b")

    audit = _read_json(bundle / "audit.json") if (bundle / "audit.json").exists() else {"pass": False}
    runtime_state, runtime_path = _runtime_state(bundle)
    repro_state, repro_path = _repro_state(bundle)
    interface_state, interface_path, interface_detail = _interface_state(bundle, manifest)
    v4_state, v4_detail = _v4_review(v4_evidence, manifest.get("candidate_sha256", ""))
    identity = manifest.get("original_sha256") == job.original_sha256
    structure = audit.get("pass") is True

    results = {
        "V0": "passed" if identity else "failed",
        "V1": "passed" if structure else "failed" if (bundle / "audit.json").exists() else "not_run",
        "V2": interface_state,
        "V3": runtime_state,
        "V4": v4_state,
        "V5": repro_state,
    }
    evidence: dict[str, str] = {}
    details: dict[str, str] = {
        "V0": f"original {manifest.get('original_sha256')} vs job {job.original_sha256}",
        "V1": "static ELF audit passed" if structure else "static ELF audit not passed",
        "V2": interface_detail,
        "V3": ("runtime manifest " + runtime_state) if runtime_path else "no runtime manifest in bundle",
        "V4": v4_detail,
        "V5": ("build-twice " + repro_state) if repro_path else "build-twice not run",
    }

    if results["V0"] == "passed":
        evidence["V0"] = _artifact(data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                                   bundle=bundle, filename="candidate.elf")
    if results["V1"] == "passed":
        evidence["V1"] = _artifact(data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                                   bundle=bundle, filename="audit.json")
    if results["V2"] == "passed" and interface_path is not None:
        evidence["V2"] = _artifact(data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                                   bundle=bundle, filename=interface_path.name)
    if v4_evidence is not None and v4_evidence.exists() and results["V4"] != "not_run":
        evidence["V4"] = _artifact(data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                                   bundle=v4_evidence.parent, filename=v4_evidence.name)
    if results["V3"] == "passed" and runtime_path is not None:
        evidence["V3"] = _artifact(data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                                   bundle=bundle, filename=runtime_path.name)
    if results["V5"] == "passed" and repro_path is not None:
        evidence["V5"] = _artifact(data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                                   bundle=bundle, filename=repro_path.name)

    payload = {
        "route": "route_b",
        "candidate_sha256": manifest["candidate_sha256"],
        "results": results,
        "evidence": evidence,
        "details": details,
    }
    path = data_dir / "jobs" / job_id / "runs" / run_id / "attempts" / f"{attempt_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path), "payload": payload}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m routeb.attempt_writer")
    ap.add_argument("--from-env", action="store_true",
                    help="read BINARYREPAIR_* and BINARYREPAIR_ROUTEB_BUNDLE")
    ap.add_argument("--bundle", type=Path)
    ap.add_argument("--data-dir", type=Path)
    ap.add_argument("--job", dest="job_id")
    ap.add_argument("--run", dest="run_id")
    ap.add_argument("--attempt", dest="attempt_id")
    args = ap.parse_args(argv)

    if args.from_env:
        data_dir = Path(os.environ["BINARYREPAIR_DATA_DIR"])
        job_id = os.environ["BINARYREPAIR_JOB_ID"]
        run_id = os.environ["BINARYREPAIR_RUN_ID"]
        attempt_id = os.environ["BINARYREPAIR_ATTEMPT_ID"]
        bundle_raw = os.environ.get("BINARYREPAIR_ROUTEB_BUNDLE")
        if not bundle_raw:
            raise SystemExit("BINARYREPAIR_ROUTEB_BUNDLE is required")
        bundle = Path(bundle_raw)
    else:
        if not (args.bundle and args.data_dir and args.job_id and args.run_id):
            ap.error("--bundle --data-dir --job --run are required")
        data_dir, bundle = args.data_dir, args.bundle
        job_id, run_id = args.job_id, args.run_id
        if args.attempt_id is None:
            attempts = jobs.list_attempts(run_id, data_dir=data_dir)
            route_b = [a for a in attempts if a.route == "route_b"]
            if not route_b:
                raise SystemExit("no route_b attempt for this run")
            attempt_id = route_b[-1].id
        else:
            attempt_id = args.attempt_id

    result = write_attempt(bundle=bundle, data_dir=data_dir, job_id=job_id,
                           run_id=run_id, attempt_id=attempt_id, v4_evidence=args.v4_evidence)
    print(json.dumps({"path": result["path"], "results": result["payload"]["results"],
                      "evidence": result["payload"]["evidence"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
