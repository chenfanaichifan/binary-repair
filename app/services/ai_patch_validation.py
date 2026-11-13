"""Validate AI-authored binary patches before they become a candidate.

Route two lets the model answer with raw machine code (a bounded-copy guard
that must be injected into a new executable block) or with in-place byte edits
(clamping a copy-length immediate).  Those bytes are untrusted:

* injected machine code must decode completely with Capstone for the container
  architecture, may only use the closed instruction allowlist below, and must
  end with an unconditional terminator instead of falling out of the block;
* calls, system-call/privileged instructions and indirect jumps are refused,
  and every direct branch must target the injected block itself;
* the original call site must really be a direct ``call``/``bl`` that the
  writer's redirection primitive can rewrite, and the injected block must be
  encodable from that call site;
* in-place edits must be same-length rewrites of bytes inside an executable
  section, with ``before_hex`` matching the original file exactly;
* the candidate image must reparse as the same container format and
  architecture.

Everything fails closed: a rejection returns ``patched=None`` and a non-empty
``error``; the caller never receives a partially patched image.  This module
performs static validation only -- it executes nothing and does not replace
the deterministic/runtime gate.
"""
from __future__ import annotations

import re
import struct
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
from capstone.arm64 import ARM64_OP_IMM
from capstone.x86 import X86_OP_IMM, X86_OP_REG

from app.services.containers import ContainerInfo, detect_container
from app.services.repair.analyzer import Sink
from app.services.repair.writer import _inject_blob, _redirect_call

SCHEMA_VERSION = 1
MAX_CODE_BYTES = 4096
MAX_EDITS = 16
MAX_EDIT_BYTES = 256

GUARD_KINDS = frozenset({"unbounded_copy"})
IMMEDIATE_KINDS = frozenset({
    "immediate_length",
    "memcpy_length",
    "syscall_length",
    "checked_copy",
})

_CONTAINER_FORMATS = frozenset({"pe", "elf", "macho", "macho-fat"})
_ARCH_DECODERS = {
    "x86_64": (CS_ARCH_X86, CS_MODE_64),
    "i386": (CS_ARCH_X86, CS_MODE_32),
    "arm64": (CS_ARCH_ARM64, CS_MODE_ARM),
}

_X86_JCC = frozenset({
    "je", "jne", "jz", "jnz", "ja", "jae", "jb", "jbe", "jc", "jnc",
    "jg", "jge", "jl", "jle", "jo", "jno", "js", "jns", "jp", "jnp",
    "jpe", "jpo", "jcxz", "jecxz", "jrcxz",
    "jna", "jnae", "jnb", "jnbe", "jng", "jnge", "jnl", "jnle",
})
_X86_ALLOWED = frozenset({
    "mov", "movabs", "movzx", "movsx", "movsxd", "lea",
    "push", "pop", "add", "sub", "and", "or", "xor", "cmp", "test",
    "inc", "dec", "jmp", "ret", "leave", "nop",
    "shl", "shr", "sar", "xchg", "not", "neg",
}) | _X86_JCC
_X86_DENIED = frozenset({
    "call", "syscall", "sysenter", "sysexit", "sysret", "sysretq",
    "sysretl", "int", "int3", "into", "hlt", "cli", "sti", "in", "ins",
    "outs", "out", "wrmsr", "rdmsr", "iret", "iretd", "iretq", "ud2",
    "swapgs", "vmcall", "vmlaunch", "vmresume", "vmxoff", "vmxon",
    "lgdt", "lidt", "lldt", "ltr", "lret", "lretq", "rsm", "cpuid",
    "rdtsc", "rdtscp", "wbinvd", "invd", "clts", "monitor", "mwait",
    "xbegin", "xend", "xtest", "rdfsbase", "rdgsbase", "wrfsbase",
    "wrgsbase",
})
_PRIVILEGED_X86_REG = re.compile(r"^(?:cr|dr)\d+$")

