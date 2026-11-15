"""Deterministic ELF PT_LOAD address mapping.

The verifier must not treat a section-table proximity as proof that a VA has
file bytes.  This module is the single read-only mapper for ELF PT_LOAD
segments; it distinguishes file-backed bytes from memory-only (NOBITS/bss)
coverage and fails closed on ambiguous matches.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum
from typing import Any

from elftools.elf.elffile import ELFFile


class MappingStatus(str, Enum):
    MAPPED_FILE_BACKED = "mapped_file_backed"
    MAPPED_MEMORY_ONLY = "mapped_memory_only"
    OUTSIDE_PT_LOAD = "outside_pt_load"
    AMBIGUOUS_SEGMENT = "ambiguous_segment"
    INVALID_FILE_RANGE = "invalid_file_range"
    INVALID_ALIGNMENT = "invalid_alignment"


@dataclass(frozen=True)
class AddressMapping:
    status: MappingStatus
    va: int | None = None
    file_offset: int | None = None
    segment_index: int | None = None
    p_offset: int = 0
    p_vaddr: int = 0
    p_filesz: int = 0
    p_memsz: int = 0
    p_align: int = 1
    executable: bool = False
    writable: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is MappingStatus.MAPPED_FILE_BACKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "va": self.va,
            "file_offset": self.file_offset,
            "segment_index": self.segment_index,
            "p_offset": self.p_offset,
            "p_vaddr": self.p_vaddr,
            "p_filesz": self.p_filesz,
            "p_memsz": self.p_memsz,
            "p_align": self.p_align,
            "executable": self.executable,
            "writable": self.writable,
            "detail": self.detail,
        }


def _segments(data: bytes):
    elf = ELFFile(io.BytesIO(data))
    for index, segment in enumerate(elf.iter_segments()):
        if segment["p_type"] != "PT_LOAD":
            continue
        yield index, segment


def map_va(data: bytes, va: int, *, require_executable: bool = False) -> AddressMapping:
    if va < 0:
        return AddressMapping(MappingStatus.OUTSIDE_PT_LOAD, va=va, detail="negative VA")
    matches: list[AddressMapping] = []
    for index, segment in _segments(data):
        p_vaddr = int(segment["p_vaddr"])
        p_filesz = int(segment["p_filesz"])
        p_memsz = int(segment["p_memsz"])
        p_offset = int(segment["p_offset"])
        p_align = int(segment["p_align"]) or 1
        flags = int(segment["p_flags"])
        executable = bool(flags & 0x1)
        writable = bool(flags & 0x2)
        base = dict(va=va, segment_index=index, p_offset=p_offset,
                    p_vaddr=p_vaddr, p_filesz=p_filesz, p_memsz=p_memsz,
                    p_align=p_align, executable=executable, writable=writable)
        if p_vaddr <= va < p_vaddr + p_filesz:
            if p_align > 1 and (p_offset - p_vaddr) % p_align:
                matches.append(AddressMapping(
                    MappingStatus.INVALID_ALIGNMENT,
                    detail=f"PT_LOAD[{index}] p_offset/p_vaddr violates p_align",
                    **base))
                continue
            if require_executable and not executable:
                continue
            matches.append(AddressMapping(
                MappingStatus.MAPPED_FILE_BACKED,
                file_offset=p_offset + (va - p_vaddr),
                detail=f"file-backed PT_LOAD[{index}]", **base))
        elif p_vaddr + p_filesz <= va < p_vaddr + p_memsz:
            if p_align > 1 and (p_offset - p_vaddr) % p_align:
                matches.append(AddressMapping(
                    MappingStatus.INVALID_ALIGNMENT,
                    detail=f"PT_LOAD[{index}] p_offset/p_vaddr violates p_align",
                    **base))
                continue
            matches.append(AddressMapping(
                MappingStatus.MAPPED_MEMORY_ONLY,
                detail=f"memory-only PT_LOAD[{index}] (NOBITS/bss range)", **base))
    if not matches:
        return AddressMapping(MappingStatus.OUTSIDE_PT_LOAD, va=va,
                              detail="VA is not covered by any PT_LOAD")
    if len(matches) > 1:
        return AddressMapping(MappingStatus.AMBIGUOUS_SEGMENT, va=va,
                              detail=f"{len(matches)} PT_LOAD records cover this VA")
    return matches[0]


def map_offset(data: bytes, offset: int) -> AddressMapping:
    if offset < 0 or offset >= len(data):
        return AddressMapping(MappingStatus.INVALID_FILE_RANGE,
                              file_offset=offset,
                              detail="file offset is outside the file")
    matches: list[AddressMapping] = []
    for index, segment in _segments(data):
        p_offset = int(segment["p_offset"])
        p_filesz = int(segment["p_filesz"])
        p_vaddr = int(segment["p_vaddr"])
        p_memsz = int(segment["p_memsz"])
        p_align = int(segment["p_align"]) or 1
        flags = int(segment["p_flags"])
        base = dict(file_offset=offset, segment_index=index, p_offset=p_offset,
                    p_vaddr=p_vaddr, p_filesz=p_filesz, p_memsz=p_memsz,
                    p_align=p_align, executable=bool(flags & 0x1),
                    writable=bool(flags & 0x2))
        if p_offset <= offset < p_offset + p_filesz:
            if p_align > 1 and (p_offset - p_vaddr) % p_align:
                matches.append(AddressMapping(
                    MappingStatus.INVALID_ALIGNMENT,
                    detail=f"PT_LOAD[{index}] p_offset/p_vaddr violates p_align",
                    **base))
                continue
            matches.append(AddressMapping(
                MappingStatus.MAPPED_FILE_BACKED,
                va=p_vaddr + (offset - p_offset),
                detail=f"file-backed PT_LOAD[{index}]", **base))
    if not matches:
        return AddressMapping(MappingStatus.OUTSIDE_PT_LOAD, file_offset=offset,
                              detail="file offset is not covered by a file-backed PT_LOAD")
    if len(matches) > 1:
        return AddressMapping(MappingStatus.AMBIGUOUS_SEGMENT, file_offset=offset,
                              detail=f"{len(matches)} PT_LOAD records cover this offset")
    return matches[0]


__all__ = ["MappingStatus", "AddressMapping", "map_va", "map_offset"]
