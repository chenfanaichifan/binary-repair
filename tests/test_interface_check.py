from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.interface import (
    CHECK_NAMES,
    InterfaceCheckError,
    check_interface,
    validate_interface_report,
)

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf"
CANDIDATE = ROOT / "artifacts/cwe416-124-v4-rerun-2026-11-06/candidate.elf"
TARGET = "CWE416_Use_After_Free__malloc_free_char_01_bad"


def test_cwe416_124_passes_all_five_interface_checks() -> None:
    report = check_interface(ORIGINAL, CANDIDATE, TARGET)
    assert report["state"] == "passed"
    assert report["pass"] is True
    assert report["score"] == {"passed": 5, "total": 5}
    assert set(report["checks"]) == set(CHECK_NAMES)
    assert all(report["checks"].values())
    validated = validate_interface_report(
        report,
        candidate_sha256=report["candidate_sha256"],
        original_sha256=report["original_sha256"],
        target_entry=TARGET,
    )
    assert validated["score"]["passed"] == 5


def test_missing_target_symbol_is_not_run() -> None:
    report = check_interface(ORIGINAL, CANDIDATE, "no_such_symbol")
    assert report["state"] == "not_run"
    assert report["pass"] is False
    assert report["checks"]["target_entry_symbol_unchanged"] is False
    assert report["score"]["passed"] < 5


def test_changed_entry_is_not_run(tmp_path: Path) -> None:
    data = bytearray(CANDIDATE.read_bytes())
    # ELF64 e_entry is the 8-byte field at offset 24.
    data[24] ^= 0x01
    changed = tmp_path / "changed.elf"
    changed.write_bytes(bytes(data))
    report = check_interface(ORIGINAL, changed, TARGET)
    assert report["state"] == "not_run"
    assert report["checks"]["entry_unchanged"] is False


def test_measured_observation_pass_true_is_not_a_verdict() -> None:
    with pytest.raises(InterfaceCheckError):
        validate_interface_report(
            {
                "gate": "V2",
                "kind": "interface",
                "pass": True,
                "checks": {"target_symbol_present": True},
            }
        )
