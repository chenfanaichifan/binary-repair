"""PE32+ writeback primitives: sections and direct byte patches.

LIEF parses/writes structure; call-site analysis stays in raw bytes.  No PE is
executed on the host.
"""
from __future__ import annotations

import hashlib
import re
import struct
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import lief


@dataclass
class PEWriteReport:
    original_sha256: str
    patched_sha256: str
    backend: str = "pe"
    arch: str = ""
    status: str = "unsupported"
    strategy: str = "section"
    section: str = ""
    section_va: int = 0
    section_size: int = 0
    checksum: int | None = None
    signature_invalidated: bool = False
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def add_rx_section(data: bytes, code: bytes, *, name: str = ".brfix") -> tuple[bytes | None, PEWriteReport]:
    report = PEWriteReport(original_sha256=_sha(data), patched_sha256=_sha(data))
    try:
        pe = lief.PE.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        report.limitations.append(f"LIEF parse failed: {type(exc).__name__}")
        return None, report
    if pe is None:
        report.limitations.append("not a PE image")
        return None, report
    report.arch = str(pe.header.machine)
    if ("AMD64" not in report.arch and "ARM64" not in report.arch
            and "I386" not in report.arch):
        report.limitations.append(
            "only PE32 x86, PE32+ x86-64 and PE32+ arm64 are supported"
        )
        return None, report
    if pe.has_signatures:
        report.signature_invalidated = True
        report.limitations.append("Authenticode signature will be invalidated")
    section_va = 0
    for sec in pe.sections:
        section_va = max(section_va, int(sec.virtual_address) + _align(int(sec.virtual_size or len(sec.content)), 0x1000))
    sec = lief.PE.Section(name)
    sec.content = list(code)
    sec.virtual_address = section_va
    sec.characteristics = (
        lief.PE.Section.CHARACTERISTICS.MEM_READ
        | lief.PE.Section.CHARACTERISTICS.MEM_EXECUTE
        | lief.PE.Section.CHARACTERISTICS.CNT_CODE
    )
    try:
        pe.add_section(sec)
        with tempfile.TemporaryDirectory(prefix="pe-repair-") as tmp:
            path = Path(tmp) / "out.exe"
            pe.write(str(path))
            patched = path.read_bytes()
        check = lief.PE.parse(list(patched))
        if check is None:
            report.limitations.append("LIEF could not reparse the patched PE")
            return None, report
        found = check.get_section(name)
        if found is None or len(found.content) < len(code):
            report.limitations.append("new section missing after writeback")
            return None, report
        report.patched_sha256 = _sha(patched)
        report.status = "written"
        report.section = name
        report.section_va = section_va
        report.section_size = len(code)
        report.limitations.append("Static section writeback only; PE runtime not executed.")
        return patched, report
    except Exception as exc:  # noqa: BLE001
        report.limitations.append(f"PE writeback failed: {type(exc).__name__}: {exc}")
        return None, report


def patch_pe_call_site(data: bytes, cave_code: bytes, *,
                       call_va: int | None = None) -> tuple[bytes | None, PEWriteReport]:
    """Append an R-X cave and redirect one direct call.

    This is a writeback primitive; the caller is responsible for supplying a
    semantically correct wrapper.  The cave bytes are written verbatim.
    """
    patched, report = add_rx_section(data, cave_code)
    if patched is None:
        return None, report
    try:
        pe = lief.PE.parse(list(patched))
        text = pe.get_section(".text")
        if text is None:
            report.limitations.append("patched PE has no .text")
            return None, report
        text_va = int(pe.optional_header.imagebase) + int(text.virtual_address)
        raw = int(text.pointerto_raw_data)
        if call_va is None:
            # First direct call in .text, for a deterministic smoke test.
            from capstone import CS_ARCH_X86, CS_MODE_64, Cs
            ins = Cs(CS_ARCH_X86, CS_MODE_64).disasm(bytes(text.content), text_va)
            call = next((x for x in ins if x.mnemonic == "call"), None)
            if call is None:
                report.limitations.append("no call instruction found")
                return None, report
            call_va = call.address
        off = raw + (call_va - text_va)
        if off < 0 or off + 6 > len(patched):
            report.limitations.append("call site outside file")
            return None, report
        original = patched[off:off + 6]
        if original[0] == 0xE8:
            size = 5
        elif original[0] == 0xFF and original[1] == 0x15:
            size = 6
        else:
            report.limitations.append("call site is not E8 rel32 or FF15 IAT")
            return None, report
        cave_va = int(pe.optional_header.imagebase) + int(report.section_va)
        report.section_va = cave_va
        disp = cave_va - (call_va + 5)
        if not -(1 << 31) <= disp < (1 << 31):
            report.limitations.append("call target out of rel32 range")
            return None, report
        out = bytearray(patched)
        out[off:off + 5] = b"\xE8" + disp.to_bytes(4, "little", signed=True)
        if size == 6:
            out[off + 5] = 0x90
        check = lief.PE.parse(list(out))
        if check is None:
            report.limitations.append("patched PE did not reparse")
            return None, report
        report.status = "patched"
        report.strategy = "call-cave"
        report.patched_sha256 = _sha(bytes(out))
        report.limitations.append("Call-site primitive only; wrapper semantics must be validated separately.")
        return bytes(out), report
    except Exception as exc:  # noqa: BLE001
        report.limitations.append(f"PE call patch failed: {type(exc).__name__}: {exc}")
        return None, report


