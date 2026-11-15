#!/usr/bin/env python3
"""Build the Phase-8C public ground-truth corpus v2 (C3 core + C8 variants + C9 cross-arch).

The builder is deterministic and offline: no AI, no network, no wall clock.
``generated_at`` is the fixed Phase-8C timestamp, samples are assembled from
committed fixtures/PoC manifests/reference fixes, every digest is recomputed, and
unknown v2 fields are explicit ``null`` plus a limitation (never guessed).

Public artifacts (canonical C2 checker paths):

* ``benchmark/phase8c/manifest.json``     - v2 public manifest (28 core samples
  + validated variants when available);
* ``benchmark/phase8c/README.md``         - deterministic human summary;
* ``benchmark/phase8c/PROVENANCE.json``   - source digests, toolchain facts,
  variant build/validation records and dropped-variant reasons;
* ``benchmark/phase8c/SHA256SUMS``        - covers manifest/README/PROVENANCE and
  every committed ``bin/`` payload (never itself);
* ``benchmark/phase8c/bin/``              - validated variant binaries, variant
  PoC manifests and build records (created only when variants are validated).

The hidden commitment file ``benchmark/phase8c/hidden-commitment.json`` is owned
by the C4/C6 hidden workflow; this builder never creates or reads it and records
``hidden_commitment: null`` with an explicit limitation.

Usage::

    python scripts/build_phase8c_corpus.py --write
    python scripts/build_phase8c_corpus.py --check [--out DIR]
    python scripts/build_phase8c_corpus.py --json
    python scripts/build_phase8c_corpus.py --write --build-variants   # C8
    python scripts/build_phase8c_corpus.py --build-variants --json    # C8 probe

Exit codes: 0 ok, 1 check/tamper/semantic violation, 2 unusable input/usage.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCHMARK_ID = "phase8c-public-v2"
KIND = "ground_truth_benchmark_v2"
FIXED_GENERATED_AT = "2026-11-16T00:00:00Z"
PUBLIC_DIR = ROOT / "benchmark" / "phase8c"
MANIFEST_NAME = "manifest.json"
README_NAME = "README.md"
PROVENANCE_NAME = "PROVENANCE.json"
SUMS_NAME = "SHA256SUMS"
BIN_DIRNAME = "bin"
V1_MANIFEST = "benchmark/phase8-v1/manifest.json"
HARD_CASES = "fixtures/hard-cases/cases.json"
REPAIR_CASES = "fixtures/repair-benchmark/cases.json"
FIXTURE_PROVENANCE = "fixtures/PROVENANCE.json"
SCHEMA_MANIFEST = "contracts/benchmark-manifest-v2.schema.json"
SCHEMA_SAMPLE = "contracts/ground-truth-sample-v2.schema.json"
CORE_SAMPLE_COUNT = 28
RUNTIME_KINDS = frozenset({"external_poc", "native", "emulated"})
ZIG_CANDIDATES = (
    "zig",
    str(ROOT / ".tmp" / "zigpkg" / "site" / "ziglang" / "zig"),
)
VARIANT_SOURCES = {
    "repair-cwe122": {
        "case_id": "cwe122-heap-copy",
        "binary_id": "repair-cwe122",
        "source": "fixtures/repair-benchmark/CWE122_heap_copy/vuln.c",
        "poc": "fixtures/poc/repair-cwe122.json",
        "reference_fix": "fixtures/repair-benchmark/CWE122_heap_copy/reference_fix.c",
        "defect": "fixtures/repair-benchmark/CWE122_heap_copy/defect.json",
        "target": "cwe122_bad",
        "cwe": "CWE-122",
        "family": "heap copy semantic guard",
        "capacity": 16,
    },
    "repair-cwe125": {
        "case_id": "cwe125-oob-read",
        "binary_id": "repair-cwe125",
        "source": "fixtures/repair-benchmark/CWE125_oob_read/vuln.c",
        "poc": "fixtures/poc/repair-cwe125.json",
        "reference_fix": "fixtures/repair-benchmark/CWE125_oob_read/reference_fix.c",
        "defect": "fixtures/repair-benchmark/CWE125_oob_read/defect.json",
        "target": "cwe125_bad",
        "cwe": "CWE-125",
        "family": "CWE-125",
        "capacity": 16,
    },
    "repair-cwe787": {
        "case_id": "cwe787-index-write",
        "binary_id": "repair-cwe787",
        "source": "fixtures/repair-benchmark/CWE787_index_write/vuln.c",
        "poc": "fixtures/poc/repair-cwe787.json",
        "reference_fix": "fixtures/repair-benchmark/CWE787_index_write/reference_fix.c",
        "defect": "fixtures/repair-benchmark/CWE787_index_write/defect.json",
        "target": "cwe787_bad",
        "cwe": "CWE-787",
        "family": "indexed write semantic guard",
        "capacity": 16,
    },
}
#: C8 variant matrix: 2 sources x 2 distinct build configurations.  The flags are
#: deliberately different (optimization level and strip) so the variants exercise
#: compiler/flag variation rather than duplicate binaries.
VARIANT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "sample_id": "variant-cwe122-O2",
        "source": "repair-cwe122",
        "target": "x86_64-linux-gnu",
        "optimization": "-O2",
        "extra_flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
        "stripped": False,
        "static": False,
        "split": "dev",
    },
    {
        "sample_id": "variant-cwe122-O2-stripped",
        "source": "repair-cwe122",
        "target": "x86_64-linux-gnu",
        "optimization": "-O2",
        "extra_flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-s"],
        "stripped": True,
        "static": False,
        "split": "validation",
    },
    {
        "sample_id": "variant-cwe125-O3-static",
        "source": "repair-cwe125",
        "target": "x86_64-linux-musl",
        "optimization": "-O3",
        "extra_flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static"],
        "stripped": False,
        "static": True,
        "split": "dev",
    },
    {
        "sample_id": "variant-cwe125-Os-static-stripped",
        "source": "repair-cwe125",
        "target": "x86_64-linux-musl",
        "optimization": "-Os",
        "extra_flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static", "-s"],
        "stripped": True,
        "static": True,
        "split": "validation",
    },
)
#: Explicit negative probes recorded in PROVENANCE (never in the manifest): they
#: are measured compiler/flag combinations that cannot reproduce the committed
#: original PoC behavior, so they must not become public samples.
VARIANT_ATTEMPTS: tuple[dict[str, Any], ...] = (
    {
        "attempt_id": "attempt-cwe122-musl-O2-static",
        "source": "repair-cwe122",
        "target": "x86_64-linux-musl",
        "optimization": "-O2",
        "extra_flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static"],
    },
    {
        "attempt_id": "attempt-cwe787-musl-O3-static",
        "source": "repair-cwe787",
        "target": "x86_64-linux-musl",
        "optimization": "-O3",
        "extra_flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static"],
    },
    {
        "attempt_id": "attempt-cwe122-gnu-static",
        "source": "repair-cwe122",
        "target": "x86_64-linux-gnu",
        "optimization": "-O2",
        "extra_flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static"],
    },
)



def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _canonical_bytes(payload: Any) -> bytes:
    return _canonical(payload).encode("utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(relative: str) -> Path:
    return ROOT / relative


def _exists(relative: str) -> bool:
    return _rel(relative).is_file()


def _limitation_once(limitations: list[str], text: str) -> None:
    if text and text not in limitations:
        limitations.append(text)


def _migration_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_phase8c_migration", ROOT / "scripts" / "migrate_ground_truth_v2.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load scripts/migrate_ground_truth_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _container_identity(data: bytes) -> dict[str, Any] | None:
    """Minimal container sniff: format/arch/bits/endian (fail closed)."""
    if data[:4] == b"\x7fELF" and len(data) >= 20:
        bits = 64 if data[4] == 2 else 32 if data[4] == 1 else None
        endian = "little" if data[5] == 1 else "big" if data[5] == 2 else None
        machine = struct.unpack_from("<H", data, 18)[0]
        arch = {62: "x86_64", 3: "i386", 183: "arm64"}.get(machine)
        if bits and endian and arch:
            return {"format": "elf", "arch": arch, "bits": bits, "endian": endian}
        return None
    if len(data) >= 8:
        magic_le = int.from_bytes(data[:4], "little")
        if magic_le in (0xFEEDFACF, 0xFEEDFACE):
            is_64 = magic_le == 0xFEEDFACF
            cputype = int.from_bytes(data[4:8], "little", signed=False)
            arch = {0x01000007: "x86_64", 0x0100000C: "arm64",
                    0x00000007: "i386", 0x0000000C: "arm64"}.get(cputype)
            if arch:
                return {"format": "macho", "arch": arch,
                        "bits": 64 if is_64 else 32, "endian": "little"}
            return None
    if data[:2] == b"MZ" and len(data) >= 64:
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 6 <= len(data) and data[pe_offset:pe_offset + 4] == b"PE\x00\x00":
            machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
            arch = {0x8664: "x86_64", 0xAA64: "arm64", 0x14C: "i386"}.get(machine)
            if arch:
                bits = 64 if machine in (0x8664, 0xAA64) else 32
                return {"format": "pe", "arch": arch, "bits": bits,
                        "endian": "little"}
    return None


def _poc_facts(relative: str, expected_sha: str) -> dict[str, Any]:
    """Load a PoC manifest, validate identity, and extract factual case ids."""
    path = _rel(relative)
    payload = _load_json(path)
    if payload.get("fixture_sha256") != expected_sha:
        raise ValueError(
            f"{relative}: fixture_sha256 {payload.get('fixture_sha256')!r} does not "
            f"match binary sha {expected_sha}")
    poc_cases = payload.get("poc") or []
    regression_cases = payload.get("regression") or []
    return {
        "path": relative,
        "sha256": _sha256_file(path),
        "target": payload.get("target"),
        "poc_ids": [str(item.get("id")) for item in poc_cases if isinstance(item, dict)],
        "regression_ids": [
            str(item.get("id")) for item in regression_cases if isinstance(item, dict)
        ],
        "has_runtime": True,
    }


def _reference_fix(relative: str | None) -> tuple[dict[str, Any] | None, list[str]]:
    if not relative:
        return None, []
    if not _exists(relative):
        return None, [f"reference fix {relative} is missing; null, not guessed"]
    return {"path": relative, "sha256": _sha256_file(_rel(relative))}, []


def _build_metadata(relative: str) -> dict[str, Any] | None:
    path = _rel(relative)
    if not path.is_file():
        return None
    payload = _load_json(path)
    compiler = payload.get("compiler") or {}
    flags = [str(item) for item in payload.get("flags") or []]
    optimization = next((flag for flag in flags if flag.startswith("-O")), None)
    linking = "static" if "-static" in flags else None
    stripping = "stripped" if "-s" in flags else "not_stripped"
    return {
        "path": relative,
        "compiler": compiler.get("name"),
        "compiler_version": compiler.get("version"),
        "optimization_level": optimization,
        "linking_mode": linking,
        "stripping_status": stripping,
        "flags": flags,
    }


def _environment_for_v1(v1_manifest: Mapping[str, Any]) -> dict[str, Any]:
    environment = v1_manifest.get("environment_metadata")
    return environment if isinstance(environment, dict) else {}


def _build_v1_samples() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Losslessly migrate the 12 v1 samples with C2's migration mapping."""
    migration = _migration_module()
    v1 = _load_json(_rel(V1_MANIFEST))
    environment = _environment_for_v1(v1)
    samples: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    for source in v1.get("samples") or []:
        if not isinstance(source, dict):
            continue
        sample, sample_facts = migration._migrate_sample(
            source, environment.get(str(source.get("sample_id"))) or {})
        if not migration._lossless_for_sample(source, sample):
            raise ValueError(
                f"v1->v2 migration is lossy for {source.get('sample_id')}")
        samples.append(sample)
        sample_facts = dict(sample_facts)
        sample_facts["lossless"] = True
        facts.append(sample_facts)
    if len(samples) != 12:
        raise ValueError(f"expected 12 migrated v1 samples, got {len(samples)}")
    return samples, facts


