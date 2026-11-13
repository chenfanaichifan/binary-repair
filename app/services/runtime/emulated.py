"""Instruction-level runtime evidence through Unicorn.

Used when the host cannot execute the target natively (PE on macOS/Linux, ELF
AArch64 on macOS).  The harness maps the image, builds a controlled stack and
input buffer, stubs the non-copy imports (``puts``), and records whether the
copy stays inside ``capacity``.

This is emulation, not a Windows/Linux kernel run; the report says so.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

import lief
from elftools.elf.elffile import ELFFile
from unicorn import (
    UC_ARCH_ARM64, UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_64, UC_MODE_ARM,
    UC_PROT_ALL, Uc,
)
from unicorn.arm64_const import (
    UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X30,
)
from unicorn.x86_const import (
    UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDI, UC_X86_REG_RDX,
    UC_X86_REG_RIP, UC_X86_REG_RSI, UC_X86_REG_RSP,
)

from app.services.containers import ContainerInfo
from app.services.runtime.evidence import RuntimeCase, RuntimeEvidence, judge

PAGE = 0x1000
STACK_BASE = 0x7000000000
STACK_SIZE = 0x20000
INPUT_BASE = 0x6000000000
SENTINEL_BASE = 0x5000000000
CANARY = b"\xAA" * 32
FILL = b"\xCC"
MAX_INSNS = 2_000_000


@dataclass
class _Mapping:
    va: int
    size: int
    offset: int


def _align_down(value: int) -> int:
    return value & ~(PAGE - 1)


def _align_up(value: int) -> int:
    return (value + PAGE - 1) & ~(PAGE - 1)


def _elf_mappings(data: bytes) -> list[_Mapping]:
    mappings: list[_Mapping] = []
    elf = ELFFile(__import__("io").BytesIO(data))
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD":
            continue
        vaddr = int(segment["p_vaddr"])
        filesz = int(segment["p_filesz"])
        memsz = int(segment["p_memsz"])
        offset = int(segment["p_offset"])
        start = _align_down(vaddr)
        size = _align_up(vaddr + memsz) - start
        if size > 0:
            mappings.append(_Mapping(start, size, offset - (vaddr - start)))
    return mappings


def _pe_mappings(data: bytes) -> list[_Mapping]:
    pe = lief.PE.parse(list(data))
    if pe is None:
        return []
    base = int(pe.optional_header.imagebase)
    mappings = []
    for section in pe.sections:
        va = base + int(section.virtual_address)
        size = max(len(section.content), int(section.sizeof_raw_data))
        start = _align_down(va)
        mappings.append(_Mapping(start, _align_up(va + size) - start,
                                 int(section.pointerto_raw_data) - (va - start)))
    return mappings


def _mappings(data: bytes, container: ContainerInfo) -> list[_Mapping]:
    if container.format == "elf":
        return _elf_mappings(data)
    if container.format == "pe":
        return _pe_mappings(data)
    return []


def _merge(mappings: list[_Mapping]) -> list[_Mapping]:
    merged: list[_Mapping] = []
    for item in sorted(mappings, key=lambda m: m.va):
        if merged:
            last = merged[-1]
            contiguous_files = item.offset == last.offset + (item.va - last.va)
            if item.va <= last.va + last.size and contiguous_files:
                end = max(last.va + last.size, item.va + item.size)
                merged[-1] = _Mapping(last.va, end - last.va, last.offset)
                continue
        merged.append(item)
    return merged


def _callable_address(container: ContainerInfo, names: set[str]) -> int | None:
    candidates: list[int] = []
    for va, name in container.imports.items():
        short = name.lower().lstrip("_").split("@")[0]
        section = container.section_at(va)
        if short in names and section is not None and section.executable:
            candidates.append(va)
    if candidates:
        return min(candidates)
    for va, name in container.symbols.items():
        short = name.lower().lstrip("_").split("@")[0]
        if short in names:
            return va
    return None


def _read_cstr(uc: Uc, address: int, limit: int = 8192) -> bytes:
    out = bytearray()
    for index in range(limit):
        try:
            byte = uc.mem_read(address + index, 1)
        except Exception:  # noqa: BLE001
            break
        value = bytes(byte)[0]
        out.append(value)
        if value == 0:
            break
    return bytes(out)


def emulate(
    data: bytes,
    container: ContainerInfo,
    *,
    function_va: int,
    dest_rel: int,
    capacity: int,
    abi: str,
    lengths: list[int] | None = None,
) -> RuntimeEvidence:
    evidence = RuntimeEvidence(tier="emulated_run", engine=f"unicorn-{container.arch}")
    if capacity <= 0:
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append("capacity is not positive")
        return evidence
    mappings = _merge(_mappings(data, container))
    if not mappings:
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append(f"no mapping strategy for {container.format}")
        return evidence

    copy_target = _callable_address(container, {"strcpy", "strcat"})
    puts_target = _callable_address(container, {"puts", "fputs", "printf", "putchar"})
    if copy_target is None and puts_target is None:
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append("could not resolve the copy/puts imports")
        return evidence

    probe = [0, 1, capacity - 1, capacity, capacity + 1, capacity * 4]
    selected = sorted({value for value in (lengths or probe) if value >= 0})
    for length in selected:
        evidence.cases.append(_run_case(
            data, container, mappings,
            function_va=function_va, dest_rel=dest_rel, capacity=capacity,
            abi=abi, argument=b"A" * length, copy_target=copy_target,
            puts_target=puts_target,
        ))
    evidence.verdict = judge(evidence.cases, capacity)
    evidence.limitations.extend([
        "Emulated execution with modeled imports; not a native Windows/Linux run.",
        "Only the repaired function is executed; unrelated code paths are not covered.",
    ])
    return evidence


def _run_case(
    data: bytes,
    container: ContainerInfo,
    mappings: list[_Mapping],
    *,
    function_va: int,
    dest_rel: int,
    capacity: int,
    abi: str,
    argument: bytes,
    copy_target: int | None,
    puts_target: int | None,
) -> RuntimeCase:
    is_arm = container.arch == "arm64"
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM) if is_arm else Uc(UC_ARCH_X86, UC_MODE_64)
    mapped: list[tuple[int, int]] = []

    def map_range(va: int, size: int, fill: bytes = b"\x00") -> None:
        start = _align_down(va)
        total = _align_up(va + size) - start
        for other_va, other_size in mapped:
            if start < other_va + other_size and other_va < start + total:
                return
        try:
            uc.mem_map(start, total, UC_PROT_ALL)
        except Exception:  # noqa: BLE001
            return
        mapped.append((start, total))
        if fill:
            uc.mem_write(start, fill * total)

    for item in mappings:
        start = _align_down(item.va)
        total = _align_up(item.va + item.size) - start
        try:
            uc.mem_map(start, total, UC_PROT_ALL)
        except Exception:  # noqa: BLE001
            continue
        mapped.append((start, total))
        offset = item.offset
        if 0 <= offset < len(data):
            chunk = data[offset:offset + min(total, len(data) - offset)]
            if chunk:
                uc.mem_write(start, chunk)

    map_range(STACK_BASE, STACK_SIZE, b"\x00")
    map_range(INPUT_BASE, len(argument) + 64, b"\x00")
    map_range(SENTINEL_BASE, PAGE, b"\x00")
    uc.mem_write(SENTINEL_BASE, b"\xF4" if not is_arm else b"\x00\x00\x20\xD4")

    entry_sp = STACK_BASE + STACK_SIZE - 0x200
    if not is_arm:
        entry_sp -= 8  # the synthetic return address lives at the entry RSP
    dest = entry_sp + dest_rel
    map_range(dest, capacity + 96, FILL)
    # On x86 the synthetic return address occupies [entry_sp, entry_sp+8), so
    # the canary starts above it and the return slot itself is checked too.
    canary_addr = dest + capacity + (0 if is_arm else 8)
    uc.mem_write(canary_addr, CANARY)
    uc.mem_write(INPUT_BASE, argument + b"\x00")

    sentinel = SENTINEL_BASE
    if is_arm:
        uc.reg_write(UC_ARM64_REG_SP, entry_sp)
        uc.reg_write(UC_ARM64_REG_X0, INPUT_BASE)
        uc.reg_write(UC_ARM64_REG_X30, sentinel)
    else:
        uc.mem_write(entry_sp, struct.pack("<Q", sentinel))
        uc.reg_write(UC_X86_REG_RSP, entry_sp)
        if abi == "win64_x86_64":
            uc.reg_write(UC_X86_REG_RCX, INPUT_BASE)
        else:
            uc.reg_write(UC_X86_REG_RDI, INPUT_BASE)

    def finish(uc_obj: Uc) -> None:
        if is_arm:
            uc_obj.reg_write(UC_ARM64_REG_PC, uc_obj.reg_read(UC_ARM64_REG_X30))
            uc_obj.reg_write(UC_ARM64_REG_X0, 0)
        else:
            sp_now = uc_obj.reg_read(UC_X86_REG_RSP)
            ret = struct.unpack("<Q", bytes(uc_obj.mem_read(sp_now, 8)))[0]
            uc_obj.reg_write(UC_X86_REG_RSP, sp_now + 8)
            uc_obj.reg_write(UC_X86_REG_RIP, ret)
            uc_obj.reg_write(UC_X86_REG_RAX, 0)

    def hook_puts(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
        finish(uc_obj)

    def hook_copy(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
        if is_arm:
            dst = uc_obj.reg_read(UC_ARM64_REG_X0)
            src = uc_obj.reg_read(UC_ARM64_REG_X1)
        elif abi == "win64_x86_64":
            dst = uc_obj.reg_read(UC_X86_REG_RCX)
            src = uc_obj.reg_read(UC_X86_REG_RDX)
        else:
            dst = uc_obj.reg_read(UC_X86_REG_RDI)
            src = uc_obj.reg_read(UC_X86_REG_RSI)
        payload = _read_cstr(uc_obj, src, limit=8192)
        uc_obj.mem_write(dst, payload)
        finish(uc_obj)

    if puts_target is not None:
        uc.hook_add(UC_HOOK_CODE, hook_puts, begin=puts_target, end=puts_target)
    if copy_target is not None:
        uc.hook_add(UC_HOOK_CODE, hook_copy, begin=copy_target, end=copy_target)

    trace: list[int] = []

    def hook_trace(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
        trace.append(address)
        if len(trace) > 64:
            trace.pop(0)

    uc.hook_add(UC_HOOK_CODE, hook_trace)
    error = None
    try:
        uc.emu_start(function_va, sentinel, count=MAX_INSNS)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        error += " at " + " -> ".join(hex(pc) for pc in trace[-6:])

    try:
        canary = bytes(uc.mem_read(canary_addr, len(CANARY)))
        sentinel_ok = True
        if not is_arm:
            sentinel_ok = bytes(uc.mem_read(entry_sp, 8)) == struct.pack("<Q", sentinel)
        output = _read_cstr(uc, dest, limit=capacity + 64)
        output_len = len(output) - 1 if output.endswith(b"\x00") else capacity + 64
    except Exception:  # noqa: BLE001
        canary = b""
        sentinel_ok = False
        output_len = None
    return RuntimeCase(
        input_len=len(argument),
        exit_code=0 if error is None else 1,
        canary_intact=(canary == CANARY) and sentinel_ok,
        output_len=output_len,
        error=error,
    )
