"""i386 (32-bit x86) writer: cdecl guards, immediate rewrite, fail-closed."""
from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from elftools.elf.elffile import ELFFile
from unicorn import UC_ARCH_X86, UC_MODE_32, UC_PROT_ALL, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EDI,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

from app.services.code_cave import add_rx_segment
from app.services.containers import detect_container
from app.services.repair.analyzer import Sink, analyze
from app.services.repair.guards import abi_for, build_guard
from app.services.repair.writer import _patch_immediate, repair_with_sinks

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf"
ELF_DYN = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86-dyn.elf"
ELF_MEMCPY = ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"
PE = ROOT / "fixtures" / "pe" / "vuln-strcpy-x86.exe"
PE_IAT = ROOT / "fixtures" / "pe" / "vuln-strcpy-x86-iat.exe"

CODE = 0x1000
STACK = 0x7000
DST = 0x2000
SRC = 0x3000
SENTINEL = 0x9000


def _require(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def _sink_for(path: Path) -> tuple[bytes, object, Sink]:
    data = _require(path)
    analysis = analyze(data)
    sinks = analysis.patchable()
    assert len(sinks) == 1, analysis.limitations
    return data, analysis.container, sinks[0]


def _emulate_cdecl(op: str, capacity: int, src: bytes, dst: bytes) -> tuple[bytes, int]:
    code = build_guard("cdecl_x86", op, capacity)
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    for base, size in ((CODE, 0x1000), (STACK, 0x2000), (DST, 0x1000),
                       (SRC, 0x2000), (SENTINEL, 0x1000)):
        uc.mem_map(base, size, UC_PROT_ALL)
    uc.mem_write(CODE, code)
    sp = STACK + 0x1800
    # [esp] = fake return address, [esp+4] = dst, [esp+8] = src (cdecl).
    uc.mem_write(sp, struct.pack("<III", SENTINEL, DST, SRC))
    uc.mem_write(DST, dst)
    uc.mem_write(SRC, src)
    uc.reg_write(UC_X86_REG_ESP, sp)
    uc.reg_write(UC_X86_REG_ESI, 0xDEAD0000)
    uc.reg_write(UC_X86_REG_EDI, 0xBEEF0000)
    uc.emu_start(CODE, SENTINEL, count=10_000)
    out = bytes(uc.mem_read(DST, capacity + 8))
    assert int(uc.reg_read(UC_X86_REG_ESI)) == 0xDEAD0000
    assert int(uc.reg_read(UC_X86_REG_EDI)) == 0xBEEF0000
    return out, int(uc.reg_read(UC_X86_REG_EAX))


def test_i386_abi_and_guard_encoding():
    assert abi_for("elf", "i386") == "cdecl_x86"
    assert abi_for("pe", "i386") == "cdecl_x86"
    # Existing 64-bit dispatch is untouched.
    assert abi_for("elf", "x86_64") == "sysv_x86_64"
    assert abi_for("pe", "x86_64") == "win64_x86_64"
    for op in ("strcpy", "strcat"):
        code = build_guard("cdecl_x86", op, 16)
        decoded = b"".join(bytes(ins.bytes) for ins in
                           Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, 0))
        assert decoded == code  # every byte decodes in 32-bit mode
        assert code[-1] == 0xC3
    with pytest.raises(ValueError):
        build_guard("cdecl_x86", "strcpy", 0)
    with pytest.raises(ValueError):
        build_guard("cdecl_x86", "strcpy", 0x80000000)
    with pytest.raises(ValueError):
        build_guard("cdecl_x86", "memset", 16)


def test_i386_cdecl_strcpy_guard_bounds_and_returns():
    out, rc = _emulate_cdecl("strcpy", 16, b"A" * 40, b"")
    assert out[:15] == b"A" * 15
    assert out[15] == 0
    assert out[16:24] == b"\x00" * 8  # nothing written past capacity-1
    assert rc == 1

    out, rc = _emulate_cdecl("strcpy", 16, b"hello", b"")
    assert out[:6] == b"hello\x00"
    assert rc == 0


def test_i386_cdecl_strcat_guard_appends_within_capacity():
    out, rc = _emulate_cdecl("strcat", 16, b"BBBB", b"AAAA\x00")
    assert out[:9] == b"AAAABBBB\x00"
    assert rc == 0

    out, rc = _emulate_cdecl("strcat", 16, b"C" * 40, b"AAAA\x00")
    assert out[15] == 0
    assert out[16:24] == b"\x00" * 8
    assert rc == 1


