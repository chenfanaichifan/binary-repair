"""32-bit x86 (i386) cdecl bounded-copy guards.

ABI: cdecl (SysV i386 and MinGW).  On entry the stack is::

    [esp]    = return address
    [esp+4]  = dst (char *)
    [esp+8]  = src (const char *)

The guard is a leaf function: it saves/restores the callee-saved ``edi``/``esi``
and uses only caller-saved ``eax``/``ecx``/``edx`` otherwise.  It returns ``0``
on success and ``1`` on overflow; on overflow the destination is terminated at
``capacity - 1`` and no byte past ``capacity - 1`` is written.  The capacity is
encoded in the guard body as an ``imm32`` compare, so a redirected call site
only has to jump into the injected block.
"""
from __future__ import annotations

import struct

MAX_CAPACITY = 0x7FFFFFFF


class _Builder:
    def __init__(self) -> None:
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    def emit(self, raw: bytes) -> None:
        self.code += raw

    def label(self, name: str) -> None:
        self.labels[name] = len(self.code)

    def jcc(self, opcode: int, name: str) -> None:
        self.code += bytes([opcode, 0x00])
        self.fixups.append((len(self.code) - 1, name))

    def jmp(self, name: str) -> None:
        self.jcc(0xEB, name)

    def build(self) -> bytes:
        for at, name in self.fixups:
            target = self.labels[name]
            disp = target - (at + 1)
            if not -128 <= disp <= 127:
                raise ValueError("i386 guard branch out of rel8 range")
            self.code[at] = disp & 0xFF
        return bytes(self.code)


def _prologue(b: _Builder) -> None:
    b.emit(b"\x57")                       # push edi
    b.emit(b"\x56")                       # push esi
    b.emit(b"\x8B\x7C\x24\x0C")           # mov edi,[esp+12]  ; dst
    b.emit(b"\x8B\x74\x24\x10")           # mov esi,[esp+16]  ; src
    b.emit(b"\x31\xC0")                   # xor eax,eax       ; index


def _epilogue(b: _Builder) -> None:
    b.emit(b"\x5E")                       # pop esi
    b.emit(b"\x5F")                       # pop edi
    b.emit(b"\xC3")                       # ret


def _overflow(b: _Builder, capacity: int) -> None:
    b.emit(b"\x31\xC9")                   # xor ecx,ecx
    b.emit(b"\x88\x4C\x07\xFF")           # mov [edi+eax-1],cl
    b.emit(b"\xB8" + struct.pack("<I", 1))  # mov eax,1
    _epilogue(b)


def _strcpy(capacity: int) -> bytes:
    b = _Builder()
    _prologue(b)
    b.label("loop")
    b.emit(b"\x3D" + struct.pack("<I", capacity))  # cmp eax,capacity
    b.jcc(0x73, "overflow")                        # jae overflow
    b.emit(b"\x8A\x0C\x06")                        # mov cl,[esi+eax]
    b.emit(b"\x88\x0C\x07")                        # mov [edi+eax],cl
    b.emit(b"\x40")                                # inc eax
    b.emit(b"\x84\xC9")                            # test cl,cl
    b.jcc(0x75, "loop")                            # jne loop
    b.emit(b"\x31\xC0")                            # xor eax,eax
    _epilogue(b)
    b.label("overflow")
    _overflow(b, capacity)
    return b.build()


def _strcat(capacity: int) -> bytes:
    b = _Builder()
    _prologue(b)
    b.label("find")
    b.emit(b"\x3D" + struct.pack("<I", capacity))  # cmp eax,capacity
    b.jcc(0x73, "overflow")                        # jae overflow
    b.emit(b"\x80\x3C\x07\x00")                    # cmp byte [edi+eax],0
    b.jcc(0x74, "append")                          # je append
    b.emit(b"\x40")                                # inc eax
    b.jmp("find")
    b.label("append")
    b.emit(b"\x3D" + struct.pack("<I", capacity))  # cmp eax,capacity
    b.jcc(0x73, "overflow")                        # jae overflow
    b.emit(b"\x8A\x0E")                            # mov cl,[esi]
    b.emit(b"\x46")                                # inc esi
    b.emit(b"\x88\x0C\x07")                        # mov [edi+eax],cl
    b.emit(b"\x40")                                # inc eax
    b.emit(b"\x84\xC9")                            # test cl,cl
    b.jcc(0x75, "append")                          # jne append
    b.emit(b"\x31\xC0")                            # xor eax,eax
    _epilogue(b)
    b.label("overflow")
    _overflow(b, capacity)
    return b.build()


def build_i386_guard(op: str, capacity: int) -> bytes:
    """Return 32-bit cdecl machine code for one bounded-copy guard."""
    if not 0 < capacity <= MAX_CAPACITY:
        raise ValueError("capacity must be positive and <= 0x7fffffff")
    if op == "strcpy":
        return _strcpy(capacity)
    if op == "strcat":
        return _strcat(capacity)
    raise ValueError(f"unsupported i386 guard op: {op}")
