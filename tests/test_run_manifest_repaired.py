from __future__ import annotations

import json
from pathlib import Path

import pytest

from routeb import run_manifest_repaired as rep


def _binary(tmp_path: Path) -> Path:
    path = tmp_path / "candidate.elf"
    path.write_bytes(b"\x7fELF candidate")
    return path


def _no_input_tests(tmp_path: Path) -> Path:
    root = tmp_path / "tests"
    root.mkdir()
    (root / "valid.json").write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "id": "valid-only",
                        "kind": "valid",
                        "argv": ["./original"],
                        "expected": {"return_code": 0, "stdout": "OK\n", "stderr": ""},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


def _argv_tests(tmp_path: Path) -> Path:
    root = tmp_path / "tests"
    root.mkdir()
    (root / "valid.json").write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "id": "v",
                        "kind": "valid",
                        "argv": ["./original", "A"],
                        "expected": {"return_code": 0, "stdout": "A\n", "stderr": ""},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "invalid.json").write_text(
        json.dumps(
            {
                "tests": [
                    {
                        "id": "i",
                        "kind": "invalid",
                        "argv": ["./original", "B"],
                        "expected": {"return_code": 1, "stdout": "", "stderr": "ERR\n"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


def test_no_input_is_one_valid_zero_invalid(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_run(elf, arg=None, *, stdin_text=None):
        calls.append((arg, stdin_text))
        return {"returncode": 0, "stdout_hex": "4f4b0a", "stderr_hex": ""}

    monkeypatch.setattr(rep, "run", fake_run)
    result = rep.run_manifest(_binary(tmp_path), _no_input_tests(tmp_path), input_mode="none")

    assert result["input_mode"] == "none"
    assert result["invalid"] == "not_applicable"
    assert result["passed"] == result["total"] == 1
    assert result["repaired_pass"] is True
    assert calls == [(None, None)]


def test_no_input_rejects_an_invalid_manifest(tmp_path: Path, monkeypatch) -> None:
    tests = _no_input_tests(tmp_path)
    (tests / "invalid.json").write_text(
        json.dumps({"tests": []}), encoding="utf-8"
    )
    monkeypatch.setattr(rep, "run", lambda *a, **k: {})
    with pytest.raises(ValueError, match="must not ship"):
        rep.run_manifest(_binary(tmp_path), tests, input_mode="none")


def test_no_input_rejects_two_valid_cases(tmp_path: Path, monkeypatch) -> None:
    tests = _no_input_tests(tmp_path)
    data = json.loads((tests / "valid.json").read_text(encoding="utf-8"))
    data["tests"].append(dict(data["tests"][0], id="valid-second"))
    (tests / "valid.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(rep, "run", lambda *a, **k: {})
    with pytest.raises(ValueError, match="exactly 1 valid case"):
        rep.run_manifest(_binary(tmp_path), tests, input_mode="none")


def test_argv_mode_still_runs_the_argument(tmp_path: Path, monkeypatch) -> None:
    def fake_run(elf, arg=None, *, stdin_text=None):
        if arg == "A":
            return {"returncode": 0, "stdout_hex": "410a", "stderr_hex": ""}
        return {"returncode": 1, "stdout_hex": "", "stderr_hex": "4552520a"}

    monkeypatch.setattr(rep, "run", fake_run)
    result = rep.run_manifest(_binary(tmp_path), _argv_tests(tmp_path), input_mode="argv")

    assert result["input_mode"] == "argv"
    assert result["invalid"] == "measured"
    assert result["passed"] == result["total"] == 2
    assert result["repaired_pass"] is True


def test_runtime_state_reports_no_input_one_of_one(tmp_path: Path) -> None:
    from routeb.attempt_writer import runtime_state

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest-repaired.json").write_text(
        json.dumps(
            {
                "input_mode": "none",
                "invalid": "not_applicable",
                "passed": 1,
                "total": 1,
                "repaired_pass": True,
            }
        ),
        encoding="utf-8",
    )

    state, path, detail = runtime_state(bundle)
    assert state == "passed"
    assert path is not None and path.name == "manifest-repaired.json"
    assert "1/1" in detail
    assert "invalid not applicable" in detail
