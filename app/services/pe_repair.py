"""PE32+ writeback primitives: sections and direct byte patches.

LIEF parses/writes structure; call-site analysis stays in raw bytes.  No PE is
executed on the host.
"""
from __future__ import annotations

import hashlib
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
    if "AMD64" not in report.arch and "ARM64" not in report.arch:
        report.limitations.append("only PE32+ x86-64/arm64 is supported")
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
