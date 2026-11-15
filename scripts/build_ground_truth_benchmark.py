#!/usr/bin/env python3
"""Build the Phase-8A ground-truth benchmark manifest (v1).

Reads only committed fixtures/contracts and writes::

    benchmark/phase8-v1/manifest.json   # top-level wrapper + 12 typed samples
    benchmark/phase8-v1/README.md       # deterministic human summary
    benchmark/phase8-v1/SHA256SUMS      # covers the two data files

Ground-truth rules enforced by the builder (fail closed, never fabricate):

* every sample references existing real files; every file's SHA-256 is
  recomputed and recorded; a sample with a missing path is dropped with an
  explicit reason (``dropped_samples``), never replaced by a fake one;
* each sample object is validated against the committed contract
  ``contracts/benchmark-sample.schema.json`` (draft 2020-12,
  ``additionalProperties=false``) with ``jsonschema`` when present - when the
  contract or the library is missing the builder falls back to local field
  validation and records ``schema_integration.status="not_run"`` with a reason;
* semantic contract rules are also enforced: ``analysis_only`` expectations must
  not declare a runtime oracle kind, while ``function``/``whole_program``
  expectations require at least one runtime oracle kind;
* ``hidden_available`` is always false and ``hidden_commitment_sha256`` is
  always null: no hidden set exists in this tree; the limitation is explicit;
* the PoC manifest referenced by a sample is loaded through
  ``app.services.poc_runner.load_manifest`` (schema validation only, no
  execution) and its ``fixture_sha256`` must equal the sample binary SHA-256;
* deterministic output: no wall clock, no network, no git; ``generated_at`` is a
  fixed documented constant.

Usage::

    python scripts/build_ground_truth_benchmark.py            # write
    python scripts/build_ground_truth_benchmark.py --check    # verify committed
    python scripts/build_ground_truth_benchmark.py --json     # summary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCHMARK_DIR = ROOT / "benchmark" / "phase8-v1"
BENCHMARK_DIR_REL = "benchmark/phase8-v1"
MANIFEST_NAME = "manifest.json"
ARTIFACT_FILES = (MANIFEST_NAME, "README.md")
SAMPLE_SCHEMA_PATH = "contracts/benchmark-sample.schema.json"
GENERATED_AT = "2026-11-16T00:00:00Z"
GENERATED_AT_NOTE = (
    "fixed deterministic constant for a reproducible manifest; this is not the "
    "build time and no wall clock is read"
)
SCHEMA_VERSION = 1
KIND = "ground_truth_benchmark"
BENCHMARK_ID = "phase8-v1"
HIDDEN_LIMITATION = (
    "no hidden benchmark split exists in this repository; hidden_available is "
    "always false and hidden_commitment_sha256 is null. No hidden-set claim is "
    "made and no commitment is fabricated."
)
RUNTIME_ORACLE_KINDS = frozenset({"external_poc", "native", "emulated"})
ORACLE_KINDS = frozenset({"external_poc", "native", "emulated", "static"})


class BuildError(RuntimeError):
    """A required fixture/contract is missing or inconsistent."""


# ---------------------------------------------------------------------------
# Curated sample definitions (paths + evidence-based expectations)
# ---------------------------------------------------------------------------
# Every entry is data, not truth by assertion: paths are validated, hashes are
# recomputed, PoC manifests are loaded, and expectations cite committed evidence
# (cases.json / PoC manifest / docs / fixture source comments).
CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "sample_id": "stack-strcpy-x86_64",
        "binary": "fixtures/elf/vuln-strcpy-x86_64.elf",
        "poc": "fixtures/poc/elf-x86_64-strcpy.json",
        "reference_fix": None,
        "vulnerability_class": "CWE-121 stack buffer overflow (unbounded strcpy)",
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": "vuln_copy"},
        "expected_analysis": {
            "root_cause": "unbounded strcpy into a 16-byte stack destination",
            "function": "vuln_copy",
            "sink": "strcpy call into stack buffer",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [
                "bounded copy or length validation before strcpy",
                "valid short input keeps exit code 0",
                "oversized input no longer crashes the process",
            ],
            "reference_fix_available": False,
        },
        "negative_cases": ["short-hi", "boundary-15"],
        "split": "dev",
        "source_refs": [
            "fixtures/elf/vuln-strcpy-x86_64.elf",
            "fixtures/src/vuln_copy_elf_x86_64.S",
            "fixtures/src/main.c",
            "fixtures/poc/elf-x86_64-strcpy.json",
        ],
        "evidence_refs": [
            "fixtures/poc/elf-x86_64-strcpy.json#poc/regression",
            "fixtures/src/vuln_copy_elf_x86_64.S#capacity-comment",
            "fixtures/PROVENANCE.json#fixtures[name=elf-x86_64]",
        ],
        "notes": [
            "no committed reference-fix file exists for this fixture; the PoC "
            "manifest is the oracle and the patch expectations are behavioural",
        ],
    },
    {
        "sample_id": "stack-strcpy-x86",
        "binary": "fixtures/elf/vuln-strcpy-x86.elf",
        "poc": None,
        "reference_fix": None,
        "vulnerability_class": "CWE-121 stack buffer overflow (unbounded strcpy, i386)",
        "expected_scope": "analysis_only",
        "target": {"kind": "analysis_only"},
        "expected_analysis": {
            "root_cause": "unbounded strcpy into a 16-byte stack destination (i386)",
            "function": "vuln_copy",
            "sink": "strcpy call into stack buffer",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [],
            "reference_fix_available": False,
            "verification": "not_claimed",
        },
        "negative_cases": [],
        "split": "validation",
        "source_refs": [
            "fixtures/elf/vuln-strcpy-x86.elf",
            "fixtures/src/vuln_copy_elf32_x86.S",
            "fixtures/src/main.c",
        ],
        "evidence_refs": [
            "fixtures/src/vuln_copy_elf32_x86.S#capacity-comment",
            "fixtures/PROVENANCE.json#fixtures[name=elf-x86]",
        ],
        "notes": [
            "no committed PoC manifest matches this i386 fixture (no "
            "fixture_sha256 match), so no runtime oracle exists; the sample is "
            "retained as analysis-only coverage and must never be promoted to a "
            "verified expectation",
            "the task draft suggested an emulated/static oracle, but the "
            "committed contract forbids runtime oracle kinds for analysis_only "
            "expectations and no emulated oracle runner exists; schema wins",
        ],
    },
    {
        "sample_id": "stack-memcpy-x86",
        "binary": "fixtures/elf/vuln-memcpy-x86.elf",
        "poc": None,
        "reference_fix": None,
        "vulnerability_class": "CWE-121 immediate-length memcpy overflow (i386)",
        "expected_scope": "analysis_only",
        "target": {"kind": "analysis_only"},
        "expected_analysis": {
            "root_cause": "memcpy with immediate length 64 into a 16-byte stack destination (i386)",
            "function": "vuln_copy",
            "sink": "memcpy immediate-length copy into stack buffer",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [],
            "reference_fix_available": False,
            "verification": "not_claimed",
        },
        "negative_cases": [],
        "split": "dev",
        "source_refs": [
            "fixtures/elf/vuln-memcpy-x86.elf",
            "fixtures/src/vuln_memcpy_elf32_x86.S",
            "fixtures/src/main.c",
        ],
        "evidence_refs": [
            "fixtures/src/vuln_memcpy_elf32_x86.S#capacity-comment",
            "fixtures/PROVENANCE.json#fixtures[name=elf-x86-memcpy]",
        ],
        "notes": [
            "no committed PoC manifest matches this i386 fixture, so no runtime "
            "oracle exists; analysis-only coverage, never a verified expectation",
        ],
    },
    {
        "sample_id": "heap-capacity-x86_64",
        "binary": "fixtures/elf/vuln-capacity-confusion-x86_64.elf",
        "poc": "fixtures/poc/marcx-capacity.json",
        "reference_fix": None,
        "vulnerability_class": "CWE-131/697/787 capacity-check confusion (destination validated against payload-pool size)",
        "expected_scope": "function",
        "target": {"kind": "va_range", "va": 0x4020D9, "end": 0x4020E9},
        "expected_analysis": {
            "root_cause": "span destination range is validated against data_size instead of out_size",
            "function": "render",
            "sink": "OP_SPAN destination range check (CWE-131/697/787)",
            "capacity": None,
        },
        "expected_patch_properties": {
            "site_va": "0x4020d9",
            "rewrite_bytes": 16,
            "patched_sha256": "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2",
            "properties": [
                "destination range validated against the output buffer capacity",
                "16-byte in-place rewrite at the reviewed site",
            ],
            "reference_fix_available": False,
            "documented_by": "docs/architecture/capacity-check-repair.md",
        },
        "negative_cases": [
            "benign",
            "benign-sparse",
            "benign-crc",
            "ctrl-span-equal-sizes",
            "ctrl-span-no-sparse",
            "ctrl-span-src-oob",
            "ctrl-literal-dst-oob",
            "bad-crc",
        ],
        "split": "dev",
        "source_refs": [
            "fixtures/elf/vuln-capacity-confusion-x86_64.elf",
            "fixtures/hard-cases/capacity_confusion.c",
            "fixtures/poc/marcx-capacity.json",
        ],
        "evidence_refs": [
            "docs/architecture/capacity-check-repair.md#verified-fix-site",
            "fixtures/poc/marcx-capacity.json#poc/regression",
            "fixtures/hard-cases/capacity_confusion.c#span-check",
        ],
        "notes": [
            "the fixture is stripped, so the target is the reviewed site VA range "
            "from docs/architecture/capacity-check-repair.md (not a symbol claim)",
            "no committed reference-fix file exists; the documented 16-byte rewrite "
            "and patched sha256 are the expected patch properties",
        ],
    },
    {
        "sample_id": "inline-loop",
        "binary": "fixtures/elf/vuln-loop-x86_64.elf",
        "poc": "fixtures/poc/elf-x86_64-loop.json",
        "reference_fix": "fixtures/hard-cases/loop_fix.S",
        "vulnerability_class": "CWE-121 non-template inline byte-copy loop",
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": "vuln_copy"},
        "expected_analysis": {
            "root_cause": "inlined byte-copy loop into a 16-byte stack buffer without a bound",
            "function": "vuln_copy",
            "sink": "inline byte-copy loop",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [
                "copy capped at capacity-1 and NUL-terminated",
                "short/boundary inputs keep exit code 0",
                "oversized input no longer crashes",
            ],
            "reference_fix_available": True,
        },
        "negative_cases": ["loop-short", "loop-boundary"],
        "split": "dev",
        "source_refs": [
            "fixtures/elf/vuln-loop-x86_64.elf",
            "fixtures/src/vuln_copy_loop_x86_64.S",
            "fixtures/poc/elf-x86_64-loop.json",
            "fixtures/hard-cases/loop_fix.S",
        ],
        "evidence_refs": [
            "fixtures/poc/elf-x86_64-loop.json#poc/regression",
            "fixtures/hard-cases/loop_fix.S#bounded-loop",
            "fixtures/src/vuln_copy_loop_x86_64.S#deliberately-not-strcpy",
        ],
        "notes": [
            "hard-case contract is recorded in fixtures/hard-cases/cases.json "
            "(inline-byte-loop, capacity 16, baseline rejected)",
        ],
    },
    {
        "sample_id": "cwe121-public",
        "binary": "fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf",
        "poc": "fixtures/poc/cwe121.json",
        "reference_fix": "fixtures/hard-cases/cwe121_fix.c",
        "vulnerability_class": "CWE-121 stack buffer overflow (unchecked strcpy)",
        "expected_scope": "function",
        "target": {
            "kind": "symbol",
            "symbol": "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink",
        },
        "expected_analysis": {
            "root_cause": "strcpy into char[50] without validating the input length",
            "function": "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink",
            "sink": "strcpy into stack destination",
            "capacity": 50,
        },
        "expected_patch_properties": {
            "properties": [
                "reject inputs with length+1 > 50 (exit 1 with contract stderr)",
                "preserve the valid stdout behaviour",
            ],
            "reference_fix_available": True,
        },
        "negative_cases": ["cwe121-valid-0", "cwe121-valid-1", "cwe121-valid-10", "cwe121-valid-49"],
        "split": "dev",
        "source_refs": [
            "fixtures/public/CWE121_src_char_declare_cpy_51b/original.elf",
            "fixtures/public/CWE121_src_char_declare_cpy_51b/src.c",
            "fixtures/poc/cwe121.json",
            "fixtures/hard-cases/cwe121_fix.c",
        ],
        "evidence_refs": [
            "fixtures/hard-cases/cases.json#cases[id=cwe121-unchecked-strcpy]",
            "fixtures/poc/cwe121.json#poc/regression",
            "fixtures/hard-cases/cwe121_fix.c#length-reject",
        ],
        "notes": [
            "contract: reject length+1>50 with exit 1 and exact stderr; valid "
            "inputs preserved (fixtures/hard-cases/cases.json)",
        ],
    },
    {
        "sample_id": "hard-multicall",
        "binary": "fixtures/hard-cases/vuln-hardcases-c-x86_64.elf",
        "poc": "fixtures/poc/hard-multicall.json",
        "reference_fix": "fixtures/hard-cases/multicall_fix.c",
        "vulnerability_class": "CWE-121 non-template semantic/multi-layer copy",
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": "multicall_bad"},
        "expected_analysis": {
            "root_cause": "input copied into a 16-byte destination through a non-template path",
            "function": "multicall_bad",
            "sink": "semantic/multi-layer copy",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [
                "reject inputs that do not fit the 16-byte destination",
                "preserve normal short-input behaviour",
            ],
            "reference_fix_available": True,
        },
        "negative_cases": ["multicall-short"],
        "split": "dev",
        "source_refs": [
            "fixtures/hard-cases/vuln-hardcases-c-x86_64.elf",
            "fixtures/hard-cases/hard_cases.c",
            "fixtures/poc/hard-multicall.json",
            "fixtures/hard-cases/multicall_fix.c",
        ],
        "evidence_refs": [
            "fixtures/hard-cases/cases.json#cases[id=hard-multicall]",
            "fixtures/poc/hard-multicall.json#poc/regression",
            "fixtures/hard-cases/multicall_fix.c#length-reject",
        ],
        "notes": [
            "hard-case contract recorded in fixtures/hard-cases/cases.json "
            "(hard-multicall, capacity 16, baseline rejected)",
        ],
    },
    {
        "sample_id": "hard-sprintf",
        "binary": "fixtures/hard-cases/vuln-hardcases-c-x86_64.elf",
        "poc": "fixtures/poc/hard-sprintf.json",
        "reference_fix": "fixtures/hard-cases/sprintf_fix.c",
        "vulnerability_class": "CWE-121 non-template sprintf/format expansion path",
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": "sprintf_bad"},
        "expected_analysis": {
            "root_cause": "input copied into a 16-byte destination through a non-template sprintf path",
            "function": "sprintf_bad",
            "sink": "sprintf/format expansion copy",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [
                "reject inputs that do not fit the 16-byte destination",
                "preserve normal short-input behaviour",
            ],
            "reference_fix_available": True,
        },
        "negative_cases": ["sprintf-short"],
        "split": "validation",
        "source_refs": [
            "fixtures/hard-cases/vuln-hardcases-c-x86_64.elf",
            "fixtures/hard-cases/hard_cases.c",
            "fixtures/poc/hard-sprintf.json",
            "fixtures/hard-cases/sprintf_fix.c",
        ],
        "evidence_refs": [
            "fixtures/hard-cases/cases.json#cases[id=hard-sprintf]",
            "fixtures/poc/hard-sprintf.json#poc/regression",
            "fixtures/hard-cases/sprintf_fix.c#length-reject",
        ],
        "notes": [
            "hard-case contract recorded in fixtures/hard-cases/cases.json "
            "(hard-sprintf, capacity 16, baseline rejected)",
        ],
    },
    {
        "sample_id": "hard-nonconst",
        "binary": "fixtures/hard-cases/vuln-hardcases-c-x86_64.elf",
        "poc": "fixtures/poc/hard-nonconst.json",
        "reference_fix": "fixtures/hard-cases/nonconst_fix.c",
        "vulnerability_class": "CWE-121 non-constant-length copy",
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": "nonconst_bad"},
        "expected_analysis": {
            "root_cause": "input copied into a 16-byte destination with non-constant length",
            "function": "nonconst_bad",
            "sink": "non-constant-length copy",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [
                "reject inputs that do not fit the 16-byte destination",
                "preserve normal short-input behaviour",
            ],
            "reference_fix_available": True,
        },
        "negative_cases": ["nonconst-short"],
        "split": "validation",
        "source_refs": [
            "fixtures/hard-cases/vuln-hardcases-c-x86_64.elf",
            "fixtures/hard-cases/hard_cases.c",
            "fixtures/poc/hard-nonconst.json",
            "fixtures/hard-cases/nonconst_fix.c",
        ],
        "evidence_refs": [
            "fixtures/hard-cases/cases.json#cases[id=hard-nonconst]",
            "fixtures/poc/hard-nonconst.json#poc/regression",
            "fixtures/hard-cases/nonconst_fix.c#length-reject",
        ],
        "notes": [
            "hard-case contract recorded in fixtures/hard-cases/cases.json "
            "(hard-nonconst, capacity 16, baseline rejected)",
        ],
    },
    {
        "sample_id": "uaf-noinput",
        "binary": "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf",
        "poc": "fixtures/poc/cwe416.json",
        "reference_fix": "fixtures/hard-cases/uaf_fix.c",
        "vulnerability_class": "CWE-416 use-after-free (heap lifetime)",
        "expected_scope": "analysis_only",
        "target": {"kind": "analysis_only"},
        "expected_analysis": {
            "root_cause": "read of a heap block after free() (use-after-free)",
            "function": "CWE416_Use_After_Free__malloc_free_char_01_bad",
            "sink": "use-after-free heap read",
            "capacity": 100,
        },
        "expected_patch_properties": {
            "properties": [],
            "reference_fix_available": True,
            "verification": "not_claimed",
        },
        "negative_cases": [],
        "split": "dev",
        "source_refs": [
            "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/original.elf",
            "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/src.c",
            "fixtures/hard-cases/uaf_fix.c",
        ],
        "evidence_refs": [
            "fixtures/hard-cases/cases.json#cases[id=uaf-noinput]",
            "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json",
            "fixtures/hard-cases/uaf_fix.c#read-before-free",
        ],
        "notes": [
            "expected baseline is analysis_only (fixtures/hard-cases/cases.json); "
            "the committed task expects no verified claim for this class",
            "the sample keeps its PoC manifest in the benchmark for reference, but "
            "the oracle declaration is static because the expectation is "
            "analysis_only (contract forbids runtime oracle kinds here)",
        ],
    },
    {
        "sample_id": "heap-canary",
        "binary": "fixtures/hard-cases/vuln-heap-canary-x86_64.elf",
        "poc": "fixtures/poc/heap-canary.json",
        "reference_fix": "fixtures/hard-cases/heap_canary_fix.c",
        "vulnerability_class": "CWE-121 heap buffer overflow / guard corruption",
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": "heap_bad"},
        "expected_analysis": {
            "root_cause": "unbounded copy into a 16-byte heap buffer followed by a guard word",
            "function": "heap_bad",
            "sink": "heap buffer copy / guard corruption",
            "capacity": 16,
        },
        "expected_patch_properties": {
            "properties": [
                "reject oversized input before the copy (guard not corrupted)",
                "preserve normal short-input behaviour",
            ],
            "reference_fix_available": True,
        },
        "negative_cases": ["heap-short"],
        "split": "validation",
        "source_refs": [
            "fixtures/hard-cases/vuln-heap-canary-x86_64.elf",
            "fixtures/hard-cases/heap_canary.c",
            "fixtures/poc/heap-canary.json",
            "fixtures/hard-cases/heap_canary_fix.c",
        ],
        "evidence_refs": [
            "fixtures/hard-cases/cases.json#cases[id=heap-canary]",
            "fixtures/poc/heap-canary.json#poc/regression",
            "fixtures/hard-cases/heap_canary_fix.c#capacity-reject",
        ],
        "notes": [
            "hard-case contract recorded in fixtures/hard-cases/cases.json "
            "(heap-canary, capacity 16, baseline rejected)",
        ],
    },
    {
        "sample_id": "negative-control",
        "binary": "fixtures/pe/i386-control.exe",
        "poc": None,
        "reference_fix": None,
        "vulnerability_class": "none (negative control: out-of-matrix PE/i386)",
        "expected_scope": "analysis_only",
        "target": {"kind": "analysis_only"},
        "expected_analysis": {
            "root_cause": None,
            "function": None,
            "sink": None,
            "capacity": None,
        },
        "expected_patch_properties": {
            "properties": [],
            "reference_fix_available": False,
            "verification": "not_claimed",
            "expected": "no vulnerability claim and no verified candidate",
        },
        "negative_cases": [],
        "split": "dev",
        "source_refs": [
            "fixtures/pe/i386-control.exe",
            "fixtures/src/control_i386.c",
        ],
        "evidence_refs": [
            "fixtures/PROVENANCE.json#fixtures[name=pe-i386-control]",
            "fixtures/src/control_i386.c#negative-control-comment",
        ],
        "notes": [
            "negative control selected from the fixture set: the committed "
            "PE/i386 control fixture (fixtures/pe/i386-control.exe) is explicitly "
            "outside the repair matrix; the pipeline must report unsupported / "
            "analysis-only and never write a verified candidate",
        ],
    },
)


# ---------------------------------------------------------------------------
# Byte-level sample identity helpers
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    return _sha256_bytes(path.read_bytes())


def _read_bytes(relative: str) -> bytes:
    path = ROOT / relative
    if not path.is_file():
        raise BuildError(f"missing fixture file: {relative}")
    return path.read_bytes()


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, count: int) -> bytes:
        chunk = self.data[self.offset:self.offset + count]
        if len(chunk) != count:
            raise BuildError("truncated container header")
        self.offset += count
        return chunk

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]


def inspect_container(relative: str) -> dict[str, Any]:
    """Derive format/arch/bits/endian from the real container bytes."""
    data = _read_bytes(relative)
    if data[:4] == b"\x7fELF":
        if len(data) < 20:
            raise BuildError(f"truncated ELF: {relative}")
        ei_class = data[4]
        ei_data = data[5]
        e_machine = struct.unpack_from("<H", data, 18)[0]
        bits = 32 if ei_class == 1 else 64 if ei_class == 2 else 0
        endian = "little" if ei_data == 1 else "big" if ei_data == 2 else "unknown"
        arch = {0x3E: "x86_64", 0x03: "i386", 0xB7: "arm64"}.get(e_machine)
        if not arch or not bits or endian not in {"little", "big"}:
            raise BuildError(f"unsupported ELF identity for {relative}")
        return {"format": "elf", "arch": arch, "bits": bits, "endian": endian}
    if data[:2] == b"MZ":
        reader = _Reader(data)
        reader.take(2)
        reader.offset = 0x3C
        pe_offset = reader.u32()
        if data[pe_offset:pe_offset + 4] != b"PE\x00\x00":
            raise BuildError(f"invalid PE header: {relative}")
        reader.offset = pe_offset + 4
        machine = reader.u16()
        reader.take(2)      # NumberOfSections
        reader.take(4)      # TimeDateStamp
        reader.take(4)      # PointerToSymbolTable
        reader.take(4)      # NumberOfSymbols
        reader.take(2)      # SizeOfOptionalHeader
        reader.take(2)      # Characteristics
        opt_magic = reader.u16()
        arch = {0x014C: "i386", 0x8664: "x86_64", 0xAA64: "arm64"}.get(machine)
        bits = 32 if opt_magic == 0x10B else 64 if opt_magic == 0x20B else 0
        if not arch or not bits:
            raise BuildError(f"unsupported PE identity for {relative}")
        return {"format": "pe", "arch": arch, "bits": bits, "endian": "little"}
    raise BuildError(f"unrecognised container format: {relative}")


# ---------------------------------------------------------------------------
# PoC / reference / metadata loading
# ---------------------------------------------------------------------------


def _load_poc(relative: str | None) -> dict[str, Any] | None:
    if not relative:
        return None
    path = ROOT / relative
    if not path.is_file():
        raise BuildError(f"missing PoC manifest: {relative}")
    from app.services.poc_runner import load_manifest  # local import: no execution

    manifest = load_manifest(path)  # schema validation only, no PoC execution
    if not isinstance(manifest, dict):
        raise BuildError(f"PoC manifest is not an object: {relative}")
    return manifest


def _poc_identity(manifest: dict[str, Any], binary_sha256: str, sample_id: str) -> None:
    if manifest.get("fixture_sha256") != binary_sha256:
        raise BuildError(
            f"{sample_id}: PoC manifest fixture_sha256 does not match the binary "
            f"({manifest.get('fixture_sha256')} != {binary_sha256})"
        )


def _expected_string(case: dict[str, Any]) -> str:
    return json.dumps(case, sort_keys=True, separators=(",", ":"))


def _expected_from_poc(manifest: dict[str, Any], key: str) -> str | None:
    cases = manifest.get("poc") or []
    if not cases:
        return None
    value = cases[0].get(key)
    if value is None:
        return None
    return _expected_string(value)


def _negative_cases(manifest: dict[str, Any] | None) -> list[str]:
    if not manifest:
        return []
    ids = [str(case.get("id")) for case in (manifest.get("regression") or [])
           if case.get("id")]
    return ids


def _fixture_metadata() -> dict[str, Any]:
    """Committed fixture provenance (tool/command) where recorded."""
    provenance = json.loads((ROOT / "fixtures/PROVENANCE.json").read_text(encoding="utf-8"))
    return {
        str(entry.get("path")): {
            "tool": entry.get("tool") or None,
            "command": entry.get("command") or None,
            "source_sha256": entry.get("source_sha256") or {},
        }
        for entry in provenance.get("fixtures") or []
    }


def _environment_metadata(relative: str, provenance: dict[str, Any]) -> dict[str, Any]:
    entry = provenance.get(relative)
    if not entry or not entry.get("tool"):
        return {
            "compiler": None,
            "compiler_unavailable_reason": (
                "compiler toolchain is not recorded in committed metadata for this "
                "fixture; not guessed"
            ),
            "opt": None,
            "opt_unavailable_reason": (
                "optimization level is not recorded in committed metadata for this "
                "fixture (the toolchain command may exist but no -O level is "
                "asserted); not guessed"
            ),
        }
    command = entry.get("command") or []
    opt = None
    for token in command:
        if isinstance(token, str) and token.startswith("-O"):
            opt = token
            break
    return {
        "compiler": entry["tool"],
        "compiler_unavailable_reason": None,
        "opt": opt,
        "opt_unavailable_reason": (
            None if opt else
            "the recorded toolchain command does not contain an explicit -O level; not guessed"
        ),
    }


# ---------------------------------------------------------------------------
# Sample assembly / validation
# ---------------------------------------------------------------------------


def _build_sample(candidate: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any] | None:
    """Assemble one schema-shaped sample; return None (and reason) if missing."""
    binary = candidate["binary"]
    if not (ROOT / binary).is_file():
        return None
    identity = inspect_container(binary)
    binary_sha256 = _sha256_file(binary)
    poc = _load_poc(candidate.get("poc"))
    if poc is not None:
        _poc_identity(poc, binary_sha256, candidate["sample_id"])
    for path in candidate.get("source_refs", []):
        if not (ROOT / path).is_file():
            raise BuildError(f"{candidate['sample_id']}: missing source_ref {path}")
    reference_fix = candidate.get("reference_fix")
    if reference_fix and not (ROOT / reference_fix).is_file():
        raise BuildError(f"{candidate['sample_id']}: missing reference fix {reference_fix}")
    scope = candidate["expected_scope"]
    oracle_kinds = ["external_poc"] if poc is not None and scope != "analysis_only" else ["static"]
    if scope == "analysis_only" and poc is not None:
        # The PoC manifest may stay as a reference in source_refs but the oracle
        # declaration is static: an analysis_only expectation cannot claim a
        # runtime oracle under the committed contract.
        oracle_kinds = ["static"]
    oracle = {
        "kinds": oracle_kinds,
        "manifest_path": candidate.get("poc") if "external_poc" in oracle_kinds else None,
        "expected_original": (
            _expected_from_poc(poc, "original") if "external_poc" in oracle_kinds else None
        ),
        "expected_candidate": (
            _expected_from_poc(poc, "candidate") if "external_poc" in oracle_kinds else None
        ),
    }
    sample = {
        "sample_id": candidate["sample_id"],
        "sha256": binary_sha256,
        "format": identity["format"],
        "arch": identity["arch"],
        "bits": identity["bits"],
        "endian": identity["endian"],
        "vulnerability_class": candidate["vulnerability_class"],
        "expected_scope": scope,
        "target": dict(candidate["target"]),
        "source_refs": list(candidate["source_refs"]),
        "oracle": oracle,
        "expected_analysis": dict(candidate["expected_analysis"]),
        "reference_fix": reference_fix,
        "expected_patch_properties": dict(candidate["expected_patch_properties"]),
        "negative_cases": list(candidate.get("negative_cases") or []),
        "split": candidate["split"],
        "hidden_available": False,
        "hidden_commitment_sha256": None,
        "evidence_refs": list(candidate["evidence_refs"]),
    }
    return sample


def _sample_semantic_violations(sample: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    scope = sample.get("expected_scope")
    kinds = list((sample.get("oracle") or {}).get("kinds") or [])
    runtime = set(kinds) & RUNTIME_ORACLE_KINDS
    if scope == "analysis_only" and runtime:
        violations.append(
            f"{sample.get('sample_id')}: analysis_only declares runtime oracle kinds {sorted(runtime)}"
        )
    if scope in {"function", "whole_program"} and not runtime:
        violations.append(
            f"{sample.get('sample_id')}: {scope} requires at least one runtime oracle kind"
        )
    if sample.get("hidden_available") is not False:
        violations.append(f"{sample.get('sample_id')}: hidden_available must be false")
    if sample.get("hidden_commitment_sha256") is not None:
        violations.append(f"{sample.get('sample_id')}: hidden_commitment_sha256 must be null")
    if not sample.get("evidence_refs"):
        violations.append(f"{sample.get('sample_id')}: evidence_refs empty")
    return violations


def _load_sample_schema() -> tuple[dict[str, Any] | None, str]:
    path = ROOT / SAMPLE_SCHEMA_PATH
    if not path.is_file():
        return None, "contracts/benchmark-sample.schema.json is absent"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None, "contracts/benchmark-sample.schema.json is not an object"
    return payload, ""


def validate_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate every sample against the committed contract + semantic rules."""
    schema, schema_error = _load_sample_schema()
    integration: dict[str, Any] = {
        "status": "not_run",
        "schema_path": SAMPLE_SCHEMA_PATH,
        "schema_sha256": None,
        "validator": None,
        "reason": schema_error or "schema not validated",
    }
    violations: list[str] = []
    schema_path = ROOT / SAMPLE_SCHEMA_PATH
    if schema is not None:
        integration["schema_sha256"] = _sha256_file(SAMPLE_SCHEMA_PATH)
        try:
            import jsonschema  # type: ignore[import-untyped]

            validator = jsonschema.Draft202012Validator(schema)
            for sample in samples:
                errors = sorted(validator.iter_errors(sample), key=str)
                for error in errors:
                    where = "/".join(str(part) for part in error.absolute_path) or "<root>"
                    violations.append(
                        f"{sample.get('sample_id')}: schema at {where}: {error.message}"
                    )
            integration["status"] = "validated"
            integration["validator"] = f"jsonschema {getattr(jsonschema, '__version__', 'unknown')}"
            integration["reason"] = None
        except ImportError:
            local = _validate_locally(samples)
            violations.extend(local)
            integration["status"] = "validated_local_fallback"
            integration["validator"] = "local-field-validation"
            integration["reason"] = (
                "jsonschema is not installed in this environment; the builder "
                "validated the local reproduction of the committed contract"
            )
    else:
        violations.extend(_validate_locally(samples))
    for sample in samples:
        violations.extend(_sample_semantic_violations(sample))
    integration["checked_samples"] = len(samples)
    integration["violations"] = list(violations)
    return {"ok": not violations, "violations": violations, "schema_integration": integration}


