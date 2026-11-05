#!/usr/bin/env python3
"""Ingest a self-describing execution bundle into the controller store.

The guest writes a bundle directory; this host-side adapter verifies paths,
symlinks, sizes and hashes before registering artifacts and handing a result
bundle to the worker.  It is deliberately separate from ``host_importer``:
that module imports a declarative result JSON, while this module is the only
place that accepts guest files.

Expected ``bundle.json``::

    {
      "schema_version": 1,
      "route": "route_a" | "route_b",
      "candidate_sha256": "<64 hex>",
      "gates": {
        "V0": {"status": "passed", "artifacts": ["candidate.elf"]},
        ...
      },
      "analysis": [{"role": "analysis_v3", "path": "analysis/v3.json"}],
      "comparison": "behavior-comparison.json"
    }

``gates`` may be omitted; then all gates are ``not_run``.  A passed gate must
name at least one artifact.  No file is read from outside the bundle root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import connect
from app.services import jobs, worker
from tools.host_importer import import_bundle

GATES = ("V0", "V1", "V2", "V3", "V4", "V5")
STATUS = {"passed", "failed", "not_run", "unknown", "timed_out"}
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


class IngestError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise IngestError(f"artifact path must be relative: {relative!r}")
    root_resolved = root.resolve()
    raw = root_resolved / relative
    if raw.is_symlink():
        raise IngestError(f"artifact path is a symlink: {relative!r}")
    candidate = raw.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise IngestError(f"artifact path escapes bundle: {relative!r}") from exc
    if not candidate.is_file():
        raise IngestError(f"artifact is missing: {relative!r}")
    return candidate


def _read_manifest(bundle: Path) -> dict[str, Any]:
    path = bundle / "bundle.json"
    if not path.is_file():
        raise IngestError("bundle.json is missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IngestError(f"bundle.json is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise IngestError("bundle.json must be an object")
    if data.get("schema_version") != 1:
        raise IngestError("bundle.json schema_version must be 1")
    candidate = data.get("candidate_sha256")
    if not isinstance(candidate, str) or len(candidate) != 64:
        raise IngestError("bundle.json candidate_sha256 must be 64 hex characters")
    try:
        int(candidate, 16)
    except ValueError as exc:
        raise IngestError("bundle.json candidate_sha256 must be hex") from exc
    gates = data.get("gates") or {}
    if not isinstance(gates, dict):
        raise IngestError("bundle.json gates must be an object")
    for gate, entry in gates.items():
        if gate not in GATES:
            raise IngestError(f"unknown gate: {gate}")
        if not isinstance(entry, dict):
            raise IngestError(f"gate {gate} must be an object")
        if str(entry.get("status", "not_run")) not in STATUS:
            raise IngestError(f"gate {gate} has unknown status")
    return data


def _register_file(
    *,
    data_dir: Path,
    job_id: str,
    attempt_id: str,
    bundle: Path,
    relative: str,
    role: str,
) -> str:
    source = _safe_file(bundle, relative)
    size = source.stat().st_size
    if size > MAX_FILE_BYTES:
        raise IngestError(f"artifact too large: {relative}")
    destination_rel = f"jobs/{job_id}/evidence/{attempt_id}/{Path(relative).name}"
    destination = data_dir / destination_rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    digest = _sha256(destination)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection = connect(data_dir)
    try:
        with connection:
            row = connection.execute(
                "SELECT id, sha256 FROM artifacts WHERE job_id = ? AND relative_path = ?",
                (job_id, destination_rel),
            ).fetchone()
            if row is not None:
                if str(row["sha256"]) != digest:
                    raise IngestError(f"conflicting existing artifact: {destination_rel}")
                return str(row["id"])
            artifact_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO artifacts "
                "(id, job_id, attempt_id, relative_path, sha256, size_bytes, media_type, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'application/octet-stream', ?, ?)",
                (artifact_id, job_id, attempt_id, destination_rel, digest, size, role, now),
            )
    finally:
        connection.close()
    return artifact_id


def ingest(
    *,
    data_dir: str | Path,
    job_id: str,
    run_id: str,
    attempt_id: str,
    route: str,
    bundle: str | Path,
    trigger: bool = True,
) -> dict[str, Any]:
    data_dir = Path(data_dir)
    bundle = Path(bundle)
    attempt = jobs.get_attempt(attempt_id, data_dir=data_dir)
    if attempt is None:
        raise IngestError("unknown attempt")
    if attempt.run_id != run_id:
        raise IngestError("attempt does not belong to run")
    if attempt.route != route:
        raise IngestError("route does not match attempt")
    run = jobs.get_run(run_id, data_dir=data_dir)
    if run is None or run.job_id != job_id:
        raise IngestError("run does not belong to job")
    if not bundle.is_dir():
        raise IngestError("bundle must be a directory")
    manifest = _read_manifest(bundle)
    if manifest.get("route") not in (None, route):
        raise IngestError("bundle route does not match attempt")

    total = 0
    evidence: dict[str, str] = {}
    results: dict[str, str] = {}
    for gate in GATES:
        entry = (manifest.get("gates") or {}).get(gate) or {}
        status = str(entry.get("status", "not_run"))
        results[gate] = status
        names = entry.get("artifacts") or []
        if not isinstance(names, list):
            raise IngestError(f"gate {gate} artifacts must be a list")
        ids = []
        for name in names:
            if not isinstance(name, str):
                raise IngestError(f"gate {gate} artifact name must be a string")
            path = _safe_file(bundle, name)
            total += path.stat().st_size
            if total > MAX_TOTAL_BYTES:
                raise IngestError("bundle exceeds total size limit")
            ids.append(_register_file(data_dir=data_dir, job_id=job_id,
                                      attempt_id=attempt_id, bundle=bundle,
                                      relative=name, role=f"{gate.lower()}_evidence"))
        if status == "passed" and not ids:
            raise IngestError(f"gate {gate} passed without evidence")
        if ids:
            evidence[gate] = ids[0]

    analysis_ids = []
    for item in manifest.get("analysis") or []:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise IngestError("analysis entries need path")
        analysis_ids.append(_register_file(
            data_dir=data_dir, job_id=job_id, attempt_id=attempt_id, bundle=bundle,
            relative=item["path"], role=str(item.get("role") or "analysis"),
        ))
    if manifest.get("comparison"):
        _register_file(data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                       bundle=bundle, relative=str(manifest["comparison"]),
                       role="behavior_comparison")

    payload = {
        "route": route,
        "candidate_sha256": manifest["candidate_sha256"],
        "results": results,
        "evidence": evidence,
        "details": {"analysis_artifact_ids": analysis_ids},
    }
    imported = import_bundle(
        data_dir=data_dir, job_id=job_id, run_id=run_id, attempt_id=attempt_id,
        bundle=payload, route=route, trigger=trigger,
    )
    return {"imported": imported, "evidence": evidence, "analysis_artifact_ids": analysis_ids}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools/route_bundle_ingest.py")
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--attempt-id", required=True)
    ap.add_argument("--route", required=True, choices=("route_a", "route_b"))
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--no-trigger", action="store_true")
    args = ap.parse_args(argv)
    try:
        result = ingest(data_dir=args.data_dir, job_id=args.job_id, run_id=args.run_id,
                        attempt_id=args.attempt_id, route=args.route,
                        bundle=args.bundle, trigger=not args.no_trigger)
    except (IngestError, OSError, ValueError) as exc:
        print(f"route_bundle_ingest: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