def build_pe_strcpy_guard(capacity: int) -> bytes:
    """Windows x64 strcpy guard: rcx=dst, rdx=src, capacity bounded.

    The wrapper copies at most capacity bytes including the NUL.  On overflow it
    terminates the destination at capacity-1 and returns 1; success returns 0.
    It never falls through to the original import call.
    """
    if not 0 < capacity <= 0x7FFFFFFF:
        raise ValueError("capacity out of range")
    code = bytearray()
    code += b"\x31\xC0"                              # xor eax,eax
    code += b"\x3D" + struct.pack("<I", capacity)   # cmp eax,capacity
    jae_at = len(code); code += b"\x73\x00"          # jae overflow
    code += b"\x44\x8A\x14\x02"                      # mov r10b,[rdx+rax]
    code += b"\x44\x88\x14\x01"                      # mov [rcx+rax],r10b
    code += b"\xFF\xC0"                              # inc eax
    code += b"\x45\x84\xD2"                          # test r10b,r10b
    jne_at = len(code); code += b"\x75\x00"          # jne loop
    code += b"\x31\xC0"                              # xor eax,eax
    code += b"\xC3"                                  # ret
    overflow = len(code)
    code += b"\xC6\x44\x01\xFF\x00"                 # mov byte [rcx+rax-1],0
    code += b"\xB8\x01\x00\x00\x00"                 # mov eax,1
    code += b"\xC3"                                  # ret
    code[jae_at + 1] = (overflow - (jae_at + 2)) & 0xFF
    code[jne_at + 1] = (2 - (jne_at + 2)) & 0xFF
    return bytes(code)


def repair_pe_strcpy(data: bytes, *, call_va: int, capacity: int) -> tuple[bytes | None, PEWriteReport]:
    """Replace one Windows-x64 strcpy call with a bounded cave wrapper."""
    guard = build_pe_strcpy_guard(capacity)
    patched, report = patch_pe_call_site(data, guard, call_va=call_va)
    if patched is None:
        return None, report
    report.strategy = "strcpy-cave"
    report.status = "patched"
    report.limitations.append(
        f"strcpy cave capacity={capacity}; overflow returns 1 and NUL-terminates "
        f"at capacity-1; no Authenticode signature is forged."
    )
    return patched, report


