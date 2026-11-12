#!/usr/bin/env python3
"""Build a strict fixed ELF for vuln.elf.

Behavior:
  * read at most 17 bytes into a 32-byte stack area
  * 0..16 bytes: echo exactly the bytes read, exit 0
  * 17+ bytes: stderr message, exit 1
No uninitialized stack bytes are written.
"""
from __future__ import annotations

import struct
from pathlib import Path

BASE = 0x400000
VADDR = BASE + 0x1000
PROMPT = b"input> "
ERROR = b"input too long (max 16 bytes)\n"

code = bytearray()
labels: dict[str, int] = {}
patches: list[tuple[str, int, int]] = []  # kind, at, label


def emit(data: bytes) -> None:
    code.extend(data)


def mark(name: str) -> None:
    labels[name] = VADDR + len(code)


def lea_rsi(label: str) -> None:
    emit(b"\x48\x8d\x35\x00\x00\x00\x00")
    patches.append(("rel32", len(code) - 4, label))


def jcc(label: str, opcode: int = 0x87) -> None:
    # jcc rel32: 0x0f 0x87 <disp32>
    emit(bytes([0x0F, opcode, 0, 0, 0, 0]))
    patches.append(("rel32", len(code) - 4, label))


def jmp(label: str) -> None:
    emit(b"\xe9\x00\x00\x00\x00")
    patches.append(("rel32", len(code) - 4, label))


def mov_edx(value: int) -> None:
    emit(b"\xba" + struct.pack("<I", value))


# prompt
emit(b"\xb8\x01\x00\x00\x00")
emit(b"\xbf\x01\x00\x00\x00")
lea_rsi("prompt")
mov_edx(len(PROMPT))
emit(b"\x0f\x05")

# Read until EOF or 17 bytes into a 32-byte area.  A single read(17) can
# return a short count on a pipe; looping makes the boundary decision robust.
emit(b"\x48\x83\xec\x20")      # sub rsp, 32
emit(b"\x45\x31\xe4")          # xor r12d, r12d  (total)
mark("read_loop")
emit(b"\x31\xc0")               # xor eax, eax (read)
emit(b"\x31\xff")               # xor edi, edi
emit(b"\x48\x89\xe6")          # mov rsi, rsp
emit(b"\x4c\x01\xe6")          # add rsi, r12
mov_edx(17)                     # read at most 17 total
emit(b"\x44\x29\xe2")          # sub edx, r12d  (never overrun the 32-byte buffer)
emit(b"\x0f\x05")               # syscall
emit(b"\x48\x85\xc0")          # test rax, rax
jcc("reject", opcode=0x88)      # js reject (read error)
jcc("done", opcode=0x84)        # jz done (EOF)
emit(b"\x49\x01\xc4")          # add r12, rax
emit(b"\x49\x83\xfc\x10")      # cmp r12, 16
jcc("reject")                   # ja reject
jmp("read_loop")                # keep reading until EOF/17
mark("done")
emit(b"\x4c\x89\xe2")          # mov rdx, r12 (write exactly bytes read)
emit(b"\xb8\x01\x00\x00\x00")  # mov eax, 1
emit(b"\xbf\x01\x00\x00\x00")  # mov edi, 1
emit(b"\x48\x89\xe6")          # mov rsi, rsp
emit(b"\x0f\x05")               # write
emit(b"\xb8\x3c\x00\x00\x00")  # exit(0)
emit(b"\x31\xff")
emit(b"\x0f\x05")

mark("reject")
emit(b"\xb8\x01\x00\x00\x00")  # write(2, error, len)
emit(b"\xbf\x02\x00\x00\x00")
lea_rsi("error")
mov_edx(len(ERROR))
emit(b"\x0f\x05")
emit(b"\xb8\x3c\x00\x00\x00")  # exit(1)
emit(b"\xbf\x01\x00\x00\x00")
emit(b"\x0f\x05")

mark("prompt")
prompt_off = len(code)
code += PROMPT
mark("error")
error_off = len(code)
code += ERROR

# patch label addresses
for kind, at, name in patches:
    target = labels[name] if name in labels else VADDR + (prompt_off if name == "prompt" else error_off)
    if kind == "rel8":
        disp = target - (VADDR + at + 1)
        if not -128 <= disp <= 127:
            raise SystemExit("rel8 out of range")
        code[at] = disp & 0xFF
    else:
        disp = target - (VADDR + at + 4)
        code[at:at + 4] = struct.pack("<i", disp)

# ELF header + one PT_LOAD + .text/.shstrtab
ehdr = bytearray(64)
ehdr[0:4] = b"\x7fELF"
ehdr[4] = 2
ehdr[5] = 1
ehdr[6] = 1
struct.pack_into("<HHIQQQIHHHHHH", ehdr, 16,
                 2, 62, 1, VADDR, 64, 0, 0, 64, 56, 1, 0, 0, 0)
phdr = bytearray(56)
struct.pack_into("<IIQQQQQQ", phdr, 0,
                 1, 5, 0, BASE, BASE, 0x1000 + len(code), 0x1000 + len(code), 0x1000)

shstr = b"\x00.text\x00.shstrtab\x00"
text_off = 0x1000
shstr_off = text_off + len(code)
shoff = (shstr_off + len(shstr) + 7) & ~7
sh = bytearray(shoff + 3 * 64)
struct.pack_into("<IIQQQQIIQQ", sh, 64, 1, 1, 0x6, VADDR, text_off, len(code), 0, 0, 16, 0)
struct.pack_into("<IIQQQQIIQQ", sh, 128, 7, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
ehdr[0x28:0x30] = struct.pack("<Q", shoff)
ehdr[0x3a:0x3c] = struct.pack("<H", 64)
ehdr[0x3c:0x3e] = struct.pack("<H", 3)
ehdr[0x3e:0x40] = struct.pack("<H", 2)

body = bytearray(shoff)
body[0:64] = ehdr
body[64:120] = phdr
body[text_off:text_off + len(code)] = code
body[shstr_off:shstr_off + len(shstr)] = shstr
body[shoff:shoff + 3 * 64] = sh

out = Path(__file__).with_name("vuln-strict-fixed.elf")
out.write_bytes(bytes(body))
out.chmod(0o755)
print(out, "code bytes", len(code), "size", len(body))
