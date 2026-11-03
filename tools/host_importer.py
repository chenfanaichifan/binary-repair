#!/usr/bin/env python3
"""Atomically import one executor result bundle into the controller store.

The broker (``tools/host_broker.py``) uses :func:`import_bundle`; the CLI is
useful for a single manual import.

A bundle is written to::

    <data>/jobs/<job_id>/runs/<run_id>/attempts/<attempt_id>.json

The write is atomic (temp file + os.replace), idempotent for identical bytes,
and refuses to overwrite a different existing bundle. After a successful import
the worker is triggered in-process unless ``--no-trigger`` is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import jobs, worker

ROUTES = {"route_a", "route_b"}


def _validate_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError("bundle must be a JSON object")
    route = bundle.get("route")
    if route is not None and route not in ROUTES:
        raise ValueError("bundle route must be route_a or route_b")
    candidate = bundle.get("candidate_sha256")
    if not isinstance(candidate, str) or len(candidate) != 64:
        raise ValueError("bundle candidate_sha256 must be 64 hex characters")
    try:
        int(candidate, 16)
    except ValueError as exc:
        raise ValueError("bundle candidate_sha256 must be hex") from exc
    results = bundle.get("results")
    if not isinstance(results, dict):
        raise ValueError("bundle results must be an object")
    return bundle


def _target_path(data_dir: Path, job_id: str, run_id: str, attempt_id: str) -> Path:
    return data_dir / "jobs" / job_id / "runs" / run_id / "attempts" / f"{attempt_id}.json"


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as temp:
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def import_bundle(
    *,
    data_dir: str | Path,
    job_id: str,
    run_id: str,
    attempt_id: str,
    bundle: Any,
    route: str | None = None,
    trigger: bool = True,
) -> dict[str, Any]:
    """Import one bundle and optionally trigger the worker.

    Raises ValueError without writing anything when the attempt/run/job binding
    or the bundle itself is invalid.
    """

    data_dir = Path(data_dir)
    payload = _validate_bundle(bundle)
    attempt = jobs.get_attempt(attempt_id, data_dir=data_dir)
    if attempt is None:
        raise ValueError("unknown attempt id")
    if attempt.run_id != run_id:
        raise ValueError("attempt does not belong to the supplied run")
    expected_route = route or attempt.route
    if expected_route not in ROUTES:
        raise ValueError("route must be route_a or route_b")
    if expected_route != attempt.route:
        raise ValueError("route does not match the persisted attempt")
    if payload.get("route") not in (None, attempt.route):
        raise ValueError("bundle route does not match the persisted attempt")

    run = jobs.get_run(run_id, data_dir=data_dir)
    if run is None or run.job_id != job_id:
        raise ValueError("run does not belong to the supplied job")

    target = _target_path(data_dir, job_id, run_id, attempt_id)
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError(f"a different bundle already exists at {target}")
        changed = False
    else:
        _atomic_write(target, raw)
        changed = True

    processed = worker.run_once(data_dir=data_dir) if trigger else 0
    return {
        "job_id": job_id,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "route": attempt.route,
        "path": str(target),
        "changed": changed,
        "worker_processed": processed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/host_importer.py")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--route", choices=sorted(ROUTES))
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--no-trigger", action="store_true")
    args = parser.parse_args(argv)

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        result = import_bundle(
            data_dir=args.data_dir,
            job_id=args.job_id,
            run_id=args.run_id,
            attempt_id=args.attempt_id,
            bundle=bundle,
            route=args.route,
            trigger=not args.no_trigger,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"host_importer: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
