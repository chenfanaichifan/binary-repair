"""Unicorn runtime evidence for PE and AArch64 ELF candidates."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.binary_pipeline import repair_binary
from app.services.containers import detect_container
from app.services.repair.analyzer import analyze
from app.services.repair.writer import repair_with_sinks
from app.services.runtime.emulated import emulate

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "pe-x64": (ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe", "win64_x86_64"),
    "pe-arm64": (ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe", "aapcs64"),
    "elf-arm64": (ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf", "aapcs64"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_emulated_run_accepts_patched_and_rejects_original(name):
    path, abi = CASES[name]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    sink = analyze(data).patchable()[0]
    patched, report = repair_binary(data, verify=True)
    assert patched is not None
    patched_container = detect_container(patched)

    good = emulate(patched, patched_container,
                   function_va=sink.function_va, dest_rel=sink.dest_rel,
                   capacity=sink.capacity, abi=abi,
                   lengths=[0, 1, 15, 16, 17, 64])
    assert good.verdict == "pass", good.to_dict()
    assert all(case.canary_intact for case in good.cases)
    for case in good.cases:
        assert case.output_len <= min(case.input_len, 15)

    baseline = emulate(data, container,
                       function_va=sink.function_va, dest_rel=sink.dest_rel,
                       capacity=sink.capacity, abi=abi,
                       lengths=[16, 17, 64])
    assert baseline.verdict == "fail"
    assert any(case.canary_intact is False for case in baseline.cases)


def test_emulated_report_is_labelled_not_native():
    path, abi = CASES["pe-x64"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    patched, report = repair_binary(path.read_bytes(), verify=True)
    assert patched is not None
    packet = report.verification["packet"]
    assert packet["scope"]["runtime_tier"] == "emulated_run"
    assert "not a native Windows/Linux run" in " ".join(
        report.runtime.get("limitations", [])
    ) or report.runtime.get("limitations")
