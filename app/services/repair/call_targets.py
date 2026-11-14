"""Selective call targets for target-function repair experiments.

The default assembly path is leaf-only.  This module is used only by the
target-mode benchmark: it discovers the *actual* direct calls already made by
the target function (PLT imports and named internal callees) and exposes their
exact virtual addresses to the model.  A whitelisted call must target one of
those addresses; indirect calls and arbitrary symbols remain forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from capstone import (
    CS_ARCH_ARM64,
    CS_ARCH_X86,
    CS_MODE_32,
    CS_MODE_64,
    CS_OP_IMM,
    Cs,
)

#: Imported functions that may be reintroduced by a repair.  The target must
#: already call the import (or a PLT entry) in the original function; this list
#: only narrows what can be surfaced from the binary, it is not a global allow.
ALLOWED_IMPORT_NAMES = frozenset({
    "strcpy", "strncpy", "strcat", "stpcpy", "memcpy", "memmove", "memset",
    "puts", "printf", "sprintf", "snprintf", "fputs", "fprintf",
    "strlen", "malloc", "calloc", "realloc", "free", "exit", "_exit", "abort",
    "read", "write", "printLine",
})

#: Cap on the number of call targets exposed to one prompt.
MAX_CALL_TARGETS = 16


@dataclass(frozen=True)
class AllowedCall:
    name: str
    target_va: int
    source: str  # "import" | "direct"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_va": hex(self.target_va),
            "source": self.source,
        }


def _disassembler(arch: str) -> Cs:
    if arch == "i386":
        md = Cs(CS_ARCH_X86, CS_MODE_32)
    elif arch == "x86_64":
        md = Cs(CS_ARCH_X86, CS_MODE_64)
    elif arch == "arm64":
        md = Cs(CS_ARCH_ARM64, 0)
    else:
        raise ValueError(f"unsupported architecture for call discovery: {arch}")
    md.detail = True
    return md


def _direct_target(ins: Any, arch: str) -> int | None:
    mnemonic = ins.mnemonic.lower()
    if arch in {"i386", "x86_64"}:
        if mnemonic != "call":
            return None
    elif arch == "arm64":
        if mnemonic not in {"bl", "b"}:
            return None
        # A tail branch to a named callee is also a call-like edge in the
        # original function; only exact immediate targets are considered.
        if mnemonic == "b":
            return None
    for operand in ins.operands:
        if operand.type == CS_OP_IMM:
            return int(operand.imm)
    return None


def discover_allowed_calls(
    data: bytes,
    container: Any,
    function_va: int,
    *,
    max_targets: int = MAX_CALL_TARGETS,
) -> list[AllowedCall]:
    """Return only calls already present in the original target function.

    The function body is disassembled read-only for up to 512 bytes.  PLT
    imports must be in :data:`ALLOWED_IMPORT_NAMES`; internal targets must have
    a symbol name.  Non-mapped targets and indirect calls are omitted.
    """
    offset = container.va_to_offset(int(function_va))
    if offset is None:
        return []
    raw = data[offset:offset + 512]
    md = _disassembler(str(container.arch))
    imports = getattr(container, "imports", {}) or {}
    symbols = getattr(container, "symbols", {}) or {}
    found: dict[int, AllowedCall] = {}
    for ins in md.disasm(raw, int(function_va)):
        if ins.mnemonic.lower() in {"ret", "retq"}:
            break
        target = _direct_target(ins, str(container.arch))
        if target is None:
            continue
        target = int(target)
        if target in imports:
            name = str(imports[target])
            if name.rsplit("@", 1)[0] not in ALLOWED_IMPORT_NAMES:
                continue
            found.setdefault(target, AllowedCall(name=name, target_va=target, source="import"))
            continue
        name = str(symbols.get(target) or "")
        if not name:
            # A direct call to an executable address with no symbol is still a
            # call the original function makes.  Expose its exact address so
            # target repair can preserve it; this is not a general symbol allow.
            section = container.section_at(target)
            if section is None or not section.executable:
                continue
            name = f"target_{target:x}"
        if name.startswith(("plt.", "j_", "thunk.")):
            continue
        found.setdefault(target, AllowedCall(name=name, target_va=target, source="direct"))
        if len(found) >= max_targets:
            break
    return sorted(found.values(), key=lambda item: (item.source, item.target_va))


def target_set(calls: Iterable[AllowedCall]) -> frozenset[int]:
    return frozenset(int(call.target_va) for call in calls)
