"""Unicorn runtime evidence for 32-bit x86 (i386) candidates.

The i386 path uses ``UC_ARCH_X86`` + ``UC_MODE_32``: ELF32/PE32 images are mapped
from their ``PT_LOAD``/section metadata, the source pointer is passed as the
cdecl stack argument at ``[esp+4]``, a 4-byte synthetic return address is
checked for corruption, and imports are intercepted at their thunk/PLT address.

Coverage split:

* synthetic ELF32 images exercise mapping, register setup, the cdecl stack frame
  and the overflow canary without depending on generated fixtures;
* the engine's ELF32/PE32 fixtures run the patched-vs-original acceptance set
  (0/1/15/16/17/64);
* length-aware (``memcpy``) modelling reads the ABI length argument and copies
  exactly that many bytes; the ``memcpy`` immediate is patched 64 -> 16 in the
  synthetic patched case, and the engine ``vuln-memcpy-x86.elf`` fixture is
  covered end-to-end when present.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.services.containers import ContainerInfo, SectionInfo, detect_container
from app.services.repair.analyzer import analyze
from app.services.repair.writer import repair_with_sinks
from app.services.runtime import emulated as emulated_module
from app.services.runtime.emulated import (
    _elf_mappings, _i386_hook_targets, _short_name, emulate,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "elf-x86": ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf",
    "pe-x86": ROOT / "fixtures" / "pe" / "vuln-strcpy-x86.exe",
}
MEMCPY_CASE = ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"
# Dynamic ELF32 (PLT import) and PE32 ``call [IAT]`` (FF 15) fixtures: the
# runtime must intercept a PLT thunk and a direct import call site respectively.
EXTRA_CASES = {
    "elf-x86-dyn": ROOT / "fixtures" / "elf" / "vuln-strcpy-x86-dyn.elf",
    "pe-x86-iat": ROOT / "fixtures" / "pe" / "vuln-strcpy-x86-iat.exe",
}
ABI = "cdecl_x86"
PROBE = [0, 1, 15, 16, 17, 64]
CAPACITY = 15  # safe output ceiling for a 16-byte destination

# ---------------------------------------------------------------------------
# Synthetic ELF32 images (no dependency on the fixture build script).
# ---------------------------------------------------------------------------
TEXT_VA = 0x08048000
_STUB_OFFSET = 0x40
_CODE_OFFSET = 0x100


def _synthetic_elf32(
    code: bytes, *, text_va: int = TEXT_VA, stub_name: str = "strcpy",
) -> bytes:
    """Build a minimal ET_EXEC ELF32/EM_386 image with .text/.symtab/.strtab."""
    stub_va = text_va + _STUB_OFFSET
    image = bytearray(max(_STUB_OFFSET + 4, len(code)))
    image[:len(code)] = code
    image[_STUB_OFFSET] = 0xC3  # ret: hooked before it can execute

    strtab = b"\x00vuln_copy\x00" + stub_name.encode("ascii") + b"\x00"
    stub_name_off = 11  # after the NUL, "vuln_copy" and its NUL
    symtab = b"".join([
        struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0),
        struct.pack("<IIIBBH", 1, text_va, len(code), 0x12, 0, 1),
        struct.pack("<IIIBBH", stub_name_off, stub_va, 1, 0x12, 0, 1),
    ])
    shstrtab = b"\x00.text\x00.symtab\x00.strtab\x00.shstrtab\x00"
    symtab_off = _CODE_OFFSET + len(image)
    strtab_off = symtab_off + len(symtab)
    shstrtab_off = strtab_off + len(strtab)
    shoff = (shstrtab_off + len(shstrtab) + 3) & ~3

    ehdr = struct.pack(
        "<16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x01\x01" + b"\x00" * 9,
        2, 3, 1, text_va, 52, shoff, 0, 52, 32, 1, 40, 5, 4,
    )
    phdr = struct.pack(
        "<IIIIIIII", 1, _CODE_OFFSET, text_va, text_va,
        len(image), len(image), 5, 0x1000,
    )

    def section(name, kind, flags, addr, offset, size, link=0, info=0,
                align=1, entsize=0):
        return struct.pack("<IIIIIIIIII", name, kind, flags, addr, offset,
                           size, link, info, align, entsize)

    shdrs = b"".join([
        section(0, 0, 0, 0, 0, 0),
        section(1, 1, 6, text_va, _CODE_OFFSET, len(image), align=4),
        section(7, 2, 0, 0, symtab_off, len(symtab), link=3, info=1,
                align=4, entsize=16),
        section(15, 3, 0, 0, strtab_off, len(strtab)),
        section(23, 3, 0, 0, shstrtab_off, len(shstrtab)),
    ])
    out = bytearray(ehdr + phdr)
    out += b"\x00" * (_CODE_OFFSET - len(out))
    out += image + symtab + strtab + shstrtab
    out += b"\x00" * (shoff - len(out))
    out += shdrs
    return bytes(out)


def _synthetic_vulnerable_code(text_va: int = TEXT_VA) -> bytes:
    """push ebp; mov ebp,esp; sub esp,0x20; strcpy(ebp-0x10, [ebp+8])."""
    strcpy_va = text_va + _STUB_OFFSET
    code = bytearray(b"\x55\x89\xE5\x83\xEC\x20")  # push ebp / mov ebp,esp / sub
    code += b"\x8B\x45\x08"                        # mov eax,[ebp+8]  (src)
    code += b"\x8D\x55\xF0"                        # lea edx,[ebp-0x10] (dst)
    code += b"\x50\x52"                            # push eax; push edx
    call_at = len(code)
    code += b"\xE8" + struct.pack("<i", strcpy_va - (text_va + call_at + 5))
    code += b"\x83\xC4\x08\xC9\xC3"                # add esp,8; leave; ret
    return bytes(code)


def _synthetic_bounded_code() -> bytes:
    """Same frame, but only NUL-terminates the destination (safe stand-in)."""
    return bytes.fromhex("5589e583ec208b4508c60000c9c3")


_MEMCPY_IMM_OFFSET = 13  # imm32 of ``mov ecx, imm32`` in the code below


def _synthetic_memcpy_code(length: int, text_va: int = TEXT_VA) -> bytes:
    """push ebp; ...; memcpy(ebp-0x10, [ebp+8], length) via cdecl pushes."""
    stub_va = text_va + _STUB_OFFSET
    code = bytearray(b"\x55\x89\xE5\x83\xEC\x20")  # push ebp; mov ebp,esp; sub
    code += b"\x8B\x45\x08"                            # mov eax,[ebp+8]  (src)
    code += b"\x8D\x55\xF0"                            # lea edx,[ebp-0x10] (dst)
    code += b"\xB9" + struct.pack("<I", length & 0xFFFFFFFF)  # mov ecx, length
    code += b"\x51\x50\x52"                            # push ecx; eax; edx
    call_at = len(code)
    code += b"\xE8" + struct.pack("<i", stub_va - (text_va + call_at + 5))
    code += b"\x83\xC4\x0C\xC9\xC3"                  # add esp,12; leave; ret
    return bytes(code)


def _patch_imm32(data: bytes, code_offset: int, value: int) -> bytes:
    out = bytearray(data)
    position = _CODE_OFFSET + code_offset
    out[position:position + 4] = struct.pack("<I", value)
    return bytes(out)


# ---------------------------------------------------------------------------
# Synthetic ELF64 images: ABI length-argument positions for the generic path.
# ---------------------------------------------------------------------------
TEXT_VA64 = 0x400000
_MEMCPY64_IMM_OFFSET = 13   # imm32 of ``mov edx, imm32`` / ``mov r8d, imm32``
_MEMCPY_ARM64_LEN_WORD = 4  # instruction index of ``movz x2, #len``


def _synthetic_elf64(
    code: bytes, *, machine: int, text_va: int = TEXT_VA64,
    stub_name: str = "memcpy",
) -> bytes:
    """Build a minimal ET_EXEC ELF64 image with .text/.symtab/.strtab."""
    stub_va = text_va + _STUB_OFFSET
    image = bytearray(max(_STUB_OFFSET + 8, len(code)))
    image[:len(code)] = code
    image[_STUB_OFFSET] = 0xC3  # hooked before it can execute

    strtab = b"\x00vuln_copy\x00" + stub_name.encode("ascii") + b"\x00"
    symtab = b"".join([
        struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0),
        struct.pack("<IBBHQQ", 1, 0x12, 0, 1, text_va, len(code)),
        struct.pack("<IBBHQQ", 11, 0x12, 0, 1, stub_va, 1),
    ])
    shstrtab = b"\x00.text\x00.symtab\x00.strtab\x00.shstrtab\x00"
    symtab_off = _CODE_OFFSET + len(image)
    strtab_off = symtab_off + len(symtab)
    shstrtab_off = strtab_off + len(strtab)
    shoff = (shstrtab_off + len(shstrtab) + 7) & ~7

    ehdr = struct.pack(
        "<16sHHIQQQIHHHHHH",
        b"\x7fELF\x02\x01\x01" + b"\x00" * 9,
        2, machine, 1, text_va, 64, shoff, 0, 64, 56, 1, 64, 5, 4,
    )
    phdr = struct.pack(
        "<IIQQQQQQ", 1, 5, _CODE_OFFSET, text_va, text_va,
        len(image), len(image), 0x1000,
    )

    def section(name, kind, flags, addr, offset, size, link=0, info=0,
                align=1, entsize=0):
        return struct.pack("<IIQQQQIIQQ", name, kind, flags, addr, offset,
                           size, link, info, align, entsize)

    shdrs = b"".join([
        section(0, 0, 0, 0, 0, 0),
        section(1, 1, 6, text_va, _CODE_OFFSET, len(image), align=16),
        section(7, 2, 0, 0, symtab_off, len(symtab), link=3, info=1,
                align=8, entsize=24),
        section(15, 3, 0, 0, strtab_off, len(strtab)),
        section(23, 3, 0, 0, shstrtab_off, len(shstrtab)),
    ])
    out = bytearray(ehdr + phdr)
    out += b"\x00" * (_CODE_OFFSET - len(out))
    out += image + symtab + strtab + shstrtab
    out += b"\x00" * (shoff - len(out))
    out += shdrs
    return bytes(out)


def _synthetic_memcpy64_sysv_code(length: int) -> bytes:
    """sub rsp,0x20; memcpy(rsp+0x10, rdi, length) with SysV rdi/rsi/rdx."""
    stub_va = TEXT_VA64 + _STUB_OFFSET
    code = bytearray(b"\x48\x83\xEC\x20")          # sub rsp,0x20
    code += b"\x48\x89\xFE"                        # mov rsi,rdi
    code += b"\x48\x8D\x7C\x24\x10"              # lea rdi,[rsp+0x10]
    code += b"\xBA" + struct.pack("<I", length)      # mov edx, length
    call_at = len(code)
    code += b"\xE8" + struct.pack("<i", stub_va - (TEXT_VA64 + call_at + 5))
    code += b"\x48\x83\xC4\x20\xC3"              # add rsp,0x20; ret
    return bytes(code)


def _synthetic_memcpy64_win_code(length: int) -> bytes:
    """sub rsp,0x20; memcpy(rsp+0x10, rcx, length) with Win64 rcx/rdx/r8."""
    stub_va = TEXT_VA64 + _STUB_OFFSET
    code = bytearray(b"\x48\x83\xEC\x20")          # sub rsp,0x20
    code += b"\x48\x89\xCA"                        # mov rdx,rcx
    code += b"\x48\x8D\x4C\x24\x10"              # lea rcx,[rsp+0x10]
    code += b"\x41\xB8" + struct.pack("<I", length)  # mov r8d, length
    call_at = len(code)
    code += b"\xE8" + struct.pack("<i", stub_va - (TEXT_VA64 + call_at + 5))
    code += b"\x48\x83\xC4\x20\xC3"              # add rsp,0x20; ret
    return bytes(code)


def _synthetic_memcpy_arm64_code(length: int) -> bytes:
    """sub sp,#0x20; save x30; memcpy(sp+0x10, x0, x2)."""
    pc = TEXT_VA64
    words: list[int] = []
    words.append(0xD10083FF)                       # sub sp,sp,#0x20
    words.append(0xF90003FE)                       # str x30,[sp]
    words.append(0xAA0003E1)                       # mov x1,x0
    words.append(0x910043E0)                       # add x0,sp,#0x10
    words.append(0xD2800002 | ((length & 0xFFFF) << 5))  # movz x2,#length
    bl_pc = pc + len(words) * 4
    stub_va = TEXT_VA64 + _STUB_OFFSET
    words.append(0x94000000 | (((stub_va - bl_pc) >> 2) & 0x3FFFFFF))
    words.append(0xF94003FE)                       # ldr x30,[sp]
    words.append(0x910083FF)                       # add sp,sp,#0x20
    words.append(0xD65F03C0)                       # ret
    return b"".join(struct.pack("<I", word) for word in words)


