"""32-bit x86 (i386) sink analysis for stack-buffer copies.

This mirrors the x86-64 analyzer's frame model for the cdecl world:

* ``push ebp`` / ``mov ebp, esp`` sets ``frame_top = ebp``;
* ``sub esp, N`` without a frame pointer sets ``frame_top`` to the value of
  ``esp`` before the subtraction;
* destination candidates come from ``lea reg, [ebp ± K]``,
  ``lea reg, [esp + K]`` and ``mov reg, esp``;
* ``capacity = frame_top - destination``.

The i386 SysV ABI and MinGW both use cdecl for ``strcpy``/``strcat``/
``memcpy``: arguments are pushed on the stack and the destination is the last
push before the call.  Only *push*-materialized arguments are modelled.  Code
that materializes arguments with ``mov [esp + k], reg`` is deliberately not
recognized: the engine then reports no sink for that call site instead of
guessing a capacity (fail closed).  Registers and flags are not executed; this
is static decoding only.
"""
from __future__ import annotations

from dataclasses import dataclass

from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from app.services.containers import ContainerInfo, resolve_target

MAX_CAPACITY = 1 << 20

_MD_X86_32 = Cs(CS_ARCH_X86, CS_MODE_32)
_MD_X86_32.detail = True

_PTR_REGS = {"eax", "ebx", "ecx", "edx", "esi", "edi"}
_STR_COPIES = {"strcpy", "strcat", "stpcpy"}
_MEM_COPIES = {"memcpy", "memmove"}


@dataclass
class _Arg:
    """One cdecl argument candidate tracked for the next ``call``."""

    kind: str = "unknown"          # "ptr" | "imm" | "unknown"
    value: int | None = None       # destination offset (ptr) or immediate
    imm_offset: int | None = None  # file offset of an encodable imm32


def _call_name(container: ContainerInfo, ins) -> str | None:
    """Resolve a direct or IAT/PLT call target to a name, if possible."""
    if not ins.operands:
        return None
    operand = ins.operands[0]
    if operand.type == X86_OP_IMM:
        target = int(operand.imm) & 0xFFFFFFFF
        return resolve_target(container, target)
    if operand.type == X86_OP_MEM and not operand.mem.base:
        # i386 PE: ``call dword ptr [__imp_strcpy]`` = FF 15 <abs32 IAT VA>.
        target = int(operand.mem.disp) & 0xFFFFFFFF
        name = container.imports.get(target)
        if name is not None:
            return name
        return resolve_target(container, target)
    return None


def _imm32_body_offset(ins) -> int | None:
    """Return the byte offset of an encodable imm32 inside one instruction."""
    raw = bytes(ins.bytes)
    if len(raw) == 5 and 0xB8 <= raw[0] <= 0xBF:  # mov r32, imm32
        return 1
    if len(raw) == 5 and raw[0] == 0x68:  # push imm32
        return 1
    return None


def _trim_pushed(pushed: list[_Arg], count: int) -> None:
    if count <= 0:
        return
    del pushed[:count]


def _reset(state: dict) -> None:
    state.update(
        esp_rel=0,
        ebp_rel=None,
        frame_top=0,
        frame_start=None,
    )
    state["dest"].clear()
    state["consts"].clear()
    state["pushed"].clear()


