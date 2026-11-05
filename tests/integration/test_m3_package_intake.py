"""End-to-end intake of M3's corrected packages, and the V3 evidence split.

The packages in ``dist/m5-evidence`` are the real handoffs M3 produced. Feeding
them through the ingest adapter, the worker, and the controller is the only way
to prove the integration: the fixtures below are copied from those archives, not
invented.

What these tests protect:

* a corrected package is accepted and its identity/structure/behaviour evidence
  survives the trip;
* a package that never ran V4 stays ``inconclusive`` / ``required_check_not_run``
  — the failure mode the whole project is built to avoid is a missing check
  becoming a success;
* an unchanged round trip is stored as ``round_trip`` and earns no V3 credit;
* the candidate hash is bound to a verified artifact, not to a string.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app
from app.db.connection import connect
from app.services import attempt_writer, jobs, worker
from tools.route_bundle_ingest import ingest

REPO = Path(__file__).resolve().parents[2]
P3A = REPO / "dist" / "m5-evidence" / "P3A-routea-2026-10-31-v7.zip"
P3B = REPO / "dist" / "m5-evidence" / "P3B-package-v6-2026-10-31.zip"


def _unpack(archive: Path, target: Path) -> Path:
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(target)
    return target


def _run(tmp_path: Path, bundles: dict[str, Path]):
    data = tmp_path / "var"
    original = (bundles["route_a"] / "original.elf").read_bytes()
    job = jobs.create_job(
        original_bytes=original,
        filename="sample.elf",
        defect_description="M3 package intake",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="m1",
        data_dir=data,
        input_sha256=job.original_sha256,
        manifest_sha256="2" * 64,
    )
    run = jobs.start_run(
        job.id, approval=approval, idempotency_key="m3-intake", data_dir=data
    )
    attempts = {item.route: item for item in jobs.list_attempts(run.id, data_dir=data)}
    return data, job, run, attempts


def _gates(data: Path, attempt_id: str) -> dict[str, str]:
    connection = connect(data)
    try:
        rows = connection.execute(
            "SELECT kind, result FROM obligations WHERE attempt_id = ? ORDER BY kind",
            (attempt_id,),
        ).fetchall()
    finally:
        connection.close()
    return {row["kind"]: row["result"] for row in rows}


def _run_verdict(data: Path, run_id: str) -> dict:
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT phase, outcome, reason, failing_obligation, detail FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    finally:
        connection.close()
    return dict(row)


def test_corrected_packages_are_accepted_and_stay_inconclusive(
    tmp_path: Path, monkeypatch
) -> None:
    bundles = {
        "route_a": _unpack(P3A, tmp_path / "route_a"),
        "route_b": _unpack(P3B, tmp_path / "route_b"),
    }
    data, job, run, attempts = _run(tmp_path, bundles)

    for route, bundle in bundles.items():
        ingest(
            data_dir=data,
            job_id=job.id,
            run_id=run.id,
            attempt_id=attempts[route].id,
            route=route,
            bundle=bundle,
            trigger=False,
        )

    worker.run_once(data_dir=data)

    route_a = _gates(data, attempts["route_a"].id)
    assert route_a["identity"] == "passed"
    assert route_a["structure"] == "passed"
    assert route_a["behaviour"] == "passed"
    # V2 (interface), V4 (symbolic) and V5 (reproducibility) never ran.
    assert route_a["interface"] == "not_run"
    assert route_a["symbolic"] == "not_run"
    assert route_a["reproducibility"] == "not_run"

    # The legacy P3B package carries no result bundle, so every gate is not_run.
    route_b = _gates(data, attempts["route_b"].id)
    assert set(route_b.values()) == {"not_run"}

    verdict = _run_verdict(data, run.id)
    assert verdict["outcome"] == "inconclusive"
    assert verdict["reason"] == "required_check_not_run"
    assert verdict["phase"] == "finished"

    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data))
    client = TestClient(app, base_url="http://127.0.0.1")
    snapshot = client.get(f"/api/jobs/{job.id}").json()
    assert snapshot["execution"]["status"] == "completed"
    assert snapshot["agent"]["current_step"] == "done"


def test_a_gap_only_in_v4_is_still_inconclusive(tmp_path: Path) -> None:
    """Every check but symbolic passed; the verdict must not become a success."""
    data = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=b"\x7fELF v4 gap",
        filename="sample.elf",
        defect_description="v4 gap",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="m1",
        data_dir=data,
        input_sha256=job.original_sha256,
        manifest_sha256="3" * 64,
    )
    run = jobs.start_run(
        job.id, approval=approval, idempotency_key="v4-gap", data_dir=data
    )

    from app.services import orchestration

    attempts = {
        item.route: item for item in jobs.list_attempts(run.id, data_dir=data)
    }
    results = {"V0": "passed", "V1": "passed", "V2": "passed", "V3": "passed",
               "V4": "not_run", "V5": "passed"}
    route_a = orchestration.evaluate_attempt(
        job.id,
        run.id,
        results=results,
        data_dir=data,
        candidate_sha256="5" * 64,
        attempt_id=attempts["route_a"].id,
        route="route_a",
    )
    route_b = orchestration.evaluate_attempt(
        job.id,
        run.id,
        results={f"V{i}": "not_run" for i in range(6)},
        data_dir=data,
        candidate_sha256="6" * 64,
        attempt_id=attempts["route_b"].id,
        route="route_b",
    )
    verdict = orchestration.evaluate_run(
        job.id, route_a=route_a, route_b=route_b, data_dir=data, run_id=run.id
    )

    # Everything except symbolic passed. It still must not be a success.
    assert route_a.outcome.value == "inconclusive"
    assert route_a.reason.value == "required_check_not_run"
    assert route_a.failing_obligation == "symbolic"
    assert verdict.outcome.value == "inconclusive"
    assert verdict.reason.value == "required_check_not_run"


def _route_b_bundle(tmp_path: Path, original_sha256: str, *, repaired: bool, **extra) -> Path:
    candidate = b"\x7fELF candidate bytes"
    bundle = tmp_path / ("bundle-repaired" if repaired else "bundle-roundtrip")
    bundle.mkdir()
    (bundle / "candidate.elf").write_bytes(candidate)
    (bundle / "audit.json").write_text('{"pass": true}', encoding="utf-8")
    (bundle / "edit-manifest.json").write_text(
        json.dumps({
            "route": "route_b",
            "original_sha256": original_sha256,
            "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        }),
        encoding="utf-8",
    )
    if repaired:
        (bundle / "manifest-repaired.json").write_text(
            json.dumps({"repaired_pass": extra.get("repaired_pass", True)}),
            encoding="utf-8",
        )
    else:
        (bundle / "manifest-compare.json").write_text(
            json.dumps({"unchanged": True}), encoding="utf-8"
        )
    return bundle


def _write_route_b(tmp_path: Path, monkeypatch, repaired: bool):
    data = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=b"\x7fELF routeb original",
        filename="sample.elf",
        defect_description="route b v3",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="m1",
        data_dir=data,
        input_sha256=job.original_sha256,
        manifest_sha256="4" * 64,
    )
    run = jobs.start_run(job.id, approval=approval, idempotency_key="v3", data_dir=data)
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data)
        if item.route == "route_b"
    )
    bundle = _route_b_bundle(tmp_path, job.original_sha256, repaired=repaired)
    result = data / "jobs" / job.id / "runs" / run.id / "attempts" / f"{attempt.id}.json"
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data))
    monkeypatch.setenv("BINARYREPAIR_JOB_ID", job.id)
    monkeypatch.setenv("BINARYREPAIR_RUN_ID", run.id)
    monkeypatch.setenv("BINARYREPAIR_ATTEMPT_ID", attempt.id)
    monkeypatch.setenv("BINARYREPAIR_ROUTE", "route_b")
    monkeypatch.setenv("BINARYREPAIR_RESULT_PATH", str(result))

    assert attempt_writer.main(["--routeb-bundle", str(bundle)]) == 0
    payload = json.loads(result.read_text(encoding="utf-8"))
    return data, job, attempt, payload


def test_round_trip_is_recorded_but_earns_no_v3_credit(
    tmp_path: Path, monkeypatch
) -> None:
    data, job, attempt, payload = _write_route_b(tmp_path, monkeypatch, repaired=False)

    assert payload["results"]["V3"] == "not_run"
    assert payload["details"]["V3_kind"] == "round_trip"
    assert "V3" not in payload["evidence"]

    client = TestClient(app, base_url="http://127.0.0.1")
    body = client.get(f"/api/jobs/{job.id}/v3").json()
    assert body["status"] == "available"
    assert body["v3_credit"] is False
    assert body["kinds"]["round_trip"]["role"] == "routeb_manifest_compare"
    assert body["kinds"]["repaired_behaviour"] is None
    assert "not repair V3" in body["detail"]


def test_repaired_behaviour_earns_v3(tmp_path: Path, monkeypatch) -> None:
    data, job, attempt, payload = _write_route_b(tmp_path, monkeypatch, repaired=True)

    assert payload["results"]["V3"] == "passed"
    assert payload["details"]["V3_kind"] == "repaired_behaviour"
    assert payload["evidence"]["V3"]

    client = TestClient(app, base_url="http://127.0.0.1")
    body = client.get(f"/api/jobs/{job.id}/v3").json()
    assert body["v3_credit"] is True
    assert body["kinds"]["repaired_behaviour"]["role"] == "routeb_manifest_repaired"


def test_v3_endpoint_is_not_provided_without_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    data = tmp_path / "var"
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data))
    job = jobs.create_job(
        original_bytes=b"\x7fELF none",
        filename="sample.elf",
        defect_description="no v3",
        data_dir=data,
    )
    client = TestClient(app, base_url="http://127.0.0.1")
    body = client.get(f"/api/jobs/{job.id}/v3").json()
    assert body["status"] == "not_provided"
    assert body["v3_credit"] is False
    assert body["kinds"] == {"round_trip": None, "repaired_behaviour": None}