def _patch_elf64_imm32(data: bytes, offset: int, value: int) -> bytes:
    out = bytearray(data)
    position = _CODE_OFFSET + offset
    out[position:position + 4] = struct.pack("<I", value)
    return bytes(out)


def _patch_arm64_length(data: bytes, value: int) -> bytes:
    out = bytearray(data)
    position = _CODE_OFFSET + _MEMCPY_ARM64_LEN_WORD * 4
    word = 0xD2800002 | ((value & 0xFFFF) << 5)
    out[position:position + 4] = struct.pack("<I", word)
    return bytes(out)


_ELF64_ABI_CASES = {
    "x86_64-sysv": dict(
        machine=62, abi="sysv_x86_64", dest_rel=-0x10,
        code=_synthetic_memcpy64_sysv_code,
        patch=lambda data: _patch_elf64_imm32(data, _MEMCPY64_IMM_OFFSET, 16),
    ),
    "win64": dict(
        machine=62, abi="win64_x86_64", dest_rel=-0x10,
        code=_synthetic_memcpy64_win_code,
        patch=lambda data: _patch_elf64_imm32(data, _MEMCPY64_IMM_OFFSET + 1, 16),
    ),
    "arm64": dict(
        machine=183, abi="aapcs64", dest_rel=-0x10,
        code=_synthetic_memcpy_arm64_code,
        patch=lambda data: _patch_arm64_length(data, 16),
    ),
}


