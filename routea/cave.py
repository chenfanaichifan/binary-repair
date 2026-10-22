"""Route A strategy C: redirect the strcpy call into a code cave.

The cave owns the guard: scan NUL, compare with ``max_valid_input_bytes``, then
either jump to the existing ``strcpy@plt`` (which returns to ``0x401309``) or
print the exact stderr and ``exit_group(1)``.

No new PLT entry is needed: this binary already imports ``fprintf`` and has the
``stderr`` object. The exact stderr string still needs a data home; the worker
places it after the code in the same cave. Whether that is allowed is part of the
pending Gate 3 scope ruling, so ``build`` is gated.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from elftools.elf.elffile import ELFFile

from app.domain.contracts import SecurityContract
from routea.worker import (
    EditManifest,
    FunctionInfo,
    RouteAError,
    ScopeNotAuthorized,
    _bytes_at,
    _file_offset,
    _loads,
    _plt_map,
    _reloc_counts,
    _sha,
    _sym,
    decode_function,
)

MD = Cs(CS_ARCH_X86, CS_MODE_64)


@dataclass(frozen=True)
class CavePlan:
    target: FunctionInfo
    call_site: int
    cave_addr: int
    cave_size: int
    rx_vaddr: int
    rx_new_size: int
    redirect: bytes
    code: bytes
    message: bytes
    message_addr: int
    stderr_vaddr: int
    fprintf_plt: int
    strcpy_plt: int
    max_valid_input: int

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "strategy": "cave_call_redirect",
            "target": self.target.to_dict(),
            "call_site": hex(self.call_site),
            "cave_addr": hex(self.cave_addr),
            "cave_size": self.cave_size,
            "rx_vaddr": hex(self.rx_vaddr),
            "rx_new_size": hex(self.rx_new_size),
            "redirect_hex": self.redirect.hex(),
            "code_hex": self.code.hex(),
            "message": self.message.decode("ascii"),
            "message_hex": self.message.hex(),
            "message_addr": hex(self.message_addr),
            "stderr_vaddr": hex(self.stderr_vaddr),
            "fprintf_plt": hex(self.fprintf_plt),
            "strcpy_plt": hex(self.strcpy_plt),
            "max_valid_input": self.max_valid_input,
        }


def _encode_cave(
    *,
    cave_addr: int,
    message_addr: int,
    stderr_vaddr: int,
    fprintf_plt: int,
    strcpy_plt: int,
    max_valid: int,
) -> bytes:
    # entry: rdi = dest, rsi = data (from the original call site)
    code = bytearray(b"\x49\x89\xf0")              # mov r8, rsi
    code += b"\x31\xc9"                            # xor ecx, ecx
    code += b"\x41\x80\x3c\x08\x00"                # cmp byte [r8+rcx], 0
    code += b"\x74\x05"                            # je after inc+jmp
    code += b"\x48\xff\xc1"                        # inc rcx
    code += b"\xeb\xf4"                            # jmp back
    code += b"\x48\x81\xf9" + struct.pack("<I", max_valid)
    jbe_at = len(code)
    code += b"\x0f\x86\x00\x00\x00\x00"            # jbe valid
    code += b"\x48\x83\xec\x08"                    # sub rsp, 8 (align before call)
    mov_rdi_at = len(code)
    code += b"\x48\x8b\x3d\x00\x00\x00\x00"        # mov rdi, [rip+stderr]
    lea_rsi_at = len(code)
    code += b"\x48\x8d\x35\x00\x00\x00\x00"        # lea rsi, [rip+msg]
    code += b"\x31\xc0"                            # xor eax, eax
    call_at = len(code)
    code += b"\xe8\x00\x00\x00\x00"                # call fprintf@plt
    code += b"\xb8\xe7\x00\x00\x00"                # mov eax, 231
    code += b"\xbf\x01\x00\x00\x00"                # mov edi, 1
    code += b"\x0f\x05"                            # syscall
    valid_at = len(code)
    jmp_at = len(code)
    code += b"\xe9\x00\x00\x00\x00"                # jmp strcpy@plt

    def rel32(at: int, target: int, end: int) -> None:
        code[at:at + 4] = struct.pack("<i", target - end)

    rel32(jbe_at + 2, cave_addr + valid_at, cave_addr + jbe_at + 6)
    code[mov_rdi_at + 3:mov_rdi_at + 7] = struct.pack(
        "<i", stderr_vaddr - (cave_addr + mov_rdi_at + 7)
    )
    code[lea_rsi_at + 3:lea_rsi_at + 7] = struct.pack(
        "<i", message_addr - (cave_addr + lea_rsi_at + 7)
    )
    rel32(call_at + 1, fprintf_plt, cave_addr + call_at + 5)
    rel32(jmp_at + 1, strcpy_plt, cave_addr + jmp_at + 5)
    return bytes(code)


def _call_site_ok(elf_path: Path, call_site: int, strcpy_plt: int) -> bool:
    with elf_path.open("rb") as fh:
        elf = ELFFile(fh)
        off = _file_offset(elf, call_site)
    fh = elf_path.open("rb")
    try:
        fh.seek(off)
        raw = fh.read(5)
    finally:
        fh.close()
    return len(raw) == 5 and raw[0] == 0xE8 and int.from_bytes(raw[1:], "little", signed=True) + call_site + 5 == strcpy_plt


def _rx_cave_segment(elf_path: Path, addr: int, size: int) -> int:
    """Return the RX LOAD vaddr when addr..addr+size is file-backed.

    The cave may sit after p_filesz but still inside the file (zero padding);
    extending p_filesz/p_memsz maps it without adding a segment.
    """
    file_size = elf_path.stat().st_size
    with elf_path.open("rb") as fh:
        elf = ELFFile(fh)
        for seg in elf.iter_segments():
            if seg["p_type"] != "PT_LOAD" or not (seg["p_flags"] & 1):
                continue
            if seg["p_vaddr"] <= addr:
                file_end = seg["p_offset"] + (addr + size - seg["p_vaddr"])
                if file_end <= file_size:
                    return seg["p_vaddr"]
    raise RouteAError("cave must be inside an executable file-backed PT_LOAD")


def plan_route_a_cave(
    elf_path: Path,
    contract: SecurityContract,
    *,
    cave_addr: int,
    cave_size: int,
    call_site: int = 0x401304,
) -> CavePlan:
    target = decode_function(elf_path, contract.target_entry)
    if not (target.entry <= call_site < target.entry + target.size):
        raise RouteAError("call site is outside the target function")
    if not contract.invalid_stderr:
        raise RouteAError("contract has no invalid_stderr")
    message = contract.invalid_stderr.encode("ascii")
    with elf_path.open("rb") as fh:
        elf = ELFFile(fh)
        stderr_vaddr = _sym(elf, "stderr")
        plts = _plt_map(elf)
        by_name = {name: addr for addr, name in plts.items()}
        if "fprintf" not in by_name or "strcpy" not in by_name:
            raise RouteAError("fprintf/strcpy PLT entries are required")
        fprintf_plt, strcpy_plt = by_name["fprintf"], by_name["strcpy"]
    if not _call_site_ok(elf_path, call_site, strcpy_plt):
        raise RouteAError("call site is not a 5-byte call to strcpy@plt")
    rx_vaddr = _rx_cave_segment(elf_path, cave_addr, cave_size)
    rx_new_size = cave_addr + cave_size - rx_vaddr
    if rx_new_size <= 0:
        raise RouteAError("cave range is invalid")

    # Place code first, then the message in the cave; compute message address.
    placeholder = _encode_cave(
        cave_addr=cave_addr,
        message_addr=cave_addr,
        stderr_vaddr=stderr_vaddr,
        fprintf_plt=fprintf_plt,
        strcpy_plt=strcpy_plt,
        max_valid=contract.max_valid_input_bytes,
    )
    message_addr = cave_addr + len(placeholder)
    code = _encode_cave(
        cave_addr=cave_addr,
        message_addr=message_addr,
        stderr_vaddr=stderr_vaddr,
        fprintf_plt=fprintf_plt,
        strcpy_plt=strcpy_plt,
        max_valid=contract.max_valid_input_bytes,
    )
    if len(code) + len(message) > cave_size:
        raise RouteAError("cave is too small for code + message")
    redirect = b"\xe8" + struct.pack("<i", cave_addr - (call_site + 5))
    return CavePlan(target, call_site, cave_addr, cave_size, rx_vaddr,
                    rx_new_size, redirect, code, message, message_addr,
                    stderr_vaddr, fprintf_plt, strcpy_plt,
                    contract.max_valid_input_bytes)


def _segment_at(loads: list[dict], vaddr: int) -> dict | None:
    return next((s for s in loads if s["vaddr"] == vaddr), None)


def audit_cave_layout(original: Path, patched: Path, plan: CavePlan) -> dict:
    before = _loads(original)
    after = _loads(patched)
    rx = _segment_at(after, plan.rx_vaddr)
    old_rx = _segment_at(before, plan.rx_vaddr)
    checks = {
        "redirect_bytes": _bytes_at(patched, plan.call_site, 5) == plan.redirect,
        "cave_code": _bytes_at(patched, plan.cave_addr, len(plan.code)) == plan.code,
        "message_bytes": _bytes_at(patched, plan.message_addr, len(plan.message)) == plan.message,
        "harness_unchanged": _bytes_at(original, 0x401256, 90) == _bytes_at(patched, 0x401256, 90),
        "no_new_segments": sorted((s["vaddr"], s["flags"]) for s in before) ==
                           sorted((s["vaddr"], s["flags"]) for s in after),
        "relocations_unchanged": _reloc_counts(original) == _reloc_counts(patched),
        "no_wx": all(not (s["flags"] & 2 and s["flags"] & 1) for s in after),
        "rx_extended": bool(rx and old_rx and rx["filesz"] == plan.rx_new_size
                            and rx["memsz"] == plan.rx_new_size
                            and rx["flags"] == old_rx["flags"] == 5),
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "original_size": original.stat().st_size,
        "patched_size": patched.stat().st_size,
    }


def build_cave_patched(
    original: Path,
    plan: CavePlan,
    out: Path,
    *,
    scope_authorized: bool = False,
) -> EditManifest:
    if not scope_authorized:
        raise ScopeNotAuthorized(
            "cave call redirection plus exact-stderr data is a Gate 3 scope decision; "
            "pass scope_authorized=True only after the ruling"
        )
    data = bytearray(original.read_bytes())
    _extend_load_filesz(original, data, plan.rx_vaddr, plan.rx_new_size)
    for addr, blob in ((plan.call_site, plan.redirect),
                       (plan.cave_addr, plan.code),
                       (plan.message_addr, plan.message)):
        _write_at(original, data, addr, blob)
    out.write_bytes(bytes(data))
    audit = audit_cave_layout(original, out, plan)
    return EditManifest(
        original_sha256=_sha(original),
        patched_sha256=_sha(out),
        function={"name": plan.target.name, "entry": hex(plan.target.entry),
                  "size": plan.target.size},
        edits=[{"kind": "call_redirect", "vaddr": hex(plan.call_site),
                "size": 5, "new_hex": plan.redirect.hex(),
                "purpose": "redirect strcpy call to cave"}],
        mappings=[{"vaddr": hex(plan.cave_addr), "perm": "R-X",
                   "size": len(plan.code) + len(plan.message),
                   "purpose": "guard + exact stderr in existing cave"}],
        relocations_added=[],
        header_changes={"original_size": original.stat().st_size,
                        "patched_size": out.stat().st_size},
        scope_authorized=True,
        audit=audit,
    )


def _extend_load_filesz(original: Path, data: bytearray, vaddr: int, new_size: int) -> None:
    import struct
    with original.open("rb") as fh:
        elf = ELFFile(fh)
        if elf.elfclass != 64:
            raise RouteAError("only ELF64 is supported")
        phoff = elf.header["e_phoff"]
        phentsize = elf.header["e_phentsize"]
        phnum = elf.header["e_phnum"]
        for i in range(phnum):
            off = phoff + i * phentsize
            p_type = struct.unpack_from("<I", data, off)[0]
            p_vaddr = struct.unpack_from("<Q", data, off + 16)[0]
            if p_type == 1 and p_vaddr == vaddr:
                p_offset = struct.unpack_from("<Q", data, off + 8)[0]
                if p_offset + new_size > len(data):
                    raise RouteAError("extending p_filesz would run past EOF")
                struct.pack_into("<Q", data, off + 32, new_size)
                struct.pack_into("<Q", data, off + 40, new_size)
                return
    raise RouteAError("RX LOAD segment not found for extension")


def _file_offset_ext(elf: ELFFile, addr: int) -> int:
    for seg in elf.iter_segments():
        if seg["p_type"] != "PT_LOAD":
            continue
        if seg["p_vaddr"] <= addr:
            off = seg["p_offset"] + (addr - seg["p_vaddr"])
            end = elf.stream.seek(0, 2)
            if off < end:
                return off
    raise RouteAError(f"address {addr:#x} is not file-backed")


def _write_at(original: Path, data: bytearray, addr: int, blob: bytes) -> None:
    with original.open("rb") as fh:
        elf = ELFFile(fh)
        off = _file_offset_ext(elf, addr)
    data[off:off + len(blob)] = blob


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m routea.cave")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--elf", type=Path, required=True)
    pl.add_argument("--contract", type=Path, required=True)
    pl.add_argument("--cave", required=True, help="cave start address, e.g. 0x401318")
    pl.add_argument("--cave-size", type=int, required=True)
    pl.add_argument("--out", type=Path)
    args = ap.parse_args(list(argv) if argv is not None else None)
    contract = SecurityContract.from_dict(json.loads(args.contract.read_text()))
    plan = plan_route_a_cave(args.elf, contract, cave_addr=int(args.cave, 16),
                             cave_size=args.cave_size)
    text = json.dumps(plan.to_dict(), indent=2)
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
