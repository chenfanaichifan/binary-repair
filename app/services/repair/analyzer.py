"""Architecture-neutral sink analysis for stack/heap-buffer copies.

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

Heap destination recovery (x86-64 only, fail closed)
----------------------------------------------------
A subset of heap overflows has a statically recoverable capacity: a
same-function ``malloc``/``calloc`` with immediate size arguments, whose return
value (rax) is copied to the copy destination register with plain ``mov``
instructions and then used as the destination of ``strcpy``/``strcat``/
``stpcpy``.  The scanner tracks:

* the last immediate moved into the allocation argument register (SysV: rdi
  for malloc, rdi/rsi for calloc; Win64: rcx, rcx/rdx),
* the allocation base register after a resolved ``malloc``/``calloc`` call,
* plain register-to-register copies of that base register.

The destination must equal the allocation base exactly.  State is discarded at
every ``jmp``/conditional jump/``ret``/``leave``/``syscall``, on any
non-copy write to a tracked register, and on any call other than the
``malloc``/``calloc`` being consumed; a pointer-plus-offset destination emits no
heap sink and records a limitation instead.  Heap sinks carry
``destination_kind="heap"``, ``dest_rel=None`` and the recovered capacity.

Known residual (documented, not repaired here):

* **Over-estimation for structs.** ``malloc(24)`` followed by
  ``strcpy(p->data, src)`` where ``data`` is a 16-byte member at offset 0
  recovers capacity 24, not 16.  The recovered number is the allocation size,
  never a member size; a guard built on it can still overwrite the rest of the
  struct (the ``heap_canary`` hard case is exactly this shape and its oracle
  capacity is 16).  The analyzer cannot see member layout without DWARF.
* Only the single allocation base is tracked; pointers that cross a function
  boundary, are spilled to memory and reloaded, or are offset by
  ``lea reg, [rax + K]`` are not recovered (fail closed).
* i386 heap destinations are not recovered (fail closed; the i386 scanner only
  models push-materialised stack arguments).
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
# Allocation functions whose immediate size argument is recoverable.  A
# ``realloc`` size is not tracked: its returned pointer may alias the input and
# the old capacity is unknown, so the scanner fails closed instead of guessing.
ALLOC_TOKENS = ("malloc", "calloc")
# Canonical 64-bit name for every x86 integer register alias the tracker may
# see.  Tracking happens in 64-bit terms; a write to any alias kills it.
_X86_CANON: dict[str, str] = {}
for _full in ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp"):
    _X86_CANON[_full] = _full
    _short = _full[1:]
    for _alias in (_short, "e" + _short, "r" + _short, "r" + _short + "d",
                   "r" + _short + "w", "r" + _short + "b"):
        _X86_CANON.setdefault(_alias, _full)
for _index in range(8, 16):
    _X86_CANON[f"r{_index}"] = f"r{_index}"
    for _suffix in ("d", "w", "b"):
        _X86_CANON[f"r{_index}{_suffix}"] = f"r{_index}"
del _full, _short, _alias, _index, _suffix
# Instruction writers whose explicit first operand is NOT written (they only
# read it), so heap/argument tracking must survive them.
_READ_ONLY_FIRST = {
    "cmp", "test", "push", "bt", "ucomiss", "ucomisd", "comiss", "comisd",
    "vucomiss", "vucomisd", "vcomiss", "vcomisd", "nop", "endbr64",
    "prefetch", "prefetchw", "prefetcht0", "prefetcht1", "prefetcht2",
    "prefetchnta",
}
# Instructions with implicit register writes/clobbers that are easier to
# invalidate wholesale than to model.
_IMPLICIT_CLOBBER = {
    "mul", "div", "idiv", "imul", "cdq", "cqo", "cwd", "cdqe", "cwde",
    "xchg", "rdtsc", "rdtscp", "cpuid", "xgetbv",
}
_CONTROL_FLOW = {"jmp", "ret", "retf", "leave", "syscall", "sysenter",
                 "int", "int3", "ud2", "hlt", "loop", "loope", "loopne",
                 "jecxz", "jrcxz"}

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
    #: Where the destination lives: ``stack`` (frame-relative ``dest_rel``),
    #: ``heap`` (same-function allocation capacity) or ``global`` (reserved;
    #: no analyzer emits it today).
    destination_kind: str = "stack"
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


def _plain_func_name(name: str | None) -> str:
    """Return the unqualified libc-style name for an import/symbol, else ``""``.

    ``malloc`` must match exactly (after namespace/suffix cleanup): matching by
    substring would also accept e.g. ``__libc_malloc`` wrappers whose return
    conventions differ, so allocation recovery fails closed there.
    """
    if not name:
        return ""
    low = name.lower().split("@")[0]
    return low.rsplit(".", 1)[-1].lstrip("_")


def _canon_reg(name: str | None) -> str:
    """Canonical 64-bit register name for an x86 register alias."""
    if not name:
        return ""
    return _X86_CANON.get(name.lower(), name.lower())


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
        elif container.arch == "i386":
            # Imported lazily: analyzer_i386 needs this module's Sink type.
            from app.services.repair.analyzer_i386 import scan_i386

            scan_i386(analysis, container, text, code)
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
    # --- heap destination recovery state (fail closed) ---------------------
    heap_caps: dict[str, int] = {}   # canonical reg -> live allocation capacity
    arg_imms: dict[str, int] = {}    # canonical arg reg -> last moved immediate
    heap_notes: list[str] = []
    malloc_size_reg = "rdi" if sysv else "rcx"
    calloc_size_regs = ("rdi", "rsi") if sysv else ("rcx", "rdx")
    arg_regs = frozenset(calloc_size_regs)
    return_reg = "rax"

    def _clear_heap_state() -> None:
        heap_caps.clear()
        arg_imms.clear()

    def _evict(reg: str) -> None:
        heap_caps.pop(reg, None)
        arg_imms.pop(reg, None)

    def _note_heap_offset() -> None:
        if not heap_notes:
            heap_notes.append(
                "heap destination is offset from its allocation base; the sink "
                "is not recovered (fail closed)"
            )

    def _heap_step(ins_obj) -> None:
        """Track same-function allocation/arg state for one instruction."""
        step_mnemonic = ins_obj.mnemonic
        if step_mnemonic == "call":
            return  # resolved and consumed by the call handler below
        if step_mnemonic in _CONTROL_FLOW or step_mnemonic.startswith("j"):
            _clear_heap_state()
            return
        if step_mnemonic in _IMPLICIT_CLOBBER:
            _clear_heap_state()
            return
        operands = ins_obj.operands
        if not operands:
            return
        first = operands[0]
        if step_mnemonic == "pop":
            for item in operands:
                if item.type == X86_OP_REG:
                    _evict(_canon_reg(ins_obj.reg_name(item.reg)))
            return
        if first.type != X86_OP_REG or step_mnemonic in _READ_ONLY_FIRST:
            return
        target = _canon_reg(ins_obj.reg_name(first.reg))
        if step_mnemonic == "mov" and len(operands) == 2:
            source = operands[1]
            if source.type == X86_OP_REG:
                source_reg = _canon_reg(ins_obj.reg_name(source.reg))
                _evict(target)
                if source_reg in heap_caps:
                    heap_caps[target] = heap_caps[source_reg]
                if source_reg in arg_imms:
                    arg_imms[target] = arg_imms[source_reg]
                return
            if source.type == X86_OP_IMM:
                _evict(target)
                value = int(source.imm)
                if target in arg_regs and 0 < value <= MAX_CAPACITY:
                    arg_imms[target] = value
                return
            _evict(target)  # loaded from memory: value is unknown
            return
        if step_mnemonic == "lea" and len(operands) == 2:
            memory = operands[1]
            _evict(target)
            if memory.type == X86_OP_MEM and not memory.mem.index:
                base = (
                    _canon_reg(ins_obj.reg_name(memory.mem.base))
                    if memory.mem.base else ""
                )
                if base in heap_caps:
                    offset = int(memory.mem.disp or 0)
                    if offset == 0:
                        heap_caps[target] = heap_caps[base]
                    else:
                        _note_heap_offset()
            return
        _evict(target)

    def _track_call(name: str | None) -> None:
        """Consume one resolved call: recover malloc/calloc or clobber state."""
        plain = _plain_func_name(name)
        capacity: int | None = None
        if plain == "malloc":
            value = arg_imms.get(malloc_size_reg)
            if value is not None and 0 < value <= MAX_CAPACITY:
                capacity = value
        elif plain == "calloc":
            count = arg_imms.get(calloc_size_regs[0])
            size = arg_imms.get(calloc_size_regs[1])
            if (
                count is not None and size is not None
                and 0 < count <= MAX_CAPACITY and 0 < size <= MAX_CAPACITY
            ):
                product = count * size
                if 0 < product <= MAX_CAPACITY:
                    capacity = product
        _clear_heap_state()
        if capacity is not None:
            heap_caps[return_reg] = capacity

    for ins in _MD_X86.disasm(code, text.va):
        op = (ins.op_str or "").replace(" ", "")
        mnemonic = ins.mnemonic
        _heap_step(ins)
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
        # Capture a tracked heap destination for this call, then consume the
        # allocation (or clobber) state.  ``_track_call`` must run before the
        # copy dispatch below because it clears the tracked registers.
        heap_dest_capacity = heap_caps.get(dest_reg)
        _track_call(name)
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
            if heap_dest_capacity is not None and 0 < heap_dest_capacity <= MAX_CAPACITY:
                analysis.sinks.append(Sink(
                    kind="unbounded_copy",
                    arch=container.arch,
                    function_va=frame_start or 0,
                    call_va=ins.address,
                    callee=copy,
                    capacity=heap_dest_capacity,
                    dest_rel=None,
                    destination_kind="heap",
                    call_offset=call_off,
                    call_size=ins.size,
                    patchable=True,
                    confidence="medium",
                    detail=(
                        f"{copy} into heap destination of {heap_dest_capacity} "
                        "bytes recovered from a same-function malloc/calloc"
                    ),
                ))
            elif capacity is not None and 0 < capacity <= MAX_CAPACITY:
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
    if heap_notes:
        analysis.limitations.extend(heap_notes)


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
