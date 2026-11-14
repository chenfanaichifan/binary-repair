"""Static ABI checks for injected x86-64 blocks (evidence, not gate owner)."""
from __future__ import annotations

from app.services.repair.abi import check_x86_64


def test_valid_aligned_call_block_passes():
    # sub rsp,8; call rel32; add rsp,8; ret
    code = bytes.fromhex("48 83 ec 08 e8 00 00 00 00 48 83 c4 08 c3")
    report = check_x86_64(code)
    assert report.ok
    assert not [f for f in report.findings if f.code == "stack_misaligned_before_call"]


def test_call_without_alignment_is_fatal():
    # call rel32; ret
    code = bytes.fromhex("e8 00 00 00 00 c3")
    report = check_x86_64(code)
    assert not report.ok
    assert any(f.code == "stack_misaligned_before_call" and f.severity == "fatal"
               for f in report.findings)


def test_ret_with_unrestored_stack_is_fatal():
    # sub rsp,8; ret
    code = bytes.fromhex("48 83 ec 08 c3")
    report = check_x86_64(code)
    assert not report.ok
    assert any(f.code == "rsp_not_restored" for f in report.findings)


def test_pushed_callee_saved_not_restored_is_fatal():
    # push rbx; add rsp,8; ret
    code = bytes.fromhex("53 48 83 c4 08 c3")
    report = check_x86_64(code)
    assert not report.ok
    assert any(f.code == "callee_saved_not_restored" for f in report.findings)


def test_missing_ret_is_fatal():
    report = check_x86_64(b"\x90")
    assert not report.ok
    assert any(f.code == "no_ret" for f in report.findings)


def test_two_epilogue_paths_are_not_a_false_rsp_error():
    # push rbp; mov rbp,rsp; sub rsp,0x10; jne +6; two equivalent epilogues.
    code = bytes.fromhex(
        "55 48 89 e5 48 83 ec 10 75 06 48 83 c4 10 5d c3 "
        "48 83 c4 10 5d c3"
    )
    report = check_x86_64(code)
    assert report.ok
    assert not [f for f in report.findings if f.code == "rsp_not_restored"]
