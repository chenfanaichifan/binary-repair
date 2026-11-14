"""Selective call-mode tests for the assembly failure path."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_assembly_repair import (
    _apply_call_relocations,
    _assemble_with_relocations,
    _validate_assembly_text,
    _validate_code,
)
from app.services.containers import detect_container
from app.services.repair.call_targets import AllowedCall, discover_allowed_calls

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"


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