def _validate_locally(samples: list[dict[str, Any]]) -> list[str]:
    """Minimal local mirror of benchmark-sample.schema.json (fallback only)."""
    violations: list[str] = []
    required = {
        "sample_id", "sha256", "format", "arch", "bits", "endian",
        "vulnerability_class", "expected_scope", "target", "source_refs",
        "oracle", "expected_analysis", "reference_fix",
        "expected_patch_properties", "negative_cases", "split",
        "hidden_available", "hidden_commitment_sha256", "evidence_refs",
    }
    for sample in samples:
        label = sample.get("sample_id", "<unknown>")
        missing = required - set(sample)
        extra = set(sample) - required
        if missing:
            violations.append(f"{label}: missing fields {sorted(missing)}")
        if extra:
            violations.append(f"{label}: unexpected fields {sorted(extra)}")
        if not isinstance(sample.get("sha256"), str) or len(sample["sha256"]) != 64:
            violations.append(f"{label}: sha256 must be 64 hex chars")
        if sample.get("format") not in {"elf", "macho", "pe"}:
            violations.append(f"{label}: invalid format")
        if sample.get("arch") not in {"x86_64", "i386", "arm64"}:
            violations.append(f"{label}: invalid arch")
        if sample.get("bits") not in {32, 64}:
            violations.append(f"{label}: invalid bits")
        if sample.get("endian") not in {"little", "big"}:
            violations.append(f"{label}: invalid endian")
        if not str(sample.get("vulnerability_class") or "").strip():
            violations.append(f"{label}: empty vulnerability_class")
        if sample.get("expected_scope") not in {"function", "whole_program", "analysis_only"}:
            violations.append(f"{label}: invalid expected_scope")
        if sample.get("split") not in {"dev", "validation"}:
            violations.append(f"{label}: invalid split")
        target = sample.get("target")
        if not isinstance(target, dict) or target.get("kind") not in {
            "function", "symbol", "va_range", "whole_image", "analysis_only",
        }:
            violations.append(f"{label}: invalid target")
        oracle = sample.get("oracle")
        if not isinstance(oracle, dict):
            violations.append(f"{label}: oracle must be an object")
        else:
            kinds = oracle.get("kinds")
            if (
                not isinstance(kinds, list) or not kinds or len(set(kinds)) != len(kinds)
                or not set(kinds) <= ORACLE_KINDS
            ):
                violations.append(f"{label}: invalid oracle.kinds")
        analysis = sample.get("expected_analysis")
        if not isinstance(analysis, dict) or set(analysis) != {
            "root_cause", "function", "sink", "capacity",
        }:
            violations.append(f"{label}: invalid expected_analysis")
        if not isinstance(sample.get("expected_patch_properties"), dict):
            violations.append(f"{label}: expected_patch_properties must be an object")
        if not isinstance(sample.get("negative_cases"), list):
            violations.append(f"{label}: negative_cases must be a list")
        for field in ("source_refs", "evidence_refs"):
            refs = sample.get(field)
            if not isinstance(refs, list) or not refs or not all(
                isinstance(ref, str) and ref.strip() for ref in refs
            ):
                violations.append(f"{label}: {field} must be a non-empty string list")
        if sample.get("hidden_available") is not False:
            violations.append(f"{label}: hidden_available must be false")
        commitment = sample.get("hidden_commitment_sha256")
        if commitment is not None and (
            not isinstance(commitment, str) or len(commitment) != 64
        ):
            violations.append(f"{label}: invalid hidden_commitment_sha256")
    return violations


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------


