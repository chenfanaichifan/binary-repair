#!/usr/bin/env python3
"""M5 Gate 2b adapters for the agent-facing tool contracts.

These are adapters over existing entry points. They do not execute new kinds of
work: run_case delegates to the Route B manifest runners, read_evidence calls the
controller evidence endpoint, and apply_candidate delegates to the existing
route_bundle_ingest module.

The module is deliberately dependency-light so M2 can import it directly.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

class ToolError(ValueError):
    """An adapter-level request error with a stable reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


def _require(condition: bool, reason: str, detail: str = "") -> None:
    if not condition:
        raise ToolError(reason, detail)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_manifest(
    runner: Path,
    args: list[str],
    *,
    timeout_ms: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="m5-run-case-") as tmp:
        out = Path(tmp) / "result.json"
        command = [sys.executable, str(runner), *args, "--out", str(out)]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_ms / 1000,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "timeout",
                "timed_out": True,
                "returncode": None,
                "stdout": (exc.stdout or b"").decode("utf-8", "replace"),
                "stderr": (exc.stderr or b"").decode("utf-8", "replace"),
                "result": None,
            }
        except OSError as exc:
            raise ToolError("runner_error", str(exc)) from exc
        if not out.is_file():
            return {
                "status": "invalid_request" if completed.returncode == 2 else "error",
                "timed_out": False,
                "returncode": completed.returncode,
                "stdout": completed.stdout.decode("utf-8", "replace"),
                "stderr": completed.stderr.decode("utf-8", "replace"),
                "result": None,
            }
        try:
            result = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ToolError("runner_error", f"runner wrote unreadable output: {exc}") from exc
        return {
            "status": "passed" if result.get("gate4_pass") or result.get("repaired_pass") else "failed",
            "timed_out": False,
            "returncode": completed.returncode,
            "stdout": completed.stdout.decode("utf-8", "replace"),
            "stderr": completed.stderr.decode("utf-8", "replace"),
            "result": result,
        }