def scan_i386(analysis, container: ContainerInfo, text, code: bytes) -> None:
    """Decode ``.text`` in 32-bit mode and append i386 sink records."""
    # Imported lazily: analyzer.py imports this module for dispatch only.
    from app.services.repair.analyzer import (  # noqa: PLC0415
        _copy_name,
        _emit_immediate,
        Sink,
    )

    state: dict = {
        "esp_rel": 0,
        "ebp_rel": None,
        "frame_top": 0,
        "frame_start": None,
        "dest": {},
        "consts": {},
        "pushed": [],
        "mov_arg_limitation": False,
    }

    for ins in _MD_X86_32.disasm(code, text.va):
        mnemonic = ins.mnemonic
        op_text = (ins.op_str or "").replace(" ", "")

        if mnemonic == "ret" or mnemonic == "retf":
            _reset(state)
            continue
        if mnemonic == "leave":
            if state["ebp_rel"] is not None:
                state["esp_rel"] = state["ebp_rel"]
            state["ebp_rel"] = None
            state["frame_top"] = 0
            state["dest"].clear()
            state["consts"].clear()
            state["pushed"].clear()
            continue
        if mnemonic == "push":
            state["esp_rel"] -= 4
            value, imm_offset = state["dest"].get(op_text), None
            if value is not None:
                state["pushed"].insert(0, _Arg("ptr", value, None))
            elif op_text in state["consts"]:
                const, imm_offset = state["consts"][op_text]
                state["pushed"].insert(0, _Arg("imm", const, imm_offset))
            else:
                state["pushed"].insert(0, _Arg("unknown"))
            if op_text == "ebp" and state["frame_start"] is None:
                state["frame_start"] = ins.address
            continue
        if mnemonic == "pop":
            state["esp_rel"] += 4
            _trim_pushed(state["pushed"], 1)
            continue
        if mnemonic == "sub" and op_text.startswith("esp,"):
            imm = int(ins.operands[-1].imm or 0)
            if state["frame_start"] is None:
                state["frame_start"] = ins.address
            if state["ebp_rel"] is None and imm > 0:
                state["frame_top"] = state["esp_rel"]
            state["esp_rel"] -= imm
            continue
        if mnemonic == "add" and op_text.startswith("esp,"):
            imm = int(ins.operands[-1].imm or 0)
            state["esp_rel"] += imm
            _trim_pushed(state["pushed"], imm // 4 if imm > 0 else 0)
            continue
        if mnemonic == "and" and op_text.startswith("esp,"):
            # Stack realignment breaks the frame model; stop trusting it.
            state["esp_rel"] = 0
            state["frame_top"] = 0 if state["ebp_rel"] is None else state["frame_top"]
            state["pushed"].clear()
            continue
        if mnemonic == "mov" and len(ins.operands) == 2:
            dst, src = ins.operands
            if dst.type == X86_OP_REG and src.type == X86_OP_REG:
                left = ins.reg_name(dst.reg)
                right = ins.reg_name(src.reg)
                if left == "ebp" and right == "esp":
                    state["ebp_rel"] = state["esp_rel"]
                    state["frame_top"] = state["ebp_rel"]
                    if state["frame_start"] is None:
                        state["frame_start"] = ins.address
                    continue
                if left == "esp" and right == "ebp" and state["ebp_rel"] is not None:
                    state["esp_rel"] = state["ebp_rel"]
                    state["ebp_rel"] = None
                    state["frame_top"] = 0
                    state["dest"].clear()
                    continue
                if left in _PTR_REGS:
                    state["dest"].pop(left, None)
                    state["consts"].pop(left, None)
                    if right in state["dest"]:
                        state["dest"][left] = state["dest"][right]
                    elif right in state["consts"]:
                        state["consts"][left] = state["consts"][right]
                    elif right == "esp":
                        state["dest"][left] = state["esp_rel"]
                    elif right == "ebp" and state["ebp_rel"] is not None:
                        state["dest"][left] = state["ebp_rel"]
                continue
            if dst.type == X86_OP_REG and src.type == X86_OP_IMM:
                reg = ins.reg_name(dst.reg)
                if reg in _PTR_REGS:
                    state["dest"].pop(reg, None)
                    state["consts"][reg] = (
                        int(src.imm) & 0xFFFFFFFF,
                        _imm32_body_offset(ins),
                    )
                continue
            continue
        if mnemonic == "lea" and len(ins.operands) == 2 and ins.operands[0].type == X86_OP_REG:
            reg = ins.reg_name(ins.operands[0].reg)
            mem = ins.operands[1]
            if mem.type == X86_OP_MEM and reg in _PTR_REGS:
                base = ins.reg_name(mem.mem.base) if mem.mem.base else ""
                if mem.mem.index:
                    continue
                value = None
                if base == "esp":
                    value = state["esp_rel"] + int(mem.mem.disp)
                elif base == "ebp" and state["ebp_rel"] is not None:
                    value = state["ebp_rel"] + int(mem.mem.disp)
                if value is not None:
                    state["dest"][reg] = value
                    state["consts"].pop(reg, None)
                continue
            continue
        if mnemonic == "xor" and op_text and "," in op_text:
            left, right = op_text.split(",", 1)
            if left == right and left in _PTR_REGS:
                state["dest"].pop(left, None)
                state["consts"][left] = (0, None)
            continue
        if mnemonic != "call":
            continue

        name = _call_name(container, ins)
        copy = _copy_name(name) if name else None
        call_off = text.offset + (ins.address - text.va)
        if copy is not None:
            dst_arg = state["pushed"][0] if state["pushed"] else _Arg()
            dst_rel = dst_arg.value if dst_arg.kind == "ptr" else None
            if dst_rel is None and not state["mov_arg_limitation"]:
                state["mov_arg_limitation"] = True
                analysis.limitations.append(
                    "cdecl arguments materialised with mov to stack are not "
                    "analysed in v1"
                )
            capacity = (
                state["frame_top"] - dst_rel
                if state["frame_top"] is not None and dst_rel is not None
                else None
            )
            if copy in _STR_COPIES:
                if capacity is not None and 0 < capacity <= MAX_CAPACITY:
                    analysis.sinks.append(Sink(
                        kind="unbounded_copy",
                        arch="i386",
                        function_va=state["frame_start"] or 0,
                        call_va=ins.address,
                        callee=copy,
                        capacity=capacity,
                        dest_rel=dst_rel,
                        call_offset=call_off,
                        call_size=ins.size,
                        patchable=True,
                        confidence="medium",
                        detail=(
                            f"{copy} into stack destination bounded to "
                            f"{capacity} bytes (i386 cdecl)"
                        ),
                    ))
            elif copy in _MEM_COPIES:
                length_arg = state["pushed"][2] if len(state["pushed"]) > 2 else _Arg()
                if (
                    length_arg.kind == "imm"
                    and length_arg.imm_offset is not None
                    and length_arg.value is not None
                    and capacity is not None
                    and 0 < capacity <= MAX_CAPACITY
                ):
                    _emit_immediate(
                        analysis, container, text, ins, "memcpy_length", copy,
                        int(length_arg.value), length_arg.imm_offset, capacity,
                        state["frame_start"],
                        detail=(
                            "immediate copy length exceeds stack capacity "
                            "(i386 cdecl)"
                        ),
                    )
        state["pushed"].clear()
        continue