@pytest.mark.parametrize("name", sorted(_ELF64_ABI_CASES))
def test_synthetic_elf64_memcpy_reads_abi_length(name):
    case = _ELF64_ABI_CASES[name]
    original_data = _synthetic_elf64(
        case["code"](64), machine=case["machine"],
    )
    container = detect_container(original_data)
    assert container.format == "elf" and container.bits == 64
    kwargs = dict(
        function_va=TEXT_VA64, dest_rel=case["dest_rel"], capacity=16,
        abi=case["abi"], lengths=PROBE,
        copy_kind="memcpy_length", callee="memcpy",
    )
    original = emulate(original_data, container, **kwargs)
    assert original.verdict == "fail", (name, original.to_dict())
    for runtime_case in original.cases:
        assert runtime_case.canary_intact is False, (name, runtime_case.to_dict())
        assert runtime_case.output_len is None

    patched = case["patch"](original_data)
    good = emulate(patched, detect_container(patched), **kwargs)
    assert good.verdict == "pass", (name, good.to_dict())
    for runtime_case in good.cases:
        assert runtime_case.canary_intact is True, (name, runtime_case.to_dict())
        assert runtime_case.output_len is None


def test_synthetic_elf32_mapping_and_metadata():
    data = _synthetic_elf32(_synthetic_vulnerable_code())
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == ("elf", "i386", 32)
    assert container.symbols == {
        TEXT_VA: "vuln_copy",
        TEXT_VA + _STUB_OFFSET: "strcpy",
    }
    (mapping,) = _elf_mappings(data)
    assert mapping.va == TEXT_VA
    assert mapping.offset == _CODE_OFFSET
    assert mapping.size >= len(_synthetic_vulnerable_code())


