"""Real ELF code-cave injection: new R-X PT_LOAD + strcpy wrapper.

The injection has two deterministic strategies: ``append-phdr`` when the program
header table genuinely has a free slot, and ``repurpose-pt-note`` (rewrite one
non-essential PT_NOTE phdr in place) for real dynamic ELFs whose header table is
immediately followed by ``.interp``/notes.  The dynamic-ELF tests below are the
regression guard for the historical bug where growing the phdr table in place
corrupted PT_INTERP and produced candidates the loader could not start.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest
from elftools.elf.elffile import ELFFile

from app.services.code_cave import (
    PAGE,
    CaveError,
    _verify_injection,
    add_rx_segment,
    inject_strcat_guard,
    inject_strcpy_guard,
)
from app.services.binary_repair_engine import BinaryRepairReport, _apply_copy_caves
from app.services.containers import detect_container
from app.services.x86_runtime import emulate_elf

BASE = 0x400000
ENTRY = BASE + 0x1000
ROOT = Path(__file__).resolve().parents[1]
HEAP_DYNAMIC = ROOT / "fixtures" / "hard-cases" / "vuln-heap-malloc-x86_64.elf"
STATIC_X64 = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"


def _build(src: bytes, etype: int = 2) -> tuple[bytes, int, int]:
    code = bytearray()
    code += b"\x48\x83\xec\x10"                 # sub rsp,16
    code += b"\x48\x8d\x3c\x24"                 # lea rdi,[rsp]
    lea_at = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"      # lea rsi,[rip+src]
    call_at = len(code)
    code += b"\xe8\x00\x00\x00\x00"              # call (patched by cave)
    code += b"\xb8\x01\x00\x00\x00"              # write(1,rsp,16)
    code += b"\xbf\x01\x00\x00\x00"
    code += b"\x48\x89\xe6"
    code += b"\xba\x10\x00\x00\x00"
    code += b"\x0f\x05"
    code += b"\xb8\x3c\x00\x00\x00"              # exit(0)
    code += b"\x31\xff"
    code += b"\x0f\x05"
    src_off = len(code)
    code += src
    # lea rsi,[rip+src]
    disp = src_off - (lea_at + 7)
    code[lea_at + 3:lea_at + 7] = struct.pack("<i", disp)
    # initial call target is self (must not be executed before patching)
    disp = - (call_at + 5)
    code[call_at + 1:call_at + 5] = struct.pack("<i", disp)
    text_off = 0x1000
    code_off = text_off
    call_file_offset = code_off + call_at
    call_vaddr = ENTRY + call_at

    shstr = b"\x00.text\x00.shstrtab\x00"
    shstr_off = code_off + len(code)
    shoff = (shstr_off + len(shstr) + 7) & ~7
    body = bytearray(shoff)
    eh = bytearray(64); eh[:4] = b"\x7fELF"; eh[4] = 2; eh[5] = 1; eh[6] = 1
    struct.pack_into("<HHIQQQIHHHHHH", eh, 16, etype, 62, 1, ENTRY, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    ph = bytearray(56)
    struct.pack_into("<IIQQQQQQ", ph, 0, 1, 5, 0, BASE, BASE, 0x1000 + len(code), 0x1000 + len(code), 0x1000)
    sh = bytearray(3 * 64)
    struct.pack_into("<IIQQQQIIQQ", sh, 64, 1, 1, 6, ENTRY, text_off, len(code), 0, 0, 16, 0)
    struct.pack_into("<IIQQQQIIQQ", sh, 128, 7, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
    eh[0x28:0x30] = struct.pack("<Q", shoff)
    eh[0x3A:0x3C] = struct.pack("<H", 64)
    eh[0x3C:0x3E] = struct.pack("<H", 3)
    eh[0x3E:0x40] = struct.pack("<H", 2)
    body[:64] = eh; body[64:120] = ph
    body[text_off:text_off + len(code)] = code
    body[shstr_off:shstr_off + len(shstr)] = shstr
    body[shoff:shoff + 3 * 64] = sh
    return bytes(body), call_vaddr, call_file_offset


def test_new_pt_load_cave_blocks_long_strcpy_and_keeps_short():
    original, call_vaddr, call_off = _build(b"hi")
    cave = inject_strcpy_guard(original, call_vaddr=call_vaddr,
                               call_file_offset=call_off, capacity=16)
    assert cave.method == "new-pt-load"
    assert cave.report["wrapper"] == "strcpy-guard"
    assert len(cave.data) > len(original)
    result = emulate_elf(cave.data)
    assert result.exit_code == 0
    assert result.stack_tail == b"Z" * 16

    original, call_vaddr, call_off = _build(b"A" * 32)
    cave = inject_strcpy_guard(original, call_vaddr=call_vaddr,
                               call_file_offset=call_off, capacity=16)
    result = emulate_elf(cave.data)
    assert result.exit_code == 1
    assert b"copy exceeds capacity" in result.stderr
    assert result.stack_tail == b"Z" * 16


def test_strcat_guard_blocks_overflow_and_keeps_short():
    original, call_vaddr, call_off = _build(b"!")
    cave = inject_strcat_guard(original, call_vaddr=call_vaddr,
                               call_file_offset=call_off, capacity=16)
    assert cave.report["wrapper"] == "strcat-guard"
    result = emulate_elf(cave.data)
    assert result.exit_code == 0
    assert result.stack_tail == b"Z" * 16

    original, call_vaddr, call_off = _build(b"A" * 32)
    cave = inject_strcat_guard(original, call_vaddr=call_vaddr,
                               call_file_offset=call_off, capacity=16)
    result = emulate_elf(cave.data)
    assert result.exit_code == 1
    assert b"concat exceeds capacity" in result.stderr
    assert result.stack_tail == b"Z" * 16


def test_cave_works_for_et_dyn_pie_style_image():
    original, call_vaddr, call_off = _build(b"hi", etype=3)
    cave = inject_strcpy_guard(original, call_vaddr=call_vaddr,
                               call_file_offset=call_off, capacity=16)
    assert cave.method == "new-pt-load"
    result = emulate_elf(cave.data)
    assert result.exit_code == 0


def test_engine_cave_pass_integrates_strcpy_call():
    original, call_vaddr, call_off = _build(b"A" * 32)
    scan = {"findings": [{
        "kind": "unbounded_copy", "address": hex(call_vaddr),
        "callee": "strcpy", "patchable": True, "effective_capacity": 16,
        "call_file_offset": call_off,
    }]}
    report = BinaryRepairReport(
        original_sha256="x", patched_sha256="x", format="elf64-little",
        arch="x86_64", mode="unsupported", supported=False,
    )
    patched = _apply_copy_caves(original, scan, report)
    assert patched != original
    assert report.supported is False  # caller decides after this pass
    result = emulate_elf(patched)
    assert result.exit_code == 1
    assert b"copy exceeds capacity" in result.stderr


def test_cave_reports_relocations_unchanged():
    original, call_vaddr, call_off = _build(b"hi", etype=3)
    cave = inject_strcpy_guard(original, call_vaddr=call_vaddr,
                               call_file_offset=call_off, capacity=16)
    assert cave.report["relocations_before"] == cave.report["relocations_after"]
    assert cave.report["relocations_unchanged"] is True


# --- program-header strategy selection (dynamic ELF regression) -------------

def _require(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def _phdr_table(image: bytes) -> tuple[int, int, int, bytes]:
    elf = ELFFile(io.BytesIO(image))
    phoff = int(elf.header["e_phoff"])
    phentsize = int(elf.header["e_phentsize"])
    phnum = int(elf.header["e_phnum"])
    return phoff, phentsize, phnum, image[phoff:phoff + phnum * phentsize]


def _interp(image: bytes) -> tuple[int, int, bytes] | None:
    elf = ELFFile(io.BytesIO(image))
    for seg in elf.iter_segments():
        if str(seg["p_type"]) == "PT_INTERP":
            offset = int(seg["p_offset"])
            size = int(seg["p_filesz"])
            return offset, size, image[offset:offset + size]
    return None


def _segment_types(image: bytes) -> list[str]:
    return [str(seg["p_type"]) for seg in ELFFile(io.BytesIO(image)).iter_segments()]


def test_dynamic_elf_repurposes_note_and_preserves_interp():
    """Regression: phdr growth must never clobber PT_INTERP on a dynamic ELF."""
    original = _require(HEAP_DYNAMIC)
    cave = add_rx_segment(original, b"\xC3")
    report = cave.report
    assert cave.method == "new-pt-load"
    assert report["phdr_strategy"] == "repurpose-pt-note"
    assert report["interp_preserved"] is True

    original_interp = _interp(original)
    assert original_interp is not None
    assert _interp(cave.data) == original_interp

    phoff, phentsize, original_phnum, original_table = _phdr_table(original)
    new_phoff, new_phentsize, new_phnum, new_table = _phdr_table(cave.data)
    assert (new_phoff, new_phentsize) == (phoff, phentsize)
    assert new_phnum == original_phnum == report["phnum"]

    note_index = report["repurposed_note_index"]
    assert isinstance(note_index, int) and 0 <= note_index < original_phnum
    for index in range(original_phnum):
        if index == note_index:
            continue
        start = index * phentsize
        assert new_table[start:start + phentsize] == \
            original_table[start:start + phentsize], f"phdr #{index} changed"

    original_segments = ELFFile(io.BytesIO(original))
    original_note_count = sum(
        1 for seg in original_segments.iter_segments()
        if str(seg["p_type"]) == "PT_NOTE"
    )
    types = _segment_types(cave.data)
    assert types.count("PT_NOTE") == original_note_count - 1
    assert types.count("PT_LOAD") == _segment_types(original).count("PT_LOAD") + 1

    patched_elf = ELFFile(io.BytesIO(cave.data))
    cave_seg = [
        seg for index, seg in enumerate(patched_elf.iter_segments())
        if index == note_index
    ][0]
    assert str(cave_seg["p_type"]) == "PT_LOAD"
    assert int(cave_seg["p_flags"]) & 0x5 == 0x5
    assert int(cave_seg["p_vaddr"]) == cave.cave_vaddr
    assert int(cave_seg["p_offset"]) == cave.cave_offset
    assert cave.cave_vaddr % PAGE == 0 and cave.cave_offset % PAGE == 0
    assert cave.data[cave.cave_offset:] == b"\xC3"

    check = detect_container(cave.data)
    assert (check.format, check.arch, check.bits) == ("elf", "x86_64", 64)
    assert check.limitations == []


def test_static_elf_keeps_append_phdr_strategy():
    """Static images have no PT_INTERP: the legacy append-phdr path stays."""
    original = _require(STATIC_X64)
    cave = add_rx_segment(original, b"\xC3\xC3")
    report = cave.report
    assert cave.method == "new-pt-load"
    assert report["phdr_strategy"] == "append-phdr"
    assert _interp(original) is None and _interp(cave.data) is None
    _, _, original_phnum, original_table = _phdr_table(original)
    _, _, new_phnum, new_table = _phdr_table(cave.data)
    assert new_phnum == original_phnum + 1 == report["phnum"]
    assert new_table[:len(original_table)] == original_table
    check = detect_container(cave.data)
    assert (check.format, check.arch) == ("elf", "x86_64")
    assert check.limitations == []


def test_synthetic_elf_keeps_append_phdr_strategy():
    original, _call_vaddr, _call_off = _build(b"hi")
    cave = add_rx_segment(original, b"\xC3")
    assert cave.method == "new-pt-load"
    assert cave.report["phdr_strategy"] == "append-phdr"


def test_dynamic_elf_without_pt_note_fails_closed():
    """A dynamic ELF with no free slot and no PT_NOTE must not be half-patched."""
    original = _require(HEAP_DYNAMIC)
    phoff, phentsize, _phnum, _table = _phdr_table(original)
    mutated = bytearray(original)
    patched_any = False
    for index, seg in enumerate(ELFFile(io.BytesIO(original)).iter_segments()):
        if str(seg["p_type"]) != "PT_NOTE":
            continue
        # Rewrite the type to an unused OS-specific value: no PT_NOTE remains.
        struct.pack_into("<I", mutated, phoff + index * phentsize, 0x60000001)
        patched_any = True
    assert patched_any
    with pytest.raises(CaveError, match="fail closed"):
        add_rx_segment(bytes(mutated), b"\xC3")


def test_verification_rejects_interpreter_corruption():
    original = _require(HEAP_DYNAMIC)
    cave = add_rx_segment(original, b"\xC3")
    interp = _interp(original)
    assert interp is not None
    corrupted = bytearray(cave.data)
    corrupted[interp[0]] ^= 0xFF
    phoff, phentsize, phnum, _table = _phdr_table(original)
    with pytest.raises(CaveError, match="interpreter"):
        _verify_injection(
            original, bytes(corrupted), strategy="repurpose-pt-note",
            phoff=phoff, phentsize=phentsize, original_phnum=phnum,
            note_index=cave.report["repurposed_note_index"],
            cave_vaddr=cave.cave_vaddr, code_size=1,
            file_off=cave.cave_offset,
        )
