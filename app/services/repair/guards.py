"""Position-independent bounded-copy guards.

Each guard implements the destination-bound part of ``strcpy``/``strcat`` for a
specific ABI and capacity, and returns ``0`` on success / ``1`` on overflow,
terminating the destination at ``capacity - 1``.  Guards are leaf functions:
they use no stack, make no syscalls and only touch caller-saved registers.

The capacity is encoded in the guard itself, so a call site only has to be
redirected to the injected block.  Capacities above 4095 are rejected for
AArch64 because the terminating store uses a 12-bit unsigned immediate.
"""
from __future__ import annotations

import struct

MAX_ARM64_CAPACITY = 0xFFF

ABI_DST_SRC = {
    "sysv_x86_64": ("rdi", "rsi"),
    "win64_x86_64": ("rcx", "rdx"),
    "aapcs64": ("x0", "x1"),
}

# SIB base encodings for the x86-64 guards.
_X86_BASE = {"rax": 0, "rcx": 1, "rdx": 2, "rsi": 6, "rdi": 7}


def _patch_rel8(code: bytearray, at: int, target: int) -> None:
    code[at + 1] = (target - (at + 2)) & 0xFF


def _x86_strcpy(dst_sib: int, src_sib: int, capacity: int) -> bytes:
    code = bytearray()
    code += b"\x31\xC0"                              # xor eax,eax
    code += b"\x3D" + struct.pack("<I", capacity)    # cmp eax,capacity
    jae_at = len(code)
    code += b"\x73\x00"                              # jae overflow
    code += bytes([0x44, 0x8A, 0x14, src_sib])       # mov r10b,[src+rax]
    code += bytes([0x44, 0x88, 0x14, dst_sib])       # mov [dst+rax],r10b
    code += b"\xFF\xC0"                              # inc eax
    code += b"\x45\x84\xD2"                          # test r10b,r10b
    jne_at = len(code)
    code += b"\x75\x00"                              # jne loop
    code += b"\x31\xC0\xC3"                          # xor eax,eax; ret
    overflow = len(code)
    code += bytes([0xC6, 0x44, dst_sib, 0xFF, 0x00])  # mov byte [dst+rax-1],0
    code += b"\xB8\x01\x00\x00\x00\xC3"              # mov eax,1; ret
    _patch_rel8(code, jae_at, overflow)
    _patch_rel8(code, jne_at, 2)
    return bytes(code)


def _x86_strcat(dst_sib: int, src_sib: int, capacity: int) -> bytes:
    code = bytearray()
    code += b"\x31\xC0"                                    # xor eax,eax
    find = len(code)
    code += b"\x3D" + struct.pack("<I", capacity)          # cmp eax,capacity
    jae_find = len(code)
    code += b"\x73\x00"                                    # jae overflow
    code += bytes([0x80, 0x3C, dst_sib, 0x00])             # cmp byte [dst+rax],0
    je_append = len(code)
    code += b"\x74\x00"                                    # je append
    code += b"\xFF\xC0"                                    # inc eax
    jmp_find = len(code)
    code += b"\xEB\x00"                                    # jmp find
    append = len(code)
    code += b"\x3D" + struct.pack("<I", capacity)          # cmp eax,capacity
    jae_append = len(code)
    code += b"\x73\x00"                                    # jae overflow
    code += bytes([0x44, 0x8A, 0x12 if src_sib == 2 else 0x16])  # mov r10b,[src]
    code += b"\x48\xFF\xC2" if src_sib == 2 else b"\x48\xFF\xC6"  # inc src
    code += bytes([0x44, 0x88, 0x14, dst_sib])             # mov [dst+rax],r10b
    code += b"\xFF\xC0"                                    # inc eax
    code += b"\x45\x84\xD2"                                # test r10b,r10b
    jne_append = len(code)
    code += b"\x75\x00"                                    # jne append
    code += b"\x31\xC0\xC3"                                # xor eax,eax; ret
    overflow = len(code)
    code += bytes([0xC6, 0x44, dst_sib, 0xFF, 0x00])       # mov byte [dst+rax-1],0
    code += b"\xB8\x01\x00\x00\x00\xC3"                    # mov eax,1; ret
    _patch_rel8(code, jae_find, overflow)
    _patch_rel8(code, je_append, append)
    _patch_rel8(code, jmp_find, find)
    _patch_rel8(code, jae_append, overflow)
    _patch_rel8(code, jne_append, append)
    return bytes(code)


class _Arm64Builder:
    def __init__(self) -> None:
        self.words: list[object] = []
        self.labels: dict[str, int] = {}

    def emit(self, word: int) -> None:
        self.words.append(word & 0xFFFFFFFF)

    def label(self, name: str) -> None:
        self.labels[name] = len(self.words)

    def b_cond(self, cond: int, label: str) -> None:
        self.words.append(("bcond", cond, label))

    def cbz(self, rt: int, label: str) -> None:
        self.words.append(("cbz", rt, label))

    def cbnz(self, rt: int, label: str) -> None:
        self.words.append(("cbnz", rt, label))

    def b(self, label: str) -> None:
        self.words.append(("b", label))

    def build(self) -> bytes:
        out: list[int] = []
        for index, item in enumerate(self.words):
            if isinstance(item, int):
                out.append(item)
                continue
            kind, *rest = item
            if kind == "bcond":
                cond, label = rest
                off = (self.labels[label] - index) * 4
                out.append(0x54000000 | (((off >> 2) & 0x7FFFF) << 5) | cond)
            elif kind in {"cbz", "cbnz"}:
                rt, label = rest
                off = (self.labels[label] - index) * 4
                opcode = 0x34000000 if kind == "cbz" else 0x35000000
                out.append(opcode | (((off >> 2) & 0x7FFFF) << 5) | rt)
            elif kind == "b":
                (label,) = rest
                off = (self.labels[label] - index) * 4
                out.append(0x14000000 | ((off >> 2) & 0x3FFFFFF))
            else:  # pragma: no cover - programming error
                raise ValueError(f"unknown pseudo {kind}")
        return b"".join(struct.pack("<I", word) for word in out)


