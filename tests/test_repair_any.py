"""repair_any dispositions: verified, static-only, analysis-only, invalid."""
from __future__ import annotations

from pathlib import Path

import pytest

import app.services.binary_pipeline as pipeline
from app.services.binary_pipeline import repair_any, repair_binary, scan_binary

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE_VULN = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
PE_NO_SINK = ROOT / "fixtures" / "pe" / "cli-64.exe"
MACHO_NO_SINK = ROOT / "fixtures" / "macho" / "3D_Image_Toolkit"


def _read(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def test_verified_repair_reports_v4_disposition():
    data = _read(PE_VULN)
    outcome = repair_any(data)
    assert outcome.candidate is not None
    assert outcome.download_allowed is True
    assert outcome.verified is True
    report = outcome.report
    assert report.schema_version == 4
    assert report.disposition == "verified_patch"
    assert report.delivery == {
        "download_allowed": True, "verified": True, "tier": "emulated_run",
    }
    assert report.matrix["cell"] == "pe/x86_64/64/little"
    assert report.coverage["sink_classes"]
    assert report.status == "patched"
    assert report.verification["gate"]["success"] is True


def test_scan_reports_v4_matrix_and_disposition_inputs():
    payload = scan_binary(_read(PE_VULN))
    assert payload["schema_version"] == 4
    assert payload["matrix"]["repairable"] is True
    assert payload["repair_supported"] is True
    assert payload["findings"][0]["strategy"] == "guard"


def test_analysis_only_for_in_matrix_binary_without_sink():
    for path, name in ((PE_NO_SINK, "pe"), (MACHO_NO_SINK, "macho")):
        data = _read(path)
        outcome = repair_any(data)
        assert outcome.candidate is None
        assert outcome.download_allowed is False
        report = outcome.report
        assert report.disposition == "analysis_only"
        assert report.status == "unsupported"
        assert report.matrix["repairable"] is True
        assert name in report.format


def test_invalid_inputs_fail_closed():
    for data in (b"", b"not a binary", b"MZ" + b"\x00" * 128):
        outcome = repair_any(data)
        assert outcome.candidate is None
        assert outcome.report.disposition == "invalid"
        assert outcome.report.error


def test_oversized_input_is_invalid():
    outcome = repair_any(b"\x7fELF" + b"\x00" * (21 * 1024 * 1024))
    assert outcome.candidate is None
    assert outcome.report.disposition == "invalid"
    assert "exceeds" in (outcome.report.error or "")


def test_backend_mismatch_is_unsupported():
    outcome = repair_any(_read(PE_VULN), backend="elf")
    assert outcome.candidate is None
    assert outcome.report.disposition == "unsupported"
    assert "does not match" in (outcome.report.error or "")


def test_runtime_unavailable_is_not_verified_by_default(monkeypatch):
    monkeypatch.setattr(pipeline, "_select_runtime", lambda *args, **kwargs: None)
    data = _read(PE_VULN)
    outcome = repair_any(data)
    assert outcome.candidate is None
    assert outcome.download_allowed is False
    assert outcome.report.disposition == "not_verified"
    assert outcome.report.verification["gate"]["outcome"] == "inconclusive"
    assert "allow_static_only" in (outcome.report.error or "")


def test_static_only_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(pipeline, "_select_runtime", lambda *args, **kwargs: None)
    data = _read(PE_VULN)
    outcome = repair_any(data, allow_static_only=True)
    assert outcome.candidate is not None
    assert outcome.download_allowed is True
    assert outcome.verified is False
    report = outcome.report
    assert report.disposition == "static_only_patch"
    assert report.delivery == {
        "download_allowed": True, "verified": False, "tier": "static_only",
    }
    assert report.warnings
    assert report.verification["gate"]["success"] is False


def test_legacy_wrapper_verify_false_returns_static_only_candidate():
    data = _read(PE_VULN)
    patched, report = repair_binary(data, verify=False)
    assert patched is not None
    assert report.disposition == "static_only_patch"
    assert report.status == "not_verified"


def test_verified_gate_never_returns_candidate_for_wrong_backend():
    data = _read(ELF)
    patched, report = repair_binary(data, verify=True)
    assert patched is not None
    assert report.disposition == "verified_patch"
    assert report.verification["gate"]["success"] is True