def test_synthetic_elf32_detects_unbounded_overflow():
    data = _synthetic_elf32(_synthetic_vulnerable_code())
    container = detect_container(data)
    patched = emulate(data, container, function_va=TEXT_VA, dest_rel=-0x14,
                     capacity=16, abi=ABI)
    assert patched.tier == "emulated_run"
    assert patched.engine == "unicorn-i386"
    assert patched.verdict == "fail"
    by_len = {case.input_len: case for case in patched.cases}
    assert [case.input_len for case in patched.cases] == PROBE
    for length in (0, 1, 15):
        assert by_len[length].canary_intact is True
        assert by_len[length].output_len == length
    for length in (16, 17, 64):
        assert by_len[length].canary_intact is False


def test_synthetic_elf32_bounded_function_passes():
    data = _synthetic_elf32(_synthetic_bounded_code())
    container = detect_container(data)
    evidence = emulate(data, container, function_va=TEXT_VA, dest_rel=-0x14,
                       capacity=16, abi=ABI)
    assert evidence.verdict == "pass", evidence.to_dict()
    assert all(case.canary_intact is True for case in evidence.cases)
    assert all(case.output_len == 0 for case in evidence.cases)


def test_synthetic_elf32_memcpy_length_model():
    data = _synthetic_elf32(_synthetic_memcpy_code(64), stub_name="memcpy")
    container = detect_container(data)
    original = emulate(
        data, container, function_va=TEXT_VA, dest_rel=-0x14, capacity=16,
        abi=ABI, lengths=PROBE, copy_kind="memcpy_length", callee="memcpy",
    )
    assert original.verdict == "fail", original.to_dict()
    assert [case.input_len for case in original.cases] == PROBE
    for case in original.cases:
        assert case.canary_intact is False, case.to_dict()
        assert case.output_len is None

    patched = _patch_imm32(data, _MEMCPY_IMM_OFFSET, 16)
    good = emulate(
        patched, detect_container(patched), function_va=TEXT_VA, dest_rel=-0x14,
        capacity=16, abi=ABI, lengths=PROBE,
        copy_kind="memcpy_length", callee="memcpy",
    )
    assert good.verdict == "pass", good.to_dict()
    assert good.engine == "unicorn-i386"
    assert [case.input_len for case in good.cases] == PROBE
    for case in good.cases:
        assert case.canary_intact is True, case.to_dict()
        assert case.output_len is None


