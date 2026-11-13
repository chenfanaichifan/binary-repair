"""v5 advanced universal-input coverage.

Covers the paths that the first v5 acceptance round left to unit tests:

* fat Mach-O is recognised, sliced and analysis-only (no rewrite);
* big-endian / outside-matrix containers fail closed with no candidate;
* (added after the fixture work) dynamic ELF32 PLT, PE32 direct-IAT FF15 and
  i386 memcpy-immediate end-to-end repair.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.services.binary_pipeline import repair_any, scan_binary
from app.services.containers import detect_container

ROOT = Path(__file__).resolve().parents[1]
MACHO_ARM64 = ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64"
MACHO_X86_64 = ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64"


def _read(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def _synthetic_fat_macho(arm: bytes, x86: bytes) -> bytes:
    """Build a minimal universal Mach-O wrapper around two thin slices."""
    align = 0x1000
    offset0 = align
    offset1 = (offset0 + len(arm) + align - 1) // align * align
    total = (offset1 + len(x86) + align - 1) // align * align
    out = bytearray(total)
    struct.pack_into(">II", out, 0, 0xCAFEBABE, 2)
    # cputype / cpusubtype / offset / size / align
    struct.pack_into(">IIIII", out, 8, 0x0100000C, 0, offset0, len(arm), 12)  # arm64
    struct.pack_into(">IIIII", out, 28, 0x01000007, 3, offset1, len(x86), 12)  # x86_64
    out[offset0:offset0 + len(arm)] = arm
    out[offset1:offset1 + len(x86)] = x86
    return bytes(out)


def _synthetic_big_endian_elf32() -> bytes:
    ident = bytearray(16)
    ident[0:4] = b"\x7fELF"
    ident[4] = 1      # ELFCLASS32
    ident[5] = 2      # ELFDATA2MSB (big endian)
    ident[6] = 1      # EV_CURRENT
    header = struct.pack(
        ">16sHHIIIIIHHHHHH",
        bytes(ident), 2, 3, 1, 0, 0, 0, 0, 52, 32, 0, 40, 0, 0,
    )
    return header + b"\x00" * 64


def test_fat_macho_is_analysis_only_with_slice_metadata(
    tmp_path: Path,
) -> None:
    arm = _read(MACHO_ARM64)
    x86 = _read(MACHO_X86_64)
    data = _synthetic_fat_macho(arm, x86)
    container = detect_container(data)
    assert container.format == "macho-fat"
    assert container.slices == 2
    assert container.arch == "arm64"

    outcome = repair_any(data)
    assert outcome.candidate is None
    assert outcome.download_allowed is False
    report = outcome.report
    assert report.disposition == "unsupported"
    assert report.status == "unsupported"
    assert report.format == "macho-fat"
    assert len(report.slices) == 2
    by_index = {row["index"]: row for row in report.slices}
    assert by_index[0]["arch"] == "arm64"
    assert by_index[1]["arch"] == "x86_64"
    # The slices are individually in the matrix, but a fat image is never
    # rewritten in v5; that must be explicit, not a silent success.
    assert all(row["supported"] is True for row in report.slices)
    assert all(row["container_rewrite"] is False for row in report.slices)
    assert "macho-fat" in (report.error or "")

    scan = scan_binary(data)
    assert scan["format"] == "macho-fat"
    assert scan["supported"] is True
    assert scan["repair_supported"] is False
    assert len(scan["slices"]) == 2
    assert scan["matrix"]["repairable"] is False


def test_big_endian_elf_fails_closed_without_candidate() -> None:
    data = _synthetic_big_endian_elf32()
    container = detect_container(data)
    assert container.format == "elf"
    assert container.endian == "big"
    assert container.bits == 32

    outcome = repair_any(data)
    assert outcome.candidate is None
    assert outcome.report.disposition == "unsupported"
    assert outcome.report.matrix["cell"] is None
    assert "big-endian" in (outcome.report.error or "")

    scan = scan_binary(data)
    assert scan["supported"] is True
    assert scan["repair_supported"] is False
    assert scan["matrix"]["repairable"] is False


# ---------------------------------------------------------------------------
# Dynamic ELF32 / PE32 direct-IAT / memcpy immediate fixtures
# ---------------------------------------------------------------------------

ELF32_DYN = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86-dyn.elf"
PE32_IAT = ROOT / "fixtures" / "pe" / "vuln-strcpy-x86-iat.exe"
ELF32_MEMCPY = ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"


def test_dynamic_elf32_plt_repair_is_verified() -> None:
    data = _read(ELF32_DYN)
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == ("elf", "i386", 32)
    # The fixture must really be dynamically linked (PT_INTERP / PLT).
    assert any(s.name == ".plt" for s in container.sections)
    names = set()
    for reloc in container.imports.values():
        names.add(reloc.rsplit("@", 1)[0])
    assert "strcpy" in names

    scan = scan_binary(data)
    assert scan["repair_supported"] is True
    finding = scan["findings"][0]
    assert finding["kind"] == "unbounded_copy"
    assert finding["callee"] == "strcpy"
    assert finding["capacity"] == 16

    outcome = repair_any(data)
    assert outcome.verified is True
    assert outcome.report.disposition == "verified_patch"
    assert outcome.report.strategy == "guard"
    assert outcome.report.actions[0]["kind"] == "guard"
    assert outcome.report.verification["tier"] == "emulated_run"
    assert outcome.report.verification["engine"] == "unicorn-i386"
    assert outcome.report.verification["gate"]["success"] is True
    assert outcome.candidate is not None
    assert detect_container(outcome.candidate).format == "elf"


def test_pe32_direct_iat_call_is_redirected_and_verified() -> None:
    data = _read(PE32_IAT)
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == ("pe", "i386", 32)

    from app.services.repair.analyzer import analyze

    sink = analyze(data).patchable()[0]
    # The fixture deliberately uses `call dword ptr [__imp__strcpy]` (FF15)
    # rather than the E8-to-thunk form of the first PE32 fixture.
    assert sink.call_size == 6
    assert data[sink.call_offset] == 0xFF  # type: ignore[index]

    outcome = repair_any(data)
    assert outcome.verified is True
    assert outcome.report.disposition == "verified_patch"
    assert outcome.report.actions[0]["kind"] == "guard"
    # Redirect writes E8 + rel32 + NOP over the 6-byte FF15 instruction.
    patched = outcome.candidate
    assert patched is not None
    assert patched[sink.call_offset] == 0xE8  # type: ignore[index]
    assert patched[sink.call_offset + 5] == 0x90  # type: ignore[index]
    assert detect_container(patched).format == "pe"


def test_i386_memcpy_immediate_repair_is_verified() -> None:
    data = _read(ELF32_MEMCPY)
    scan = scan_binary(data)
    assert scan["repair_supported"] is True
    finding = scan["findings"][0]
    assert finding["kind"] == "memcpy_length"
    assert finding["callee"] == "memcpy"
    assert finding["capacity"] == 16
    assert finding["before"] == 64

    outcome = repair_any(data)
    assert outcome.verified is True
    report = outcome.report
    assert report.disposition == "verified_patch"
    assert report.strategy == "immediate"
    assert report.actions[0]["kind"] == "immediate"
    assert report.actions[0]["before"] == 64
    assert report.actions[0]["after"] == 16
    assert report.verification["tier"] == "emulated_run"
    assert report.verification["gate"]["success"] is True
    assert report.runtime.get("verdict") == "pass"

    # The original immediate overflows: 64-byte copy into a 16-byte buffer.
    from app.services.runtime.emulated import emulate

    baseline = emulate(
        data, detect_container(data),
        function_va=finding["address"],
        dest_rel=-24,
        capacity=16,
        abi="cdecl_x86",
        copy_kind="memcpy_length",
        callee="memcpy",
        lengths=[0, 1, 15, 16, 17, 64],
    )
    assert baseline.verdict == "fail"
