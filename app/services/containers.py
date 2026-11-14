"""Container-neutral metadata for ELF, PE and Mach-O.

The v4 repair pipeline must not assume one executable format.  This module
answers the questions every repair needs, without executing the target:

* which container and architecture is this?
* where are the executable sections, and how do VA and file offsets map?
* which call targets are imported functions (PLT / IAT / Mach-O stubs)?
* which symbols exist for direct calls?

Parsing is bounded and fail-closed: malformed input yields ``format="unknown"``
with a reason instead of an exception.  No bytes are written here.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from typing import Any

import lief
from elftools.elf.elffile import ELFFile

# LIEF prints parser diagnostics for corrupted inputs; the pipeline reports
# those as limitations instead, so keep the console quiet.
try:
    lief.logging.disable()
except Exception:  # noqa: BLE001 - logging API varies across LIEF builds
    pass

MAX_PARSE_BYTES = 20 * 1024 * 1024

_ELF_MACHINES = {
    3: "i386",
    8: "mips",
    20: "powerpc",
    40: "arm",
    62: "x86_64",
    183: "arm64",
    243: "riscv",
}

_MACHO_CPU = (
    ("ARM64", "arm64"),
    ("X86_64", "x86_64"),
    ("ARM", "arm"),
    ("X86", "i386"),
    ("I386", "i386"),
)

_COPY_NAMES = (
    "strcpy", "strcat", "stpcpy", "memcpy", "memmove",
    "__memcpy_chk", "__strcpy_chk", "__strcat_chk", "strcpy_s", "memcpy_s",
)


@dataclass(frozen=True)
class SectionInfo:
    name: str
    segment: str
    va: int
    size: int
    offset: int
    executable: bool


@dataclass
class ContainerInfo:
    format: str = "unknown"
    arch: str = "unknown"
    bits: int | None = None
    endian: str = "little"
    image_base: int = 0
    entry: int = 0
    sections: list[SectionInfo] = field(default_factory=list)
    imports: dict[int, str] = field(default_factory=dict)
    symbols: dict[int, str] = field(default_factory=dict)
    slices: int = 1
    limitations: list[str] = field(default_factory=list)
    raw: Any = None

    def section_at(self, va: int) -> SectionInfo | None:
        for section in self.sections:
            if section.va <= va < section.va + max(section.size, 1):
                return section
        return None

    def va_to_offset(self, va: int) -> int | None:
        section = self.section_at(va)
        if section is None:
            return None
        return section.offset + (va - section.va)

    def executable_section(self) -> SectionInfo | None:
        for section in self.sections:
            if section.executable and section.size:
                return section
        return None

    def copy_imports(self) -> dict[int, str]:
        return {
            va: name for va, name in self.imports.items()
            if any(token in name.lower() for token in _COPY_NAMES)
        }


def _as_int(value: object) -> int:
    """LIEF enums in this build do not always support ``int()``."""
    if value is None:
        return 0
    for attr in ("value", "Value"):
        inner = getattr(value, attr, None)
        if isinstance(inner, int):
            return inner
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _u64(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]


def _adrp_target(pc: int, word: int) -> int:
    immhi = (word >> 5) & 0x7FFFF
    immlo = (word >> 29) & 0x3
    raw = (immhi << 2) | immlo
    if raw & (1 << 20):
        raw -= 1 << 21
    return (pc & ~0xFFF) + (raw << 12)


def _decode_arm64_stub(code: bytes, va: int) -> int | None:
    if len(code) < 12:
        return None
    adrp, ldr, br = struct.unpack_from("<III", code)
    if (adrp & 0x9F00001F) != 0x90000010:  # adrp x16, page
        return None
    if (ldr & 0xFFC00000) != 0xF9400000:  # ldr x16, [x16, #imm]
        return None
    if br != 0xD61F0200:  # br x16
        return None
    offset = ((ldr >> 10) & 0xFFF) * 8
    return _adrp_target(va, adrp) + offset


def _decode_x86_stub(code: bytes, va: int) -> int | None:
    """x86-64 ``jmp *GOT(%rip)`` (FF 25 rel32)."""
    if len(code) >= 6 and code[0] == 0xFF and code[1] == 0x25:
        disp = struct.unpack_from("<i", code, 2)[0]
        return va + 6 + disp
    return None


def _decode_x86_abs_stub(code: bytes) -> int | None:
    """i386 ``jmp *GOT`` (FF 25 abs32): the GOT slot is an absolute address."""
    if len(code) >= 6 and code[0] == 0xFF and code[1] == 0x25:
        return struct.unpack_from("<I", code, 2)[0]
    return None


def _decode_elf_plt_stub(code: bytes, va: int, arch: str) -> int | None:
    if arch == "arm64" and len(code) >= 16:
        adrp, ldr = struct.unpack_from("<II", code)
        if (adrp & 0x9F00001F) == 0x90000010 and (ldr & 0xFFC00000) == 0xF9400000:
            offset = ((ldr >> 10) & 0xFFF) * 8
            if (adrp & 0x9F00001F) == 0x90000010:
                return _adrp_target(va, adrp) + offset
    if arch == "i386":
        # i386 PLT entries are 16 bytes: ``jmp *GOT`` (FF 25 abs32) at +0,
        # optionally after a 4-byte ``endbr32`` when the image is IBT-enabled.
        for start in range(0, max(len(code) - 5, 0)):
            target = _decode_x86_abs_stub(code[start:])
            if target is not None:
                return target
        return None
    if arch == "x86_64":
        # x86-64 PLT stubs have several layouts across toolchains:
        #   * lazy .plt entry: push/jmp resolver at +0, ``jmp *GOT(%rip)`` at +6;
        #   * IBT/CET .plt / .plt.sec: ``endbr64`` then ``jmp *GOT(%rip)``;
        #   * MPX-enabled: ``bnd jmp *GOT(%rip)`` (F2 prefix).
        # The stable anchor is the ``FF 25 rel32`` opcode pair anywhere in the
        # 16-byte stub; scanning by instruction position keeps every layout
        # covered and the caller still validates the decoded slot against the
        # relocation map, so a stray match cannot invent an import.
        for start in range(0, max(len(code) - 5, 0)):
            target = _decode_x86_stub(code[start:], va + start)
            if target is not None:
                return target
        return None
    return None


def _elf_info(data: bytes) -> ContainerInfo:
    info = ContainerInfo(format="elf")
    try:
        elf = ELFFile(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        info.limitations.append(f"ELF parse failed: {type(exc).__name__}")
        return info
    try:
        machine = elf.header["e_machine"]
        if isinstance(machine, str):
            info.arch = {
                "EM_X86_64": "x86_64", "EM_386": "i386", "EM_AARCH64": "arm64",
                "EM_ARM": "arm", "EM_MIPS": "mips", "EM_RISCV": "riscv",
                "EM_PPC": "powerpc",
            }.get(machine, machine.lower())
        else:
            info.arch = _ELF_MACHINES.get(int(machine), f"em_{machine}")
        info.bits = 64 if elf.elfclass == 64 else 32
        info.endian = "little" if elf.little_endian else "big"
        info.image_base = min(
            (int(seg["p_vaddr"]) for seg in elf.iter_segments()
             if seg["p_type"] == "PT_LOAD"), default=0,
        )
        info.entry = int(elf.header["e_entry"])
        for section in elf.iter_sections():
            flags = int(section["sh_flags"])
            info.sections.append(SectionInfo(
                name=section.name,
                segment="",
                va=int(section["sh_addr"]),
                size=int(section["sh_size"]),
                offset=int(section["sh_offset"]),
                executable=bool(flags & 0x4),
            ))
        _elf_symbols(elf, info)
        _elf_imports(elf, info)
    except Exception as exc:  # noqa: BLE001
        info.limitations.append(f"ELF metadata failed: {type(exc).__name__}")
    return info


def _elf_symbols(elf: ELFFile, info: ContainerInfo) -> None:
    for section in elf.iter_sections():
        if section.name not in {".symtab", ".dynsym"}:
            continue
        try:
            for sym in section.iter_symbols():
                name = sym.name
                value = int(sym["st_value"])
                kind = sym["st_info"]["type"]
                if name and value and str(kind) in {"STT_FUNC", "func"}:
                    info.symbols.setdefault(value, name)
        except Exception:  # noqa: BLE001
            continue


def _elf_imports(elf: ELFFile, info: ContainerInfo) -> None:
    dynsym = elf.get_section_by_name(".dynsym")
    if dynsym is None:
        return
    reloc_names: dict[int, str] = {}
    for section in elf.iter_sections():
        if section.name not in {".rela.plt", ".rel.plt", ".rela.dyn", ".rel.dyn"}:
            continue
        try:
            for rel in section.iter_relocations():
                sym_idx = int(rel["r_info_sym"])
                if not sym_idx:
                    continue
                name = dynsym.get_symbol(sym_idx).name
                if name:
                    reloc_names[int(rel["r_offset"])] = name
        except Exception:  # noqa: BLE001
            continue
    if not reloc_names:
        return
    plt_names = [".plt"]
    if info.arch == "i386":
        # IBT-enabled i386 images keep the FF 25 abs32 jump in .plt.sec.
        plt_names.append(".plt.sec")
    elif info.arch == "x86_64":
        # IBT/CET x86-64 images keep the GOT jumps in .plt.sec; without it the
        # analyzer cannot resolve strcpy/malloc/... for default-toolchain
        # dynamic ELF and sees zero sinks (a real capability gap).
        plt_names.append(".plt.sec")
    for plt_name in plt_names:
        plt = elf.get_section_by_name(plt_name)
        if plt is None:
            continue
        raw = plt.data()
        if not raw:
            continue
        base = int(plt["sh_addr"])
        step = 16
        for index in range(0, len(raw) // step):
            va = base + index * step
            got = _decode_elf_plt_stub(raw[index * step:(index + 1) * step], va, info.arch)
            if got is not None and got in reloc_names:
                info.imports[va] = reloc_names[got]
    # Direct GOT call sites are resolved by the call instruction itself.
    for got, name in reloc_names.items():
        info.imports.setdefault(got, name)


def _pe_info(data: bytes) -> ContainerInfo:
    info = ContainerInfo(format="pe")
    try:
        pe = lief.PE.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        info.limitations.append(f"PE parse failed: {type(exc).__name__}")
        return info
    if pe is None:
        info.limitations.append("not a PE image")
        return info
    info.raw = pe
    try:
        machine = str(pe.header.machine)
        info.arch = (
            "x86_64" if "AMD64" in machine else
            "arm64" if "ARM64" in machine else
            "i386" if "I386" in machine or "386" in machine else "unknown"
        )
        magic = int(getattr(pe.optional_header, "magic", 0) or 0)
        info.bits = 64 if magic == 0x20B else 32 if magic == 0x10B else None
        info.image_base = int(pe.optional_header.imagebase)
        info.entry = info.image_base + int(pe.optional_header.addressof_entrypoint)
        for section in pe.sections:
            characteristics = _as_int(getattr(section, "characteristics", 0))
            info.sections.append(SectionInfo(
                name=section.name,
                segment="",
                va=info.image_base + int(section.virtual_address),
                size=len(section.content),
                offset=int(section.pointerto_raw_data),
                executable=bool(characteristics & 0x20000000),
            ))
        iat: dict[int, str] = {}
        for imp in pe.imports:
            for entry in imp.entries:
                try:
                    iat[info.image_base + int(entry.iat_address)] = entry.name
                except Exception:  # noqa: BLE001
                    continue
        info.imports.update(iat)
        # Direct calls may target a `jmp [rip+disp]` thunk (x86-64), an
        # `jmp [abs32]` thunk (i386) or an `adrp/ldr/br x16` thunk (arm64) in
        # .text.
        text = next((s for s in info.sections if s.name == ".text"), None)
        if text is not None and text.size:
            raw = data[text.offset:text.offset + text.size]
            if info.arch == "x86_64":
                for index in range(len(raw) - 6):
                    if raw[index] == 0xFF and raw[index + 1] == 0x25:
                        va = text.va + index
                        disp = struct.unpack_from("<i", raw, index + 2)[0]
                        target = va + 6 + disp
                        if target in iat:
                            info.imports[va] = iat[target]
            elif info.arch == "i386":
                # 32-bit PE import thunks are ``jmp dword ptr [__imp_x]``:
                # FF 25 <absolute IAT VA>.
                for index in range(len(raw) - 6):
                    if raw[index] == 0xFF and raw[index + 1] == 0x25:
                        va = text.va + index
                        target = struct.unpack_from("<I", raw, index + 2)[0]
                        if target in iat:
                            info.imports[va] = iat[target]
            elif info.arch == "arm64":
                for index in range(0, len(raw) - 12, 4):
                    va = text.va + index
                    target = _decode_arm64_stub(raw[index:index + 12], va)
                    if target is not None and target in iat:
                        info.imports[va] = iat[target]
    except Exception as exc:  # noqa: BLE001
        info.limitations.append(f"PE metadata failed: {type(exc).__name__}")
    return info


def _macho_info(data: bytes, fat: bool) -> ContainerInfo:
    info = ContainerInfo(format="macho-fat" if fat else "macho")
    try:
        parsed = lief.MachO.parse(list(data))
    except Exception as exc:  # noqa: BLE001
        info.limitations.append(f"Mach-O parse failed: {type(exc).__name__}")
        return info
    if parsed is None:
        info.limitations.append("not a Mach-O image")
        return info
    info.raw = parsed
    try:
        info.slices = int(getattr(parsed, "size", 1) or 1)
    except Exception:  # noqa: BLE001
        info.slices = 1
    try:
        binary = parsed.at(0)
    except Exception:  # noqa: BLE001
        binary = parsed
    if binary is None:
        info.limitations.append("Mach-O has no slice")
        return info
    try:
        cpu = str(binary.header.cpu_type)
        info.arch = next((arch for token, arch in _MACHO_CPU if token in cpu), "unknown")
        info.bits = 64 if "64" in str(binary.header.cpu_type) else 32
        info.image_base = min(
            (int(seg.virtual_address) for seg in binary.segments
             if seg.name != "__PAGEZERO"), default=0,
        )
        info.entry = int(binary.entrypoint)
        for section in binary.sections:
            info.sections.append(SectionInfo(
                name=section.name,
                segment=section.segment_name,
                va=int(section.virtual_address),
                size=int(section.size),
                offset=int(section.offset),
                executable=section.segment_name == "__TEXT",
            ))
        bindings: dict[int, str] = {}
        try:
            for binding in binary.bindings:
                name = str(getattr(binding, "symbol", None).name if hasattr(binding, "symbol") else "")
                if name:
                    bindings[int(binding.address)] = name
        except Exception:  # noqa: BLE001
            pass
        for va, name in bindings.items():
            info.imports.setdefault(va, name)
        stubs = next((s for s in info.sections if s.name == "__stubs"), None)
        if stubs is not None and stubs.size:
            raw = data[stubs.offset:stubs.offset + stubs.size]
            step = 12 if info.arch == "arm64" else 6
            for index in range(len(raw) // step):
                va = stubs.va + index * step
                got = (
                    _decode_arm64_stub(raw[index * step:(index + 1) * step], va)
                    if step == 12 else
                    _decode_x86_stub(raw[index * step:(index + 1) * step], va)
                )
                if got is not None and got in bindings:
                    info.imports[va] = bindings[got]
        for symbol in binary.symbols:
            try:
                value = int(symbol.value)
                if value and symbol.name:
                    info.symbols.setdefault(value, symbol.name)
            except Exception:  # noqa: BLE001
                continue
    except Exception as exc:  # noqa: BLE001
        info.limitations.append(f"Mach-O metadata failed: {type(exc).__name__}")
    return info


def detect_container(data: bytes) -> ContainerInfo:
    """Detect and describe one binary without executing it."""
    if not data:
        return ContainerInfo(limitations=["empty input"])
    if len(data) > MAX_PARSE_BYTES:
        return ContainerInfo(limitations=[f"input exceeds {MAX_PARSE_BYTES} bytes"])
    if data[:4] == b"\x7fELF":
        return _elf_info(data)
    if data[:2] == b"MZ":
        return _pe_info(data)
    if data[:4] == b"\xca\xfe\xba\xbe" and len(data) >= 8:
        count = struct.unpack_from(">I", data, 4)[0]
        if 0 < count <= 64:
            return _macho_info(data, fat=True)
        return _macho_info(data, fat=False)
    if data[:4] in {
        b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
    }:
        return _macho_info(data, fat=False)
    return ContainerInfo(limitations=["unrecognized container magic"])


def resolve_target(container: ContainerInfo, target: int) -> str | None:
    """Return an imported/symbol name for a call target, else ``None``."""
    if target in container.imports:
        return container.imports[target]
    if target in container.symbols:
        return container.symbols[target]
    return None


def is_supported_repair(container: ContainerInfo) -> bool:
    return (container.format, container.arch) in {
        ("elf", "x86_64"), ("elf", "arm64"),
        ("pe", "x86_64"), ("pe", "arm64"),
        ("macho", "arm64"), ("macho", "x86_64"),
    }