def test_i386_immediate_patch_writes_little_endian_imm32():
    data = _require(ELF)
    container = detect_container(data)
    section = container.executable_section()
    assert section is not None
    loc = section.offset + 8
    sink = Sink(
        kind="memcpy_length",
        arch="i386",
        capacity=16,
        length=64,
        length_offset=loc,
        call_offset=section.offset,
        call_va=section.va,
        call_size=5,
        patchable=True,
    )
    patched = _patch_immediate(data, sink, 16)
    assert patched is not None
    assert patched[loc:loc + 4] == struct.pack("<I", 16)
    assert patched[:loc] == data[:loc]
    assert patched[loc + 4:] == data[loc + 4:]

    result = repair_with_sinks(data, container, [sink])
    assert result.ok, result.limitations
    assert result.actions[0]["kind"] == "immediate"
    assert result.actions[0]["after"] == 16
    check = detect_container(result.patched)
    assert (check.format, check.arch, check.bits) == ("elf", "i386", 32)


def test_i386_immediate_patch_fails_closed_out_of_range():
    data = _require(ELF)
    container = detect_container(data)
    sink = Sink(
        kind="memcpy_length",
        arch="i386",
        capacity=16,
        length=64,
        length_offset=len(data) - 2,
        call_offset=0,
        call_va=0,
        call_size=5,
        patchable=True,
    )
    assert _patch_immediate(data, sink, 16) is None
    result = repair_with_sinks(data, container, [sink])
    assert result.patched is None
    assert any("immediate patch failed" in item for item in result.limitations)


def test_i386_elf32_guard_injection_redirects_and_reparses():
    data, container, sink = _sink_for(ELF)
    result = repair_with_sinks(data, container, [sink])
    assert result.ok, result.limitations
    assert result.injected_va is not None
    assert result.actions and result.actions[0]["kind"] == "guard"
    assert result.actions[0]["method"] == "new-pt-load"
    patched = result.patched
    assert patched is not None and patched != data

    check = detect_container(patched)
    assert (check.format, check.arch, check.bits) == ("elf", "i386", 32)
    assert check.limitations == []

    off = sink.call_offset
    assert patched[off] == 0xE8
    delta = struct.unpack_from("<i", patched, off + 1)[0]
    assert sink.call_va + 5 + delta == result.injected_va

    elf = ELFFile(io.BytesIO(patched))
    loads = [seg for seg in elf.iter_segments() if seg["p_type"] == "PT_LOAD"]
    cave = [seg for seg in loads if int(seg["p_vaddr"]) == result.injected_va]
    assert cave, [hex(int(seg["p_vaddr"])) for seg in loads]
    seg = cave[0]
    assert int(seg["p_flags"]) & 0x5 == 0x5  # R-X
    raw = patched[int(seg["p_offset"]):int(seg["p_offset"]) + int(seg["p_filesz"])]
    guard = build_guard(abi_for("elf", "i386"), sink.callee, int(sink.capacity))
    assert raw[:len(guard)] == guard
    original_phnum = int(ELFFile(io.BytesIO(data)).header["e_phnum"])
    assert int(elf.header["e_phnum"]) == original_phnum + 1


def test_i386_pe32_guard_injection_redirects_and_reparses():
    import lief

    data, container, sink = _sink_for(PE)
    result = repair_with_sinks(data, container, [sink])
    assert result.ok, result.limitations
    assert result.injected_va is not None
    assert result.actions and result.actions[0]["kind"] == "guard"
    assert result.actions[0]["method"] == "pe-section"
    patched = result.patched
    assert patched is not None and patched != data

    check = detect_container(patched)
    assert (check.format, check.arch, check.bits) == ("pe", "i386", 32)
    assert check.limitations == []

    off = sink.call_offset
    assert patched[off] == 0xE8
    delta = struct.unpack_from("<i", patched, off + 1)[0]
    assert sink.call_va + 5 + delta == result.injected_va

    pe = lief.PE.parse(list(patched))
    section = pe.get_section(".brfix")
    assert section is not None
    base = int(pe.optional_header.imagebase)
    assert base + int(section.virtual_address) == result.injected_va
    guard = build_guard(abi_for("pe", "i386"), sink.callee, int(sink.capacity))
    assert bytes(section.content)[:len(guard)] == guard
    # The writer always flags PE writeback as signature-invalidating.
    assert result.signature_invalidated is True