def scan_pe_copy_calls(data: bytes) -> dict[str, Any]:
    """Find Windows-x64 strcpy/strcat calls through the IAT."""
    out: dict[str, Any] = {"format": "pe", "arch": "unknown", "findings": []}
    try:
        pe = lief.PE.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    if pe is None:
        return out
    machine = str(pe.header.machine)
    if "AMD64" not in machine:
        out["arch"] = machine
        return out
    text = pe.get_section(".text")
    if text is None:
        return out
    imagebase = int(pe.optional_header.imagebase)
    iat: dict[int, str] = {}
    for imp in pe.imports:
        for entry in imp.entries:
            try:
                iat[imagebase + int(entry.iat_address)] = entry.name
            except Exception:
                continue
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    base = imagebase + int(text.virtual_address)
    capacity = None
    for ins in md.disasm(bytes(text.content), base):
        op = (ins.op_str or "").replace(" ", "")
        if ins.mnemonic == "sub" and op.startswith("rsp,"):
            try:
                capacity = int(op.split(",")[-1], 0)
            except ValueError:
                pass
        elif ins.mnemonic == "call" and "rip" in op:
            m = re.search(r"\[rip([+-]0x[0-9a-fA-F]+)\]", op)
            if not m:
                continue
            disp = int(m.group(1), 16)
            target = ins.address + ins.size + disp
            name = iat.get(target)
            if not name:
                continue
            low = name.lower()
            if "strcpy" not in low and "strcat" not in low:
                continue
            if capacity and capacity > 0:
                out["findings"].append({
                    "kind": "copy_call", "address": hex(ins.address),
                    "callee": name, "capacity": capacity,
                    "patchable": True,
                    "detail": "IAT call with stack capacity; cave candidate",
                })
    out["arch"] = "x86_64"
    return out


def build_pe_strcat_guard(capacity: int) -> bytes:
    """Windows x64 strcat guard: rcx=dst, rdx=src, total size bounded."""
    if not 1 < capacity <= 0x7FFFFFFF:
        raise ValueError("capacity out of range")
    code = bytearray()
    code += b"\x31\xC0"                              # xor eax,eax
    find = len(code)
    code += b"\x3D" + struct.pack("<I", capacity)   # cmp eax,capacity
    jae_find = len(code); code += b"\x73\x00"        # jae overflow
    code += b"\x80\x3C\x01\x00"                      # cmp byte [rcx+rax],0
    je_append = len(code); code += b"\x74\x00"       # je append
    code += b"\xFF\xC0"                              # inc eax
    jmp_find = len(code); code += b"\xEB\x00"        # jmp find
    append = len(code)
    code += b"\x3D" + struct.pack("<I", capacity)   # cmp eax,capacity
    jae_append = len(code); code += b"\x73\x00"      # jae overflow
    code += b"\x44\x8A\x12"                          # mov r10b,[rdx]
    code += b"\x48\xFF\xC2"                          # inc rdx
    code += b"\x44\x88\x14\x01"                      # mov [rcx+rax],r10b
    code += b"\xFF\xC0"                              # inc eax
    code += b"\x45\x84\xD2"                          # test r10b,r10b
    jne_append = len(code); code += b"\x75\x00"      # jne append
    code += b"\x31\xC0"                              # xor eax,eax
    code += b"\xC3"                                  # ret
    overflow = len(code)
    code += b"\xC6\x44\x01\xFF\x00"                 # mov byte [rcx+rax-1],0
    code += b"\xB8\x01\x00\x00\x00"                 # mov eax,1
    code += b"\xC3"                                  # ret
    code[jae_find + 1] = (overflow - (jae_find + 2)) & 0xFF
    code[je_append + 1] = (append - (je_append + 2)) & 0xFF
    code[jmp_find + 1] = (find - (jmp_find + 2)) & 0xFF
    code[jae_append + 1] = (overflow - (jae_append + 2)) & 0xFF
    code[jne_append + 1] = (append - (jne_append + 2)) & 0xFF
    return bytes(code)


def repair_pe_strcat(data: bytes, *, call_va: int, capacity: int) -> tuple[bytes | None, PEWriteReport]:
    """Replace one Windows-x64 strcat call with a bounded cave wrapper."""
    guard = build_pe_strcat_guard(capacity)
    patched, report = patch_pe_call_site(data, guard, call_va=call_va)
    if patched is None:
        return None, report
    report.strategy = "strcat-cave"
    report.status = "patched"
    report.limitations.append(
        f"strcat cave capacity={capacity}; total destination length is bounded; "
        f"overflow NUL-terminates at capacity-1 and returns 1."
    )
    return patched, report


