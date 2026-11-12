#!/usr/bin/env python3
"""Generate a minimal, intentionally vulnerable x86-64 Linux ELF.

No libc, no linker: one R-X PT_LOAD, raw syscalls.
Vulnerability: read(0, stack_buf, 256) where stack_buf is only 16 bytes.
For local, isolated testing only.
"""
from __future__ import annotations

import struct
from pathlib import Path

BASE = 0x400000
CODE_VADDR = BASE + 0x1000
PROMPT = b"input> "

code = bytearray()
labels: dict[str, int] = {}


def emit(data: bytes) -> None:
    code.extend(data)


def label(name: str) -> None:
    labels[name] = CODE_VADDR + len(code)


prompt_patch_at = 0
# write(1, prompt, len(prompt))
emit(b"\xb8\x01\x00\x00\x00")          # mov eax, 1
emit(b"\xbf\x01\x00\x00\x00")          # mov edi, 1
emit(b"\x48\x8d\x35\x00\x00\x00\x00")  # lea rsi, [rip+prompt]
prompt_patch_at = len(code) - 4
emit(b"\xba" + struct.pack("<I", len(PROMPT)))  # mov edx, len
emit(b"\x0f\x05")                       # syscall

# vulnerable stack buffer: 16 bytes, read up to 256
emit(b"\x48\x83\xec\x10")              # sub rsp, 16
emit(b"\x31\xc0")                       # xor eax,eax (read)
emit(b"\x31\xff")                       # xor edi,edi (stdin)
emit(b"\x48\x89\xe6")                   # mov rsi,rsp
emit(b"\xba\x00\x01\x00\x00")          # mov edx,256
emit(b"\x0f\x05")                       # syscall

# write(1, rsp, 256) to make the overwrite observable
emit(b"\xb8\x01\x00\x00\x00")
emit(b"\xbf\x01\x00\x00\x00")
emit(b"\x48\x89\xe6")
emit(b"\xba\x00\x01\x00\x00")
emit(b"\x0f\x05")

# exit(0)
emit(b"\xb8\x3c\x00\x00\x00")
emit(b"\x31\xff")
emit(b"\x0f\x05")

prompt_addr = CODE_VADDR + len(code)
disp = prompt_addr - (CODE_VADDR + prompt_patch_at + 4)
code[prompt_patch_at:prompt_patch_at + 4] = struct.pack("<i", disp)
code += PROMPT

# ELF header + one PT_LOAD; no section table (valid loadable ELF).
ehdr = bytearray(64)
ehdr[0:4] = b"\x7fELF"
ehdr[4] = 2          # ELFCLASS64
ehdr[5] = 1          # little endian
ehdr[6] = 1          # EV_CURRENT
struct.pack_into("<HHIQQQIHHHHHH", ehdr, 16,
                 2, 62, 1, CODE_VADDR, 64, 0, 0, 64, 56, 1, 0, 0, 0)
phdr = bytearray(56)
struct.pack_into("<IIQQQQQQ", phdr, 0,
                 1, 5, 0, BASE, BASE, 0x1000 + len(code), 0x1000 + len(code), 0x1000)

# Add section headers so objdump/readelf can see .text (the program header
# alone is enough for the kernel, but tooling expects sections).
shstr = b"\x00.text\x00.shstrtab\x00"
text_off = 0x1000
shstr_off = text_off + len(code)
shoff = (shstr_off + len(shstr) + 7) & ~7
sh = bytearray(shoff + 3 * 64)
# .text
struct.pack_into("<IIQQQQIIQQ", sh, 64,
                 1, 1, 0x6, CODE_VADDR, text_off, len(code), 0, 0, 16, 0)
# .shstrtab
struct.pack_into("<IIQQQQIIQQ", sh, 128,
                 7, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)

ehdr[0x28:0x30] = struct.pack("<Q", shoff)  # e_shoff
ehdr[0x3a:0x3c] = struct.pack("<H", 64)     # e_shentsize
ehdr[0x3c:0x3e] = struct.pack("<H", 3)      # e_shnum
ehdr[0x3e:0x40] = struct.pack("<H", 2)      # e_shstrndx

body = bytearray(shoff)
body[0:64] = ehdr
body[64:120] = phdr
body[text_off:text_off + len(code)] = code
body[shstr_off:shstr_off + len(shstr)] = shstr
body[shoff:shoff + 3 * 64] = sh

out = Path(__file__).with_name("vuln.elf")
out.write_bytes(bytes(body))
out.chmod(0o755)
print(out)
print("code bytes:", len(code), "entry:", hex(CODE_VADDR), "size:", len(body))