_ARM64_BRANCHES = frozenset({"b", "cbz", "cbnz"})
_ARM64_LOAD_STORE = frozenset({
    "ldr", "str", "ldrb", "strb", "ldrh", "strh", "ldrsb", "ldrsh",
    "ldrsw", "ldur", "stur", "ldurb", "sturb", "ldurh", "sturh",
    "ldursb", "ldursh", "ldursw", "ldp", "stp", "ldnp", "stnp",
})
_ARM64_ALLOWED = frozenset({
    "mov", "movz", "movk", "add", "sub", "cmp", "and", "orr", "eor",
    "lsl", "lsr", "b", "ret", "nop", "cbz", "cbnz",
}) | _ARM64_LOAD_STORE
_ARM64_DENIED = frozenset({
    "bl", "blr", "br", "svc", "hvc", "smc", "brk", "hlt", "eret",
    "eretab", "drps", "msr", "mrs", "sys", "sysl", "at", "dc", "ic",
    "tlbi", "dcps1", "dcps2", "dcps3",
})


@dataclass
class AIPatchResult:
    """Outcome of validating one AI-authored binary patch."""

    patched: bytes | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    error: str | None = None
    injected_va: int | None = None
    method: str | None = None

    @property
    def ok(self) -> bool:
        return self.patched is not None and self.error is None


class _Rejected(Exception):
    """Internal fail-closed signal; the public API turns it into ``error``."""


