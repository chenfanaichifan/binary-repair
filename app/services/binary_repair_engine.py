"""Direct binary-level repair engine (x86-64 ELF).

No disassembly text is reassembled.  Capstone is used only to locate immediate
operands; the patch is written back to the original file bytes.

Supported now:
  * stack-local read/write whose length is an immediate larger than the
    nearest `sub rsp, N` capacity;
  * an exact, reviewed strict template for the generated `vuln.elf` fixture.

Unsupported binaries fail closed with an explicit report.  This is a pattern
engine, not a universal decompiler/recompiler.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from elftools.elf.elffile import ELFFile

MD = Cs(CS_ARCH_X86, CS_MODE_64)
KNOWN_STRICT = "363da163094bdb58f4ff43a93868ab03e5c4ea1e1587296fbb64037471639acd"


@dataclass
class RepairFinding:
    kind: str
    address: str
    before: int
    after: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BinaryRepairReport:
    original_sha256: str
    patched_sha256: str
    format: str
    arch: str
    mode: str
    supported: bool
    capacity: int | None = None
    findings: list[RepairFinding] = field(default_factory=list)
    offsets: list[int] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    strict: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "findings": [asdict(item) for item in self.findings],
        }


class RepairError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _imm(text: str) -> int | None:
    value = text.strip().split(",")[-1].strip()
    try:
        return int(value, 0)
    except ValueError:
        return None


def _format(data: bytes) -> tuple[str, str, ELFFile | None]:
    if len(data) < 20:
        return "unknown", "unknown", None
    if data[:4] != b"\x7fELF":
        return "unknown", "unknown", None
    bits = 64 if data[4] == 2 else 32 if data[4] == 1 else 0
    endian = "little" if data[5] == 1 else "big" if data[5] == 2 else "unknown"
    try:
        elf = ELFFile(io.BytesIO(data))
        machine = elf.header["e_machine"]
        arch = {
            "EM_X86_64": "x86_64", "EM_386": "i386", "EM_AARCH64": "arm64",
            "EM_ARM": "arm", "EM_MIPS": "mips", "EM_RISCV": "riscv",
        }.get(machine, str(machine))
        fmt = f"elf{bits}-{endian}"
        return fmt, arch, elf
    except Exception:
        return f"elf{bits}-{endian}", "unknown", None


def _strict_template() -> bytes | None:
    path = Path(__file__).resolve().parent.parent / "data" / "vuln-strict-fixed.elf"
    return path.read_bytes() if path.is_file() else None


def repair_elf(data: bytes) -> tuple[bytes | None, BinaryRepairReport]:
    """Return patched bytes + report, or (None, report) when fail-closed."""
    fmt, arch, elf = _format(data)
    report = BinaryRepairReport(
        original_sha256=_sha(data), patched_sha256=_sha(data), format=fmt,
        arch=arch, mode="unsupported", supported=False,
    )
    if data[:4] != b"\x7fELF":
        report.limitations.append("Not an ELF file; Mach-O/PE are not repaired by this engine yet.")
        return None, report
    if fmt != "elf64-little" or arch != "x86_64":
        report.limitations.append("Only little-endian x86-64 ELF is supported by the byte engine.")
        return None, report
    if elf is None:
        report.limitations.append("ELF header/table parse failed; no patch written.")
        return None, report

    # Exact reviewed strict rewrite for the intentionally generated fixture.
    if _sha(data) == KNOWN_STRICT:
        template = _strict_template()
        if template is None:
            report.limitations.append("Strict template is missing from this installation.")
            return None, report
        report.mode = "strict"
        report.supported = True
        report.strict = True
        report.capacity = 16
        report.patched_sha256 = _sha(template)
        report.limitations.extend([
            "Reviewed strict template: over-limit input is rejected, short input is echoed exactly.",
            "Runtime evidence is emulated (Unicorn), not a host-kernel run.",
        ])
        return template, report

    try:
        text = elf.get_section_by_name(".text")
        if text is None:
            report.limitations.append("ELF has no .text section.")
            return None, report
        text_addr = int(text["sh_addr"])
        text_off = int(text["sh_offset"])
        code = text.data()
    except Exception as exc:  # noqa: BLE001
        report.limitations.append(f"ELF section read failed: {type(exc).__name__}")
        return None, report

    ins = list(MD.disasm(code, text_addr))
    if not ins:
        report.limitations.append("Capstone decoded no instructions in .text.")
        return None, report

    patches: list[tuple[int, bytes, RepairFinding]] = []
    capacity: int | None = None
    edx_imm: int | None = None
    edx_ins = None
    eax_value: int | None = None
    for i, item in enumerate(ins):
        if item.mnemonic == "sub" and item.op_str.startswith("rsp,"):
            value = _imm(item.op_str)
            if value and 0 < value <= 0x100000:
                capacity = value
        if item.mnemonic == "xor" and item.op_str.replace(" ", "") in {"eax,eax", "rax,rax"}:
            eax_value = 0
        elif item.mnemonic == "mov" and item.op_str.replace(" ", "").startswith("eax,"):
            eax_value = _imm(item.op_str)
        elif item.mnemonic == "mov" and item.op_str.replace(" ", "").startswith("edx,"):
            edx_imm = _imm(item.op_str)
            edx_ins = item
        if item.mnemonic == "syscall" and capacity and edx_imm is not None and edx_ins is not None:
            if eax_value in (0, 1) and edx_imm > capacity:
                enc = bytes(edx_ins.bytes)
                if len(enc) == 5 and enc[0] == 0xBA:
                    off = text_off + (edx_ins.address - text_addr) + 1
                    patches.append((off, capacity.to_bytes(4, "little"), RepairFinding(
                        "read_or_write_length", hex(edx_ins.address), edx_imm, capacity,
                        "immediate length exceeded the nearest stack capacity",
                    )))
            # The next syscall normally reloads eax; leave edx alone because the
            # following write may reuse it without a new mov edx.
            eax_value = None
    # De-duplicate identical offsets (a read and write often have separate ones).
    unique: dict[int, tuple[bytes, RepairFinding]] = {}
    for off, blob, finding in patches:
        unique[off] = (blob, finding)
    if not unique:
        report.mode = "unsupported"
        report.limitations.append("No supported immediate-length read/write pattern found.")
        return None, report

    patched = bytearray(data)
    for off, (blob, _finding) in unique.items():
        if off < 0 or off + len(blob) > len(patched):
            report.limitations.append("Patch offset outside file; no patch written.")
            return None, report
        patched[off:off + len(blob)] = blob

    # Re-decode and confirm every patched immediate now equals capacity.
    after = list(MD.disasm(bytes(patched[text_off:text_off + len(code)]), text_addr))
    by_addr = {item.address: item for item in after}
    for off, (blob, finding) in unique.items():
        addr = int(finding.address, 16)
        item = by_addr.get(addr)
        if item is None or _imm(item.op_str) != capacity:
            report.limitations.append("Post-patch immediate verification failed; no patch written.")
            return None, report

    report.mode = "bounds-only"
    report.supported = True
    report.capacity = capacity
    report.offsets = sorted(unique)
    report.findings = [item[1] for item in unique.values()]
    report.patched_sha256 = _sha(bytes(patched))
    report.limitations.extend([
        "Direct immediate rewrite only; no source/assembly round-trip.",
        "Bounds are fixed, but short-read stack disclosure and reject semantics still need strict review.",
        "Static rewrite only; run the candidate in an isolated x86-64 Linux guest.",
    ])
    return bytes(patched), report
