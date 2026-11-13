"""Guard encodings and semantics for every supported ABI."""
from __future__ import annotations

import struct

import pytest
from capstone import CS_ARCH_ARM64, CS_ARCH_X86, CS_MODE_64, CS_MODE_ARM, Cs
from unicorn import UC_ARCH_ARM64, UC_ARCH_X86, UC_MODE_64, UC_MODE_ARM, UC_PROT_ALL, Uc
from unicorn.arm64_const import UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X30
from unicorn.x86_const import (
    UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDI, UC_X86_REG_RDX,
    UC_X86_REG_RIP, UC_X86_REG_RSI, UC_X86_REG_RSP,
)

from app.services.repair.guards import build_guard

CODE = 0x1000
STACK = 0x7000
DST = 0x2000
SRC = 0x3000
SENTINEL = 0x9000


def _x86_emulate(abi: str, op: str, capacity: int, src: bytes, dst: bytes) -> tuple[bytes, int]:
    code = build_guard(abi, op, capacity)
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    for base, size in ((CODE, 0x1000), (STACK, 0x2000), (DST, 0x1000),
                       (SRC, 0x2000), (SENTINEL, 0x1000)):
        uc.mem_map(base, size, UC_PROT_ALL)
    uc.mem_write(CODE, code)
    sp = STACK + 0x1800
    uc.mem_write(sp, struct.pack("<Q", SENTINEL))
    uc.mem_write(DST, dst)
    uc.mem_write(SRC, src)
    uc.reg_write(UC_X86_REG_RSP, sp)
    if abi == "sysv_x86_64":
        uc.reg_write(UC_X86_REG_RDI, DST)
        uc.reg_write(UC_X86_REG_RSI, SRC)
    else:
        uc.reg_write(UC_X86_REG_RCX, DST)
        uc.reg_write(UC_X86_REG_RDX, SRC)
    uc.emu_start(CODE, SENTINEL, count=10_000)
    return bytes(uc.mem_read(DST, capacity + 8)), int(uc.reg_read(UC_X86_REG_RAX))


def _arm_emulate(op: str, capacity: int, src: bytes, dst: bytes) -> tuple[bytes, int]:
    code = build_guard("aapcs64", op, capacity)
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for base, size in ((CODE, 0x1000), (STACK, 0x2000), (DST, 0x1000),
                       (SRC, 0x2000), (SENTINEL, 0x1000)):
        uc.mem_map(base, size, UC_PROT_ALL)
    uc.mem_write(CODE, code)
    uc.mem_write(DST, dst)
    uc.mem_write(SRC, src)
    uc.reg_write(UC_ARM64_REG_SP, STACK + 0x1800)
    uc.reg_write(UC_ARM64_REG_X0, DST)
    uc.reg_write(UC_ARM64_REG_X1, SRC)
    uc.reg_write(UC_ARM64_REG_X30, SENTINEL)
    uc.emu_start(CODE, SENTINEL, count=10_000)
    return bytes(uc.mem_read(DST, capacity + 8)), int(uc.reg_read(UC_ARM64_REG_X0))


@pytest.mark.parametrize("abi", ["sysv_x86_64", "win64_x86_64"])
def test_x86_strcpy_guard_bounds_and_returns(abi):
    out, code = _x86_emulate(abi, "strcpy", 16, b"A" * 40, b"")
    assert out[15] == 0 and out[:15] == b"A" * 15
    assert out[16:24] == b"\x00" * 8
    assert code == 1

    out, code = _x86_emulate(abi, "strcpy", 16, b"hello", b"")
    assert out[:5] == b"hello" and out[5] == 0
    assert code == 0


def test_x86_strcat_guard_appends_within_capacity():
    out, code = _x86_emulate("sysv_x86_64", "strcat", 16, b"BBBB", b"AAAA\x00")
    assert out[:8] == b"AAAABBBB" and out[8] == 0
    assert code == 0
    out, code = _x86_emulate("sysv_x86_64", "strcat", 16, b"C" * 40, b"AAAA\x00")
    assert out[15] == 0
    assert code == 1


def test_arm64_strcpy_guard_bounds_and_returns():
    out, code = _arm_emulate("strcpy", 16, b"A" * 40, b"")
    assert out[15] == 0 and out[:15] == b"A" * 15
    assert out[16:24] == b"\x00" * 8
    assert code == 1
    out, code = _arm_emulate("strcpy", 16, b"hi", b"")
    assert out[:3] == b"hi\x00"
    assert code == 0


def test_arm64_strcat_guard_appends_within_capacity():
    out, code = _arm_emulate("strcat", 16, b"BBBB", b"AAAA\x00")
    assert out[:8] == b"AAAABBBB" and out[8] == 0
    assert code == 0
    out, code = _arm_emulate("strcat", 16, b"C" * 40, b"AAAA\x00")
    assert out[15] == 0
    assert code == 1


def test_guard_encodings_disassemble_cleanly():
    for abi in ("sysv_x86_64", "win64_x86_64"):
        code = build_guard(abi, "strcpy", 16)
        ins = list(Cs(CS_ARCH_X86, CS_MODE_64).disasm(code, 0))
        assert ins and all(item.mnemonic for item in ins)
        assert ins[0].mnemonic == "xor"
    code = build_guard("aapcs64", "strcpy", 16)
    ins = list(Cs(CS_ARCH_ARM64, CS_MODE_ARM).disasm(code, 0))
    assert ins and ins[0].mnemonic == "mov"
    assert ins[-1].mnemonic == "ret"


def test_guard_rejects_bad_capacity():
    with pytest.raises(ValueError):
        build_guard("aapcs64", "strcpy", 0)
    with pytest.raises(ValueError):
        build_guard("aapcs64", "strcpy", 5000)
    with pytest.raises(ValueError):
        build_guard("unknown", "strcpy", 16)
