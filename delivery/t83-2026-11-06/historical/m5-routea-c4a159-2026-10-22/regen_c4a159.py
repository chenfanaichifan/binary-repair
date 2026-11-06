#!/usr/bin/env python3
"""Standalone deterministic regenerator for candidate c4a159…aa82.

No third-party imports. Applies the reviewed Strategy C patch to the frozen
original ELF: redirect call at 0x401304 to cave 0x4018e9, write 71-byte guard +
42-byte exact stderr, extend RX PT_LOAD filesz/memsz 0x8e9 -> 0x1000.
"""
import hashlib
import struct
import sys
from pathlib import Path

ORIGINAL_SHA = "aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393"
PATCHED_SHA = "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82"
CALL_OFF = 0x1304
CAVE_OFF = 0x18E9
MSG_OFF = 0x1930
RX_VADDR = 0x401000
RX_NEW_SIZE = 0x1000
CALL = bytes.fromhex("e8e0050000")
CODE = bytes.fromhex(
    "4989f031c941803c0800740548ffc1ebf44881f9310000000f8624000000"
    "b801000000bf02000000488d3518000000ba2a0000000f05b8e7000000bf"
    "010000000f05e9a0f7ffff"
)
MSG = bytes.fromhex(
    "4552524f523a20696e70757420657863656564732064657374696e617469"
    "6f6e2063617061636974790a"
)


def main(src: Path, dst: Path) -> int:
    data = bytearray(src.read_bytes())
    if hashlib.sha256(data).hexdigest() != ORIGINAL_SHA:
        raise SystemExit("original ELF hash mismatch")
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise SystemExit("not ELF64 little-endian")
    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phentsize = struct.unpack_from("<H", data, 0x36)[0]
    phnum = struct.unpack_from("<H", data, 0x38)[0]
    for i in range(phnum):
        off = phoff + i * phentsize
        p_type = struct.unpack_from("<I", data, off)[0]
        p_vaddr = struct.unpack_from("<Q", data, off + 16)[0]
        if p_type == 1 and p_vaddr == RX_VADDR:
            struct.pack_into("<Q", data, off + 32, RX_NEW_SIZE)
            struct.pack_into("<Q", data, off + 40, RX_NEW_SIZE)
            break
    else:
        raise SystemExit("RX PT_LOAD 0x401000 not found")
    data[CALL_OFF:CALL_OFF + 5] = CALL
    data[CAVE_OFF:CAVE_OFF + len(CODE)] = CODE
    data[MSG_OFF:MSG_OFF + len(MSG)] = MSG
    dst.write_bytes(bytes(data))
    dst.chmod(0o755)
    got = hashlib.sha256(dst.read_bytes()).hexdigest()
    print(f"wrote {dst} sha256={got}")
    if got != PATCHED_SHA:
        raise SystemExit(f"patched hash mismatch: {got}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: regen_c4a159.py ORIGINAL.elf OUT.elf")
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
