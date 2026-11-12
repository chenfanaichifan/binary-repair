"""Direct AArch64 ELF immediate repair, no assembly text round-trip."""
from __future__ import annotations

import struct
from pathlib import Path

from app.services.arm64_repair import repair_arm64, scan_arm64

BASE = 0x400000
ENTRY = BASE + 0x1000
CODE = bytes.fromhex(
    "ff8300d1"   # sub sp, sp, #0x20
    "02208052"   # mov w2, #0x100
    "e8078052"   # mov w8, #63
    "010000d4"   # svc #0
    "08088052"   # mov w8, #64
    "010000d4"   # svc #0
    "a80b8052"   # mov w8, #93
    "010000d4"   # svc #0
)


def _elf() -> bytes:
    shstr = b"\x00.text\x00.shstrtab\x00"
    off = 0x1000
    shstr_off = off + len(CODE)
    shoff = (shstr_off + len(shstr) + 7) & ~7
    body = bytearray(shoff)
    eh = bytearray(64); eh[:4] = b"\x7fELF"; eh[4] = 2; eh[5] = 1; eh[6] = 1
    struct.pack_into("<HHIQQQIHHHHHH", eh, 16, 2, 183, 1, ENTRY, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    ph = bytearray(56)
    struct.pack_into("<IIQQQQQQ", ph, 0, 1, 5, 0, BASE, BASE, 0x1000 + len(CODE), 0x1000 + len(CODE), 0x1000)
    sh = bytearray(3 * 64)
    struct.pack_into("<IIQQQQIIQQ", sh, 64, 1, 1, 6, ENTRY, off, len(CODE), 0, 0, 16, 0)
    struct.pack_into("<IIQQQQIIQQ", sh, 128, 7, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
    eh[0x28:0x30] = struct.pack("<Q", shoff); eh[0x3A:0x3C] = struct.pack("<H", 64)
    eh[0x3C:0x3E] = struct.pack("<H", 3); eh[0x3E:0x40] = struct.pack("<H", 2)
    body[:64] = eh; body[64:120] = ph
    body[off:off + len(CODE)] = CODE
    body[shstr_off:shstr_off + len(shstr)] = shstr
    body[shoff:shoff + 3 * 64] = sh
    return bytes(body)


def test_arm64_scan_and_immediate_patch():
    data = _elf()
    scan = scan_arm64(data)
    assert scan["arch"] == "arm64"
    assert len(scan["findings"]) == 1
    patched, report = repair_arm64(data)
    assert patched is not None
    assert report.status == "patched"
    assert report.capacity == 32
    assert struct.unpack_from("<I", patched, 0x1004)[0] == 0x52800402
    assert len(patched) == len(data)