def test_synthetic_elf32_memcpy_length_comes_from_abi_argument():
    """Only the stack length argument changes: the model must read it, not the
    callee name.  ``callee`` alone (no ``copy_kind``) selects length semantics."""
    for length, expected in ((0, "pass"), (16, "pass"), (17, "fail"), (64, "fail")):
        data = _synthetic_elf32(_synthetic_memcpy_code(length), stub_name="memcpy")
        evidence = emulate(
            data, detect_container(data), function_va=TEXT_VA, dest_rel=-0x14,
            capacity=16, abi=ABI, lengths=[0, 64], callee="memcpy",
        )
        assert evidence.verdict == expected, (length, evidence.to_dict())
        for case in evidence.cases:
            assert case.output_len is None

    # strcpy keeps the C-string model and still reports output lengths.
    strcpy_data = _synthetic_elf32(_synthetic_vulnerable_code())
    strcpy_evidence = emulate(
        strcpy_data, detect_container(strcpy_data), function_va=TEXT_VA,
        dest_rel=-0x14, capacity=16, abi=ABI, lengths=[0, 1, 15],
        callee="strcpy",
    )
    assert strcpy_evidence.verdict == "pass"
    assert all(case.output_len is not None for case in strcpy_evidence.cases)


def test_memcpy_fixture_end_to_end():
    path = MEMCPY_CASE
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == ("elf", "i386", 32)
    sinks = analyze(data).patchable()
    if not sinks:
        pytest.skip("i386 memcpy immediate sink is not available in this analyzer")
    sink = sinks[0]
    assert sink.kind == "memcpy_length", sink.to_dict()
    assert sink.capacity == 16, sink.to_dict()
    assert sink.length == 64, sink.to_dict()

    written = repair_with_sinks(data, container, [sink])
    assert written.ok, written.limitations
    patched = written.patched
    assert patched is not None and patched != data
    emulate_kwargs = dict(
        function_va=sink.function_va,
        dest_rel=int(sink.dest_rel or 0),
        capacity=sink.capacity,
        abi=ABI,
        lengths=PROBE,
        copy_kind=sink.kind,
        callee=sink.callee,
    )
    good = emulate(patched, detect_container(patched), **emulate_kwargs)
    assert good.verdict == "pass", good.to_dict()
    for case in good.cases:
        assert case.canary_intact is True, case.to_dict()
        assert case.output_len is None

    baseline = emulate(data, container, **emulate_kwargs)
    assert baseline.verdict == "fail", baseline.to_dict()
    assert any(case.canary_intact is False for case in baseline.cases)


