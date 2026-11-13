"""End-to-end v4 pipeline matrix: six positives and the fail-closed controls."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.binary_pipeline import detect_format, repair_binary, scan_binary

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = {
    "macho-arm64": (ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64", "macho", "arm64", "native_run"),
    "macho-x86_64": (ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64", "macho", "x86_64", "native_run"),
    "pe-x64": (ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe", "pe", "x86_64", "emulated_run"),
    "pe-arm64": (ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe", "pe", "arm64", "emulated_run"),
    "elf-arm64": (ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf", "elf", "arm64", "emulated_run"),
}


def _require(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


@pytest.mark.parametrize("name", sorted(POSITIVE))
def test_positive_matrix_returns_verified_candidate(name):
    path, fmt, arch, tier = POSITIVE[name]
    data = _require(path)
    assert detect_format(data)[:2] == (fmt, arch)
    patched, report = repair_binary(data, verify=True)
    assert patched is not None, report.to_dict()
    assert report.format == fmt and report.arch == arch
    assert report.status == "patched"
    assert report.supported is True
    assert report.candidate_available is True
    assert report.strategy == "guard"
    assert report.capacity == 16
    assert report.actions and report.actions[0]["kind"] == "guard"
    gate = report.verification["gate"]
    assert gate["success"] is True, report.verification
    assert gate["outcome"] == "success_within_scope"
    assert report.verification["tier"] == tier
    assert report.verification["static_reparse"] is True
    assert patched != data
    assert detect_format(patched)[:2] == (fmt, arch)


@pytest.mark.parametrize("name", sorted(POSITIVE))
def test_positive_scan_reports_patchable_sink(name):
    path, fmt, arch, _tier = POSITIVE[name]
    payload = scan_binary(_require(path))
    assert payload["format"] == fmt and payload["arch"] == arch
    assert payload["repair_supported"] is True
    assert payload["findings"]
    assert payload["findings"][0]["capacity"] == 16
    assert payload["findings"][0]["patchable"] is True


def test_i386_pe_fails_closed():
    path = ROOT / "fixtures" / "pe" / "i386-control.exe"
    patched, report = repair_binary(_require(path), verify=True)
    assert patched is None
    assert report.status == "unsupported"
    assert "no repair backend" in (report.error or "")


def test_unknown_and_malformed_fail_closed():
    for data in (b"", b"not a binary", b"MZ" + b"\x00" * 128,
                 b"\x7fELF" + b"\x00" * 60):
        patched, report = repair_binary(data, verify=True)
        assert patched is None
        assert report.error or report.limitations


def test_backend_mismatch_is_unsupported():
    path = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
    patched, report = repair_binary(_require(path), backend="elf", verify=False)
    assert patched is None
    assert "does not match" in (report.error or "")


def test_oversized_input_is_rejected():
    patched, report = repair_binary(b"\x7fELF" + b"\x00" * (21 * 1024 * 1024),
                                    verify=False)
    assert patched is None
    assert "exceeds" in (report.error or "")


def test_old_fixtures_remain_negative_controls():
    for path in (ROOT / "fixtures" / "pe" / "cli-64.exe",
                 ROOT / "fixtures" / "macho" / "3D_Image_Toolkit"):
        if not path.is_file():
            continue
        patched, report = repair_binary(path.read_bytes(), verify=True)
        assert patched is None
        assert report.candidate_available is False
        assert report.error
