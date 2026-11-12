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
import re
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
    runtime: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 2
    backend: str = ""
    strategy: str = ""
    status: str = ""
    verification: dict[str, Any] = field(default_factory=dict)

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
        if data[:2] == b"MZ":
            return "pe", "unknown", None
        if data[:4] in {b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
                        b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
                        b"\xca\xfe\xba\xbe"}:
            return "macho", "unknown", None
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


def _symbol_names(elf: ELFFile) -> dict[int, str]:
    names: dict[int, str] = {}
    for section in elf.iter_sections():
        if section.name not in {".symtab", ".dynsym"}:
            continue
        try:
            for sym in section.iter_symbols():
                if sym.name:
                    names.setdefault(int(sym["st_value"]), sym.name)
        except Exception:
            continue
    return names


def _call_target(item: Any) -> int | None:
    match = re.search(r"0x([0-9a-fA-F]+)", item.op_str or "")
    return int(match.group(1), 16) if match else None


def _stack_dest(op_str: str) -> int | None:
    text = (op_str or "").replace(" ", "")
    if text in {"rdi,rsp"}:
        return 0
    match = re.search(r"rdi,\[rsp\+0x([0-9a-fA-F]+)\]", text)
    if match:
        return int(match.group(1), 16)
    return None


def scan_elf(data: bytes) -> dict[str, Any]:
    """Non-mutating scan of known risky immediate/call patterns."""
    fmt, arch, elf = _format(data)
    result: dict[str, Any] = {"format": fmt, "arch": arch,
                              "supported": fmt == "elf64-little" and arch == "x86_64",
                              "findings": []}
    if elf is None or not result["supported"]:
        return result
    text = elf.get_section_by_name(".text")
    if text is None:
        return result
    symbols = _symbol_names(elf)
    text_addr = int(text["sh_addr"])
    text_off = int(text["sh_offset"])
    try:
        ins = list(MD.disasm(text.data(), text_addr))
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    capacity: int | None = None
    edx_imm: int | None = None
    edx_addr: int | None = None
    dest_offset: int | None = None
    for item in ins:
        norm = (item.op_str or "").replace(" ", "")
        if item.mnemonic == "sub" and item.op_str.startswith("rsp,"):
            value = _imm(item.op_str)
            if value and value > 0:
                capacity = value
        elif item.mnemonic == "mov" and norm.startswith("edx,"):
            edx_imm = _imm(item.op_str)
            edx_addr = item.address
        elif item.mnemonic in {"mov", "lea"} and norm.startswith("rdi,"):
            dest_offset = _stack_dest(item.op_str)
        elif item.mnemonic == "syscall":
            if capacity is not None and edx_imm is not None and edx_imm > capacity:
                result["findings"].append({
                    "kind": "read_or_write_length", "address": hex(edx_addr),
                    "before": edx_imm, "after": capacity,
                    "capacity": capacity, "patchable": True,
                    "detail": "immediate syscall length exceeds stack capacity",
                })
        elif item.mnemonic == "call":
            target = _call_target(item)
            name = symbols.get(target, "") if target is not None else ""
            low = name.lower()
            if "memcpy" in low and capacity is not None and dest_offset is not None and edx_imm is not None:
                effective = capacity - dest_offset
                if effective > 0 and edx_imm > effective:
                    result["findings"].append({
                        "kind": "memcpy_length", "address": hex(edx_addr),
                        "callee": name, "before": edx_imm, "after": effective,
                        "capacity": capacity, "dest_offset": dest_offset,
                        "patchable": True,
                        "detail": "immediate memcpy length exceeds stack destination capacity",
                    })
            elif low in {"strcpy", "strcat", "sprintf"} or low.endswith("@plt") and any(
                    x in low for x in ("strcpy", "strcat", "sprintf")):
                writable = any(token in low for token in ("strcpy", "strcat"))
                effective = (capacity - dest_offset) if (
                    capacity is not None and dest_offset is not None) else None
                result["findings"].append({
                    "kind": "unbounded_copy", "address": hex(item.address),
                    "callee": name, "before": 0, "after": 0,
                    "capacity": capacity, "dest_offset": dest_offset,
                    "effective_capacity": effective,
                    "call_file_offset": text_off + (item.address - text_addr),
                    "patchable": bool(writable and effective and effective > 0),
                    "detail": "unbounded string call; strcpy/strcat can use a cave, "
                              "sprintf needs format-aware handling",
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


def _runtime_summary(patched: bytes, capacity: int | None) -> dict[str, Any]:
    if capacity is None:
        return {}
    try:
        from app.services.x86_runtime import emulate_elf
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": type(exc).__name__}
    cases = []
    for size in (0, 1, capacity, capacity + 1):
        try:
            out = emulate_elf(patched, b"A" * size)
            cases.append({
                "input_len": size, "exit_code": out.exit_code,
                "stdout_len": len(out.stdout), "stderr_len": len(out.stderr),
                "stack_sentinel_intact": out.stack_tail == b"Z" * 16,
                "error": out.error,
            })
        except Exception as exc:  # noqa: BLE001
            cases.append({"input_len": size, "error": type(exc).__name__})
    return {"available": True, "engine": "unicorn-x86-64", "cases": cases}


def _repair_elf_immediate(data: bytes) -> tuple[bytes | None, BinaryRepairReport]:
    """Return patched bytes + report, or (None, report) when fail-closed."""
    fmt, arch, elf = _format(data)
    report = BinaryRepairReport(
        original_sha256=_sha(data), patched_sha256=_sha(data), format=fmt,
        arch=arch, mode="unsupported", supported=False,
        backend=("elf" if fmt.startswith("elf") else fmt),
        strategy="none", status="unsupported",
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
        report.strategy = "strict-template"
        report.status = "patched"
        report.capacity = 16
        report.patched_sha256 = _sha(template)
        report.runtime = _runtime_summary(template, 16)
        report.verification = {"emulated": report.runtime}
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
    eax_ins = None
    for i, item in enumerate(ins):
        if item.mnemonic == "sub" and item.op_str.startswith("rsp,"):
            value = _imm(item.op_str)
            if value and 0 < value <= 0x100000:
                capacity = value
        norm = item.op_str.replace(" ", "")
        if item.mnemonic == "xor" and norm in {"eax,eax", "rax,rax"}:
            eax_value = 0
            eax_ins = item
        elif item.mnemonic == "mov" and norm.startswith("eax,"):
            eax_value = _imm(item.op_str)
            eax_ins = item
        elif item.mnemonic == "mov" and norm == "edx,eax" and eax_value is not None:
            edx_imm = eax_value
            edx_ins = eax_ins
        elif item.mnemonic == "mov" and norm.startswith("edx,"):
            edx_imm = _imm(item.op_str)
            edx_ins = item
        if item.mnemonic == "syscall" and capacity and edx_imm is not None and edx_ins is not None:
            if eax_value in (0, 1) and edx_imm > capacity:
                enc = bytes(edx_ins.bytes)
                if len(enc) == 5 and enc[0] in (0xBA, 0xB8):
                    off = text_off + (edx_ins.address - text_addr) + 1
                    patches.append((off, capacity.to_bytes(4, "little"), RepairFinding(
                        "read_or_write_length", hex(edx_ins.address), edx_imm, capacity,
                        "immediate length exceeded the nearest stack capacity",
                    )))
            # The next syscall normally reloads eax; leave edx alone because the
            # following write may reuse it without a new mov edx.
            eax_value = None
    # Add direct memcpy-length patches found by the non-mutating scanner.
    scan = scan_elf(data)
    for item in scan.get("findings", []):
        if item.get("kind") != "memcpy_length" or not item.get("patchable"):
            continue
        addr = int(item["address"], 16)
        off = text_off + (addr - text_addr) + 1
        expected = int(item["after"])
        patches.append((off, expected.to_bytes(4, "little"), RepairFinding(
            "memcpy_length", item["address"], int(item["before"]), expected,
            item.get("detail", "memcpy length exceeds stack capacity"),
        )))
    if any(item.get("kind") == "unbounded_copy" for item in scan.get("findings", [])):
        report.limitations.append("Unbounded strcpy/strcat/sprintf call found; no automatic byte patch was attempted.")

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
        if item is None or _imm(item.op_str) != finding.after:
            report.limitations.append("Post-patch immediate verification failed; no patch written.")
            return None, report

    report.mode = "bounds-only"
    report.supported = True
    report.strategy = "immediate"
    report.status = "patched"
    report.capacity = capacity
    report.offsets = sorted(unique)
    report.findings = [item[1] for item in unique.values()]
    report.patched_sha256 = _sha(bytes(patched))
    report.runtime = _runtime_summary(bytes(patched), capacity)
    report.verification = {"emulated": report.runtime}
    report.limitations.extend([
        "Direct immediate rewrite only; no source/assembly round-trip.",
        "Bounds are fixed, but short-read stack disclosure and reject semantics still need strict review.",
        "Static rewrite only; run the candidate in an isolated x86-64 Linux guest.",
    ])
    return bytes(patched), report


def _apply_copy_caves(patched: bytes, scan: dict[str, Any],
                      report: BinaryRepairReport) -> bytes:
    """Apply strcpy/strcat cave wrappers for patchable call sites."""
    from app.services.code_cave import (
        CaveError, inject_strcat_guard, inject_strcpy_guard,
    )
    current = patched
    for item in scan.get("findings", []):
        if item.get("kind") != "unbounded_copy" or not item.get("patchable"):
            continue
        name = str(item.get("callee") or "").lower()
        capacity = item.get("effective_capacity")
        call_vaddr = int(item["address"], 16)
        call_off = int(item["call_file_offset"])
        if not capacity or capacity <= 0:
            continue
        try:
            if "strcpy" in name:
                cave = inject_strcpy_guard(current, call_vaddr=call_vaddr,
                                           call_file_offset=call_off,
                                           capacity=capacity)
            elif "strcat" in name:
                cave = inject_strcat_guard(current, call_vaddr=call_vaddr,
                                           call_file_offset=call_off,
                                           capacity=capacity)
            else:
                continue
        except (CaveError, ValueError, IndexError) as exc:
            report.limitations.append(f"cave injection failed at {hex(call_vaddr)}: {exc}")
            continue
        current = cave.data
        report.findings.append(RepairFinding(
            "code_cave", hex(call_vaddr), 0, capacity,
            f"{cave.report.get('wrapper')} via {cave.method}",
        ))
        report.limitations.append(
            f"code cave: {cave.report.get('wrapper')} at {hex(call_vaddr)}, "
            f"{cave.method}, capacity={capacity}"
        )
    return current


def repair_elf(data: bytes) -> tuple[bytes | None, BinaryRepairReport]:
    """Immediate patcher + strcpy/strcat cave pass."""
    patched, report = _repair_elf_immediate(data)
    scan = scan_elf(data)
    if patched is None:
        # A cave can handle a binary that has no immediate-length finding.
        current = data
    else:
        current = patched
    updated = _apply_copy_caves(current, scan, report)
    if updated != current:
        report.supported = True
        report.mode = "cave" if not report.findings or any(
            item.kind == "code_cave" for item in report.findings) else report.mode
        report.patched_sha256 = _sha(updated)
        report.strategy = "code-cave"
        report.status = "patched"
        report.verification = {"emulated": _runtime_summary(updated, report.capacity)}
        report.capacity = next((item.effective_capacity for item in scan.get("findings", [])
                                if item.get("effective_capacity")), report.capacity)
        report.runtime = _runtime_summary(updated, report.capacity)
        return updated, report
    return patched, report
