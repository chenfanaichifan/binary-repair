"""Minimal ELF x86-64 code-cave/segment injection for repaired wrappers.

This is deliberately narrow but real: a new R-X PT_LOAD is appended when the
program-header table has room; otherwise the last R-X PT_LOAD is extended.  The
wrapper is machine code written directly into the new bytes; no assembly text
is parsed or reassembled.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Any

from elftools.elf.elffile import ELFFile

PAGE = 0x1000


@dataclass
class CaveResult:
    data: bytes
    cave_vaddr: int
    cave_offset: int
    method: str
    report: dict[str, Any]


class CaveError(RuntimeError):
    pass


def _align(value: int, alignment: int = 16) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def _elf_layout(data: bytes):
    elf = ELFFile(io.BytesIO(data))
    loads = []
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_LOAD":
            loads.append({
                "offset": int(seg["p_offset"]), "vaddr": int(seg["p_vaddr"]),
                "filesz": int(seg["p_filesz"]), "memsz": int(seg["p_memsz"]),
                "flags": int(seg["p_flags"]), "index": len(loads),
            })
    if not loads:
        raise CaveError("ELF has no PT_LOAD")
    return elf, loads


def add_rx_segment(data: bytes, code: bytes) -> CaveResult:
    if not code:
        raise CaveError("empty cave code")
    elf, loads = _elf_layout(data)
    eh = elf.header
    phoff = int(eh["e_phoff"])
    phentsize = int(eh["e_phentsize"])
    phnum = int(eh["e_phnum"])
    # Only add a phdr when it does not overwrite the first mapped bytes.
    first_mapped = PAGE
    can_add = phoff + (phnum + 1) * phentsize <= first_mapped
    max_vaddr = max(x["vaddr"] + x["memsz"] for x in loads)
    if can_add:
        file_off = _align(len(data), PAGE)
        vaddr = _align(max_vaddr, PAGE)
        body = bytearray(data)
        if len(body) < file_off:
            body.extend(b"\x00" * (file_off - len(body)))
        body.extend(code)
        # new program header
        new_ph = struct.pack("<IIQQQQQQ", 1, 5, file_off, vaddr, vaddr,
                             len(code), len(code), PAGE)
        at = phoff + phnum * phentsize
        if at + len(new_ph) > len(body):
            raise CaveError("program header table has no room")
        body[at:at + len(new_ph)] = new_ph
        struct.pack_into("<H", body, 0x38, phnum + 1)  # e_phnum
        return CaveResult(bytes(body), vaddr, file_off, "new-pt-load", {
            "segment": {"p_offset": file_off, "p_vaddr": vaddr,
                        "p_filesz": len(code), "p_flags": "R-X"},
            "phnum": phnum + 1,
        })

    # Fallback: extend a writable-header R-X segment.  This is still a binary
    # segment extension, but not a new PT_LOAD.
    candidates = [x for x in loads if x["flags"] & 0x1]
    if not candidates:
        raise CaveError("no executable PT_LOAD available for extension")
    seg = candidates[-1]
    file_off = _align(len(data), 16)
    vaddr = seg["vaddr"] + (file_off - seg["offset"])
    body = bytearray(data)
    if len(body) < file_off:
        body.extend(b"\x00" * (file_off - len(body)))
    body.extend(code)
    new_filesz = max(seg["filesz"], file_off + len(code) - seg["offset"])
    ph_at = phoff + seg["index"] * phentsize
    struct.pack_into("<Q", body, ph_at + 32, new_filesz)
    struct.pack_into("<Q", body, ph_at + 40, max(seg["memsz"], new_filesz))
    return CaveResult(bytes(body), vaddr, file_off, "extend-rx", {
        "segment": {"p_offset": seg["offset"], "p_vaddr": seg["vaddr"],
                    "p_filesz": new_filesz, "p_flags": "R-X"},
        "extended_index": seg["index"],
    })


def patch_call(data: bytearray, call_vaddr: int, cave_vaddr: int,
               *, file_offset: int) -> None:
    """Patch a 5-byte E8 call at file_offset."""
    if data[file_offset] != 0xE8:
        raise CaveError("call site is not an E8 rel32 instruction")
    disp = cave_vaddr - (call_vaddr + 5)
    if not -(1 << 31) <= disp < (1 << 31):
        raise CaveError("call target out of rel32 range")
    data[file_offset + 1:file_offset + 5] = struct.pack("<i", disp)


def build_strcpy_guard(capacity: int, *, message: bytes = b"copy exceeds capacity\n") -> bytes:
    """Machine-code strcpy guard. rdi=dst, rsi=src; returns or exits(1)."""
    if not 0 < capacity <= 0x7FFFFFFF:
        raise CaveError("invalid capacity")
    code = bytearray()
    labels: dict[str, int] = {}
    patches: list[tuple[str, int, str]] = []

    def emit(b: bytes) -> None:
        code.extend(b)

    def mark(name: str) -> None:
        labels[name] = len(code)

    def jcc(label: str, opcode: int) -> None:
        emit(bytes([0x0F, opcode, 0, 0, 0, 0]))
        patches.append(("rel32", len(code) - 4, label))

    def jmp(label: str) -> None:
        emit(b"\xE9\x00\x00\x00\x00")
        patches.append(("rel32", len(code) - 4, label))

    emit(b"\x48\xC7\xC1" + struct.pack("<I", capacity))  # mov rcx,capacity
    mark("loop")
    emit(b"\x8A\x06")                  # mov al,[rsi]
    emit(b"\x84\xC0")                  # test al,al
    jcc("done", 0x84)                  # jz done
    emit(b"\x48\xFF\xC9")             # dec rcx
    jcc("overflow", 0x84)             # jz overflow
    emit(b"\x88\x07")                  # mov [rdi],al
    emit(b"\x48\xFF\xC7")             # inc rdi
    emit(b"\x48\xFF\xC6")             # inc rsi
    jmp("loop")
    mark("done")
    emit(b"\xC6\x07\x00")             # mov byte [rdi],0
    emit(b"\xC3")                       # ret
    mark("overflow")
    emit(b"\xB8\x01\x00\x00\x00")     # write(2,msg,len)
    emit(b"\xBF\x02\x00\x00\x00")
    emit(b"\x48\x8D\x35\x00\x00\x00\x00")
    patches.append(("rel32", len(code) - 4, "message"))
    emit(b"\xBA" + struct.pack("<I", len(message)))
    emit(b"\x0F\x05")
    emit(b"\xB8\x3C\x00\x00\x00")     # exit_group(1)
    emit(b"\xBF\x01\x00\x00\x00")
    emit(b"\x0F\x05")
    mark("message")
    code.extend(message)
    for kind, at, name in patches:
        target = labels[name]
        disp = target - (at + 4)
        code[at:at + 4] = struct.pack("<i", disp)
    return bytes(code)


def inject_strcpy_guard(data: bytes, *, call_vaddr: int, call_file_offset: int,
                        capacity: int) -> CaveResult:
    cave = build_strcpy_guard(capacity)
    added = add_rx_segment(data, cave)
    patched = bytearray(added.data)
    patch_call(patched, call_vaddr, added.cave_vaddr, file_offset=call_file_offset)
    result = CaveResult(bytes(patched), added.cave_vaddr, added.cave_offset,
                        added.method, dict(added.report))
    result.report["call_site"] = hex(call_vaddr)
    result.report["capacity"] = capacity
    result.report["cave_size"] = len(cave)
    result.report["wrapper"] = "strcpy-guard"
    return result