def test_i386_ff15_call_site_is_redirected_with_a_nop_pad():
    """A PE32 ``call [IAT]`` (FF 15 abs32) becomes E8 rel32 + NOP."""
    data = _require(PE)
    container = detect_container(data)
    section = next(s for s in container.sections
                   if s.name == ".text" and s.executable)
    raw = data[section.offset:section.offset + section.size]
    ff15 = next(
        ins for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(raw, section.va)
        if ins.mnemonic == "call" and bytes(ins.bytes)[:2] == b"\xFF\x15"
    )
    off = section.offset + (ff15.address - section.va)
    sink = Sink(
        kind="unbounded_copy",
        arch="i386",
        function_va=ff15.address,
        call_va=ff15.address,
        callee="strcpy",
        capacity=16,
        dest_rel=-20,
        call_offset=off,
        call_size=6,
        patchable=True,
    )
    result = repair_with_sinks(data, container, [sink])
    assert result.ok, result.limitations
    patched = result.patched
    assert patched[off] == 0xE8
    assert patched[off + 5] == 0x90
    delta = struct.unpack_from("<i", patched, off + 1)[0]
    assert ff15.address + 5 + delta == result.injected_va
    assert result.injected_va is not None


def test_i386_guard_redirect_fails_closed_on_bad_call_site():
    data = _require(ELF)
    container = detect_container(data)
    section = container.executable_section()
    # Bytes at the section start are "push ebp", neither E8 nor FF15.
    sink = Sink(
        kind="unbounded_copy",
        arch="i386",
        function_va=section.va,
        call_va=section.va,
        callee="strcpy",
        capacity=16,
        dest_rel=-20,
        call_offset=section.offset,
        call_size=5,
        patchable=True,
    )
    result = repair_with_sinks(data, container, [sink])
    assert result.patched is None
    assert any("call redirection failed" in item for item in result.limitations)


@pytest.mark.parametrize("path", [ELF, PE], ids=["elf32", "pe32"])
def test_i386_injection_failure_fails_closed(path):
    data, container, sink = _sink_for(path)
    truncated = data[:min(len(data), 300)]
    result = repair_with_sinks(truncated, container, [sink])
    assert result.patched is None
    assert result.limitations


def test_i386_guard_skipped_for_nonpositive_capacity():
    data, container, sink = _sink_for(ELF)
    bad = Sink(**{**sink.to_dict(), "capacity": 0})
    result = repair_with_sinks(data, container, [bad])
    assert result.patched is None
    assert any("non-positive capacity" in item for item in result.limitations)


def test_i386_guard_skipped_for_unsupported_copy_op():
    data, container, sink = _sink_for(PE)
    bad = Sink(**{**sink.to_dict(), "capacity": 16, "callee": "strcpy_s"})
    result = repair_with_sinks(data, container, [bad])
    assert result.patched is None
    assert any("guard skipped" in item for item in result.limitations)


def test_i386_elf32_dynamic_guard_injection_redirects_and_reparses():
    """Dynamic ELF32: the guard cave is appended and E8 -> .plt is redirected."""
    data, container, sink = _sink_for(ELF_DYN)
    assert sink.call_size == 5
    result = repair_with_sinks(data, container, [sink])
    assert result.ok, result.limitations
    assert result.injected_va is not None
    assert result.actions and result.actions[0]["kind"] == "guard"
    assert result.actions[0]["method"] == "new-pt-load"
    patched = result.patched
    assert patched is not None and patched != data

    check = detect_container(patched)
    assert (check.format, check.arch, check.bits) == ("elf", "i386", 32)
    assert check.limitations == []

    off = sink.call_offset
    assert patched[off] == 0xE8
    delta = struct.unpack_from("<i", patched, off + 1)[0]
    assert sink.call_va + 5 + delta == result.injected_va

    elf = ELFFile(io.BytesIO(patched))
    loads = [seg for seg in elf.iter_segments() if seg["p_type"] == "PT_LOAD"]
    cave = [seg for seg in loads if int(seg["p_vaddr"]) == result.injected_va]
    assert cave
    seg = cave[0]
    assert int(seg["p_flags"]) & 0x5 == 0x5
    raw = patched[int(seg["p_offset"]):int(seg["p_offset"]) + int(seg["p_filesz"])]
    guard = build_guard(abi_for("elf", "i386"), sink.callee, int(sink.capacity))
    assert raw[:len(guard)] == guard


