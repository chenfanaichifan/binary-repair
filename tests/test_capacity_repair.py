"""Tests for the reviewed capacity-check divergence repair (CWE-131/697/787).

The end-to-end fixture is the MARCX1 archive renderer ``marcx``: its ``render()``
function inlines the same range check three times and the ``span`` branch uses
the payload-pool size instead of the output buffer size.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from capstone import CS_ARCH_X86, CS_MODE_64, Cs

from app.services.repair.capacity import (
    detect_capacity_confusion,
    repair_capacity_confusion,
)

ROOT = Path(__file__).resolve().parents[1]
MARCX = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"
SYNTHETIC = ROOT / "fixtures" / "hard-cases" / "vuln-capacity-param-x86_64.elf"
MANIFEST = ROOT / "fixtures" / "poc" / "marcx-capacity.json"

MARCX_SHA256 = "72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5"
PATCHED_SHA256 = "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2"
SITE_VA = 0x4020D9
SITE_FILE_OFFSET = 0x20D9
BLOCK_SIZE = 16
BEFORE_HEX = "39f3720c89df29f739d70f83c4feffff"
AFTER_HEX = "4489e729f7720939d70f83c5feffff90"
MESSAGE_VA = 0x483800
MESSAGE_OFFSET = 538624

SYNTHETIC_SHA256 = "371b9edd51b72764f0a3e821f47c0ba8286ba7540b749fcb8a658aec3e6346a5"
SYNTHETIC_PATCHED_SHA256 = "5b6501b058f24591d9aa4cc954acf6cb6dbcb29bdf445fe9f70480645fdb4322"
SYNTHETIC_SITE_VA = 0x401EB3
SYNTHETIC_SITE_OFFSET = 0x1EB3
SYNTHETIC_BLOCK_SIZE = 12


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="module")
def marcx() -> bytes:
    return MARCX.read_bytes()


@pytest.fixture(scope="module")
def repaired() -> tuple[bytes, object]:
    data = MARCX.read_bytes()
    patched, report = repair_capacity_confusion(data)
    assert patched is not None, report.limitations
    return patched, report


def test_fixture_is_the_expected_binary(marcx: bytes) -> None:
    assert _sha(marcx) == MARCX_SHA256
    assert marcx[:4] == b"\x7fELF"


def test_detects_exactly_one_divergent_check(marcx: bytes) -> None:
    sites, limitations = detect_capacity_confusion(marcx)
    assert len(sites) == 1, limitations
    site = sites[0]
    assert site.site_va == SITE_VA
    assert site.file_offset == SITE_FILE_OFFSET
    assert site.block_size == BLOCK_SIZE
    assert site.base_reg == "r15"
    assert site.dst_disp == 4
    assert site.bad_capacity == "ebx"
    assert site.good_capacity == "r12d"
    assert site.source_disp == 8
    assert len(site.sibling_vas) == 2
    assert 0x401F97 in site.sibling_vas  # literal branch
    assert 0x40208A in site.sibling_vas  # fill branch


def test_repair_produces_reviewed_candidate(repaired) -> None:
    patched, report = repaired
    assert report.status == "patched"
    assert report.supported is True
    assert report.mode == "capacity-check"
    assert report.strategy == "capacity"
    assert report.patched_sha256 == PATCHED_SHA256
    assert _sha(patched) == PATCHED_SHA256
    assert len(patched) == len(MARCX.read_bytes())
    assert len(report.actions) == 1
    action = report.actions[0]
    assert action.kind == "capacity_check_rewrite"
    assert action.offset == SITE_FILE_OFFSET
    assert action.size == BLOCK_SIZE
    assert action.before_hex == BEFORE_HEX
    assert action.after_hex == AFTER_HEX
    assert action.site_va == SITE_VA
    assert action.bad_capacity == "ebx"
    assert action.good_capacity == "r12d"
    # The report is JSON-serialisable for the evidence bundle.
    json.dumps(report.to_dict())


def test_patch_changes_only_recorded_regions(repaired) -> None:
    patched, report = repaired
    original = MARCX.read_bytes()
    allowed = [
        (int(action.offset), int(action.size)) for action in report.actions
    ] + [
        (int(item["offset"]), int(item["size"]))
        for item in report.message_actions
    ]
    changed = [
        index
        for index in range(len(original))
        if original[index] != patched[index]
    ]
    assert changed, "patch must change at least one byte"
    for index in changed:
        assert any(start <= index < start + size for start, size in allowed), (
            f"unrecorded change at {index}"
        )
    # Every recorded region changed at least one byte, and nothing else changed.
    for start, size in allowed:
        assert any(start <= index < start + size for index in changed)
    assert len(changed) < sum(size for _, size in allowed)


def test_rewrite_is_the_capacity_check(repaired) -> None:
    patched, _report = repaired
    start = SITE_FILE_OFFSET
    ins = list(Cs(CS_ARCH_X86, CS_MODE_64).disasm(patched[start:start + BLOCK_SIZE], SITE_VA))
    assert [item.mnemonic for item in ins] == ["mov", "sub", "jb", "cmp", "jae", "nop"]
    assert ins[0].op_str == "edi, r12d"  # out_size is the capacity now
    assert ins[1].op_str == "edi, esi"   # out_size - dst_off (underflow-safe)
    assert ins[3].op_str == "edi, edx"   # remaining capacity vs length
    assert ins[5].mnemonic == "nop"


def test_error_message_aligned_to_sibling_wording(repaired) -> None:
    patched, report = repaired
    assert report.message_actions, "span destination message should be aligned"
    action = report.message_actions[0]
    assert action["kind"] == "rodata_message_align"
    assert action["offset"] == MESSAGE_OFFSET
    assert action["string_va"] == MESSAGE_VA
    assert action["old_text"] == "op[%u]: span destination outside the payload pool"
    assert action["new_text"] == "op[%u]: span destination outside the output"
    assert patched[MESSAGE_OFFSET:].startswith(
        report.message_actions[0]["new_text"].encode("ascii") + b"\x00"
    )


def test_second_pass_is_idempotent(repaired) -> None:
    patched, _report = repaired
    sites, _limitations = detect_capacity_confusion(patched)
    assert sites == []
    second, report = repair_capacity_confusion(patched)
    assert second is None
    assert report.status == "unsupported"
    assert report.supported is False


def test_po_manifest_fixture_matches_the_binary() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["fixture_sha256"] == MARCX_SHA256
    assert manifest["format"] == "elf"
    assert manifest["arch"] == "x86_64"
    assert manifest["poc"] and manifest["regression"]
    for case in manifest["poc"] + manifest["regression"]:
        assert isinstance(case.get("argv"), list)
        for fixture in case.get("files", []):
            assert fixture["name"] and isinstance(fixture["base64"], str)


@pytest.mark.parametrize(
    "name",
    ["not-an-elf", "truncated-elf", "pe-rewrite"],
)
def test_fail_closed_on_unsupported_input(name: str) -> None:
    data = {
        "not-an-elf": b"hello world, definitely not ELF",
        "truncated-elf": b"\x7fELF\x02\x01\x01" + b"\x00" * 10,
        "pe-rewrite": b"MZ" + b"\x00" * 0x100,
    }[name]
    patched, report = repair_capacity_confusion(data)
    assert patched is None
    assert report.status == "unsupported"
    assert report.supported is False
    assert report.actions == []


def test_fail_closed_on_other_elf_fixtures() -> None:
    # AArch64 header: rejected before any disassembly.
    arm64 = ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf"
    if arm64.is_file():
        patched, report = repair_capacity_confusion(arm64.read_bytes())
        assert patched is None
        assert report.status == "unsupported"
    # A different x86-64 fixture with no duplicated range checks.
    cwe121 = ROOT / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b" / "original.elf"
    if cwe121.is_file():
        patched, report = repair_capacity_confusion(cwe121.read_bytes())
        assert patched is None
        assert report.status == "unsupported"
        assert report.sites == []


def test_synthetic_compiler_variant_is_repaired() -> None:
    """A second binary (different compiler layout and registers) is repaired."""
    data = SYNTHETIC.read_bytes()
    assert _sha(data) == SYNTHETIC_SHA256
    sites, limitations = detect_capacity_confusion(data)
    assert len(sites) == 1, limitations
    site = sites[0]
    assert site.site_va == SYNTHETIC_SITE_VA
    assert site.file_offset == SYNTHETIC_SITE_OFFSET
    assert site.block_size == SYNTHETIC_BLOCK_SIZE
    assert site.base_reg == "rbx"
    assert site.dst_disp == 4
    assert site.bad_capacity == "ebp"
    assert site.good_capacity == "r12d"
    assert site.source_disp == 8
    patched, report = repair_capacity_confusion(data)
    assert patched is not None, report.limitations
    assert report.status == "patched"
    assert report.patched_sha256 == SYNTHETIC_PATCHED_SHA256
    assert _sha(patched) == SYNTHETIC_PATCHED_SHA256
    assert len(report.actions) == 1
    action = report.actions[0]
    assert action.site_va == SYNTHETIC_SITE_VA
    assert action.size == SYNTHETIC_BLOCK_SIZE
    # The wrong capacity register is replaced by the sibling-consistent one.
    ins = list(Cs(CS_ARCH_X86, CS_MODE_64).disasm(
        patched[SYNTHETIC_SITE_OFFSET:SYNTHETIC_SITE_OFFSET + SYNTHETIC_BLOCK_SIZE],
        SYNTHETIC_SITE_VA,
    ))
    assert ins[0].op_str == "esi, r12d"
    assert ins[1].op_str == "esi, ecx"
    assert ins[3].op_str == "esi, edx"
    assert [item.mnemonic for item in ins] == ["mov", "sub", "jb", "cmp", "jb", "nop"]
    # Idempotent: a second pass must not produce another candidate.
    second, second_report = repair_capacity_confusion(patched)
    assert second is None
    assert second_report.status == "unsupported"
    # The error message is aligned to the sibling destination wording.
    assert report.message_actions
    assert report.message_actions[0]["new_text"] == "span destination outside the output"


def test_synthetic_runtime_differential_when_guest_available(tmp_path) -> None:
    """The synthetic fixture's PoC is rejected and valid archives are unchanged.

    Skipped when no native/qemu/Lima runner exists for x86-64 ELF.
    """
    import base64
    import json
    import subprocess
    import sys

    from app.services.poc_runner import run_poc

    assert (ROOT / "fixtures" / "hard-cases" / "gen_capacity_archives.py").is_file()
    subprocess.run(
        [sys.executable, str(ROOT / "fixtures" / "hard-cases" / "gen_capacity_archives.py"),
         str(tmp_path)],
        check=True,
        capture_output=True,
    )
    data = SYNTHETIC.read_bytes()
    patched, report = repair_capacity_confusion(data)
    assert patched is not None, report.limitations

    files = {
        name: base64.b64encode((tmp_path / name).read_bytes()).decode("ascii")
        for name in sorted(path.name for path in tmp_path.iterdir())
    }

    def case(case_id: str, name: str, original: dict, candidate: dict | None = None) -> dict:
        entry = {
            "id": case_id,
            "files": [{"name": name, "base64": files[name]}],
            "argv": ["{tmp}/" + name],
            "original": original,
        }
        if candidate is not None:
            entry["candidate"] = candidate
        return entry

    manifest = {
        "schema_version": 1,
        "fixture_sha256": SYNTHETIC_SHA256,
        "format": "elf",
        "arch": "x86_64",
        "target": "render",
        "poc": [
            case(
                "poc-overflow", "poc_overflow.marc",
                {"exit_code": 1, "stderr_contains": "output guard corrupt"},
                {"exit_code": 1, "stderr_contains": "span destination outside the output"},
            )
        ],
        "regression": [
            case("benign", "benign.marc", {"exit_code": 0}),
            case("benign-sparse", "benign_sparse.marc", {"exit_code": 0}),
            case("benign-fill", "benign_fill.marc", {"exit_code": 0}),
            case("ctrl-literal-dst-oob", "ctrl_literal_dst_oob.marc",
                 {"exit_code": 1, "stderr_contains": "literal destination outside the output"}),
            case("ctrl-span-src-oob", "ctrl_span_src_oob.marc",
                 {"exit_code": 1, "stderr_contains": "span source outside the payload pool"}),
            case("ctrl-span-no-sparse", "ctrl_span_no_sparse.marc",
                 {"exit_code": 1, "stderr_contains": "span ops require FLAG_SPARSE"}),
            case("ctrl-span-equal-sizes", "ctrl_span_equal_sizes.marc", {"exit_code": 0}),
        ],
    }
    evidence = run_poc(data, patched, manifest)
    if evidence.status == "unavailable":
        pytest.skip(f"no guest runner: {evidence.limitations}")
    assert evidence.status == "pass", (
        evidence.limitations,
        [case.to_dict() for case in evidence.cases + evidence.regression],
    )
    assert evidence.tier in {"native_run", "emulated_run"}
