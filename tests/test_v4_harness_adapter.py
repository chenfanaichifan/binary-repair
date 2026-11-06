from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.v4 import (
    V4EvidenceError,
    from_v4_harness,
    validate_v4_evidence,
    write_v4_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/fixtures/v4_harness_output.json"


def test_real_v4_harness_output_converts_to_product_schema() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    evidence = from_v4_harness(data)
    assert evidence.candidate_sha256 == data["candidate_sha256"]
    assert evidence.original_sha256 == data["original_sha256"]
    assert evidence.claimed_scope == "model"
    assert evidence.calibration.cases == 2
    assert evidence.calibration.passed == 1
    assert evidence.calibration.failed == 1
    assert evidence.calibration.known_good is True
    assert evidence.calibration.known_bad_rejected is True
    assert evidence.exploration_accounting.deadended == 2
    assert evidence.exploration_accounting.unexplored == []
    assert evidence.solver_accounting.queries == 4
    assert evidence.source["entry_address"] == "0x4012aa"
    assert evidence.source["contract_sha256"]


def test_converted_evidence_round_trips_through_product_writer(tmp_path: Path) -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    evidence = from_v4_harness(data)
    path = tmp_path / "v4-symbolic.json"
    write_v4_evidence(path, evidence)
    loaded = validate_v4_evidence(
        json.loads(path.read_text(encoding="utf-8")),
        candidate_sha256=evidence.candidate_sha256,
        original_sha256=evidence.original_sha256,
    )
    assert loaded.exploration_accounting.initial == 2
    assert loaded.replay.runs == 2


def test_converter_rejects_incomplete_harness_output() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    del data["states"]
    with pytest.raises(V4EvidenceError):
        from_v4_harness(data)


def test_adapter_adds_empty_disjunction_disclosure_without_evidence_defaults() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    data["not_claimed"] = [
        item for item in data["not_claimed"]
        if "empty-disjunction" not in item.lower()
    ]
    evidence = from_v4_harness(data)
    assert any("empty-disjunction" in item.lower() for item in evidence.not_claimed)
    assert evidence.forbidden_ranges is None
    assert "forbidden_ranges" not in evidence.model_dump(exclude_none=True)


def test_adapter_does_not_invent_missing_negative_control() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    data["cases"] = [case for case in data["cases"] if case["kind"] != "known_bad"]
    with pytest.raises(V4EvidenceError):
        from_v4_harness(data)


def test_adapter_does_not_invent_missing_accounting() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    del data["solver"]["sat"]
    with pytest.raises(V4EvidenceError):
        from_v4_harness(data)


def test_adapter_requires_every_known_bad_case_rejected() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    bad = next(case for case in data["cases"] if case["kind"] == "known_bad")
    second = json.loads(json.dumps(bad))
    second["id"] = "known_bad_second"
    second["observed"] = "holds"
    data["cases"].append(second)
    with pytest.raises(V4EvidenceError):
        from_v4_harness(data)


def test_adapter_does_not_add_disclosure_when_free_calls_is_nonzero() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    data["not_claimed"] = [
        item for item in data["not_claimed"]
        if "empty-disjunction" not in item.lower()
    ]
    good = next(case for case in data["cases"] if case["kind"] == "known_good")
    good["witness"]["free_calls"] = 1
    evidence = from_v4_harness(data)
    assert not any(
        "empty-disjunction" in item.lower() for item in evidence.not_claimed
    )


def test_adapter_rejects_missing_property_kind_without_text_inference() -> None:
    data = json.loads(HARNESS.read_text(encoding="utf-8"))
    del data["property_kind"]
    # property_text still says "pointer"; the adapter must not infer from it.
    with pytest.raises(V4EvidenceError):
        from_v4_harness(data)
