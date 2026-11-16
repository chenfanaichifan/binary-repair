"""Read-only basic-block CFG reconstruction (Phase-9 E-01 prototype).

This module is a *prototype analysis layer*: it is not wired into
``repair_any`` or the unified gate, it writes no bytes, it executes nothing,
and it produces no repair candidates.

Honesty rules (nothing is guessed):

* function starts come only from authoritative container metadata: ELF
  ``.symtab``/``.dynsym`` ``STT_FUNC`` entries (with ``st_size`` when present),
  the image entry point, and executable PLT/import stubs.  A stripped image
  therefore yields very few functions plus an explicit ``limitation``
  instead of invented symbols;
* blocks are built by a bounded linear sweep plus leader splitting, and only
  blocks reachable from the function entry are reported;
* unknown sizes (ELF ``st_size == 0`` and non-ELF containers) are swept with
  a hard byte cap and stop at the next known function start;
* indirect branches are never resolved: the block ends with an explicit
  ``unresolved`` terminator reason;
* every truncation (function cap, instruction budget, invalid byte, jump
  outside the analyzed range) is reported in ``limitations`` and/or as a
  ``decode_gap`` terminator -- nothing is invented.

JSON shape (stable, consumed by the P0-1 acceptance test and by
``scripts/analyze_crossfn.py``)::

    {
      "schema_version": 1,
      "format": "elf", "arch": "x86_64", "bits": 64, "entry": 16955840,
      "functions": [
        {"va": ..., "name": "vuln_copy", "source": "symtab",
         "size": 31, "instruction_count": 10,
         "blocks": [{"va":..., "end_va":..., "terminator": "ret",
                     "successors": [...],
                     "instructions": [{"va":..., "size": 1,
                                       "bytes": "55", "mnemonic": "push",
                                       "op_str": "rbp"}]}]}
      ],
      "limitations": [...],
      "statistics": {...}
    }

The combined call-graph JSON (``edges`` / ``callgraph_statistics``) is added
by :mod:`app.services.analysis.callgraph` / :func:`analyze_binary`.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from capstone import (
    CS_ARCH_ARM64,
    CS_ARCH_X86,
    CS_MODE_32,
    CS_MODE_64,
    CS_MODE_ARM,
    Cs,
)

from app.services.containers import ContainerInfo, detect_container

#: Analysis scope limits.  Exceeding any of them truncates the result and adds
#: a limitation; the walker never silently drops coverage.
MAX_FUNCTIONS = 5000
MAX_TOTAL_INSTRUCTIONS = 3_000_000
MAX_FUNCTION_INSTRUCTIONS = 200_000
MAX_BLOCK_INSTRUCTIONS = 20_000
MAX_FUNCTION_BYTES = 1 << 20
MAX_UNKNOWN_FUNCTION_BYTES = 16 * 1024
MAX_CALL_TARGET_FUNCTIONS = 2000
MAX_DECODE_GAPS_REPORTED = 32

_SCHEMA_VERSION = 1

_ARCH_MODES: dict[tuple[str, int | None], tuple[int, int]] = {
    ("x86_64", 64): (CS_ARCH_X86, CS_MODE_64),
    ("i386", 32): (CS_ARCH_X86, CS_MODE_32),
    ("arm64", 64): (CS_ARCH_ARM64, CS_MODE_ARM),
}

_MD_CACHE: dict[tuple[str, int | None], Cs] = {}

# x86 conditional-jump / loop mnemonics are all "j*" except jmp; loop-family
# mnemonics are explicit.
_X86_LOOP_MNEMONICS = {"loop", "loope", "loopne", "loopnz", "loopz", "jecxz",
                       "jrcxz"}
_X86_STOP_MNEMONICS = {"hlt", "ud2", "int3", "int1"}
_ARM64_STOP = {"hlt", "brk", "udf"}

# capstone operand type tags (identical numeric values in x86 and arm64)
_OP_REG = 1
_OP_IMM = 2
_OP_MEM = 3


def _disassembler(arch: str, bits: int | None) -> Cs | None:
    key = (arch, bits)
    cached = _MD_CACHE.get(key)
    if cached is not None:
        return cached
    mode = _ARCH_MODES.get(key)
    if mode is None:
        return None
    md = Cs(*mode)
    md.detail = True
    _MD_CACHE[key] = md
    return md


@dataclass
class _BranchInfo:
    """Classification of one instruction for CFG construction."""

    kind: str = "none"  # none | call | indirect_call | jmp | indirect_jmp | jcc | ret | stop
    target: int | None = None
    indirect: bool = False
    mem_slot: int | None = None
    reason: str = ""


@dataclass
class Instruction:
    """One decoded instruction.

    ``branch``, ``target``, ``mem_slot`` and ``reason`` are internal call-graph
    inputs and are not serialized; ``to_dict`` emits the stable public view.
    """

    va: int
    size: int
    bytes_hex: str
    mnemonic: str
    op_str: str
    branch: str = "none"
    target: int | None = None
    indirect: bool = False
    mem_slot: int | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "va": self.va,
            "size": self.size,
            "bytes": self.bytes_hex,
            "mnemonic": self.mnemonic,
            "op_str": self.op_str,
        }


@dataclass
class BasicBlock:
    va: int
    end_va: int
    terminator: str = "fallthrough"
    successors: list[int] = field(default_factory=list)
    instructions: list[Instruction] = field(default_factory=list)
    unresolved_reason: str = ""

    def to_dict(self, *, include_instructions: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "va": self.va,
            "end_va": self.end_va,
            "terminator": self.terminator,
            "successors": list(self.successors),
        }
        if self.unresolved_reason:
            payload["unresolved_reason"] = self.unresolved_reason
        if include_instructions:
            payload["instructions"] = [ins.to_dict() for ins in self.instructions]
        return payload


@dataclass
class FunctionCfg:
    va: int
    name: str | None
    source: str  # symtab | symbol | entry | plt_stub
    size: int | None = None
    end_va: int | None = None
    blocks: list[BasicBlock] = field(default_factory=list)

    @property
    def instruction_count(self) -> int:
        return sum(len(block.instructions) for block in self.blocks)

    def to_dict(self, *, include_instructions: bool = True) -> dict[str, Any]:
        return {
            "va": self.va,
            "name": self.name,
            "source": self.source,
            "size": self.size,
            "end_va": self.end_va,
            "instruction_count": self.instruction_count,
            "block_count": len(self.blocks),
            "blocks": [
                block.to_dict(include_instructions=include_instructions)
                for block in self.blocks
            ],
        }


@dataclass
class CfgResult:
    format: str
    arch: str
    bits: int | None
    entry: int
    functions: list[FunctionCfg] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_instructions: bool = True) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "tool": "m2-analysis-cfg",
            "format": self.format,
            "arch": self.arch,
            "bits": self.bits,
            "entry": self.entry,
            "functions": [
                function.to_dict(include_instructions=include_instructions)
                for function in self.functions
            ],
            "limitations": list(self.limitations),
            "statistics": dict(self.statistics),
        }


# ---------------------------------------------------------------------------
# function discovery (metadata only; never heuristics on code bytes)
# ---------------------------------------------------------------------------


@dataclass
class _FuncStart:
    va: int
    name: str | None
    source: str
    size: int | None = None


def _exec_section(container: ContainerInfo, va: int):
    section = container.section_at(va)
    if section is None or not section.executable or not section.size:
        return None
    return section


def _elf_function_symbols(
    data: bytes,
) -> tuple[list[tuple[int, str, int]], dict[int, str], str]:
    """Return ELF code symbols.

    Returns ``(func_rows, notype_names, reason)`` where ``func_rows`` are
    ``(va, name, size)`` STT_FUNC rows (authoritative function starts) and
    ``notype_names`` maps a VA to a NOTYPE symbol name.  Hand-written assembly
    frequently declares ``.globl name`` without `.type name, @function`, so
    those labels are not STT_FUNC; they are used only to *name* a function that
    was independently justified as a direct-call target, never to invent one.
    """
    from elftools.elf.elffile import ELFFile

    try:
        elf = ELFFile(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - container layer already records it
        return [], {}, f"elf symbol table unavailable: {type(exc).__name__}"
    func_rows: list[tuple[int, str, int]] = []
    notype_names: dict[int, str] = {}
    for section_name in (".symtab", ".dynsym"):
        try:
            section = elf.get_section_by_name(section_name)
        except Exception:  # noqa: BLE001
            continue
        if section is None:
            continue
        try:
            symbols = list(section.iter_symbols())
        except Exception:  # noqa: BLE001
            continue
        for symbol in symbols:
            try:
                symbol_type = symbol["st_info"]["type"]
                value = int(symbol["st_value"])
                size = int(symbol["st_size"])
            except Exception:  # noqa: BLE001
                continue
            if not value:
                continue
            name = symbol.name or ""
            if symbol_type in {"STT_FUNC", "func"}:
                func_rows.append((value, name, size))
            elif symbol_type in {"STT_NOTYPE", "notype"}:
                if name and not name.startswith(("$", ".L")):
                    notype_names.setdefault(value, name)
    if not func_rows:
        return [], notype_names, "no STT_FUNC symbols in .symtab/.dynsym"
    return func_rows, notype_names, ""


def _function_starts(
    container: ContainerInfo,
    data: bytes,
) -> tuple[dict[int, _FuncStart], list[str], dict[int, str]]:
    limitations: list[str] = []
    starts: dict[int, _FuncStart] = {}
    notype_names: dict[int, str] = {}

    def _add(va: int, name: str | None, source: str, size: int | None) -> None:
        if _exec_section(container, va) is None:
            return
        existing = starts.get(va)
        if existing is None:
            starts[va] = _FuncStart(va=va, name=name or None, source=source, size=size)
            return
        if not existing.name and name:
            existing.name = name
        if not existing.size and size:
            existing.size = size

    if container.format == "elf":
        rows, elf_notype_names, reason = _elf_function_symbols(data)
        for va, name in elf_notype_names.items():
            if _exec_section(container, va) is not None:
                notype_names.setdefault(va, name)
        if reason:
            limitations.append(reason)
        for va, name, size in rows:
            _add(va, name, "symtab", size)
        if not rows:
            limitations.append(
                "no function symbols: CFG function list is limited to the entry "
                "point and executable import stubs (stripped image)"
            )
    else:
        for va, name in sorted(container.symbols.items()):
            _add(va, name, "symbol", None)
        if not container.symbols:
            limitations.append(
                "container exposes no function symbols: function list is limited "
                "to the entry point and executable import stubs"
            )

    if container.entry:
        _add(container.entry, "<entry>", "entry", None)

    for va, name in sorted(container.imports.items()):
        if _exec_section(container, va) is None:
            continue
        if va not in starts:
            starts[va] = _FuncStart(va=va, name=name, source="plt_stub", size=None)
    # Some toolchains define the imported symbol itself as an STT_FUNC symbol at
    # the PLT stub address (size 0).  Those are still trampolines, not user
    # code; count them regardless of which source registered the start.
    stub_vas = [va for va in starts
                if va in container.imports and _exec_section(container, va) is not None]
    if stub_vas:
        limitations.append(
            f"{len(stub_vas)} executable import stub(s) are present in the function "
            "list; their bodies are PLT/trampoline code, not user code, and they are "
            "not treated as patch targets by this prototype"
        )
    return starts, limitations, notype_names


# ---------------------------------------------------------------------------
# disassembly / branch classification
# ---------------------------------------------------------------------------


def _x86_mem_slot(ins: Any, bits: int | None) -> int | None:
    """Static slot address for an x86 memory operand, when unambiguous."""
    try:
        operand = ins.operands[0]
        mem = operand.mem
    except (AttributeError, IndexError):
        return None
    base = getattr(mem, "base", 0)
    index = getattr(mem, "index", 0)
    disp = getattr(mem, "disp", 0)
    if index:
        return None
    if base == 0:  # absolute [addr] (i386 / non-PIE)
        return int(disp) & ((1 << (bits or 64)) - 1)
    try:
        from capstone.x86 import X86_REG_RIP

        rip = X86_REG_RIP
    except Exception:  # noqa: BLE001
        rip = 41
    if base == rip:
        return ins.address + ins.size + int(disp)
    return None


def _branch_info(ins: Any, arch: str, bits: int | None) -> _BranchInfo:
    mnemonic = (ins.mnemonic or "").lower()
    if arch in {"x86_64", "i386"}:
        if mnemonic.startswith("ret") or mnemonic.startswith("iret"):
            return _BranchInfo(kind="ret")
        if mnemonic == "call":
            operands = list(ins.operands)
            if operands and operands[0].type == _OP_REG:
                return _BranchInfo(kind="indirect_call", indirect=True,
                                   reason="register-indirect call")
            if operands and operands[0].type == _OP_MEM:
                slot = _x86_mem_slot(ins, bits)
                if slot is not None:
                    return _BranchInfo(kind="call", target=None, indirect=True,
                                       mem_slot=slot)
                return _BranchInfo(kind="indirect_call", indirect=True,
                                   reason="memory-indirect call with computed address")
            target = operands[0].imm if operands else None
            return _BranchInfo(kind="call", target=target)
        if mnemonic == "jmp":
            operands = list(ins.operands)
            if operands and operands[0].type == _OP_REG:
                return _BranchInfo(kind="indirect_jmp", indirect=True,
                                   reason="register-indirect jump")
            if operands and operands[0].type == _OP_MEM:
                slot = _x86_mem_slot(ins, bits)
                if slot is not None:
                    return _BranchInfo(kind="jmp", target=None, indirect=True,
                                       mem_slot=slot)
                return _BranchInfo(kind="indirect_jmp", indirect=True,
                                   reason="memory-indirect jump with computed address")
            target = operands[0].imm if operands else None
            return _BranchInfo(kind="jmp", target=target)
        if mnemonic.startswith("j") or mnemonic in _X86_LOOP_MNEMONICS:
            operands = list(ins.operands)
            target = operands[0].imm if operands and operands[0].type == _OP_IMM else None
            return _BranchInfo(kind="jcc", target=target)
        if mnemonic in _X86_STOP_MNEMONICS:
            return _BranchInfo(kind="stop")
        return _BranchInfo(kind="none")

    # arm64
    if mnemonic in {"ret", "retaa", "retab", "eret"}:
        return _BranchInfo(kind="ret")
    if mnemonic in _ARM64_STOP:
        return _BranchInfo(kind="stop")
    if mnemonic in {"br", "braa", "brab"}:
        return _BranchInfo(kind="indirect_jmp", indirect=True,
                           reason="register-indirect branch (br)")
    if mnemonic in {"blr", "blraa", "blrab"}:
        return _BranchInfo(kind="indirect_call", indirect=True,
                           reason="register-indirect call (blr)")
    if mnemonic in {"bl", "blraaz", "blrabz"}:
        operands = list(ins.operands)
        target = operands[0].imm if operands and getattr(operands[0], "type", None) == _OP_IMM else None
        return _BranchInfo(kind="call", target=target)
    if mnemonic == "b" or mnemonic.startswith("b."):
        operands = list(ins.operands)
        target = operands[0].imm if operands and getattr(operands[0], "type", None) == _OP_IMM else None
        if mnemonic == "b":
            return _BranchInfo(kind="jmp", target=target)
        return _BranchInfo(kind="jcc", target=target)
    if mnemonic in {"cbz", "cbnz", "tbz", "tbnz"}:
        # cbz x0, label      -> [REG, IMM(label)]
        # tbz x0, #bit, label -> [REG, IMM(bit), IMM(label)]; the label is the
        # last immediate operand, never the bit index.
        operands = list(ins.operands)
        immediates = [op.imm for op in operands
                      if getattr(op, "type", None) == _OP_IMM]
        target = immediates[-1] if immediates else None
        return _BranchInfo(kind="jcc", target=target)
    return _BranchInfo(kind="none")


def _make_instruction(ins: Any, arch: str, bits: int | None) -> Instruction:
    branch = _branch_info(ins, arch, bits)
    return Instruction(
        va=int(ins.address),
        size=int(ins.size),
        bytes_hex=bytes(ins.bytes).hex(),
        mnemonic=ins.mnemonic or "",
        op_str=ins.op_str or "",
        branch=branch.kind,
        target=branch.target,
        indirect=branch.indirect,
        mem_slot=branch.mem_slot,
        reason=branch.reason,
    )


def _decode_window(
    md: Cs,
    data: bytes,
    container: ContainerInfo,
    start: int,
    end: int,
) -> list[Instruction]:
    """Linear-disassemble ``[start, end)`` into ``Instruction`` records.

    Capstone skips undecodable bytes inside the window; the skipped ranges are
    detected later as ``decode_gap`` block terminators.
    """
    section = _exec_section(container, start)
    if section is None:
        return []
    offset = section.offset + (start - section.va)
    if offset < 0 or offset >= len(data):
        return []
    end = min(end, section.va + section.size, start + MAX_FUNCTION_BYTES)
    length = min(max(0, end - start), len(data) - offset)
    if length <= 0:
        return []
    out: list[Instruction] = []
    for ins in md.disasm(data[offset:offset + length], start):
        out.append(_make_instruction(ins, container.arch, container.bits))
        if len(out) > MAX_FUNCTION_INSTRUCTIONS:
            break
    return out


# ---------------------------------------------------------------------------
# CFG construction
# ---------------------------------------------------------------------------


def _build_function(
    md: Cs,
    data: bytes,
    container: ContainerInfo,
    start: _FuncStart,
    other_starts: frozenset[int],
    budget: list[int],
) -> tuple[FunctionCfg, list[str]]:
    limitations: list[str] = []
    function = FunctionCfg(va=start.va, name=start.name, source=start.source, size=start.size)
    section = _exec_section(container, start.va)
    if section is None:
        return function, limitations
    section_end = section.va + section.size

    known_end: int | None = None
    if start.size and start.size > 0:
        known_end = min(start.va + start.size, section_end)
        if start.size > MAX_FUNCTION_BYTES:
            limitations.append(
                f"function 0x{start.va:x} declared size {start.size} exceeds "
                f"{MAX_FUNCTION_BYTES} bytes; analysis window truncated"
            )
    function.end_va = known_end
    window_end = known_end if known_end is not None else min(
        start.va + MAX_UNKNOWN_FUNCTION_BYTES, section_end,
    )
    if known_end is None:
        function.end_va = window_end
    if budget[0] <= 0:
        limitations.append(
            f"function 0x{start.va:x} skipped: global instruction budget exhausted"
        )
        function.blocks = []
        return function, limitations

    decoded = _decode_window(md, data, container, start.va, window_end)
    if not decoded:
        limitations.append(
            f"function 0x{start.va:x}: no instruction decoded in the analysis window"
        )
        return function, limitations
    budget[0] -= len(decoded)

    # ---- leaders (classic linear-sweep): entry, branch targets, instructions
    # following a control-flow terminator, and the instruction after a gap.
    leaders: set[int] = {start.va}
    previous_end: int | None = None
    for ins in decoded:
        if previous_end is not None and ins.va != previous_end:
            leaders.add(ins.va)
        next_va = ins.va + ins.size
        if ins.branch in {"jmp", "jcc"} and ins.target is not None:
            if start.va <= ins.target < window_end:
                leaders.add(ins.target)
        if ins.branch in {"jmp", "jcc", "ret", "stop"}:
            leaders.add(next_va)
        if ins.branch in {"indirect_jmp", "indirect_call"}:
            pass  # unresolved target; cannot be a leader
        previous_end = next_va

    # ---- split into blocks (linear order)
    blocks: list[BasicBlock] = []
    current: BasicBlock | None = None
    for ins in decoded:
        if ins.va in other_starts and ins.va != start.va:
            break  # next known function: stop before it
        if ins.va >= window_end:
            break
        if current is None or ins.va in leaders or current.end_va != ins.va:
            if current is not None and not current.terminator:
                current.terminator = "fallthrough"
            current = BasicBlock(va=ins.va, end_va=ins.va)
            blocks.append(current)
        current.instructions.append(ins)
        current.end_va = ins.va + ins.size
        if ins.branch in {"jmp", "jcc", "ret", "stop", "indirect_jmp"}:
            current.terminator = ""  # finalized below
            current = None
    if current is not None and not current.terminator:
        current.terminator = "fallthrough"

    block_by_va = {block.va: block for block in blocks}

    # ---- per-block terminator classification + intra-function successors
    for block in blocks:
        if not block.instructions:
            block.terminator = "decode_gap"
            block.unresolved_reason = f"no instruction decodes at 0x{block.va:x}"
            continue
        last = block.instructions[-1]
        branch = last.branch
        if branch in {"ret", "stop"}:
            block.terminator = branch
            continue
        if branch in {"jmp", "indirect_jmp"}:
            if branch == "indirect_jmp" or last.mem_slot is not None:
                slot = f" through slot 0x{last.mem_slot:x}" if last.mem_slot is not None else ""
                block.terminator = "unresolved_jmp"
                block.unresolved_reason = (
                    f"indirect jump{slot} at 0x{last.va:x}: target depends on runtime data"
                )
                limitations.append(
                    f"function 0x{start.va:x}: {block.unresolved_reason}"
                )
                continue
            target = last.target
            if target is None:
                block.terminator = "unresolved_jmp"
                block.unresolved_reason = f"direct jump at 0x{last.va:x} has no immediate target"
                continue
            if target in other_starts:
                block.terminator = "tail_jmp"
                continue
            if target in block_by_va:
                block.successors = [target]
                block.terminator = "jmp"
            else:
                block.terminator = "jmp_out"
                block.unresolved_reason = (
                    f"jump target 0x{target:x} is outside the analyzed function range"
                )
                limitations.append(
                    f"function 0x{start.va:x}: jump at 0x{last.va:x} leaves the "
                    f"analyzed range (target 0x{target:x}); outer target not followed"
                )
            continue
        if branch == "jcc":
            successors: list[int] = []
            if last.target is not None:
                if last.target in block_by_va and last.target not in other_starts:
                    successors.append(last.target)
                else:
                    limitations.append(
                        f"function 0x{start.va:x}: conditional target "
                        f"0x{last.target:x} outside the analyzed range; not followed"
                    )
            fallthrough = last.va + last.size
            if fallthrough in block_by_va and fallthrough not in other_starts:
                successors.append(fallthrough)
            block.successors = list(dict.fromkeys(successors))
            block.terminator = "jcc"
            continue
        # block ended because the next instruction is a leader or a gap
        next_va = block.end_va
        if next_va in block_by_va:
            block.successors = [next_va]
            block.terminator = "fallthrough"
        elif next_va >= window_end:
            block.terminator = "fallthrough_end"
        else:
            block.terminator = "decode_gap"
            block.unresolved_reason = (
                f"no instruction decodes at 0x{next_va:x} (invalid byte sequence)"
            )

    # ---- keep only blocks reachable from the function entry
    entry_block = block_by_va.get(start.va)
    reachable: set[int] = set()
    stack = [entry_block.va] if entry_block is not None else []
    while stack:
        va = stack.pop()
        if va in reachable:
            continue
        reachable.add(va)
        block = block_by_va.get(va)
        if block is None:
            continue
        stack.extend(block.successors)
    unreachable = len(blocks) - len(reachable)
    if unreachable:
        limitations.append(
            f"function 0x{start.va:x}: {unreachable} block(s) not reachable from the "
            "function entry were dropped (may be padding, jump-table bodies, or "
            "unlabeled code)"
        )
    function.blocks = [block for block in blocks if block.va in reachable]
    if known_end is None:
        # Unknown declared size: report the actually analyzed extent instead of
        # the sweep window (the window is a cap, not a claim about the body).
        function.end_va = max(
            (block.end_va for block in function.blocks), default=None,
        )
    if not function.blocks:
        limitations.append(f"function 0x{start.va:x}: no reachable block decoded")
    return function, limitations


def build_cfg(
    data: bytes,
    *,
    container: ContainerInfo | None = None,
    include_instructions: bool = True,
    max_functions: int = MAX_FUNCTIONS,
    max_instructions: int = MAX_TOTAL_INSTRUCTIONS,
) -> CfgResult:
    """Reconstruct a basic-block CFG for one container image (read-only)."""
    del include_instructions  # serialization option, not an analysis option
    if container is None:
        container = detect_container(data)
    result = CfgResult(
        format=container.format,
        arch=container.arch,
        bits=container.bits,
        entry=container.entry,
        limitations=list(container.limitations),
    )
    if container.format == "unknown" or container.bits is None:
        result.limitations.append("unrecognised container; no CFG is reconstructed")
        result.statistics = {"functions": 0, "blocks": 0, "instructions": 0,
                             "decode_gaps": 0}
        return result
    md = _disassembler(container.arch, container.bits)
    if md is None:
        result.limitations.append(
            f"no CFG disassembler for {container.format}/{container.arch}/"
            f"{container.bits} bits; nothing is reconstructed"
        )
        result.statistics = {"functions": 0, "blocks": 0, "instructions": 0,
                             "decode_gaps": 0}
        return result
    if container.endian == "big":
        result.limitations.append("big-endian containers are not supported by the CFG prototype")
        result.statistics = {"functions": 0, "blocks": 0, "instructions": 0,
                             "decode_gaps": 0}
        return result

    starts, start_limitations, notype_names = _function_starts(container, data)
    result.limitations.extend(start_limitations)
    ordered = [starts[va] for va in sorted(starts)]
    if len(ordered) > max_functions:
        result.limitations.append(
            f"{len(ordered)} candidate functions exceed the cap {max_functions}; "
            f"only the lowest {max_functions} addresses are analyzed"
        )
        ordered = ordered[:max_functions]
    all_starts = frozenset(item.va for item in ordered)

    budget = [max_instructions]
    unknown_size_functions = 0
    for start in ordered:
        if start.size is None or start.size == 0:
            unknown_size_functions += 1
        others = all_starts - {start.va}
        function, function_limitations = _build_function(
            md, data, container, start, others, budget,
        )
        result.functions.append(function)
        result.limitations.extend(function_limitations)

    # ---- direct-call-target augmentation.  A statically computed call target
    # that lies outside every analyzed function span is a code address the
    # image explicitly calls; analyzing it is justified by the instruction, not
    # guessed from layout.  NOTYPE symbol names are used only to label such a
    # function, never to invent one.
    covered: list[tuple[int, int]] = [
        (function.va, function.end_va)
        for function in result.functions
        if function.end_va is not None
    ]
    known_starts = set(starts)
    orphan_targets: set[int] = set()
    for function in result.functions:
        for block in function.blocks:
            for ins in block.instructions:
                if ins.branch != "call" or ins.indirect or ins.target is None:
                    continue
                target = ins.target
                if target in known_starts:
                    continue
                if any(start <= target < end for start, end in covered):
                    continue
                if _exec_section(container, target) is not None:
                    orphan_targets.add(target)
    added = 0
    for target in sorted(orphan_targets):
        if added >= MAX_CALL_TARGET_FUNCTIONS:
            result.limitations.append(
                f"more than {MAX_CALL_TARGET_FUNCTIONS} direct-call-target functions; "
                "the remaining call targets are not analyzed"
            )
            break
        if any(start <= target < end for start, end in covered):
            continue  # nested inside an earlier call-target function
        call_start = _FuncStart(
            va=target, name=notype_names.get(target), source="call_target", size=None,
        )
        function, function_limitations = _build_function(
            md, data, container, call_start,
            frozenset(known_starts | {target}), budget,
        )
        result.functions.append(function)
        result.limitations.extend(function_limitations)
        known_starts.add(target)
        if function.end_va is not None:
            covered.append((function.va, function.end_va))
        added += 1
    if orphan_targets:
        result.limitations.append(
            f"{len(orphan_targets)} direct call target(s) fell outside "
            f"symbol-covered function spans; {added} were analyzed as "
            "call_target functions (target address from the call instruction; "
            "name from a NOTYPE/.globl-only symbol when present)"
        )
    result.functions.sort(key=lambda function: function.va)
    if unknown_size_functions:
        result.limitations.append(
            f"{unknown_size_functions} function(s) have no declared size; their "
            f"analysis window is bounded to {MAX_UNKNOWN_FUNCTION_BYTES} bytes and "
            "stops at the next known function start"
        )

    decode_gap_functions = sum(
        1 for function in result.functions
        if any(block.terminator == "decode_gap" for block in function.blocks)
    )
    total_blocks = sum(len(function.blocks) for function in result.functions)
    total_instructions = sum(function.instruction_count for function in result.functions)
    result.statistics = {
        "functions": len(result.functions),
        "blocks": total_blocks,
        "instructions": total_instructions,
        "functions_without_blocks": sum(
            1 for function in result.functions if not function.blocks
        ),
        "functions_with_decode_gap": decode_gap_functions,
        "functions_with_unresolved_terminator": sum(
            1 for function in result.functions
            if any(block.terminator in {"unresolved_jmp", "decode_gap"}
                   for block in function.blocks)
        ),
        "instruction_budget_remaining": budget[0],
    }
    return result
