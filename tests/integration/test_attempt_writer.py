"""Tests for the executor -> worker attempt bundle writer."""

from __future__ import annotations

import json
from pathlib import Path

from app.services import attempt_writer, jobs


def _job(tmp_path: Path):
    data_dir = tmp_path / "var"
    record = jobs.create_job(
        original_bytes=b"\x7fELF attempt writer",
        filename="sample.elf",
        defect_description="test",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        record.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data_dir,
        input_sha256=record.original_sha256,
        manifest_sha256="1" * 64,
    )
    run = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="writer-1",
        data_dir=data_dir,
    )
    attempt = next(a for a in jobs.list_attempts(run.id, data_dir=data_dir) if a.route == "route_a")
    return data_dir, record, run, attempt


def test_generic_writer_writes_worker_bundle(tmp_path: Path) -> None:
    data_dir, record, run, attempt = _job(tmp_path)
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(
            {
                "results": {f"V{i}": "not_run" for i in range(6)},
                "details": {"V0": "identity pending"},
            }
        ),
        encoding="utf-8",
    )
    out = data_dir / "jobs" / record.id / "runs" / run.id / "attempts" / f"{attempt.id}.json"
    code = attempt_writer.main(
        [
            "--input",
            str(source),
            "--out",
            str(out),
            "--route",
            "route_a",
            "--candidate-sha256",
            record.original_sha256,
        ]
    )
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["route"] == "route_a"
    assert payload["candidate_sha256"] == record.original_sha256
    assert payload["results"]["V0"] == "not_run"


def test_routeb_bundle_maps_static_audit_without_runtime_pass(tmp_path: Path) -> None:
    data_dir, record, run, attempt = _job(tmp_path)
    bundle = tmp_path / "routeb"
    bundle.mkdir()
    (bundle / "candidate.elf").write_bytes(b"\x7fELF candidate")
    (bundle / "audit.json").write_text('{"pass": true}', encoding="utf-8")
    out = data_dir / "jobs" / record.id / "runs" / run.id / "attempts" / f"{attempt.id}.json"

    code = attempt_writer.main(
        [
            "--routeb-bundle",
            str(bundle),
            "--data-dir",
            str(data_dir),
            "--job-id",
            record.id,
            "--attempt-id",
            attempt.id,
            "--out",
            str(out),
        ]
    )
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["route"] == "route_b"
    assert payload["results"]["V1"] == "passed"
    assert payload["results"]["V3"] == "not_run"
    assert "V1" in payload["evidence"]
