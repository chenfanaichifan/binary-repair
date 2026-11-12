"""The generated vulnerable ELF has the intended layout and unsafe read."""
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"


def test_vuln_elf_is_x86_64_and_has_text():
    with ELF.open("rb") as fh:
        elf = ELFFile(fh)
        assert elf.header["e_machine"] == "EM_X86_64"
        assert elf.header["e_type"] == "ET_EXEC"
        text = elf.get_section_by_name(".text")
        assert text is not None
        assert text["sh_addr"] == 0x401000
        assert text.data()[:4] == b"\xb8\x01\x00\x00"


def test_vuln_elf_has_unbounded_read_after_16_byte_stack_buffer():
    with ELF.open("rb") as fh:
        elf = ELFFile(fh)
        text = elf.get_section_by_name(".text").data()
    instructions = list(Cs(CS_ARCH_X86, CS_MODE_64).disasm(text, 0x401000))
    mnemonics = [(ins.mnemonic, ins.op_str) for ins in instructions]
    assert ("sub", "rsp, 0x10") in mnemonics
    # read: rax=0, rdi=0, rsi=rsp, rdx=0x100, syscall
    assert ("mov", "edx, 0x100") in mnemonics
    assert ("syscall", "") in mnemonics
