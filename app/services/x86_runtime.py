"""Small x86-64 ELF emulator for static fixtures (Unicorn, no host execution).

It emulates only the syscalls used by the generated test fixtures:
read(0), write(1/2), exit_group(60).  It is a test oracle, not a sandbox.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_X86, UC_HOOK_INSN, UC_MODE_64, UC_PROT_ALL
from unicorn.x86_const import (
    UC_X86_INS_SYSCALL,
    UC_X86_REG_RAX, UC_X86_REG_RDI, UC_X86_REG_RDX,
    UC_X86_REG_RIP, UC_X86_REG_RSI, UC_X86_REG_RSP,
)

STACK = 0x7FFFFFF00000
STACK_SIZE = 0x20000


@dataclass
class EmulationResult:
    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: int | None = None
    instructions: int = 0
    stack_tail: bytes = b""
    error: str | None = None
    maps: list[tuple[int, int]] = field(default_factory=list)


def emulate_elf(raw: bytes, stdin: bytes = b"", *, limit: int = 2000) -> EmulationResult:
    result = EmulationResult()
    try:
        elf = ELFFile(io.BytesIO(raw))
        entry = int(elf.header["e_entry"])
        uc = Uc(UC_ARCH_X86, UC_MODE_64)
        for seg in elf.iter_segments():
            if seg["p_type"] != "PT_LOAD":
                continue
            vaddr = int(seg["p_vaddr"])
            filesz = int(seg["p_filesz"])
            memsz = int(seg["p_memsz"])
            off = int(seg["p_offset"])
            base = vaddr & ~0xFFF
            size = (memsz + (vaddr - base) + 0xFFF) & ~0xFFF
            if not size:
                continue
            uc.mem_map(base, size, UC_PROT_ALL)
            uc.mem_write(vaddr, raw[off:off + filesz])
            result.maps.append((base, size))
        uc.mem_map(STACK, STACK_SIZE, UC_PROT_ALL)
        initial_rsp = STACK + 0x10000
        uc.reg_write(UC_X86_REG_RSP, initial_rsp)
        # Sentinel immediately beyond a 32-byte local buffer.
        uc.mem_write(initial_rsp, b"\x5a" * 16)

        state = {"stdin": stdin, "pos": 0, "exit": None}
        count = {"n": 0}

        def hook(uc: Uc, *_args) -> None:
            count["n"] += 1
            rax = uc.reg_read(UC_X86_REG_RAX)
            rdi = uc.reg_read(UC_X86_REG_RDI)
            rsi = uc.reg_read(UC_X86_REG_RSI)
            rdx = uc.reg_read(UC_X86_REG_RDX)
            if rax == 0:  # read(0, rsi, rdx)
                chunk = state["stdin"][state["pos"]:state["pos"] + rdx]
                state["pos"] += len(chunk)
                uc.mem_write(rsi, chunk)
                uc.reg_write(UC_X86_REG_RAX, len(chunk))
            elif rax == 1:  # write(fd, rsi, rdx)
                payload = bytes(uc.mem_read(rsi, rdx))
                if rdi == 1:
                    result.stdout += payload
                elif rdi == 2:
                    result.stderr += payload
                uc.reg_write(UC_X86_REG_RAX, rdx)
            elif rax == 60:  # exit_group(status)
                state["exit"] = rdi
                uc.emu_stop()
            else:
                result.error = f"unsupported syscall {rax}"
                uc.emu_stop()

        uc.hook_add(UC_HOOK_INSN, hook, None, 1, 0, UC_X86_INS_SYSCALL)
        uc.emu_start(entry, 0, count=limit)
        result.exit_code = state["exit"]
        result.instructions = count["n"]
        result.stack_tail = bytes(uc.mem_read(initial_rsp, 16))
    except Exception as exc:  # noqa: BLE001 - report, never execute host code
        result.error = f"{type(exc).__name__}: {exc}"
    return result
