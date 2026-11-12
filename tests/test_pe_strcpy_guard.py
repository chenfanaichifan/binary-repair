from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_PROT_ALL
from unicorn.x86_const import UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_RSP

from app.services.pe_repair import build_pe_strcpy_guard

CODE = 0x1000
RET = 0x1500
STACK = 0x2000
DEST = 0x4000
SRC = 0x5000


def _run(src: bytes) -> tuple[int, bytes, bytes]:
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(CODE, 0x1000, UC_PROT_ALL)
    uc.mem_map(STACK, 0x1000, UC_PROT_ALL)
    uc.mem_map(DEST, 0x1000, UC_PROT_ALL)
    uc.mem_map(SRC, 0x1000, UC_PROT_ALL)
    uc.mem_write(CODE, build_pe_strcpy_guard(16))
    uc.mem_write(RET, b"\xC3")
    uc.mem_write(SRC, src)
    uc.mem_write(DEST, b"Z" * 32)
    uc.mem_write(STACK, RET.to_bytes(8, "little") + (0).to_bytes(8, "little"))
    uc.reg_write(UC_X86_REG_RSP, STACK)
    uc.reg_write(UC_X86_REG_RCX, DEST)
    uc.reg_write(UC_X86_REG_RDX, SRC)
    try:
        uc.emu_start(CODE, 0, count=200)
    except Exception:
        # The outer ret returns to 0; state is already available.
        pass
    return (uc.reg_read(UC_X86_REG_RAX),
            bytes(uc.mem_read(DEST, 32)),
            bytes(uc.mem_read(DEST + 16, 16)))


def test_pe_strcpy_guard_short_and_overflow():
    rax, dest, sentinel = _run(b"hi\x00")
    assert rax == 0
    assert dest[:3] == b"hi\x00"
    assert sentinel == b"Z" * 16

    rax, dest, sentinel = _run(b"A" * 32)
    assert rax == 1
    assert dest[15:16] == b"\x00"
    assert sentinel == b"Z" * 16
