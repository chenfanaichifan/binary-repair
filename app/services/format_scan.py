"""PE/Mach-O metadata and import inventory (no execution, no patching yet)."""
from __future__ import annotations

import hashlib
from typing import Any

import lief


def _base(data: bytes) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "supported": False,
            "findings": [], "limits": []}


def scan_pe(data: bytes) -> dict[str, Any]:
    out = _base(data)
    try:
        pe = lief.PE.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    if pe is None:
        out["error"] = "not a PE"
        return out
    machine = str(getattr(pe.header, "machine", ""))
    out.update({
        "format": "pe", "arch": machine,
        "entrypoint": hex(int(pe.optional_header.addressof_entrypoint)),
        "imagebase": hex(int(pe.optional_header.imagebase)),
        "sections": [
            {"name": s.name, "va": hex(int(s.virtual_address)),
             "raw": hex(int(s.pointerto_raw_data)), "size": len(s.content)}
            for s in pe.sections
        ],
        "imports": [e.name for imp in pe.imports for e in imp.entries][:200],
        "relocations": len(list(pe.relocations)),
        "signatures": len(pe.signatures),
        "supported": False,
        "limits": ["PE repair is not enabled in this build; scan-only."],
    })
    return out


def scan_macho(data: bytes) -> dict[str, Any]:
    out = _base(data)
    try:
        binary = lief.MachO.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    if binary is None:
        out["error"] = "not a Mach-O"
        return out
    try:
        b = binary.at(0)
    except Exception:
        b = binary
    out.update({
        "format": "macho",
        "arch": str(getattr(b.header, "cpu_type", "")),
        "segments": [
            {"name": s.name, "va": hex(int(s.virtual_address)),
             "fileoff": int(s.file_offset), "filesize": int(s.file_size)}
            for s in b.segments
        ],
        "sections": [
            {"name": s.name, "segment": s.segment_name,
             "va": hex(int(s.virtual_address)), "size": int(s.size),
             "offset": int(s.offset)}
            for s in b.sections
        ],
        "supported": False,
        "limits": ["Mach-O repair is not enabled in this build; scan-only."],
    })
    return out