def apply_ai_patch(
    data: bytes,
    container: ContainerInfo,
    sinks: list[Sink],
    payload: dict[str, Any],
) -> AIPatchResult:
    """Validate and apply one AI-authored patch, or fail closed.

    ``payload`` (``schema_version == 1``) carries a ``sink_index`` into
    ``sinks`` plus either ``inject.code_hex`` for an ``unbounded_copy`` sink
    or ``edits`` for a length-immediate sink.  The returned result never
    contains a partially patched image: on any validation failure
    ``patched`` is ``None`` and ``error`` is a human-readable reason.
    """
    try:
        return _apply(data, container, sinks, payload)
    except _Rejected as exc:
        return AIPatchResult(error=str(exc))
    except Exception as exc:  # noqa: BLE001 - fail closed on any validator bug
        return AIPatchResult(
            error=f"AI binary patch validation failed unexpectedly: "
                  f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# Payload plumbing
# ---------------------------------------------------------------------------

def _apply(
    data: bytes,
    container: ContainerInfo,
    sinks: list[Sink],
    payload: dict[str, Any],
) -> AIPatchResult:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise _Rejected("input executable must be bytes")
    data = bytes(data)
    if not data:
        raise _Rejected("input executable is empty")

    container_format = getattr(container, "format", None)
    container_arch = getattr(container, "arch", None)
    if container_format not in _CONTAINER_FORMATS:
        raise _Rejected(f"container format {container_format!r} is not supported")
    if container_arch not in _ARCH_DECODERS:
        raise _Rejected(
            f"container architecture {container_arch!r} is not supported "
            f"(expected one of {sorted(_ARCH_DECODERS)})"
        )
    if not isinstance(sinks, (list, tuple)):
        raise _Rejected("sinks must be a list")

    if not isinstance(payload, dict):
        raise _Rejected("AI patch payload must be a JSON object")
    schema = payload.get("schema_version")
    if isinstance(schema, bool) or schema != SCHEMA_VERSION:
        raise _Rejected(
            f"AI patch payload schema_version must be {SCHEMA_VERSION}, "
            f"got {schema!r}"
        )
    index = payload.get("sink_index")
    if isinstance(index, bool) or not isinstance(index, int):
        raise _Rejected("AI patch payload sink_index must be an integer")
    if not 0 <= index < len(sinks):
        raise _Rejected(
            f"sink_index {index} is out of range for {len(sinks)} sink(s)"
        )
    sink = sinks[index]
    kind = getattr(sink, "kind", None)
    patchable = getattr(sink, "patchable", False)
    if kind not in GUARD_KINDS and kind not in IMMEDIATE_KINDS:
        raise _Rejected(f"sink kind {kind!r} is not supported by the AI patch validator")
    if not patchable:
        raise _Rejected(f"sink {index} ({kind}) is not patchable")
    sink_arch = getattr(sink, "arch", None)
    if sink_arch != container_arch:
        raise _Rejected(
            f"sink architecture {sink_arch!r} does not match container "
            f"architecture {container_arch!r}"
        )

    injected_va: int | None = None
    method: str | None = None
    if kind in GUARD_KINDS:
        patched, actions, injected_va, method = _apply_guard(
            data, container, sink, payload
        )
    else:
        patched, actions = _apply_immediate(data, container, sink, payload)

    # Same fail-closed container check the writer performs: a patch that
    # breaks the container is not a candidate.
    check = detect_container(patched)
    if check.format != container_format or check.arch != container_arch:
        raise _Rejected(
            "patched candidate failed container reparse: expected "
            f"{container_format}/{container_arch}, got {check.format}/{check.arch}"
        )
    limitations: list[str] = []
    if check.limitations:
        limitations.append(
            "patched candidate reparse limitations: "
            + "; ".join(check.limitations[:2])
        )
    return AIPatchResult(
        patched=patched,
        actions=actions,
        limitations=limitations,
        injected_va=injected_va,
        method=method,
    )


def _decode_hex(value: Any, field_name: str, *, max_bytes: int) -> bytes:
    if not isinstance(value, str):
        raise _Rejected(f"{field_name} must be a hex string")
    text = value.strip()
    if text[:2].lower() == "0x":
        text = text[2:]
    text = "".join(text.split())
    if not text:
        raise _Rejected(f"{field_name} is empty")
    if len(text) > 2 * max_bytes + 64:
        raise _Rejected(f"{field_name} exceeds the {max_bytes}-byte limit")
    if len(text) % 2:
        raise _Rejected(f"{field_name} has an odd number of hex digits")
    try:
        return bytes.fromhex(text)
    except ValueError:
        raise _Rejected(f"{field_name} is not valid hexadecimal") from None


# ---------------------------------------------------------------------------
# Guard injection (unbounded_copy sinks)
# ---------------------------------------------------------------------------

def _apply_guard(
    data: bytes,
    container: ContainerInfo,
    sink: Sink,
    payload: dict[str, Any],
) -> tuple[bytes, list[dict[str, Any]], int, str]:
    if payload.get("edits") is not None:
        raise _Rejected(
            "guard sink payload must not contain edits; it requires "
            "inject.code_hex"
        )
    inject = payload.get("inject")
    if not isinstance(inject, dict):
        raise _Rejected("guard sink payload requires inject.code_hex")
    code = _decode_hex(
        inject.get("code_hex"), "inject.code_hex", max_bytes=MAX_CODE_BYTES
    )
    if not code:
        raise _Rejected("inject.code_hex is empty")
    if len(code) > MAX_CODE_BYTES:
        raise _Rejected(
            f"injected code is {len(code)} bytes; the limit is {MAX_CODE_BYTES}"
        )
    arch = getattr(container, "arch", "unknown")
    _validate_machine_code(code, arch)

    _check_call_site(data, container, sink)
    injected, block_va, method = _inject_blob(container, data, code)
    if injected is None or block_va is None:
        raise _Rejected(f"code injection failed: {method}")
    if not 0 <= block_va <= 0xFFFFFFFFFFFFFFFF:
        raise _Rejected(f"injector returned an impossible block address {block_va!r}")
    _check_call_site_unchanged(data, injected, sink)
    _check_redirect_range(sink, block_va)
    patched = _redirect_call(injected, sink, block_va)
    if patched is None:
        raise _Rejected(
            "call redirection failed at "
            f"{hex(int(getattr(sink, 'call_va', 0) or 0))} -> {hex(block_va)} "
            f"({method})"
        )
    action = {
        "kind": "ai-injected-guard",
        "site": hex(int(sink.call_va)),  # type: ignore[arg-type]
        "cave_va": hex(block_va),
        "method": method,
        "code_bytes": len(code),
    }
    return patched, [action], block_va, method


def _call_site_fields(sink: Sink) -> tuple[int, int, int]:
    offset = getattr(sink, "call_offset", None)
    size = getattr(sink, "call_size", None)
    call_va = getattr(sink, "call_va", None)
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise _Rejected("sink has no usable call_offset; cannot redirect it")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise _Rejected("sink has no usable call_size; cannot redirect it")
    if isinstance(call_va, bool) or not isinstance(call_va, int) or call_va < 0:
        raise _Rejected("sink has no usable call_va; cannot redirect it")
    return offset, size, call_va


def _check_call_site(
    data: bytes, container: ContainerInfo, sink: Sink
) -> None:
    """Confirm the bytes at the sink really form a redirectable call."""
    offset, size, call_va = _call_site_fields(sink)
    if offset + size > len(data):
        raise _Rejected(
            f"call site at file offset {offset:#x} extends past EOF"
        )
    mapped = None
    va_to_offset = getattr(container, "va_to_offset", None)
    if callable(va_to_offset):
        mapped = va_to_offset(call_va)
    if mapped is not None and int(mapped) != offset:
        raise _Rejected(
            f"sink.call_offset {offset:#x} does not match the container "
            f"mapping of call_va {call_va:#x} (offset {int(mapped):#x})"
        )
    arch = getattr(sink, "arch", None)
    head = data[offset:offset + size]
    if arch in {"x86_64", "i386"}:
        if head[0] == 0xE8:
            if size != 5:
                raise _Rejected(
                    f"call site at {call_va:#x} is E8 rel32 but call_size is "
                    f"{size}; expected 5"
                )
            return
        if head[0] == 0xFF and head[1] == 0x15:
            if size != 6:
                raise _Rejected(
                    f"call site at {call_va:#x} is FF 15 but call_size is "
                    f"{size}; expected 6"
                )
            return
        if arch == "x86_64" and head[0] == 0xFF and head[1] == 0x25:
            if size != 6:
                raise _Rejected(
                    f"call site at {call_va:#x} is FF 25 but call_size is "
                    f"{size}; expected 6"
                )
            return
        raise _Rejected(
            f"call site at {call_va:#x} is not a direct call "
            f"(E8/FF15/FF25): {head.hex()}"
        )
    if arch == "arm64":
        if size != 4:
            raise _Rejected(
                f"arm64 call site at {call_va:#x} has call_size {size}; "
                "expected 4"
            )
        word = struct.unpack_from("<I", data, offset)[0]
        if word & 0xFC000000 != 0x94000000:
            raise _Rejected(
                f"call site at {call_va:#x} is not an arm64 BL "
                f"(0x{word:08x})"
            )
        return
    raise _Rejected(f"no call-site model for architecture {arch!r}")


def _check_call_site_unchanged(data: bytes, injected: bytes, sink: Sink) -> None:
    offset, size, _ = _call_site_fields(sink)
    if injected[offset:offset + size] != data[offset:offset + size]:
        raise _Rejected("code injection changed the original call-site bytes")


def _check_redirect_range(sink: Sink, block_va: int) -> None:
    _, _, call_va = _call_site_fields(sink)
    arch = getattr(sink, "arch", None)
    if arch in {"x86_64", "i386"}:
        delta = block_va - (call_va + 5)
        if not -(1 << 31) <= delta < (1 << 31):
            raise _Rejected(
                f"injected block at {block_va:#x} is out of rel32 range from "
                f"the call site at {call_va:#x}"
            )
        return
    if arch == "arm64":
        delta = block_va - call_va
        if delta % 4:
            raise _Rejected(
                f"injected block at {block_va:#x} is not 4-byte aligned "
                f"relative to the BL at {call_va:#x}"
            )
        if not -(1 << 27) <= delta < (1 << 27):
            raise _Rejected(
                f"injected block at {block_va:#x} is out of BL range from "
                f"the call site at {call_va:#x}"
            )
        return
    raise _Rejected(f"no redirect-range model for architecture {arch!r}")


# ---------------------------------------------------------------------------
# In-place edits (immediate-length sinks)
# ---------------------------------------------------------------------------

def _apply_immediate(
    data: bytes,
    container: ContainerInfo,
    sink: Sink,
    payload: dict[str, Any],
) -> tuple[bytes, list[dict[str, Any]]]:
    if payload.get("inject") is not None:
        raise _Rejected(
            "length-immediate sink payload must not contain inject; it "
            "requires same-length edits"
        )
    edits = payload.get("edits")
    if not isinstance(edits, (list, tuple)) or not edits:
        raise _Rejected("length-immediate sink payload requires a non-empty edits list")
    if len(edits) > MAX_EDITS:
        raise _Rejected(
            f"payload has {len(edits)} edits; the limit is {MAX_EDITS}"
        )
    executable = [
        section for section in getattr(container, "sections", [])
        if getattr(section, "executable", False)
    ]
    if not executable:
        raise _Rejected("container reports no executable section to edit")

    prepared: list[tuple[int, bytes, bytes]] = []
    ranges: list[tuple[int, int]] = []
    total = 0
    for position, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise _Rejected(f"edits[{position}] must be an object")
        offset = edit.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise _Rejected(
                f"edits[{position}].offset must be a non-negative integer"
            )
        before = _decode_hex(
            edit.get("before_hex"), f"edits[{position}].before_hex",
            max_bytes=MAX_EDIT_BYTES,
        )
        after = _decode_hex(
            edit.get("after_hex"), f"edits[{position}].after_hex",
            max_bytes=MAX_EDIT_BYTES,
        )
        if not before:
            raise _Rejected(f"edits[{position}] has an empty before_hex")
        if len(before) != len(after):
            raise _Rejected(
                f"edits[{position}] changes length: before_hex is "
                f"{len(before)} byte(s), after_hex is {len(after)} byte(s)"
            )
        if offset + len(before) > len(data):
            raise _Rejected(
                f"edits[{position}] at {offset:#x} extends past EOF"
            )
        original = data[offset:offset + len(before)]
        if original != before:
            raise _Rejected(
                f"edits[{position}] before_hex does not match the original "
                f"bytes at {offset:#x} (found {original.hex()})"
            )
        if not _inside_executable(executable, offset, len(after)):
            raise _Rejected(
                f"edits[{position}] offset {offset:#x} is outside every "
                "executable section"
            )
        ranges.append((offset, offset + len(after)))
        total += len(after)
        prepared.append((offset, before, after))

    if total > MAX_EDIT_BYTES:
        raise _Rejected(
            f"edits rewrite {total} byte(s); the limit is {MAX_EDIT_BYTES}"
        )
    ranges.sort()
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            raise _Rejected(
                f"edits overlap at file offset {current[0]:#x}; "
                "each byte may be rewritten once"
            )

    patched = bytearray(data)
    actions: list[dict[str, Any]] = []
    for offset, before, after in prepared:
        patched[offset:offset + len(after)] = after
        actions.append({
            "kind": "ai-edit",
            "offset": offset,
            "before_hex": before.hex(),
            "after_hex": after.hex(),
        })
    candidate = bytes(patched)
    if candidate == data:
        raise _Rejected("edits do not modify any byte")
    return candidate, actions


def _inside_executable(
    executable: list[Any], offset: int, size: int
) -> bool:
    for section in executable:
        start = int(getattr(section, "offset", -1) or 0)
        length = int(getattr(section, "size", 0) or 0)
        if length > 0 and start <= offset and offset + size <= start + length:
            return True
    return False


# ---------------------------------------------------------------------------
# Injected machine-code validation
# ---------------------------------------------------------------------------

def _validate_machine_code(code: bytes, arch: str) -> None:
    """Reject injected code that is not fully decodable and allowlisted."""
    decoder = _ARCH_DECODERS.get(arch)
    if decoder is None:
        raise _Rejected(f"no Capstone decoder for architecture {arch!r}")
    capstone_arch, capstone_mode = decoder
    md = Cs(capstone_arch, capstone_mode)
    md.detail = True
    try:
        instructions = list(md.disasm(code, 0))
    except Exception as exc:  # noqa: BLE001 - capstone raises on some inputs
        raise _Rejected(
            f"Capstone could not decode the injected {arch} code: {exc}"
        ) from None
    decoded = sum(int(ins.size) for ins in instructions)
    if decoded != len(code):
        raise _Rejected(
            f"injected code has {len(code) - decoded} trailing byte(s) that "
            f"do not decode as {arch} instructions"
        )
    if arch == "arm64" and len(code) % 4:
        raise _Rejected("arm64 injected code must be a multiple of 4 bytes")
    for ins in instructions:
        _validate_instruction(ins, arch, len(code))
    _require_terminator(instructions[-1], arch)


def _require_terminator(last: Any, arch: str) -> None:
    """Reject a block that would fall through past its last instruction."""
    mnemonic = (last.mnemonic or "").lower()
    terminals = {"ret", "jmp"} if arch in {"x86_64", "i386"} else {"ret", "b"}
    if mnemonic not in terminals:
        raise _Rejected(
            f"injected code ends with {mnemonic!r} and would fall through "
            "past the end of the block; the last instruction must be "
            f"one of {sorted(terminals)}"
        )


def _validate_instruction(ins: Any, arch: str, code_size: int) -> None:
    mnemonic = (ins.mnemonic or "").lower()
    offset = int(ins.address)
    if not mnemonic:
        raise _Rejected(f"undecodable instruction at block offset {offset:#x}")
    if arch in {"x86_64", "i386"}:
        if mnemonic in _X86_DENIED or mnemonic.startswith("int"):
            raise _Rejected(
                f"injected code uses forbidden instruction {mnemonic!r} at "
                f"block offset {offset:#x}"
            )
        if mnemonic not in _X86_ALLOWED:
            raise _Rejected(
                f"injected code uses instruction {mnemonic!r} at block "
                f"offset {offset:#x}, which is not on the allowlist"
            )
        _validate_x86_instruction(ins, mnemonic, offset, code_size)
        return
    if arch == "arm64":
        if mnemonic in _ARM64_DENIED or mnemonic in {"bl", "blr", "br"}:
            raise _Rejected(
                f"injected code uses forbidden instruction {mnemonic!r} at "
                f"block offset {offset:#x}"
            )
        if mnemonic not in _ARM64_ALLOWED and not mnemonic.startswith("b."):
            raise _Rejected(
                f"injected code uses instruction {mnemonic!r} at block "
                f"offset {offset:#x}, which is not on the allowlist"
            )
        _validate_arm64_instruction(ins, mnemonic, offset, code_size)
        return
    raise _Rejected(f"no instruction policy for architecture {arch!r}")


def _validate_x86_instruction(
    ins: Any, mnemonic: str, offset: int, code_size: int
) -> None:
    for operand in ins.operands:
        if operand.type == X86_OP_REG:
            name = ins.reg_name(operand.reg) or ""
            if _PRIVILEGED_X86_REG.match(name):
                raise _Rejected(
                    f"injected code touches privileged register {name!r} "
                    f"at block offset {offset:#x}"
                )
    if mnemonic == "jmp":
        if len(ins.operands) != 1 or ins.operands[0].type != X86_OP_IMM:
            raise _Rejected(
                f"injected code uses an indirect jmp at block offset "
                f"{offset:#x}; only direct branches are allowed"
            )
        _require_branch_inside(
            int(ins.operands[0].imm), offset, code_size, "jmp"
        )
        return
    if mnemonic in _X86_JCC:
        if len(ins.operands) != 1 or ins.operands[0].type != X86_OP_IMM:
            raise _Rejected(
                f"injected code uses an indirect conditional branch at block "
                f"offset {offset:#x}"
            )
        _require_branch_inside(
            int(ins.operands[0].imm), offset, code_size, mnemonic
        )
        return
    if mnemonic == "ret" and ins.operands:
        raise _Rejected(
            f"injected code uses a parameterised ret at block offset "
            f"{offset:#x}; it would corrupt the caller's stack"
        )


def _validate_arm64_instruction(
    ins: Any, mnemonic: str, offset: int, code_size: int
) -> None:
    if mnemonic == "ret":
        if ins.operands:
            raise _Rejected(
                f"injected code uses a parameterised ret at block offset "
                f"{offset:#x}; it would corrupt the caller's stack"
            )
        return
    if mnemonic in _ARM64_BRANCHES or mnemonic.startswith("b."):
        immediates = [
            operand for operand in ins.operands if operand.type == ARM64_OP_IMM
        ]
        if len(immediates) != 1:
            raise _Rejected(
                f"injected code uses an indirect {mnemonic!r} at block "
                f"offset {offset:#x}; only direct branches are allowed"
            )
        _require_branch_inside(
            int(immediates[-1].imm), offset, code_size, mnemonic,
            alignment=4,
        )


def _require_branch_inside(
    target: int, offset: int, code_size: int, mnemonic: str, *,
    alignment: int = 1,
) -> None:
    if target < 0 or target >= code_size:
        raise _Rejected(
            f"injected {mnemonic} at block offset {offset:#x} targets "
            f"{target:#x}, outside the {code_size:#x}-byte block"
        )
    if target % alignment:
        raise _Rejected(
            f"injected {mnemonic} at block offset {offset:#x} targets "
            f"unaligned address {target:#x}"
        )
