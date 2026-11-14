"""Conservative ABI checks for injected x86-64 assembly blocks.

These checks are *not* the acceptance owner.  They reject blocks whose control
flow/stack discipline is demonstrably inconsistent before the native gate; the
deterministic gate remains the authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from capstone import CS_ARCH_ARM64, CS_ARCH_X86, CS_MODE_32, CS_MODE_64, CS_OP_IMM, Cs

CALLEE_SAVED_X86 = frozenset({"rbx", "rbp", "r12", "r13", "r14", "r15"})
FN_ENTRY_MOD16 = 8  # System V AMD64: RSP % 16 == 8 at function entry


@dataclass
class AbiFinding:
    code: str
    severity: str  # fatal | warning | unknown
    detail: str
    address: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail, "address": self.address}


@dataclass
class AbiReport:
    ok: bool
    findings: list[AbiFinding] = field(default_factory=list)

    @property
    def fatal(self) -> list[AbiFinding]:
        return [f for f in self.findings if f.severity == "fatal"]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "fatal": len(self.fatal),
                "findings": [f.to_dict() for f in self.findings]}


def _disasm(code: bytes, arch: str):
    if arch == "i386":
        md = Cs(CS_ARCH_X86, CS_MODE_32)
    elif arch == "x86_64":
        md = Cs(CS_ARCH_X86, CS_MODE_64)
    elif arch == "arm64":
        md = Cs(CS_ARCH_ARM64, 0)
    else:
        return None
    md.detail = True
    return md


def _operand_regs(ins: Any) -> list[str]:
    names: list[str] = []
    for op in getattr(ins, "operands", []):
        try:
            if op.type == 1:  # CS_OP_REG
                names.append(ins.reg_name(op.reg).lower())
        except Exception:  # noqa: BLE001
            continue
    return names


def check_x86_64(code: bytes, *, allowed_call_targets: Iterable[int] = ()) -> AbiReport:
    """CFG-aware stack/return/callee-saved discipline for an x86-64 block."""
    md = _disasm(code, "x86_64")
    if md is None:
        return AbiReport(False, [AbiFinding("unsupported_arch", "unknown", "not x86-64")])
    instructions = list(md.disasm(code, 0))
    if not instructions:
        return AbiReport(False, [AbiFinding("no_instructions", "fatal", "empty block")])
    by_address = {int(ins.address): index for index, ins in enumerate(instructions)}
    allowed = {int(value) for value in allowed_call_targets}
    findings: list[AbiFinding] = []
    seen_findings: set[tuple[str, str, str | None]] = set()

    def add(code_name: str, severity: str, detail: str,
            address: int | None = None) -> None:
        key = (code_name, severity, str(address))
        if key not in seen_findings:
            seen_findings.add(key)
            findings.append(AbiFinding(code_name, severity, detail,
                                       hex(address) if address is not None else None))

    # Worklist state: instruction index, RSP depth, pushed callee-saved set,
    # and whether the stack state is unknown beyond this point.
    from collections import deque
    queue = deque([(0, 0, frozenset(), False)])
    visited: dict[int, tuple[int, frozenset[str], bool]] = {}
    saw_ret = False
    while queue:
        index, depth, pushed, unknown = queue.popleft()
        if index < 0 or index >= len(instructions):
            continue
        state = (depth, pushed, unknown)
        previous = visited.get(index)
        if previous is not None:
            if previous == state:
                continue
            # A join with different stack facts is not provably wrong here;
            # mark it unknown rather than emitting a false fatal.
            if previous[0] == depth and previous[1] == pushed:
                continue
            depth, pushed, unknown = previous[0], previous[1], True
            if previous[2]:
                unknown = True
        visited[index] = (depth, pushed, unknown)
        ins = instructions[index]
        mnemonic = ins.mnemonic.lower()
        regs = _operand_regs(ins)
        next_index = index + 1

        def enqueue(target_index: int, ndepth: int, npushed: frozenset[str],
                    nunknown: bool) -> None:
            if 0 <= target_index < len(instructions):
                queue.append((target_index, ndepth, npushed, nunknown))

        if mnemonic == "push":
            ndepth = depth - 8
            npushed = pushed
            if regs:
                npushed = pushed | {regs[0]}
            enqueue(next_index, ndepth, frozenset(npushed), unknown)
            continue
        if mnemonic == "pop":
            ndepth = depth + 8
            npushed = pushed - ({regs[0]} if regs else set())
            enqueue(next_index, ndepth, frozenset(npushed), unknown)
            continue
        if mnemonic in {"sub", "add"} and regs and regs[0] == "rsp":
            op = ins.operands[1] if len(ins.operands) > 1 else None
            if op is not None and op.type == CS_OP_IMM:
                delta = int(op.imm)
                ndepth = depth + (delta if mnemonic == "sub" else -delta)
                enqueue(next_index, ndepth, frozenset(pushed), unknown)
            else:
                enqueue(next_index, depth, frozenset(pushed), True)
            continue
        if mnemonic == "leave":
            enqueue(next_index, 0, frozenset(), unknown)
            continue
        if mnemonic == "call":
            target = None
            for op in ins.operands:
                if op.type == CS_OP_IMM:
                    target = int(op.imm)
                    break
            if target is None or (allowed and target not in allowed):
                add("call_target_not_allowed", "fatal",
                    f"call target {target} not in allowed targets", ins.address)
            if unknown:
                add("stack_alignment_unknown", "warning",
                    "call reached with an unknown RSP adjustment", ins.address)
            elif (FN_ENTRY_MOD16 + depth) % 16 != 0:
                add("stack_misaligned_before_call", "fatal",
                    f"RSP has depth {depth} bytes at call; entry RSP%16=8 "
                    "requires an 8-byte adjustment before a call", ins.address)
            enqueue(next_index, depth, frozenset(pushed), unknown)
            continue
        if mnemonic == "ret":
            saw_ret = True
            if not unknown and depth != 0:
                add("rsp_not_restored", "fatal",
                    f"ret with RSP depth {depth} (entry depth 0 expected)", ins.address)
            if pushed:
                add("callee_saved_not_restored", "fatal",
                    "ret while pushed callee-saved registers remain: "
                    + ", ".join(sorted(pushed)), ins.address)
            continue
        if mnemonic == "jmp":
            target = None
            for op in ins.operands:
                if op.type == CS_OP_IMM:
                    target = int(op.imm)
                    break
            if target is None or target not in by_address:
                add("branch_target_unknown", "warning",
                    f"jmp target {target} is outside the block", ins.address)
            else:
                enqueue(by_address[target], depth, frozenset(pushed), unknown)
            continue
        if mnemonic.startswith("j") and mnemonic != "jmp":
            target = None
            for op in ins.operands:
                if op.type == CS_OP_IMM:
                    target = int(op.imm)
                    break
            enqueue(next_index, depth, frozenset(pushed), unknown)
            if target is not None and target in by_address:
                enqueue(by_address[target], depth, frozenset(pushed), unknown)
            else:
                add("branch_target_unknown", "warning",
                    f"conditional branch target {target} is outside the block",
                    ins.address)
            continue
        # Callee-saved registers must be saved if written.  Only inspect the
        # first operand as a conservative destination approximation.
        if regs and regs[0] in CALLEE_SAVED_X86 and regs[0] not in pushed:
            if mnemonic in {"mov", "lea", "xor", "add", "sub", "and", "or",
                            "shl", "shr", "sar", "inc", "dec", "imul"}:
                add("callee_saved_used", "warning",
                    f"{regs[0]} is written without an observed push", ins.address)
        enqueue(next_index, depth, frozenset(pushed), unknown)

    if not saw_ret:
        add("no_ret", "fatal", "block has no ret")
    fatal = any(f.severity == "fatal" for f in findings)
    return AbiReport(not fatal, findings)


def check_block(code: bytes, arch: str, *, allowed_call_targets: Iterable[int] = ()) -> AbiReport:
    if arch == "x86_64":
        return check_x86_64(code, allowed_call_targets=allowed_call_targets)
    if arch == "i386":
        md = _disasm(code, "i386")
        if md is None:
            return AbiReport(False, [AbiFinding("unsupported_arch", "unknown", "i386 unavailable")])
        return AbiReport(True, [AbiFinding("abi_check_not_implemented", "unknown",
                                            "i386 ABI checks are not implemented")])
    return AbiReport(True, [AbiFinding("abi_check_not_implemented", "unknown",
                                        f"ABI checks are not implemented for {arch}")])