def _runtime_sample(
    *,
    sample_id: str,
    binary: str,
    poc: str,
    reference_fix: str | None,
    target: str,
    capacity: int,
    cwe: str | None,
    family: str,
    subtype: str,
    split: str,
    contract: str,
    source_refs: list[str],
    evidence_refs: list[str],
    build_metadata: dict[str, Any] | None,
    extra_limitations: list[str] | None = None,
    confidence: str = "high",
) -> dict[str, Any]:
    data = _rel(binary).read_bytes()
    identity = _container_identity(data)
    if identity is None:
        raise ValueError(f"{binary}: unsupported/unknown container")
    sha = _sha256_bytes(data)
    poc_facts = _poc_facts(poc, sha)
    reference, reference_limitations = _reference_fix(reference_fix)
    limitations: list[str] = []
    for item in reference_limitations:
        _limitation_once(limitations, item)
    limitations.extend(extra_limitations or [])
    _limitation_once(
        limitations,
        "affected byte ranges are not recorded for this fixture; empty, not guessed")
    _limitation_once(
        limitations,
        "ABI/linking details are not declared for this fixture; null, not guessed")
    build = build_metadata or {}
    if not reference:
        _limitation_once(limitations, "no committed reference fix for this fixture")
    if not build:
        _limitation_once(
            limitations,
            "compiler/version/flags for this checked-in fixture are not recorded "
            "in a committed build manifest; null, not guessed")
    trigger: list[str] = []
    if poc_facts["poc_ids"]:
        trigger.append(
            f"oversized input triggers the vulnerability per PoC case(s) "
            f"{poc_facts['poc_ids']}")
    if poc_facts["regression_ids"]:
        trigger.append(
            f"safe/regression behavior must be preserved per case(s) "
            f"{poc_facts['regression_ids']}")
    return {
        "sample_id": sample_id,
        "sample_version": 2,
        "binary_sha256": sha,
        "format": identity["format"],
        "arch": identity["arch"],
        "bits": identity["bits"],
        "endian": identity["endian"],
        "abi": None,
        "compiler": build.get("compiler"),
        "compiler_version": build.get("compiler_version"),
        "optimization_level": build.get("optimization_level"),
        "linking_mode": build.get("linking_mode"),
        "stripping_status": build.get("stripping_status"),
        "vulnerability_family": family,
        "vulnerability_subtype": subtype,
        "cwe": cwe,
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": target},
        "root_cause": {
            "statement": (
                f"Reviewed root cause: {contract}" if contract
                else f"Reviewed root cause for {sample_id}"),
            "evidence_refs": source_refs[:2] or [binary],
        },
        "trigger_conditions": trigger,
        "affected_function": target,
        "affected_ranges": [],
        "oracle": {
            "kind": "external_poc",
            "kinds": ["external_poc"],
            "manifest_path": poc,
            "expected_original": False,
            "expected_candidate": True,
            "regression_case_ids": poc_facts["regression_ids"],
        },
        "reference_fix": reference,
        "expected_original_behavior": (
            f"original binary does not survive the PoC case(s) "
            f"{poc_facts['poc_ids']} (crash/abort), while regression case(s) "
            f"{poc_facts['regression_ids']} keep their recorded behavior"
        ),
        "expected_fixed_behavior": (
            f"candidate must survive the PoC case(s) and preserve the regression "
            f"case behavior: {contract}" if contract else
            "candidate must survive the PoC cases and preserve regression behavior"
        ),
        "semantic_regression": {
            "required": bool(poc_facts["regression_ids"]),
            "case_ids": list(poc_facts["regression_ids"]),
        },
        "expected_patch_properties": {
            "capacity": capacity,
            "target": target,
            "oracle_kind": "external_poc",
        },
        "negative_cases": list(poc_facts["regression_ids"]),
        "split": split,
        "source_refs": list(dict.fromkeys(source_refs)),
        "evidence_refs": list(dict.fromkeys(evidence_refs + [poc])),
        "confidence": confidence,
        "limitations": sorted(set(limitations)),
    }


