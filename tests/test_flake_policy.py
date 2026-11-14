"""Tests for scripts/check_flake_policy.py (offline, tmp registries)."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_flake_policy as flake  # noqa: E402

AS_OF = date(2026, 11, 15)


def _prohibited() -> list[str]:
    return list(flake.REQUIRED_PROHIBITED)


def _entry(**overrides) -> dict:
    entry = {
        "test_id": "tests/test_binary_review.py::test_accept_concurs_but_deterministic_gate_is_authority",
        "owner": "release-owner",
        "reason": "observed intermittent browser timeout on the e2e path",
        "opened": "2026-11-10",
        "expiry": "2026-11-17",
        "evidence": "artifacts/logs/flake-2026-11-10.txt",
    }
    entry.update(overrides)
    return entry


def _registry(*, entries: list[dict] | None = None,
              prohibited: list[str] | None = None) -> dict:
    payload = {
        "schema_version": 1,
        "generated_at": "2026-11-15T00:00:00+08:00",
        "entries": list(entries or []),
        "prohibited": _prohibited() if prohibited is None else prohibited,
    }
    return payload


def _evaluate(payload: dict) -> dict:
    return flake.evaluate_registry(payload, as_of=AS_OF)


def _write_registry(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_empty_registry_is_valid() -> None:
    report = _evaluate(_registry())
    assert report["ok"] is True
    assert report["violations"] == []
    assert report["entry_count"] == 0
    assert report["active_count"] == 0
    assert report["prohibited_count"] == len(flake.REQUIRED_PROHIBITED)


def test_single_valid_entry_passes() -> None:
    report = _evaluate(_registry(entries=[_entry()]))
    assert report["ok"] is True, report["violations"]
    assert report["entry_count"] == 1
    assert report["active_count"] == 1


def test_missing_entry_fields_fail() -> None:
    entry = _entry()
    del entry["owner"]
    del entry["evidence"]
    report = _evaluate(_registry(entries=[entry]))
    assert report["ok"] is False
    joined = " ".join(report["violations"])
    assert "missing fields" in joined
    assert "owner" in joined and "evidence" in joined


def test_quarantine_window_over_14_days_fails() -> None:
    report = _evaluate(_registry(entries=[
        _entry(opened="2026-11-01", expiry="2026-11-20"),
    ]))
    assert report["ok"] is False
    assert any("max 14" in item for item in report["violations"])


def test_expiry_before_opened_fails() -> None:
    report = _evaluate(_registry(entries=[
        _entry(opened="2026-11-12", expiry="2026-11-11"),
    ]))
    assert report["ok"] is False
    assert any("before opened" in item for item in report["violations"])


def test_expired_quarantine_fails() -> None:
    report = _evaluate(_registry(entries=[
        _entry(opened="2026-10-20", expiry="2026-10-27"),
    ]))
    assert report["ok"] is False
    assert any("expired" in item for item in report["violations"])
    assert report["active_count"] == 0


def test_missing_test_file_fails() -> None:
    report = _evaluate(_registry(entries=[
        _entry(test_id="tests/test_this_file_does_not_exist.py::test_x"),
    ]))
    assert report["ok"] is False
    assert any("does not exist" in item for item in report["violations"])


def test_test_id_outside_tests_is_rejected() -> None:
    report = _evaluate(_registry(entries=[
        _entry(test_id="app/main.py::test_x"),
    ]))
    assert report["ok"] is False
    assert any("tests/*.py" in item for item in report["violations"])


def test_gate_critical_test_cannot_be_quarantined() -> None:
    for test_id in (
        "tests/test_target_scope.py::test_target_scope_filters_sink",
        "tests/test_acceptance_invariants.py::test_verified_requires_profile",
        "tests/test_release_gate.py::test_pr_mode",
        "tests/test_provider_matrix.py::test_records",
        "tests/test_capability_audit.py::test_static_audit",
        "tests/test_coverage_gate.py::test_static_gate_json_exposes_roadmap_sync",
        "tests/test_ci_evidence.py::test_ci_evidence_claim",
        "tests/test_contract_revision.py::test_claims",
    ):
        report = _evaluate(_registry(entries=[_entry(test_id=test_id)]))
        assert report["ok"] is False, test_id
        assert any("gate-critical" in item for item in report["violations"]), test_id


def test_registry_must_declare_all_required_prohibited_patterns() -> None:
    prohibited = _prohibited()
    prohibited.remove("tests/test_release_gate.py::*")
    report = _evaluate(_registry(prohibited=prohibited))
    assert report["ok"] is False
    assert report["missing_required_prohibited"] == ["tests/test_release_gate.py::*"]


def test_empty_prohibited_list_fails() -> None:
    report = _evaluate(_registry(prohibited=[]))
    assert report["ok"] is False
    assert any("prohibited" in item for item in report["violations"])


def test_duplicate_test_id_fails() -> None:
    report = _evaluate(_registry(entries=[_entry(), _entry()]))
    assert report["ok"] is False
    assert any("duplicate test_id" in item for item in report["violations"])


def test_bad_evidence_shape_fails() -> None:
    for bad in (None, "", [], [""], 42):
        report = _evaluate(_registry(entries=[_entry(evidence=bad)]))
        assert report["ok"] is False, bad
        assert any("evidence" in item for item in report["violations"]), bad


def test_bad_schema_and_generated_at_fail() -> None:
    payload = _registry()
    payload["schema_version"] = "1"
    payload["generated_at"] = "not-a-date"
    report = _evaluate(payload)
    assert report["ok"] is False
    joined = " ".join(report["violations"])
    assert "schema_version" in joined
    assert "generated_at" in joined


def test_real_registry_is_valid_and_empty() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_flake_policy.py"),
         "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["entry_count"] == 0
    assert payload["prohibited"] == list(flake.REQUIRED_PROHIBITED)


def test_cli_fails_on_tampered_registry(tmp_path: Path) -> None:
    payload = _registry(entries=[
        _entry(test_id="tests/test_target_scope.py::test_x"),
    ])
    registry = _write_registry(tmp_path, payload)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_flake_policy.py"),
         "--registry", str(registry), "--as-of", "2026-11-15", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is False


def test_cli_unreadable_registry_exits_2(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("{not json", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_flake_policy.py"),
         "--registry", str(registry), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 2


def test_registry_entry_deep_copy_isolation() -> None:
    """A valid registry must not be mutated by evaluation."""
    payload = _registry(entries=[_entry()])
    before = copy.deepcopy(payload)
    report = _evaluate(payload)
    assert report["ok"] is True
    assert payload == before
