from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services import jobs
from routeb.attempt_writer import write_attempt
from tools.routea_bundle_to_attempt import convert


def _job(tmp_path: Path, route: str):
    data = tmp_path / "var"
    record = jobs.create_job(original_bytes=b"\x7fELF supplement", filename="s.elf",
                             defect_description="supplement", data_dir=data)
    approval = jobs.approve_contract(record.id, contract_revision=1, reviewer_label="t",
                                     data_dir=data, input_sha256=record.original_sha256,
                                     manifest_sha256="1" * 64)
    run = jobs.start_run(record.id, approval=approval, idempotency_key="s", data_dir=data)
    attempt = next(a for a in jobs.list_attempts(run.id, data_dir=data) if a.route == route)
    return data, record, run, attempt


def test_routea_v2_v5_supplements_map_passed(tmp_path: Path) -> None:
    data, record, run, attempt = _job(tmp_path, "route_a")
    root = tmp_path / "pkg"; root.mkdir()
    candidate = "a" * 64
    (root / "v2-routea-supplement.json").write_text(json.dumps({
        "hashes": {"candidate_sha256": candidate},
        "checks": {"same_machine": True, "candidate_loads_and_runs": True},
        "failures": [],
    }))
    (root / "v5-routea-supplement.json").write_text(json.dumps({
        "candidate_sha256": candidate,
        "result": "passed", "byte_identical": True,
    }))
    payload = convert({"route": "route_a", "identity": {"candidate_sha256": candidate},
                       "gates": {gate: {"status": "not_run"} for gate in ("V0","V1","V2","V3","V4","V5")}},
                      evidence_root=root, data_dir=data, job_id=record.id, attempt_id=attempt.id)
    assert payload["results"]["V2"] == "passed"
    assert payload["results"]["V5"] == "passed"
    assert "V2" in payload["evidence"] and "V5" in payload["evidence"]


def test_routeb_v2_supplement_maps_passed(tmp_path: Path) -> None:
    data, record, run, attempt = _job(tmp_path, "route_b")
    bundle = tmp_path / "bundle"; bundle.mkdir()
    candidate = b"\x7fELF candidate"; (bundle / "candidate.elf").write_bytes(candidate)
    (bundle / "original.elf").write_bytes(b"\x7fELF original")
    (bundle / "audit.json").write_text('{"pass": true}')
    (bundle / "edit-manifest.json").write_text(json.dumps({
        "route": "route_b",
        "original_sha256": hashlib.sha256(b"\x7fELF original").hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
    }))
    (bundle / "v2-routeb-fixed.json").write_text(json.dumps({
        "hashes": {"candidate_sha256": hashlib.sha256(candidate).hexdigest()},
        "checks": {"same_machine": True, "extra_load_segments_within_contract": True},
        "failures": [],
    }))
    result = write_attempt(bundle=bundle, data_dir=data, job_id=record.id,
                           run_id=run.id, attempt_id=attempt.id)
    assert result["payload"]["results"]["V2"] == "passed"
    assert "V2" in result["payload"]["evidence"]
