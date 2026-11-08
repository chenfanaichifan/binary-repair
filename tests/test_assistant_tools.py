"""M2 seam between the agent runtime and the M5 v2 tool adapters.

These tests mock the runner/HTTP boundary so they run on Windows without
`readelf` or an executable guest binary.  They pin request validation, dispatch
choice, and the v2 status envelopes the agent consumes.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from app.services import assistant_tools
from tools import mcp_tool_adapters


def _files(tmp_path: Path) -> tuple[Path, Path, Path]:
    binary = tmp_path / "candidate.elf"
    binary.write_bytes(b"\x7fELF")
    original = tmp_path / "original.elf"
    original.write_bytes(b"\x7fELF")
    tests = tmp_path / "tests"
    tests.mkdir()
    return binary, original, tests


def test_specs_cover_the_three_v2_tools():
    specs = assistant_tools.tool_specs()
    names = {spec["function"]["name"] for spec in specs}
    assert names == {"run_case", "read_evidence", "apply_candidate"}
    for spec in specs:
        schema = spec["function"]["parameters"]
        assert schema["properties"]["schema_version"]["const"] == 2
        assert spec["function"]["description"]


def test_unknown_tool_is_a_runtime_error():
    with pytest.raises(assistant_tools.ToolCallError) as exc:
        assistant_tools.call_tool("nope", {"schema_version": 2})
    assert exc.value.reason == "unknown_tool"


def test_wrong_schema_version_is_a_runtime_error():
    with pytest.raises(assistant_tools.ToolCallError) as exc:
        assistant_tools.call_tool("read_evidence", {"schema_version": 1,
                                                   "attempt_id": "a"})
    assert exc.value.reason == "invalid_request"


def test_run_case_none_with_original_dispatches_to_compare(monkeypatch, tmp_path):
    binary, original, tests = _files(tmp_path)
    seen = {}

    def fake(runner, args, *, timeout_ms):
        seen["runner"] = Path(runner).name
        seen["args"] = args
        return {"status": "passed", "timed_out": False, "returncode": 0,
                "stdout": "", "stderr": "",
                "result": {"repaired_pass": True, "passed": 1, "total": 1,
                           "cases": [{"id": "c", "ok": True}]}}

    monkeypatch.setattr(mcp_tool_adapters, "_run_manifest", fake)
    out = assistant_tools.call_tool("run_case", {
        "schema_version": 2, "binary_path": str(binary),
        "original_path": str(original), "tests_dir": str(tests),
        "input_mode": "none", "timeout_ms": 5000,
    })
    assert seen["runner"] == "run_manifest_compare.py"
    assert "--input-mode" in seen["args"]
    assert out["status"] == "passed"
    assert out["edge"]["invalid_applicable"] is False


def test_run_case_argv_dispatches_to_the_repaired_runner(monkeypatch, tmp_path):
    binary, _original, tests = _files(tmp_path)
    seen = {}

    def fake(runner, args, *, timeout_ms):
        seen["runner"] = Path(runner).name
        seen["args"] = args
        return {"status": "failed", "timed_out": False, "returncode": 0,
                "stdout": "", "stderr": "",
                "result": {"repaired_pass": False, "passed": 0, "total": 1,
                           "cases": [{"id": "c", "ok": False}]}}

    monkeypatch.setattr(mcp_tool_adapters, "_run_manifest", fake)
    out = assistant_tools.call_tool("run_case", {
        "schema_version": 2, "binary_path": str(binary),
        "tests_dir": str(tests), "input_mode": "argv",
    })
    assert seen["runner"] == "run_manifest_repaired.py"
    assert seen["args"][seen["args"].index("--input-mode") + 1] == "argv"
    assert out["status"] == "failed"


def test_run_case_rejects_a_raw_argv_list(tmp_path):
    binary, _original, tests = _files(tmp_path)
    out = assistant_tools.call_tool("run_case", {
        "schema_version": 2, "binary_path": str(binary),
        "tests_dir": str(tests), "input_mode": "argv", "argv": ["x"],
    })
    assert out["status"] == "invalid_request"
    assert out["reason"] == "invalid_request"


class _Response:
    def __init__(self, payload: dict) -> None:
        self.status = 200
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_read_evidence_maps_input_mode_and_drops_invented_sha256(monkeypatch):
    payload = {
        "attempt_id": "attempt-1", "run_id": "run-1", "route": "route_b",
        "evidence": "persisted", "result": "passed",
        "gates": [{"gate": "V3", "kind": "behaviour", "result": "passed"}],
        "v3": {"gate": "V3", "kind": "behaviour", "result": "passed",
               "input_mode": "none",
               "valid": {"passed": 1, "total": 1},
               "invalid": {"passed": 0, "total": 0},
               "invalid_applicable": False},
        "obligations": {"A": [], "B": []},
        "sha256": "should-be-dropped",
    }
    monkeypatch.setattr(mcp_tool_adapters.urllib.request, "urlopen",
                        lambda url, timeout: _Response(payload))
    out = assistant_tools.call_tool("read_evidence", {
        "schema_version": 2, "attempt_id": "attempt-1",
    })
    assert out["status"] == "ok"
    assert out["input_mode"] == "none"
    assert out["v3"]["input_mode"] == "none"
    assert out["v3"]["legacy_invalid_applicable"] is True
    assert "sha256" not in out["v3"]


def test_read_evidence_404_is_not_found(monkeypatch):
    def raise_404(url, timeout):
        raise urllib.error.HTTPError(url, 404, "not found", None, None)

    monkeypatch.setattr(mcp_tool_adapters.urllib.request, "urlopen", raise_404)
    out = assistant_tools.call_tool("read_evidence", {
        "schema_version": 2, "attempt_id": "missing",
    })
    assert out["status"] == "not_found"


def test_apply_candidate_dry_run_checks_the_hash_and_writes_nothing(
        monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    candidate = "a" * 64
    (bundle / "bundle.json").write_text(
        json.dumps({"candidate_sha256": candidate}), encoding="utf-8")

    def explode(*args, **kwargs):
        raise AssertionError("dry_run must not reach ingest")

    monkeypatch.setattr("tools.route_bundle_ingest.ingest", explode)
    out = assistant_tools.call_tool("apply_candidate", {
        "schema_version": 2, "job_id": "job-1", "run_id": "run-1",
        "attempt_id": "attempt-1", "bundle_path": str(bundle),
        "candidate_sha256": candidate, "dry_run": True,
    })
    assert out["status"] == "no_op"
    assert out["bundle_path"] == str(bundle)


def test_apply_candidate_hash_mismatch_is_rejected(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "bundle.json").write_text(
        json.dumps({"candidate_sha256": "b" * 64}), encoding="utf-8")
    out = assistant_tools.call_tool("apply_candidate", {
        "schema_version": 2, "job_id": "job-1", "run_id": "run-1",
        "attempt_id": "attempt-1", "bundle_path": str(bundle),
        "candidate_sha256": "a" * 64,
    })
    assert out["status"] == "rejected"
    assert out["reason"] == "candidate_hash_mismatch"
