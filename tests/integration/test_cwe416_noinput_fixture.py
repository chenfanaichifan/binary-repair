"""The accepted CWE416 no-input fixture reaches the controller/worker boundary.

This is a wiring test, not a repair: there is no candidate, so it must not create
any V0-V5 obligation or move the run out of ``queued``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services import jobs, worker

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput"
REJECTION_FIELDS = (
    "invalid_input_response",
    "invalid_exit_code",
    "invalid_stdout",
    "invalid_stderr",
    "max_valid_input_bytes",
)


def test_cwe416_noinput_fixture_reaches_worker_without_gate_upgrade(
    tmp_path: Path,
) -> None:
    contract = json.loads((FIXTURE / "contract.json").read_text(encoding="utf-8"))
    assert contract["schema_version"] == 3
    assert contract["input_mode"] == "none"
    assert all(field not in contract for field in REJECTION_FIELDS)
    valid = json.loads((FIXTURE / "tests/valid.json").read_text(encoding="utf-8"))
    assert len(valid["tests"]) == 1
    assert not (FIXTURE / "tests/invalid.json").exists()

    data_dir = tmp_path / "var"
    record = jobs.create_job(
        original_bytes=(FIXTURE / "original.elf").read_bytes(),
        filename="CWE416_Use_After_Free__malloc_free_char_01_noinput.elf",
        defect_description="use after free: read the freed block",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        record.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data_dir,
        contract_body=contract,
        input_sha256=record.original_sha256,
    )
    run = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="cwe416-noinput-wiring",
        data_dir=data_dir,
    )
    assert run.phase == "queued"

    # The worker can materialise the verified original and the approved v3
    # contract, but nothing has executed yet.
    original_path, contract_path = worker._executor_inputs(
        data_dir, record.id, run.id
    )
    assert hashlib.sha256(original_path.read_bytes()).hexdigest() == record.original_sha256
    body = json.loads(contract_path.read_text(encoding="utf-8"))
    assert body["schema_version"] == 3
    assert body["input_mode"] == "none"
    assert all(field not in body for field in REJECTION_FIELDS)
    assert hashlib.sha256(contract_path.read_bytes()).hexdigest() == run.reviewed_scope_sha256

    attempts = jobs.list_attempts(run.id, data_dir=data_dir)
    assert len(attempts) == 2
    assert {attempt.phase for attempt in attempts} == {"queued"}
    assert {attempt.outcome for attempt in attempts} == {None}
    for attempt in attempts:
        assert jobs.list_obligations(attempt.id, data_dir=data_dir) == []
    assert jobs.get_run(run.id, data_dir=data_dir).phase == "queued"