def _movz(rd: int, imm: int) -> int:
    return 0xD2800000 | ((imm & 0xFFFF) << 5) | rd


def _cmp_imm(rn: int, imm: int) -> int:
    return 0xF1000000 | ((imm & 0xFFF) << 10) | (rn << 5) | 31


def _add_imm_w(rd: int, rn: int, imm: int) -> int:
    return 0x11000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd


def _add_imm_x(rd: int, rn: int, imm: int) -> int:
    return 0x91000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd


def _ldrb_reg(rt: int, rn: int, rm: int) -> int:
    return 0x38606820 | (rm << 16) | (rn << 5) | rt


def _strb_reg(rt: int, rn: int, rm: int) -> int:
    return 0x38206800 | (rm << 16) | (rn << 5) | rt


def _ldrb_imm(rt: int, rn: int, imm: int) -> int:
    return 0x39400000 | ((imm & 0xFFF) << 10) | (rn << 5) | rt


def _strb_imm(rt: int, rn: int, imm: int) -> int:
    return 0x39000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rt


def _arm64_strcpy(capacity: int) -> bytes:
    if capacity > MAX_ARM64_CAPACITY:
        raise ValueError("arm64 guard capacity exceeds the 12-bit immediate")
    b = _Arm64Builder()
    b.emit(_movz(9, 0))                 # 0:  mov w9,#0
    b.label("loop")
    b.emit(_cmp_imm(9, capacity))       # 4:  cmp w9,#capacity
    b.b_cond(2, "overflow")             # 8:  b.hs overflow
    b.emit(_ldrb_reg(10, 1, 9))         # 12: ldrb w10,[x1,x9]
    b.emit(_strb_reg(10, 0, 9))         # 16: strb w10,[x0,x9]
    b.cbz(10, "done")                   # 20: cbz w10,done
    b.emit(_add_imm_w(9, 9, 1))         # 24: add w9,w9,#1
    b.b("loop")                         # 28: b loop
    b.label("overflow")
    b.emit(_strb_imm(31, 0, capacity - 1))  # 32: strb wzr,[x0,#capacity-1]
    b.emit(_movz(0, 1))                 # 36: mov w0,#1
    b.emit(0xD65F03C0)                  # 40: ret
    b.label("done")
    b.emit(_movz(0, 0))                 # 44: mov w0,#0
    b.emit(0xD65F03C0)                  # 48: ret
    return b.build()


def _arm64_strcat(capacity: int) -> bytes:
    if capacity > MAX_ARM64_CAPACITY:
        raise ValueError("arm64 guard capacity exceeds the 12-bit immediate")
    b = _Arm64Builder()
    b.emit(_movz(9, 0))                 # w9 = index
    b.label("find")
    b.emit(_cmp_imm(9, capacity))       # cmp w9,#capacity
    b.b_cond(2, "overflow")             # b.hs overflow
    b.emit(_ldrb_reg(10, 0, 9))         # ldrb w10,[x0,x9]
    b.cbz(10, "append")                 # cbz w10,append
    b.emit(_add_imm_w(9, 9, 1))         # add w9,w9,#1
    b.b("find")
    b.label("append")
    b.emit(_cmp_imm(9, capacity))       # cmp w9,#capacity
    b.b_cond(2, "overflow")
    b.emit(_ldrb_imm(10, 1, 0))         # ldrb w10,[x1]
    b.emit(_add_imm_x(1, 1, 1))         # add x1,x1,#1
    b.emit(_strb_reg(10, 0, 9))         # strb w10,[x0,x9]
    b.emit(_add_imm_w(9, 9, 1))         # add w9,w9,#1
    b.cbnz(10, "append")                # cbnz w10,append
    b.emit(_movz(0, 0))                 # mov w0,#0
    b.emit(0xD65F03C0)                  # ret
    b.label("overflow")
    b.emit(_strb_imm(31, 0, capacity - 1))
    b.emit(_movz(0, 1))
    b.emit(0xD65F03C0)
    return b.build()


def build_guard(abi: str, op: str, capacity: int) -> bytes:
    """Return the machine code for one bounded-copy guard."""
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    if abi == "aapcs64":
        if op == "strcpy":
            return _arm64_strcpy(capacity)
        if op == "strcat":
            return _arm64_strcat(capacity)
        raise ValueError(f"unsupported arm64 guard op: {op}")
    if abi not in ABI_DST_SRC:
        raise ValueError(f"unsupported ABI: {abi}")
    dst, src = ABI_DST_SRC[abi]
    dst_sib = _X86_BASE[dst]
    src_sib = _X86_BASE[src]
    if op == "strcpy":
        return _x86_strcpy(dst_sib, src_sib, capacity)
    if op == "strcat":
        return _x86_strcat(dst_sib, src_sib, capacity)
    raise ValueError(f"unsupported x86 guard op: {op}")


def abi_for(format_name: str, arch: str) -> str:
    """Return the guard ABI for a container/architecture pair."""
    if arch == "arm64":
        return "aapcs64"
    if format_name == "pe":
        return "win64_x86_64"
    return "sysv_x86_64"
