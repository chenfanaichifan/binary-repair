"""Native Mach-O runtime evidence (macOS only)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services.binary_pipeline import repair_binary
from app.services.runtime import macho_native

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "arm64": ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64",
    "x86_64": ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64",
}

DARWIN = pytest.mark.skipif(
    not (sys.platform == "darwin" and macho_native.available()),
    reason="native Mach-O execution requires macOS with codesign",
)


@DARWIN
@pytest.mark.parametrize("arch", sorted(FIXTURES))
def test_native_run_verdict_pass_for_patched(arch):
    path = FIXTURES[arch]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    patched, report = repair_binary(data, verify=True)
    assert patched is not None
    assert report.verification["tier"] == "native_run"
    evidence = macho_native.run(patched, arch=arch, capacity=16)
    assert evidence.verdict == "pass", evidence.to_dict()
    lengths = {case.input_len for case in evidence.cases}
    assert {0, 1, 15, 16, 17, 64} <= lengths
    for case in evidence.cases:
        assert case.exit_code == 0
        assert case.output_len is not None and case.output_len <= min(case.input_len, 15)


@DARWIN
@pytest.mark.parametrize("arch", sorted(FIXTURES))
def test_original_binary_fails_the_contract(arch):
    path = FIXTURES[arch]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    evidence = macho_native.run(path.read_bytes(), arch=arch, capacity=16)
    assert evidence.verdict == "fail"


def test_native_runner_reports_unavailable_off_darwin(monkeypatch):
    monkeypatch.setattr(macho_native.sys, "platform", "linux")
    evidence = macho_native.run(b"", arch="arm64", capacity=16)
    assert evidence.verdict == "unavailable"
    assert evidence.tier == "unavailable"