def run_case(request: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a case to the existing runner and normalise its result.

    v1 supports ``none`` and ``argv``. stdin is rejected rather than silently
    ignored. For ``none`` an ``original_path`` selects the compare runner; without
    it, the repaired runner's native no-input path is used.
    """

    if request.get("schema_version") != 2:
        raise ToolError("invalid_request", "schema_version must be 2")
    input_mode = request.get("input_mode")
    if input_mode not in {"none", "argv"}:
        raise ToolError("invalid_request", f"unsupported input_mode: {input_mode!r}")
    for key in ("argv", "stdin_literal", "stdin_artifact"):
        if key in request:
            raise ToolError("invalid_request", f"{key} is not supported in v1")
    binary = Path(str(request.get("binary_path", "")))
    tests = Path(str(request.get("tests_dir", "")))
    if not binary.is_file():
        raise ToolError("binary_not_found", str(binary))
    if not tests.is_dir():
        raise ToolError("invalid_request", f"tests_dir not found: {tests}")
    timeout_ms = request.get("timeout_ms", 10000)
    if not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise ToolError("invalid_request", "timeout_ms must be a positive integer")
    original = request.get("original_path")
    if input_mode == "none" and original is not None:
        runner = ROOT / "routeb" / "run_manifest_compare.py"
        args = [
            "--original", str(Path(str(original))),
            "--patched", str(binary),
            "--tests", str(tests),
            "--input-mode", "none",
        ]
    else:
        runner = ROOT / "routeb" / "run_manifest_repaired.py"
        args = [
            "--binary", str(binary),
            "--tests", str(tests),
            "--input-mode", input_mode,
        ]
        contract = request.get("contract_path")
        if contract is not None:
            args += ["--contract", str(Path(str(contract)))]
    if not runner.is_file():
        raise ToolError("runner_error", f"missing runner: {runner}")
    normalized = _run_manifest(runner, args, timeout_ms=timeout_ms)
    result = normalized["result"] or {}
    return {
        "schema_version": 2,
        "case_id": request.get("case_id"),
        "status": normalized["status"],
        "timed_out": normalized["timed_out"],
        "returncode": normalized["returncode"],
        "repaired_pass": bool(result.get("repaired_pass")),
        "passed": result.get("passed"),
        "total": result.get("total"),
        "cases": result.get("cases", []),
        "edge": {
            "timeout": normalized["timed_out"],
            "invalid_applicable": input_mode != "none",
        },
        "evidence_path": request.get("evidence_path"),
        "idempotency_key": request.get("idempotency_key"),
        "stderr": normalized["stderr"],
    }


def read_evidence(request: dict[str, Any]) -> dict[str, Any]:
    """Read the controller evidence endpoint and map it to the v2 envelope."""

    if request.get("schema_version") != 2:
        raise ToolError("invalid_request", "schema_version must be 2")
    attempt_id = request.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id:
        raise ToolError("invalid_request", "attempt_id is required")
    base = str(request.get("base_url") or "http://127.0.0.1:8000").rstrip("/")
    timeout_ms = request.get("timeout_ms", 5000)
    if not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise ToolError("invalid_request", "timeout_ms must be a positive integer")
    url = f"{base}/api/attempts/{attempt_id}/evidence"
    try:
        with urllib.request.urlopen(url, timeout=timeout_ms / 1000) as response:
            status_code = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"schema_version": 2, "status": "not_found", "attempt_id": attempt_id}
        raise ToolError("backend_error", f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ToolError("backend_error", str(exc)) from exc
    if status_code != 200:
        raise ToolError("backend_error", f"HTTP {status_code}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ToolError("backend_error", "endpoint returned non-JSON") from exc
    v3 = payload.get("v3")
    if isinstance(v3, dict):
        v3 = dict(v3)
        v3.setdefault("kind", "behaviour")
        v3.setdefault("result", payload.get("result"))
        v3["legacy_invalid_applicable"] = True
        v3.pop("sha256", None)
    return {
        "schema_version": 2,
        "status": "ok" if payload.get("evidence") == "persisted" else "not_persisted",
        "attempt_id": payload.get("attempt_id", attempt_id),
        "run_id": payload.get("run_id"),
        "route": payload.get("route"),
        "evidence": payload.get("evidence"),
        "input_mode": v3.get("input_mode") if isinstance(v3, dict) else None,
        "gates": payload.get("gates", []),
        "v3": v3,
        "obligations": payload.get("obligations", {"A": [], "B": []}),
    }


def apply_candidate(request: dict[str, Any]) -> dict[str, Any]:
    """Delegate to route_bundle_ingest after validating the candidate assertion.

    The pre-layer (creating run/attempt) is not hidden here: callers must supply
    an existing run_id/attempt_id, or the adapter returns pre_layer_required.
    This keeps the adapter honest about the layer that does not exist yet.
    """

    if request.get("schema_version") != 2:
        raise ToolError("invalid_request", "schema_version must be 2")
    for key in ("job_id", "bundle_path", "candidate_sha256"):
        if not request.get(key):
            raise ToolError("pre_layer_required", f"{key} is required")
    job_id = str(request["job_id"])
    data_dir = Path(str(request.get("data_dir", "var")))
    route = str(request.get("route", "route_b"))
    run_id = request.get("run_id")
    attempt_id = request.get("attempt_id")
    if not run_id or not attempt_id:
        from app.services import jobs

        revision = request.get("contract_revision")
        manifest_sha256 = request.get("manifest_sha256")
        if revision is None or not manifest_sha256:
            raise ToolError(
                "pre_layer_required",
                "run_id/attempt_id absent; contract_revision and manifest_sha256 are required to create them",
            )
        contract = jobs.get_contract(job_id, int(revision), data_dir=data_dir)
        if contract is None:
            raise ToolError("invalid_request", f"contract revision {revision} not found")
        approval = jobs.approval_from_contract(contract, manifest_sha256=str(manifest_sha256))
        run = jobs.start_run(
            job_id,
            approval=approval,
            idempotency_key=str(request.get("idempotency_key") or "apply-candidate"),
            data_dir=data_dir,
        )
        run_id = run.id
        attempts = jobs.list_job_attempts(job_id, data_dir=data_dir)
        match = next(
            (item for item in attempts if item["run_id"] == run_id and item["route"] == route),
            None,
        )
        if match is None:
            raise ToolError("pre_layer_required", f"no {route} attempt was created")
        attempt_id = match["id"]
    candidate = str(request["candidate_sha256"])
    if len(candidate) != 64:
        raise ToolError("invalid_request", "candidate_sha256 must be 64 hex chars")
    bundle = Path(str(request["bundle_path"]))
    if not bundle.is_dir():
        raise ToolError("invalid_request", f"bundle not found: {bundle}")
    manifest_path = bundle / "bundle.json"
    if not manifest_path.is_file():
        raise ToolError("bundle_invalid", "bundle.json is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError("bundle_invalid", str(exc)) from exc
    if manifest.get("candidate_sha256") != candidate:
        raise ToolError("candidate_hash_mismatch", "bundle manifest candidate differs")
    if request.get("dry_run"):
        return {
            "schema_version": 2,
            "status": "no_op",
            "job_id": job_id,
            "run_id": str(run_id),
            "attempt_id": str(attempt_id),
            "candidate_sha256": candidate,
            "previous_candidate_sha256": None,
            "bundle_path": str(bundle),
            "rejected_reason": None,
            "idempotency_key": request.get("idempotency_key"),
        }
    from tools import route_bundle_ingest

    try:
        result = route_bundle_ingest.ingest(
            data_dir=Path(str(request.get("data_dir", "var"))),
            job_id=job_id,
            run_id=str(run_id),
            attempt_id=str(attempt_id),
            route=route,
            bundle=bundle,
            trigger=not bool(request.get("no_trigger")),
        )
    except Exception as exc:
        if exc.__class__.__name__ == "IngestError":
            raise ToolError("bundle_invalid", str(exc)) from exc
        raise
    return {
        "schema_version": 2,
        "status": "applied" if result.get("imported") is not None else "no_op",
        "job_id": job_id,
        "run_id": str(run_id),
        "attempt_id": str(attempt_id),
        "candidate_sha256": candidate,
        "previous_candidate_sha256": None,
        "bundle_path": str(bundle),
        "evidence_artifact_ids": list((result.get("evidence") or {}).values()),
        "rejected_reason": None,
        "idempotency_key": request.get("idempotency_key"),
    }


__all__ = ["ToolError", "run_case", "read_evidence", "apply_candidate"]
