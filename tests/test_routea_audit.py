"""Independent Gate 3 audit tests against the canonical candidate.

Retargeted M4 tooling (patch review B1-B6): canonical candidate `c4a159…`,
contract `24bfe568…`, `write(2)`/`exit_group` code shape. These tests parse the
real ELF and therefore must run in the guest/CI, never on the host.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.contracts import SecurityContract
from routea.audit import audit_canonical_candidate
from routea.cave import build_cave_patched, plan_route_a_cave
from routea.evidence import run_tool, verify_sha256sums
from routea.facts import header_fields, program_headers
from routea.gate3 import bundle_command

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "fixtures/public/CWE121_src_char_declare_cpy_51b"
ELF = CASE / "original.elf"
CONTRACT_PATH = CASE / "contract.json"
CAVE_ADDR = 0x4018E9
CAVE_SIZE = 1815
GOLDEN_CANDIDATE = "c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82"
GOLDEN_CONTRACT = "24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37"


def contract() -> SecurityContract:
    return SecurityContract.from_dict(json.loads(CONTRACT_PATH.read_text(encoding="utf-8")))


def plan():
    return plan_route_a_cave(ELF, contract(), cave_addr=CAVE_ADDR, cave_size=CAVE_SIZE)


def build(tmp_path: Path) -> tuple[Path, object]:
    candidate = tmp_path / "candidate.elf"
    manifest = build_cave_patched(ELF, plan(), candidate, scope_authorized=True)
    return candidate, manifest


def test_canonical_contract_hash() -> None:
    assert contract().sha256() == GOLDEN_CONTRACT


def test_canonical_candidate_audit_passes(tmp_path: Path) -> None:
    candidate, manifest = build(tmp_path)
    assert manifest.patched_sha256 == GOLDEN_CANDIDATE
    audit = audit_canonical_candidate(ELF, candidate, plan())
    assert audit["pass"] is True, audit["failed"]
    for name in (
        "original_call_is_strcpy_plt",
        "redirect_bytes_written",
        "redirect_target_is_cave",
        "resume_address_after_call",
        "exactly_one_header_changed",
        "rx_end_file_backed",
        "page_congruent",
        "no_overlap_with_next_load",
        "entry_unchanged",
        # review finding B4: the cave starts at the original p_memsz end
        "inside_extended_rx_load",
        "cave_within_extended_memsz",
        "cave_inside_one_page",
        "cave_not_file_backed_before_extension",
        "no_section_covers_cave",
        "no_symbol_in_cave",
        "no_relocation_targets_cave",
        "no_incoming_reference",
        # canonical write(2) code shape (review finding B2)
        "two_syscalls",
        "write_syscall_setup",
        "exit_group_status_1_setup",
        "no_plt_call",
        "no_callee_saved_write",
        "no_stack_write",
        "no_return_instruction",
        "no_indirect_transfer",
        "valid_path_reuses_strcpy",
        "changed_bytes_inside_declared_intervals",
        "candidate_differs_from_original",
    ):
        assert audit["checks"].get(name) is True, name


def test_unpatched_binary_fails_candidate_differs(tmp_path: Path) -> None:
    # review finding B5: no-op diff is not a byte-audit failure; an explicit
    # candidate-differs check must fail for original == patched.
    audit = audit_canonical_candidate(ELF, ELF, plan())
    assert audit["pass"] is False
    assert audit["checks"]["candidate_differs_from_original"] is False
    assert audit["checks"]["redirect_bytes_written"] is False


def test_audit_rejects_undeclared_byte(tmp_path: Path) -> None:
    candidate, _ = build(tmp_path)
    data = bytearray(candidate.read_bytes())
    data[0x1200] ^= 0xFF
    tampered = tmp_path / "tampered-text.elf"
    tampered.write_bytes(bytes(data))
    audit = audit_canonical_candidate(ELF, tampered, plan())
    assert audit["pass"] is False
    assert audit["checks"]["changed_bytes_inside_declared_intervals"] is False


def test_audit_rejects_header_tamper(tmp_path: Path) -> None:
    candidate, manifest = build(tmp_path)
    data = bytearray(candidate.read_bytes())
    fields = header_fields(candidate)
    index = manifest.to_dict()["header_changes"]["rx_load"].get("index")
    if index is None:
        # manifest stores the phdr file offset; map it back through the table
        offset = int(manifest.to_dict()["header_changes"]["rx_load"]["phdr_file_offset"], 16)
        index = (offset - fields["e_phoff"]) // fields["e_phentsize"]
    entry = fields["e_phoff"] + index * fields["e_phentsize"]
    data[entry + 40:entry + 48] = (0x8E9).to_bytes(8, "little")
    tampered = tmp_path / "tampered-header.elf"
    tampered.write_bytes(bytes(data))
    audit = audit_canonical_candidate(ELF, tampered, plan())
    assert audit["pass"] is False
    assert audit["checks"]["rx_end_file_backed"] is False


def test_independent_readelf_view(tmp_path: Path) -> None:
    if not run_tool(["readelf", "--version"])["available"]:
        pytest.skip("readelf unavailable: independent view is required on the VM")
    candidate, _ = build(tmp_path)
    result = run_tool(["readelf", "-lW", str(candidate)])
    assert result["returncode"] == 0
    audit = audit_canonical_candidate(ELF, candidate, plan(), readelf_text=result["stdout"])
    assert audit["checks"]["readelf_matches_elftools_values"] is True
    assert audit["pass"] is True, audit["failed"]


def test_bundle_writes_hashed_static_evidence(tmp_path: Path) -> None:
    outdir = tmp_path / "bundle"
    info = bundle_command(ELF, CONTRACT_PATH, outdir)
    assert info["sha256sums_ok"] is True
    assert verify_sha256sums(outdir) is True
    for name in ("candidate.elf", "original.elf", "edit-manifest.json", "audit.json",
                 "reproducibility.json", "environment.json", "gate3-record.md",
                 "SHA256SUMS", "bundle-sha256.txt"):
        assert (outdir / name).exists(), name
    manifest = json.loads((outdir / "edit-manifest.json").read_text(encoding="utf-8"))
    assert manifest["patched_sha256"] == GOLDEN_CANDIDATE
    states = info["item_states"]
    assert states["2_reproducibility_and_manifest"]["state"] == "measured"
    assert states["4_six_case_run"]["state"] == "not_run"
    assert states["5_isolation_evidence"]["state"] == "not_run"


def test_candidate_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "one.elf"
    second = tmp_path / "two.elf"
    build_cave_patched(ELF, plan(), first, scope_authorized=True)
    build_cave_patched(ELF, plan(), second, scope_authorized=True)
    assert first.read_bytes() == second.read_bytes()
    assert header_fields(first) == header_fields(second)
    assert len(program_headers(first)) == 13
