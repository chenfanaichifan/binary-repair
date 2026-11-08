from __future__ import annotations

import json
from pathlib import Path

import pytest

from routeb import run_manifest_compare as cmp


def _tests(tmp_path: Path, *, valid=True, invalid=True) -> Path:
    root = tmp_path / "tests"; root.mkdir()
    (root / "valid.json").write_text(json.dumps({"tests": [
        {"id": "v", "kind": "valid", "argv": ["./x", "A"],
         "expected": {"return_code": 0, "stdout": "A\n", "stderr": ""}}
    ] if valid else []}))
    (root / "invalid.json").write_text(json.dumps({"tests": [
        {"id": "i", "kind": "invalid", "argv": ["./x", "B"],
         "expected": {"return_code": 1, "stdout": "", "stderr": "ERROR\n"}}
    ] if invalid else []}))
    return root


def _binary(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name; path.write_bytes(b"\x7fELF " + name.encode()); return path


def test_compare_rejects_empty_cases(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no frozen cases"):
        cmp.compare(_binary(tmp_path, "a"), _binary(tmp_path, "b"),
                    _tests(tmp_path, valid=False, invalid=False))


def test_compare_timeout_is_not_gate4_pass(tmp_path: Path, monkeypatch) -> None:
    original = _binary(tmp_path, "original")
    patched = _binary(tmp_path, "patched")
    tests = _tests(tmp_path)

    def fake_run(elf, arg):
        if elf == original:
            return {"returncode": 0, "stdout_hex": "410a", "stderr_hex": ""} if arg == "A" else {"returncode": 0, "stdout_hex": "", "stderr_hex": ""}
        return {"timeout": True, "returncode": None, "stdout_hex": "", "stderr_hex": ""}
    monkeypatch.setattr(cmp, "run", fake_run)
    result = cmp.compare(original, patched, tests)
    assert result["gate4_pass"] is False


def test_compare_requires_original_to_be_unrepaired(tmp_path: Path, monkeypatch) -> None:
    original = _binary(tmp_path, "original")
    patched = _binary(tmp_path, "patched")
    tests = _tests(tmp_path)

    def fake_run(elf, arg):
        if arg == "A":
            return {"returncode": 0, "stdout_hex": "410a", "stderr_hex": ""}
        # Original already matches repaired invalid expectation -> not a valid round trip.
        return {"returncode": 1, "stdout_hex": "", "stderr_hex": "4552524f520a"}
    monkeypatch.setattr(cmp, "run", fake_run)
    result = cmp.compare(original, patched, tests)
    assert result["original_ok"] is False
    assert result["gate4_pass"] is False


def test_no_input_compare_is_one_of_one(tmp_path: Path, monkeypatch) -> None:
    tests = tmp_path / "tests"; tests.mkdir()
    (tests / "valid.json").write_text(json.dumps({"tests": [
        {"id": "v", "kind": "valid", "argv": ["./x"],
         "expected": {"return_code": 0, "stdout": "OK\n", "stderr": ""}}
    ]}))
    original = _binary(tmp_path, "original")
    patched = _binary(tmp_path, "patched")
    monkeypatch.setattr(cmp, "run", lambda *a, **k: {
        "returncode": 0, "stdout_hex": "4f4b0a", "stderr_hex": ""
    })

    result = cmp.compare(original, patched, tests, input_mode="none")
    assert result["input_mode"] == "none"
    assert result["invalid"] == "not_applicable"
    assert result["same_count"] == result["total"] == 1
    assert result["gate4_pass"] is True


def test_no_input_compare_rejects_an_invalid_manifest(tmp_path: Path) -> None:
    tests = tmp_path / "tests"; tests.mkdir()
    (tests / "valid.json").write_text(json.dumps({"tests": [
        {"id": "v", "kind": "valid", "argv": ["./x"],
         "expected": {"return_code": 0, "stdout": "", "stderr": ""}}
    ]}))
    (tests / "invalid.json").write_text(json.dumps({"tests": []}))
    with pytest.raises(ValueError, match="must not ship"):
        cmp.compare(_binary(tmp_path, "a"), _binary(tmp_path, "b"), tests, input_mode="none")