@pytest.mark.parametrize("name", sorted(EXTRA_CASES))
def test_plt_and_iat_strcpy_candidates(name):
    path = EXTRA_CASES[name]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) in {
        ("elf", "i386", 32), ("pe", "i386", 32),
    }
    sinks = analyze(data).patchable()
    if not sinks:
        pytest.skip(f"fixture sink not available: {name}")
    sink = sinks[0]
    written = repair_with_sinks(data, container, [sink])
    assert written.ok, written.limitations
    patched = written.patched
    assert patched is not None
    runtime_kwargs = dict(
        function_va=sink.function_va,
        dest_rel=int(sink.dest_rel or 0),
        capacity=sink.capacity,
        abi=ABI,
        lengths=PROBE,
    )
    good = emulate(patched, detect_container(patched), **runtime_kwargs)
    assert good.verdict == "pass", (name, good.to_dict())
    assert all(case.canary_intact is True for case in good.cases)
    for case in good.cases:
        assert case.output_len is not None
        assert case.output_len <= min(case.input_len, CAPACITY)

    baseline = emulate(data, container, **runtime_kwargs)
    assert baseline.verdict == "fail", (name, baseline.to_dict())
    assert any(case.canary_intact is False for case in baseline.cases)


def test_short_name_normalisation():
    assert _short_name("c.string.strcpy") == "strcpy"
    assert _short_name("_strcpy") == "strcpy"
    assert _short_name("strcpy@GLIBC_2.0") == "strcpy"
    assert _short_name("c.string.stpcpy") == "stpcpy"


