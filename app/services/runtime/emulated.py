"""Instruction-level runtime evidence through Unicorn.

Used when the host cannot execute the target natively (PE on macOS/Linux, ELF
AArch64 on macOS).  The harness maps the image, builds a controlled stack and
input buffer, stubs the non-copy imports (``puts``), and records whether the
copy stays inside ``capacity``.

Arches: ``x86_64`` (SysV/Win64), ``arm64`` (AAPCS64) and ``i386`` (cdecl /
32-bit x86, ``UC_ARCH_X86`` + ``UC_MODE_32``).  For i386 the harness reserves a
4-byte synthetic return address, passes the source pointer as the cdecl stack
argument at ``[esp+4]`` and intercepts imports at their thunk/PLT address (or,
for ``call [IAT]`` sites, at the call instruction itself).

Copy modelling is either C-string (``strcpy``/``strcat``/``stpcpy``) or
length-aware (``memcpy``/``memmove`` and the ``__*_chk``/``*_s`` variants): a
length-aware run reads the ABI length argument and copies exactly that many
bytes, so an immediate-length candidate is judged by whether its patched length
fits ``capacity``.  Length-aware cases report ``output_len=None`` because the
result is not a NUL-terminated string.

This is emulation, not a Windows/Linux kernel run; the report says so.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Callable

import lief
from elftools.elf.elffile import ELFFile
from unicorn import (
    UC_ARCH_ARM64, UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, UC_MODE_64,
    UC_MODE_ARM, UC_PROT_ALL, Uc,
)
from unicorn.arm64_const import (
    UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X2, UC_ARM64_REG_X30,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EIP, UC_X86_REG_ESP,
    UC_X86_REG_R8, UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDI,
    UC_X86_REG_RDX, UC_X86_REG_RIP, UC_X86_REG_RSI, UC_X86_REG_RSP,
)

from app.services.containers import ContainerInfo
from app.services.runtime.evidence import RuntimeCase, RuntimeEvidence, judge

PAGE = 0x1000
# 64-bit (x86_64 / arm64) scratch windows.
STACK_BASE = 0x7000000000
STACK_SIZE = 0x20000
INPUT_BASE = 0x6000000000
SENTINEL_BASE = 0x5000000000
# 32-bit x86 cannot address the 64-bit windows above, so i386 uses its own.
I386_STACK_BASE = 0x70000000
I386_INPUT_BASE = 0x60000000
I386_SENTINEL_BASE = 0x50000000
CANARY = b"\xAA" * 32
FILL = b"\xCC"
MAX_INSNS = 2_000_000
# cdecl callees keep the destination pointer on the stack; for frames that
# reserve the slot just below the return address (the usual ``push ebp``
# prologue) the first byte past ``capacity`` is the saved-EBP slot.  The prologue
# writes EBP there, so the register is seeded with a marker and the slot is
# checked afterwards: a NUL past the buffer shows up as a changed marker.
I386_BOUNDARY_MARK = 0xA5A5A5A5
_STOP_NAMES = {"puts", "fputs", "printf", "putchar"}
# Sink kinds whose runtime model is length-aware (the repair patches an
# immediate/AArch64 length operand instead of replacing the call).
_LENGTH_KINDS = {
    "immediate_length", "memcpy_length", "syscall_length", "checked_copy",
}
_LENGTH_FAMILIES = {"memcpy", "memmove"}
_STR_FAMILIES = {"strcpy", "strcat", "stpcpy"}
# Name classifiers: namespaced static-libc symbols and Zig compiler-rt aliases
# (``compiler_rt.memcpy.memcpyFast``) must still resolve to the libc family.
_FAMILY_TOKENS = (
    ("__memmove_chk", "memmove"),
    ("__memcpy_chk", "memcpy"),
    ("memmove", "memmove"),
    ("memcpy", "memcpy"),
    ("strcpy", "strcpy"),
    ("strcat", "strcat"),
    ("stpcpy", "stpcpy"),
)
# Modeled memcpy writes are exact for realistic lengths; very large lengths are
# only written up to this many bytes (the overflow flag is still exact).
MAX_MODEL_COPY = 1 << 16


@dataclass
class _Mapping:
    va: int
    size: int
    offset: int


def _align_down(value: int) -> int:
    return value & ~(PAGE - 1)


def _align_up(value: int) -> int:
    return (value + PAGE - 1) & ~(PAGE - 1)


def _elf_mappings(data: bytes) -> list[_Mapping]:
    mappings: list[_Mapping] = []
    elf = ELFFile(__import__("io").BytesIO(data))
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD":
            continue
        vaddr = int(segment["p_vaddr"])
        filesz = int(segment["p_filesz"])
        memsz = int(segment["p_memsz"])
        offset = int(segment["p_offset"])
        start = _align_down(vaddr)
        size = _align_up(vaddr + memsz) - start
        if size > 0:
            mappings.append(_Mapping(start, size, offset - (vaddr - start)))
    return mappings


def _pe_mappings(data: bytes) -> list[_Mapping]:
    pe = lief.PE.parse(list(data))
    if pe is None:
        return []
    base = int(pe.optional_header.imagebase)
    mappings = []
    for section in pe.sections:
        va = base + int(section.virtual_address)
        size = max(len(section.content), int(section.sizeof_raw_data))
        start = _align_down(va)
        mappings.append(_Mapping(start, _align_up(va + size) - start,
                                 int(section.pointerto_raw_data) - (va - start)))
    return mappings


def _mappings(data: bytes, container: ContainerInfo) -> list[_Mapping]:
    if container.format == "elf":
        return _elf_mappings(data)
    if container.format == "pe":
        return _pe_mappings(data)
    return []


def _merge(mappings: list[_Mapping]) -> list[_Mapping]:
    merged: list[_Mapping] = []
    for item in sorted(mappings, key=lambda m: m.va):
        if merged:
            last = merged[-1]
            contiguous_files = item.offset == last.offset + (item.va - last.va)
            if item.va <= last.va + last.size and contiguous_files:
                end = max(last.va + last.size, item.va + item.size)
                merged[-1] = _Mapping(last.va, end - last.va, last.offset)
                continue
        merged.append(item)
    return merged


def _short_name(name: str) -> str:
    """Normalize an import/symbol name to its libc-facing short form.

    Static libc symbols can be namespaced (``c.string.strcpy``) and Windows
    import symbols carry a leading underscore and ``@n`` decoration.
    """
    short = name.strip().lower().split("@")[0]
    short = short.rsplit(".", 1)[-1]
    return short.lstrip("_")


def _copy_family(name: str | None) -> str | None:
    """Classify a resolved copy symbol name as strcpy/memcpy family, if any."""
    if not name:
        return None
    low = name.strip().lower().split("@")[0]
    short = low.rsplit(".", 1)[-1].lstrip("_")
    for token, family in _FAMILY_TOKENS:
        if token in short or token in low:
            return family
    return None


def _stop_family(name: str | None) -> str | None:
    """Classify a resolved print symbol name as a terminating call, if any."""
    if not name:
        return None
    low = name.strip().lower().split("@")[0]
    short = low.rsplit(".", 1)[-1].lstrip("_")
    for token in _STOP_NAMES:
        if token in short or token in low:
            return token
    return None


def _copy_mode(family: str) -> str:
    return "length" if family in _LENGTH_FAMILIES else "cstr"


def _length_hint(copy_kind: str, callee: str) -> bool:
    """Whether the caller classified this sink as length-aware."""
    return copy_kind in _LENGTH_KINDS or _copy_family(callee) in _LENGTH_FAMILIES


def _i386_import_edges(
    data: bytes, container: ContainerInfo,
) -> tuple[dict[int, str], dict[int, tuple[str, int]]]:
    """Discover i386 import thunks and direct ``call [IAT]`` sites.

    ``ff 25 <abs32>`` is ``jmp dword ptr [IAT]`` (the MinGW/ELF-PLT thunk a
    ``call`` reaches); ``ff 15 <abs32>`` is ``call dword ptr [IAT]`` (an inline
    call site).  Both reference the IAT/GOT address recorded in
    ``container.imports``.
    """
    thunks: dict[int, str] = {}
    calls: dict[int, tuple[str, int]] = {}
    for section in container.sections:
        if not section.executable or section.size <= 0 or section.offset < 0:
            continue
        raw = data[section.offset:section.offset + section.size]
        for index in range(max(0, len(raw) - 5)):
            if raw[index] != 0xFF or raw[index + 1] not in (0x25, 0x15):
                continue
            target = struct.unpack_from("<I", raw, index + 2)[0]
            name = container.imports.get(target)
            if not name:
                continue
            va = section.va + index
            if raw[index + 1] == 0x25:
                thunks[va] = name
            else:
                calls[va] = (name, 6)
    return thunks, calls


def _imports_for(data: bytes, container: ContainerInfo) -> dict[int, str]:
    imports = dict(container.imports)
    if container.arch == "i386":
        thunks, _calls = _i386_import_edges(data, container)
        for va, name in thunks.items():
            imports.setdefault(va, name)
    return imports


def _i386_hook_targets(
    data: bytes, container: ContainerInfo,
) -> tuple[
    list[tuple[int, str]], list[int], dict[int, tuple[int, str]], dict[int, int],
]:
    """Resolve every i386 copy/stop entry the target function could reach.

    A static i386 libc namespaces its symbols (``c.string.strcpy``,
    ``compiler_rt.memcpy.memcpyFast``, ...); the fixture's call target is one of
    them.  Hooking all candidate entries keeps the harness correct without
    guessing which alias the emitted call instruction refers to, and each
    target carries its model mode (C-string vs length-aware).
    """
    imports = _imports_for(data, container)
    copy_targets: dict[int, str] = {}
    puts_targets: set[int] = set()
    for table in (imports, container.symbols):
        for va, name in table.items():
            section = container.section_at(va)
            if section is None or not section.executable:
                continue
            family = _copy_family(name)
            if family is not None:
                copy_targets[va] = _copy_mode(family)
            elif _stop_family(name) is not None:
                puts_targets.add(va)
    _thunks, direct_calls = _i386_import_edges(data, container)
    copy_calls: dict[int, tuple[int, str]] = {}
    puts_calls: dict[int, int] = {}
    for va, (name, size) in direct_calls.items():
        family = _copy_family(name)
        if family is not None:
            copy_calls[va] = (size, _copy_mode(family))
        elif _stop_family(name) is not None:
            puts_calls[va] = size
    ordered = sorted(copy_targets.items())
    return ordered, sorted(puts_targets), copy_calls, puts_calls


def _resolve_callable(
    container: ContainerInfo,
    predicate: Callable[[str], bool],
    imports: dict[int, str] | None = None,
) -> int | None:
    """Resolve a callable import/symbol entry whose name matches ``predicate``.

    An executable import thunk/PLT entry is preferred over a raw symbol address
    because the emulator intercepts the address the call instruction reaches.
    """
    table = container.imports if imports is None else imports
    candidates: list[int] = []
    for va, name in table.items():
        section = container.section_at(va)
        if section is not None and section.executable and predicate(name):
            candidates.append(va)
    if candidates:
        return min(candidates)
    for va, name in container.symbols.items():
        if predicate(name):
            return va
    return None


def _read_cstr(uc: Uc, address: int, limit: int = 8192) -> bytes:
    out = bytearray()
    for index in range(limit):
        try:
            byte = uc.mem_read(address + index, 1)
        except Exception:  # noqa: BLE001
            break
        value = bytes(byte)[0]
        out.append(value)
        if value == 0:
            break
    return bytes(out)


def _read_u32(uc: Uc, address: int) -> int:
    return struct.unpack("<I", bytes(uc.mem_read(address, 4)))[0]


def _read_mem(uc: Uc, address: int, length: int) -> bytes:
    """Read ``length`` bytes, returning the readable prefix on a partial map."""
    if length <= 0:
        return b""
    try:
        return bytes(uc.mem_read(address, length))
    except Exception:  # noqa: BLE001
        pass
    out = bytearray()
    for index in range(length):
        try:
            out += bytes(uc.mem_read(address + index, 1))
        except Exception:  # noqa: BLE001
            break
    return bytes(out)


def _write_u32(uc: Uc, address: int, value: int) -> None:
    uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))


def emulate(
    data: bytes,
    container: ContainerInfo,
    *,
    function_va: int,
    dest_rel: int,
    capacity: int,
    abi: str,
    lengths: list[int] | None = None,
    copy_kind: str = "",
    callee: str = "",
) -> RuntimeEvidence:
    evidence = RuntimeEvidence(tier="emulated_run", engine=f"unicorn-{container.arch}")
    if capacity <= 0:
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append("capacity is not positive")
        return evidence
    mappings = _merge(_mappings(data, container))
    if not mappings:
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append(f"no mapping strategy for {container.format}")
        return evidence

    length_hint = _length_hint(copy_kind, callee)
    expect_copy = ""
    copy_family = _copy_family(callee) if callee else ""
    if length_hint:
        expect_copy = "length"
    elif copy_family in {"strcpy", "stpcpy"}:
        expect_copy = "strcpy"
    imports = _imports_for(data, container)
    copy_targets: list[tuple[int, str]] = []
    puts_targets: list[int] = []
    copy_calls: dict[int, tuple[int, str]] = {}
    puts_calls: dict[int, int] = {}
    if container.arch == "i386":
        copy_targets, puts_targets, copy_calls, puts_calls = _i386_hook_targets(
            data, container,
        )
    else:
        puts_target = _resolve_callable(
            container, lambda name: _stop_family(name) is not None, imports,
        )
        puts_targets = [puts_target] if puts_target is not None else []
        if length_hint:
            # Length-aware immediate patches keep the original callee; hook the
            # memcpy-family entry in addition to any strcpy-family alias.
            mem_target = _resolve_callable(
                container,
                lambda name: _copy_family(name) in _LENGTH_FAMILIES,
                imports,
            )
            if mem_target is not None:
                copy_targets.append((mem_target, "length"))
            str_target = _resolve_callable(
                container,
                lambda name: _copy_family(name) in _STR_FAMILIES,
                imports,
            )
            if str_target is not None and str_target != mem_target:
                copy_targets.append((str_target, "cstr"))
        else:
            str_target = _resolve_callable(
                container,
                lambda name: _copy_family(name) in _STR_FAMILIES,
                imports,
            )
            if str_target is not None:
                copy_targets.append((str_target, "cstr"))
    if not copy_targets and not puts_targets and not copy_calls and not puts_calls:
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append("could not resolve the copy/puts imports")
        return evidence
    length_targets = [mode for _va, mode in copy_targets]
    length_targets += [mode for _size, mode in copy_calls.values()]
    length_modelled = "length" in length_targets
    if length_hint and not length_modelled:
        evidence.limitations.append(
            "Length-aware sink was requested but no memcpy/memmove entry could "
            "be resolved; the real callee executes unmodeled."
        )

    probe = [0, 1, capacity - 1, capacity, capacity + 1, capacity * 4]
    if length_hint or length_modelled:
        evidence.limitations.append(
            "Length-aware copy model: memcpy/memmove copies the ABI length "
            "argument exactly; output_len is not reported because the result is "
            "not a NUL-terminated string (the gate uses canary/return-slot "
            "checks)."
        )
        if dest_rel == 0:
            evidence.limitations.append(
                "Length-aware sink has no recorded destination offset; the "
                "modeled copy uses the callee's runtime destination and the "
                "canary is placed conservatively."
            )

    selected = sorted({value for value in (lengths or probe) if value >= 0})
    for length in selected:
        evidence.cases.append(_run_case(
            data, container, mappings,
            function_va=function_va, dest_rel=dest_rel, capacity=capacity,
            abi=abi, argument=b"A" * length,
            copy_targets=copy_targets, puts_targets=puts_targets,
            copy_calls=copy_calls, puts_calls=puts_calls,
            length_hint=length_hint, expect_copy=expect_copy,
        ))
    evidence.verdict = judge(evidence.cases, capacity)
    evidence.limitations.extend([
        "Emulated execution with modeled imports; not a native Windows/Linux run.",
        "Only the repaired function is executed; unrelated code paths are not covered.",
    ])
    return evidence


def _run_case(
    data: bytes,
    container: ContainerInfo,
    mappings: list[_Mapping],
    *,
    function_va: int,
    dest_rel: int,
    capacity: int,
    abi: str,
    argument: bytes,
    copy_targets: list[tuple[int, str]],
    puts_targets: list[int],
    copy_calls: dict[int, tuple[int, str]],
    puts_calls: dict[int, int],
    length_hint: bool = False,
    expect_copy: str = "",
) -> RuntimeCase:
    is_arm = container.arch == "arm64"
    is_i386 = container.arch == "i386"
    if is_arm:
        uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    elif is_i386:
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
    else:
        uc = Uc(UC_ARCH_X86, UC_MODE_64)
    if is_i386:
        stack_base, input_base, sentinel_base = (
            I386_STACK_BASE, I386_INPUT_BASE, I386_SENTINEL_BASE,
        )
        ret_size = 4
    else:
        stack_base, input_base, sentinel_base = (
            STACK_BASE, INPUT_BASE, SENTINEL_BASE,
        )
        ret_size = 0 if is_arm else 8
    mapped: list[tuple[int, int]] = []

    def map_range(va: int, size: int, fill: bytes = b"\x00") -> None:
        start = _align_down(va)
        total = _align_up(va + size) - start
        for other_va, other_size in mapped:
            if start < other_va + other_size and other_va < start + total:
                return
        try:
            uc.mem_map(start, total, UC_PROT_ALL)
        except Exception:  # noqa: BLE001
            return
        mapped.append((start, total))
        if fill:
            uc.mem_write(start, fill * total)

    for item in mappings:
        start = _align_down(item.va)
        total = _align_up(item.va + item.size) - start
        try:
            uc.mem_map(start, total, UC_PROT_ALL)
        except Exception:  # noqa: BLE001
            continue
        mapped.append((start, total))
        offset = item.offset
        if 0 <= offset < len(data):
            chunk = data[offset:offset + min(total, len(data) - offset)]
            if chunk:
                uc.mem_write(start, chunk)

    map_range(stack_base, STACK_SIZE, b"\x00")
    map_range(input_base, len(argument) + 64, b"\x00")
    map_range(sentinel_base, PAGE, b"\x00")
    uc.mem_write(sentinel_base, b"\xF4" if not is_arm else b"\x00\x00\x20\xD4")

    entry_sp = stack_base + STACK_SIZE - 0x200
    if ret_size:
        entry_sp -= ret_size  # the synthetic return address lives at [esp]
    dest = entry_sp + dest_rel
    map_range(dest, capacity + 96, FILL)
    boundary = dest + capacity
    i386_marker = False
    if is_i386:
        # [esp] is the 4-byte synthetic return address and [esp+4] the cdecl
        # argument; the canary starts in the caller-owned slot above both.
        canary_addr = entry_sp + 8
        i386_marker = boundary + 4 <= entry_sp
        if i386_marker:
            _write_u32(uc, boundary, I386_BOUNDARY_MARK)
        uc.mem_write(canary_addr, CANARY)
        _write_u32(uc, entry_sp, sentinel_base)
        _write_u32(uc, entry_sp + 4, input_base)  # cdecl argument at [esp+4]
        uc.reg_write(UC_X86_REG_ESP, entry_sp)
        uc.reg_write(UC_X86_REG_EBP, I386_BOUNDARY_MARK)
        uc.reg_write(UC_X86_REG_EAX, 0)
    elif is_arm:
        canary_addr = dest + capacity
        uc.mem_write(canary_addr, CANARY)
        uc.reg_write(UC_ARM64_REG_SP, entry_sp)
        uc.reg_write(UC_ARM64_REG_X0, input_base)
        uc.reg_write(UC_ARM64_REG_X30, sentinel_base)
    else:
        # On x86-64 the synthetic return address occupies [entry_sp, entry_sp+8).
        # Keep the canary above both the buffer and the return slot; for a frame
        # whose buffer ends just below the saved RBP the naive
        # dest+capacity+8 address would land on the return slot itself.
        canary_addr = max(dest + capacity + 8, entry_sp + 8)
        uc.mem_write(canary_addr, CANARY)
        uc.mem_write(entry_sp, struct.pack("<Q", sentinel_base))
        uc.reg_write(UC_X86_REG_RSP, entry_sp)
        if abi == "win64_x86_64":
            uc.reg_write(UC_X86_REG_RCX, input_base)
        else:
            uc.reg_write(UC_X86_REG_RDI, input_base)
    uc.mem_write(input_base, argument + b"\x00")

    copy_overflow = [False]
    modeled_len: list[int | None] = [None]
    length_used = [False]

    def complete(uc_obj: Uc, ret: int, sp: int | None) -> None:
        """Return from a modeled callee, exactly like its own epilogue would."""
        if is_arm:
            uc_obj.reg_write(UC_ARM64_REG_PC, ret)
            uc_obj.reg_write(UC_ARM64_REG_X0, 0)
        elif is_i386:
            uc_obj.reg_write(UC_X86_REG_ESP, (sp or 0) + 4)
            uc_obj.reg_write(UC_X86_REG_EIP, ret)
            uc_obj.reg_write(UC_X86_REG_EAX, 0)
        else:
            uc_obj.reg_write(UC_X86_REG_RSP, (sp or 0) + 8)
            uc_obj.reg_write(UC_X86_REG_RIP, ret)
            uc_obj.reg_write(UC_X86_REG_RAX, 0)

    def finish(uc_obj: Uc) -> None:
        """Return from a modeled print/spill callee (unchanged legacy path)."""
        if is_arm:
            uc_obj.reg_write(UC_ARM64_REG_PC, uc_obj.reg_read(UC_ARM64_REG_X30))
            uc_obj.reg_write(UC_ARM64_REG_X0, 0)
        else:
            sp_now = uc_obj.reg_read(UC_X86_REG_RSP if not is_i386 else UC_X86_REG_ESP)
            ret = bytes(uc_obj.mem_read(sp_now, ret_size))
            uc_obj.reg_write(
                UC_X86_REG_RSP if not is_i386 else UC_X86_REG_ESP, sp_now + ret_size,
            )
            uc_obj.reg_write(
                UC_X86_REG_RIP if not is_i386 else UC_X86_REG_EIP,
                struct.unpack("<Q" if ret_size == 8 else "<I", ret)[0],
            )
            uc_obj.reg_write(UC_X86_REG_RAX if not is_i386 else UC_X86_REG_EAX, 0)

    def model_cstr(uc_obj: Uc, dst: int, src: int) -> None:
        payload = _read_cstr(uc_obj, src, limit=8192)
        uc_obj.mem_write(dst, payload)

    def model_length(uc_obj: Uc, dst: int, src: int, length: int, bits: int) -> None:
        """Copy exactly ``length`` bytes, flagging any write past ``capacity``."""
        length &= (1 << bits) - 1
        modeled_len[0] = length
        if length > capacity:
            copy_overflow[0] = True
        count = length if length <= MAX_MODEL_COPY else capacity + 96
        payload = _read_mem(uc_obj, src, count)
        if payload:
            uc_obj.mem_write(dst, payload)

    def hook_puts(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
        finish(uc_obj)

    def make_copy_hook(mode: str):
        def hook_copy(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
            if is_i386:
                # Import thunk/PLT entry: the callee's cdecl arguments live
                # above the return address pushed by the call.
                sp = uc_obj.reg_read(UC_X86_REG_ESP)
                ret = _read_u32(uc_obj, sp)
                dst = _read_u32(uc_obj, sp + 4)
                src = _read_u32(uc_obj, sp + 8)
                if mode == "length":
                    length_used[0] = True
                    model_length(uc_obj, dst, src, _read_u32(uc_obj, sp + 12), 32)
                else:
                    model_cstr(uc_obj, dst, src)
                complete(uc_obj, ret, sp)
                return
            sp = None
            if is_arm:
                ret = uc_obj.reg_read(UC_ARM64_REG_X30)
                dst = uc_obj.reg_read(UC_ARM64_REG_X0)
                src = uc_obj.reg_read(UC_ARM64_REG_X1)
            elif abi == "win64_x86_64":
                sp = uc_obj.reg_read(UC_X86_REG_RSP)
                ret = struct.unpack("<Q", bytes(uc_obj.mem_read(sp, 8)))[0]
                dst = uc_obj.reg_read(UC_X86_REG_RCX)
                src = uc_obj.reg_read(UC_X86_REG_RDX)
            else:
                sp = uc_obj.reg_read(UC_X86_REG_RSP)
                ret = struct.unpack("<Q", bytes(uc_obj.mem_read(sp, 8)))[0]
                dst = uc_obj.reg_read(UC_X86_REG_RDI)
                src = uc_obj.reg_read(UC_X86_REG_RSI)
            if mode == "length":
                length_used[0] = True
                if is_arm:
                    length = uc_obj.reg_read(UC_ARM64_REG_X2)
                elif abi == "win64_x86_64":
                    length = uc_obj.reg_read(UC_X86_REG_R8)
                else:
                    length = uc_obj.reg_read(UC_X86_REG_RDX)
                model_length(uc_obj, dst, src, length, 64)
            else:
                model_cstr(uc_obj, dst, src)
            complete(uc_obj, ret, sp)
        return hook_copy

    def make_copy_site_hook(mode: str):
        def hook_copy_site(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
            # ``call dword ptr [IAT]`` site: the call has not pushed a return
            # address yet, so [esp]/[esp+4]/[esp+8] are the cdecl arguments and
            # skipping the instruction leaves the caller's stack unchanged.
            sp = uc_obj.reg_read(UC_X86_REG_ESP)
            dst = _read_u32(uc_obj, sp)
            src = _read_u32(uc_obj, sp + 4)
            if mode == "length":
                length_used[0] = True
                model_length(uc_obj, dst, src, _read_u32(uc_obj, sp + 8), 32)
            else:
                model_cstr(uc_obj, dst, src)
            uc_obj.reg_write(UC_X86_REG_EIP, address + size)
        return hook_copy_site

    def hook_puts_site(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
        uc_obj.reg_write(UC_X86_REG_EIP, address + size)

    for target in puts_targets:
        uc.hook_add(UC_HOOK_CODE, hook_puts, begin=target, end=target)
    for site in puts_calls:
        uc.hook_add(UC_HOOK_CODE, hook_puts_site, begin=site, end=site)
    for target, mode in copy_targets:
        uc.hook_add(UC_HOOK_CODE, make_copy_hook(mode), begin=target, end=target)
    for site, (_size, mode) in copy_calls.items():
        uc.hook_add(
            UC_HOOK_CODE, make_copy_site_hook(mode), begin=site, end=site,
        )

    trace: list[int] = []

    def hook_trace(uc_obj: Uc, address: int, size: int, _user: Any) -> None:
        trace.append(address)
        if len(trace) > 64:
            trace.pop(0)

    uc.hook_add(UC_HOOK_CODE, hook_trace)
    error = None
    try:
        uc.emu_start(function_va, sentinel_base, count=MAX_INSNS)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        error += " at " + " -> ".join(hex(pc) for pc in trace[-6:])

    try:
        canary = bytes(uc.mem_read(canary_addr, len(CANARY)))
        sentinel_ok = True
        marker_ok = True
        if is_arm:
            pass
        elif is_i386:
            sentinel_ok = (
                bytes(uc.mem_read(entry_sp, 4)) == struct.pack("<I", sentinel_base)
            )
            if i386_marker:
                marker_ok = (
                    bytes(uc.mem_read(boundary, 4))
                    == struct.pack("<I", I386_BOUNDARY_MARK)
                )
        else:
            sentinel_ok = (
                bytes(uc.mem_read(entry_sp, 8))
                == struct.pack("<Q", sentinel_base)
            )
        if length_hint or length_used[0]:
            # memcpy-style results are not NUL-terminated strings; the gate
            # relies on the canary/return-slot checks instead.
            output_len = None
        else:
            output = _read_cstr(uc, dest, limit=capacity + 64)
            output_len = (
                len(output) - 1 if output.endswith(b"\x00") else capacity + 64
            )
    except Exception:  # noqa: BLE001
        canary = b""
        sentinel_ok = False
        marker_ok = False
        output_len = None
    buffer_match: bool | None = None
    if error is None and expect_copy and capacity > 0:
        try:
            if expect_copy == "strcpy":
                if len(argument) < capacity:
                    expected = argument + b"\x00"
                else:
                    expected = argument[:max(capacity - 1, 0)] + b"\x00"
            else:
                # Length-aware copies are not NUL-terminated.  Only compare
                # when the ABI length was actually observed and is in range; a
                # patched code path that never reaches the modelled callee is
                # an evidence gap, not a pass.
                if modeled_len[0] is None or modeled_len[0] > capacity:
                    expected = None
                else:
                    expected = (argument + b"\x00" * capacity)[:modeled_len[0]]
            if expected is not None:
                buffer_match = bytes(uc.mem_read(dest, len(expected))) == expected
        except Exception:  # noqa: BLE001 - evidence gap, never a crash
            buffer_match = None
    return RuntimeCase(
        input_len=len(argument),
        exit_code=0 if error is None else 1,
        canary_intact=(
            (canary == CANARY)
            and sentinel_ok
            and marker_ok
            and not copy_overflow[0]
        ),
        output_len=output_len,
        buffer_match=buffer_match,
        error=error,
    )
