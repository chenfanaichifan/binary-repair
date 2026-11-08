"""Tests for the host-side attempt driver (Route B wiring, fail-closed paths).

The driver is the host half of the executor contract: the worker supplies the
environment, the guest supplies the static bundle, and the driver only maps
measured evidence to the worker result bundle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services import attempt_driver, jobs


def _route_b_attempt(tmp_path: Path):
    data_dir = tmp_path / "var"
    record = jobs.create_job(
        original_bytes=b"\x7fELF driver original",
        filename="sample.elf",
        defect_description="driver test",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        record.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data_dir,
        input_sha256=record.original_sha256,
        manifest_sha256="2" * 64,
    )
    run = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="driver-1",
        data_dir=data_dir,
    )
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data_dir)
        if item.route == "route_b"
    )
    return data_dir, record, run, attempt


def _write_bundle(bundle: Path, *, original_sha256: str, candidate: bytes | None = None) -> None:
    candidate = candidate if candidate is not None else b"\x7fELF candidate"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "candidate.elf").write_bytes(candidate)
    (bundle / "audit.json").write_text('{"pass": true}', encoding="utf-8")
    (bundle / "edit-manifest.json").write_text(
        json.dumps(
            {
                "route": "route_b",
                "original_sha256": original_sha256,
                "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


def _set_env(monkeypatch, *, data_dir: Path, record, run, attempt, bundle: Path | None):
    result = data_dir / "jobs" / record.id / "runs" / run.id / "attempts" / f"{attempt.id}.json"
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data_dir))
    monkeypatch.setenv("BINARYREPAIR_JOB_ID", record.id)
    monkeypatch.setenv("BINARYREPAIR_RUN_ID", run.id)
    monkeypatch.setenv("BINARYREPAIR_ATTEMPT_ID", attempt.id)
    monkeypatch.setenv("BINARYREPAIR_ROUTE", "route_b")
    monkeypatch.setenv("BINARYREPAIR_RESULT_PATH", str(result))
    if bundle is None:
        monkeypatch.delenv("BINARYREPAIR_ROUTEB_BUNDLE", raising=False)
    else:
        monkeypatch.setenv("BINARYREPAIR_ROUTEB_BUNDLE", str(bundle))
    return result


def test_routeb_bundle_maps_to_worker_result(tmp_path: Path, monkeypatch) -> None:
    data_dir, record, run, attempt = _route_b_attempt(tmp_path)
    bundle = tmp_path / "guest-bundle"
    _write_bundle(bundle, original_sha256=record.original_sha256)
    result = _set_env(
        monkeypatch, data_dir=data_dir, record=record, run=run, attempt=attempt, bundle=bundle
    )

    assert attempt_driver.main([]) == 0

    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["route"] == "route_b"
    assert payload["candidate_sha256"] == hashlib.sha256(b"\x7fELF candidate").hexdigest()
    assert payload["results"]["V0"] == "passed"
    assert payload["results"]["V1"] == "passed"
    # The static bundle proves nothing about behaviour or reproducibility.
    assert payload["results"]["V2"] == "not_run"
    assert payload["results"]["V3"] == "not_run"
    assert payload["results"]["V4"] == "not_run"
    assert payload["results"]["V5"] == "not_run"


def test_canonical_staging_path_is_used_without_an_override(
    tmp_path: Path, monkeypatch
) -> None:
    data_dir, record, run, attempt = _route_b_attempt(tmp_path)
    bundle = attempt_driver.routeb_bundle_dir(data_dir, record.id, run.id, attempt.id)
    _write_bundle(bundle, original_sha256=record.original_sha256)
    result = _set_env(
        monkeypatch, data_dir=data_dir, record=record, run=run, attempt=attempt, bundle=None
    )

    assert attempt_driver.main([]) == 0
    assert json.loads(result.read_text(encoding="utf-8"))["results"]["V0"] == "passed"


def test_missing_bundle_fails_closed(tmp_path: Path, monkeypatch) -> None:
    data_dir, record, run, attempt = _route_b_attempt(tmp_path)
    result = _set_env(
        monkeypatch, data_dir=data_dir, record=record, run=run, attempt=attempt, bundle=None
    )

    with pytest.raises(SystemExit) as raised:
        attempt_driver.main([])

    assert raised.value.code == 3
    # Missing evidence must not produce a result bundle the worker would read.
    assert not result.exists()


def test_bundle_without_candidate_fails_closed(tmp_path: Path, monkeypatch) -> None:
    data_dir, record, run, attempt = _route_b_attempt(tmp_path)
    bundle = tmp_path / "guest-bundle"
    bundle.mkdir()
    (bundle / "audit.json").write_text('{"pass": true}', encoding="utf-8")
    result = _set_env(
        monkeypatch, data_dir=data_dir, record=record, run=run, attempt=attempt, bundle=bundle
    )

    with pytest.raises(SystemExit) as raised:
        attempt_driver.main([])

    assert raised.value.code == 3
    assert not result.exists()


def test_route_a_without_adapter_input_is_explicit(tmp_path: Path, monkeypatch) -> None:
    data_dir, record, run, _attempt = _route_b_attempt(tmp_path)
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data_dir))
    monkeypatch.setenv("BINARYREPAIR_JOB_ID", record.id)
    monkeypatch.setenv("BINARYREPAIR_RUN_ID", run.id)
    monkeypatch.setenv("BINARYREPAIR_ATTEMPT_ID", "attempt-a")
    monkeypatch.setenv("BINARYREPAIR_ROUTE", "route_a")
    monkeypatch.setenv("BINARYREPAIR_RESULT_PATH", str(tmp_path / "never.json"))
    monkeypatch.delenv("BINARYREPAIR_ATTEMPT_INPUT", raising=False)

    with pytest.raises(SystemExit) as raised:
        attempt_driver.main([])

    assert raised.value.code == 4
    assert not (tmp_path / "never.json").exists()


def test_incomplete_environment_is_rejected(monkeypatch) -> None:
    for name in attempt_driver.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit) as raised:
        attempt_driver.main([])

    assert raised.value.code == 2
