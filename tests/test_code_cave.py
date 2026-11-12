"""Real ELF code-cave injection: new R-X PT_LOAD + strcpy wrapper."""
from __future__ import annotations

import struct
from pathlib import Path

from app.services.code_cave import inject_strcat_guard, inject_strcpy_guard
from app.services.binary_repair_engine import BinaryRepairReport, _apply_copy_caves
from app.services.x86_runtime import emulate_elf

BASE = 0x400000
ENTRY = BASE + 0x1000


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
