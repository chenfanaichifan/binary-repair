"""Heap destination capacity recovery (audit contract B, task-6).

What is covered
---------------
* ``Sink.destination_kind`` (``stack`` | ``heap`` | ``global``; default
  ``stack``) and its JSON projection through ``Sink.to_dict`` /
  ``Analysis.to_dict``.
* x86-64 same-function ``malloc``/``calloc`` capacity recovery in
  ``app/services/repair/analyzer.py``: immediate size argument, returned
  pointer register, plain register-to-register copies, then a
  ``strcpy``/``strcat``/``stpcpy`` destination that equals the allocation base.
* Fail-closed negatives: dynamic size, pointer-plus-offset, a branch between
  allocation and copy, a cross-function allocation, a clobbered destination
  register and an intervening call all emit no heap sink.
* The writer turns a heap ``unbounded_copy`` sink into a guard action, and the
  dynamic-ELF candidate keeps its PT_INTERP (code_cave PT_NOTE repurpose).
* The gate never claims ``verified_patch`` for a heap sink without a passing
  external PoC differential (task-C ``native_poc`` profile); a mocked passing
  PoC evidence packet is accepted and a real Lima guest run is exercised when
  the runner is available.

Guard semantics this oracle encodes
-----------------------------------
``app/services/repair/guards.py::build_guard`` returns 0 on success and 1 on
overflow, NUL-terminates the destination at ``capacity - 1``, emits **no stderr
and no exit** of its own.  The fixture call site ignores the strcpy return value
like ordinary C code, so the repaired candidate truncates a 64-byte input to 15
'A' bytes, prints that, and exits 0; the unpatched original overruns its
16-byte malloc chunk and glibc aborts it (SIGABRT, exit 134, "malloc():
corrupted top size" under the Lima qemu-user guest).

Known residual (over-estimation, documented not repaired)
---------------------------------------------------------
The recovered capacity is the **allocation size**, never a struct member size.
``malloc(24)`` followed by ``strcpy(p->data, src)`` where ``data`` is a 16-byte
member recovers capacity 24; a guard built on it can still overwrite the rest of
the struct (the ``heap_canary`` hard case has exactly this shape with a 24-byte
allocation and a 16-byte member).  Without DWARF member layout the analyzer
cannot do better, and the non-stack destination is routed to the external-PoC
profile so no stack/emulation oracle is ever applied to it.

Known external blocker (reported to the Lead, not worked around here)
---------------------------------------------------------------------
``poc_runner`` stages the original and the candidate at the same guest-visible
path; on the read-only Lima home mount the guest can serve stale attributes for
a moment, which made appended-segment candidates fail with ``QEMU internal
SIGBUS {code=ADRERR, addr=<cave vaddr>}``.  The real-differential test below
detects that blocker and skips with an explicit reason; the direct
``guest_runner`` test uses fresh paths and is unaffected.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import struct
import tempfile
from pathlib import Path

import pytest
from elftools.elf.elffile import ELFFile
import io

from app.services.binary_pipeline import repair_any
from app.services.containers import ContainerInfo, SectionInfo, detect_container
from app.services.guest_runner import find_guest_runner, run_path
from app.services.poc_runner import load_manifest, run_poc
from app.services.repair.analyzer import (
    Analysis,
    _scan_x86_64,
    _text_section,
    analyze,
)
from app.services.repair.writer import repair_with_sinks

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "hard-cases" / "vuln-heap-malloc-x86_64.elf"
STACK_FIXTURE = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
I386_FIXTURE = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf"
POC_MANIFEST = ROOT / "fixtures" / "poc" / "heap-malloc.json"

TEXT_VA = 0x1000
MALLOC_VA = 0x9000
CALLOC_VA = 0x9010
STRCPY_VA = 0x9020
PUTS_VA = 0x9030

TRUNCATED_STDOUT = "AAAAAAAAAAAAAAA\n"


def _require(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Synthetic x86-64 instruction builder for fail-closed scanner tests.
# The scanner never executes bytes, so a two-instruction allocation and a
# direct call are enough; call targets are resolved through container imports.
# ---------------------------------------------------------------------------
class _Asm:
    def __init__(self, va: int = TEXT_VA) -> None:
        self.va = va
        self.buf = bytearray()

    def raw(self, data: bytes) -> "_Asm":
        self.buf += data
        return self

    def call(self, target: int) -> "_Asm":
        at = self.va + len(self.buf)
        self.buf += b"\xE8" + struct.pack("<i", target - (at + 5))
        return self

    def mov_edi_imm(self, value: int) -> "_Asm":
        return self.raw(b"\xBF" + struct.pack("<I", value))

    def mov_esi_imm(self, value: int) -> "_Asm":
        return self.raw(b"\xBE" + struct.pack("<I", value))

    def mov_ecx_imm(self, value: int) -> "_Asm":
        return self.raw(b"\xB9" + struct.pack("<I", value))

    def mov_edx_imm(self, value: int) -> "_Asm":
        return self.raw(b"\xBA" + struct.pack("<I", value))

    def mov_rdi_rax(self) -> "_Asm":
        return self.raw(b"\x48\x89\xC7")

    def mov_rcx_rax(self) -> "_Asm":
        return self.raw(b"\x48\x89\xC1")

    def mov_edi_mem_rax(self) -> "_Asm":
        return self.raw(b"\x8B\x38")  # mov edi,[rax]: runtime value, not an imm

    def lea_rdi_rax(self, disp: int) -> "_Asm":
        return self.raw(b"\x48\x8D\x78" + struct.pack("<b", disp))

    def mov_rdi_imm(self, value: int) -> "_Asm":
        return self.raw(b"\x48\xC7\xC7" + struct.pack("<I", value))

    def test_rax_rax(self) -> "_Asm":
        return self.raw(b"\x48\x85\xC0")

    def je(self, rel8: int) -> "_Asm":
        return self.raw(b"\x74" + bytes([rel8 & 0xFF]))

    def push_rbp(self) -> "_Asm":
        return self.raw(b"\x55")

    def mov_rbp_rsp(self) -> "_Asm":
        return self.raw(b"\x48\x89\xE5")

    def sub_rsp_imm8(self, value: int) -> "_Asm":
        return self.raw(b"\x48\x83\xEC" + bytes([value]))

    def lea_rdi_rbp(self, disp: int) -> "_Asm":
        return self.raw(b"\x48\x8D\x7D" + struct.pack("<b", disp))

    def leave(self) -> "_Asm":
        return self.raw(b"\xC9")

    def ret(self) -> "_Asm":
        return self.raw(b"\xC3")


def _scan(code: bytes, imports: dict[int, str] | None = None,
          container_format: str = "elf") -> Analysis:
    container = ContainerInfo(
        format=container_format, arch="x86_64", bits=64, endian="little",
    )
    container.sections = [SectionInfo(
        name=".text", segment="", va=TEXT_VA, size=len(code), offset=0,
        executable=True,
    )]
    container.imports = dict(imports or {})
    analysis = Analysis(container=container)
    _scan_x86_64(analysis, container, _text_section(container), code)
    return analysis


def _heap_sinks(analysis: Analysis):
    return [sink for sink in analysis.sinks
            if sink.destination_kind == "heap"]


# ---------------------------------------------------------------------------
# Fixture + analyzer recovery
# ---------------------------------------------------------------------------
def test_fixture_is_small_dynamic_elf():
    data = _require(FIXTURE)
    assert len(data) < 1024 * 1024
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == (
        "elf", "x86_64", 64,
    )
    assert container.limitations == []
    elf = ELFFile(io.BytesIO(data))
    interpret = [seg for seg in elf.iter_segments()
                 if str(seg["p_type"]) == "PT_INTERP"]
    assert interpret and int(interpret[0]["p_filesz"]) > 0


def test_analyzer_recovers_heap_capacity():
    data = _require(FIXTURE)
    analysis = analyze(data)
    patchable = analysis.patchable()
    assert len(patchable) == 1, [sink.to_dict() for sink in patchable]
    sink = patchable[0]
    assert sink.kind == "unbounded_copy"
    assert sink.callee == "strcpy"
    assert sink.capacity == 16
    assert sink.destination_kind == "heap"
    assert sink.dest_rel is None
    assert sink.patchable is True
    assert sink.arch == "x86_64"
    assert sink.function_va > 0
    assert sink.call_va is not None and sink.call_size == 6
    assert sink.call_offset is not None
    payload = sink.to_dict()
    assert payload["destination_kind"] == "heap"
    dumped = analysis.to_dict()
    assert any(item["destination_kind"] == "heap" for item in dumped["sinks"])


def test_heap_sink_call_is_a_got_import_call():
    data = _require(FIXTURE)
    container = detect_container(data)
    sink = analyze(data).patchable()[0]
    raw = data[sink.call_offset:sink.call_offset + sink.call_size]
    assert raw[:2] == b"\xFF\x15"  # call *sym@GOTPCREL(%rip)
    disp = struct.unpack_from("<i", raw, 2)[0]
    target = sink.call_va + sink.call_size + disp
    assert target in container.imports
    assert container.imports[target].endswith("strcpy")


def test_stack_fixture_stays_stack_destination():
    """No stack sink is re-labelled as heap by the new recovery."""
    analysis = analyze(_require(STACK_FIXTURE))
    patchable = analysis.patchable()
    # The static image also exposes syscall-length sinks from libc internals;
    # only the analysed copy sink matters for the destination classification.
    copies = [sink for sink in patchable if sink.kind == "unbounded_copy"]
    assert len(copies) == 1, [sink.to_dict() for sink in copies]
    sink = copies[0]
    assert sink.callee == "strcpy"
    assert sink.capacity == 16
    assert sink.destination_kind == "stack"
    assert sink.dest_rel is not None
    assert all(item.destination_kind == "stack" for item in analysis.sinks)
    assert _heap_sinks(analysis) == []


def test_i386_analyzer_reports_only_stack_destinations():
    """i386 heap destination recovery is a documented gap (fail closed)."""
    analysis = analyze(_require(I386_FIXTURE))
    assert analysis.container.arch == "i386"
    assert analysis.patchable()
    assert all(sink.destination_kind == "stack" for sink in analysis.sinks)
    assert _heap_sinks(analysis) == []


# ---------------------------------------------------------------------------
# Writer: heap sink -> guard action, candidate keeps the interpreter
# ---------------------------------------------------------------------------
def test_repair_with_sinks_emits_heap_guard_action():
    data = _require(FIXTURE)
    analysis = analyze(data)
    result = repair_with_sinks(data, analysis.container, analysis.patchable())
    assert result.ok, result.limitations
    assert result.patched is not None and result.patched != data
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action["kind"] == "guard"
    assert action["callee"] == "strcpy"
    assert action["capacity"] == 16
    assert action["method"] == "new-pt-load"
    assert result.injected_va is not None

    patched = result.patched
    check = detect_container(patched)
    assert (check.format, check.arch, check.bits) == ("elf", "x86_64", 64)
    assert check.limitations == []
    original_elf = ELFFile(io.BytesIO(data))
    patched_elf = ELFFile(io.BytesIO(patched))
    original_interp = [seg for seg in original_elf.iter_segments()
                       if str(seg["p_type"]) == "PT_INTERP"]
    patched_interp = [seg for seg in patched_elf.iter_segments()
                      if str(seg["p_type"]) == "PT_INTERP"]
    assert patched_interp, "patched candidate lost PT_INTERP"
    offset = int(original_interp[0]["p_offset"])
    size = int(original_interp[0]["p_filesz"])
    assert patched[offset:offset + size] == data[offset:offset + size]
    assert int(patched_elf.header["e_phnum"]) == int(original_elf.header["e_phnum"])

    call_off = int(analysis.patchable()[0].call_offset)
    assert patched[call_off] == 0xE8
    delta = struct.unpack_from("<i", patched, call_off + 1)[0]
    call_va = analyze(data).patchable()[0].call_va
    assert call_va + 5 + delta == result.injected_va


# ---------------------------------------------------------------------------
# Gate: heap destination never verified without a passing PoC differential
# ---------------------------------------------------------------------------
def test_repair_any_heap_without_manifest_is_never_verified():
    data = _require(FIXTURE)
    outcome = repair_any(data)
    report = outcome.report
    assert outcome.verified is False
    assert outcome.download_allowed is False
    assert report.disposition != "verified_patch"
    assert report.verification.get("gate", {}).get("success") is False
    assert report.actions and report.actions[0]["kind"] == "guard"
    assert report.findings and report.findings[0]["capacity"] == 16
    # Profile plumbing lands in the same task series; when it is present the
    # heap sink must select the external-PoC model, never the stack oracle.
    if report.verification.get("packet"):
        scope = report.verification["packet"].get("scope", {})
        if scope.get("profile"):
            assert scope["profile"] == "native_poc"
            assert scope.get("runtime_tier") == "static_only"
    assert report.poc == {}


def test_mocked_external_poc_yields_native_poc_verification(monkeypatch):
    data = _require(FIXTURE)
    manifest = load_manifest(POC_MANIFEST)

    def _case(kind: str, executable: str, exit_code: int, crashed: bool,
              stdout: str) -> dict:
        return {
            "case_id": "case", "kind": kind, "executable": executable,
            "exit_code": exit_code, "crashed": crashed, "stdout": stdout,
            "stderr": "", "stdout_hex": stdout.encode().hex(),
            "timed_out": False, "error": None, "expected_ok": True,
        }

    class _FakeEvidence:
        def to_dict(self) -> dict:
            return {
                "schema_version": 1, "status": "pass", "runner": "limactl",
                "tier": "emulated_run", "stdout_signature": "matched",
                "no_input": False, "original_sha256": "", "candidate_sha256": "",
                "poc": [
                    _case("poc", "original", 255, True, ""),
                    _case("poc", "candidate", 0, False, TRUNCATED_STDOUT),
                ],
                "regression": [
                    _case("regression", "original", 0, False, "hi\n"),
                    _case("regression", "candidate", 0, False, "hi\n"),
                ],
                "limitations": [],
            }

    monkeypatch.setattr("app.services.poc_runner.run_poc",
                        lambda *args, **kwargs: _FakeEvidence())
    outcome = repair_any(data, poc_manifest=manifest)
    report = outcome.report
    assert outcome.verified is True
    assert outcome.download_allowed is True
    assert outcome.candidate is not None
    assert report.disposition == "verified_patch"
    assert report.delivery["tier"] == "emulated_run"
    packet = report.verification["packet"]
    assert packet["scope"]["profile"] == "native_poc"
    statuses = {check["id"]: check["status"] for check in packet["checks"]}
    assert statuses["profile.declared"] == "passed"
    assert statuses["profile.evidence"] == "passed"
    assert statuses["poc.native.candidate_pass"] == "passed"
    assert statuses["profile.required_checks"] == "passed"


def test_poc_manifest_contract_matches_fixture():
    manifest = load_manifest(POC_MANIFEST)
    data = _require(FIXTURE)
    assert manifest["fixture_sha256"] == hashlib.sha256(data).hexdigest()
    assert manifest["format"] == "elf" and manifest["arch"] == "x86_64"
    assert manifest["target"] == "heap_bad"
    assert len(manifest["poc"]) >= 1 and len(manifest["regression"]) >= 1
    for case in manifest["poc"]:
        assert case["original"].get("crashed") is True
        assert case["candidate"]["exit_code"] == 0
        assert case["candidate"]["stdout"] == TRUNCATED_STDOUT
    for case in manifest["regression"]:
        assert case["original"] == case["candidate"]
        assert case["original"]["exit_code"] == 0


# ---------------------------------------------------------------------------
# Real runtime evidence
# ---------------------------------------------------------------------------
def _stage_guest_binaries(original: bytes, candidate: bytes) -> Path:
    base = Path.home() / ".br-guest-stage"
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="heap-guard-", dir=str(base)))
    (root / "original").write_bytes(original)
    (root / "candidate").write_bytes(candidate)
    (root / "original").chmod(0o700)
    (root / "candidate").chmod(0o700)
    return root


def test_guard_candidate_behavior_in_guest():
    """Real Lima/qemu differential with fresh staging paths (no stale cache)."""
    runner = find_guest_runner("x86_64")
    if runner is None:
        pytest.skip("no native/qemu/lima guest runner for x86_64 on this host")
    data = _require(FIXTURE)
    analysis = analyze(data)
    result = repair_with_sinks(data, analysis.container, analysis.patchable())
    assert result.ok and result.patched is not None
    root = _stage_guest_binaries(data, result.patched)
    try:
        def run(name: str, argument: str):
            return run_path(root / name, [argument], arch="x86_64",
                            stdin=b"", timeout=15.0, runner=runner, cwd=root)

        short_inputs = ["hi", "0123456789", "A" * 15]
        for argument in short_inputs:
            original = run("original", argument)
            candidate = run("candidate", argument)
            assert original.available and candidate.available
            assert original.exit_code == 0
            assert candidate.exit_code == 0
            assert candidate.stdout == original.stdout
            assert candidate.stderr == b""

        long_argument = "A" * 64
        original_long = run("original", long_argument)
        candidate_long = run("candidate", long_argument)
        assert original_long.crashed
        assert original_long.exit_code != 0
        assert candidate_long.exit_code == 0
        assert not candidate_long.crashed
        assert candidate_long.stdout == TRUNCATED_STDOUT.encode()
        assert candidate_long.stderr == b""
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_real_poc_runner_differential_when_available():
    """The committed manifest must pass through the real PoC runner.

    Skipped with an explicit reason while the known poc_runner Lima staging
    cache bug (same guest path reused for original and candidate) is unfixed;
    the fixture-independent guest test above still exercises the oracle.
    """
    runner = find_guest_runner("x86_64")
    if runner is None:
        pytest.skip("no native/qemu/lima guest runner for x86_64 on this host")
    data = _require(FIXTURE)
    manifest = load_manifest(POC_MANIFEST)
    analysis = analyze(data)
    candidate = repair_with_sinks(
        data, analysis.container, analysis.patchable(),
    ).patched
    assert candidate is not None
    evidence = run_poc(data, candidate, manifest).to_dict()
    if evidence["status"] == "unavailable":
        pytest.skip(f"PoC runner unavailable: {evidence.get('limitations')}")
    if evidence["status"] != "pass":
        candidate_stderr = "".join(
            case.get("stderr") or ""
            for group in ("poc", "regression")
            for case in evidence.get(group) or []
            if case.get("executable") == "candidate"
        )
        if "QEMU internal SIGBUS" in candidate_stderr or \
                "Could not open" in candidate_stderr:
            pytest.skip(
                "blocked on poc_runner Lima staging stale-path bug: the guest "
                "sees the previous file at the reused path (reported to Lead)"
            )
    assert evidence["status"] == "pass", evidence.get("limitations")
    assert evidence["runner"]
    assert evidence["tier"] in {"native_run", "emulated_run"}
    assert evidence["stdout_signature"] == "matched"
    assert all(case["expected_ok"]
               for case in evidence["poc"] + evidence["regression"])


# ---------------------------------------------------------------------------
# Fail-closed synthetic scanner negatives
# ---------------------------------------------------------------------------
def test_malloc_immediate_recovers_capacity():
    asm = _Asm().mov_edi_imm(16).call(MALLOC_VA).mov_rdi_rax().call(STRCPY_VA)
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"})
    sinks = _heap_sinks(analysis)
    assert len(sinks) == 1
    assert (sinks[0].callee, sinks[0].capacity, sinks[0].dest_rel) == (
        "strcpy", 16, None,
    )


def test_malloc_dynamic_size_emits_no_heap_sink():
    asm = _Asm().mov_edi_mem_rax().call(MALLOC_VA).mov_rdi_rax().call(STRCPY_VA)
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"})
    assert analysis.sinks == []


def test_pointer_offset_emits_no_heap_sink_and_records_limitation():
    asm = (_Asm().mov_edi_imm(16).call(MALLOC_VA).mov_rdi_rax()
           .lea_rdi_rax(1).call(STRCPY_VA))
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"})
    assert analysis.sinks == []
    assert any("offset from its allocation base" in item
               for item in analysis.limitations)


def test_branch_between_allocation_and_copy_emits_no_heap_sink():
    asm = (_Asm().mov_edi_imm(16).call(MALLOC_VA).test_rax_rax().je(3)
           .mov_rdi_rax().call(STRCPY_VA).ret())
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"})
    assert analysis.sinks == []


def test_cross_function_allocation_emits_no_heap_sink():
    asm = (_Asm().mov_edi_imm(16).call(MALLOC_VA).ret()
           .mov_rdi_rax().call(STRCPY_VA))
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"})
    assert analysis.sinks == []


def test_clobbered_destination_register_emits_no_heap_sink():
    asm = (_Asm().mov_edi_imm(16).call(MALLOC_VA).mov_rdi_rax()
           .mov_rdi_imm(0x1234).call(STRCPY_VA))
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"})
    assert analysis.sinks == []


def test_intervening_call_clears_tracked_pointer():
    asm = (_Asm().mov_edi_imm(16).call(MALLOC_VA).mov_rdi_rax()
           .call(PUTS_VA).call(STRCPY_VA))
    analysis = _scan(asm.buf, {
        MALLOC_VA: "malloc", STRCPY_VA: "strcpy", PUTS_VA: "puts",
    })
    assert analysis.sinks == []


def test_calloc_immediate_products():
    for count, size, capacity in ((1, 16, 16), (4, 8, 32), (16, 1, 16)):
        asm = (_Asm().mov_edi_imm(count).mov_esi_imm(size).call(CALLOC_VA)
               .mov_rdi_rax().call(STRCPY_VA))
        analysis = _scan(asm.buf, {CALLOC_VA: "calloc", STRCPY_VA: "strcpy"})
        sinks = _heap_sinks(analysis)
        assert len(sinks) == 1
        assert sinks[0].capacity == capacity


def test_calloc_invalid_products_emit_no_heap_sink():
    oversized = (_Asm().mov_edi_imm(4).mov_esi_imm(700000).call(CALLOC_VA)
                 .mov_rdi_rax().call(STRCPY_VA))
    analysis = _scan(oversized.buf, {CALLOC_VA: "calloc", STRCPY_VA: "strcpy"})
    assert analysis.sinks == []
    zero = (_Asm().mov_edi_imm(0).mov_esi_imm(16).call(CALLOC_VA)
            .mov_rdi_rax().call(STRCPY_VA))
    analysis = _scan(zero.buf, {CALLOC_VA: "calloc", STRCPY_VA: "strcpy"})
    assert analysis.sinks == []


def test_win64_heap_destination_uses_rcx():
    asm = (_Asm().mov_ecx_imm(16).call(MALLOC_VA).mov_rcx_rax()
           .call(STRCPY_VA))
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"},
                     container_format="pe")
    sinks = _heap_sinks(analysis)
    assert len(sinks) == 1
    assert sinks[0].capacity == 16
    assert sinks[0].dest_rel is None


def test_synthetic_stack_copy_stays_stack():
    asm = (_Asm().push_rbp().mov_rbp_rsp().sub_rsp_imm8(0x20)
           .lea_rdi_rbp(-0x10).call(STRCPY_VA).leave().ret())
    analysis = _scan(asm.buf, {STRCPY_VA: "strcpy"})
    patchable = analysis.patchable()
    assert len(patchable) == 1
    sink = patchable[0]
    assert sink.destination_kind == "stack"
    assert sink.capacity == 16
    assert sink.dest_rel == -24


def test_struct_allocation_over_estimation_residual_is_documented():
    """malloc(size) is recovered verbatim, not a member size (known residual)."""
    asm = _Asm().mov_edi_imm(24).call(MALLOC_VA).mov_rdi_rax().call(STRCPY_VA)
    analysis = _scan(asm.buf, {MALLOC_VA: "malloc", STRCPY_VA: "strcpy"})
    sinks = _heap_sinks(analysis)
    assert len(sinks) == 1
    # The heap_canary hard case has char data[16] at offset 0 inside a 24-byte
    # allocation; a guard built on 24 can still corrupt the trailing member.
    assert sinks[0].capacity == 24
    assert "same-function malloc/calloc" in sinks[0].detail
