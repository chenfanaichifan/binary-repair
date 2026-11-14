"""Measured ELF symbol inventory used by Route A auto-symbol resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.repair.elf_symbols import available_symbols

ROOT = Path(__file__).resolve().parents[1]
CWE121 = ROOT / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b" / "original.elf"
CWE416 = ROOT / "fixtures" / "public" / "CWE416_Use_After_Free__malloc_free_char_01_noinput" / "original.elf"


@pytest.mark.skipif(not CWE121.is_file(), reason="CWE121 fixture missing")
def test_cwe121_has_printline_but_no_malloc():
    inv = available_symbols(CWE121.read_bytes())
    assert "printLine" in inv.by_name
    assert "malloc" not in inv.by_name
    assert "free" not in inv.by_name


@pytest.mark.skipif(not CWE416.is_file(), reason="CWE416 fixture missing")
def test_cwe416_exposes_malloc_free_when_imported():
    inv = available_symbols(CWE416.read_bytes())
    joined = set(inv.by_name) | set(inv.ambiguous)
    assert "malloc" in joined
    assert "free" in joined


@pytest.mark.skipif(not CWE121.is_file(), reason="CWE121 fixture missing")
def test_resolver_blocks_malloc_only_when_no_plt_dependency():
    from routeb.symbol_resolver import resolve

    inv = available_symbols(CWE121.read_bytes())
    blocked = resolve("void target(){ malloc(8); }", inv.names, target_name="target")
    assert blocked.blocked == ["malloc"]

    if CWE416.is_file():
        inv416 = available_symbols(CWE416.read_bytes())
        allowed = resolve("void target(){ malloc(8); free(0); }",
                          inv416.names, target_name="target")
        assert allowed.ok
        assert set(allowed.available) == {"malloc", "free"}
