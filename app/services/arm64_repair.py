"""Direct AArch64 ELF byte repair for stack-bounded read/write immediates.

Capstone is used only to decode; the original instruction word is patched in
place.  No assembly text is reassembled.
"""
from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import asdict, dataclass, field
from typing import Any

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs
from elftools.elf.elffile import ELFFile

MD = Cs(CS_ARCH_ARM64, CS_MODE_ARM)


@dataclass
class Arm64Finding:
    kind: str
    address: str
    before: int
    after: int
    detail: str


@dataclass
class Arm64Report:
    original_sha256: str
    patched_sha256: str
    format: str
    arch: str
    backend: str
    strategy: str
    status: str
    capacity: int | None = None
    findings: list[Arm64Finding] = field(default_factory=list)
    offsets: list[int] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "findings": [asdict(x) for x in self.findings]}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _imm(text: str) -> int | None:
    value = text.split("#")[-1].strip()
    try:
        return int(value, 0)
    except ValueError:
        return None


def _movz_imm(word: int) -> int | None:
    # MOVZ/MOVN 32/64-bit: bits 28..23 are 101001/100101; immediate bits 20..5.
    if (word & 0x7F800000) not in (0x52800000, 0xD2800000,
                                   0x12800000, 0x92800000):
        return None
    return (word >> 5) & 0xFFFF


def _set_movz_imm(word: int, value: int) -> int:
    if not 0 <= value <= 0xFFFF:
        raise ValueError("ARM64 MOVZ immediate out of range")
    return (word & ~(0xFFFF << 5)) | ((value & 0xFFFF) << 5)


def scan_arm64(data: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"format": "unknown", "arch": "unknown",
                              "backend": "elf", "findings": []}
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return result
    try:
        elf = ELFFile(io.BytesIO(data))
        if elf.header["e_machine"] != "EM_AARCH64":
            return result
        text = elf.get_section_by_name(".text")
        if text is None:
            return result
        section_addr = int(text["sh_addr"])
        section_off = int(text["sh_offset"])
        result["format"] = "elf64-little"
        result["arch"] = "arm64"
        ins = list(MD.disasm(text.data(), section_addr))
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    capacity: int | None = None
    w2_imm: int | None = None
    w2_ins = None
    x8: int | None = None
    for item in ins:
        op = item.op_str.replace(" ", "")
        if item.mnemonic == "sub" and op.startswith("sp,sp,#"):
            value = _imm(item.op_str)
            if value and value > 0:
                capacity = value
        elif item.mnemonic == "mov" and op.startswith(("w2,#", "x2,#")):
            w2_imm = _imm(item.op_str)
            w2_ins = item
        elif item.mnemonic == "mov" and op.startswith(("w8,#", "x8,#")):
            x8 = _imm(item.op_str)
        elif item.mnemonic == "svc" and x8 in (63, 64) and capacity and w2_ins is not None:
            if w2_imm is not None and w2_imm > capacity:
                result["findings"].append({
                    "kind": "read_or_write_length", "address": hex(w2_ins.address),
                    "before": w2_imm, "after": capacity, "capacity": capacity,
                    "offset": section_off + (w2_ins.address - section_addr),
                    "patchable": True,
                    "detail": "AArch64 x2 immediate exceeds stack capacity",
                })
    seen = set()
    unique = []
    for item in result["findings"]:
        key = (item.get("kind"), item.get("address"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    result["findings"] = unique
    return result


def repair_arm64(data: bytes) -> tuple[bytes | None, Arm64Report]:
    report = Arm64Report(
        original_sha256=_sha(data), patched_sha256=_sha(data),
        format="unknown", arch="unknown", backend="elf", strategy="none",
        status="unsupported",
    )
    scan = scan_arm64(data)
    if scan.get("arch") != "arm64" or not scan.get("findings"):
        report.limitations.append("No supported AArch64 immediate read/write pattern.")
        return None, report
    report.format = scan["format"]
    report.arch = "arm64"
    report.capacity = int(scan["findings"][0]["capacity"])
    patched = bytearray(data)
    for item in scan["findings"]:
        if not item.get("patchable"):
            continue
        off = int(item["offset"])
        word = struct.unpack_from("<I", patched, off)[0]
        before = _movz_imm(word)
        if before is None or before != int(item["before"]):
            report.limitations.append("AArch64 MOVZ encoding check failed.")
            return None, report
        new_word = _set_movz_imm(word, int(item["after"]))
        struct.pack_into("<I", patched, off, new_word)
        report.findings.append(Arm64Finding(
            "read_or_write_length", item["address"], before, item["after"],
            "direct AArch64 MOVZ immediate rewrite",
        ))
        report.offsets.append(off)
    report.patched_sha256 = _sha(bytes(patched))
    report.strategy = "immediate"
    report.status = "patched"
    report.limitations.extend([
        "Direct AArch64 instruction-word patch; no assembly text round-trip.",
        "Static verification only unless an AArch64 guest is available.",
    ])
    return bytes(patched), report
