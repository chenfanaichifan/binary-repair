from __future__ import annotations

import copy

import pytest

from app.domain.v4 import V4EvidenceError, validate_v4_evidence

H = "a" * 64
C = "b" * 64
O = "c" * 64


def _valid() -> dict:
    return {
        "schema_version": 1,
        "gate": "V4",
        "kind": "symbolic",
        "scope": "model",
        "state": "passed",
        "ran": True,
        "candidate_sha256": C,
        "original_sha256": O,
        "tool_versions": {"angr": "10.0.4.post1", "z3": "5.1.0"},
        "preconditions": ["no ASLR", "one no-input path"],
        "property_kind": "pointer-flow",
        "memory_predicates": ["data points to a freed chunk"],
        "forbidden_ranges": [{"start": 0, "end": 64, "reason": "freed object"}],
        "hooks": ["after free", "before read"],
        "exploration_accounting": {
            "initial": 12,
            "deadended": 10,
            "errored": 0,
            "unconstrained": 0,
            "deferred": 0,
            "active": 0,
            "pruned": 2,
            "complete": True,
            "unexplored": [],
        },
        "solver_accounting": {
            "engine": "z3",
            "version": "5.1.0",
            "queries": 12,
            "sat": 1,
            "unsat": 11,
            "unknown": 0,
            "eval": 0,
            "timeouts": 0,
            "steps": 80,
            "max_steps": 200,
            "complete": True,
        },
        "calibration": {
            "suite": "known-safe/known-bad",
            "cases": 3,
            "passed": 2,
            "failed": 1,
            "known_good": True,
            "known_bad": True,
            "known_bad_rejected": True,
            "complete": True,
        },
        "replay": {
            "command": "angr replay",
            "runs": 2,
            "identical": True,
            "evidence_sha256": H,
        },
        "claimed_scope": "model",
        "not_claimed": ["binary-level proof"],
    }


def test_complete_v4_evidence_is_accepted() -> None:
    loaded = validate_v4_evidence(_valid(), candidate_sha256=C, original_sha256=O)
    assert loaded.state == "passed"
    assert loaded.replay.runs == 2


@pytest.mark.parametrize(
    "field",
    [
        "candidate_sha256",
        "original_sha256",
        "tool_versions",
        "preconditions",
        "memory_predicates",
        "hooks",
        "exploration_accounting",
        "solver_accounting",
        "calibration",
        "replay",
        "property_kind",
        "claimed_scope",
        "not_claimed",
    ],
)
def test_missing_v4_section_is_not_verified(field: str) -> None:
    data = copy.deepcopy(_valid())
    del data[field]
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_incomplete_solver_or_replay_is_not_verified() -> None:
    data = copy.deepcopy(_valid())
    data["solver_accounting"]["complete"] = False
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)
    data = copy.deepcopy(_valid())
    data["replay"]["identical"] = False
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_hash_mismatch_is_not_verified() -> None:
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(_valid(), candidate_sha256="d" * 64)
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(_valid(), original_sha256="d" * 64)


def test_write_v4_evidence_only_writes_validated_content(tmp_path) -> None:
    from app.domain.v4 import write_v4_evidence

    path = tmp_path / "v4.json"
    write_v4_evidence(path, _valid(), candidate_sha256=C, original_sha256=O)
    assert path.is_file()
    assert validate_v4_evidence(__import__("json").loads(path.read_text()), candidate_sha256=C)

    bad = tmp_path / "bad.json"
    data = copy.deepcopy(_valid())
    del data["solver_accounting"]
    with pytest.raises(V4EvidenceError):
        write_v4_evidence(bad, data)
    assert not bad.exists()


def test_step_cap_and_missing_pruned_accounting_are_not_verified() -> None:
    data = copy.deepcopy(_valid())
    data["solver_accounting"]["steps"] = data["solver_accounting"]["max_steps"]
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)

    data = copy.deepcopy(_valid())
    del data["exploration_accounting"]["pruned"]
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


@pytest.mark.parametrize("field", ["known_good", "known_bad", "known_bad_rejected"])
def test_calibration_requires_all_known_controls(field: str) -> None:
    data = copy.deepcopy(_valid())
    data["calibration"][field] = False
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_complete_exploration_cannot_have_unexplored_states() -> None:
    data = copy.deepcopy(_valid())
    data["exploration_accounting"]["unexplored"] = ["state-1"]
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_complete_solver_cannot_have_unknown_or_timeout() -> None:
    data = copy.deepcopy(_valid())
    data["solver_accounting"]["unknown"] = 1
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)
    data = copy.deepcopy(_valid())
    data["solver_accounting"]["timeouts"] = 1
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_claimed_scope_is_model_only() -> None:
    data = copy.deepcopy(_valid())
    data["claimed_scope"] = "bound 64"
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_not_claimed_must_exclude_binary_level() -> None:
    data = copy.deepcopy(_valid())
    data["not_claimed"] = ["memory-safety on other paths"]
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_calibration_cases_one_is_rejected() -> None:
    data = copy.deepcopy(_valid())
    data["calibration"].update({
        "cases": 1, "passed": 1, "failed": 0,
        "known_good": True, "known_bad": True, "known_bad_rejected": True,
    })
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_known_bad_rejected_requires_failed_case() -> None:
    data = copy.deepcopy(_valid())
    data["calibration"].update({
        "cases": 2, "passed": 2, "failed": 0,
        "known_good": True, "known_bad": True, "known_bad_rejected": True,
    })
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)


def test_pointer_flow_may_have_empty_forbidden_ranges() -> None:
    data = copy.deepcopy(_valid())
    data["forbidden_ranges"] = []
    validate_v4_evidence(data)


def test_memory_range_needs_a_forbidden_range() -> None:
    data = copy.deepcopy(_valid())
    data["property_kind"] = "memory-range"
    data["forbidden_ranges"] = []
    with pytest.raises(V4EvidenceError):
        validate_v4_evidence(data)
