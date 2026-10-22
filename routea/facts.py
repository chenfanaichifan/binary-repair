"""ELF fact extraction for the independent Route A gate-3 audit.

Read-only helpers built on pyelftools. They return JSON-serialisable facts and
never modify a binary. Header enum fields are kept **as pyelftools returns them**
(strings such as ``ELFCLASS64`` / ``EV_CURRENT``): converting them with ``int()``
crashes on pyelftools 0.33 (review finding B3), so comparisons use the raw values.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import struct
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

PT_LOAD = 1


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def program_headers(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("rb") as fh:
        elf = ELFFile(fh)
        for index in range(elf.num_segments()):
            seg = elf.get_segment(index)
            out.append(
                {
                    "index": index,
                    "type": seg["p_type"],
                    "flags": int(seg["p_flags"]),
                    "offset": int(seg["p_offset"]),
                    "vaddr": int(seg["p_vaddr"]),
                    "paddr": int(seg["p_paddr"]),
                    "filesz": int(seg["p_filesz"]),
                    "memsz": int(seg["p_memsz"]),
                    "align": int(seg["p_align"]),
                }
            )
    return out


def header_fields(path: Path) -> dict[str, Any]:
    """Raw ELF header fields; enum values stay as pyelftools strings."""
    with path.open("rb") as fh:
        elf = ELFFile(fh)
        header = elf.header
        return {
            "e_ident_class": header["e_ident"]["EI_CLASS"],
            "e_ident_data": header["e_ident"]["EI_DATA"],
            "e_type": header["e_type"],
            "e_machine": header["e_machine"],
            "e_version": header["e_version"],
            "e_entry": int(header["e_entry"]),
            "e_phoff": int(header["e_phoff"]),
            "e_shoff": int(header["e_shoff"]),
            "e_flags": int(header["e_flags"]),
            "e_ehsize": int(header["e_ehsize"]),
            "e_phentsize": int(header["e_phentsize"]),
            "e_phnum": int(header["e_phnum"]),
            "e_shentsize": int(header["e_shentsize"]),
            "e_shnum": int(header["e_shnum"]),
            "e_shstrndx": int(header["e_shstrndx"]),
        }


def table_bytes(path: Path, *, kind: str) -> bytes:
    raw = path.read_bytes()
    fields = header_fields(path)
    if kind == "program":
        start, count, size = fields["e_phoff"], fields["e_phnum"], fields["e_phentsize"]
    elif kind == "section":
        start, count, size = fields["e_shoff"], fields["e_shnum"], fields["e_shentsize"]
    else:  # pragma: no cover
        raise ValueError(f"unknown table kind: {kind!r}")
    return raw[start : start + count * size]


def section_headers(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("rb") as fh:
        elf = ELFFile(fh)
        for index, sec in enumerate(elf.iter_sections()):
            flags = int(sec["sh_flags"])
            out.append(
                {
                    "index": index,
                    "name": sec.name,
                    "type": sec["sh_type"],
                    "flags": flags,
                    "alloc": bool(flags & 0x2),
                    "exec": bool(flags & 0x4),
                    "addr": int(sec["sh_addr"]),
                    "offset": int(sec["sh_offset"]),
                    "size": int(sec["sh_size"]),
                }
            )
    return out


def symbols(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("rb") as fh:
        elf = ELFFile(fh)
        for sec in elf.iter_sections():
            if not isinstance(sec, SymbolTableSection):
                continue
            for sym in sec.iter_symbols():
                if not sym.name:
                    continue
                out.append(
                    {
                        "name": sym.name,
                        "value": int(sym["st_value"]),
                        "size": int(sym["st_size"]),
                        "type": sym["st_info"]["type"],
                        "bind": sym["st_info"]["bind"],
                        "section": sec.name,
                    }
                )
    return out


def relocations(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("rb") as fh:
        elf = ELFFile(fh)
        for sec in elf.iter_sections():
            if sec["sh_type"] not in ("SHT_RELA", "SHT_REL"):
                continue
            for rel in sec.iter_relocations():
                out.append(
                    {
                        "section": sec.name,
                        "offset": int(rel["r_offset"]),
                        "type": int(rel["r_info_type"]),
                    }
                )
    return out


def dynamic_entries(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("rb") as fh:
        elf = ELFFile(fh)
        sec = elf.get_section_by_name(".dynamic")
        if sec is None:
            return out
        for tag in sec.iter_tags():
            raw = tag.entry.get("d_val", tag.entry.get("d_ptr", 0))
            out.append({"tag": str(tag.entry["d_tag"]),
                        "value": raw if isinstance(raw, int) else str(raw)})
    return out


def section_content_sha256(path: Path, name: str) -> str | None:
    with path.open("rb") as fh:
        elf = ELFFile(fh)
        sec = elf.get_section_by_name(name)
        if sec is None:
            return None
        return sha256_bytes(sec.data())


X86_FEATURE_PROPERTY = 0xC0000002


def cet_report(path: Path) -> dict[str, Any]:
    """Compile-time CET property note (not runtime enforcement)."""
    try:
        with path.open("rb") as fh:
            elf = ELFFile(fh)
            for seg in elf.iter_segments():
                if seg["p_type"] != "PT_NOTE":
                    continue
                for note in seg.iter_notes():
                    if note["n_type"] != "NT_GNU_PROPERTY_TYPE_0":
                        continue
                    desc = note["n_desc"]
                    if not isinstance(desc, (bytes, bytearray)):
                        continue
                    offset = 0
                    while offset + 8 <= len(desc):
                        prop_type, prop_size = struct.unpack_from("<II", desc, offset)
                        offset += 8
                        data = bytes(desc[offset : offset + prop_size])
                        offset += prop_size
                        if prop_type == X86_FEATURE_PROPERTY and len(data) >= 4:
                            bits = struct.unpack_from("<I", data, 0)[0]
                            return {
                                "available": True,
                                "ibt": bool(bits & 1),
                                "shstk": bool(bits & 2),
                                "raw_feature_bits": hex(bits),
                                "note": "compile-time GNU property; runtime enforcement unverified",
                            }
        return {"available": False, "reason": "no x86 feature property note"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"available": False, "reason": f"note parse failed: {exc}"}


def tools_report() -> dict[str, str]:
    def version(dist: str) -> str:
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            return "not_installed"

    return {
        "python": platform.python_version(),
        "pyelftools": version("pyelftools"),
        "capstone": version("capstone"),
        "lief": version("lief"),
        "platform": platform.platform(),
    }


def elf_facts(path: Path) -> dict[str, Any]:
    return {
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "header": header_fields(path),
        "program_headers": program_headers(path),
        "program_header_table_sha256": sha256_bytes(table_bytes(path, kind="program")),
        "section_headers": section_headers(path),
        "section_header_table_sha256": sha256_bytes(table_bytes(path, kind="section")),
        "symbols": symbols(path),
        "relocations": relocations(path),
        "dynamic": dynamic_entries(path),
        "cet": cet_report(path),
        "section_content_sha256": {
            name: section_content_sha256(path, name)
            for name in (
                ".dynamic", ".dynsym", ".dynstr", ".rela.dyn", ".rela.plt",
                ".rel.dyn", ".rel.plt", ".got", ".got.plt", ".plt", ".plt.sec",
                ".init", ".fini", ".rodata", ".data", ".bss",
            )
        },
    }
