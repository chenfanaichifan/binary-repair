"""Architecture-neutral sink analysis for stack-buffer copies.

The analyzer decodes the executable section of an already-parsed container and
produces :class:`Sink` records.  It never writes or executes bytes.

Frame model (documented limitation: this is frame geometry, not DWARF object
size):

* x86-64: ``sub rsp, N`` sets ``frame_top = rsp_before``; a ``push rbp`` /
  ``mov rbp, rsp`` prologue sets ``frame_top = rbp``.
* AArch64: ``sub sp, sp, #N`` sets ``frame_top = sp_before``.
* destination addresses come from ``lea rdi/rcx, [rsp/rbp ± K]``,
  ``mov reg, rsp`` and ``add x0, sp, #K``.
* ``capacity = frame_top - destination``.

A sink is only marked patchable when the capacity is positive, bounded and the
callee is a known copy function.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from capstone import CS_ARCH_ARM64, CS_ARCH_X86, CS_MODE_64, CS_MODE_ARM, Cs
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from app.services.containers import ContainerInfo, detect_container, resolve_target

MAX_CAPACITY = 1 << 20
COPY_TOKENS = ("strcpy", "strcat", "stpcpy", "memcpy", "memmove",
               "__memcpy_chk", "__strcpy_chk", "__strcat_chk")

_MD_X86 = Cs(CS_ARCH_X86, CS_MODE_64)
_MD_X86.detail = True
_MD_ARM64 = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
_MD_ARM64.detail = True


@dataclass
class Sink:
    kind: str
    arch: str
    function_va: int = 0
    call_va: int | None = None
    callee: str = ""
    capacity: int | None = None
    dest_rel: int | None = None
    length: int | None = None
    length_offset: int | None = None
    length_width: int = 0
    call_offset: int | None = None
    call_size: int = 0
    patchable: bool = False
    confidence: str = "medium"
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Analysis:
    container: ContainerInfo
    sinks: list[Sink] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def patchable(self) -> list[Sink]:
        return [sink for sink in self.sinks if sink.patchable]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.container.format,
            "arch": self.container.arch,
            "bits": self.container.bits,
            "sinks": [sink.to_dict() for sink in self.sinks],
            "limitations": list(self.limitations),
        }


def _copy_name(name: str | None) -> str | None:
    if not name:
        return None
    low = name.lower().split("@")[0]
    short = low.rsplit(".", 1)[-1].lstrip("_")
    for token in COPY_TOKENS:
        if short == token or short.endswith("!" + token) or token in short:
            return short
    return None


def _text_section(container: ContainerInfo):
    preferred = {".text", "__text", "text"}
    for section in container.sections:
        if section.executable and section.name in preferred and section.size:
            return section
    return container.executable_section()


def analyze(data: bytes) -> Analysis:
    container = detect_container(data)
    analysis = Analysis(container=container, limitations=list(container.limitations))
    if not analysis.limitations:
        analysis.limitations = []
    if container.format == "unknown":
        return analysis
    text = _text_section(container)
    if text is None:
        analysis.limitations.append("no executable section; nothing to analyze")
        return analysis
    if text.offset + text.size > len(data):
        analysis.limitations.append("executable section extends past EOF")
        return analysis
    code = data[text.offset:text.offset + text.size]
    try:
        if container.arch == "x86_64":
            _scan_x86_64(analysis, container, text, code)
        elif container.arch == "arm64":
            _scan_arm64(analysis, container, text, code)
        else:
            analysis.limitations.append(
                f"no analyzer for {container.format}/{container.arch}"
            )
    except Exception as exc:  # noqa: BLE001
        analysis.limitations.append(f"analysis failed: {type(exc).__name__}: {exc}")
    if not analysis.patchable():
        analysis.limitations.append(
            "no patchable copy sink with a recoverable capacity was found"
        )
    return analysis


def _imm32_offset(ins: Any) -> int | None:
    raw = bytes(ins.bytes)
    if len(raw) == 5 and raw[0] in (0xB8, 0xBA):
        return 1
    if len(raw) == 6 and raw[0] == 0x41 and raw[1] in (0xB8, 0xBA):
        return 2
    return None


def _x86_mem_target(ins: Any, operand: Any) -> int | None:
    if operand.type != X86_OP_MEM or operand.mem.base != 41:  # X86_REG_RIP == 41?
        return None
    return ins.address + ins.size + operand.mem.disp


def _scan_x86_64(analysis: Analysis, container: ContainerInfo, text, code: bytes) -> None:
    sysv = container.format != "pe"
    dest_reg = "rdi" if sysv else "rcx"
    rsp_rel = 0
    rbp_rel: int | None = None
    frame_top: int | None = 0
    frame_start: int | None = None
    dest: dict[str, int] = {}
    length: int | None = None
    length_off: int | None = None
    eax_imm: int | None = None
    eax_off: int | None = None

    for ins in _MD_X86.disasm(code, text.va):
        op = (ins.op_str or "").replace(" ", "")
        mnemonic = ins.mnemonic
        if mnemonic == "ret":
            rsp_rel, rbp_rel, frame_top, frame_start = 0, None, 0, None
            dest.clear()
            length = length_off = eax_imm = eax_off = None
            continue
        if mnemonic == "push":
            value = 8 if op in {"rbp", "rsp", "rax", "rcx", "rdx", "rbx",
                                "rsi", "rdi", "r8", "r9", "r10", "r11",
                                "r12", "r13", "r14", "r15"} else 0
            rsp_rel -= value
            if op == "rbp" and frame_start is None:
                frame_start = ins.address
            continue
        if mnemonic == "pop":
            rsp_rel += 8
            continue
        if mnemonic == "leave":
            rsp_rel = rbp_rel if rbp_rel is not None else rsp_rel
            rbp_rel, frame_top = None, 0
            continue
        if mnemonic == "sub" and op.startswith("rsp,"):
            imm = ins.operands[-1].imm if ins.operands else 0
            if imm and 0 < imm <= MAX_CAPACITY:
                if frame_start is None:
                    frame_start = ins.address
                rsp_rel -= imm
                if rbp_rel is None:
                    frame_top = rsp_rel + imm
            continue
        if mnemonic == "add" and op.startswith("rsp,"):
            imm = ins.operands[-1].imm if ins.operands else 0
            rsp_rel += imm or 0
            continue
        if mnemonic == "mov" and op == "rbp,rsp":
            rbp_rel = rsp_rel
            frame_top = rbp_rel
            if frame_start is None:
                frame_start = ins.address
            continue
        if mnemonic == "lea" and len(ins.operands) == 2 and ins.operands[0].type == X86_OP_REG:
            reg = ins.reg_name(ins.operands[0].reg)
            mem = ins.operands[1]
            if mem.type == X86_OP_MEM and reg in {"rdi", "rcx", "rdx", "rsi", "r8", "r9", "x0"}:
                base = ins.reg_name(mem.mem.base) if mem.mem.base else ""
                if base == "rsp":
                    dest[reg] = rsp_rel + mem.mem.disp
                elif base == "rbp" and rbp_rel is not None:
                    dest[reg] = rbp_rel + mem.mem.disp
            continue
        if mnemonic == "mov" and len(ins.operands) == 2:
            dst, src = ins.operands
            if dst.type == X86_OP_REG and src.type == X86_OP_REG:
                left = ins.reg_name(dst.reg)
                right = ins.reg_name(src.reg)
                if left in {"rdi", "rcx", "rsi", "rdx"} and right == "rsp":
                    dest[left] = rsp_rel
                elif left == "edx" and right == "eax" and eax_imm is not None:
                    length, length_off = eax_imm, eax_off
                continue
            if dst.type == X86_OP_REG and src.type == X86_OP_IMM:
                reg = ins.reg_name(dst.reg)
                value = int(src.imm)
                if reg in {"edx", "r8d", "rdx", "r8"}:
                    offset = _imm32_offset(ins)
                    if offset is not None:
                        length = value
                        length_off = text.offset + (ins.address - text.va) + offset
                elif reg in {"eax", "rax"}:
                    offset = _imm32_offset(ins)
                    if offset is not None:
                        eax_imm = value
                        eax_off = text.offset + (ins.address - text.va) + offset
                continue
            continue
        if mnemonic == "syscall":
            if length is not None and length_off is not None and frame_top is not None:
                dest_rel = dest.get("rsi", dest.get(dest_reg))
                if dest_rel is not None:
                    capacity = frame_top - dest_rel
                    if 0 < capacity <= MAX_CAPACITY and length > capacity:
                        _emit_immediate(analysis, container, text, ins, "syscall_length",
                                        "syscall read/write", length, length_off, capacity,
                                        frame_start, detail="immediate syscall length exceeds stack capacity")
            length = length_off = None
            continue
        if mnemonic != "call":
            continue
        name = None
        if ins.operands:
            operand = ins.operands[0]
            if operand.type == X86_OP_IMM:
                name = resolve_target(container, int(operand.imm))
            elif operand.type == X86_OP_MEM and operand.mem.base:
                base = ins.reg_name(operand.mem.base)
                if base == "rip":
                    iat = ins.address + ins.size + operand.mem.disp
                    name = container.imports.get(iat)
        copy = _copy_name(name)
        if copy is None:
            length = length_off = None
            continue
        dest_rel = dest.get(dest_reg)
        capacity = frame_top - dest_rel if (frame_top is not None and dest_rel is not None) else None
        call_off = text.offset + (ins.address - text.va)
        if "_chk" in copy or copy.endswith("_chk"):
            size = None
            if len(ins.operands) >= 1:
                pass
            # SysV __*_chk: dst, src, len, dst_size -> 4th arg rcx (immediate in
            # the common clang pattern).  Win64 has no __chk family here.
            size_reg = "rcx" if sysv else None
            size = dest.get("_size_" + size_reg) if size_reg else None
            if size is None and length is not None:
                size = _lookback_imm(code, text, ins.address, "rcx", container)
            if size is not None and length is not None and length > size:
                _emit_immediate(analysis, container, text, ins, "checked_copy",
                                copy, length, length_off, size, frame_start,
                                detail=f"checked copy length exceeds explicit destination size {size}",
                                confidence="high")
            length = length_off = None
            continue
        if copy in {"memcpy", "memmove"}:
            if length is not None and length_off is not None and capacity is not None:
                if 0 < capacity <= MAX_CAPACITY and length > capacity:
                    _emit_immediate(analysis, container, text, ins, "memcpy_length",
                                    copy, length, length_off, capacity, frame_start,
                                    detail="immediate copy length exceeds stack capacity")
            length = length_off = None
            continue
        if copy in {"strcpy", "strcat", "stpcpy"}:
            if capacity is not None and 0 < capacity <= MAX_CAPACITY:
                analysis.sinks.append(Sink(
                    kind="unbounded_copy",
                    arch=container.arch,
                    function_va=frame_start or 0,
                    call_va=ins.address,
                    callee=copy,
                    capacity=capacity,
                    dest_rel=dest_rel,
                    call_offset=call_off,
                    call_size=ins.size,
                    patchable=True,
                    confidence="medium",
                    detail=f"{copy} into stack destination bounded to {capacity} bytes",
                ))
            length = length_off = None
        continue


def _lookback_imm(code: bytes, text, call_va: int, reg: str, container: ContainerInfo) -> int | None:
    """Best-effort: find the last ``mov reg, imm`` before a call."""
    target = {"rcx": "rcx", "rdx": "rdx"}.get(reg)
    if target is None:
        return None
    last = None
    for ins in _MD_X86.disasm(code, text.va):
        if ins.address >= call_va:
            break
        if ins.mnemonic == "mov" and ins.operands and ins.operands[0].type == X86_OP_REG:
            if ins.reg_name(ins.operands[0].reg) in {target, "e" + target[1:]}:
                if len(ins.operands) == 2 and ins.operands[1].type == X86_OP_IMM:
                    last = int(ins.operands[1].imm)
    return last


def _emit_immediate(analysis: Analysis, container: ContainerInfo, text, ins, kind: str,
                    callee: str, length: int, length_off: int | None, capacity: int,
                    frame_start: int | None, *, detail: str, confidence: str = "medium") -> None:
    if length_off is None or length <= capacity:
        return
    analysis.sinks.append(Sink(
        kind=kind,
        arch=container.arch,
        function_va=frame_start or 0,
        call_va=ins.address,
        callee=callee,
        capacity=capacity,
        length=length,
        length_offset=length_off,
        length_width=4,
        call_offset=text.offset + (ins.address - text.va),
        call_size=ins.size,
        patchable=True,
        confidence=confidence,
        detail=detail,
    ))


def _scan_arm64(analysis: Analysis, container: ContainerInfo, text, code: bytes) -> None:
    sp_rel = 0
    frame_top: int | None = 0
    frame_start: int | None = None
    dest: dict[str, int] = {}
    length: int | None = None
    length_off: int | None = None
    size: int | None = None

    for ins in _MD_ARM64.disasm(code, text.va):
        op = (ins.op_str or "").replace(" ", "")
        mnemonic = ins.mnemonic
        if mnemonic == "ret":
            sp_rel, frame_top, frame_start = 0, 0, None
            dest.clear()
            length = length_off = size = None
            continue
        if mnemonic in {"sub", "add"} and op.startswith("sp,sp,"):
            value = ins.operands[-1].imm if ins.operands else 0
            value = int(value or 0)
            if mnemonic == "sub":
                if frame_start is None:
                    frame_start = ins.address
                sp_rel -= value
                if frame_top is None:
                    frame_top = sp_rel + value
            else:
                sp_rel += value
            continue
        if mnemonic == "mov" and len(ins.operands) == 2:
            dst = ins.operands[0]
            src = ins.operands[1]
            if dst.type == ARM64_OP_REG and src.type == ARM64_OP_REG:
                left = ins.reg_name(dst.reg)
                right = ins.reg_name(src.reg)
                if left in {"x0", "w0"} and right == "sp":
                    dest["x0"] = sp_rel
                continue
            if dst.type == ARM64_OP_REG and src.type == ARM64_OP_IMM:
                reg = ins.reg_name(dst.reg)
                value = int(src.imm)
                if reg in {"x2", "w2"}:
                    length = value
                    length_off = text.offset + (ins.address - text.va)
                elif reg in {"x3", "w3"}:
                    size = value
                continue
            continue
        if mnemonic == "add" and len(ins.operands) == 3:
            dst, src, imm = ins.operands
            if (dst.type == ARM64_OP_REG and src.type == ARM64_OP_REG
                    and imm.type == ARM64_OP_IMM):
                left = ins.reg_name(dst.reg)
                right = ins.reg_name(src.reg)
                if left in {"x0", "w0"} and right == "sp":
                    dest["x0"] = sp_rel + int(imm.imm)
                elif left in {"x2", "w2"} and right in {"x0", "w0"} and 0 not in dest:
                    pass
            continue
        if mnemonic != "bl":
            continue
        target = int(ins.operands[0].imm) if ins.operands and ins.operands[0].type == ARM64_OP_IMM else None
        name = resolve_target(container, target) if target is not None else None
        copy = _copy_name(name)
        if copy is None:
            length = length_off = size = None
            continue
        dest_rel = dest.get("x0")
        capacity = frame_top - dest_rel if (frame_top is not None and dest_rel is not None) else None
        call_off = text.offset + (ins.address - text.va)
        if "_chk" in copy:
            if length is not None and size is not None and length > size:
                _emit_immediate(analysis, container, text, ins, "checked_copy", copy,
                                length, length_off, size, frame_start,
                                detail=f"checked copy length exceeds explicit destination size {size}",
                                confidence="high")
            length = length_off = size = None
            continue
        if copy in {"memcpy", "memmove"}:
            if length is not None and capacity is not None and 0 < capacity <= MAX_CAPACITY and length > capacity:
                _emit_immediate(analysis, container, text, ins, "memcpy_length", copy,
                                length, length_off, capacity, frame_start,
                                detail="immediate copy length exceeds stack capacity")
            length = length_off = size = None
            continue
        if copy in {"strcpy", "strcat", "stpcpy"}:
            if capacity is not None and 0 < capacity <= MAX_CAPACITY:
                analysis.sinks.append(Sink(
                    kind="unbounded_copy",
                    arch=container.arch,
                    function_va=frame_start or 0,
                    call_va=ins.address,
                    callee=copy,
                    capacity=capacity,
                    dest_rel=dest_rel,
                    call_offset=call_off,
                    call_size=ins.size,
                    patchable=True,
                    confidence="medium",
                    detail=f"{copy} into stack destination bounded to {capacity} bytes",
                ))
        length = length_off = size = None
