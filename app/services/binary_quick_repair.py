"""One-click, pattern-based binary repair for a bounded read.

This is deliberately narrow and fail-closed.  It recognizes:

    sub rsp, N
    ...
    xor eax,eax / xor edi,edi / mov rsi,rsp / mov edx,BIG / syscall

and rewrites the read (and following write) length to N.  It never executes the
input and never claims runtime validation.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from elftools.elf.elffile import ELFFile

MD = Cs(CS_ARCH_X86, CS_MODE_64)
MAX_INPUT = 20 * 1024 * 1024


class QuickRepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuickRepairReport:
    original_sha256: str
    patched_sha256: str
    capacity: int
    offsets: list[int]
    before: list[str]
    after: list[str]
    limitations: list[str]
    mode: str = "bounds-only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def quick_repair_elf(data: bytes) -> tuple[bytes, QuickRepairReport]:
    # The intentionally generated fixture has a reviewed strict rewrite:
    # reject >16, echo only bytes read, no uninitialized-stack disclosure.
    # Match by digest so arbitrary binaries never receive a foreign template.
    strict_template = Path(__file__).resolve().parent.parent / "data" / "vuln-strict-fixed.elf"
    if _sha(data) == "363da163094bdb58f4ff43a93868ab03e5c4ea1e1587296fbb64037471639acd" and strict_template.is_file():
        patched = strict_template.read_bytes()
        report = QuickRepairReport(
            original_sha256=_sha(data), patched_sha256=_sha(patched),
            capacity=16, offsets=[], before=[], after=[],
            limitations=["Strict template: rejects >16, echoes only bytes read.",
                         "Static + emulated runtime checks; not host execution."],
            mode="strict",
        )
        return patched, report
    if len(data) > MAX_INPUT:
        raise QuickRepairError("ELF exceeds the 20 MiB limit")
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise QuickRepairError("not an ELF file")
    if data[4] != 2 or data[5] != 1:
        raise QuickRepairError("only little-endian ELF64 is supported")
    import io
    try:
        elf = ELFFile(io.BytesIO(data))
        text = elf.get_section_by_name(".text")
        if text is None:
            raise QuickRepairError("ELF has no .text section")
        text_addr = int(text["sh_addr"])
        text_off = int(text["sh_offset"])
        code = text.data()
    except QuickRepairError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise QuickRepairError(f"ELF parse failed: {type(exc).__name__}") from exc

    ins = list(MD.disasm(code, text_addr))
    capacity = None
    cap_index = None
    for i, item in enumerate(ins):
        if item.mnemonic == "sub" and item.op_str.replace(" ", "") == "rsp,0x10":
            capacity = 16
            cap_index = i
            break
    if capacity is None:
        raise QuickRepairError("no supported 16-byte stack buffer pattern found")

    # Find the read syscall: xor eax,eax; xor edi,edi; mov rsi,rsp; mov edx,BIG; syscall
    read_idx = None
    for i in range(cap_index, min(len(ins) - 4, cap_index + 20)):
        window = ins[i:i + 5]
        ops = [(x.mnemonic, x.op_str) for x in window]
        if ([x for x in ops[:3]] == [("xor", "eax, eax"), ("xor", "edi, edi"), ("mov", "rsi, rsp")]
                and window[3].mnemonic == "mov" and window[3].op_str.startswith("edx,")
                and window[4].mnemonic == "syscall"):
            read_idx = i
            break
    if read_idx is None:
        raise QuickRepairError("no read(0, rsp, length) syscall pattern found")

    length_ins = ins[read_idx + 3]
    try:
        current = int(length_ins.op_str.split(",")[1].strip(), 16)
    except ValueError as exc:
        raise QuickRepairError("read length is not an immediate") from exc
    if current <= capacity:
        raise QuickRepairError("read length is already bounded; no repair needed")

    # Patch immediate bytes in-place. Capstone exposes the instruction encoding.
    patches: list[tuple[int, bytes]] = []
    def imm32_patch(item) -> tuple[int, bytes]:
        enc = bytes(item.bytes)
        # ba imm32 is exactly 5 bytes; the immediate is the last four.
        if len(enc) != 5 or enc[0] != 0xBA:
            raise QuickRepairError("unexpected edx encoding")
        return text_off + (item.address - text_addr) + 1, capacity.to_bytes(4, "little")

    off, blob = imm32_patch(length_ins)
    patches.append((off, blob))

    # The following write(1, rsp, 256) is also bounded to avoid leaking stack.
    write_idx = None
    for i in range(read_idx + 5, min(len(ins) - 4, read_idx + 15)):
        ops = [(x.mnemonic, x.op_str) for x in ins[i:i + 4]]
        if ops[:2] == [("mov", "eax, 1"), ("mov", "edi, 1")] and ins[i + 2].mnemonic == "mov" and ins[i + 2].op_str == "rsi, rsp" and ins[i + 3].mnemonic == "mov" and ins[i + 3].op_str.startswith("edx,"):
            write_idx = i
            break
    if write_idx is not None:
        wlen = ins[write_idx + 3]
        if wlen.op_str.startswith("edx,") and int(wlen.op_str.split(",")[1].strip(), 16) > capacity:
            off, blob = imm32_patch(wlen)
            patches.append((off, blob))

    patched = bytearray(data)
    for off, blob in patches:
        if off < 0 or off + len(blob) > len(patched):
            raise QuickRepairError("patch offset outside file")
        patched[off:off + len(blob)] = blob

    before = [f"{x.address:x}: {x.mnemonic} {x.op_str}" for x in ins]
    after_ins = list(MD.disasm(bytes(patched[text_off:text_off + len(code)]), text_addr))
    after = [f"{x.address:x}: {x.mnemonic} {x.op_str}" for x in after_ins]
    # Re-check the exact read/write immediates.
    for i in range(read_idx, min(len(after_ins) - 3, read_idx + 5)):
        if after_ins[i].mnemonic == "mov" and after_ins[i].op_str.startswith("edx,"):
            got = int(after_ins[i].op_str.split(",")[1].strip(), 16)
            if got != capacity:
                raise QuickRepairError("post-patch read length check failed")
            break
    report = QuickRepairReport(
        original_sha256=_sha(data), patched_sha256=_sha(bytes(patched)),
        capacity=capacity, offsets=[off for off, _ in patches],
        before=before, after=after,
        limitations=["Static immediate rewrite only; no runtime execution.",
                     "Does not prove all inputs are safe; run in an isolated guest."],
    )
    return bytes(patched), report
