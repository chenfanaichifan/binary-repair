from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools import mcp_tool_adapters as adapters

# run_case executes the binary through run_manifest_compare.py, which requires a
# real ELF. That is ELF execution semantics, not generic subprocess dispatch, so
# these cases are skipped on Windows instead of being pointed at sys.executable.
_ELF_RUNNER_REQUIRED = pytest.mark.skipif(
    os.name == "nt",
    reason="run_case executes a real ELF through run_manifest_compare.py",
)


def _valid_none(tmp_path: Path) -> Path:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "valid.json").write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "id": "valid-no-input",
                        "kind": "valid",
                        "argv": ["/usr/bin/true"],
                        "expected": {
                            "return_code": 0,
                            "stdout": "",
                            "stderr": "",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return tests


@_ELF_RUNNER_REQUIRED
def test_run_case_none_dispatches_to_repaired_runner(tmp_path: Path) -> None:
    tests = _valid_none(tmp_path)
    response = adapters.run_case(
        {
            "schema_version": 2,
            "case_id": "valid-no-input",
            "binary_path": "/usr/bin/true",
            "original_path": "/usr/bin/true",
            "tests_dir": str(tests),
            "input_mode": "none",
            "timeout_ms": 5000,
        }
    )
    assert response["status"] == "passed"
    assert response["repaired_pass"] is True
    assert response["passed"] == 1
    assert response["total"] == 1
    assert response["edge"]["invalid_applicable"] is False


def test_run_case_rejects_fake_stdin(tmp_path: Path) -> None:
    tests = _valid_none(tmp_path)
    with pytest.raises(adapters.ToolError) as exc:
        adapters.run_case(
            {
                "schema_version": 2,
                "binary_path": "/usr/bin/true",
                "original_path": "/usr/bin/true",
                "tests_dir": str(tests),
                "input_mode": "none",
                "stdin_literal": "x",
            }
        )
    assert exc.value.reason == "invalid_request"


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status = 200
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_read_evidence_maps_input_mode_and_drops_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "attempt_id": "a1",
        "run_id": "r1",
        "route": "route_b",
        "evidence": "persisted",
        "gates": [{"gate": "V3"}],
        "v3": {
            "gate": "V3",
            "input_mode": "none",
            "valid": {"passed": 1, "total": 1},
            "invalid": {"passed": 0, "total": 0},
            "sha256": "must-be-dropped",
        },
        "obligations": {"A": [], "B": []},
    }
    monkeypatch.setattr(adapters.urllib.request, "urlopen", lambda *a, **k: _Response(payload))
    response = adapters.read_evidence(
        {"schema_version": 2, "attempt_id": "a1", "base_url": "http://x"}
    )
    assert response["status"] == "ok"
    assert response["input_mode"] == "none"
    assert "sha256" not in response["v3"]
    assert response["v3"]["legacy_invalid_applicable"] is True


def _bundle(tmp_path: Path, candidate: str) -> Path:
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "bundle.json").write_text(
        json.dumps({"candidate_sha256": candidate, "route": "route_b"}),
        encoding="utf-8",
    )
    return root


def test_apply_candidate_dry_run_checks_hash(tmp_path: Path) -> None:
    candidate = "a" * 64
    bundle = _bundle(tmp_path, candidate)
    response = adapters.apply_candidate(
        {
            "schema_version": 2,
            "job_id": "j1",
            "run_id": "r1",
            "attempt_id": "a1",
            "bundle_path": str(bundle),
            "candidate_sha256": candidate,
            "dry_run": True,
        }
    )
    assert response["status"] == "no_op"
    assert response["candidate_sha256"] == candidate


def test_apply_candidate_rejects_hash_mismatch(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, "b" * 64)
    with pytest.raises(adapters.ToolError) as exc:
        adapters.apply_candidate(
            {
                "schema_version": 2,
                "job_id": "j1",
                "run_id": "r1",
                "attempt_id": "a1",
                "bundle_path": str(bundle),
                "candidate_sha256": "a" * 64,
                "dry_run": True,
            }
        )
    assert exc.value.reason == "candidate_hash_mismatch"


def _argv_tests(tmp_path: Path, *, include_invalid: bool = True) -> Path:
    tests = tmp_path / "tests"
    tests.mkdir()
    case = {
        "id": "v1",
        "kind": "valid",
        "argv": ["/usr/bin/true", "x"],
        "expected": {"return_code": 0, "stdout": "", "stderr": ""},
    }
    (tests / "valid.json").write_text(json.dumps({"tests": [case]}), encoding="utf-8")
    if include_invalid:
        bad = {
            "id": "i1",
            "kind": "invalid",
            "argv": ["/usr/bin/false", "x"],
            "expected": {"return_code": 1, "stdout": "", "stderr": ""},
        }
        (tests / "invalid.json").write_text(json.dumps({"tests": [bad]}), encoding="utf-8")
    return tests


@_ELF_RUNNER_REQUIRED
def test_run_case_timeout_has_machine_reason(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "valid.json").write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "id": "slow",
                        "kind": "valid",
                        "argv": ["/bin/sleep", "2"],
                        "expected": {"return_code": 0, "stdout": "", "stderr": ""},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tests / "invalid.json").write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "id": "slow-bad",
                        "kind": "invalid",
                        "argv": ["/bin/sleep", "2"],
                        "expected": {"return_code": 1, "stdout": "", "stderr": ""},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    response = adapters.run_case(
        {
            "schema_version": 2,
            "case_id": "slow",
            "binary_path": "/bin/sleep",
            "tests_dir": str(tests),
            "input_mode": "argv",
            "timeout_ms": 100,
        }
    )
    assert response["status"] == "timeout"
    assert response["reason"] == "timeout_observed"
    assert response["edge"]["timeout"] is True


@_ELF_RUNNER_REQUIRED
def test_run_case_incomplete_set_is_machine_reason(tmp_path: Path) -> None:
    tests = _argv_tests(tmp_path, include_invalid=False)
    response = adapters.run_case(
        {
            "schema_version": 2,
            "case_id": "v1",
            "binary_path": "/usr/bin/true",
            "tests_dir": str(tests),
            "input_mode": "argv",
            "timeout_ms": 2000,
        }
    )
    assert response["status"] == "incomplete_test_set"
    assert response["reason"] == "incomplete_test_set"


def test_apply_candidate_maps_ingest_hash_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import tools.route_bundle_ingest as rbi

    candidate = "c" * 64
    bundle = _bundle(tmp_path, candidate)

    def fake_ingest(**kwargs: object) -> dict[str, object]:
        raise rbi.IngestError("artifact hash does not match recorded evidence")

    monkeypatch.setattr(rbi, "ingest", fake_ingest)
    with pytest.raises(adapters.ToolError) as exc:
        adapters.apply_candidate(
            {
                "schema_version": 2,
                "job_id": "j1",
                "run_id": "r1",
                "attempt_id": "a1",
                "bundle_path": str(bundle),
                "candidate_sha256": candidate,
                "data_dir": str(tmp_path),
            }
        )
    assert exc.value.reason == "evidence_hash_mismatch"