def build_manifest() -> dict[str, Any]:
    provenance = _fixture_metadata()
    samples: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    environment: dict[str, Any] = {}
    notes: dict[str, list[str]] = {}
    for candidate in CANDIDATES:
        try:
            sample = _build_sample(candidate, provenance)
        except (FileNotFoundError, BuildError) as exc:
            dropped.append({
                "sample_id": candidate["sample_id"],
                "reason": str(exc),
                "paths": [path for path in [candidate.get("binary"), candidate.get("poc")]
                          if path],
            })
            continue
        if sample is None:
            dropped.append({
                "sample_id": candidate["sample_id"],
                "reason": f"missing required fixture: {candidate.get('binary')}",
                "paths": [candidate.get("binary")],
            })
            continue
        samples.append(sample)
        environment[sample["sample_id"]] = _environment_metadata(
            candidate["binary"], provenance
        )
        notes[sample["sample_id"]] = list(candidate.get("notes") or [])
    samples.sort(key=lambda sample: sample["sample_id"])
    split_map: dict[str, list[str]] = {"dev": [], "validation": []}
    for sample in samples:
        split_map[sample["split"]].append(sample["sample_id"])
    for split in split_map:
        split_map[split].sort()
    validation = validate_samples(samples)
    if not validation["ok"]:
        raise BuildError(f"sample contract validation failed: {validation['violations']}")
    if len(samples) < 10:
        raise BuildError(f"only {len(samples)} valid samples (<10 required)")
    if len({sample["sample_id"] for sample in samples}) != len(samples):
        raise BuildError("duplicate sample_id in manifest")
    if not split_map["dev"] or not split_map["validation"]:
        raise BuildError("both dev and validation splits must be non-empty")
    if any(str(sample["hidden_available"]).lower() != "false" for sample in samples):
        raise BuildError("hidden_available must be false for every sample")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "benchmark_id": BENCHMARK_ID,
        "generated_at": GENERATED_AT,
        "generated_at_note": GENERATED_AT_NOTE,
        "hidden_available": False,
        "hidden_commitment_sha256": None,
        "hidden_limitation": HIDDEN_LIMITATION,
        "sample_count": len(samples),
        "split_counts": {split: len(ids) for split, ids in split_map.items()},
        "splits": split_map,
        "schema_integration": validation["schema_integration"],
        "dropped_samples": dropped,
        "environment_metadata": environment,
        "sample_notes": notes,
        "samples": samples,
        "provenance": {
            "builder": "scripts/build_ground_truth_benchmark.py",
            "build_method": (
                "deterministic assembly from committed fixtures/contracts; real "
                "SHA-256 recomputation; PoC manifests schema-loaded but not "
                "executed; no network, no git commands, no wall clock"
            ),
            "fixture_sources": [
                "fixtures/PROVENANCE.json",
                "fixtures/hard-cases/cases.json",
                SAMPLE_SCHEMA_PATH,
            ],
            "source_digest_sha256": _sha256_bytes(
                json.dumps(
                    {
                        "poc": {
                            candidate["sample_id"]: _sha256_file(candidate["poc"])
                            for candidate in CANDIDATES if candidate.get("poc")
                        },
                        "binaries": {
                            candidate["sample_id"]: _sha256_file(candidate["binary"])
                            for candidate in CANDIDATES
                            if (ROOT / candidate["binary"]).is_file()
                        },
                        "schema": _sha256_file(SAMPLE_SCHEMA_PATH)
                        if (ROOT / SAMPLE_SCHEMA_PATH).is_file() else None,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
        },
        "limitations": [
            "12 candidate samples; samples with insufficient oracle evidence are "
            "declared analysis_only and are never promoted to a verified expectation.",
            "two i386 fixtures have no committed matching PoC manifest; they are "
            "retained as analysis-only coverage (explicitly noted per sample).",
            "no hidden split exists; hidden_available=false and "
            "hidden_commitment_sha256=null, with an explicit limitation.",
            "the benchmark measures deterministic repair readiness only; it does "
            "not call an AI provider or the network.",
            "reference_fix is null where no committed reference-fix file exists; "
            "expected patch properties are behavioural/documented instead.",
        ],
    }
    return manifest


# ---------------------------------------------------------------------------
# README / SHA256SUMS
# ---------------------------------------------------------------------------


def render_sha256sums(files: dict[str, bytes]) -> bytes:
    lines = [f"{_sha256_bytes(files[name])}  {name}" for name in ARTIFACT_FILES]
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_readme(manifest: dict[str, Any]) -> str:
    integration = manifest["schema_integration"]
    lines: list[str] = [
        "# Ground-truth benchmark v1 (Phase-8A)",
        "",
        "Generated deterministically by `scripts/build_ground_truth_benchmark.py`",
        "from committed fixtures and contracts. No network, no git commands, no",
        "wall clock, and PoC manifests are loaded for schema validation only (never",
        "executed by the builder).",
        "",
        f"- benchmark_id: `{manifest['benchmark_id']}`",
        f"- generated_at: `{manifest['generated_at']}` ({manifest['generated_at_note']})",
        f"- samples: {manifest['sample_count']} "
        f"(dev {manifest['split_counts']['dev']}, "
        f"validation {manifest['split_counts']['validation']})",
        f"- hidden split: available={manifest['hidden_available']}, "
        f"commitment={manifest['hidden_commitment_sha256']}; "
        f"{manifest['hidden_limitation']}",
        f"- sample contract: `{SAMPLE_SCHEMA_PATH}` -> "
        f"status=`{integration['status']}`, validator=`{integration['validator']}`",
        "",
        "Artifact files: `manifest.json` (wrapper + typed samples), `README.md`",
        "(this file), `SHA256SUMS` (covers both; never itself).",
        "",
        "## Samples",
        "",
        "| sample_id | split | scope | format/arch | class | target | oracle | reference fix |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sample in manifest["samples"]:
        target = sample["target"]
        if target.get("kind") in {"symbol", "function"}:
            target_text = target.get("symbol") or target.get("function") or "-"
        elif target.get("kind") == "va_range":
            target_text = f"va_range {target.get('va')}..{target.get('end')}"
        else:
            target_text = target["kind"]
        oracle = ", ".join(sample["oracle"]["kinds"])
        reference = sample["reference_fix"] or "(none)"
        lines.append(
            f"| `{sample['sample_id']}` | {sample['split']} | "
            f"{sample['expected_scope']} | {sample['format']}/{sample['arch']}/"
            f"{sample['bits']} | {sample['vulnerability_class']} | "
            f"{target_text} | {oracle} | `{reference}` |"
        )
    lines += [
        "",
        "## Per-sample ground-truth details",
        "",
    ]
    for sample in manifest["samples"]:
        analysis = sample["expected_analysis"]
        lines += [
            f"### {sample['sample_id']}",
            "",
            f"- binary: `{sample['source_refs'][0]}` sha256 `{sample['sha256']}`",
            f"- expected analysis: root_cause=`{analysis['root_cause']}`, "
            f"function=`{analysis['function']}`, sink=`{analysis['sink']}`, "
            f"capacity={analysis['capacity']}",
            f"- oracle: kinds={sample['oracle']['kinds']}, "
            f"manifest_path={sample['oracle']['manifest_path']}",
            f"- expected_original: {sample['oracle']['expected_original']}",
            f"- expected_candidate: {sample['oracle']['expected_candidate']}",
            f"- negative cases: {sample['negative_cases']}",
            f"- evidence: {sample['evidence_refs']}",
        ]
        notes = manifest["sample_notes"].get(sample["sample_id"]) or []
        lines.extend(f"- note: {note}" for note in notes)
        lines.append("")
    lines += [
        "## Validation",
        "",
        "```bash",
        "python scripts/build_ground_truth_benchmark.py --check",
        "python -m pytest -q tests/test_ground_truth_benchmark.py",
        "```",
        "",
        "`--check` rebuilds the manifest in memory, compares `manifest.json`, "
        "`README.md` and `SHA256SUMS` byte-for-byte, re-validates every sample "
        "against the committed contract and the semantic oracle rules, and exits "
        "1 on any mismatch.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in manifest["limitations"])
    if manifest["dropped_samples"]:
        lines += ["", "## Dropped samples (missing evidence)", ""]
        for item in manifest["dropped_samples"]:
            lines.append(f"- `{item['sample_id']}`: {item['reason']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Build / check API
# ---------------------------------------------------------------------------


def build_artifact() -> dict[str, bytes]:
    manifest = build_manifest()
    manifest_bytes = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    files: dict[str, bytes] = {
        MANIFEST_NAME: manifest_bytes,
        "README.md": render_readme(manifest).encode("utf-8"),
    }
    files["SHA256SUMS"] = render_sha256sums(files)
    return files


def write_artifact(out_dir: Path) -> list[dict[str, str]]:
    files = build_artifact()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        target = out_dir / name
        target.write_bytes(files[name])
        written.append({"path": str(target), "sha256": _sha256_bytes(files[name])})
    return written


def check_artifact(artifact_dir: Path) -> dict[str, Any]:
    files = build_artifact()
    report: dict[str, Any] = {
        "artifact_dir": str(artifact_dir),
        "ok": True,
        "files": {},
        "violations": [],
    }
    on_disk: dict[str, bytes] = {}
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        target = artifact_dir / name
        if not target.is_file():
            report["ok"] = False
            report["violations"].append(f"missing artifact file: {name}")
            report["files"][name] = {"match": False, "reason": "missing"}
            continue
        on_disk[name] = target.read_bytes()
        match = on_disk[name] == files[name]
        report["files"][name] = {
            "match": match,
            "fresh_sha256": _sha256_bytes(files[name]),
            "actual_sha256": _sha256_bytes(on_disk[name]),
        }
        if not match:
            report["ok"] = False
            report["violations"].append(f"fresh build differs from committed {name}")
    sums_bytes = on_disk.get("SHA256SUMS")
    if sums_bytes is not None:
        entries: dict[str, str] = {}
        try:
            for line in sums_bytes.decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                digest, relative = line.split(None, 1)
                entries[relative.strip()] = digest.strip()
        except (UnicodeDecodeError, ValueError) as exc:
            report["ok"] = False
            report["violations"].append(f"on-disk SHA256SUMS unreadable: {exc}")
            entries = {}
        for name in ARTIFACT_FILES:
            if name not in entries:
                report["ok"] = False
                report["violations"].append(f"on-disk SHA256SUMS does not cover {name}")
                continue
            if name in on_disk and entries[name] != _sha256_bytes(on_disk[name]):
                report["ok"] = False
                report["violations"].append(f"on-disk SHA256SUMS mismatch for {name}")
    report["sample_count"] = json.loads(files[MANIFEST_NAME])["sample_count"]
    report["schema_integration"] = json.loads(files[MANIFEST_NAME])["schema_integration"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Phase-8A ground-truth benchmark manifest from committed "
            "fixtures and contracts (offline; deterministic)."
        ),
    )
    parser.add_argument("--out", type=Path, default=BENCHMARK_DIR,
                        help="artifact directory (default: %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="rebuild in memory and compare with the artifact on disk")
    parser.add_argument("--json", action="store_true",
                        help="print a JSON summary instead of writing files")
    args = parser.parse_args(argv)
    try:
        if args.check:
            report = check_artifact(args.out)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["ok"] else 1
        manifest = build_manifest()
        if args.json:
            print(json.dumps({
                "ok": True,
                "benchmark_id": manifest["benchmark_id"],
                "sample_count": manifest["sample_count"],
                "split_counts": manifest["split_counts"],
                "hidden_available": manifest["hidden_available"],
                "schema_integration": manifest["schema_integration"],
                "dropped_samples": manifest["dropped_samples"],
                "samples": [
                    {
                        "sample_id": sample["sample_id"],
                        "split": sample["split"],
                        "expected_scope": sample["expected_scope"],
                        "sha256": sample["sha256"],
                        "oracle_kinds": sample["oracle"]["kinds"],
                    }
                    for sample in manifest["samples"]
                ],
            }, indent=2, ensure_ascii=False))
            return 0
        written = write_artifact(args.out)
        print(json.dumps({"ok": True, "out": str(args.out), "written": written},
                         indent=2, ensure_ascii=False))
        return 0
    except BuildError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