def test_i386_pe_import_thunks_are_resolved():
    path = CASES["pe-x86"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    copy_targets, puts_targets, _copy_calls, _puts_calls = _i386_hook_targets(
        data, container,
    )
    assert copy_targets, "PE32 strcpy thunk was not resolved"
    assert puts_targets, "PE32 puts thunk was not resolved"
    assert any(mode == "cstr" for _va, mode in copy_targets)

    text = next(section for section in container.sections if section.name == ".text")
    raw = data[text.offset:text.offset + text.size]
    for target in [va for va, _mode in copy_targets] + puts_targets:
        section = container.section_at(target)
        assert section is not None and section.executable
        offset = target - text.va
        # MinGW thunk: ff 25 <abs32> == jmp dword ptr [IAT]
        assert raw[offset] == 0xFF and raw[offset + 1] == 0x25


def test_i386_direct_iat_call_site_is_hooked(monkeypatch):
    """``call dword ptr [IAT]`` (ff 15) sites are modeled at the call itself."""
    # push ebp; mov ebp,esp; sub esp,0x20; mov eax,[ebp+8]; lea edx,[ebp-0x10];
    # push eax; push edx; call dword ptr [0x403000]; add esp,8; leave; ret
    code = bytes.fromhex(
        "5589e583ec208b45088d55f05052"
        "ff1500304000"
        "83c408c9c3"
    )
    data = code + b"\x00" * 16
    container = ContainerInfo(
        format="pe", arch="i386", bits=32, image_base=0x400000,
        sections=[SectionInfo(name=".text", segment="", va=0x401000,
                              size=len(data), offset=0, executable=True)],
        imports={0x403000: "strcpy"},
    )
    _thunks, calls = emulated_module._i386_import_edges(data, container)
    assert calls == {0x40100E: ("strcpy", 6)}

    monkeypatch.setattr(
        emulated_module, "_pe_mappings",
        lambda _data: [emulated_module._Mapping(0x401000, 0x1000, 0)],
    )
    evidence = emulate(data, container, function_va=0x401000, dest_rel=-0x14,
                       capacity=16, abi=ABI, lengths=[0, 1, 15, 16, 17, 64])
    assert evidence.verdict == "fail"
    by_len = {case.input_len: case for case in evidence.cases}
    for length in (0, 1, 15):
        assert by_len[length].canary_intact is True
    for length in (16, 17, 64):
        assert by_len[length].canary_intact is False


def test_i386_guard_abi_contract():
    from app.services.repair.guards import abi_for

    assert abi_for("elf", "i386") == ABI
    assert abi_for("pe", "i386") == ABI


@pytest.mark.parametrize("name", sorted(CASES))
def test_emulated_run_accepts_patched_and_rejects_original(name):
    path = CASES[name]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) in {
        ("elf", "i386", 32), ("pe", "i386", 32),
    }

    analysis = analyze(data)
    sinks = analysis.patchable()
    assert sinks, analysis.limitations
    sink = sinks[0]
    assert sink.arch == "i386"
    assert sink.capacity == 16
    assert sink.dest_rel is not None and sink.dest_rel < 0
    assert sink.function_va

    written = repair_with_sinks(data, container, [sink])
    assert written.ok, written.limitations
    patched = written.patched
    assert patched is not None and patched != data
    patched_container = detect_container(patched)
    assert (patched_container.format, patched_container.arch) == (
        container.format, "i386",
    )

    good = emulate(
        patched, patched_container,
        function_va=sink.function_va, dest_rel=sink.dest_rel,
        capacity=sink.capacity, abi=ABI, lengths=PROBE,
    )
    assert good.tier == "emulated_run"
    assert good.engine == "unicorn-i386"
    assert good.verdict == "pass", good.to_dict()
    assert [case.input_len for case in good.cases] == PROBE
    assert all(case.canary_intact is True for case in good.cases), good.to_dict()
    for case in good.cases:
        assert case.output_len is not None
        assert case.output_len <= min(case.input_len, CAPACITY)

    # The original function overflows at and above its capacity.
    baseline = emulate(
        data, container,
        function_va=sink.function_va, dest_rel=sink.dest_rel,
        capacity=sink.capacity, abi=ABI, lengths=[16, 17, 64],
    )
    assert baseline.verdict == "fail", baseline.to_dict()
    assert all(case.canary_intact is False for case in baseline.cases)

    # Short inputs are clean even on the vulnerable build.
    small = emulate(
        data, container,
        function_va=sink.function_va, dest_rel=sink.dest_rel,
        capacity=sink.capacity, abi=ABI, lengths=[0, 1, 15],
    )
    assert small.verdict == "pass", small.to_dict()
    assert all(case.canary_intact is True for case in small.cases)
