"""Selective call-mode tests for the assembly failure path."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_assembly_repair import (
    ControlledCall,
    _apply_call_relocations,
    _assemble_with_relocations,
    _controlled_syscall_config,
    _expand_controlled_template,
    _validate_assembly_text,
    _validate_code,
    discover_controlled_calls,
)
from app.services.containers import detect_container
from app.services.repair.call_targets import AllowedCall, discover_allowed_calls

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
CWE121 = (ROOT / "fixtures" / "public"
          / "CWE121_src_char_declare_cpy_51b" / "original.elf")
CWE121_TARGET = (
    "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink")
CWE121_CONTRACT = {
    "exit_code": 1,
    "stderr": "ERROR: input exceeds destination capacity\n",
}
CWE121_MESSAGE = b"ERROR: input exceeds destination capacity\n"


def test_numeric_and_named_calls_are_rewritten_to_allowed_symbol():
    allowed = [AllowedCall(name="puts", target_va=0x401030, source="import")]
    clean = _validate_assembly_text("call puts\ncall 0x401030\nret\n", "x86_64", allowed)
    assert clean.count("call puts") == 2
    # Default leaf-only mode still rejects the same text.
    with pytest.raises(ValueError, match="forbidden|not allowed"):
        _validate_assembly_text("call puts\nret\n", "x86_64")


def test_indirect_and_unknown_calls_are_rejected():
    allowed = [AllowedCall(name="puts", target_va=0x401030, source="import")]
    with pytest.raises(ValueError, match="forbidden|not allowed"):
        _validate_assembly_text("call *%rax\nret\n", "x86_64", allowed)
    with pytest.raises(ValueError, match="not allowed"):
        _validate_assembly_text("call puts\ncall other\nret\n", "x86_64", allowed)


def test_call_relocation_is_resolved_for_the_cave_address():
    allowed = [AllowedCall(name="puts", target_va=0x401030, source="import")]
    clean = _validate_assembly_text("call puts\nret\n", "x86_64", allowed)
    code, relocs = _assemble_with_relocations(clean, "x86_64")
    assert len(relocs) == 1 and relocs[0]["symbol"] == "puts"
    cave = 0x200000
    patched = _apply_call_relocations(code, "x86_64", cave, relocs, allowed)
    assert patched != code
    _validate_code(patched, "x86_64", allowed, base_va=cave)
    with pytest.raises(ValueError):
        _validate_code(patched, "x86_64", allowed)  # wrong base must fail closed


def test_call_relocation_rejects_non_allowed_symbol():
    allowed = [AllowedCall(name="puts", target_va=0x401030, source="import")]
    clean = _validate_assembly_text("call puts\nret\n", "x86_64", allowed)
    code, relocs = _assemble_with_relocations(clean, "x86_64")
    with pytest.raises(ValueError, match="not allowed"):
        _apply_call_relocations(code, "x86_64", 0x200000, relocs, [])


@pytest.mark.skipif(not ELF.is_file(), reason="fixture missing")
def test_discovery_exposes_only_existing_direct_calls():
    data = ELF.read_bytes()
    container = detect_container(data)
    va = next(va for va, name in container.symbols.items() if name == "vuln_copy")
    calls = discover_allowed_calls(data, container, va)
    names = {call.name for call in calls}
    assert "puts" in names
    assert all(call.target_va > 0 for call in calls)




@pytest.mark.skipif(not CWE121.is_file(), reason="CWE121 fixture missing")
def test_controlled_calls_expose_only_real_imports_and_fixed_templates():
    data = CWE121.read_bytes()
    container = detect_container(data)
    va = next(va for va, name in container.symbols.items()
              if name == CWE121_TARGET)
    calls = discover_controlled_calls(data, container, va, CWE121_CONTRACT)
    by_name = {call.name: call for call in calls}
    exit_call = by_name["br_exit_group"]
    assert exit_call.source == "template" and exit_call.kind == "exit"
    assert exit_call.exit_code == 1
    write_call = by_name["br_write_stderr"]
    assert write_call.source == "template" and write_call.fd == 2
    assert write_call.payload() == CWE121_MESSAGE
    # This ELF imports neither exit() nor fputs(): no real exit call target.
    assert "exit" not in by_name and "fputs" not in by_name
    # Only a real PLT import may be surfaced as an import call.
    assert by_name["strcpy"].source == "import"
    assert all(call.target_va for call in calls
               if call.source == "import")
    # No contract -> no templates (fail closed).
    plain = discover_controlled_calls(data, container, va, None)
    assert all(call.source != "template" for call in plain)


@pytest.mark.skipif(not CWE121.is_file(), reason="CWE121 fixture missing")
def test_controlled_templates_are_expanded_and_byte_validated():
    data = CWE121.read_bytes()
    container = detect_container(data)
    va = next(va for va, name in container.symbols.items()
              if name == CWE121_TARGET)
    calls = discover_controlled_calls(data, container, va, CWE121_CONTRACT)
    text = "\n".join([
        ".intel_syntax noprefix",
        "call br_write_stderr",
        "call br_exit_group",
    ])
    clean = _validate_assembly_text(text, "x86_64", calls,
                                    controlled_calls=calls)
    assert "syscall" in clean and "br_write_stderr" not in clean
    code, relocs = _assemble_with_relocations(clean, "x86_64")
    assert relocs == []
    config = _controlled_syscall_config(CWE121_CONTRACT)
    assert config == {"exit_codes": {1},
                      "write_lengths": {len(CWE121_MESSAGE)},
                      "write_fds": {2}}
    _validate_code(code, "x86_64", calls, controlled_syscalls=config)
    # No contract means no allowed syscall: the same bytes fail closed.
    with pytest.raises(ValueError, match="syscall"):
        _validate_code(code, "x86_64", calls)


def test_controlled_template_expansion_is_arch_and_kind_fail_closed():
    exit_template = ControlledCall(
        name="br_exit_group", source="template", kind="exit", exit_code=1)
    with pytest.raises(ValueError, match="x86-64"):
        _expand_controlled_template(exit_template, "arm64")
    with pytest.raises(ValueError, match="exit code"):
        _expand_controlled_template(
            ControlledCall(name="br_exit_group", source="template",
                            kind="exit"), "x86_64")
    with pytest.raises(ValueError, match="no payload"):
        _expand_controlled_template(
            ControlledCall(name="br_write_stderr", source="template",
                            kind="write", fd=2), "x86_64")


def test_unknown_or_handwritten_controlled_call_rejected():
    allowed = [ControlledCall(name="br_exit_group", source="template",
                              kind="exit", exit_code=1)]
    with pytest.raises(ValueError, match="not allowed"):
        _validate_assembly_text("call br_other", "x86_64", [],
                                controlled_calls=allowed)
    with pytest.raises(ValueError, match="not allowed"):
        _validate_assembly_text("call exit", "x86_64", [],
                                controlled_calls=allowed)
    with pytest.raises(ValueError, match="forbidden"):
        _validate_assembly_text("syscall", "x86_64", [],
                                controlled_calls=allowed)


@pytest.mark.skipif(not (ROOT / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b" / "original.elf").is_file(),
                    reason="CWE121 fixture missing")
def test_inject_target_resolves_whitelisted_call_into_new_pt_load():
    from scripts.run_hard_benchmark import _inject_target, _target_va

    data = (ROOT / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b" / "original.elf").read_bytes()
    container = detect_container(data)
    va = _target_va(container, "badSink")
    calls = discover_allowed_calls(data, container, va)
    assert any(call.name == "printLine" for call in calls)
    patched, meta = _inject_target(
        data, "badSink", 50,
        ".intel_syntax noprefix\n.text\ncall printLine\nret\n",
        calls,
    )
    assert patched is not None, meta
    assert meta["call_relocations"] >= 1


def test_call_relocations_patch_executed_pt_load_not_nobits_section():
    """The hard multicall cave VA overlaps .tbss; relocations must patch PT_LOAD."""
    import io
    from elftools.elf.elffile import ELFFile
    from scripts.run_hard_benchmark import _inject_target, _target_va

    binary = ROOT / "fixtures" / "hard-cases" / "vuln-hardcases-c-x86_64.elf"
    if not binary.is_file():
        import pytest
        pytest.skip("hard multicall fixture missing")
    data = binary.read_bytes()
    container = detect_container(data)
    va = _target_va(container, "multicall_bad")
    calls = discover_allowed_calls(data, container, va)
    patched, meta = _inject_target(
        data, "multicall_bad", 16,
        ".intel_syntax noprefix\n.text\ncall helper_copy\ncall puts\nret\n",
        calls,
    )
    assert patched is not None, meta
    cave = int(meta["cave_va"], 16)
    code = bytes.fromhex(meta["code_hex"])
    with io.BytesIO(patched) as stream:
        elf = ELFFile(stream)
        offset = None
        for segment in elf.iter_segments():
            if segment["p_type"] != "PT_LOAD":
                continue
            start, filesz = int(segment["p_vaddr"]), int(segment["p_filesz"])
            if start <= cave < start + filesz:
                offset = int(segment["p_offset"]) + (cave - start)
                break
    assert offset is not None
    executed = patched[offset:offset + len(code)]
    assert executed != code
    # Calls were zero displacement in the assembled block; the executed cave
    # must now contain non-zero rel32 call targets.
    assert executed.count(b"\xe8\x00\x00\x00\x00") == 0
