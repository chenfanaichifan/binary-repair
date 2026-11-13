"""Sink analysis across ELF, PE and Mach-O."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.containers import detect_container
from app.services.repair.analyzer import analyze

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "macho-arm64": ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64",
    "macho-x86_64": ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64",
    "pe-x64": ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe",
    "pe-arm64": ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe",
    "elf-arm64": ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf",
    "pe-i386": ROOT / "fixtures" / "pe" / "i386-control.exe",
}


@pytest.mark.parametrize("name", ["macho-arm64", "macho-x86_64", "pe-x64",
                                  "pe-arm64", "elf-arm64"])
def test_stack_copy_sink_has_exact_capacity(name):
    path = FIXTURES[name]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    analysis = analyze(path.read_bytes())
    sinks = analysis.patchable()
    assert len(sinks) == 1, analysis.limitations
    sink = sinks[0]
    assert sink.kind == "unbounded_copy"
    assert sink.callee == "strcpy"
    assert sink.capacity == 16
    assert sink.dest_rel is not None
    assert sink.function_va > 0


@pytest.mark.parametrize("name", ["macho-arm64", "macho-x86_64", "pe-x64",
                                  "pe-arm64", "elf-arm64", "pe-i386"])
def test_detection_matrix(name):
    path = FIXTURES[name]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    container = detect_container(path.read_bytes())
    assert container.format in {"elf", "pe", "macho"}
    assert container.arch in {"x86_64", "arm64", "i386"}


def test_i386_control_has_no_analyzer():
    path = FIXTURES["pe-i386"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    analysis = analyze(path.read_bytes())
    assert analysis.patchable() == []
    assert any("no analyzer" in item for item in analysis.limitations)


def test_truncated_inputs_do_not_raise():
    from app.services.binary_pipeline import repair_binary

    for name, path in FIXTURES.items():
        if not path.is_file():
            continue
        data = path.read_bytes()
        for size in (0, 4, 16, 64, len(data) // 2, len(data) - 1):
            truncated = data[:size]
            analysis = analyze(truncated)
            assert isinstance(analysis.limitations, list)
            patched, report = repair_binary(truncated, verify=True)
            if patched is not None:
                assert report.verification["gate"]["success"] is True


def test_fixture_metadata_is_consistent():
    path = FIXTURES["pe-x64"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    container = detect_container(path.read_bytes())
    assert container.format == "pe"
    assert any("strcpy" in name for name in container.imports.values())
    assert container.executable_section() is not None
