"""Unified dispatch across ELF, PE and Mach-O.

The pipeline is deliberately fail-closed: a format/arch outside the matrix must
return no candidate, never a corrupted file.
"""
from __future__ import annotations

from pathlib import Path

from app.services.binary_pipeline import (
    detect_format,
    repair_binary,
    scan_binary,
)

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"
MACHO = ROOT / "fixtures" / "macho" / "3D_Image_Toolkit"


def test_detect_elf_pe_macho():
    assert detect_format(ELF.read_bytes())[:2] == ("elf", "x86_64")
    assert detect_format(PE.read_bytes())[:2] == ("pe", "x86_64")
    assert detect_format(MACHO.read_bytes())[:2] == ("macho", "arm64")
    assert detect_format(b"not a binary")[0] == "unknown"


def test_scan_reports_three_formats():
    elf = scan_binary(ELF.read_bytes())
    assert elf["format"] == "elf"
    assert elf["arch"] == "x86_64"
    assert elf["repair_supported"] is True
    assert elf["findings"]

    pe = scan_binary(PE.read_bytes())
    assert pe["format"] == "pe"
    assert pe["arch"] == "x86_64"

    macho = scan_binary(MACHO.read_bytes())
    assert macho["format"] == "macho"
    assert macho["arch"] == "arm64"


def test_repair_elf_returns_verified_candidate():
    patched, report = repair_binary(ELF.read_bytes(), verify=True)
    assert patched is not None
    assert patched[:4] == b"\x7fELF"
    assert report.format == "elf"
    assert report.status == "patched"
    assert report.strategy == "strict-template"
    assert report.candidate_available is True
    assert report.verification["gate"]["success"] is True
    assert report.verification["static_reparse"] is True


def test_repair_unsupported_formats_fail_closed():
    for data in (PE.read_bytes(), MACHO.read_bytes()):
        patched, report = repair_binary(data, verify=False)
        assert patched is None
        assert report.supported is False
        assert report.candidate_available is False
        assert report.status in {"unsupported", "not_verified", "rejected"}
        assert report.error


def test_backend_mismatch_is_unsupported():
    patched, report = repair_binary(ELF.read_bytes(), backend="pe", verify=False)
    assert patched is None
    assert "does not match" in (report.error or "")


def test_unknown_input_is_unsupported():
    patched, report = repair_binary(b"MZ" + b"\x00" * 64, verify=False)
    assert patched is None
    assert report.format == "pe"
    assert report.error
