"""Cross-function value-origin tracing (Phase-9 E-02 prototype).

Read-only analysis evidence: this module never writes bytes, never executes the
target and is not wired into repair_any or any gate.

For every known copy sink (strcpy/strcat/stpcpy/memcpy/memmove and _chk
variants) the prototype answers: *where does the destination capacity come
from?*  It walks backwards through registers, stack spills/reloads, return
values and one level of call edges (bounded, configurable), then resolves the
origin to one of:

* stack_local - a frame slot of the sink function or of a caller; capacity is
  frame geometry (frame_top - destination) and is reported as an explicit
  UPPER BOUND (frame_geometry_upper_bound), because the prototype does not read
  DWARF object sizes;
* global_object - a concrete global address that matches an ELF STT_OBJECT
  symbol; capacity is that symbol's st_size (object_symbol_size, exact);
* global_address - a concrete global address with no exact symbol/size match;
  capacity unknown;
* heap_allocation - a same-function malloc/calloc with a statically recovered
  immediate size (allocation_immediate_size);
* return_value - the value returned by a called function whose own return
  origin is resolved to one of the above (one extra level);
* parameter - the sink function receives the pointer from its callers; every
  resolved caller call site is reported as a separate path with its own origin
  and capacity.  Call-site-dependent capacities are reported as a conflict, not
  silently averaged or guessed;
* unknown - no sound conclusion; an explicit limitation says why.

The JSON shape is stable and mirrored by scripts/analyze_crossfn.py::

    {"schema_version": 1, "tool": "m2-analysis-dataflow",
     "format": "elf", "arch": "x86_64",
     "sinks": [{"site_va": ..., "callee": "strcpy",
                "function": {"va": ..., "name": "copy_payload"},
                "destination": {"origin": "parameter", "capacity": null,
                                "capacity_source": null, "agreement": "conflict",
                                "resolution": "partially_resolved",
                                "paths": [{"caller": {...}, "origin": ...,
                                           "capacity": 32, "steps": [...]}]},
                "source_argument": {...}, "alias": {...},
                "confidence": "low", "limitations": [...]}],
     "limitations": [...], "statistics": {...}}

Non-x86_64 targets are reported as sinks with destination.resolution
"unsupported_arch" plus a limitation; nothing is guessed for them.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from app.services.analysis.alias import (
    ARG_REGS,
    UNKNOWN,
    Location,
    analyze_points_to,
    canon_reg,
    frame_model,
    mem_operand,
    must_alias,
    must_not_alias,
    parameter as parameter_location,
    points_to_at,
    sets_may_alias,
    stack_local,
)
from app.services.analysis.callgraph import CallEdge, CallGraph, build_call_graph
from app.services.analysis.cfg import CfgResult, FunctionCfg, Instruction, build_cfg
from app.services.containers import ContainerInfo, detect_container

SCHEMA_VERSION = 1
COPY_TOKENS = ("strcpy", "strcat", "stpcpy", "memcpy", "memmove",
               "__memcpy_chk", "__strcpy_chk", "__strcat_chk")
ALLOC_TOKENS = ("malloc", "calloc")
MAX_TRACE_STEPS = 64
MAX_INTERPROC_DEPTH = 3
MAX_PATHS_PER_SINK = 8
MAX_LIMITATIONS = 200

_X86_CALLER_SAVED = frozenset({"rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9",
                               "r10", "r11"})
_ALL_REGS = frozenset({
    "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
})
_READ_ONLY_FIRST = frozenset({
    "cmp", "test", "push", "bt", "ucomiss", "ucomisd", "comiss", "comisd",
    "nop", "endbr64", "prefetch", "prefetchw", "jmp", "ret", "retf", "leave",
    "call", "syscall", "int3", "ud2", "hlt",
})


def canonical_name(name: str | None) -> str:
    """Canonical libc-style name: '@GLIBC' suffix and namespace stripped."""
    if not name:
        return ""
    low = name.lower().split("@")[0]
    return low.rsplit(".", 1)[-1]


def copy_token(name: str | None) -> str | None:
    short = canonical_name(name)
    if not short:
        return None
    if short in COPY_TOKENS:
        return short
    stripped = short.lstrip("_")
    if stripped in COPY_TOKENS:
        return stripped
    for token in COPY_TOKENS:
        if token.lstrip("_") in stripped:
            return token.lstrip("_")
    return None


def alloc_token(name: str | None) -> str | None:
    short = canonical_name(name)
    if short in ALLOC_TOKENS:
        return short
    stripped = short.lstrip("_")
    return stripped if stripped in ALLOC_TOKENS else None


def _parse_int(text: str) -> int | None:
    text = text.strip()
    if text.startswith(("0x", "0X")):
        try:
            return int(text, 16)
        except ValueError:
            return None
    try:
        return int(text, 10)
    except ValueError:
        return None


def object_symbols(container: ContainerInfo, data: bytes) -> dict[int, tuple[str, int | None]]:
    """Return ELF STT_OBJECT address -> (name, size) from .symtab/.dynsym."""
    if container.format != "elf":
        return {}
    from elftools.elf.elffile import ELFFile

    try:
        elf = ELFFile(io.BytesIO(data))
    except Exception:  # noqa: BLE001 - container layer already records the reason
        return {}
    out: dict[int, tuple[str, int | None]] = {}
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
                if symbol["st_info"]["type"] not in {"STT_OBJECT", "object"}:
                    continue
                value = int(symbol["st_value"])
                size = int(symbol["st_size"])
            except Exception:  # noqa: BLE001
                continue
            name = symbol.name or ""
            if value:
                out.setdefault(value, (name, size or None))
    return out


# ---------------------------------------------------------------------------
# origin model
# ---------------------------------------------------------------------------


@dataclass
class Step:
    kind: str
    function: str | None = None
    va: int | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind}
        if self.function:
            payload["function"] = self.function
        if self.va is not None:
            payload["va"] = self.va
        if self.detail:
            payload["detail"] = self.detail
        return payload


@dataclass
class Origin:
    kind: str = "unknown"  # stack_local | global_object | global_address |
    #                        heap_allocation | return_value | immediate |
    #                        parameter | unknown
    capacity: int | None = None
    capacity_source: str | None = None
    value: int | None = None
    address: int | None = None
    symbol: str | None = None
    function_va: int | None = None
    function_name: str | None = None
    offset: int | None = None
    parameter_index: int | None = None
    callee_name: str | None = None
    steps: list[Step] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    confidence: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "origin": self.kind,
            "capacity": self.capacity,
            "capacity_source": self.capacity_source,
            "confidence": self.confidence,
            "steps": [step.to_dict() for step in self.steps],
        }
        if self.value is not None:
            payload["value"] = self.value
        if self.address is not None:
            payload["address"] = self.address
        if self.symbol is not None:
            payload["symbol"] = self.symbol
        if self.function_name is not None:
            payload["function"] = {"va": self.function_va, "name": self.function_name}
        if self.offset is not None:
            payload["frame_offset"] = self.offset
        if self.callee_name is not None:
            payload["callee"] = self.callee_name
        if self.limitations:
            payload["limitations"] = list(self.limitations)
        return payload


def _unknown(reason: str, steps: list[Step] | None = None) -> Origin:
    return Origin(kind="unknown", steps=list(steps or []), limitations=[reason],
                  confidence="unknown")


# ---------------------------------------------------------------------------
# tracing context
# ---------------------------------------------------------------------------


class TraceContext:
    """Bounded backward value tracer over one decoded CFG + call graph."""

    def __init__(self, cfg: CfgResult, call_graph: CallGraph,
                 container: ContainerInfo, globals_: dict[int, tuple[str, int | None]]):
        self.cfg = cfg
        self.call_graph = call_graph
        self.container = container
        self.globals = globals_
        self.function_by_va = {function.va: function for function in cfg.functions}
        self.site_edges: dict[int, CallEdge] = {edge.site_va: edge for edge in call_graph.edges}
        self._blocks: dict[int, dict[int, tuple[Any, int]]] = {}
        self._preds: dict[int, dict[int, list[int]]] = {}
        self._alias: dict[int, dict[int, dict[str, frozenset[Location]]]] = {}
        self._frame: dict[int, tuple[int, str | None]] = {}
        self.call_targets: dict[int, str] = {
            edge.site_va: edge.callee or ""
            for edge in call_graph.edges
            if edge.callee and edge.resolved
        }
        self.notes: list[str] = []

    # -- structural helpers -------------------------------------------------
    def _index(self, function: FunctionCfg) -> dict[int, tuple[Any, int]]:
        cached = self._blocks.get(function.va)
        if cached is not None:
            return cached
        index: dict[int, tuple[Any, int]] = {}
        for block in function.blocks:
            for position, ins in enumerate(block.instructions):
                index[ins.va] = (block, position)
        self._blocks[function.va] = index
        return index

    def block_by_va(self, function: FunctionCfg) -> dict[int, Any]:
        return {block.va: block for block in function.blocks}

    def predecessors(self, function: FunctionCfg) -> dict[int, list[int]]:
        cached = self._preds.get(function.va)
        if cached is not None:
            return cached
        blocks = self.block_by_va(function)
        preds: dict[int, list[int]] = {block.va: [] for block in function.blocks}
        for block in function.blocks:
            for succ in block.successors:
                if succ in blocks:
                    preds[succ].append(block.va)
        self._preds[function.va] = preds
        return preds

    def frame(self, function: FunctionCfg) -> tuple[int, str | None]:
        cached = self._frame.get(function.va)
        if cached is None:
            cached = frame_model(function)
            self._frame[function.va] = cached
        return cached

    def alias(self, function: FunctionCfg) -> dict[int, dict[str, frozenset[Location]]]:
        cached = self._alias.get(function.va)
        if cached is None:
            cached = analyze_points_to(self.cfg, function, self.globals,
                                       call_targets=self.call_targets)
            self._alias[function.va] = cached
        return cached

    def note(self, text: str) -> None:
        if text not in self.notes and len(self.notes) < MAX_LIMITATIONS:
            self.notes.append(text)

    def _stack_offset(self, function: FunctionCfg, base: str | None, disp: int | None) -> int | None:
        if base is None or disp is None:
            return None
        frame_size, frame_pointer = self.frame(function)
        if base == "rbp" and frame_pointer == "rbp":
            return disp
        if base == "rsp":
            return disp - frame_size
        return None

    # -- definition discovery ----------------------------------------------
    def _defines(self, ins: Instruction, reg: str) -> bool:
        if ins.branch in {"call", "indirect_call"}:
            return reg in _X86_CALLER_SAVED
        if ins.branch in {"jmp", "jcc", "ret", "stop"}:
            return False
        mnemonic = ins.mnemonic.lower()
        if mnemonic in _READ_ONLY_FIRST:
            return False
        arguments = [part.strip() for part in ins.op_str.split(",")] if ins.op_str else []
        if not arguments:
            return False
        if mnemonic in {"mov", "lea", "movabs", "movzx", "movsx", "movsxd",
                        "add", "sub", "and", "or", "xor", "imul", "shl", "shr",
                        "sar", "not", "neg", "inc", "dec", "setne", "sete"}:
            first = arguments[0]
            if "[" in first:
                return False
            return canon_reg(first) == reg
        if mnemonic == "pop":
            return canon_reg(arguments[0]) == reg
        if mnemonic == "leave":
            return reg == "rbp"
        return False

    def _find_store(self, function: FunctionCfg, at_va: int,
                    slot_offset: int) -> tuple[Instruction, str] | None:
        """Find the unique reaching store to frame slot rbp+slot_offset.

        Backward search over all predecessor paths (bounded).  The store is
        returned only when exactly one store instruction reaches the load on
        every analyzed path; zero or multiple distinct stores are unknown.
        Assumption (recorded as a limitation): a call does not write the
        caller's analyzed frame slot -- no escape analysis is modeled.
        """
        index = self._index(function)
        location = index.get(at_va)
        if location is None:
            return None
        blocks = self.block_by_va(function)
        preds = self.predecessors(function)
        block, position = location
        pending: list[tuple[Any, int]] = [(block, position)]
        visited: set[int] = set()
        candidates: list[tuple[Instruction, str]] = []
        steps = 0
        while pending and steps < MAX_TRACE_STEPS * 4:
            steps += 1
            current_block, current_position = pending.pop()
            found: tuple[Instruction, str] | None = None
            while current_position - 1 >= 0:
                current_position -= 1
                ins = current_block.instructions[current_position]
                mnemonic = ins.mnemonic.lower()
                arguments = ([part.strip() for part in ins.op_str.split(",")]
                             if ins.op_str else [])
                if mnemonic in {"mov", "movabs"} and len(arguments) == 2 and "[" in arguments[0]:
                    memory = mem_operand(ins)
                    if memory is None:
                        return None
                    base, disp = memory
                    offset = self._stack_offset(function, base, disp)
                    if offset == slot_offset:
                        if "[" in arguments[1]:
                            return None
                        found = (ins, arguments[1])
                        break
                    if offset is None:
                        # A store through a pointer address: only ignore it when
                        # alias analysis proves it cannot alias the tracked
                        # frame slot; otherwise fail closed.
                        base_register = canon_reg(base)
                        if base_register:
                            locations = points_to_at(self.alias(function), ins.va,
                                                     base_register)
                            target = {stack_local(function.va, slot_offset)}
                            if must_not_alias(locations, target):
                                continue
                        return None
            if found is not None:
                candidates.append(found)
                continue
            if current_block.va in visited:
                continue
            visited.add(current_block.va)
            predecessor_list = preds.get(current_block.va, [])
            if not predecessor_list:
                # reached the function entry without a store on this path
                continue
            for predecessor in predecessor_list:
                if predecessor in blocks:
                    pending.append((blocks[predecessor],
                                    len(blocks[predecessor].instructions)))
        unique = {(ins.va): (ins, source) for ins, source in candidates}
        if len(unique) == 1:
            return next(iter(unique.values()))
        return None

    # -- public tracing -----------------------------------------------------
    def trace(self, function: FunctionCfg, at_va: int, reg: str,
              depth: int = 0, visited: frozenset[tuple[int, int, str]] | None = None) -> Origin:
        """Trace the origin of register reg at instruction at_va (backwards)."""
        reg = canon_reg(reg)
        visited = visited or frozenset()
        key = (function.va, at_va, reg)
        if key in visited:
            return _unknown(f"cyclic definition chain for {reg} at 0x{at_va:x}")
        if depth > MAX_INTERPROC_DEPTH:
            return _unknown(f"inter-procedural depth cap ({MAX_INTERPROC_DEPTH}) reached")
        visited = visited | {key}
        index = self._index(function)
        location = index.get(at_va)
        if location is None:
            return _unknown(f"instruction 0x{at_va:x} not in analyzed function {function.name}")
        block, position = location
        blocks = self.block_by_va(function)
        preds = self.predecessors(function)
        current_block, current_position = block, position
        steps: list[Step] = []
        for _ in range(MAX_TRACE_STEPS):
            found: Instruction | None = None
            while current_position - 1 >= 0:
                current_position -= 1
                candidate = current_block.instructions[current_position]
                if self._defines(candidate, reg):
                    found = candidate
                    break
            if found is None:
                predecessor_list = preds.get(current_block.va, [])
                if len(predecessor_list) == 1:
                    current_block = blocks[predecessor_list[0]]
                    current_position = len(current_block.instructions)
                    steps.append(Step(kind="predecessor_block",
                                      function=function.name, va=current_block.va,
                                      detail="continue in the unique predecessor"))
                    continue
                if not predecessor_list and reg in ARG_REGS:
                    parameter_index = ARG_REGS.index(reg)
                    steps.append(Step(kind="function_entry", function=function.name,
                                      va=function.va,
                                      detail=f"argument {parameter_index} ({reg})"))
                    return Origin(
                        kind="parameter", function_va=function.va,
                        function_name=function.name, parameter_index=parameter_index,
                        steps=steps, confidence="medium",
                        limitations=[
                            f"{reg} is argument {parameter_index} of {function.name}: "
                            "its identity/capacity is defined by each caller"
                        ],
                    )
                return _unknown(
                    f"no unique definition of {reg} before 0x{at_va:x} in "
                    f"{function.name} (predecessors={len(predecessor_list)})",
                    steps,
                )
            origin = self._classify(function, found, reg, depth, visited, steps)
            return origin
        return _unknown(f"trace step cap ({MAX_TRACE_STEPS}) reached for {reg}", steps)

    def _classify(self, function: FunctionCfg, ins: Instruction, reg: str,
                  depth: int, visited: frozenset[tuple[int, int, str]],
                  steps: list[Step]) -> Origin:
        mnemonic = ins.mnemonic.lower()
        arguments = [part.strip() for part in ins.op_str.split(",")] if ins.op_str else []

        if ins.branch in {"call", "indirect_call"}:
            if reg != "rax":
                steps.append(Step(kind="call_clobber", function=function.name,
                                  va=ins.va, detail=f"{reg} is caller-saved"))
                return _unknown(
                    f"{reg} is caller-saved and clobbered by the call at 0x{ins.va:x}; "
                    "its value after the call is not recoverable",
                    steps,
                )
            return self._return_value(function, ins, depth, visited, steps)

        if mnemonic == "lea" and len(arguments) == 2:
            memory = mem_operand(ins)
            if memory is None:
                return _unknown(f"lea at 0x{ins.va:x} has a non-simple address", steps)
            base, disp = memory
            if base == "rip":
                address = ins.va + ins.size + (disp or 0)
                steps.append(Step(kind="global_address", function=function.name,
                                  va=ins.va, detail=f"lea {reg}, [rip + {disp or 0}]"))
                return self._global_origin(address, steps)
            offset = self._stack_offset(function, base, disp)
            if offset is not None:
                steps.append(Step(kind="stack_frame_local", function=function.name,
                                  va=ins.va,
                                  detail=f"lea {reg}, [{base} {'-' if (disp or 0) < 0 else '+'} "
                                          f"0x{abs(disp or 0):x}]"))
                frame_size, frame_pointer = self.frame(function)
                capacity = -offset if offset < 0 else None
                limitations = []
                if capacity is not None:
                    limitations.append(
                        "capacity is frame geometry (frame_top - destination), an "
                        "UPPER BOUND; the DWARF object size is not analyzed in this "
                        "increment (a buffer that does not sit at the frame top is "
                        "over-estimated)"
                    )
                return Origin(
                    kind="stack_local", function_va=function.va,
                    function_name=function.name, offset=offset,
                    capacity=capacity,
                    capacity_source="frame_geometry_upper_bound" if capacity is not None else None,
                    steps=steps, limitations=limitations,
                    confidence="medium" if capacity is not None else "low",
                )
            return _unknown(f"lea at 0x{ins.va:x} targets an unmodelled base", steps)

        if mnemonic in {"mov", "movabs"} and len(arguments) == 2:
            dest_text, source_text = arguments[0], arguments[1]
            if "[" in source_text:
                memory = mem_operand(ins)
                if memory is None:
                    return _unknown(f"memory load at 0x{ins.va:x} has a complex address", steps)
                base, disp = memory
                if base in {"rbp", "rsp"}:
                    slot_offset = self._stack_offset(function, base, disp)
                    if slot_offset is None:
                        return _unknown(f"frame slot at 0x{ins.va:x} not resolvable", steps)
                    store = self._find_store(function, ins.va, slot_offset)
                    if store is None:
                        return _unknown(
                            f"frame slot [{base} {disp}] loaded at 0x{ins.va:x} has no "
                            "unique preceding store in the analyzed path (or a call/"
                            "aliasing store intervenes)",
                            steps,
                        )
                    store_ins, store_source = store
                    steps.append(Step(kind="frame_slot_spill", function=function.name,
                                      va=store_ins.va,
                                      detail=f"store of {store_source} to [{base} {disp}]"))
                    source_reg = canon_reg(store_source)
                    if source_reg not in _ALL_REGS:
                        return _unknown(
                            f"frame slot [{base} {disp}] holds a non-register value", steps)
                    steps.append(Step(kind="frame_slot_reload", function=function.name,
                                      va=ins.va, detail=f"load {reg} from [{base} {disp}]"))
                    nested = self.trace(function, store_ins.va, source_reg, depth, visited)
                    nested.steps = steps + nested.steps
                    return nested
                if base == "rip":
                    address = ins.va + ins.size + (disp or 0)
                    steps.append(Step(kind="memory_load", function=function.name,
                                      va=ins.va,
                                      detail=f"load {reg} from global 0x{address:x}"))
                    return _unknown(
                        f"value loaded from global 0x{address:x} at 0x{ins.va:x} is a "
                        "pointee, not a statically known pointer", steps)
                steps.append(Step(kind="memory_load", function=function.name,
                                  va=ins.va, detail=f"load {reg} through computed pointer"))
                return _unknown(
                    f"memory load at 0x{ins.va:x} through a computed pointer is not "
                    "statically resolvable", steps)

            immediate = _parse_int(source_text)
            if immediate is not None:
                steps.append(Step(kind="immediate", function=function.name, va=ins.va,
                                  detail=f"{reg} = {source_text}"))
                return Origin(kind="immediate", value=immediate, steps=steps,
                              confidence="high")
            source_reg = canon_reg(source_text)
            if source_reg in _ALL_REGS:
                steps.append(Step(kind="register_copy", function=function.name,
                                  va=ins.va, detail=f"{reg} <- {source_reg}"))
                nested = self.trace(function, ins.va, source_reg, depth, visited)
                nested.steps = steps + nested.steps
                return nested
            return _unknown(f"unmodelled mov source {source_text!r} at 0x{ins.va:x}", steps)

        if mnemonic == "pop":
            return _unknown(f"{reg} comes from a stack pop at 0x{ins.va:x}", steps)
        return _unknown(
            f"unmodelled definition of {reg} at 0x{ins.va:x} ({ins.mnemonic} "
            f"{ins.op_str})", steps,
        )

    def _global_origin(self, address: int, steps: list[Step]) -> Origin:
        entry = self.globals.get(address)
        if entry is None:
            return Origin(kind="global_address", address=address, steps=steps,
                          confidence="low",
                          limitations=[
                              f"global address 0x{address:x} has no exact STT_OBJECT "
                              "symbol/size match; capacity is unknown"
                          ])
        name, size = entry
        if size:
            return Origin(kind="global_object", address=address, symbol=name,
                          capacity=size, capacity_source="object_symbol_size",
                          steps=steps, confidence="high")
        return Origin(kind="global_object", address=address, symbol=name,
                      capacity=None, steps=steps, confidence="low",
                      limitations=[
                          f"global object {name} at 0x{address:x} has no st_size; "
                          "capacity is unknown"
                      ])

    def _return_value(self, function: FunctionCfg, call_ins: Instruction,
                      depth: int, visited: frozenset[tuple[int, int, str]],
                      steps: list[Step]) -> Origin:
        edge = self.site_edges.get(call_ins.va)
        if edge is None or not edge.resolved:
            return _unknown(f"call at 0x{call_ins.va:x} has no resolved target", steps)
        alloc = alloc_token(edge.callee)
        if alloc is not None:
            steps.append(Step(kind="allocation", function=function.name,
                              va=call_ins.va,
                              detail=f"rax <- return value of {alloc}()"))
            size_reg = "rcx" if self.container.format == "pe" else "rdi"
            size_origin = self.trace(function, call_ins.va, size_reg,
                                     depth + 1, visited)
            size_steps = steps + size_origin.steps
            if size_origin.kind == "immediate" and size_origin.value is not None:
                return Origin(
                    kind="heap_allocation", capacity=size_origin.value,
                    capacity_source="allocation_immediate_size",
                    steps=size_steps, confidence="medium",
                    limitations=[
                        "heap capacity is the immediate allocation size, not a "
                        "struct-member size: malloc(24) for a char data[16] member "
                        "is a documented OVER-ESTIMATE (member layout needs DWARF)"
                    ],
                )
            return _unknown(
                f"allocation at 0x{call_ins.va:x} has a non-immediate size "
                f"({size_origin.kind}); heap capacity is unknown", size_steps)
        if edge.to_va is None:
            steps.append(Step(kind="return_value", function=function.name,
                              va=call_ins.va,
                              detail=f"return value of import {edge.callee}"))
            return _unknown(
                f"rax is the return value of imported {edge.callee}: its result is "
                "not statically known", steps)
        callee = self.function_by_va.get(edge.to_va)
        if callee is None or callee.source == "plt_stub":
            return _unknown(
                f"rax is the return value of {edge.callee or hex(edge.to_va)}: the "
                "callee body is not analyzed", steps)
        steps.append(Step(kind="return_value", function=function.name, va=call_ins.va,
                          detail=f"rax <- return value of {callee.name}"))
        origins: list[Origin] = []
        for block in callee.blocks:
            if block.terminator != "ret" or not block.instructions:
                continue
            ret_ins = block.instructions[-1]
            if ret_ins.mnemonic.lower() not in {"ret", "retf"}:
                continue
            origins.append(self.trace(callee, ret_ins.va, "rax", depth + 1, visited))
        if not origins:
            return _unknown(f"callee {callee.name} has no analyzed return site", steps)
        known = [origin for origin in origins if origin.kind != "unknown"]
        if not known:
            return _unknown(
                f"callee {callee.name} returns an unknown value on every analyzed "
                "return path", steps)
        keys = {
            (origin.kind, origin.capacity, origin.capacity_source, origin.address,
             origin.symbol, origin.offset, origin.function_va)
            for origin in known
        }
        if len(keys) > 1:
            return _unknown(
                f"callee {callee.name} has multiple returns with different origins; "
                "the returned pointer origin is not unique", steps)
        if len(known) != len(origins):
            self.note(
                f"callee {callee.name}: some return paths are unknown, so the "
                "returned value is only partially resolved"
            )
        result = known[0]
        result.steps = steps + result.steps
        if len(origins) > 1:
            result.limitations.append(
                f"callee {callee.name} has {len(origins)} analyzed return sites "
                "agreeing on this origin"
            )
        return result

    # -- inter-procedural argument paths -----------------------------------
    def argument_paths(self, function: FunctionCfg, at_va: int, reg: str,
                       origin: Origin) -> list[dict[str, Any]]:
        """Resolve a parameter origin into one path per resolved caller site."""
        if origin.kind != "parameter" or origin.parameter_index is None:
            return []
        arg_reg = ARG_REGS[origin.parameter_index]
        paths: list[dict[str, Any]] = []
        seen_sites: set[int] = set()
        for edge in self.call_graph.edges:
            if not edge.resolved or edge.to_va != function.va:
                continue
            if edge.kind not in {"direct"}:
                continue
            if edge.site_va in seen_sites:
                continue
            seen_sites.add(edge.site_va)
            caller = self.function_by_va.get(edge.from_va)
            if caller is None or caller.source == "plt_stub":
                continue
            caller_origin = self.trace(caller, edge.site_va, arg_reg)
            caller_alias = points_to_at(self.alias(caller), edge.site_va, arg_reg)
            alias_relation = "unknown"
            if caller_origin.kind in {"stack_local", "global_object"}:
                if caller_origin.kind == "stack_local":
                    location = stack_local(caller.va, caller_origin.offset or 0)
                else:
                    location = Location(kind="global_object",
                                        symbol=caller_origin.symbol,
                                        address=caller_origin.address,
                                        size=caller_origin.capacity)
                valid = sets_may_alias(caller_alias, {location})
                alias_relation = "must_alias_at_callsite" if valid and must_alias(
                    caller_alias, {location}) else "may_alias_at_callsite"
            paths.append({
                "caller": {"va": caller.va, "name": caller.name},
                "call_site_va": edge.site_va,
                "call_kind": edge.kind,
                "origin": caller_origin.kind,
                "capacity": caller_origin.capacity,
                "capacity_source": caller_origin.capacity_source,
                "resolution": (
                    "resolved" if caller_origin.capacity is not None
                    else "partially_resolved" if caller_origin.kind != "unknown"
                    else "unknown"
                ),
                "confidence": caller_origin.confidence,
                "alias": {
                    "relation": alias_relation,
                    "argument_locations": [location.to_dict()
                                           for location in caller_alias],
                },
                "steps": [step.to_dict() for step in origin.steps]
                + [Step(kind="call_site", function=caller.name, va=edge.site_va,
                        detail=f"{caller.name} -> {function.name}").to_dict()]
                + [step.to_dict() for step in caller_origin.steps],
                "limitations": list(caller_origin.limitations),
            })
            if len(paths) >= MAX_PATHS_PER_SINK:
                self.note(
                    f"argument path list truncated at {MAX_PATHS_PER_SINK} call sites "
                    f"for {function.name}"
                )
                break
        return paths


# ---------------------------------------------------------------------------
# sink scan + report
# ---------------------------------------------------------------------------


@dataclass
class SinkSite:
    function: FunctionCfg
    site_va: int
    callee: str | None
    token: str
    instruction: Instruction
    edge: CallEdge


def find_copy_sinks(cfg: CfgResult, call_graph: CallGraph) -> list[SinkSite]:
    """Return every resolved call site whose callee is a known copy function."""
    function_by_va = {function.va: function for function in cfg.functions}
    indexes: dict[int, dict[int, tuple[Any, int]]] = {}
    sinks: list[SinkSite] = []
    seen: set[int] = set()
    for edge in call_graph.edges:
        if not edge.resolved or edge.site_va in seen:
            continue
        token = copy_token(edge.callee)
        if token is None:
            continue
        function = function_by_va.get(edge.from_va)
        if function is None or function.source == "plt_stub":
            continue
        index = indexes.get(function.va)
        if index is None:
            index = {}
            for block in function.blocks:
                for position, ins in enumerate(block.instructions):
                    index[ins.va] = (block, position)
            indexes[function.va] = index
        location = index.get(edge.site_va)
        if location is None:
            continue
        block, position = location
        sinks.append(SinkSite(function=function, site_va=edge.site_va,
                              callee=edge.callee, token=token,
                              instruction=block.instructions[position], edge=edge))
        seen.add(edge.site_va)
    sinks.sort(key=lambda sink: sink.site_va)
    return sinks


def _argument_register(container: ContainerInfo) -> str | None:
    if container.arch != "x86_64":
        return None
    return "rcx" if container.format == "pe" else "rdi"


def _length_register(container: ContainerInfo) -> str | None:
    if container.arch != "x86_64":
        return None
    return "rdx" if container.format != "pe" else "r8"


def _summarize_paths(context: TraceContext, paths: list[dict[str, Any]]) -> tuple[
        int | None, str | None, str, str]:
    """Return (capacity, capacity_source, agreement, resolution) over paths."""
    if not paths:
        return (None, None, "no_paths", "unknown")
    capacities = [path.get("capacity") for path in paths]
    sources = [path.get("capacity_source") for path in paths]
    origins = [path.get("origin") for path in paths]
    resolved = [capacity for capacity in capacities if capacity is not None]
    if not resolved:
        resolution = "partially_resolved" if any(
            origin != "unknown" for origin in origins) else "unknown"
        return (None, None, "no_capacity", resolution)
    if len(resolved) == len(capacities) and len(set(resolved)) == 1:
        source = sources[0] if len(set(sources)) == 1 else None
        return (resolved[0], source, "all_paths", "resolved")
    resolution = "partially_resolved"
    return (None, None, "conflict", resolution)


def analyze_crossfn(
    data: bytes,
    *,
    container: ContainerInfo | None = None,
    cfg: CfgResult | None = None,
    call_graph: CallGraph | None = None,
) -> dict[str, Any]:
    """Return the stable cross-function dataflow JSON for one image."""
    if container is None:
        container = detect_container(data)
    if cfg is None:
        cfg = build_cfg(data, container=container)
    if call_graph is None:
        call_graph = build_call_graph(data, cfg, container=container)
    globals_ = object_symbols(container, data)
    context = TraceContext(cfg, call_graph, container, globals_)
    argument_register = _argument_register(container)
    length_register = _length_register(container)
    limitations: list[str] = [
        "frame-slot store/reload forwarding does not model a callee writing the "
        "caller's analyzed frame slot through an escaped pointer (no escape "
        "analysis); calls do not invalidate a tracked slot",
        "stack capacities are frame geometry (frame_top - destination) UPPER "
        "BOUNDS unless stated otherwise; DWARF object sizes are not analyzed in "
        "this increment",
    ]
    if container.format != "elf":
        limitations.append(
            "global object sizes require ELF STT_OBJECT symbols in this increment; "
            "non-ELF global capacities are reported as unknown"
        )
    if argument_register is None:
        limitations.append(
            f"cross-function argument tracing supports x86-64 SysV only in this "
            f"increment; {container.format}/{container.arch} sinks are reported with "
            "destination.resolution=unsupported_arch"
        )

    sinks: list[dict[str, Any]] = []
    unsupported = 0
    for site in find_copy_sinks(cfg, call_graph):
        sink_limitations: list[str] = []
        alias_snapshot = context.alias(site.function)
        destination_locations = (
            points_to_at(alias_snapshot, site.site_va, argument_register)
            if argument_register else frozenset({UNKNOWN})
        )
        source_locations = (
            points_to_at(alias_snapshot, site.site_va, ARG_REGS[1])
            if argument_register else frozenset({UNKNOWN})
        )
        sink: dict[str, Any] = {
            "site_va": site.site_va,
            "callee": site.callee,
            "copy_token": site.token,
            "instruction": f"{site.instruction.mnemonic} {site.instruction.op_str}".strip(),
            "function": {"va": site.function.va, "name": site.function.name,
                         "source": site.function.source},
            "alias": {
                "destination_locations": [loc.to_dict() for loc in destination_locations],
                "destination_may_alias_anything": any(
                    loc.kind in {"unknown", "parameter"} for loc in destination_locations
                ),
                "source_locations": [loc.to_dict() for loc in source_locations],
            },
            "limitations": sink_limitations,
        }
        if argument_register is None:
            unsupported += 1
            sink["destination"] = {
                "origin": "unknown",
                "capacity": None,
                "capacity_source": None,
                "agreement": "unsupported_arch",
                "resolution": "unsupported_arch",
                "paths": [],
            }
            sink["confidence"] = "unknown"
            sink_limitations.append(
                f"no argument trace for {container.arch}; destination is not resolved"
            )
            sink["source_argument"] = {"origin": "unknown",
                                       "resolution": "unsupported_arch"}
            sinks.append(sink)
            continue

        destination_origin = context.trace(site.function, site.site_va,
                                           argument_register)
        paths: list[dict[str, Any]] = []
        if destination_origin.kind == "parameter":
            paths = context.argument_paths(site.function, site.site_va,
                                           argument_register, destination_origin)
            if not paths:
                sink_limitations.append(
                    "destination is a function parameter but no resolved caller call "
                    "site was found; capacity is unknown"
                )
            sink_limitations.extend(destination_origin.limitations)
        else:
            paths = [{
                "caller": None,
                "call_site_va": None,
                "call_kind": None,
                "origin": destination_origin.kind,
                "capacity": destination_origin.capacity,
                "capacity_source": destination_origin.capacity_source,
                "resolution": (
                    "resolved" if destination_origin.capacity is not None
                    else "partially_resolved" if destination_origin.kind != "unknown"
                    else "unknown"
                ),
                "confidence": destination_origin.confidence,
                "alias": {
                    "relation": "same_function" if destination_origin.kind != "unknown"
                    else "unknown",
                    "argument_locations": [loc.to_dict() for loc in destination_locations],
                },
                "steps": [step.to_dict() for step in destination_origin.steps],
                "limitations": list(destination_origin.limitations),
            }]
            sink_limitations.extend(destination_origin.limitations)

        capacity, capacity_source, agreement, resolution = _summarize_paths(
            context, paths)
        if agreement == "conflict":
            sink_limitations.append(
                "different resolved call paths give different destination capacities; "
                "no single capacity is claimed (call-site-dependent capacity)"
            )
        sink["destination"] = {
            "origin": destination_origin.kind if destination_origin.kind != "parameter"
            else "parameter",
            "capacity": capacity,
            "capacity_source": capacity_source,
            "agreement": agreement,
            "resolution": resolution,
            "paths": paths,
        }
        sink["confidence"] = (
            "high" if resolution == "resolved" and capacity_source == "object_symbol_size"
            else "medium" if resolution == "resolved"
            else "low" if resolution == "partially_resolved"
            else "unknown"
        )

        # source argument summary (bounded: one inter-procedural hop total)
        source_origin = context.trace(site.function, site.site_va, ARG_REGS[1])
        source_summary: dict[str, Any] = {
            "origin": source_origin.kind,
            "capacity": source_origin.capacity,
            "resolution": (
                "resolved" if source_origin.capacity is not None
                else "partially_resolved" if source_origin.kind != "unknown"
                else "unknown"
            ),
            "steps": [step.to_dict() for step in source_origin.steps],
        }
        if source_origin.kind == "parameter":
            source_paths = context.argument_paths(site.function, site.site_va,
                                                  ARG_REGS[1], source_origin)
            source_summary["caller_origins"] = [
                {"caller": path["caller"], "origin": path["origin"]}
                for path in source_paths
            ]
            sink_limitations.append(
                "the copy source pointer is caller-defined; its data length is not "
                "statically bounded (unbounded libc copy)"
            )
        elif source_origin.kind == "unknown":
            source_summary["limitations"] = list(source_origin.limitations)
        sink["source_argument"] = source_summary

        if site.token in {"memcpy", "memmove"} and length_register is not None:
            length_origin = context.trace(site.function, site.site_va, length_register)
            sink["length_argument"] = {
                "origin": length_origin.kind,
                "value": length_origin.address,
                "capacity": length_origin.capacity,
                "resolution": (
                    "resolved" if length_origin.kind in {"immediate", "global_object"}
                    else "unknown"
                ),
                "steps": [step.to_dict() for step in length_origin.steps],
                "limitations": list(length_origin.limitations),
            }
        sinks.append(sink)

    limitations.extend(context.notes)
    if not globals_:
        limitations.append(
            "no ELF STT_OBJECT symbols were recovered; global capacities are unknown"
        )
    # de-duplicate, preserving order, with a hard cap
    deduped: list[str] = []
    for text in limitations:
        if text not in deduped:
            deduped.append(text)
    limitations = deduped[:MAX_LIMITATIONS]

    origin_counts: dict[str, int] = {}
    for sink in sinks:
        origin = sink["destination"]["origin"]
        origin_counts[origin] = origin_counts.get(origin, 0) + 1
    callees: dict[str, int] = {}
    for sink in sinks:
        key = sink["copy_token"]
        callees[key] = callees.get(key, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "m2-analysis-dataflow",
        "format": container.format,
        "arch": container.arch,
        "bits": container.bits,
        "entry": container.entry,
        "sinks": sinks,
        "limitations": limitations,
        "statistics": {
            "sinks": len(sinks),
            "sinks_by_copy_token": dict(sorted(callees.items())),
            "sinks_by_destination_origin": dict(sorted(origin_counts.items())),
            "sinks_resolved_capacity": sum(
                1 for sink in sinks
                if sink["destination"].get("resolution") == "resolved"
            ),
            "sinks_conflicting_capacity": sum(
                1 for sink in sinks
                if sink["destination"].get("agreement") == "conflict"
            ),
            "sinks_unsupported_arch": unsupported,
            "paths_total": sum(len(sink["destination"].get("paths", []))
                               for sink in sinks),
            "global_object_symbols": len(globals_),
            "cfg_functions": cfg.statistics.get("functions"),
            "cfg_limitations_not_inlined": len(cfg.limitations),
            "callgraph_edges": len(call_graph.edges),
            "callgraph_unresolved_edges": call_graph.statistics.get("edges_unresolved"),
        },
    }
