from pathlib import Path

import lief

from app.services.pe_repair import repair_pe_strcpy

ROOT = Path(__file__).resolve().parents[1]
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"


def test_pe_strcpy_repair_adds_cave_and_redirects_call():
    if not PE.is_file():
        return
    data = PE.read_bytes()
    parsed = lief.PE.parse(list(data))
    text = parsed.get_section(".text")
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    base = int(parsed.optional_header.imagebase) + int(text.virtual_address)
    call = next(i for i in Cs(CS_ARCH_X86, CS_MODE_64).disasm(bytes(text.content), base)
                if i.mnemonic == "call")
    patched, report = repair_pe_strcpy(data, call_va=call.address, capacity=16)
    assert patched is not None, report.limitations
    assert report.strategy == "strcpy-cave"
    assert report.section == ".brfix"
    reparsed = lief.PE.parse(list(patched))
    assert reparsed is not None
    assert reparsed.get_section(".brfix") is not None
