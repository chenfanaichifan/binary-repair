"""Write one worker attempt bundle from an executor result.

Modes:

* ``--routea-bundle <dir>`` (production Route A entry): validate the canonical
  guest bundle with :mod:`app.domain.route_a_evidence`, recomputing what the
  host can recompute and registering host-written verification records. This is
  the only mode the attempt driver uses for Route A.
* ``--routeb-bundle <dir>``: map a `routeb/executor.py` static bundle to V0-V5
  without inventing a pass. Runtime checks without ``manifest-compare.json``
  stay ``not_run``.
* ``--input result.json``: a generic declaration map. It is **test/preview
  only** and is deliberately not reachable from :mod:`app.services.attempt_driver`;
  a production attempt can never fall back to it when the canonical bundle is
  missing.

The output path defaults to ``BINARYREPAIR_RESULT_PATH`` and identifiers default
to the environment the worker passes to ``BINARYREPAIR_ATTEMPT_CMD``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.db.connection import connect
from app.services import jobs
from app.services.assistant_key_store import is_secret_file

ROUTES = ("route_a", "route_b")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default(value: str | None, env: str) -> str:
    resolved = value or os.environ.get(env)
    if not resolved:
        raise SystemExit(f"missing --{env.lower().replace('binaryrepair_', '').replace('_', '-')} / {env}")
    return resolved


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    return path


def _register(
    *,
    data_dir: Path,
    job_id: str,
    attempt_id: str,
    source: Path,
    role: str,
) -> str:
    if is_secret_file(source) or source.name in {".env", "session.token"}:
        raise ValueError("refusing to copy secret material into evidence")
    if not source.is_file():
        raise SystemExit(f"evidence file does not exist: {source}")
    artifact_id = uuid.uuid4().hex
    relative = f"jobs/{job_id}/artifacts/attempts/{attempt_id}/{artifact_id}-{source.name}"
    target = data_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    digest = _sha256(target)
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "INSERT INTO artifacts "
                "(id, job_id, attempt_id, relative_path, sha256, size_bytes, media_type, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'application/octet-stream', ?, ?)",
                (
                    artifact_id,
                    job_id,
                    attempt_id,
                    relative,
                    digest,
                    target.stat().st_size,
                    role,
                    "2026-10-22T00:00:00+00:00",
                ),
            )
    finally:
        connection.close()
    return artifact_id


def _generic(
    input_path: Path,
    *,
    route: str,
    candidate: str | None,
    data_dir: Path | None,
    job_id: str | None,
    attempt_id: str | None,
) -> dict[str, Any]:
    """Map a generic declaration bundle (test/preview only).

    Production Route A never reaches this function: the attempt driver only calls
    ``--routea-bundle`` and fails closed when the canonical bundle is missing.
    """
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read input bundle {input_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("input bundle must be an object")
    body_route = payload.get("route")
    if body_route is not None and body_route != route:
        raise SystemExit(f"input route {body_route!r} does not match --route {route!r}")
    results = payload.get("results")
    if not isinstance(results, dict):
        raise SystemExit("input bundle results must be an object")
    candidate_sha = candidate or payload.get("candidate_sha256")
    if not isinstance(candidate_sha, str) or len(candidate_sha) != 64:
        raise SystemExit("candidate_sha256 must be a 64-character hex digest")

    evidence = dict(payload.get("evidence") or {})
    evidence_files = payload.get("evidence_files") or {}
    if not isinstance(evidence_files, dict):
        raise SystemExit("evidence_files must be an object")
    if evidence_files:
        if data_dir is None or job_id is None or attempt_id is None:
            raise SystemExit(
                "evidence_files requires --data-dir, --job-id and --attempt-id"
            )
        for gate, raw_path in evidence_files.items():
            if gate in evidence:
                continue
            path = Path(raw_path)
            if not path.is_absolute():
                path = input_path.parent / path
            evidence[gate] = _register(
                data_dir=data_dir,
                job_id=job_id,
                attempt_id=attempt_id,
                source=path,
                role=f"route_{route}_evidence",
            )

    return {
        "route": route,
        "candidate_sha256": candidate_sha,
        "results": results,
        "evidence": evidence,
        "details": payload.get("details") or {},
    }


def _job_original_path(data_dir: Path, job_id: str) -> Path:
    """Return the job's stored original ELF, re-hashed against the job record."""

    connection = connect(data_dir)
    try:
        row = connection.execute(
            "SELECT relative_path FROM artifacts "
            "WHERE job_id = ? AND role = 'original' ORDER BY created_at LIMIT 1",
            (job_id,),
        ).fetchone()
        job = connection.execute(
            "SELECT original_sha256 FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None or job is None:
        raise SystemExit(f"job {job_id} has no stored original artifact")
    path = data_dir / str(row["relative_path"])
    if not path.is_file():
        raise SystemExit(f"job original is missing: {path}")
    if _sha256(path) != str(job["original_sha256"]):
        raise SystemExit("job original bytes do not match the job record")
    return path


def _run_contract(data_dir: Path, job_id: str, run_id: str) -> tuple[dict[str, Any], Path | None]:
    """Return the run-bound reviewed contract body and its file when present."""

    connection = connect(data_dir)
    try:
        row = connection.execute(
            "SELECT c.id AS contract_id, c.body_json FROM runs r "
            "JOIN contracts c ON c.id = r.contract_id "
            "WHERE r.id = ? AND r.job_id = ? AND c.job_id = ?",
            (run_id, job_id, job_id),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise SystemExit(f"run {run_id} has no reviewed contract")
    try:
        body = json.loads(str(row["body_json"]))
    except ValueError as exc:
        raise SystemExit(f"run contract body is not JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise SystemExit("run contract body is not an object")
    path = data_dir / "jobs" / job_id / "contracts" / f"{row['contract_id']}.json"
    return body, (path if path.is_file() else None)


def _routea(
    bundle: Path,
    *,
    data_dir: Path,
    job_id: str,
    run_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    """Validate a canonical Route A bundle and write the worker result payload."""

    from app.domain.route_a_evidence import (
        GATES,
        RouteAEvidenceError,
        validate_route_a_bundle,
    )

    attempt = jobs.get_attempt(attempt_id, data_dir=data_dir)
    if attempt is None or attempt.route != "route_a":
        raise SystemExit(f"attempt {attempt_id} is not a stored route_a attempt")
    original = _job_original_path(data_dir, job_id)
    contract_body, contract_file = _run_contract(data_dir, job_id, run_id)
    try:
        validation = validate_route_a_bundle(
            bundle,
            original_elf=original,
            contract_body=contract_body,
            contract_file=contract_file,
        )
    except RouteAEvidenceError as exc:
        raise SystemExit(str(exc)) from exc

    evidence_dir = data_dir / "jobs" / job_id / "evidence" / attempt_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    identity = {
        "candidate_sha256": validation.candidate_sha256,
        "original_sha256": validation.original_sha256,
        "contract_canonical_sha256": validation.contract_canonical_sha256,
    }
    evidence: dict[str, str] = {}
    raw_ids: dict[str, str] = {}
    for gate in GATES:
        finding = validation.findings[gate]
        if finding.raw_source:
            source = bundle / finding.raw_source
            if source.is_file() and gate == "V4":
                raw_ids[gate] = _register(
                    data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                    source=source, role=f"routea_{gate.lower()}_evidence",
                )
            elif source.is_file():
                raw_ids[gate] = _register(
                    data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                    source=source, role=f"routea_{gate.lower()}_source",
                )

        if gate == "V0" and finding.status == "passed":
            candidate = bundle / "route_a" / "candidate.elf"
            evidence["V0"] = _register(
                data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                source=candidate, role="routea_v0_candidate",
            )
        elif gate == "V1" and finding.status == "passed":
            source_artifacts = []
            for source in finding.sources:
                path = bundle / source["path"]
                if path.is_file():
                    artifact_id = _register(
                        data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                        source=path, role="routea_v1_source",
                    )
                    source_artifacts.append(
                        {"artifact_id": artifact_id, "path": source["path"], "sha256": source["sha256"]}
                    )
            record = finding.as_record(
                source_artifacts=source_artifacts, **identity
            )
            record["checks"] = {
                "audit_pass": True,
                "edit_manifest_bound": True,
                "readelf_present": True,
                "lief_present": True,
            }
            record_path = _write(evidence_dir / "V1-verified.json", record)
            evidence["V1"] = _register(
                data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                source=record_path, role="routea_v1_verification",
            )
        elif gate == "V2" and finding.status == "passed" and finding.generated is not None:
            report_path = _write(
                evidence_dir / str(finding.generated_name or "v2-interface-scored.json"),
                finding.generated,
            )
            evidence["V2"] = _register(
                data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                source=report_path, role="routea_v2_interface",
            )
        elif gate == "V3" and finding.status == "passed":
            source_artifacts = []
            raw_id = raw_ids.get("V3")
            if raw_id is not None:
                source_artifacts.append(
                    {"artifact_id": raw_id, "path": finding.raw_source, "sha256": finding.sources[0]["sha256"]}
                )
            record = finding.as_record(source_artifacts=source_artifacts, **identity)
            record["checks"] = {
                "repaired_pass": True,
                "passed": finding.checks.get("passed"),
                "total": finding.checks.get("total"),
                "input_mode": finding.checks.get("input_mode"),
                "cases_ok": True,
                "guest_observed": True,
            }
            record_path = _write(evidence_dir / "V3-verified.json", record)
            evidence["V3"] = _register(
                data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                source=record_path, role="routea_v3_verification",
            )
        elif gate == "V4" and finding.status == "passed":
            evidence["V4"] = raw_ids[gate]
        elif gate == "V5" and finding.status == "passed":
            source_artifacts = []
            raw_id = raw_ids.get("V5")
            if raw_id is not None:
                source_artifacts.append(
                    {"artifact_id": raw_id, "path": finding.raw_source, "sha256": finding.sources[0]["sha256"]}
                )
            record = finding.as_record(source_artifacts=source_artifacts, **identity)
            record["checks"] = {
                "independent_replay": True,
                "sha256_all_candidate": True,
                "byte_identical": True,
                "patch_tool_sha256": finding.checks.get("patch_tool_sha256"),
                "replayed_by": finding.checks.get("replayed_by"),
                "runs": finding.checks.get("runs"),
            }
            record_path = _write(evidence_dir / "V5-verified.json", record)
            evidence["V5"] = _register(
                data_dir=data_dir, job_id=job_id, attempt_id=attempt_id,
                source=record_path, role="routea_v5_verification",
            )

    return {
        "route": "route_a",
        "candidate_sha256": validation.candidate_sha256,
        "results": validation.results,
        "evidence": evidence,
        "details": validation.details,
    }


def _job_original_sha256(data_dir: Path, job_id: str) -> str | None:
    """Return the job's recorded original hash, or None when the job is absent."""
    connection = connect(data_dir)
    try:
        row = connection.execute(
            "SELECT original_sha256 FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return row["original_sha256"]


def _routeb(
    bundle: Path,
    *,
    data_dir: Path,
    job_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    candidate = bundle / "candidate.elf"
    audit = bundle / "audit.json"
    compare = bundle / "manifest-compare.json"
    manifest_path = bundle / "edit-manifest.json"
    original = bundle / "original.elf"
    if not candidate.is_file():
        raise SystemExit(f"routeb bundle has no candidate.elf: {bundle}")

    results: dict[str, str] = {
        "V0": "not_run",
        "V1": "not_run",
        "V2": "not_run",
        "V3": "not_run",
        "V4": "not_run",
        "V5": "not_run",
    }
    details: dict[str, str] = {}
    evidence: dict[str, str] = {}
    candidate_sha = _sha256(candidate)
    job_original = _job_original_sha256(data_dir, job_id)

    # V0 identity: pass only when the bundle declares an original hash that
    # matches the job record and the candidate bytes match the declared candidate.
    # A bundle that does not carry that evidence stays `not_run`; existence of a
    # candidate.elf is not identity proof (missing is not passing).
    declared_original: str | None = None
    declared_candidate: str | None = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            manifest = None
        if isinstance(manifest, dict):
            value = manifest.get("original_sha256")
            if isinstance(value, str) and len(value) == 64:
                declared_original = value
            value = manifest.get("candidate_sha256")
            if isinstance(value, str) and len(value) == 64:
                declared_candidate = value
    elif original.is_file():
        declared_original = _sha256(original)

    if declared_original is None:
        details["V0"] = "identity not confirmed: bundle provides no original hash"
    elif declared_candidate is not None and declared_candidate != candidate_sha:
        results["V0"] = "failed"
        details["V0"] = "candidate.elf hash does not match edit-manifest.json"
    elif job_original is None:
        details["V0"] = "identity not confirmed: job record not found"
    elif declared_original != job_original:
        results["V0"] = "failed"
        details["V0"] = f"original {declared_original} does not match job {job_original}"
    else:
        results["V0"] = "passed"
        details["V0"] = f"original {declared_original} matches the job record"
        evidence["V0"] = _register(
            data_dir=data_dir,
            job_id=job_id,
            attempt_id=attempt_id,
            source=candidate,
            role="v0_evidence",
        )

    if audit.is_file():
        try:
            audit_data = json.loads(audit.read_text(encoding="utf-8"))
        except ValueError:
            audit_data = {}
        passed = bool(audit_data.get("pass")) if isinstance(audit_data, dict) else False
        results["V1"] = "passed" if passed else "failed"
        details["V1"] = "routeb static audit"
        if passed:
            evidence["V1"] = _register(
                data_dir=data_dir,
                job_id=job_id,
                attempt_id=attempt_id,
                source=audit,
                role="routeb_audit",
            )

    # V2 is a gate only when the bundle carries an explicit interface
    # observation. The P1 guest bundle has no v2-interface.json and therefore
    # stays not_run; the 124 bundle has one and is scored here.
    v2_observation = bundle / "v2-interface.json"
    if v2_observation.is_file():
        try:
            observed = json.loads(v2_observation.read_text(encoding="utf-8"))
        except ValueError:
            observed = {}
        target_entry = observed.get("target_symbol") if isinstance(observed, dict) else None
        if isinstance(target_entry, str) and target_entry:
            from app.domain.interface import check_interface
            try:
                interface = check_interface(original, candidate, target_entry)
            except Exception as exc:  # noqa: BLE001 - absent tools are not a pass
                results["V2"] = "not_run"
                details["V2"] = f"V2 interface check unavailable: {exc}"
            else:
                results["V2"] = "passed" if interface["pass"] else "not_run"
                details["V2"] = (
                    f"{interface['score']['passed']}/{interface['score']['total']} "
                    "static interface checks"
                )
                scored = bundle / "v2-interface-scored.json"
                scored.write_text(json.dumps(interface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                if interface["pass"]:
                    evidence["V2"] = _register(
                        data_dir=data_dir,
                        job_id=job_id,
                        attempt_id=attempt_id,
                        source=scored,
                        role="routeb_v2_interface",
                    )
        else:
            details["V2"] = "V2 observation has no target_symbol"
    else:
        details["V2"] = "V2 not_run: no v2-interface.json in bundle"

    from routeb.attempt_writer import runtime_state
    runtime, runtime_path, runtime_detail = runtime_state(bundle)
    results["V3"] = runtime
    details["V3"] = runtime_detail
    # V3 has two distinct kinds. An unchanged round trip is recorded as evidence
    # but never earns behaviour credit: it may preserve the vulnerability.
    v3_kind = None
    if runtime_path is not None:
        if runtime_path.name == "manifest-compare.json":
            v3_kind = "round_trip"
            _register(
                data_dir=data_dir,
                job_id=job_id,
                attempt_id=attempt_id,
                source=runtime_path,
                role="routeb_manifest_compare",
            )
        else:
            v3_kind = "repaired_behaviour"
            repaired_id = _register(
                data_dir=data_dir,
                job_id=job_id,
                attempt_id=attempt_id,
                source=runtime_path,
                role="routeb_manifest_repaired",
            )
            if runtime == "passed":
                evidence["V3"] = repaired_id
    details["V3_kind"] = v3_kind

    # V4 is a gate only when the bundle carries an independently verified
    # marker. Producer V4 without verified_by="m4" stays not_run.
    v4_path = bundle / "v4-symbolic.json"
    if v4_path.is_file():
        try:
            v4_payload = json.loads(v4_path.read_text(encoding="utf-8"))
        except ValueError:
            v4_payload = {}
        if isinstance(v4_payload, dict) and (v4_payload.get("replay") or {}).get("verified_by") == "m4":
            try:
                from app.domain.v4 import validate_v4_evidence
                validate_v4_evidence(v4_payload, require_independent=True)
            except Exception as exc:  # noqa: BLE001 - invalid evidence is not a pass
                results["V4"] = "not_run"
                details["V4"] = f"V4 marker rejected: {exc}"
            else:
                results["V4"] = "passed"
                details["V4"] = "V4 independently verified by M4"
                evidence["V4"] = _register(
                    data_dir=data_dir,
                    job_id=job_id,
                    attempt_id=attempt_id,
                    source=v4_path,
                    role="routeb_v4_evidence",
                )
        else:
            details["V4"] = "V4 not_run: no replay.verified_by=m4 marker"
    else:
        details["V4"] = "V4 not_run: no v4-symbolic.json"

    # V5 is a gate only from a measured build-twice artifact. Independent
    # replay evidence (v5-replay.json) takes precedence over the guest's own
    # first-run reproducibility observation.
    v5_path = bundle / "v5-replay.json"
    if not v5_path.is_file():
        v5_path = bundle / "reproducibility.json"
    if v5_path.is_file():
        try:
            v5_payload = json.loads(v5_path.read_text(encoding="utf-8"))
        except ValueError:
            v5_payload = {}
        if isinstance(v5_payload, dict) and v5_payload.get("pass") is True:
            results["V5"] = "passed"
            details["V5"] = "build-twice measured, byte-identical"
            evidence["V5"] = _register(
                data_dir=data_dir,
                job_id=job_id,
                attempt_id=attempt_id,
                source=v5_path,
                role="routeb_v5_evidence",
            )
        else:
            details["V5"] = "V5 not_run: reproducibility.json not passed"
    else:
        details["V5"] = "V5 not_run: no reproducibility.json"

    return {
        "route": "route_b",
        "candidate_sha256": _sha256(candidate),
        "results": results,
        "evidence": evidence,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.services.attempt_writer")
    parser.add_argument("--input", type=Path, help="generic result JSON (test/preview only)")
    parser.add_argument("--routea-bundle", type=Path, help="canonical Route A evidence bundle dir")
    parser.add_argument("--routeb-bundle", type=Path, help="routeb/executor.py bundle dir")
    parser.add_argument("--data-dir", default=os.environ.get("BINARYREPAIR_DATA_DIR"))
    parser.add_argument("--job-id", default=os.environ.get("BINARYREPAIR_JOB_ID"))
    parser.add_argument("--run-id", default=os.environ.get("BINARYREPAIR_RUN_ID"))
    parser.add_argument("--attempt-id", default=os.environ.get("BINARYREPAIR_ATTEMPT_ID"))
    parser.add_argument("--route", default=os.environ.get("BINARYREPAIR_ROUTE"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--candidate-sha256")
    args = parser.parse_args(argv)

    if args.out is None:
        out = os.environ.get("BINARYREPAIR_RESULT_PATH")
        if not out:
            raise SystemExit("missing --out / BINARYREPAIR_RESULT_PATH")
        args.out = Path(out)

    route = args.route or (
        "route_b" if args.routeb_bundle else "route_a" if args.routea_bundle else None
    )
    if route not in ROUTES:
        raise SystemExit("route must be route_a or route_b")

    if args.routea_bundle:
        data_dir = Path(_default(args.data_dir, "BINARYREPAIR_DATA_DIR"))
        job_id = _default(args.job_id, "BINARYREPAIR_JOB_ID")
        run_id = _default(args.run_id, "BINARYREPAIR_RUN_ID")
        attempt_id = _default(args.attempt_id, "BINARYREPAIR_ATTEMPT_ID")
        payload = _routea(
            args.routea_bundle,
            data_dir=data_dir,
            job_id=job_id,
            run_id=run_id,
            attempt_id=attempt_id,
        )
    elif args.routeb_bundle:
        data_dir = Path(_default(args.data_dir, "BINARYREPAIR_DATA_DIR"))
        job_id = _default(args.job_id, "BINARYREPAIR_JOB_ID")
        attempt_id = _default(args.attempt_id, "BINARYREPAIR_ATTEMPT_ID")
        payload = _routeb(
            args.routeb_bundle,
            data_dir=data_dir,
            job_id=job_id,
            attempt_id=attempt_id,
        )
    elif args.input:
        data_dir = Path(args.data_dir) if args.data_dir else None
        payload = _generic(
            args.input,
            route=route,
            candidate=args.candidate_sha256,
            data_dir=data_dir,
            job_id=args.job_id,
            attempt_id=args.attempt_id,
        )
    else:
        raise SystemExit("provide --routea-bundle, --routeb-bundle or --input")

    path = _write(args.out, payload)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
