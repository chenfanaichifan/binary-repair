"""Fail-closed symbol-gap classification for Route A."""
from __future__ import annotations

from routeb.symbol_resolver import apply_stubs, called_names, resolve


def test_existing_and_defined_symbols_are_not_gaps():
    source = """
static void helper(void) { }
void target(char *p) { helper(); printLine(p); }
"""
    r = resolve(source, {"printLine"}, target_name="target")
    assert r.ok
    assert r.defined_in_source == ["helper"]
    assert r.available == ["printLine"]
    assert r.unresolved == []


def test_write_and_exit_gain_reviewed_syscall_stubs():
    source = "void target(void) { write(2, \"x\", 1); exit(1); }"
    r = resolve(source, set(), target_name="target")
    assert r.ok
    assert set(r.stubs) == {"br_write", "br_exit"}
    out = apply_stubs(source, r)
    assert "syscall" in out and "br_write" in out and "br_exit" in out
    assert "fputs" not in out


def test_strlen_is_a_pure_template_not_fail_closed():
    source = "void target(char *p) { strlen(p); }"
    r = resolve(source, set(), target_name="target")
    assert r.ok
    assert r.stubs == ["strlen"]
    assert "static unsigned long strlen" in apply_stubs(source, r)


def test_side_effecting_unknown_symbol_fails_closed():
    source = "void target(char *p) { fputs(p, stderr); }"
    r = resolve(source, set(), target_name="target")
    assert not r.ok
    assert "fputs" in r.unresolved


def test_fputs_stderr_has_a_reviewed_write_shortcut():
    source = "void target(char *p) { fputs(p, stderr); }"
    r = resolve(source, set(), target_name="target", allow_fputs_stderr=True)
    assert r.ok
    assert r.stubs == ["br_fputs"]
    out = apply_stubs(source, r)
    assert "br_fputs(p)" in out
    assert "syscall" in out
    # Non-stderr stream is not silently rewritten.
    r2 = resolve("void t(char*p){ fputs(p, stdout); }", set(), target_name="t",
                 allow_fputs_stderr=True)
    assert not r2.ok


def test_call_extraction_ignores_control_flow():
    names = called_names("if (x) { foo(); } else { bar(); }")
    assert names == {"foo", "bar"}
