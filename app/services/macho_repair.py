"""Mach-O direct instruction repair (AArch64 immediate form).

Parsing is done with LIEF; writes are raw section bytes.  No code signature is
forged: any modification reports codesign_invalidated.
"""
from __future__ import annotations

import hashlib
import struct
import tempfile
from pathlib import Path
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
    section: str = ""
    section_va: int = 0
    section_offset: int = 0

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


def add_macho_rx_section(data: bytes, code: bytes, *, name: str = "__brfix") -> tuple[bytes | None, MachoReport]:
    """Add an executable section to __TEXT and reparse it with LIEF."""
    report = MachoReport(original_sha256=_sha(data), patched_sha256=_sha(data))
    try:
        binary = lief.MachO.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        report.limitations.append(f"Mach-O parse failed: {type(exc).__name__}")
        return None, report
    if binary is None:
        report.limitations.append("not a Mach-O image")
        return None, report
    try:
        b = binary.at(0)
        report.codesign_invalidated = bool(getattr(b, "has_code_signature", False))
        sec = lief.MachO.Section.create(name, list(code))
        if sec is None:
            report.limitations.append("LIEF could not create Mach-O section")
            return None, report
        b.add_section(sec)
        with tempfile.TemporaryDirectory(prefix="macho-repair-") as tmp:
            path = Path(tmp) / "out.macho"
            b.write(str(path))
            patched = path.read_bytes()
        check = lief.MachO.parse(list(patched))
        if check is None:
            report.limitations.append("LIEF could not reparse patched Mach-O")
            return None, report
        cb = check.at(0)
        found = next((x for x in cb.sections if x.name == name), None)
        if found is None:
            report.limitations.append("new Mach-O section missing after writeback")
            return None, report
        report.status = "written"
        report.strategy = "section"
        report.section = name
        report.section_va = int(found.virtual_address)
        report.section_offset = int(found.offset)
        report.patched_sha256 = _sha(patched)
        report.limitations.append("Static Mach-O section writeback; code signature is not forged.")
        return patched, report
    except Exception as exc:  # noqa: BLE001
        report.limitations.append(f"Mach-O section writeback failed: {type(exc).__name__}: {exc}")
        return None, report


def patch_macho_call_site(data: bytes, cave_code: bytes, *, call_va: int | None = None) -> tuple[bytes | None, MachoReport]:
    """Add a __brfix section and redirect one BL/E8 call to it."""
    patched, report = add_macho_rx_section(data, cave_code)
    if patched is None:
        return None, report
    try:
        binary = lief.MachO.parse(list(patched)).at(0)
        text = next((s for s in binary.sections if s.name == "__text"), None)
        if text is None:
            report.limitations.append("patched Mach-O has no __text")
            return None, report
        text_va = int(text.virtual_address)
        text_off = int(text.offset)
        code = bytes(text.content)
        if call_va is None:
            md = MD
            ins = next((x for x in md.disasm(code, text_va) if x.mnemonic in ("bl", "call")), None)
            if ins is None:
                report.limitations.append("no BL/E8 call found")
                return None, report
            call_va = ins.address
        off = text_off + (call_va - text_va)
        if off < 0 or off + 4 > len(patched):
            report.limitations.append("call site outside file")
            return None, report
        word = struct.unpack_from("<I", patched, off)[0]
        if (word & 0xFC000000) == 0x94000000:  # ARM64 BL
            imm = word & 0x03FFFFFF
            if imm & 0x02000000:
                imm -= 0x04000000
            old_target = call_va + imm * 4
            delta = int(report.section_va) - call_va
            if delta % 4 or not -(1 << 27) <= delta < (1 << 27):
                report.limitations.append("ARM64 BL target out of range/alignment")
                return None, report
            new_word = 0x94000000 | ((delta >> 2) & 0x03FFFFFF)
            out = bytearray(patched); struct.pack_into("<I", out, off, new_word)
            report.limitations.append(f"BL redirected from {hex(old_target)}")
        elif patched[off] == 0xE8:
            delta = int(report.section_va) - (call_va + 5)
            if not -(1 << 31) <= delta < (1 << 31):
                report.limitations.append("x86-64 E8 target out of range")
                return None, report
            out = bytearray(patched); out[off:off + 5] = b"\xE8" + struct.pack("<i", delta)
        else:
            report.limitations.append("call site is not ARM64 BL or E8")
            return None, report
        check = lief.MachO.parse(list(out))
        if check is None:
            report.limitations.append("patched Mach-O did not reparse")
            return None, report
        report.status = "patched"
        report.strategy = "call-cave"
        report.patched_sha256 = _sha(bytes(out))
        return bytes(out), report
    except Exception as exc:  # noqa: BLE001
        report.limitations.append(f"Mach-O call patch failed: {type(exc).__name__}: {exc}")
        return None, report
