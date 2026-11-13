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
    "pe-x86-iat": ROOT / "fixtures" / "pe" / "vuln-strcpy-x86-iat.exe",
    "elf-arm64": ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf",
    "elf-x86": ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf",
    "elf-x86-dyn": ROOT / "fixtures" / "elf" / "vuln-strcpy-x86-dyn.elf",
    "elf-x86-memcpy": ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf",
    "pe-i386": ROOT / "fixtures" / "pe" / "i386-control.exe",
}


@pytest.mark.parametrize("name", ["macho-arm64", "macho-x86_64", "pe-x64",
                                  "pe-arm64", "pe-x86", "pe-x86-iat",
                                  "elf-arm64", "elf-x86", "elf-x86-dyn"])
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
                                  "pe-arm64", "pe-x86", "pe-x86-iat",
                                  "elf-arm64", "elf-x86", "elf-x86-dyn",
                                  "elf-x86-memcpy", "pe-i386"])
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


def test_i386_dynamic_elf32_uses_plt_and_interp():
    """Dynamic ELF32: E8 -> .plt stub, resolved through rel.plt / .plt."""
    import io

    from elftools.elf.elffile import ELFFile

    path = FIXTURES["elf-x86-dyn"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == ("elf", "i386", 32)
    assert container.limitations == []
    elf = ELFFile(io.BytesIO(data))
    assert any(seg["p_type"] == "PT_INTERP" for seg in elf.iter_segments())
    interp = elf.get_section_by_name(".interp")
    assert interp is not None and b"ld-linux" in interp.data()
    plt = elf.get_section_by_name(".plt")
    assert plt is not None and int(plt["sh_size"]) > 0
    assert any(name.endswith("strcpy") for name in container.imports.values())

    analysis = analyze(data)
    sinks = analysis.patchable()
    assert len(sinks) == 1, analysis.limitations
    sink = sinks[0]
    assert sink.kind == "unbounded_copy"
    assert sink.callee == "strcpy"
    assert sink.capacity == 16
    assert sink.call_size == 5
    delta = struct.unpack_from("<i", data, sink.call_offset + 1)[0]
    target = sink.call_va + sink.call_size + delta
    assert target in container.imports, hex(target)
    assert container.imports[target].endswith("strcpy")  # E8 -> .plt stub


def test_i386_pe32_direct_iat_call_is_six_bytes():
    """PE32 ``call *__imp__strcpy`` is a 6-byte FF 15 <abs32 IAT slot>."""
    path = FIXTURES["pe-x86-iat"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == ("pe", "i386", 32)
    analysis = analyze(data)
    sinks = analysis.patchable()
    assert len(sinks) == 1, analysis.limitations
    sink = sinks[0]
    assert sink.kind == "unbounded_copy"
    assert sink.callee == "strcpy"
    assert sink.capacity == 16
    assert sink.call_size == 6
    raw = data[sink.call_offset:sink.call_offset + 6]
    assert raw[:2] == b"\xFF\x15"
    slot = struct.unpack_from("<I", raw, 2)[0]
    assert container.imports[slot].endswith("strcpy")


def test_i386_memcpy_immediate_sink_is_patchable():
    """Static i386 memcpy(dst, src, 64) is a single imm32-length sink."""
    path = FIXTURES["elf-x86-memcpy"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    analysis = analyze(data)
    assert (analysis.container.format, analysis.container.arch) == ("elf", "i386")
    sinks = analysis.patchable()
    assert len(sinks) == 1, analysis.limitations
    sink = sinks[0]
    assert sink.kind == "memcpy_length"
    assert sink.callee == "memcpy"
    assert sink.capacity == 16
    assert sink.length == 64
    assert sink.length_offset is not None
    assert data[sink.length_offset:sink.length_offset + 4] == struct.pack("<I", 64)
    assert sink.call_size == 5
    assert sink.arch == "i386"


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
