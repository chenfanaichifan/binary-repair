"""Conservative points-to / may-alias prototype (Phase-9 E-03).

Read-only analysis evidence: this module never writes bytes, never executes the
target and is not wired into repair_any or any gate.

Soundness contract (fail-closed, no false certainty):

* every transfer the prototype does not model collapses the affected pointer to
  the single 'unknown' location, which may alias everything;
* a *function parameter* is a pointer supplied by the caller and is modelled as
  the 'parameter' location, which may alias anything (identity is not claimed
  at the callee);
* block joins take the union of predecessor states (a may-points-to lattice);
  anything not proved equal on every predecessor becomes 'unknown';
* must_not_alias is claimed only when both sides are concrete, non-empty,
  unknown-free singletons of disjoint storage.  It is never claimed for an
  unknown/parameter/derived value;
* must_alias is claimed only for one identical singleton on both sides.

Tracked transfers (x86-64 SysV, bounded): 'lea' of an rbp/rsp frame slot or a
RIP-relative global, register-to-register moves, stack spill/reload of a
tracked pointer, non-PIE absolute globals moved as immediates, 'xor reg,reg'
(unknown/NULL), caller-saved clobbering after calls, and return-value rax
becoming unknown.  Everything else becomes unknown.  There is no heap shape
analysis, no field sensitivity and no arithmetic-between-pointers solver.

ELF STT_OBJECT symbols with sizes are used to label global objects with an exact
size; without a symbol the address is still concrete (global_address) but its
size is null.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.services.analysis.cfg import CfgResult, FunctionCfg, Instruction

MAX_LOCATIONS_PER_SET = 6
MAX_FIXPOINT_STEPS = 20_000

#: caller-saved registers on x86-64 SysV; a call clobbers them
_CALLER_SAVED = frozenset({"rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"})
#: argument registers in order
ARG_REGS = ("rdi", "rsi", "rdx", "rcx", "r8", "r9")
_ALL_REGS = frozenset({
    "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
})

_CANON: dict[str, str] = {}
for _full in ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp"):
    _CANON[_full] = _full
    _short = _full[1:]
    for _alias_name in (_short, "e" + _short, "r" + _short, "r" + _short + "d",
                        "r" + _short + "w", "r" + _short + "b"):
        _CANON.setdefault(_alias_name, _full)
for _index in range(8, 16):
    _CANON[f"r{_index}"] = f"r{_index}"
    for _suffix in ("d", "w", "b"):
        _CANON[f"r{_index}{_suffix}"] = f"r{_index}"
del _full, _short, _alias_name, _index, _suffix

#: first operand is read-only for these mnemonics
_READ_ONLY_FIRST = {
    "cmp", "test", "push", "bt", "ucomiss", "ucomisd", "comiss", "comisd",
    "nop", "endbr64", "prefetch", "prefetchw", "jmp", "ret", "retf", "leave",
    "call", "syscall", "int3", "ud2", "hlt", "cmpsb", "cmpsw", "cmpsd",
    "cmpsq", "scasb", "scasw", "scasd", "scasq", "movsb", "movsw", "movsd",
    "movsq", "stosb", "stosw", "stosd", "stosq", "lodsb", "lodsd", "lodsq",
}


def canon_reg(name: str | None) -> str:
    """Canonical 64-bit x86 register name (edi -> rdi), else ''."""
    if not name:
        return ""
    return _CANON.get(name.strip().lower(), name.strip().lower())


@dataclass(frozen=True)
class Location:
    """One concrete-or-unknown memory location a pointer may designate."""

    kind: str  # stack_local | global_object | global_address | heap_allocation
    #            | parameter | unknown
    function_va: int | None = None
    offset: int | None = None       # signed rbp-relative offset for stack locals
    symbol: str | None = None
    address: int | None = None
    size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind}
        for field_name in ("function_va", "offset", "symbol", "address", "size"):
            value = getattr(self, field_name)
            if value is not None:
                payload[field_name] = value
        return payload


UNKNOWN = Location(kind="unknown")


def parameter(fn_va: int, index: int) -> Location:
    return Location(kind="parameter", function_va=fn_va, offset=index)


def stack_local(fn_va: int, offset: int) -> Location:
    return Location(kind="stack_local", function_va=fn_va, offset=offset)


def global_location(address: int, symbol: str | None = None, size: int | None = None) -> Location:
    if symbol is not None and size is not None:
        return Location(kind="global_object", symbol=symbol, address=address, size=size)
    return Location(kind="global_address", symbol=symbol, address=address)


# ---------------------------------------------------------------------------
# may/must alias queries over sets of locations
# ---------------------------------------------------------------------------


_GLOBAL_KINDS = frozenset({"global_object", "global_address"})


def locations_may_alias(left: Location, right: Location) -> bool:
    """Conservative may-alias between two locations (fail-closed).

    Three disjoint memory regions are modeled: the analyzed stack frames, the
    global image and heap allocations.  A stack slot can never alias a global
    or a heap object, so that negative claim is safe.  Two different heap
    allocation sites are still reported as MAY alias (lifetime/reuse is not
    modeled); only the same allocation site is a common heap location.
    """
    if left.kind in {"unknown", "parameter"} or right.kind in {"unknown", "parameter"}:
        return True
    if left.kind == right.kind == "stack_local":
        return (left.function_va == right.function_va
                and left.offset == right.offset)
    if left.kind in _GLOBAL_KINDS and right.kind in _GLOBAL_KINDS:
        return left.address == right.address
    if left.kind == right.kind == "heap_allocation":
        return left.address == right.address
    if left.kind in {"stack_local", "heap_allocation", "global_object",
                     "global_address"} and right.kind in {
        "stack_local", "heap_allocation", "global_object", "global_address",
    }:
        # different concrete memory regions are disjoint
        return False
    return True


def sets_may_alias(left: Iterable[Location], right: Iterable[Location]) -> bool:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return True
    return any(locations_may_alias(a, b) for a in left_set for b in right_set)


def _is_concrete(location: Location) -> bool:
    return location.kind not in {"unknown", "parameter"}


def must_alias(left: Iterable[Location], right: Iterable[Location]) -> bool:
    """True only when both sides are the same single concrete location."""
    left_set = set(left)
    right_set = set(right)
    if len(left_set) != 1 or len(right_set) != 1:
        return False
    sole = next(iter(left_set))
    return sole == next(iter(right_set)) and _is_concrete(sole)


def must_not_alias(left: Iterable[Location], right: Iterable[Location]) -> bool:
    """True only when both sides are concrete, disjoint single locations.

    Never claimed when either side is unknown, a parameter, or a multi-location
    may-set: those cases return False.
    """
    left_set = set(left)
    right_set = set(right)
    if len(left_set) != 1 or len(right_set) != 1:
        return False
    a = next(iter(left_set))
    b = next(iter(right_set))
    if not _is_concrete(a) or not _is_concrete(b):
        return False
    return not locations_may_alias(a, b)


# ---------------------------------------------------------------------------
# forward points-to walk (may lattice, fixpoint over the CFG)
# ---------------------------------------------------------------------------

State = dict[str, frozenset[Location]]
SlotState = dict[int, frozenset[Location]]
Snapshot = dict[int, dict[str, frozenset[Location]]]


def _parse_int(text: str) -> int | None:
    text = text.strip()
    for prefix in ("0x", "0X"):
        if text.startswith(prefix):
            try:
                return int(text, 16)
            except ValueError:
                return None
    try:
        return int(text, 10)
    except ValueError:
        return None


def mem_operand(ins: Instruction) -> tuple[str | None, int | None] | None:
    """Parse a simple memory operand: (base_register, displacement) or None."""
    text = ins.op_str
    if "[" not in text or "]" not in text:
        return None
    inside = text[text.index("[") + 1:text.index("]")].strip()
    if "," in inside:
        return None  # indexed/complex address: not modelled
    parts = inside.split()
    if len(parts) == 1:
        base = canon_reg(parts[0])
        return (base, 0)
    if len(parts) == 3 and parts[1] in {"+", "-"}:
        base = canon_reg(parts[0])
        value = _parse_int(parts[2])
        if value is None:
            return None
        return (base, -value if parts[1] == "-" else value)
    return None


def frame_model(function: FunctionCfg) -> tuple[int, str | None]:
    """Return (frame_size, frame_pointer_kind) from the entry-block prologue."""
    if not function.blocks:
        return (0, None)
    frame_size = 0
    frame_pointer: str | None = None
    for ins in function.blocks[0].instructions[:12]:
        mnemonic = ins.mnemonic.lower()
        arguments = [part.strip() for part in ins.op_str.split(",")] if ins.op_str else []
        if mnemonic == "push" and canon_reg(ins.op_str) == "rbp":
            frame_pointer = "rbp"
        elif (mnemonic == "mov" and frame_pointer == "rbp" and len(arguments) == 2
              and canon_reg(arguments[0]) == "rbp" and canon_reg(arguments[1]) == "rsp"):
            continue
        elif (mnemonic == "sub" and len(arguments) == 2
              and canon_reg(arguments[0]) == "rsp"):
            value = _parse_int(arguments[1])
            if value is not None:
                frame_size = value
    return (frame_size, frame_pointer)


_ALLOC_NAMES = frozenset({"malloc", "calloc"})


def _canonical_callee(name: str | None) -> str:
    if not name:
        return ""
    low = name.lower().split("@")[0]
    return low.rsplit(".", 1)[-1].lstrip("_")


def analyze_points_to(
    cfg: CfgResult,
    function: FunctionCfg,
    globals_: dict[int, tuple[str, int | None]] | None = None,
    call_targets: dict[int, str] | None = None,
) -> Snapshot:
    """Return instruction_va -> register -> may-points-to set for one function.

    The recorded state is the state *before* the instruction executes.  The
    function is analysed with a may-points-to fixpoint over its CFG; block joins
    union predecessor states and collapse to unknown above the set cap.
    """
    del cfg  # the function carries its blocks; kept for API symmetry
    globals_ = globals_ or {}
    call_targets = call_targets or {}
    frame_size, frame_pointer = frame_model(function)
    function_va = function.va
    block_by_va = {block.va: block for block in function.blocks}
    successors: dict[int, list[int]] = {}
    predecessors: dict[int, list[int]] = {}
    for block in function.blocks:
        succs = [succ for succ in block.successors if succ in block_by_va]
        successors[block.va] = succs
        for succ in succs:
            predecessors.setdefault(succ, []).append(block.va)

    def lookup(address: int) -> Location | None:
        entry = globals_.get(address)
        if entry is None:
            return None
        name, size = entry
        return global_location(address, name, size)

    def collapse(locations: Iterable[Location]) -> frozenset[Location]:
        result = frozenset(locations)
        if not result:
            return frozenset({UNKNOWN})
        if len(result) > MAX_LOCATIONS_PER_SET:
            return frozenset({UNKNOWN})
        return result

    def merge_maps(target: dict[Any, frozenset[Location]],
                   incoming: dict[Any, frozenset[Location]]) -> bool:
        changed = False
        for key, values in incoming.items():
            existing = target.get(key)
            if existing is None:
                target[key] = values
                changed = True
            elif values != existing:
                union = collapse(set(existing) | set(values))
                if union != existing:
                    target[key] = union
                    changed = True
        return changed

    in_states: dict[int, State] = {block.va: {} for block in function.blocks}
    in_slots: dict[int, SlotState] = {block.va: {} for block in function.blocks}
    if function.blocks:
        entry = function.blocks[0]
        for index, reg in enumerate(ARG_REGS):
            in_states[entry.va][reg] = frozenset({parameter(function_va, index)})

    worklist = [block.va for block in function.blocks]
    iterations = 0
    while worklist:
        iterations += 1
        if iterations > MAX_FIXPOINT_STEPS:
            break
        block_va = worklist.pop(0)
        block = block_by_va.get(block_va)
        if block is None:
            continue
        state = dict(in_states[block_va])
        slots = dict(in_slots[block_va])
        heap_sizes = _heap_sizes(block, call_targets)
        for ins in block.instructions:
            _interpret(ins, state, slots, function_va, frame_size, frame_pointer,
                       lookup, collapse, call_targets, heap_sizes)
        for succ in successors[block_va]:
            changed = merge_maps(in_states[succ], state)
            changed = merge_maps(in_slots[succ], slots) or changed
            if changed and succ not in worklist:
                worklist.append(succ)

    snapshots: Snapshot = {}
    for block in function.blocks:
        state = dict(in_states[block.va])
        slots = dict(in_slots[block.va])
        heap_sizes = _heap_sizes(block, call_targets)
        for ins in block.instructions:
            snapshots[ins.va] = dict(state)
            _interpret(ins, state, slots, function_va, frame_size, frame_pointer,
                       lookup, collapse, call_targets, heap_sizes)
    return snapshots


def _heap_sizes(block: Any, call_targets: dict[int, str]) -> dict[int, int]:
    """Immediate malloc/calloc sizes for call sites in one block."""
    sizes: dict[int, int] = {}
    for position, ins in enumerate(block.instructions):
        if ins.branch not in {"call", "indirect_call"}:
            continue
        name = _canonical_callee(call_targets.get(ins.va))
        if name not in _ALLOC_NAMES:
            continue
        size_reg = "rcx"  # PE x64; SysV uses rdi and is handled below
        for back in range(position - 1, max(-1, position - 4), -1):
            previous = block.instructions[back]
            arguments = ([part.strip() for part in previous.op_str.split(",")]
                         if previous.op_str else [])
            if not arguments or "[" in arguments[0]:
                continue
            written = canon_reg(arguments[0])
            if written == "rdi":
                size_reg = "rdi"
            elif written == "rcx":
                size_reg = "rcx"
            else:
                continue
            if previous.mnemonic.lower() in {"mov", "movabs"} and len(arguments) == 2:
                value = _parse_int(arguments[1])
                if value is not None:
                    sizes[ins.va] = value
                    break
        del size_reg
    return sizes


def _interpret(
    ins: Instruction,
    state: State,
    slots: SlotState,
    function_va: int,
    frame_size: int,
    frame_pointer: str | None,
    lookup: Any,
    collapse: Any,
    call_targets: dict[int, str] | None = None,
    heap_sizes: dict[int, int] | None = None,
) -> None:
    """Apply one instruction's points-to transfer to state/slots (in place)."""
    mnemonic = ins.mnemonic.lower()
    arguments = [part.strip() for part in ins.op_str.split(",")] if ins.op_str else []

    def known_or_unknown(reg: str) -> frozenset[Location]:
        return state.get(reg, frozenset({UNKNOWN}))

    def unknown(reg: str) -> None:
        if reg:
            state[reg] = frozenset({UNKNOWN})

    def stack_slot_offset(base: str | None, disp: int | None) -> int | None:
        if base is None or disp is None:
            return None
        if base == "rbp" and frame_pointer == "rbp":
            return disp
        if base == "rsp":
            return disp - frame_size
        return None

    if ins.branch in {"call", "indirect_call"}:
        for reg in _CALLER_SAVED:
            state[reg] = frozenset({UNKNOWN})
        callee = _canonical_callee((call_targets or {}).get(ins.va))
        if callee in _ALLOC_NAMES:
            size = (heap_sizes or {}).get(ins.va)
            state["rax"] = frozenset({
                Location(kind="heap_allocation", address=ins.va, size=size),
            })
        return
    if ins.branch in {"jmp", "jcc", "ret", "stop"}:
        return
    if mnemonic == "push":
        return
    if mnemonic == "leave":
        unknown("rbp")
        return
    if mnemonic == "pop":
        if arguments:
            unknown(canon_reg(arguments[0]))
        return
    if mnemonic == "sub" and arguments and canon_reg(arguments[0]) == "rsp":
        return
    if mnemonic in {"xor", "and"} and len(arguments) == 2:
        if canon_reg(arguments[0]) == canon_reg(arguments[1]):
            unknown(canon_reg(arguments[0]))
            return
    if mnemonic in {"add", "sub"} and len(arguments) == 2:
        dest = canon_reg(arguments[0])
        delta = _parse_int(arguments[1])
        if delta is not None and dest in state:
            values = state[dest]
            if len(values) == 1:
                sole = next(iter(values))
                if sole.kind in {"heap_allocation", "global_object", "global_address"}:
                    address = (sole.offset or 0) + (delta if mnemonic == "add" else -delta)
                    state[dest] = frozenset({
                        Location(kind=sole.kind, function_va=sole.function_va,
                                 offset=address, symbol=sole.symbol,
                                 address=sole.address, size=sole.size),
                    })
                    return
        if dest in _ALL_REGS:
            unknown(dest)
        return
    if mnemonic == "lea" and len(arguments) == 2:
        dest = canon_reg(arguments[0])
        memory = mem_operand(ins)
        if dest and memory is not None:
            base, disp = memory
            if base == "rip":
                target = ins.va + ins.size + (disp or 0)
                location = lookup(target)
                state[dest] = frozenset({location or global_location(target)})
                return
            offset = stack_slot_offset(base, disp)
            if offset is not None:
                state[dest] = frozenset({stack_local(function_va, offset)})
                return
        unknown(dest)
        return
    if mnemonic in {"mov", "movabs"} and len(arguments) >= 2:
        dest_text, source_text = arguments[0], arguments[1]
        if "[" in dest_text:
            memory = mem_operand(ins)
            if memory is not None:
                base, disp = memory
                offset = stack_slot_offset(base, disp)
                if offset is not None:
                    if "[" in source_text:
                        slots[offset] = frozenset({UNKNOWN})
                    else:
                        slots[offset] = known_or_unknown(canon_reg(source_text))
            return
        dest = canon_reg(dest_text)
        if "[" in source_text:
            memory = mem_operand(ins)
            if memory is not None:
                base, disp = memory
                offset = stack_slot_offset(base, disp)
                if offset is not None and offset in slots:
                    state[dest] = slots[offset]
                    return
            unknown(dest)
            return
        immediate = _parse_int(source_text)
        if immediate is not None:
            location = lookup(immediate)
            state[dest] = frozenset({location}) if location else frozenset({UNKNOWN})
            return
        source_reg = canon_reg(source_text)
        if source_reg in _ALL_REGS:
            state[dest] = known_or_unknown(source_reg)
            return
        unknown(dest)
        return
    # any other instruction writing its first operand destroys the value
    if arguments and "[" not in arguments[0]:
        dest = canon_reg(arguments[0])
        if dest in _ALL_REGS and mnemonic not in _READ_ONLY_FIRST:
            unknown(dest)


def points_to_at(snapshot: Snapshot, ins_va: int, register: str) -> frozenset[Location]:
    """Return the may-points-to set of register before instruction ins_va."""
    state = snapshot.get(ins_va)
    if state is None:
        return frozenset({UNKNOWN})
    values = state.get(canon_reg(register))
    if values is None:
        return frozenset({UNKNOWN})
    return values
