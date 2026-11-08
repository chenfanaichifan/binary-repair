from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from routeb.attempt_writer import _verify_contract
from routeb.contract_mode import load_contract, load_contract_mode

ROOT = Path(__file__).resolve().parents[1]
CWE121_CONTRACT = ROOT / "fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"


def _no_input_contract() -> dict:
    return {
        "schema_version": 3,
        "input_mode": "none",
        "target_entry": "demo",
        "target_signature": "void demo(void)",
        "valid_domain": "no program input",
        "valid_behavior": "exit 0 and print OK",
        "forbidden_behavior": "read or write through a pointer after its object is freed",
        "dest_capacity_bytes": 50,
        "capacity_includes_terminator": True,
        "authorized_edits": [],
        "allowed_calls": [],
        "environment_assumptions": [],
        "required_obligations": [
            "behaviour",
            "identity",
            "interface",
            "reproducibility",
            "structure",
            "symbolic",
        ],
    }


def _write_contract(tmp_path: Path, *, sentinel: str | None = None) -> Path:
    body = _no_input_contract()
    if sentinel is not None:
        body[sentinel] = "not applicable"
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _write_tests(tmp_path: Path) -> Path:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "valid.json").write_text(
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
    return tests


def _candidate(tmp_path: Path) -> Path:
    path = tmp_path / "candidate.sh"
    path.write_text("#!/bin/sh\nprintf 'OK\\n'\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _run_cli(tmp_path: Path, contract: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "routeb/run_manifest_repaired.py"),
            "--binary",
            str(_candidate(tmp_path)),
            "--tests",
            str(_write_tests(tmp_path)),
            "--out",
            str(tmp_path / "manifest-repaired.json"),
            "--contract",
            str(contract),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable script")
def test_no_input_cli_is_exactly_one_of_one(tmp_path: Path) -> None:
    contract = _write_contract(tmp_path)
    result = _run_cli(tmp_path, contract)

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary == {
        "input_mode": "none",
        "invalid": "not_applicable",
        "passed": 1,
        "total": 1,
        "repaired_pass": True,
        "binary_sha256": summary["binary_sha256"],
    }
    artifact = json.loads((tmp_path / "manifest-repaired.json").read_text())
    assert artifact["valid"] == "1/1"
    assert artifact["invalid"] == "not_applicable"
    assert artifact["total"] == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable script")
@pytest.mark.parametrize(
    "sentinel",
    [
        "invalid_input_response",
        "invalid_exit_code",
        "invalid_stdout",
        "invalid_stderr",
        "max_valid_input_bytes",
    ],
)
def test_no_input_cli_rejects_a_sentinel_field(
    tmp_path: Path, sentinel: str
) -> None:
    contract = _write_contract(tmp_path, sentinel=sentinel)
    result = _run_cli(tmp_path, contract)

    assert result.returncode == 2
    assert "unknown contract fields" in result.stderr
    assert not (tmp_path / "manifest-repaired.json").exists()


def test_shared_loader_uses_m5_schema_and_keeps_cwe121_hash(tmp_path: Path) -> None:
    loaded = load_contract(CWE121_CONTRACT)
    assert loaded.input_mode == "argv"
    assert loaded.sha256() == "24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37"

    contract = _write_contract(tmp_path)
    assert load_contract_mode(contract) == "none"


def test_attempt_writer_rejects_a_sentinel_contract(tmp_path: Path) -> None:
    contract = _write_contract(tmp_path, sentinel="invalid_input_response")

    with pytest.raises(ValueError, match="not a valid SecurityContract"):
        _verify_contract(contract)


def test_executor_rejects_a_sentinel_contract_before_work(tmp_path: Path) -> None:
    contract = _write_contract(tmp_path, sentinel="invalid_input_response")
    out = tmp_path / "bundle"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "routeb.executor",
            "--original",
            str(CWE121_CONTRACT.parent / "original.elf"),
            "--candidate",
            str(CWE121_CONTRACT.parent / "original.elf"),
            "--func",
            "demo",
            "--out-dir",
            str(out),
            "--contract",
            str(contract),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "unknown contract fields" in result.stderr
    assert not out.exists()