def test_i386_pe32_direct_iat_ff15_redirects_with_nop_and_reparses():
    """PE32 FF 15 abs32 call site becomes E8 rel32 + one NOP (end-to-end)."""
    import lief

    data, container, sink = _sink_for(PE_IAT)
    assert sink.call_size == 6
    assert data[sink.call_offset:sink.call_offset + 2] == b"\xFF\x15"
    result = repair_with_sinks(data, container, [sink])
    assert result.ok, result.limitations
    assert result.injected_va is not None
    assert result.actions and result.actions[0]["kind"] == "guard"
    assert result.actions[0]["method"] == "pe-section"
    patched = result.patched
    assert patched is not None

    off = sink.call_offset
    assert patched[off] == 0xE8
    assert patched[off + 5] == 0x90  # original 6-byte FF15 -> E8 + NOP
    delta = struct.unpack_from("<i", patched, off + 1)[0]
    assert sink.call_va + 5 + delta == result.injected_va

    check = detect_container(patched)
    assert (check.format, check.arch, check.bits) == ("pe", "i386", 32)
    assert check.limitations == []
    pe = lief.PE.parse(list(patched))
    section = pe.get_section(".brfix")
    assert section is not None
    guard = build_guard(abi_for("pe", "i386"), sink.callee, int(sink.capacity))
    assert bytes(section.content)[:len(guard)] == guard


def test_i386_memcpy_immediate_patch_end_to_end():
    """The writer clamps memcpy's push imm32 from 64 to the 16-byte capacity."""
    data, container, sink = _sink_for(ELF_MEMCPY)
    assert sink.kind == "memcpy_length"
    assert sink.length == 64
    assert sink.capacity == 16
    assert sink.length_offset is not None
    result = repair_with_sinks(data, container, [sink])
    assert result.ok, result.limitations
    assert result.actions and result.actions[0]["kind"] == "immediate"
    assert result.actions[0]["before"] == 64
    assert result.actions[0]["after"] == 16
    patched = result.patched
    assert patched is not None
    assert patched[sink.length_offset:sink.length_offset + 4] == struct.pack("<I", 16)
    check = detect_container(patched)
    assert (check.format, check.arch, check.bits) == ("elf", "i386", 32)
    assert check.limitations == []


def _synthetic_elf32_full_phdr_page() -> bytes:
    """ELF32 whose phdr table fills the first page, forcing extend-rx."""
    entry = 0x08048000
    phoff = 0x40
    phnum = 127  # (127 + 1) * 32 + 0x40 = 0x1040 > 0x1000
    body = bytearray(0x2000)
    eh = bytearray(52)
    eh[:4] = b"\x7fELF"
    eh[4] = 1  # ELFCLASS32
    eh[5] = 1  # little endian
    eh[6] = 1  # current version
    struct.pack_into("<HHIIIIIHHHHHH", eh, 16, 2, 3, 1, entry, phoff, 0, 0,
                     52, 32, phnum, 40, 0, 0)
    ph = struct.pack("<IIIIIIII", 1, 0, entry, entry, 0x2000, 0x2000, 5, 0x1000)
    body[:52] = eh
    body[phoff:phoff + 32] = ph
    body[0x1100] = 0xC3  # ret
    return bytes(body)


def test_elf32_extend_rx_fallback_when_phdr_table_is_full():
    """ELF32 with no room for one more phdr extends the last R-X PT_LOAD."""
    original = _synthetic_elf32_full_phdr_page()
    cave = add_rx_segment(original, b"\xC3")
    assert cave.method == "extend-rx"
    assert cave.report["class"] == 32
    assert cave.report["extended_index"] == 0
    assert cave.report["segment"]["p_flags"] == "R-X"
    assert cave.cave_vaddr == 0x08048000 + 0x2000
    assert cave.cave_offset == 0x2000

    assert detect_container(original).format == "elf"
    reparsed = detect_container(cave.data)
    assert (reparsed.format, reparsed.arch, reparsed.bits) == ("elf", "i386", 32)
    assert reparsed.limitations == []
    elf = ELFFile(io.BytesIO(cave.data))
    loads = [seg for seg in elf.iter_segments() if seg["p_type"] == "PT_LOAD"]
    assert len(loads) == 1
    seg = loads[0]
    assert int(seg["p_flags"]) & 0x1  # executable
    assert int(seg["p_filesz"]) == 0x2001
    assert int(seg["p_memsz"]) == 0x2001
    assert cave.data.endswith(b"\xC3")
    assert cave.data[cave.cave_offset:] == b"\xC3"
