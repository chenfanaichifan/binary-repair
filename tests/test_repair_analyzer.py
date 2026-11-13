"""Sink analysis across ELF, PE and Mach-O (including 32-bit x86)."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.services.containers import (
    _decode_elf_plt_stub,
    detect_container,
    resolve_target,
)
from app.services.repair.analyzer import analyze

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "macho-arm64": ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64",
    "macho-x86_64": ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64",
    "pe-x64": ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe",
    "pe-arm64": ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe",
    "pe-x86": ROOT / "fixtures" / "pe" / "vuln-strcpy-x86.exe",
    "elf-arm64": ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf",
    "elf-x86": ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf",
    "pe-i386": ROOT / "fixtures" / "pe" / "i386-control.exe",
}


@pytest.mark.parametrize("name", ["macho-arm64", "macho-x86_64", "pe-x64",
                                  "pe-arm64", "pe-x86", "elf-arm64",
                                  "elf-x86"])
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
    assert sink.arch == analysis.container.arch
    assert sink.call_offset is not None and sink.call_size > 0


@pytest.mark.parametrize("name", ["macho-arm64", "macho-x86_64", "pe-x64",
                                  "pe-arm64", "pe-x86", "elf-arm64",
                                  "elf-x86", "pe-i386"])
def test_detection_matrix(name):
    path = FIXTURES[name]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    container = detect_container(path.read_bytes())
    assert container.format in {"elf", "pe", "macho"}
    assert container.arch in {"x86_64", "arm64", "i386"}


def test_i386_control_has_no_patchable_sink():
    """The stack-cookie control keeps passing cdecl args via ``mov [esp]``.

    The v1 i386 analyzer only models push-materialized cdecl arguments, so the
    control must stay a negative: no sink at all (and no ``no analyzer`` text).
    """
    path = FIXTURES["pe-i386"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    analysis = analyze(path.read_bytes())
    assert analysis.container.arch == "i386"
    assert analysis.patchable() == []
    assert not any("no analyzer" in item for item in analysis.limitations)
    assert any("no patchable copy sink" in item for item in analysis.limitations)
    assert any("materialised with mov to stack" in item
               for item in analysis.limitations)


def test_i386_elf32_symbol_suffix_resolution():
    """Static musl keeps ``c.string.strcpy`` in .symtab (no PLT for the call)."""
    path = FIXTURES["elf-x86"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert container.format == "elf" and container.arch == "i386"
    analysis = analyze(data)
    sink = analysis.patchable()[0]
    reach = sink.call_va + sink.call_size
    delta = struct.unpack_from("<i", data, sink.call_offset + 1)[0]
    target = reach + delta
    assert target in container.symbols
    name = container.symbols[target]
    assert name.endswith("strcpy"), name
    assert resolve_target(container, target) == name


def test_i386_pe32_thunk_and_iat_resolution():
    """MinGW resolves ``call _strcpy`` to a ``jmp [IAT]`` thunk (FF 25 abs32)."""
    path = FIXTURES["pe-x86"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert container.format == "pe" and container.arch == "i386"
    assert any(name.endswith("strcpy") for name in container.imports.values())
    analysis = analyze(data)
    sink = analysis.patchable()[0]
    delta = struct.unpack_from("<i", data, sink.call_offset + 1)[0]
    target = sink.call_va + sink.call_size + delta
    assert target in container.imports, hex(target)
    assert container.imports[target].endswith("strcpy")


def test_i386_elf_plt_stub_decodes_absolute_target():
    """i386 PLT entries are ``jmp *GOT`` with an absolute 32-bit GOT address."""
    got = 0x4BCA90
    stub = b"\xFF\x25" + struct.pack("<I", got) + b"\x00" * 10
    assert _decode_elf_plt_stub(stub, 0x402000, "i386") == got
    endbr32 = b"\xF3\x0F\x1E\xFB"
    ibt_stub = endbr32 + b"\xFF\x25" + struct.pack("<I", got) + b"\x00" * 6
    assert _decode_elf_plt_stub(ibt_stub, 0x402000, "i386") == got


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