def repair_pe(data: bytes, *, capacity: int | None = None) -> tuple[bytes | None, PEWriteReport]:
    """Auto-apply the supported PE copy-call repairs."""
    scan = scan_pe_copy_calls(data)
    findings = [f for f in scan.get("findings", []) if f.get("patchable")]
    if not findings:
        report = PEWriteReport(original_sha256=_sha(data), patched_sha256=_sha(data))
        report.limitations.append("No supported PE strcpy/strcat call found.")
        return None, report
    current = data
    last: PEWriteReport | None = None
    applied = 0
    for item in findings:
        cap = int(capacity or item.get("capacity") or 0)
        if cap <= 0:
            continue
        call_va = int(str(item["address"]), 16)
        low = str(item.get("callee", "")).lower()
        if "strcat" in low:
            patched, report = repair_pe_strcat(current, call_va=call_va, capacity=cap)
        else:
            patched, report = repair_pe_strcpy(current, call_va=call_va, capacity=cap)
        if patched is None:
            return None, report
        current = patched
        last = report
        applied += 1
    if last is None:
        report = PEWriteReport(original_sha256=_sha(data), patched_sha256=_sha(data))
        report.limitations.append("No supported PE copy-call with a positive capacity.")
        return None, report
    last.patched_sha256 = _sha(current)
    last.limitations.append(f"Applied {applied} PE copy-call cave(s).")
    return current, last


def scan_pe_memcpy_calls(data: bytes) -> dict[str, Any]:
    """Find Windows-x64 memcpy calls with immediate length arguments."""
    out: dict[str, Any] = {"format": "pe", "arch": "unknown", "findings": []}
    try:
        pe = lief.PE.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    if pe is None or "AMD64" not in str(pe.header.machine):
        return out
    text = pe.get_section(".text")
    if text is None:
        return out
    imagebase = int(pe.optional_header.imagebase)
    iat: dict[int, str] = {}
    for imp in pe.imports:
        for entry in imp.entries:
            try:
                iat[imagebase + int(entry.iat_address)] = entry.name
            except Exception:
                continue
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    base = imagebase + int(text.virtual_address)
    text_off = int(text.pointerto_raw_data)
    capacity = None
    length = None
    length_ins = None
    for ins in md.disasm(bytes(text.content), base):
        op = (ins.op_str or "").replace(" ", "")
        if ins.mnemonic == "sub" and op.startswith("rsp,"):
            try:
                capacity = int(op.split(",")[-1], 0)
            except ValueError:
                pass
        elif ins.mnemonic == "mov" and op.startswith(("r8d,#", "edx,#")):
            try:
                length = int(op.split("#")[-1], 0)
                length_ins = ins
            except ValueError:
                length = None
        elif ins.mnemonic == "call" and "rip" in op and capacity and length_ins:
            m = re.search(r"\[rip([+-]0x[0-9a-fA-F]+)\]", op)
            if not m:
                continue
            target = ins.address + ins.size + int(m.group(1), 16)
            name = iat.get(target)
            if name and "memcpy" in name.lower() and length and length > capacity:
                imm_at = 2 if (length_ins.bytes and length_ins.bytes[0] == 0x41) else 1
                out["findings"].append({
                    "kind": "memcpy_length", "address": hex(length_ins.address),
                    "callee": name, "before": length, "after": capacity,
                    "capacity": capacity, "patchable": True,
                    "offset": text_off + (length_ins.address - base) + imm_at,
                })
            length = None
            length_ins = None
    out["arch"] = "x86_64"
    return out


def repair_pe_memcpy(data: bytes) -> tuple[bytes | None, PEWriteReport]:
    """Patch the immediate length of Windows-x64 memcpy calls."""
    scan = scan_pe_memcpy_calls(data)
    findings = [f for f in scan.get("findings", []) if f.get("patchable")]
    report = PEWriteReport(original_sha256=_sha(data), patched_sha256=_sha(data))
    if not findings:
        report.limitations.append("No supported PE memcpy immediate-length call found.")
        return None, report
    patched = bytearray(data)
    for item in findings:
        off = int(item["offset"])
        if off < 0 or off + 4 > len(patched):
            report.limitations.append("memcpy immediate outside file")
            return None, report
        patched[off:off + 4] = struct.pack("<I", int(item["after"]))
    report.patched_sha256 = _sha(bytes(patched))
    report.status = "patched"
    report.strategy = "immediate"
    report.limitations.append("PE memcpy immediate length rewrite; no runtime executed.")
    return bytes(patched), report
