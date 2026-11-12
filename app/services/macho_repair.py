"""Mach-O direct instruction repair (AArch64 immediate form).

Parsing is done with LIEF; writes are raw section bytes.  No code signature is
forged: any modification reports codesign_invalidated.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import asdict, dataclass, field
from typing import Any

import lief
from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs

MD = Cs(CS_ARCH_ARM64, CS_MODE_ARM)


@dataclass
class MachoReport:
    original_sha256: str
    patched_sha256: str
    format: str = "macho"
    arch: str = "arm64"
    status: str = "unsupported"
    strategy: str = "immediate"
    capacity: int | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    offsets: list[int] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    codesign_invalidated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _imm(text: str) -> int | None:
    value = text.split("#")[-1].strip()
    try:
        return int(value, 0)
    except ValueError:
        return None


def _movz_imm(word: int) -> int | None:
    if (word & 0x7F800000) not in (0x52800000, 0xD2800000,
                                   0x12800000, 0x92800000):
        return None
    return (word >> 5) & 0xFFFF


def _set_movz_imm(word: int, value: int) -> int:
    if not 0 <= value <= 0xFFFF:
        raise ValueError("MOVZ immediate out of range")
    return (word & ~(0xFFFF << 5)) | ((value & 0xFFFF) << 5)


def _slice(data: bytes) -> tuple[lief.MachO.Binary, Any] | None:
    try:
        binary = lief.MachO.parse(list(data))
    except Exception:
        return None
    if binary is None:
        return None
    try:
        b = binary.at(0)
    except Exception:
        return None
    text = next((s for s in b.sections
                 if s.name == "__text" and s.segment_name == "__TEXT"), None)
    if text is None:
        return None
    return b, text


def scan_macho(data: bytes) -> dict[str, Any]:
    parsed = _slice(data)
    if parsed is None:
        return {"format": "macho", "arch": "unknown", "findings": []}
    b, text = parsed
    section_va = int(text.virtual_address)
    section_off = int(text.offset)
    content = bytes(text.content)
    findings = []
    capacity = None
    w2 = None
    w2_ins = None
    x8 = None
    for item in MD.disasm(content, section_va):
        op = item.op_str.replace(" ", "")
        if item.mnemonic == "sub" and op.startswith("sp,sp,#"):
            capacity = _imm(item.op_str)
        elif item.mnemonic == "mov" and op.startswith(("w2,#", "x2,#")):
            w2 = _imm(item.op_str)
            w2_ins = item
        elif item.mnemonic == "mov" and op.startswith(("w8,#", "x8,#")):
            x8 = _imm(item.op_str)
        elif item.mnemonic == "svc" and x8 in (63, 64) and capacity and w2_ins and w2 is not None:
            if w2 > capacity:
                findings.append({
                    "kind": "read_or_write_length", "address": hex(w2_ins.address),
                    "before": w2, "after": capacity, "capacity": capacity,
                    "offset": section_off + (w2_ins.address - section_va),
                    "patchable": True,
                    "detail": "AArch64 MOVZ immediate exceeds stack capacity",
                })
    seen = set()
    unique = []
    for item in findings:
        key = (item["kind"], item["address"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return {"format": "macho", "arch": "arm64", "findings": unique}


def repair_macho(data: bytes) -> tuple[bytes | None, MachoReport]:
    report = MachoReport(original_sha256=_sha(data), patched_sha256=_sha(data))
    scan = scan_macho(data)
    if not scan.get("findings"):
        report.limitations.append("No supported Mach-O immediate read/write pattern.")
        return None, report
    parsed = _slice(data)
    if parsed is None:
        report.limitations.append("Mach-O parse failed.")
        return None, report
    b, text = parsed
    report.codesign_invalidated = bool(getattr(b, "has_code_signature", False))
    patched = bytearray(data)
    for item in scan["findings"]:
        if not item.get("patchable"):
            continue
        off = int(item["offset"])
        word = struct.unpack_from("<I", patched, off)[0]
        before = _movz_imm(word)
        if before is None or before != int(item["before"]):
            report.limitations.append("MOVZ encoding check failed.")
            return None, report
        struct.pack_into("<I", patched, off, _set_movz_imm(word, int(item["after"])))
        report.findings.append(dict(item))
        report.offsets.append(off)
    report.patched_sha256 = _sha(bytes(patched))
    report.capacity = int(scan["findings"][0]["capacity"])
    report.status = "patched"
    report.limitations.extend([
        "Direct Mach-O section byte patch; no assembly text round-trip.",
        "Code signature is not forged; modification invalidates it.",
    ])
    return bytes(patched), report