def _analysis_only_sample(
    *,
    sample_id: str,
    binary: str,
    format_expected: str,
    source_refs: list[str],
    evidence_refs: list[str],
    split: str,
    provenance_entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = _rel(binary).read_bytes()
    identity = _container_identity(data)
    if identity is None:
        raise ValueError(f"{binary}: unsupported/unknown container")
    if identity["format"] != format_expected:
        raise ValueError(
            f"{binary}: detected {identity['format']}, expected {format_expected}")
    sha = _sha256_bytes(data)
    limitations = [
        "cross-architecture analysis-only sample: no runtime oracle is claimed or "
        "executed for this format/arch in the public Phase-8C corpus",
        "affected byte ranges and function names are not recorded for this "
        "fixture; empty/null, not guessed",
        "ABI/linking/stripping details are not declared for this fixture; null, "
        "not guessed",
    ]
    compiler = compiler_version = optimization = None
    if provenance_entry:
        tool = str(provenance_entry.get("tool") or "")
        command = [str(item) for item in provenance_entry.get("command") or []]
        if "clang" in tool:
            compiler = "clang"
        elif tool.strip().startswith("0."):
            compiler = "zig"
        elif "gcc" in tool:
            compiler = "gcc"
        compiler_version = tool or None
        optimization = next((item for item in command if item.startswith("-O")), None)
    else:
        _limitation_once(
            limitations,
            "fixture provenance entry is missing; compiler/toolchain null")
    return {
        "sample_id": sample_id,
        "sample_version": 2,
        "binary_sha256": sha,
        "format": identity["format"],
        "arch": identity["arch"],
        "bits": identity["bits"],
        "endian": identity["endian"],
        "abi": None,
        "compiler": compiler,
        "compiler_version": compiler_version,
        "optimization_level": optimization,
        "linking_mode": None,
        "stripping_status": None,
        "vulnerability_family": "stack_buffer_overflow",
        "vulnerability_subtype": "unchecked strcpy (cross-architecture analysis-only)",
        "cwe": "CWE-121",
        "expected_scope": "analysis_only",
        "target": {"kind": "analysis_only"},
        "root_cause": {
            "statement": (
                "Cross-architecture unchecked-copy fixture: the fixture is "
                "declared for static analysis only in this phase; no runtime "
                "repair/verification claim is made."),
            "evidence_refs": evidence_refs,
        },
        "trigger_conditions": [],
        "affected_function": None,
        "affected_ranges": [],
        "oracle": {
            "kind": "static",
            "kinds": ["static"],
            "manifest_path": None,
            "expected_original": None,
            "expected_candidate": None,
            "regression_case_ids": [],
        },
        "reference_fix": None,
        "expected_original_behavior": None,
        "expected_fixed_behavior": None,
        "semantic_regression": None,
        "expected_patch_properties": {},
        "negative_cases": [],
        "split": split,
        "source_refs": list(dict.fromkeys(source_refs)),
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "confidence": None,
        "limitations": sorted(set(limitations)),
    }


def _hard_case_samples() -> list[dict[str, Any]]:
    cases_payload = _load_json(_rel(HARD_CASES))
    cases = {
        str(case.get("id")): case for case in cases_payload.get("cases") or []
        if isinstance(case, dict)
    }
    #: Deterministic public split assignment for the 6 new hard cases.
    split_by_id = {
        "hard-loop8": "dev",
        "hard-loop16": "dev",
        "hard-loop32": "dev",
        "hard-loop64": "validation",
        "hard-reverse": "validation",
        "heap-malloc": "validation",
    }
    definitions = (
        ("hard-loop8", "hard-loop8", "vuln_loop8", 8, "CWE-121",
         "non-template inline copy", "inline bounded-copy loop into an 8-byte "
         "stack buffer; bounded copy + NUL required"),
        ("hard-loop16", "hard-loop16", "vuln_loop16", 16, "CWE-121",
         "non-template inline copy", "inline byte-copy loop into a 16-byte stack "
         "buffer; bounded copy + NUL required"),
        ("hard-loop32", "hard-loop32", "vuln_loop32", 32, "CWE-121",
         "non-template inline copy", "inline byte-copy loop into a 32-byte stack "
         "buffer; bounded copy + NUL required"),
        ("hard-loop64", "hard-loop64", "vuln_loop64", 64, "CWE-121",
         "non-template inline copy", "inline byte-copy loop into a 64-byte stack "
         "buffer; bounded copy + NUL required"),
        ("hard-reverse", "hard-reverse", "vuln_loop_reverse", 16, "CWE-121",
         "non-template inline copy", "reverse inline copy loop into a 16-byte "
         "stack buffer; bounded copy + NUL required"),
    )
    samples: list[dict[str, Any]] = []
    for sample_id, case_id, target, capacity, cwe, family, contract in definitions:
        case = cases.get(case_id)
        if case is None:
            raise ValueError(f"hard-case definition {case_id!r} is missing")
        source_extra = (
            ["fixtures/hard-cases/hard_loops.S", "fixtures/hard-cases/hard_loops_extra.S"]
            if "loop8" in sample_id or "loop64" in sample_id
            else ["fixtures/hard-cases/hard_loops.S"]
        )
        samples.append(_runtime_sample(
            sample_id=sample_id,
            binary=str(case["binary"]),
            poc=str(case["poc"]),
            reference_fix=str(case["reference_fix"]),
            target=target,
            capacity=capacity,
            cwe=cwe,
            family=family,
            subtype=str(case.get("contract") or family),
            split=split_by_id[sample_id],
            contract=contract,
            source_refs=[str(case["binary"]), str(case["reference_fix"]),
                         *source_extra, f"{HARD_CASES}#{case_id}"],
            evidence_refs=[f"{HARD_CASES}#{case_id}"],
            build_metadata=None,
        ))
    # heap-malloc: checked-in heap fixture with PoC but no dedicated fixed source.
    heap_binary = "fixtures/hard-cases/vuln-heap-malloc-x86_64.elf"
    heap_poc = "fixtures/poc/heap-malloc.json"
    heap_source = "fixtures/hard-cases/heap_capacity.c"
    samples.append(_runtime_sample(
        sample_id="heap-malloc",
        binary=heap_binary,
        poc=heap_poc,
        reference_fix=None,
        target="heap_bad",
        capacity=16,
        cwe="CWE-122",
        family="heap_buffer_overflow",
        subtype="heap malloc capacity hard case (unbounded strcpy)",
        split=split_by_id["heap-malloc"],
        contract="heap_bad copies argv[1] into a 16-byte malloc block with strcpy; "
                 "a repaired path must reject/truncate oversized input and keep "
                 "normal output",
        source_refs=[heap_binary, heap_source, heap_poc],
        evidence_refs=[heap_source],
        build_metadata=None,
        extra_limitations=[
            "no dedicated committed reference-fix source exists for "
            "vuln-heap-malloc-x86_64.elf; reference_fix is null, not guessed",
            "compiler/flags for this checked-in heap fixture are recorded only in "
            "a source comment; null in the sample, not guessed",
        ],
    ))
    return samples


def _repair_case_samples() -> list[dict[str, Any]]:
    cases_payload = _load_json(_rel(REPAIR_CASES))
    cases = {
        str(case.get("id")): case for case in cases_payload.get("cases") or []
        if isinstance(case, dict)
    }
    mapping = (
        ("repair-cwe122", "cwe122-heap-copy", "dev"),
        ("repair-cwe125", "cwe125-oob-read", "dev"),
        ("repair-cwe134", "cwe134-format-string", "dev"),
        ("repair-cwe190", "cwe190-integer-overflow", "validation"),
        ("repair-cwe476", "cwe476-null-deref", "validation"),
        ("repair-cwe787", "cwe787-index-write", "validation"),
    )
    samples: list[dict[str, Any]] = []
    for sample_id, case_id, split in mapping:
        case = cases.get(case_id)
        if case is None:
            raise ValueError(f"repair-benchmark case {case_id!r} is missing")
        binary = str(case["binary"])
        build_relative = str(Path(binary).parent / "build.json")
        build = _build_metadata(build_relative)
        cwe = str(case.get("cwe") or "") or None
        sample = _runtime_sample(
            sample_id=sample_id,
            binary=binary,
            poc=str(case["poc"]),
            reference_fix=str(case["reference_fix"]),
            target=str(case["target"]),
            capacity=int(case.get("capacity") or 0),
            cwe=cwe,
            family=str(case.get("family") or "non_template"),
            subtype=str(case.get("contract") or case.get("family") or "non_template"),
            split=split,
            contract=str(case.get("contract") or ""),
            source_refs=[binary, str(case["reference_fix"]),
                         str(Path(binary).parent / "vuln.c"),
                         str(Path(binary).parent / "defect.json"),
                         f"{REPAIR_CASES}#{case_id}"],
            evidence_refs=[f"{REPAIR_CASES}#{case_id}",
                           str(Path(binary).parent / "build.json")],
            build_metadata=build,
            extra_limitations=[
                "source case split field is "
                f"{case.get('split')!r}; the Phase-8C public split assignment is "
                f"{split!r} per the approved public corpus table"
                if case.get("split") in {"hidden", "dev"} else ""
            ],
        )
        samples.append(sample)
    return samples


def _fixture_provenance() -> dict[str, dict[str, Any]]:
    payload = _load_json(_rel(FIXTURE_PROVENANCE))
    entries = {}
    for item in payload.get("fixtures") or []:
        if isinstance(item, dict) and item.get("path"):
            entries[str(item["path"])] = item
    return entries


def _cross_arch_samples() -> list[dict[str, Any]]:
    provenance = _fixture_provenance()
    definitions = (
        ("xarch-macho-arm64", "fixtures/macho/vuln-strcpy-arm64", "macho", "dev"),
        ("xarch-macho-x86_64", "fixtures/macho/vuln-strcpy-x86_64", "macho", "dev"),
        ("xarch-pe-arm64", "fixtures/pe/vuln-strcpy-arm64.exe", "pe", "validation"),
        ("xarch-pe-x64", "fixtures/pe/vuln-strcpy-x64.exe", "pe", "validation"),
    )
    samples = []
    for sample_id, binary, expected_format, split in definitions:
        entry = provenance.get(binary)
        evidence = [FIXTURE_PROVENANCE] if entry else []
        if entry:
            evidence.append(f"{FIXTURE_PROVENANCE}#{entry.get('name')}")
        samples.append(_analysis_only_sample(
            sample_id=sample_id,
            binary=binary,
            format_expected=expected_format,
            source_refs=[binary, *evidence],
            evidence_refs=evidence,
            split=split,
            provenance_entry=entry,
        ))
    return samples


# ---------------------------------------------------------------------------
# C8 variants: build with Zig if available, validate the original oracle, drop
# failures with explicit reasons.  Binaries/PoCs/build records are committed
# under benchmark/phase8c/bin/ so the deterministic manifest can be rebuilt.
# ---------------------------------------------------------------------------


def _zig_path() -> str | None:
    for candidate in ZIG_CANDIDATES:
        path = candidate if os.path.isabs(candidate) else shutil.which(candidate)
        if path and Path(path).is_file():
            return str(path)
    return None


def _zig_version(zig: str | None) -> str | None:
    if not zig:
        return None
    try:
        result = subprocess.run([zig, "version"], capture_output=True, text=True,
                                timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    version = result.stdout.strip()
    return version or None


def _variant_provenance() -> dict[str, Any]:
    zig = _zig_path()
    gcc = shutil.which("gcc")
    clang = shutil.which("clang")
    def _version(command: list[str]) -> str | None:
        if not command:
            return None
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        return (result.stdout or result.stderr).splitlines()[0].strip() or None
    return {
        "zig": {
            "path": zig,
            "version": _zig_version(zig),
            "status": "available" if zig else "not_run",
            "reason": None if zig else (
                "zig was not found on PATH or at .tmp/zigpkg/site/ziglang/zig; "
                "compiler variants cannot be built/validated on this host"),
        },
        "gcc": {"path": gcc, "version": _version([gcc, "--version"]) if gcc else None},
        "clang": {"path": clang, "version": _version([clang, "--version"]) if clang else None},
    }


def _attempts_path() -> Path:
    return PUBLIC_DIR / BIN_DIRNAME / "variant-attempts.json"


def _variant_paths(sample_id: str) -> dict[str, Path]:
    base = PUBLIC_DIR / BIN_DIRNAME
    return {
        "binary": base / f"{sample_id}.elf",
        "poc": base / f"{sample_id}.poc.json",
        "build": base / f"{sample_id}.build.json",
    }


def _validate_variant_oracle(binary: Path, poc_path: Path) -> dict[str, Any]:
    """Execute the oracle against the variant binary itself (must reproduce the bug).

    The PoC differential is run with the original bytes as the candidate: a
    vulnerable original must not satisfy the fixed-candidate expectations, so the
    evidence status is expected to be ``fail`` with an executed runner/tier.  A
    missing runner is recorded as ``not_run`` and the variant is dropped.
    """
    from app.services.poc_runner import run_poc

    data = binary.read_bytes()
    evidence = run_poc(data, data, poc_path)
    payload = evidence.to_dict() if hasattr(evidence, "to_dict") else {}
    status = str(payload.get("status") or "")
    runner = str(payload.get("runner") or "")
    tier = str(payload.get("tier") or "")
    cases = [case for case in payload.get("poc") or [] if isinstance(case, dict)]
    original_poc_cases = [
        case for case in cases
        if case.get("executable") == "original" and case.get("kind") == "poc"
    ]
    vulnerable = bool(original_poc_cases) and all(
        case.get("crashed") is True for case in original_poc_cases)
    executed = status in {"pass", "fail"} and bool(runner)
    reason = None
    if not executed:
        reason = (
            "external PoC runner unavailable/inconclusive for this variant; "
            "variant dropped rather than faked")
    elif not vulnerable:
        reason = (
            "variant build does not reproduce the committed PoC's expected "
            "vulnerable original behavior (original PoC case did not crash); "
            "variant dropped rather than admitting an unvalidated build")
    elif status != "fail":
        reason = (
            f"variant differential status {status!r} is not the expected fail; "
            "variant dropped")
    return {
        "status": status,
        "runner": runner,
        "tier": tier,
        "executed": executed,
        "original_vulnerable_observed": vulnerable,
        "original_poc_case_count": len(original_poc_cases),
        "reason": reason,
        "evidence_sha256": _sha256_bytes(_canonical_bytes(payload)),
    }


def build_variants(*, allow_build: bool, provenance: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(variant_samples, build_records)``; never fake a variant."""
    records: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    zig = _zig_path()
    toolchain = provenance.setdefault("toolchain", {})
    zig_info = toolchain.setdefault("zig", {
        "path": None, "version": None, "status": "not_run", "reason": None})
    zig_info["path"] = zig
    zig_info["version"] = _zig_version(zig)
    zig_info["status"] = "available" if zig else "not_run"
    zig_info["reason"] = None if zig else (
        "zig was not found on PATH or at .tmp/zigpkg/site/ziglang/zig; compiler "
        "variants cannot be built/validated on this host")
    base = PUBLIC_DIR / BIN_DIRNAME
    for spec in VARIANT_SPECS:
        sample_id = str(spec["sample_id"])
        source_spec = VARIANT_SOURCES[str(spec["source"])]
        paths = _variant_paths(sample_id)
        record: dict[str, Any] = {
            "sample_id": sample_id,
            "source_sample": str(spec["source"]),
            "status": "dropped",
            "reason": None,
        }
        if zig is None:
            record["reason"] = (
                "cross_compiler_not_run: no Zig compiler available (PATH or "
                ".tmp/zigpkg/site/ziglang/zig); variant not built, not faked")
            records.append(record)
            continue
        if not allow_build:
            if not (paths["binary"].is_file() and paths["poc"].is_file()
                    and paths["build"].is_file()):
                record["reason"] = (
                    "variant payloads are not committed and --build-variants was "
                    "not requested; no variant sample emitted")
                records.append(record)
                continue
            build = _load_json(paths["build"])
            sha = _sha256_file(paths["binary"])
            if build.get("output_sha256") != sha:
                record["reason"] = "committed variant binary digest does not match build record"
                records.append(record)
                continue
            record.update({"status": "validated", "binary": str(paths["binary"].relative_to(ROOT)),
                           "poc": str(paths["poc"].relative_to(ROOT)),
                           "build_record": str(paths["build"].relative_to(ROOT)),
                           "binary_sha256": sha,
                           "compiler": build.get("compiler"),
                           "compiler_version": build.get("compiler_version"),
                           "flags": build.get("flags"),
                           "oracle_validation": build.get("oracle_validation")})
            samples.append(_variant_sample(spec, source_spec, build, sha))
            records.append(record)
            continue
        # --build-variants: compile from the committed fixture source with Zig.
        base.mkdir(parents=True, exist_ok=True)
        source_path = _rel(source_spec["source"])
        temp_binary = base / f".{sample_id}.tmp.elf"
        command = [
            zig, "cc", "-target", str(spec["target"]),
            str(spec["optimization"]), "-g0",
            *[str(item) for item in spec["extra_flags"]],
            "-o", str(temp_binary), str(source_path),
        ]
        try:
            compile_result = subprocess.run(
                command, capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            record["reason"] = f"compiler invocation failed: {type(exc).__name__}: {exc}"
            records.append(record)
            temp_binary.unlink(missing_ok=True)
            continue
        if compile_result.returncode != 0 or not temp_binary.is_file():
            record["reason"] = (
                "cross-compiler build failed: "
                f"{compile_result.stderr.strip()[:400] or compile_result.stdout.strip()[:400]}")
            records.append(record)
            temp_binary.unlink(missing_ok=True)
            continue
        sha = _sha256_file(temp_binary)
        # variant PoC: same cases, fixture digest rebound to the variant bytes.
        original_poc = _load_json(_rel(source_spec["poc"]))
        variant_poc = dict(original_poc)
        variant_poc["fixture_sha256"] = sha
        variant_poc["description"] = (
            f"Phase-8C C8 compiler variant {sample_id}: original repair-benchmark "
            f"PoC cases rebound to the variant binary")
        paths["poc"].write_bytes(_canonical_bytes(variant_poc))
        validation = _validate_variant_oracle(temp_binary, paths["poc"])
        build_record = {
            "sample_id": sample_id,
            "source_sample": str(spec["source"]),
            "source": str(source_spec["source"]),
            "source_sha256": _sha256_file(source_path),
            "compiler": "zig",
            "compiler_version": _zig_version(zig),
            "target": str(spec["target"]),
            "optimization": str(spec["optimization"]),
            "flags": [str(spec["optimization"]), "-g0",
                      *[str(item) for item in spec["extra_flags"]]],
            "stripped": bool(spec["stripped"]),
            "static": bool(spec.get("static")),
            "linking_mode": "static" if spec.get("static") else "dynamic",
            "command": command,
            "output": str(paths["binary"].relative_to(ROOT)),
            "output_sha256": sha,
            "oracle_validation": validation,
            "network": False,
            "deterministic": False,
        }
        if validation["reason"] is not None:
            path_binary = paths["binary"]
            if path_binary.is_file():
                path_binary.unlink()
            record["reason"] = (
                "variant oracle validation failed: " + str(validation["reason"]))
            records.append(record)
            temp_binary.unlink(missing_ok=True)
            continue
        build_record["oracle_validation"]["expected_original_fail_observed"] = True
        paths["build"].write_bytes(_canonical_bytes(build_record))
        if paths["binary"].is_file():
            paths["binary"].unlink()
        temp_binary.replace(paths["binary"])
        record.update({
            "status": "validated",
            "binary": str(paths["binary"].relative_to(ROOT)),
            "poc": str(paths["poc"].relative_to(ROOT)),
            "build_record": str(paths["build"].relative_to(ROOT)),
            "binary_sha256": sha,
            "compiler": "zig",
            "compiler_version": _zig_version(zig),
            "flags": build_record["flags"],
            "oracle_validation": validation,
        })
        samples.append(_variant_sample(spec, source_spec, build_record, sha))
        records.append(record)
    # Negative probes: measured compiler/flag combinations that must NOT become
    # public samples because they cannot reproduce the committed original oracle
    # behavior.  Drop reasons are committed in bin/variant-attempts.json.
    attempt_records: list[dict[str, Any]] = []
    for attempt in VARIANT_ATTEMPTS:
        attempt_id = str(attempt["attempt_id"])
        source_spec = VARIANT_SOURCES[str(attempt["source"])]
        record = {
            "attempt_id": attempt_id,
            "source_sample": str(attempt["source"]),
            "status": "dropped",
            "reason": None,
            "compiler": "zig",
            "compiler_version": _zig_version(zig),
            "target": str(attempt["target"]),
            "optimization": str(attempt["optimization"]),
            "flags": [str(attempt["optimization"]), "-g0",
                      *[str(item) for item in attempt["extra_flags"]]],
        }
        temp_binary = PUBLIC_DIR / BIN_DIRNAME / f".{attempt_id}.tmp.elf"
        command = [
            zig, "cc", "-target", str(attempt["target"]),
            str(attempt["optimization"]), "-g0",
            *[str(item) for item in attempt["extra_flags"]],
            "-o", str(temp_binary), str(_rel(source_spec["source"])),
        ]
        try:
            compile_result = subprocess.run(
                command, capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            record["reason"] = f"compiler invocation failed: {type(exc).__name__}: {exc}"
            attempt_records.append(record)
            continue
        if compile_result.returncode != 0 or not temp_binary.is_file():
            record["reason"] = (
                "cross-compiler build failed: "
                f"{compile_result.stderr.strip()[:400] or compile_result.stdout.strip()[:400]}")
            attempt_records.append(record)
            temp_binary.unlink(missing_ok=True)
            continue
        sha = _sha256_file(temp_binary)
        original_poc = _load_json(_rel(source_spec["poc"]))
        attempt_poc = dict(original_poc)
        attempt_poc["fixture_sha256"] = sha
        attempt_poc_path = PUBLIC_DIR / BIN_DIRNAME / f".{attempt_id}.poc.json"
        attempt_poc_path.write_bytes(_canonical_bytes(attempt_poc))
        validation = _validate_variant_oracle(temp_binary, attempt_poc_path)
        if validation["reason"] is not None:
            record["reason"] = validation["reason"]
        else:
            record["reason"] = (
                "probe unexpectedly reproduced the original oracle behavior; it "
                "remains a probe and is not admitted to the public manifest without "
                "an explicit spec entry")
        record["oracle_validation"] = validation
        attempt_records.append(record)
        temp_binary.unlink(missing_ok=True)
        attempt_poc_path.unlink(missing_ok=True)
    if attempt_records and _attempts_path().parent.is_dir():
        _attempts_path().write_bytes(_canonical_bytes({
            "schema_version": 1,
            "kind": "phase8c_variant_attempts",
            "generated_at": FIXED_GENERATED_AT,
            "attempts": attempt_records,
        }))
    provenance["variant_attempts"] = attempt_records
    provenance["variants"] = records
    return samples, records


def _variant_sample(spec: Mapping[str, Any], source_spec: Mapping[str, Any],
                    build: Mapping[str, Any], sha: str) -> dict[str, Any]:
    sample_id = str(spec["sample_id"])
    binary = str(_variant_paths(sample_id)["binary"].relative_to(ROOT))
    poc = str(_variant_paths(sample_id)["poc"].relative_to(ROOT))
    build_path = str(_variant_paths(sample_id)["build"].relative_to(ROOT))
    source_refs = [
        binary, str(source_spec["source"]), str(source_spec["reference_fix"]),
        "fixtures/repair-benchmark/cases.json",
        build_path,
    ]
    evidence_refs = [poc, build_path, f"fixtures/repair-benchmark/cases.json#{source_spec['case_id']}"]
    data = _rel(binary).read_bytes()
    identity = _container_identity(data)
    if identity is None:
        raise ValueError(f"{binary}: unsupported variant container")
    reference, reference_limitations = _reference_fix(str(source_spec["reference_fix"]))
    limitations = [
        "compiler variant: behavior/build variation is recorded in the committed "
        "build record; the variant is public and NOT the hidden corpus",
        "affected byte ranges are not recorded for this variant; empty, not guessed",
    ] + reference_limitations
    return {
        "sample_id": sample_id,
        "sample_version": 2,
        "binary_sha256": sha,
        "format": identity["format"],
        "arch": identity["arch"],
        "bits": identity["bits"],
        "endian": identity["endian"],
        "abi": "sysv-amd64",
        "compiler": str(build.get("compiler") or "zig"),
        "compiler_version": str(build.get("compiler_version") or "") or None,
        "optimization_level": str(spec.get("optimization") or "") or None,
        "linking_mode": str(build.get("linking_mode") or (
            "static" if build.get("static") else "dynamic")),
        "stripping_status": "stripped" if spec.get("stripped") else "not_stripped",
        "vulnerability_family": str(source_spec["family"]),
        "vulnerability_subtype": (
            f"CWE variant of {source_spec['case_id']} built with "
            f"{spec.get('optimization')} and flags "
            f"{' '.join(str(item) for item in build.get('flags') or [])}"),
        "cwe": str(source_spec["cwe"]),
        "expected_scope": "function",
        "target": {"kind": "symbol", "symbol": str(source_spec["target"])},
        "root_cause": {
            "statement": (
                "Reviewed root cause of the source repair-benchmark case, rebuilt "
                "as a compiler/flag variant; original oracle behavior was executed "
                "and observed vulnerable before inclusion."),
            "evidence_refs": evidence_refs[:2],
        },
        "trigger_conditions": [
            "oversized input per the rebound PoC cases triggers the vulnerability "
            "in the variant build"],
        "affected_function": str(source_spec["target"]),
        "affected_ranges": [],
        "oracle": {
            "kind": "external_poc",
            "kinds": ["external_poc"],
            "manifest_path": poc,
            "expected_original": False,
            "expected_candidate": True,
            "regression_case_ids": [
                str(item.get("id")) for item in
                (_load_json(_rel(poc)).get("regression") or [])
                if isinstance(item, dict)
            ],
        },
        "reference_fix": reference,
        "expected_original_behavior": (
            "variant original fails the rebound PoC differential exactly as the "
            "committed build record's executed oracle evidence shows"),
        "expected_fixed_behavior": (
            "candidate must survive the rebound PoC cases and preserve regression "
            "behavior of the source repair-benchmark case"),
        "semantic_regression": {
            "required": True,
            "case_ids": [
                str(item.get("id")) for item in
                (_load_json(_rel(poc)).get("regression") or [])
                if isinstance(item, dict)
            ],
        },
        "expected_patch_properties": {
            "capacity": int(source_spec["capacity"]),
            "target": str(source_spec["target"]),
            "oracle_kind": "external_poc",
            "variant_of": str(source_spec["case_id"]),
        },
        "negative_cases": [
            str(item.get("id")) for item in
            (_load_json(_rel(poc)).get("regression") or [])
            if isinstance(item, dict)
        ],
        "split": str(spec["split"]),
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "confidence": "medium",
        "limitations": limitations,
    }


# ---------------------------------------------------------------------------
# Manifest assembly, semantic validation, artifacts and checks
# ---------------------------------------------------------------------------


def _source_digest(paths: list[str]) -> str:
    entries = []
    for relative in sorted(set(paths)):
        path = _rel(relative)
        if path.is_file():
            entries.append(f"{_sha256_file(path)}  {relative}")
    return _sha256_bytes(("\n".join(entries) + "\n").encode("utf-8"))


def _semantic_violations(manifest: Mapping[str, Any]) -> list[str]:
    """Mirror the C2 manifest/sample semantic rules for fail-closed validation."""
    violations: list[str] = []
    samples = manifest.get("samples") or []
    if manifest.get("schema_version") != 2:
        violations.append("manifest schema_version must be 2")
    if manifest.get("kind") != KIND:
        violations.append(f"manifest kind must be {KIND!r}")
    if manifest.get("hidden_available") is not False:
        violations.append("manifest hidden_available must be false")
    if manifest.get("sample_count") != len(samples):
        violations.append("manifest sample_count must equal len(samples)")
    split_counts = manifest.get("split_counts") or {}
    actual: dict[str, int] = {}
    for sample in samples:
        if isinstance(sample, Mapping):
            split = str(sample.get("split"))
            actual[split] = actual.get(split, 0) + 1
    for split in ("dev", "validation"):
        if split_counts.get(split) != actual.get(split, 0):
            violations.append(f"manifest split_counts.{split} does not match samples")
    if sum(int(value) for value in split_counts.values()) != len(samples):
        violations.append("manifest split counts must sum to the sample count")
    commitment = manifest.get("hidden_commitment")
    if isinstance(commitment, Mapping):
        counts = commitment.get("counts") or {}
        if counts.get("sample_count") != (
                counts.get("runtime_count", 0) + counts.get("analysis_only_count", 0)):
            violations.append("hidden commitment counts do not sum")
    ids = [str(sample.get("sample_id")) for sample in samples if isinstance(sample, Mapping)]
    if len(set(ids)) != len(ids):
        violations.append("duplicate sample_id in manifest")
    for sample in samples:
        if not isinstance(sample, Mapping):
            violations.append("sample is not an object")
            continue
        sample_id = str(sample.get("sample_id"))
        limitations = sample.get("limitations") or []
        null_fields = [
            field for field in (
                "abi", "compiler", "linking_mode", "stripping_status", "cwe",
                "affected_function", "expected_original_behavior",
                "expected_fixed_behavior", "semantic_regression", "confidence",
            )
            if sample.get(field) is None
        ]
        if null_fields and not limitations:
            violations.append(f"{sample_id}: null unknown fields require limitations")
        if not sample.get("trigger_conditions") and not limitations:
            violations.append(f"{sample_id}: empty trigger_conditions require a limitation")
        if not sample.get("affected_ranges") and not limitations:
            violations.append(f"{sample_id}: empty affected_ranges require a limitation")
        if sample.get("reference_fix") is None and not limitations:
            violations.append(f"{sample_id}: null reference_fix requires a limitation")
        reference = sample.get("reference_fix")
        if isinstance(reference, Mapping) and reference.get("sha256") is None \
                and not limitations:
            violations.append(f"{sample_id}: unknown reference_fix sha256 requires a limitation")
        oracle = sample.get("oracle") or {}
        kinds = set(oracle.get("kinds") or [])
        if oracle.get("kind"):
            kinds.add(str(oracle.get("kind")))
        runtime = kinds & RUNTIME_KINDS
        scope = sample.get("expected_scope")
        if scope in {"function", "whole_program"} and not runtime:
            violations.append(
                f"{sample_id}: function/whole_program requires an independent "
                "runtime oracle kind")
        if scope == "analysis_only" and runtime:
            violations.append(
                f"{sample_id}: analysis_only must not claim a runtime oracle kind")
        if sample.get("expected_scope") == "analysis_only":
            if sample.get("target", {}).get("kind") != "analysis_only":
                violations.append(
                    f"{sample_id}: analysis_only sample target.kind must be analysis_only")
            if oracle.get("manifest_path") is not None:
                violations.append(
                    f"{sample_id}: analysis_only sample must not declare a runtime manifest")
    return violations


def _schema_context() -> tuple[Any, Any]:
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        return None, None
    manifest_schema = _load_json(_rel(SCHEMA_MANIFEST))
    sample_schema = _load_json(_rel(SCHEMA_SAMPLE))
    return (jsonschema.Draft202012Validator(manifest_schema),
            jsonschema.Draft202012Validator(sample_schema))


def _schema_violations(manifest: Mapping[str, Any]) -> list[str]:
    validator, sample_validator = _schema_context()
    if validator is None or sample_validator is None:
        return ["jsonschema is unavailable; schema validation not_run"]
    violations = []
    for error in sorted(validator.iter_errors(manifest), key=str):
        where = "/".join(str(part) for part in error.absolute_path) or "<root>"
        violations.append(f"manifest schema {where}: {error.message}")
    for sample in manifest.get("samples") or []:
        if not isinstance(sample, Mapping):
            continue
        for error in sorted(sample_validator.iter_errors(sample), key=str):
            where = "/".join(str(part) for part in error.absolute_path) or "<root>"
            violations.append(
                f"sample {sample.get('sample_id')} schema {where}: {error.message}")
    return violations


def _migration_report(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the per-sample migration facts for the 12 preserved v1 samples."""
    migration = _migration_module()
    v1 = _load_json(_rel(V1_MANIFEST))
    environment = _environment_for_v1(v1)
    migrated = {
        str(sample.get("sample_id")): sample
        for sample in manifest.get("samples") or []
        if isinstance(sample, Mapping)
    }
    facts = []
    for source in v1.get("samples") or []:
        if not isinstance(source, dict):
            continue
        sample_id = str(source.get("sample_id"))
        target = migrated.get(sample_id)
        if target is None:
            facts.append({"sample_id": sample_id, "preserved": False,
                          "reason": "missing from public manifest"})
            continue
        expected, sample_facts = migration._migrate_sample(
            source, environment.get(sample_id) or {})
        facts.append({
            **sample_facts,
            "lossless": migration._lossless_for_sample(source, target),
            "preserved_against_fresh_migration": target == expected,
        })
    return facts


def build_manifest() -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the in-memory manifest + provenance without writing anything."""
    v1_samples, migration_facts = _build_v1_samples()
    hard_samples = _hard_case_samples()
    repair_samples = _repair_case_samples()
    cross_samples = _cross_arch_samples()
    core = v1_samples + hard_samples + repair_samples + cross_samples
    provenance: dict[str, Any] = {"toolchain": _variant_provenance(),
                                  "variants": []}
    variant_samples: list[dict[str, Any]] = []
    variant_records: list[dict[str, Any]] = []
    # Committed validated variants are included deterministically even when the
    # toolchain is absent on the checking host; new builds happen only in
    # --build-variants mode (handled by the CLI before build_manifest()).
    if (PUBLIC_DIR / BIN_DIRNAME).is_dir():
        for spec in VARIANT_SPECS:
            sample_id = str(spec["sample_id"])
            paths = _variant_paths(sample_id)
            if not (paths["binary"].is_file() and paths["poc"].is_file()
                    and paths["build"].is_file()):
                continue
            build = _load_json(paths["build"])
            sha = _sha256_file(paths["binary"])
            if build.get("output_sha256") != sha:
                variant_records.append({
                    "sample_id": sample_id, "status": "dropped",
                    "reason": "committed variant binary digest does not match build record"})
                continue
            variant_samples.append(_variant_sample(
                spec, VARIANT_SOURCES[str(spec["source"])], build, sha))
            variant_records.append({
                "sample_id": sample_id, "status": "validated",
                "source_sample": str(spec["source"]),
                "binary": str(paths["binary"].relative_to(ROOT)),
                "poc": str(paths["poc"].relative_to(ROOT)),
                "build_record": str(paths["build"].relative_to(ROOT)),
                "binary_sha256": sha,
                "compiler": build.get("compiler"),
                "compiler_version": build.get("compiler_version"),
                "flags": build.get("flags"),
                "oracle_validation": build.get("oracle_validation"),
            })
    provenance["variants"] = variant_records
    attempts: list[dict[str, Any]] = []
    if _attempts_path().is_file():
        attempts_payload = _load_json(_attempts_path())
        attempts = [
            record for record in attempts_payload.get("attempts") or []
            if isinstance(record, dict)
        ]
    provenance["variant_attempts"] = attempts
    samples = core + variant_samples
    samples.sort(key=lambda sample: str(sample["sample_id"]))
    split_counts = {
        "dev": sum(1 for sample in samples if sample["split"] == "dev"),
        "validation": sum(1 for sample in samples if sample["split"] == "validation"),
    }
    source_paths = [
        V1_MANIFEST, HARD_CASES, REPAIR_CASES, FIXTURE_PROVENANCE,
        SCHEMA_MANIFEST, SCHEMA_SAMPLE,
        "scripts/migrate_ground_truth_v2.py",
        "scripts/build_phase8c_corpus.py",
    ]
    for sample in samples:
        source_paths.extend(sample.get("source_refs") or [])
        source_paths.extend(sample.get("evidence_refs") or [])
        oracle = sample.get("oracle") or {}
        if oracle.get("manifest_path"):
            source_paths.append(str(oracle["manifest_path"]))
        reference = sample.get("reference_fix")
        if isinstance(reference, Mapping) and reference.get("path"):
            source_paths.append(str(reference["path"]))
    source_paths = [path.split("#", 1)[0] for path in source_paths if path]
    manifest = {
        "schema_version": 2,
        "kind": KIND,
        "benchmark_id": BENCHMARK_ID,
        "generated_at": FIXED_GENERATED_AT,
        "hidden_available": False,
        "samples": samples,
        "sample_count": len(samples),
        "split_counts": split_counts,
        "hidden_commitment": None,
        "provenance": {
            "builder": "scripts/build_phase8c_corpus.py",
            "source_digest_sha256": _source_digest(source_paths),
            "source_manifest": V1_MANIFEST,
            "migration_report_sha256": _sha256_bytes(_canonical_bytes(
                migration_facts)),
        },
        "limitations": [
            "public corpus only: hidden_available=false and hidden_commitment is "
            "null. The hidden commitment file benchmark/phase8c/hidden-commitment."
            "json is owned by the C4/C6 hidden workflow; this builder never "
            "creates, reads or fabricates hidden contents.",
            "compiler/ABI/linking/stripping/ranges unknown for some checked-in "
            "fixtures are explicit null/empty with per-sample limitations, never "
            "guessed.",
            "the public split assignment for the new hard/repair/cross-arch groups "
            "is deterministic (hard 3/3, repair 3/3, cross-arch 2/2); the 12 v1 "
            "samples keep their v1 split.",
            "runtime-oracle samples are 20 and analysis-only samples are 8 among "
            "the 28 core samples; variants add only independently validated "
            "compiler/flag builds.",
            "no network and no AI provider are used by the builder; generated_at "
            "is the fixed Phase-8C timestamp.",
        ],
    }
    provenance.update({
        "schema_version": 1,
        "kind": "phase8c_public_corpus_provenance",
        "benchmark_id": BENCHMARK_ID,
        "generated_at": FIXED_GENERATED_AT,
        "builder": "scripts/build_phase8c_corpus.py",
        "source_manifest": {"path": V1_MANIFEST, "sha256": _sha256_file(_rel(V1_MANIFEST))},
        "migration": {
            "report_sha256": manifest["provenance"]["migration_report_sha256"],
            "sample_count": len(v1_samples),
            "lossless": all(fact.get("lossless") for fact in migration_facts),
            "facts": migration_facts,
        },
        "sources": [
            {"path": relative, "sha256": _sha256_file(_rel(relative))}
            for relative in sorted(set(source_paths)) if _exists(relative)
        ],
        "dropped_samples": variant_records,
        "variant_attempts": provenance.get("variant_attempts") or [],
        "toolchain": provenance["toolchain"],
        "limitations": manifest["limitations"],
    })
    return manifest, provenance


def render_readme(manifest: Mapping[str, Any], provenance: Mapping[str, Any]) -> str:
    samples = manifest.get("samples") or []
    runtime = sum(
        1 for sample in samples
        if set((sample.get("oracle") or {}).get("kinds") or []) & RUNTIME_KINDS)
    analysis = sum(1 for sample in samples
                   if sample.get("expected_scope") == "analysis_only")
    lines = [
        "# Phase-8C public ground-truth corpus v2 (2026-11-16)",
        "",
        "Deterministic public corpus built by `scripts/build_phase8c_corpus.py` "
        "from committed fixtures, PoC manifests and reference fixes. No AI, no "
        "network, no wall clock. Hidden contents are never read or claimed.",
        "",
        f"- benchmark_id: `{manifest['benchmark_id']}`",
        f"- generated_at: `{manifest['generated_at']}` (fixed)",
        f"- samples: **{manifest['sample_count']}** "
        f"(dev {manifest['split_counts']['dev']} / "
        f"validation {manifest['split_counts']['validation']})",
        f"- oracle kinds: **{runtime} runtime-oracle** samples, "
        f"**{analysis} analysis-only** samples (core 28: 20 runtime / 8 analysis-only)",
        "- hidden_available: `false`; hidden commitment is owned by C4/C6 and is "
        "not created or read by this builder.",
        "",
        "## Split assignment",
        "",
        "| group | dev | validation | rule |",
        "|---|---|---|---|",
        "| v1 migrated (12) | 8 | 4 | v1 split preserved losslessly |",
        "| hard cases (6) | 3 | 3 | loop8/loop16/loop32 -> dev; "
        "loop64/reverse/heap-malloc -> validation |",
        "| repair-benchmark (6) | 3 | 3 | cwe122/cwe125/cwe134 -> dev; "
        "cwe190/cwe476/cwe787 -> validation |",
        "| cross-arch analysis-only (4) | 2 | 2 | Mach-O arm64/x86_64 -> dev; "
        "PE arm64/x64 -> validation |",
        "| compiler variants (validated only) | 2 | 2 | CWE122 -O2 dynamic "
        "(not-stripped/stripped) + CWE125 -O3/-Os static (strip) -> 2 dev / "
        "2 validation |",
        "",
        "## Samples",
        "",
        "| sample_id | split | format/arch | scope | oracle |",
        "|---|---|---|---|---|",
    ]
    for sample in samples:
        oracle = sample.get("oracle") or {}
        kind = str(oracle.get("kind") or "static")
        lines.append(
            f"| `{sample['sample_id']}` | {sample['split']} | "
            f"{sample['format']}/{sample['arch']}/{sample['bits']} | "
            f"{sample['expected_scope']} | {kind} |")
    dropped = [
        record for record in provenance.get("variants") or []
        if record.get("status") != "validated"
    ]
    lines += [
        "",
        "## Variants (C8)",
        "",
    ]
    validated = [
        record for record in provenance.get("variants") or []
        if record.get("status") == "validated"
    ]
    if validated:
        lines.append("| variant | source | compiler/flags | binary sha256 |")
        lines.append("|---|---|---|---|")
        for record in validated:
            lines.append(
                f"| `{record['sample_id']}` | `{record.get('source_sample')}` | "
                f"{record.get('compiler')} {' '.join(str(item) for item in record.get('flags') or [])} | "
                f"`{record.get('binary_sha256')}` |")
    else:
        lines.append("No compiler variant is currently committed as validated.")
    if dropped:
        lines += ["", "Dropped/not-run variant records (never faked):", ""]
        for record in dropped:
            lines.append(f"- `{record.get('sample_id')}`: {record.get('reason')}")
    attempts = [record for record in provenance.get("variant_attempts") or []
                if isinstance(record, dict)]
    if attempts:
        lines += ["", "Measured negative variant probes (explicitly dropped):", ""]
        for record in attempts:
            lines.append(
                f"- `{record.get('attempt_id')}` ({record.get('target')} "
                f"{record.get('optimization')}): {record.get('reason')}")
    lines += [
        "",
        "## Provenance and validation",
        "",
        f"- builder: `{provenance.get('builder')}`",
        f"- source digest: `{manifest['provenance']['source_digest_sha256']}`",
        f"- migration report sha256: "
        f"`{manifest['provenance']['migration_report_sha256']}`",
        f"- v1 migration: {provenance['migration']['sample_count']} samples, "
        f"lossless={provenance['migration']['lossless']}",
        f"- Zig toolchain: `{provenance['toolchain']['zig']['status']}`"
        + (f" ({provenance['toolchain']['zig'].get('reason')})"
           if provenance['toolchain']['zig'].get('reason') else ""),
        "- every runtime sample validates `poc.fixture_sha256 == binary sha256`; "
        "every reference fix digest is recomputed; analysis-only samples never "
        "declare a runtime oracle.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in manifest.get("limitations") or [])
    return "\n".join(lines) + "\n"


def build_artifacts() -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    manifest, provenance = build_manifest()
    readme = render_readme(manifest, provenance)
    files: dict[str, bytes] = {
        MANIFEST_NAME: _canonical_bytes(manifest),
        README_NAME: readme.encode("ascii"),
        PROVENANCE_NAME: _canonical_bytes(provenance),
    }
    bin_dir = PUBLIC_DIR / BIN_DIRNAME
    if bin_dir.is_dir():
        for path in sorted(bin_dir.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            files[path.relative_to(PUBLIC_DIR).as_posix()] = path.read_bytes()
    sums_lines = [
        f"{_sha256_bytes(files[relative])}  {relative}"
        for relative in sorted(files)
    ]
    files[SUMS_NAME] = ("\n".join(sums_lines) + "\n").encode("utf-8")
    return manifest, provenance, files


def write_artifacts(out_dir: Path, files: Mapping[str, bytes]) -> list[dict[str, str]]:
    written: list[dict[str, str]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for relative, payload in sorted(files.items()):
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        written.append({"path": str(target), "sha256": _sha256_bytes(payload)})
    return written


def check_artifacts(out_dir: Path) -> tuple[bool, list[str]]:
    manifest, provenance, fresh = build_artifacts()
    schema = _schema_violations(manifest)
    semantic = _semantic_violations(manifest)
    problems = [*schema, *semantic]
    for relative in (MANIFEST_NAME, README_NAME, PROVENANCE_NAME, SUMS_NAME):
        if not (out_dir / relative).is_file():
            problems.append(f"missing committed artifact {relative}")

    # Compare stable corpus content, not provenance bytes that intentionally
    # record the checking host's optional toolchain and the builder/source
    # digests.  A builder edit or a host without Zig must not make the committed
    # corpus look tampered; exact payload bytes are covered by SHA256SUMS below.
    def _stable_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
        view = dict(payload)
        view.pop("provenance", None)
        return view

    committed_manifest_path = out_dir / MANIFEST_NAME
    if committed_manifest_path.is_file():
        try:
            committed_manifest = _load_json(committed_manifest_path)
        except (OSError, json.JSONDecodeError):
            committed_manifest = None
        fresh_manifest = json.loads(fresh[MANIFEST_NAME].decode("utf-8"))
        if committed_manifest is not None and (
            _stable_manifest(committed_manifest) != _stable_manifest(fresh_manifest)
        ):
            problems.append("committed manifest content differs from rebuilt corpus")

    committed_prov_path = out_dir / PROVENANCE_NAME
    if committed_prov_path.is_file():
        try:
            committed_prov = _load_json(committed_prov_path)
        except (OSError, json.JSONDecodeError):
            committed_prov = None
        if committed_prov is not None:
            def _stable_provenance(payload: Mapping[str, Any]) -> dict[str, Any]:
                view = dict(payload)
                view.pop("toolchain", None)
                view.pop("sources", None)
                return view
            if _stable_provenance(committed_prov) != _stable_provenance(provenance):
                problems.append(
                    "committed provenance content differs from rebuilt corpus")

    committed_sums = out_dir / SUMS_NAME
    if committed_sums.is_file():
        listed: dict[str, str] = {}
        for line in committed_sums.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, relative = line.split(None, 1)
            listed[relative.strip()] = digest
        expected = {name for name in fresh if name != SUMS_NAME}
        if set(listed) != expected:
            problems.append(
                "SHA256SUMS entries do not match the artifact payload set")
        for relative, digest in listed.items():
            target = out_dir / relative
            if not target.is_file():
                problems.append(f"SHA256SUMS lists missing file {relative}")
            elif _sha256_file(target) != digest:
                problems.append(f"SHA256SUMS digest mismatch for {relative}")
    return (not problems), problems

def _summary(manifest: Mapping[str, Any], provenance: Mapping[str, Any],
             ok: bool, problems: list[str] | None = None) -> dict[str, Any]:
    samples = manifest.get("samples") or []
    runtime = sum(
        1 for sample in samples
        if set((sample.get("oracle") or {}).get("kinds") or []) & RUNTIME_KINDS)
    analysis = sum(1 for sample in samples
                   if sample.get("expected_scope") == "analysis_only")
    variants = [record for record in provenance.get("variants") or []
                if record.get("status") == "validated"]
    dropped = [record for record in provenance.get("variants") or []
               if record.get("status") != "validated"]
    return {
        "ok": ok,
        "benchmark_id": manifest.get("benchmark_id"),
        "sample_count": manifest.get("sample_count"),
        "core_sample_count": CORE_SAMPLE_COUNT,
        "variant_count": len(variants),
        "split_counts": manifest.get("split_counts"),
        "runtime_oracle_samples": runtime,
        "analysis_only_samples": analysis,
        "lossless_v1_migration": (
            provenance.get("migration") or {}).get("lossless"),
        "migrated_sample_count": (
            provenance.get("migration") or {}).get("sample_count"),
        "hidden_available": manifest.get("hidden_available"),
        "hidden_commitment": manifest.get("hidden_commitment"),
        "schema_validation": "ok" if not problems else "failed",
        "problems": problems or [],
        "variants": [
            {"sample_id": record.get("sample_id"), "status": record.get("status"),
             "reason": record.get("reason")}
            for record in dropped
        ],
        "variant_attempts": [
            {"attempt_id": record.get("attempt_id"), "status": record.get("status"),
             "reason": record.get("reason")}
            for record in provenance.get("variant_attempts") or []
        ],
        "compiler_variants": [
            {"sample_id": record.get("sample_id"),
             "binary_sha256": record.get("binary_sha256")}
            for record in variants
        ],
        "zig": provenance.get("toolchain", {}).get("zig"),
        "manifest_sha256": _sha256_bytes(_canonical_bytes(manifest)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build/check the Phase-8C public ground-truth corpus v2")
    parser.add_argument("--out", type=Path, default=PUBLIC_DIR)
    parser.add_argument("--write", action="store_true",
                        help="write the deterministic public artifacts")
    parser.add_argument("--check", action="store_true",
                        help="check the committed artifacts and schemas")
    parser.add_argument("--json", action="store_true",
                        help="print a JSON summary (does not write unless --write)")
    parser.add_argument("--build-variants", action="store_true",
                        help="attempt C8 compiler variants with Zig (writes bin/)")
    args = parser.parse_args(argv)
    if not (args.write or args.check or args.json or args.build_variants):
        args.write = True
    try:
        if args.build_variants:
            provenance_probe = {"toolchain": _variant_provenance(), "variants": []}
            # Build only when explicitly allowed; records dropped reasons.
            PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
            build_variants(allow_build=True, provenance=provenance_probe)
        if args.check:
            ok, problems = check_artifacts(args.out)
            manifest, provenance, _files = build_artifacts()
            summary = _summary(manifest, provenance, ok, problems)
            if args.json:
                print(json.dumps(summary, indent=2, ensure_ascii=False))
            else:
                print(json.dumps({"ok": ok, "problems": problems[:20]},
                                 indent=2, ensure_ascii=False))
            return 0 if ok else 1
        manifest, provenance, files = build_artifacts()
        problems = [*_schema_violations(manifest), *_semantic_violations(manifest)]
        if problems:
            if args.json:
                print(json.dumps(_summary(manifest, provenance, False, problems),
                                 indent=2, ensure_ascii=False))
            else:
                print(json.dumps({"ok": False, "problems": problems[:20]},
                                 indent=2, ensure_ascii=False))
            return 1
        if args.write:
            written = write_artifacts(args.out, files)
            print(json.dumps({
                "ok": True,
                "out": str(args.out),
                "written": written,
                "summary": _summary(manifest, provenance, True, []),
            }, indent=2, ensure_ascii=False))
            return 0
        print(json.dumps(_summary(manifest, provenance, True, []),
                         indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
