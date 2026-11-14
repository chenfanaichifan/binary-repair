"""Minimal ELF code-cave/segment injection for repaired wrappers.

This is deliberately narrow but real: a new R-X PT_LOAD is added so a redirected
call can execute injected machine code.  The wrapper is machine code written
directly into the new bytes; no assembly text is parsed or reassembled.

Two deterministic strategies add exactly one new PT_LOAD:

``append-phdr``
    The program-header table has a free slot: the next phdr entry is written at
    the end of the table and ``e_phnum`` grows by one.  The slot must stay inside
    the first page (the historical constraint) **and** must not overlap early
    runtime metadata (PT_INTERP / PT_NOTE / PT_DYNAMIC file ranges).  This is
    the normal path for the small synthetic images and the static fixtures used
    by the legacy engine.

``repurpose-pt-note``
    The phdr table has no free slot, which is the common case for real
    dynamically linked ELFs: the table is immediately followed by ``.interp``
    and the note sections.  Growing the table in place would overwrite the
    interpreter path string, producing candidates the dynamic loader cannot
    start.  Instead one non-essential ``PT_NOTE`` program header is rewritten in
    place into the new ``PT_LOAD`` (``PF_R|PF_X``, payload at 4 KiB-aligned EOF,
    vaddr at 4 KiB-aligned end of the image, ``p_align=4096``) and ``e_phnum``
    is left unchanged, so PT_INTERP and every dynamic segment are preserved.

After either strategy the result is re-parsed and verified fail-closed: the
container identity, program-header count, interpreter string, untouched phdr
entries and the new R-X PT_LOAD payload are all checked.  A verification
failure raises :class:`CaveError` and no candidate is returned.

ELF32 (i386) and ELF64 (x86-64/AArch64) are both supported: the program header
encoding, ``e_phnum`` offset and ``p_filesz``/``p_memsz`` offsets are selected
from the ELF class.

Known residual: static ET_EXEC images without PT_INTERP/PT_NOTE keep the legacy
``append-phdr`` path (that is what their existing fixtures exercise); if the
table has no genuine padding there, the new phdr slot can overwrite the first
bytes of an allocatable section in the header page.  Dynamic ELFs never take
that path because their PT_INTERP/PT_NOTE ranges block it.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Any

from elftools.elf.elffile import ELFFile

PAGE = 0x1000

_ELF32_PHDR = "<IIIIIIII"
_ELF64_PHDR = "<IIQQQQQQ"
_E_PHNUM_OFF = {32: 0x2C, 64: 0x38}
_P_FILESZ_OFF = {32: 16, 64: 32}
_P_MEMSZ_OFF = {32: 20, 64: 40}
# Early file metadata whose bytes must never be overwritten by a new phdr.
_CRITICAL_EARLY_SEGMENTS = ("PT_INTERP", "PT_NOTE", "PT_DYNAMIC")


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


def _reloc_count(data: bytes) -> int:
    elf = ELFFile(io.BytesIO(data))
    total = 0
    for sec in elf.iter_sections():
        if sec["sh_type"] in ("SHT_RELA", "SHT_REL"):
            total += sec.num_relocations()
    return total


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


def _phdrs(elf) -> list[dict[str, Any]]:
    """Every program header in on-disk order (index == phdr table position)."""
    entries: list[dict[str, Any]] = []
    for index, seg in enumerate(elf.iter_segments()):
        entries.append({
            "index": index,
            "type": str(seg["p_type"]),
            "offset": int(seg["p_offset"]),
            "vaddr": int(seg["p_vaddr"]),
            "filesz": int(seg["p_filesz"]),
            "memsz": int(seg["p_memsz"]),
            "flags": int(seg["p_flags"]),
            "align": int(seg["p_align"]),
        })
    return entries


def _ranges_overlap(start: int, end: int, ranges) -> bool:
    return any(start < other_end and other_start < end
               for other_start, other_end in ranges)


def _phdr_slot_has_room(data: bytes, elf, phoff: int, phentsize: int,
                        phnum: int) -> bool:
    """Whether one more phdr can be appended without clobbering metadata."""
    at = phoff + phnum * phentsize
    end = at + phentsize
    if end > PAGE or end > len(data):
        return False
    critical = [
        (entry["offset"], entry["offset"] + entry["filesz"])
        for entry in _phdrs(elf)
        if entry["type"] in _CRITICAL_EARLY_SEGMENTS and entry["filesz"] > 0
    ]
    return not _ranges_overlap(at, end, critical)


def _note_repurpose_index(elf) -> int | None:
    """Pick one non-essential PT_NOTE phdr that can become the new PT_LOAD.

    A note whose file range is described by another program header (for example
    ``.note.gnu.property`` is also referenced by PT_GNU_PROPERTY) is avoided:
    its bytes stay valid in the file, but its phdr is not needed to describe
    them.  Later notes (build-id style) are preferred deterministically.
    """
    entries = _phdrs(elf)
    notes = [
        entry for entry in entries
        if entry["type"] == "PT_NOTE" and entry["filesz"] > 0
    ]
    if not notes:
        return None
    other_ranges = [
        (entry["offset"], entry["offset"] + entry["filesz"])
        for entry in entries
        if entry["type"] != "PT_NOTE" and entry["filesz"] > 0
    ]
    unreferenced = [
        entry for entry in notes
        if not _ranges_overlap(entry["offset"],
                               entry["offset"] + entry["filesz"], other_ranges)
    ]
    pool = unreferenced or notes
    # Highest file offset first (build-id notes usually trail properties),
    # then lowest phdr index for a stable tie-break.
    return sorted(pool, key=lambda item: (-item["offset"], item["index"]))[0]["index"]


def _payload(data: bytes, code: bytes, max_vaddr: int,
             bits: int) -> tuple[bytearray, int, int]:
    file_off = _align(len(data), PAGE)
    vaddr = _align(max_vaddr, PAGE)
    body = bytearray(data)
    if len(body) < file_off:
        body.extend(b"\x00" * (file_off - len(body)))
    body.extend(code)
    if bits == 32:
        if max(file_off, vaddr, len(code)) > 0xFFFFFFFF:
            raise CaveError("ELF32 cave exceeds 32-bit address space")
    return body, file_off, vaddr


def _pack_load(bits: int, file_off: int, vaddr: int, size: int) -> bytes:
    if bits == 32:
        return struct.pack(_ELF32_PHDR, 1, file_off, vaddr, vaddr,
                           size, size, 5, PAGE)
    return struct.pack(_ELF64_PHDR, 1, 5, file_off, vaddr, vaddr,
                       size, size, PAGE)


def _verify_injection(original: bytes, patched: bytes, *, strategy: str,
                      phoff: int, phentsize: int, original_phnum: int,
                      note_index: int | None, cave_vaddr: int,
                      code_size: int, file_off: int) -> None:
    """Re-parse the result and fail closed on any identity/metadata change."""
    try:
        new_elf = ELFFile(io.BytesIO(patched))
        new_phnum = int(new_elf.header["e_phnum"])
        new_phoff = int(new_elf.header["e_phoff"])
    except Exception as exc:  # noqa: BLE001 - fail closed on any parse error
        raise CaveError(f"patched ELF no longer parses: {type(exc).__name__}") from exc
    if new_phoff != phoff:
        raise CaveError("patched ELF moved the program-header table")
    expected = original_phnum + (1 if strategy == "append-phdr" else 0)
    if new_phnum != expected:
        raise CaveError(
            f"patched ELF phnum={new_phnum}, expected {expected} for {strategy}"
        )
    # Untouched program headers must stay byte-identical.
    original_table = original[phoff:phoff + original_phnum * phentsize]
    patched_table = patched[phoff:phoff + original_phnum * phentsize]
    if strategy == "append-phdr":
        if original_table != patched_table:
            raise CaveError("append-phdr path modified existing program headers")
    else:
        slot = -1 if note_index is None else note_index
        if not 0 <= slot < original_phnum:
            raise CaveError("repurpose-pt-note path has no source phdr")
        for index in range(original_phnum):
            if index == slot:
                continue
            start = index * phentsize
            if (original_table[start:start + phentsize]
                    != patched_table[start:start + phentsize]):
                raise CaveError(
                    f"repurpose-pt-note path modified phdr #{index}"
                )

    def interpreter(image: bytes) -> tuple[int, int, bytes] | None:
        elf = ELFFile(io.BytesIO(image))
        for seg in elf.iter_segments():
            if str(seg["p_type"]) != "PT_INTERP":
                continue
            offset = int(seg["p_offset"])
            size = int(seg["p_filesz"])
            return offset, size, bytes(image[offset:offset + size])
        return None

    original_interp = interpreter(original)
    if original_interp is not None:
        patched_interp = interpreter(patched)
        if patched_interp is None:
            raise CaveError("patched ELF lost PT_INTERP")
        if patched_interp[2] != original_interp[2]:
            raise CaveError("patched ELF corrupted the interpreter path")
    # The new cave has to be an R-X PT_LOAD covering exactly the blob.
    try:
        new_elf = ELFFile(io.BytesIO(patched))
        cave = None
        for seg in new_elf.iter_segments():
            if (str(seg["p_type"]) == "PT_LOAD"
                    and int(seg["p_vaddr"]) == cave_vaddr):
                cave = seg
                break
        if cave is None:
            raise CaveError("patched ELF is missing the injected R-X PT_LOAD")
        if int(cave["p_flags"]) & 0x5 != 0x5:
            raise CaveError("injected PT_LOAD is not R-X")
        if int(cave["p_filesz"]) != code_size or int(cave["p_memsz"]) != code_size:
            raise CaveError("injected PT_LOAD size does not match the guard blob")
        if int(cave["p_offset"]) != file_off:
            raise CaveError("injected PT_LOAD offset does not match the payload")
    except CaveError:
        raise
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise CaveError(
            f"patched ELF cave re-parse failed: {type(exc).__name__}"
        ) from exc


def _extend_rx_segment(data: bytes, elf, loads, code: bytes, bits: int,
                       report: dict[str, Any]) -> CaveResult:
    """Legacy fallback: extend the last executable PT_LOAD (no new phdr)."""
    eh = elf.header
    phoff = int(eh["e_phoff"])
    phentsize = int(eh["e_phentsize"])
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
    if bits == 32:
        if new_filesz > 0xFFFFFFFF:
            raise CaveError("ELF32 segment extension exceeds 32-bit range")
        struct.pack_into("<I", body, ph_at + _P_FILESZ_OFF[32], new_filesz)
        struct.pack_into("<I", body, ph_at + _P_MEMSZ_OFF[32],
                         max(seg["memsz"], new_filesz))
    else:
        struct.pack_into("<Q", body, ph_at + _P_FILESZ_OFF[64], new_filesz)
        struct.pack_into("<Q", body, ph_at + _P_MEMSZ_OFF[64],
                         max(seg["memsz"], new_filesz))
    before = _reloc_count(data)
    after = _reloc_count(bytes(body))
    report.update({
        "segment": {"p_offset": seg["offset"], "p_vaddr": seg["vaddr"],
                    "p_filesz": new_filesz, "p_flags": "R-X"},
        "phdr_strategy": "extend-rx",
        "extended_index": seg["index"],
        "relocations_before": before,
        "relocations_after": after,
        "relocations_unchanged": before == after,
    })
    return CaveResult(bytes(body), vaddr, file_off, "extend-rx", report)


def add_rx_segment(data: bytes, code: bytes) -> CaveResult:
    if not code:
        raise CaveError("empty cave code")
    elf, loads = _elf_layout(data)
    eh = elf.header
    bits = 32 if elf.elfclass == 32 else 64
    if bits not in _E_PHNUM_OFF:
        raise CaveError(f"unsupported ELF class: {bits}-bit")
    phoff = int(eh["e_phoff"])
    phentsize = int(eh["e_phentsize"])
    phnum = int(eh["e_phnum"])
    max_vaddr = max(x["vaddr"] + x["memsz"] for x in loads)
    report: dict[str, Any] = {
        "class": bits,
        "phnum": phnum,
        "phoff": phoff,
        "phdr_strategy": "",
    }

    if _phdr_slot_has_room(data, elf, phoff, phentsize, phnum):
        body, file_off, vaddr = _payload(data, code, max_vaddr, bits)
        at = phoff + phnum * phentsize
        body[at:at + phentsize] = _pack_load(bits, file_off, vaddr, len(code))
        struct.pack_into("<H", body, _E_PHNUM_OFF[bits], phnum + 1)  # e_phnum
        patched = bytes(body)
        strategy = "append-phdr"
        phnum_after = phnum + 1
        note_index = None
    else:
        note_index = _note_repurpose_index(elf)
        if note_index is None:
            has_interp = any(
                str(seg["p_type"]) == "PT_INTERP" for seg in elf.iter_segments()
            )
            if has_interp:
                # A dynamic image needs its interpreter and dynamic metadata;
                # the legacy extend-rx fallback can overlap another PT_LOAD's
                # virtual range, so fail closed instead of emitting a candidate
                # the loader cannot start.
                raise CaveError(
                    "dynamic ELF has no free program-header slot and no "
                    "PT_NOTE to repurpose (fail closed)"
                )
            return _extend_rx_segment(data, elf, loads, code, bits, report)
        body, file_off, vaddr = _payload(data, code, max_vaddr, bits)
        at = phoff + note_index * phentsize
        body[at:at + phentsize] = _pack_load(bits, file_off, vaddr, len(code))
        patched = bytes(body)
        strategy = "repurpose-pt-note"
        phnum_after = phnum

    _verify_injection(
        data, patched, strategy=strategy, phoff=phoff, phentsize=phentsize,
        original_phnum=phnum, note_index=note_index, cave_vaddr=vaddr,
        code_size=len(code), file_off=file_off,
    )
    before = _reloc_count(data)
    after = _reloc_count(patched)
    report.update({
        "segment": {"p_offset": file_off, "p_vaddr": vaddr,
                    "p_filesz": len(code), "p_flags": "R-X"},
        "phnum": phnum_after,
        "phdr_strategy": strategy,
        "cave_vaddr": vaddr,
        "cave_offset": file_off,
        "interp_preserved": any(
            str(seg["p_type"]) == "PT_INTERP" for seg in elf.iter_segments()
        ),
        "relocations_before": before,
        "relocations_after": after,
        "relocations_unchanged": before == after,
    })
    if strategy == "repurpose-pt-note":
        report["repurposed_note_index"] = note_index
    return CaveResult(patched, vaddr, file_off, "new-pt-load", report)


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


def build_strcat_guard(capacity: int, *, message: bytes = b"concat exceeds capacity\n") -> bytes:
    """Machine-code strcat guard. rdi=dst, rsi=src; returns or exits(1)."""
    if not 0 < capacity <= 0x7FFFFFFF:
        raise CaveError("invalid capacity")
    code = bytearray()
    labels: dict[str, int] = {}
    patches: list[tuple[int, str]] = []

    def emit(b: bytes) -> None:
        code.extend(b)

    def mark(name: str) -> None:
        labels[name] = len(code)

    def jcc(label: str, opcode: int) -> None:
        emit(bytes([0x0F, opcode, 0, 0, 0, 0]))
        patches.append((len(code) - 4, label))

    def jmp(label: str) -> None:
        emit(b"\xE9\x00\x00\x00\x00")
        patches.append((len(code) - 4, label))

    emit(b"\x48\xC7\xC1" + struct.pack("<I", capacity))  # mov rcx,capacity
    mark("find_end")
    emit(b"\x8A\x07")                  # mov al,[rdi]
    emit(b"\x84\xC0")                  # test al,al
    jcc("append", 0x84)                # jz append
    emit(b"\x48\xFF\xC7")             # inc rdi
    emit(b"\x48\xFF\xC9")             # dec rcx
    jcc("overflow", 0x84)             # jz overflow
    jmp("find_end")
    mark("append")
    emit(b"\x8A\x06")                  # mov al,[rsi]
    emit(b"\x84\xC0")
    jcc("done", 0x84)                  # jz done
    emit(b"\x48\xFF\xC9")             # dec rcx
    jcc("overflow", 0x84)
    emit(b"\x88\x07")                  # mov [rdi],al
    emit(b"\x48\xFF\xC7")
    emit(b"\x48\xFF\xC6")
    jmp("append")
    mark("done")
    emit(b"\xC6\x07\x00")             # mov byte [rdi],0
    emit(b"\xC3")
    mark("overflow")
    emit(b"\xB8\x01\x00\x00\x00")
    emit(b"\xBF\x02\x00\x00\x00")
    emit(b"\x48\x8D\x35\x00\x00\x00\x00")
    patches.append((len(code) - 4, "message"))
    emit(b"\xBA" + struct.pack("<I", len(message)))
    emit(b"\x0F\x05")
    emit(b"\xB8\x3C\x00\x00\x00")
    emit(b"\xBF\x01\x00\x00\x00")
    emit(b"\x0F\x05")
    mark("message")
    code.extend(message)
    for at, name in patches:
        code[at:at + 4] = struct.pack("<i", labels[name] - (at + 4))
    return bytes(code)


def inject_strcat_guard(data: bytes, *, call_vaddr: int, call_file_offset: int,
                        capacity: int) -> CaveResult:
    cave = build_strcat_guard(capacity)
    added = add_rx_segment(data, cave)
    patched = bytearray(added.data)
    patch_call(patched, call_vaddr, added.cave_vaddr, file_offset=call_file_offset)
    result = CaveResult(bytes(patched), added.cave_vaddr, added.cave_offset,
                        added.method, dict(added.report))
    result.report["call_site"] = hex(call_vaddr)
    result.report["capacity"] = capacity
    result.report["cave_size"] = len(cave)
    result.report["wrapper"] = "strcat-guard"
    return result
