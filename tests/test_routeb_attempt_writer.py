from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services import jobs, worker
from routeb.attempt_writer import write_attempt

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf"
FUNC = "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink"


def _setup(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=ORIGINAL.read_bytes(), filename="CWE121.elf",
                          defect_description="stack buffer overflow", data_dir=data)
    approval = jobs.approve_contract(job.id, contract_revision=1, reviewer_label="test",
                                     data_dir=data, input_sha256=job.original_sha256,
                                     manifest_sha256="1" * 64)
    run = jobs.start_run(job.id, approval=approval, idempotency_key="routeb-attempt",
                         data_dir=data)
    attempt = next(a for a in jobs.list_attempts(run.id, data_dir=data) if a.route == "route_b")
    return data, job, run, attempt


def _bundle(tmp_path: Path, *, candidate: bytes = b"\x7fELF candidate") -> tuple[Path, str]:
    """Build a small bundle without importing routeb.executor (no pyelftools)."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "candidate.elf").write_bytes(candidate)
    (bundle / "original.elf").write_bytes(ORIGINAL.read_bytes())
    (bundle / "audit.json").write_text('{"pass": true}', encoding="utf-8")
    candidate_sha = hashlib.sha256(candidate).hexdigest()
    (bundle / "edit-manifest.json").write_text(json.dumps({
        "route": "route_b",
        "original_sha256": hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
        "candidate_sha256": candidate_sha,
    }), encoding="utf-8")
    return bundle, candidate_sha


def test_routeb_static_bundle_maps_to_not_run_attempt(tmp_path: Path) -> None:
    data, job, run, attempt = _setup(tmp_path)
    bundle, candidate_sha = _bundle(tmp_path)
    result = write_attempt(bundle=bundle, data_dir=data, job_id=job.id,
                           run_id=run.id, attempt_id=attempt.id)
    payload = json.loads(Path(result["path"]).read_text())
    assert payload["route"] == "route_b"
    assert payload["candidate_sha256"] == candidate_sha
    assert payload["results"] == {
        "V0": "passed", "V1": "passed", "V2": "not_run",
        "V3": "not_run", "V4": "not_run", "V5": "not_run",
    }
    assert set(payload["evidence"]) == {"V0", "V1"}

    worker.run_once(data_dir=data)
    finished = jobs.get_attempt(attempt.id, data_dir=data)
    assert finished is not None
    assert finished.phase == "finished"
    assert finished.outcome == "inconclusive"
    assert finished.reason == "required_check_not_run"
    obligations = jobs.list_obligations(attempt.id, data_dir=data)
    assert len(obligations) == 6
    by_kind = {row["kind"]: row for row in obligations}
    assert by_kind["identity"]["result"] == "passed"
    assert by_kind["structure"]["result"] == "passed"
    assert by_kind["identity"]["result"] == "passed"


def _contract_file(tmp_path: Path, data: Path, job_id: str, run) -> Path:
    from app.db.connection import connect
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT body_json FROM contracts WHERE id = ? AND job_id = ?",
            (run.contract_id, job_id),
        ).fetchone()
    finally:
        connection.close()
    path = tmp_path / "run-contract.json"
    path.write_bytes(row["body_json"].encode("utf-8"))
    assert run.reviewed_scope_sha256 == __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    return path


def test_routeb_uses_worker_original_and_contract_paths(tmp_path: Path) -> None:
    data, job, run, attempt = _setup(tmp_path)
    bundle, _ = _bundle(tmp_path)
    (bundle / "original.elf").unlink()
    original = tmp_path / "original.elf"
    original.write_bytes(ORIGINAL.read_bytes())
    contract = _contract_file(tmp_path, data, job.id, run)
    result = write_attempt(bundle=bundle, data_dir=data, job_id=job.id,
                           run_id=run.id, attempt_id=attempt.id,
                           original_path=original, contract_path=contract)
    assert result["payload"]["results"]["V0"] == "passed"
    assert Path(result["path"]).exists()


def test_routeb_fails_closed_on_missing_worker_contract(tmp_path: Path) -> None:
    data, job, run, attempt = _setup(tmp_path)
    bundle, _ = _bundle(tmp_path)
    original = tmp_path / "original.elf"
    original.write_bytes(ORIGINAL.read_bytes())
    with pytest.raises(ValueError, match="BINARYREPAIR_CONTRACT is not readable"):
        write_attempt(bundle=bundle, data_dir=data, job_id=job.id,
                      run_id=run.id, attempt_id=attempt.id,
                      original_path=original, contract_path=tmp_path / "missing.json")


def test_manifest_compare_is_not_repair_v3(tmp_path: Path) -> None:
    data, job, run, attempt = _setup(tmp_path)
    bundle, _ = _bundle(tmp_path)
    (bundle / "manifest-compare.json").write_text(json.dumps({
        "gate4_pass": True, "total": 6, "same_count": 6,
    }), encoding="utf-8")
    result = write_attempt(bundle=bundle, data_dir=data, job_id=job.id,
                           run_id=run.id, attempt_id=attempt.id)
    payload = json.loads(Path(result["path"]).read_text())
    assert payload["results"]["V3"] == "not_run"
    assert "V3" not in payload["evidence"]
    assert "round-trip" in payload["details"]["V3"]
