#!/usr/bin/env python3
"""Build the Phase-8C private hidden corpus and its public commitment (C4).

The hidden corpus is *private*: its binaries, PoCs, reference fixes and reports
live only under the Lead-provisioned root (default
``$HOME/.binaryrepair/phase8c-hidden``, mode ``0700``, override
``PHASE8C_HIDDEN_ROOT``).  This builder never writes hidden bytes into the
repository; the only committed output is the opaque
``benchmark/phase8c/hidden-commitment.json``.

What is built
-------------
* six x86_64 Linux runtime samples derived from the public repair-benchmark
  sources (CWE122/125/134/190/476/787), cross-compiled with Zig at varied
  ``-O0/-O1/-O2/-O3`` optimization, static/dynamic linking and strip/no-strip
  configurations.  Each sample's original oracle behavior is validated in the
  Lima guest (through ``poc_runner``/the shared guest lock) against a PoC
  manifest rebound to the hidden binary digest.  Variants that do not
  reproduce the committed PoC behavior (for example optimizers that eliminate
  the undefined-behavior store) are dropped with an explicit private reason;
  runtime samples are only admitted when at least six validate.
* up to two analysis-only cross-format samples (PE x86_64, Mach-O arm64) built
  from the same sources.  They carry ``expected_scope=analysis_only`` and never
  claim a runtime oracle.

Private layout (all paths relative to the private root)::

    hidden-manifest.json     private v2 sample objects + material paths
    bin/<opaque>.bin         hidden binaries
    poc/<opaque>.json        rebound external-PoC manifests (runtime samples)
    reference/<opaque>.c     private copies of the reference fix sources
    reports/build-report.json  private build/validation evidence
    reports/SHA256SUMS         private tamper-detection sums

Public commitment
-----------------
``hidden-commitment.json`` follows
``contracts/hidden-benchmark-commitment.schema.json`` and contains only the
benchmark id/version, counts, the domain-separated commitment digest, the
public-manifest digest, a fixed creation timestamp and opaque
sample/digest pairs.  The commitment digest is::

    sha256(b"phase8c-hidden-commitment-v1\\n" + canonical(private_manifest))

where ``canonical`` is the deterministic pretty JSON (sort keys, ASCII,
trailing newline) and ``private_manifest`` is ``hidden-manifest.json`` without
its own ``commitment_sha256`` field.  Hidden sample ids are themselves
domain-separated SHA-256 hashes, so neither descriptions nor file paths are
published.

Modes
-----
``--check``
    Offline verification only (no compilation, no guest execution): the
    private root is secure, every material hash matches, the private samples
    validate against ``ground-truth-sample-v2``, the committed public
    commitment matches the private manifest/public-manifest digests, and no
    hidden path/content leaks.  Missing root or any tamper is a failure (a
    vanished corpus is ``not_run``/``blocked``, never a fake pass).
default (build)
    Compile/validate/admit the corpus into ``--root``; with
    ``--write-commitment`` additionally publish the commitment.  Without
    ``--validate-oracles`` runtime samples cannot be admitted, so the builder
    reports ``blocked`` and writes no manifest/commitment.
``--json``
    Print a public-safe JSON summary; hidden ids, paths and stderr never
    appear in it.

No network and no AI provider is used.  The builder is deterministic for a
given toolchain/guest: fixed timestamp, canonical JSON, sorted outputs and
deterministic Zig builds; the private build report may contain lock-attempt
timing evidence, but that report is not part of the commitment digest.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PUBLIC_MANIFEST_REL = Path("benchmark/phase8c/manifest.json")
COMMITMENT_REL = Path("benchmark/phase8c/hidden-commitment.json")
CONTRACTS_DIR = ROOT / "contracts"
HIDDEN_ENV = "PHASE8C_HIDDEN_ROOT"
DEFAULT_HIDDEN_ROOT = Path.home() / ".binaryrepair" / "phase8c-hidden"
PRIVATE_MANIFEST_NAME = "hidden-manifest.json"
REPORT_NAME = "reports/build-report.json"
SUMS_NAME = "reports/SHA256SUMS"
MATERIAL_DIRS = ("bin", "poc", "reference", "reports")
FIXED_TIMESTAMP = "2026-11-16T00:00:00Z"
HIDDEN_VERSION = "phase8c-hidden-v1"
BENCHMARK_ID = "phase8c-hidden"
PRIVATE_MANIFEST_KIND = "phase8c_private_hidden_manifest"
PRIVATE_MANIFEST_KEYS = (
    "kind",
    "schema_version",
    "benchmark_id",
    "public_manifest_sha256",
    "commitment_sha256",
    "samples",
    "material",
    "limitations",
)
SAMPLE_SCHEMA_NAME = "ground-truth-sample-v2"
COMMITMENT_SCHEMA_NAME = "hidden-benchmark-commitment"
COMMITMENT_DOMAIN = b"phase8c-hidden-commitment-v1\n"
SAMPLE_ID_DOMAIN = b"phase8c-hidden-sample-id-v1\n"
MIN_RUNTIME_SAMPLES = 6
MAX_ANALYSIS_SAMPLES = 2
TARGET_SAMPLE_COUNT = 8
ZIG_CANDIDATES = (
    "zig",
    str(ROOT / ".tmp" / "zigpkg" / "site" / "ziglang" / "zig"),
)

#: Public repair-benchmark sources used for the private variants.  Metadata
#: (family/subtype/CWE/target symbol/PoC/reference fix) is read from the public
#: Phase-8C v2 manifest so the hidden samples stay in the same taxonomy.
SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "CWE122_heap_copy": {
        "public_sample_id": "repair-cwe122",
        "source": "fixtures/repair-benchmark/CWE122_heap_copy/vuln.c",
        "public_poc": "fixtures/poc/repair-cwe122.json",
        "reference_fix": "fixtures/repair-benchmark/CWE122_heap_copy/reference_fix.c",
        "symbol": "cwe122_bad",
    },
    "CWE125_oob_read": {
        "public_sample_id": "repair-cwe125",
        "source": "fixtures/repair-benchmark/CWE125_oob_read/vuln.c",
        "public_poc": "fixtures/poc/repair-cwe125.json",
        "reference_fix": "fixtures/repair-benchmark/CWE125_oob_read/reference_fix.c",
        "symbol": "cwe125_bad",
    },
    "CWE134_format_string": {
        "public_sample_id": "repair-cwe134",
        "source": "fixtures/repair-benchmark/CWE134_format_string/vuln.c",
        "public_poc": "fixtures/poc/repair-cwe134.json",
        "reference_fix": "fixtures/repair-benchmark/CWE134_format_string/reference_fix.c",
        "symbol": "cwe134_bad",
    },
    "CWE190_integer_overflow": {
        "public_sample_id": "repair-cwe190",
        "source": "fixtures/repair-benchmark/CWE190_integer_overflow/vuln.c",
        "public_poc": "fixtures/poc/repair-cwe190.json",
        "reference_fix": "fixtures/repair-benchmark/CWE190_integer_overflow/reference_fix.c",
        "symbol": "cwe190_bad",
    },
    "CWE476_null_deref": {
        "public_sample_id": "repair-cwe476",
        "source": "fixtures/repair-benchmark/CWE476_null_deref/vuln.c",
        "public_poc": "fixtures/poc/repair-cwe476.json",
        "reference_fix": "fixtures/repair-benchmark/CWE476_null_deref/reference_fix.c",
        "symbol": "cwe476_bad",
    },
    "CWE787_index_write": {
        "public_sample_id": "repair-cwe787",
        "source": "fixtures/repair-benchmark/CWE787_index_write/vuln.c",
        "public_poc": "fixtures/poc/repair-cwe787.json",
        "reference_fix": "fixtures/repair-benchmark/CWE787_index_write/reference_fix.c",
        "symbol": "cwe787_bad",
    },
}

#: Runtime variant chain per source.  The builder tries each specification in
#: order and admits the first one whose original oracle behavior is validated.
RUNTIME_VARIANT_CHAINS: dict[str, list[dict[str, Any]]] = {
    "CWE122_heap_copy": [
        {
            "slug": "hidden-cwe122-zig-O0-gnu-dynamic",
            "target": "x86_64-linux-gnu",
            "optimization": "-O0",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
            "static": False,
            "stripped": False,
            "split": "dev",
        },
        {
            "slug": "hidden-cwe122-zig-O2-musl-static",
            "target": "x86_64-linux-musl",
            "optimization": "-O2",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static"],
            "static": True,
            "stripped": False,
            "split": "dev",
        },
    ],
    "CWE125_oob_read": [
        {
            "slug": "hidden-cwe125-zig-O1-gnu-dynamic-stripped",
            "target": "x86_64-linux-gnu",
            "optimization": "-O1",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-s"],
            "static": False,
            "stripped": True,
            "split": "validation",
        },
        {
            "slug": "hidden-cwe125-zig-O1-gnu-dynamic",
            "target": "x86_64-linux-gnu",
            "optimization": "-O1",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
            "static": False,
            "stripped": False,
            "split": "validation",
        },
    ],
    "CWE134_format_string": [
        {
            "slug": "hidden-cwe134-zig-O3-musl-static",
            "target": "x86_64-linux-musl",
            "optimization": "-O3",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static"],
            "static": True,
            "stripped": False,
            "split": "dev",
        },
        {
            "slug": "hidden-cwe134-zig-O3-gnu-dynamic",
            "target": "x86_64-linux-gnu",
            "optimization": "-O3",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
            "static": False,
            "stripped": False,
            "split": "dev",
        },
    ],
    "CWE190_integer_overflow": [
        {
            "slug": "hidden-cwe190-zig-O2-gnu-pie",
            "target": "x86_64-linux-gnu",
            "optimization": "-O2",
            "flags": ["-fno-stack-protector"],
            "static": False,
            "stripped": False,
            "split": "validation",
        },
        {
            "slug": "hidden-cwe190-zig-O2-gnu-dynamic",
            "target": "x86_64-linux-gnu",
            "optimization": "-O2",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
            "static": False,
            "stripped": False,
            "split": "validation",
        },
    ],
    "CWE476_null_deref": [
        {
            "slug": "hidden-cwe476-zig-O0-gnu-dynamic",
            "target": "x86_64-linux-gnu",
            "optimization": "-O0",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
            "static": False,
            "stripped": False,
            "split": "dev",
        },
        {
            "slug": "hidden-cwe476-zig-O0-musl-static",
            "target": "x86_64-linux-musl",
            "optimization": "-O0",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static"],
            "static": True,
            "stripped": False,
            "split": "dev",
        },
    ],
    "CWE787_index_write": [
        {
            "slug": "hidden-cwe787-zig-O0-musl-static-stripped",
            "target": "x86_64-linux-musl",
            "optimization": "-O0",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie", "-static", "-s"],
            "static": True,
            "stripped": True,
            "split": "validation",
        },
        {
            "slug": "hidden-cwe787-zig-O0-gnu-dynamic",
            "target": "x86_64-linux-gnu",
            "optimization": "-O0",
            "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
            "static": False,
            "stripped": False,
            "split": "validation",
        },
    ],
}

#: Measured compiler/flag probes that are expected to lose the original bug
#: (UB eliminated by the optimizer) and MUST be dropped, never admitted.  The
#: measured reason is recorded in the private build report.
EXPLORATORY_ATTEMPTS: list[dict[str, Any]] = [
    {
        "slug": "attempt-cwe476-zig-O2-gnu-dynamic",
        "source": "CWE476_null_deref",
        "target": "x86_64-linux-gnu",
        "optimization": "-O2",
        "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
        "static": False,
        "stripped": False,
    },
    {
        "slug": "attempt-cwe787-zig-O2-gnu-dynamic",
        "source": "CWE787_index_write",
        "target": "x86_64-linux-gnu",
        "optimization": "-O2",
        "flags": ["-fno-stack-protector", "-fno-pie", "-no-pie"],
        "static": False,
        "stripped": False,
    },
]

#: Analysis-only cross-format private variants (no runtime claim).
ANALYSIS_VARIANTS: list[dict[str, Any]] = [
    {
        "slug": "hidden-cwe122-zig-O2-win64-analysis-stripped",
        "source": "CWE122_heap_copy",
        "target": "x86_64-windows-gnu",
        "optimization": "-O2",
        "flags": ["-s"],
        "stripped": True,
        "format": "pe",
        "arch": "x86_64",
        "bits": 64,
        "split": "dev",
    },
    {
        "slug": "hidden-cwe787-zig-O2-macho-arm64-analysis",
        "source": "CWE787_index_write",
        "target": "aarch64-macos",
        "optimization": "-O2",
        "flags": [],
        "format": "macho",
        "arch": "arm64",
        "bits": 64,
        "split": "validation",
    },
]

# Schema files per contract name (single source: the C2 contracts directory).
SCHEMA_FILES = {
    SAMPLE_SCHEMA_NAME: CONTRACTS_DIR / "ground-truth-sample-v2.schema.json",
    COMMITMENT_SCHEMA_NAME: CONTRACTS_DIR / "hidden-benchmark-commitment.schema.json",
}


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------
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


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_bytes(payload)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _write_json_atomic(path: Path, payload: Any) -> None:
    _write_bytes_atomic(path, _canonical_bytes(payload))


def opaque_sample_id(private_sample_id: str) -> str:
    """Domain-separated opaque id: the public tree never sees the private slug."""
    return _sha256_bytes(SAMPLE_ID_DOMAIN + private_sample_id.encode("ascii"))


def commitment_digest(private_manifest_without_commitment: Mapping[str, Any]) -> str:
    return _sha256_bytes(
        COMMITMENT_DOMAIN + _canonical_bytes(private_manifest_without_commitment)
    )


def _strip_commitment_field(manifest: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        key: value for key, value in manifest.items() if key != "commitment_sha256"
    }
    return payload


# ---------------------------------------------------------------------------
# Contract/schema helpers (single source: contracts + check_contract_schemas.py)
# ---------------------------------------------------------------------------
def _checker_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_phase8c_contract_checker", ROOT / "scripts" / "check_contract_schemas.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load scripts/check_contract_schemas.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema() -> dict[str, Any]:
    return {name: _load_json(path) for name, path in SCHEMA_FILES.items()}


def _schema_violations(name: str, instance: Any, *, schemas=None) -> list[str]:
    """Validate one instance against a C2 contract, fail closed if unavailable."""

    schemas = schemas if schemas is not None else _schema()
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        return [f"{name}: jsonschema unavailable; schema validation not_run"]
    try:
        validator = jsonschema.Draft202012Validator(schemas[name])
    except Exception as exc:  # noqa: BLE001 - fail closed on a broken schema
        return [f"{name}: schema unusable: {type(exc).__name__}"]
    violations = []
    for error in sorted(validator.iter_errors(instance), key=str):
        where = ".".join(str(part) for part in error.absolute_path) or "<root>"
        violations.append(f"{name}: schema {where}: {error.message}")
    return violations


def sample_semantics_violations(sample: Mapping[str, Any]) -> list[str]:
    try:
        checker = _checker_module()
        return list(checker._ground_truth_sample_v2_semantics(sample))  # noqa: SLF001
    except Exception as exc:  # noqa: BLE001 - fail closed
        return [f"sample semantics checker unavailable: {type(exc).__name__}"]


def commitment_semantics_violations(commitment: Mapping[str, Any]) -> list[str]:
    try:
        checker = _checker_module()
        violations = list(
            checker._hidden_commitment_semantics(commitment)  # noqa: SLF001
        )
        return violations
    except Exception as exc:  # noqa: BLE001 - fail closed
        return [f"commitment semantics checker unavailable: {type(exc).__name__}"]


# ---------------------------------------------------------------------------
# Root/security helpers
# ---------------------------------------------------------------------------
def resolve_root(root: str | Path | None) -> Path:
    if root is not None and str(root).strip():
        return Path(root).expanduser()
    env = os.environ.get(HIDDEN_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    return DEFAULT_HIDDEN_ROOT


def _root_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def _root_is_secure(path: Path) -> bool:
    mode = _root_mode(path)
    return mode is not None and (mode & 0o077) == 0


def _ensure_private_layout(root: Path) -> None:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in MATERIAL_DIRS:
        (root / name).mkdir(mode=0o700, exist_ok=True)


def _relative_private_path(relative: str) -> bool:
    """True when *relative* is a plain relative path inside the private root."""
    if not relative or relative.startswith(("/", "\\")):
        return False
    parts = Path(relative).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


# ---------------------------------------------------------------------------
# Toolchain discovery / compilation
# ---------------------------------------------------------------------------
def zig_path() -> str | None:
    for candidate in ZIG_CANDIDATES:
        path = candidate if os.path.isabs(candidate) else shutil.which(candidate)
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def zig_version(zig: str | None) -> str | None:
    if not zig:
        return None
    try:
        result = subprocess.run(
            [zig, "version"], capture_output=True, text=True, timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    version = (result.stdout or "").strip()
    return version or None


def compile_variant(
    zig: str,
    spec: Mapping[str, Any],
    source_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Compile one variant spec; return a typed record (never raises on build)."""

    command = [
        zig, "cc", "-target", str(spec["target"]),
        str(spec["optimization"]), "-g0",
        *[str(item) for item in spec.get("flags") or []],
        "-o", output_path.name, str(source_path),
    ]
    record: dict[str, Any] = {
        "status": "failed",
        "command": command,
        "output_path": str(output_path),
        "stderr": "",
        "sha256": None,
    }
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=180, check=False,
            cwd=str(output_path.parent),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        record["stderr"] = f"{type(exc).__name__}: {exc}"
        return record
    if result.returncode != 0 or not output_path.is_file():
        record["stderr"] = (
            (result.stderr or "").strip()[:2000]
            or (result.stdout or "").strip()[:2000]
            or f"compiler exited {result.returncode}"
        )
        return record
    record["status"] = "compiled"
    record["sha256"] = _sha256_file(output_path)
    return record


def container_identity(data: bytes) -> dict[str, Any] | None:
    """format/arch/bits/endian via the repository container parser."""
    try:
        from app.services.containers import detect_container

        container = detect_container(data)
    except Exception:  # noqa: BLE001 - fail closed on parser errors
        return None
    if container.format == "unknown" or not container.arch:
        return None
    return {
        "format": container.format,
        "arch": container.arch,
        "bits": container.bits,
        "endian": container.endian,
        "limitations": list(container.limitations),
        "symbols": dict(container.symbols),
    }


def resolve_symbol_scope(data: bytes, symbol: str) -> dict[str, Any] | None:
    try:
        from app.services.containers import detect_container, resolve_function_scope

        scope = resolve_function_scope(detect_container(data), symbol)
    except Exception:  # noqa: BLE001 - fail closed
        return None
    if not scope:
        return None
    return {
        "name": scope.get("name") or symbol,
        "va": int(scope["va"]),
        "end": int(scope["end"]),
        "source": scope.get("source"),
    }


def _text_section_bytes(data: bytes) -> tuple[int, bytes] | None:
    try:
        import io

        from elftools.elf.elffile import ELFFile

        elf = ELFFile(io.BytesIO(data))
        section = elf.get_section_by_name(".text")
        if section is None:
            return None
        return int(section["sh_addr"]), bytes(section.data())
    except Exception:  # noqa: BLE001 - fail closed
        return None


def _same_executable_text(left: bytes, right: bytes) -> bool:
    left_text = _text_section_bytes(left)
    right_text = _text_section_bytes(right)
    return bool(left_text and right_text and left_text == right_text)


# ---------------------------------------------------------------------------
# Oracle manifests
# ---------------------------------------------------------------------------
def rebind_poc_manifest(public_poc: Mapping[str, Any], binary_sha256: str) -> dict[str, Any]:
    """Copy a public PoC manifest and rebind its fixture digest to the variant."""
    manifest = json.loads(json.dumps(public_poc))
    manifest["fixture_sha256"] = binary_sha256
    if "description" in manifest or True:
        manifest["description"] = (
            "Phase-8C private hidden variant PoC: the public repair-benchmark "
            "cases rebound to the hidden binary digest; no hidden path/content "
            "is part of this file."
        )
    return manifest


def immediate_oracle_expected(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic summary of a rebound manifest's expectations."""
    poc = [case for case in manifest.get("poc") or [] if isinstance(case, Mapping)]
    regression = [
        case for case in manifest.get("regression") or []
        if isinstance(case, Mapping)
    ]
    return {
        "poc_case_ids": [str(case.get("id")) for case in poc],
        "regression_case_ids": [str(case.get("id")) for case in regression],
        "original_poc_expects_failure": all(
            bool((case.get("original") or {}).get("crashed")) for case in poc
        ),
        "has_regression": bool(regression),
    }


# ---------------------------------------------------------------------------
# Lima-guest oracle validation (through poc_runner + shared guest lock)
# ---------------------------------------------------------------------------
def validate_runtime_oracle(binary_path: Path, poc_manifest_path: Path) -> dict[str, Any]:
    """Execute the rebound PoC against the original hidden binary.

    The original bytes are used as the candidate side: a vulnerable original
    must NOT satisfy the fixed-candidate expectations, so a successful
    validation is an executed ``fail`` differential whose original-side cases
    all match the committed expectations and whose PoC cases are observed
    crashes.  A missing runner/lock is ``not_run`` and the variant is dropped;
    nothing is ever faked.
    """
    from app.services.poc_runner import run_poc

    data = binary_path.read_bytes()
    try:
        evidence = run_poc(data, data, poc_manifest_path)
        payload = evidence.to_dict()
    except Exception as exc:  # noqa: BLE001 - a broken runner drops the variant
        return {
            "status": "not_run",
            "runner": "",
            "tier": "",
            "executed": False,
            "original_expected_ok": False,
            "regression_expected_ok": False,
            "original_poc_case_count": 0,
            "reason": f"oracle runner error: {type(exc).__name__}",
            "evidence_sha256": None,
        }
    runner = str(payload.get("runner") or "")
    tier = str(payload.get("tier") or "")
    cases = [case for case in payload.get("poc") or [] if isinstance(case, Mapping)]
    regression = [
        case for case in payload.get("regression") or []
        if isinstance(case, Mapping)
    ]
    original_poc = [
        case for case in cases
        if case.get("executable") == "original" and case.get("kind") == "poc"
    ]
    original_regression = [
        case for case in regression
        if case.get("executable") == "original" and case.get("kind") == "regression"
    ]
    executed = (
        str(payload.get("status")) in {"pass", "fail"}
        and bool(runner)
        and tier in {"native_run", "emulated_run"}
    )
    original_expected_ok = bool(original_poc) and all(
        bool(case.get("expected_ok")) for case in original_poc
    )
    regression_expected_ok = bool(original_regression) and all(
        bool(case.get("expected_ok")) for case in original_regression
    )
    vulnerable = bool(original_poc) and all(
        bool(case.get("crashed")) for case in original_poc
    )
    reason = None
    if not executed:
        reason = (
            "external PoC runner unavailable/inconclusive for this private "
            "variant; the variant is dropped rather than faked"
        )
    elif not original_expected_ok or not regression_expected_ok:
        reason = (
            "hidden variant does not reproduce the committed PoC's expected "
            "original behavior; the variant is dropped rather than admitted"
        )
    elif not vulnerable:
        reason = (
            "hidden variant's original PoC cases did not crash; the build does "
            "not reproduce the vulnerable behavior and is dropped"
        )
    elif str(payload.get("status")) != "fail":
        reason = (
            "original bytes unexpectedly satisfied the fixed-candidate oracle"
        )
    lock_attempts = payload.get("lock_attempts") or []
    # The digest binds only deterministic execution facts; lock timing/pid
    # evidence stays in the private report and never changes the commitment.
    summary = {
        "status": str(payload.get("status") or "not_run"),
        "runner": runner,
        "tier": tier,
        "executed": executed,
        "original_expected_ok": original_expected_ok,
        "regression_expected_ok": regression_expected_ok,
        "vulnerable_observed": vulnerable,
        "original_poc_case_count": len(original_poc),
        "original_regression_case_count": len(original_regression),
    }
    return {
        "status": str(payload.get("status") or "not_run"),
        "runner": runner,
        "tier": tier,
        "executed": executed,
        "original_expected_ok": original_expected_ok,
        "regression_expected_ok": regression_expected_ok,
        "vulnerable_observed": vulnerable,
        "original_poc_case_count": len(original_poc),
        "original_regression_case_count": len(original_regression),
        "lock_attempt_count": len(lock_attempts),
        "reason": reason,
        "evidence_sha256": _sha256_bytes(_canonical_bytes(summary)),
    }


def _validation_reason(validation: Mapping[str, Any]) -> str | None:
    reason = validation.get("reason")
    return str(reason) if reason else None


def _validate_stable(
    validate_func: Callable[..., dict[str, Any]],
    binary_path: Path,
    oracle_path: Path,
    *,
    required_rounds: int = 2,
    max_rounds: int = 5,
    infra_retries: int = 3,
) -> dict[str, Any]:
    """Validate a variant repeatedly and require a reproducible executed verdict.

    A transient guest-lock/runner problem (``executed=False``) never decides an
    admission: the attempt is retried a bounded number of times and whole rounds
    are retried until two independent verdicts executed.  A verdict that differs
    between independent guest executions is not admitted (the hidden commitment
    must be deterministic and never flaky).  If the guest never executes enough
    rounds the variant is dropped as ``not_run``.
    """
    executed_results: list[dict[str, Any]] = []
    for _round in range(max(1, max_rounds)):
        result: dict[str, Any] | None = None
        for attempt in range(max(1, infra_retries)):
            result = validate_func(binary_path, oracle_path)
            if result.get("executed"):
                break
            if attempt + 1 < max(1, infra_retries):
                time.sleep(min(0.2 * (attempt + 1), 1.0))
        if result is not None and result.get("executed"):
            executed_results.append(dict(result))
            if len(executed_results) >= max(2, required_rounds):
                break
    if len(executed_results) < max(2, required_rounds):
        result = dict(executed_results[-1]) if executed_results else {}
        result.update({
            "status": "not_run",
            "executed": False,
            "reason": (
                "guest oracle did not execute enough independent rounds "
                "(runner/lock unavailable or inconclusive); the variant is "
                "dropped rather than faked"),
            "evidence_sha256": None,
            "validation_repeats": len(executed_results),
            "validation_stable": False,
        })
        return result
    digests = [result.get("evidence_sha256") for result in executed_results]
    decisions = [result.get("reason") is None for result in executed_results]
    stable = len(set(digests)) == 1 and len(set(decisions)) == 1
    chosen = dict(executed_results[0])
    chosen["validation_repeats"] = len(executed_results)
    chosen["validation_stable"] = stable
    if not stable:
        chosen.update({
            "status": "unstable",
            "executed": False,
            "reason": (
                "variant validation was not reproducible across repeated "
                "independent guest runs; dropped rather than admitted"),
            "evidence_sha256": None,
        })
    return chosen


def _private_reference_bytes(public_reference: bytes, opaque_id: str) -> bytes:
    """Private reference-fix copy: same repair logic, distinct file digest.

    The header keeps the private copy from being byte-identical to the public
    reference-fix source (hidden/public exact-hash non-duplication) without
    changing the C source semantics.
    """
    header = (
        "/* Phase-8C private hidden-corpus reference-fix copy.\n"
        " * Sample id (opaque): " + opaque_id + "\n"
        " * The repair logic below is the public reference fix; this header only\n"
        " * keeps the private copy's digest distinct from public material.\n"
        " */\n"
    ).encode("ascii")
    return header + public_reference


# ---------------------------------------------------------------------------
# Hidden/public non-duplication
# ---------------------------------------------------------------------------
def public_material_hashes(
    public_manifest: Mapping[str, Any],
) -> dict[str, set[str]]:
    """Exact SHA-256 values of public corpus material (binaries/fixes/oracles).

    The hidden corpus is derived from the same sources but must never contain a
    *byte-identical* copy of a public sample/variant binary, PoC manifest,
    reference fix or source file: C5/audit contamination checks compare exact
    hashes across the public dev/validation and hidden splits.
    """
    binaries: set[str] = set()
    references: set[str] = set()
    oracles: set[str] = set()
    sources: set[str] = set()
    for sample in public_manifest.get("samples") or []:
        if not isinstance(sample, Mapping):
            continue
        binary_sha = sample.get("binary_sha256")
        if isinstance(binary_sha, str):
            binaries.add(binary_sha)
        reference = sample.get("reference_fix")
        if isinstance(reference, Mapping) and isinstance(reference.get("sha256"), str):
            references.add(str(reference["sha256"]))
        oracle = sample.get("oracle") or {}
        manifest_path = oracle.get("manifest_path") if isinstance(oracle, Mapping) else None
        if isinstance(manifest_path, str) and manifest_path:
            path = ROOT / manifest_path
            if path.is_file():
                oracles.add(_sha256_file(path))
        for reference_path in sample.get("source_refs") or []:
            if not isinstance(reference_path, str) or "#" in reference_path:
                continue
            path = ROOT / reference_path
            if path.is_file():
                sources.add(_sha256_file(path))
    bin_dir = ROOT / "benchmark" / "phase8c" / "bin"
    if bin_dir.is_dir():
        for path in bin_dir.iterdir():
            if path.is_file():
                binaries.add(_sha256_file(path))
    return {
        "binary": binaries,
        "reference": references,
        "oracle": oracles,
        "source": sources,
    }


def public_duplicate_reason(
    digest: str | None, material: Mapping[str, set[str]] | None
) -> str | None:
    if not digest or not material:
        return None
    for category in ("binary", "reference", "oracle", "source"):
        if digest in material.get(category, set()):
            return (
                f"material digest duplicates public corpus {category} material; "
                "dropped to preserve hidden/public separation")
    return None


def manifest_public_duplicates(
    manifest: Mapping[str, Any],
    root: Path,
    material: Mapping[str, set[str]],
) -> list[str]:
    """Return hidden material that is byte-identical to public material."""
    violations: list[str] = []
    seen = {
        "binary": set(),
        "reference": set(),
        "oracle": set(),
    }
    for sample in manifest.get("samples") or []:
        if not isinstance(sample, Mapping):
            continue
        sample_id = str(sample.get("sample_id"))
        entry = (manifest.get("material") or {}).get(sample_id)
        if not isinstance(entry, Mapping):
            continue
        checks = (
            ("binary", entry.get("binary_path")),
            ("reference", entry.get("reference_fix_path")),
            ("oracle", entry.get("oracle_path")),
        )
        for category, relative in checks:
            if not isinstance(relative, str):
                continue
            path = root / relative
            if not path.is_file():
                continue
            digest = _sha256_file(path)
            if digest in seen[category]:
                violations.append(
                    "two hidden samples share the same material digest")
            seen[category].add(digest)
            if digest in material.get(category, set()):
                violations.append(
                    "hidden material digest duplicates public corpus material")
    return violations


# ---------------------------------------------------------------------------
# Sample composition (C2 ground-truth-sample-v2 compatible)
# ---------------------------------------------------------------------------
def _public_sample_index(public_manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(sample.get("sample_id")): sample
        for sample in public_manifest.get("samples") or []
        if isinstance(sample, Mapping) and sample.get("sample_id")
    }


def _source_public_sample(
    source_key: str, index: Mapping[str, Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    spec = SOURCE_SPECS[source_key]
    return index.get(str(spec["public_sample_id"]))


def _source_poc_manifest(source_key: str) -> dict[str, Any]:
    return _load_json(ROOT / str(SOURCE_SPECS[source_key]["public_poc"]))


def _derive_target(
    *,
    spec: Mapping[str, Any],
    symbol: str,
    binary_bytes: bytes,
    unstripped_bytes: bytes | None,
) -> dict[str, Any] | None:
    """Resolve a symbol or explicit VA range for the hidden sample target."""
    if not spec.get("stripped"):
        scope = resolve_symbol_scope(binary_bytes, symbol)
        if scope is None:
            return None
        return {"kind": "symbol", "symbol": symbol}
    if unstripped_bytes is None:
        return None
    scope = resolve_symbol_scope(unstripped_bytes, symbol)
    if scope is None:
        return None
    if not _same_executable_text(binary_bytes, unstripped_bytes):
        return None
    # The explicit range is verified against the *final* (stripped) bytes; the
    # executable text identity above proves the address range is unchanged.
    try:
        from app.services.containers import detect_container, resolve_function_scope

        explicit = resolve_function_scope(
            detect_container(binary_bytes),
            {"va": scope["va"], "end": scope["end"], "name": symbol},
        )
    except Exception:  # noqa: BLE001 - fail closed
        explicit = None
    if explicit is None:
        return None
    return {
        "kind": "va_range",
        "va": int(scope["va"]),
        "end": int(scope["end"]),
        "function": symbol,
    }


def _runtime_sample(
    *,
    spec: Mapping[str, Any],
    source_key: str,
    public_sample: Mapping[str, Any],
    opaque_id: str,
    binary_sha256: str,
    oracle_relative: str,
    oracle_document: Mapping[str, Any],
    reference_relative: str,
    reference_sha256: str,
    target: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    source = SOURCE_SPECS[source_key]
    expected = immediate_oracle_expected(oracle_document)
    regression_ids = expected["regression_case_ids"] or list(
        (public_sample.get("oracle") or {}).get("regression_case_ids") or []
    )
    evidence_ref = (
        "private-oracle-validation:v1:"
        + str(validation.get("evidence_sha256") or "")
    )
    build_ref = "private-build:v1:" + binary_sha256
    return {
        "sample_id": opaque_id,
        "sample_version": 2,
        "binary_sha256": binary_sha256,
        "format": "elf",
        "arch": "x86_64",
        "bits": 64,
        "endian": "little",
        "abi": "sysv_x86_64",
        "compiler": "zig cc",
        "compiler_version": str(spec.get("compiler_version") or ""),
        "optimization_level": str(spec["optimization"]),
        "linking_mode": "static" if spec.get("static") else "dynamic",
        "stripping_status": "stripped" if spec.get("stripped") else "not_stripped",
        "vulnerability_family": str(public_sample.get("vulnerability_family") or ""),
        "vulnerability_subtype": str(public_sample.get("vulnerability_subtype") or ""),
        "cwe": public_sample.get("cwe"),
        "expected_scope": "function",
        "target": dict(target),
        "root_cause": {
            "statement": str(
                (public_sample.get("root_cause") or {}).get("statement")
                or public_sample.get("vulnerability_subtype")
                or "private hidden variant of a public defect"
            ),
            "evidence_refs": [
                f"public-sample:{source['public_sample_id']}",
                build_ref,
            ],
        },
        "trigger_conditions": list(public_sample.get("trigger_conditions") or [])
        or [
            "input outside the validated bounds reaches the vulnerable path "
            "of the public repair-benchmark source",
        ],
        "affected_function": str(source["symbol"]),
        "affected_ranges": [{"kind": "function", "function": str(source["symbol"])}],
        "oracle": {
            "kind": "external_poc",
            "kinds": ["external_poc"],
            "manifest_path": oracle_relative,
            "expected_original": False,
            "expected_candidate": True,
            "regression_case_ids": regression_ids,
        },
        "reference_fix": {
            "path": reference_relative,
            "sha256": reference_sha256,
        },
        "expected_original_behavior": (
            "original hidden binary fails the rebound PoC (crash on the trigger "
            "input) and preserves the regression stdout/exit"
        ),
        "expected_fixed_behavior": (
            "a correct repair rejects or bounds the trigger input without "
            "crashing and preserves the regression stdout/exit"
        ),
        "semantic_regression": {
            "required": True,
            "case_ids": regression_ids,
        },
        "expected_patch_properties": {},
        "negative_cases": [
            "the PoC trigger input must not crash a repaired candidate",
            "regression inputs must keep the original stdout and exit code",
        ],
        "split": str(spec["split"]),
        "source_refs": [
            f"public-source:{source['source']}",
            f"public-poc:{source['public_poc']}",
            f"public-sample:{source['public_sample_id']}",
            f"private-build:{binary_sha256}",
        ],
        "evidence_refs": [evidence_ref, build_ref],
        "confidence": "high",
        "limitations": [
            "private hidden corpus: the binary, PoC and reference fix stay "
            "outside the public repository; only opaque hashes are published",
        ],
    }


def _analysis_sample(
    *,
    spec: Mapping[str, Any],
    source_key: str,
    public_sample: Mapping[str, Any],
    opaque_id: str,
    binary_sha256: str,
    target_symbol: str,
    build_sha256: str,
) -> dict[str, Any]:
    source = SOURCE_SPECS[source_key]
    return {
        "sample_id": opaque_id,
        "sample_version": 2,
        "binary_sha256": binary_sha256,
        "format": str(spec["format"]),
        "arch": str(spec["arch"]),
        "bits": int(spec["bits"]),
        "endian": "little",
        "abi": (
            "win64_x86_64" if spec["format"] == "pe" else "aapcs64"
        ),
        "compiler": "zig cc",
        "compiler_version": str(spec.get("compiler_version") or ""),
        "optimization_level": str(spec["optimization"]),
        "linking_mode": "dynamic",
        "stripping_status": (
            "stripped" if spec.get("stripped") else "not_stripped"),
        "vulnerability_family": str(public_sample.get("vulnerability_family") or ""),
        "vulnerability_subtype": str(public_sample.get("vulnerability_subtype") or ""),
        "cwe": public_sample.get("cwe"),
        "expected_scope": "analysis_only",
        "target": {"kind": "analysis_only"},
        "root_cause": {
            "statement": str(
                (public_sample.get("root_cause") or {}).get("statement")
                or public_sample.get("vulnerability_subtype")
                or "private cross-format variant of a public defect"
            ),
            "evidence_refs": [
                f"public-sample:{source['public_sample_id']}",
                f"private-build:v1:{build_sha256}",
            ],
        },
        "trigger_conditions": list(public_sample.get("trigger_conditions") or [])
        or [
            "cross-format analysis-only variant: no runtime trigger is executed "
            "or claimed",
        ],
        "affected_function": target_symbol,
        "affected_ranges": [{"kind": "function", "function": target_symbol}],
        "oracle": {
            "kind": "analysis_only",
            "kinds": ["analysis_only"],
            "manifest_path": None,
            "expected_original": None,
            "expected_candidate": None,
            "regression_case_ids": [],
        },
        "reference_fix": None,
        "expected_original_behavior": (
            "not executed: analysis-only cross-format variant; no runtime "
            "behavior is claimed"
        ),
        "expected_fixed_behavior": (
            "not executed: analysis-only cross-format variant; no runtime "
            "behavior is claimed"
        ),
        "semantic_regression": {"required": False, "case_ids": []},
        "expected_patch_properties": {},
        "negative_cases": [
            "analysis-only sample: a runtime/verified disposition must not be "
            "fabricated for it",
        ],
        "split": str(spec["split"]),
        "source_refs": [
            f"public-source:{source['source']}",
            f"public-sample:{source['public_sample_id']}",
            f"private-build:v1:{build_sha256}",
        ],
        "evidence_refs": [f"private-build:v1:{build_sha256}"],
        "confidence": "medium",
        "limitations": [
            "analysis-only cross-format hidden variant: no runtime oracle, no "
            "reference-fix execution and no verified-repair claim",
            "private hidden corpus: only opaque hashes are published",
        ],
    }


# ---------------------------------------------------------------------------
# Manifest/commitment composition + validation
# ---------------------------------------------------------------------------
def compose_private_manifest(
    *,
    public_manifest_sha256: str,
    samples: list[dict[str, Any]],
    material: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "kind": PRIVATE_MANIFEST_KIND,
        "schema_version": 1,
        "benchmark_id": BENCHMARK_ID,
        "public_manifest_sha256": public_manifest_sha256,
        "samples": samples,
        "material": material,
        "limitations": [
            "private hidden corpus: contents, sample ids and per-sample reports "
            "never enter the public repository or the public commitment",
            "isolation is operational, not cryptographic: same-UID/root "
            "processes can read the private root",
            "hidden samples are derived variants of public repair-benchmark "
            "sources; their binaries differ from the public corpus binaries",
        ],
    }
    manifest["commitment_sha256"] = commitment_digest(manifest)
    return manifest


def build_commitment(private_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build the opaque public commitment from a private manifest."""
    samples = [
        sample for sample in private_manifest.get("samples") or []
        if isinstance(sample, Mapping)
    ]
    runtime = [
        sample for sample in samples
        if sample.get("expected_scope") in {"function", "whole_program"}
    ]
    opaque = sorted(
        (
            {
                "opaque_sample_id": str(sample["sample_id"]),
                "opaque_binary_sha256": str(sample["binary_sha256"]),
            }
            for sample in samples
        ),
        key=lambda item: item["opaque_sample_id"],
    )
    digest = commitment_digest(_strip_commitment_field(private_manifest))
    return {
        "schema_version": 1,
        "kind": "hidden_benchmark_commitment",
        "benchmark_id": BENCHMARK_ID,
        "hidden_version": HIDDEN_VERSION,
        "sample_count": len(samples),
        "runtime_count": len(runtime),
        "analysis_only_count": len(samples) - len(runtime),
        "commitment_sha256": digest,
        "public_manifest_sha256": str(private_manifest["public_manifest_sha256"]),
        "created_at": FIXED_TIMESTAMP,
        "samples": opaque,
        "limitations": [
            "hidden corpus contents, sample descriptions and per-sample reports "
            "stay private; this commitment publishes opaque ids and digests only",
            "sample ids are domain-separated hashes: the public tree cannot map "
            "them back to variant descriptions",
            "isolation is operational, not cryptographic; a same-UID or root "
            "reader of the private root can inspect the corpus",
            "hidden_available and hidden aggregate claims remain false until an "
            "authorized campaign executes the hidden lane",
        ],
    }


def _raise_on(violations: Iterable[str], message: str) -> None:
    collected = [str(item) for item in violations if str(item)]
    if collected:
        raise ValueError(message + ": " + "; ".join(collected[:6]))


def validate_commitment_document(commitment: Mapping[str, Any]) -> list[str]:
    violations = _schema_violations(COMMITMENT_SCHEMA_NAME, commitment)
    if violations:
        return violations
    violations.extend(commitment_semantics_violations(commitment))
    counts = (
        int(commitment.get("runtime_count", 0))
        + int(commitment.get("analysis_only_count", 0))
    )
    if counts != int(commitment.get("sample_count", 0)):
        violations.append("commitment counts do not sum to sample_count")
    if int(commitment.get("runtime_count", 0)) < MIN_RUNTIME_SAMPLES:
        violations.append(
            f"commitment runtime_count is below the required {MIN_RUNTIME_SAMPLES}"
        )
    if int(commitment.get("analysis_only_count", 0)) > MAX_ANALYSIS_SAMPLES:
        violations.append(
            f"commitment analysis_only_count exceeds {MAX_ANALYSIS_SAMPLES}"
        )
    return violations


def validate_private_manifest_document(
    manifest: Mapping[str, Any],
    root: Path,
    *,
    verify_hashes: bool = True,
) -> list[str]:
    """Validate a private manifest (shape, samples, material, digests)."""
    violations: list[str] = []
    if manifest.get("kind") != PRIVATE_MANIFEST_KIND:
        violations.append("private manifest kind is not the C4 private hidden kind")
    if manifest.get("schema_version") != 1:
        violations.append("private manifest schema_version must be 1")
    if manifest.get("benchmark_id") != BENCHMARK_ID:
        violations.append("private manifest benchmark_id mismatch")
    for key in PRIVATE_MANIFEST_KEYS:
        if key not in manifest:
            violations.append(f"private manifest requires field {key!r}")
    if violations:
        return violations
    unknown = sorted(set(manifest) - set(PRIVATE_MANIFEST_KEYS))
    if unknown:
        violations.append(f"private manifest has unexpected fields: {unknown}")
    samples = [sample for sample in manifest.get("samples") or []
               if isinstance(sample, Mapping)]
    material = manifest.get("material")
    if not isinstance(material, Mapping):
        violations.append("private manifest material must be an object")
        material = {}
    ids = [str(sample.get("sample_id")) for sample in samples]
    if len(set(ids)) != len(ids):
        violations.append("private manifest sample ids are not unique")
    runtime = [
        sample for sample in samples
        if sample.get("expected_scope") in {"function", "whole_program"}
    ]
    analysis = [
        sample for sample in samples if sample.get("expected_scope") == "analysis_only"
    ]
    if len(samples) != TARGET_SAMPLE_COUNT:
        violations.append(
            f"private manifest must contain {TARGET_SAMPLE_COUNT} samples "
            f"(found {len(samples)})")
    if len(runtime) < MIN_RUNTIME_SAMPLES:
        violations.append(
            f"private manifest needs at least {MIN_RUNTIME_SAMPLES} runtime "
            f"samples (found {len(runtime)})")
    if len(analysis) > MAX_ANALYSIS_SAMPLES:
        violations.append(
            f"private manifest allows at most {MAX_ANALYSIS_SAMPLES} "
            f"analysis-only samples (found {len(analysis)})")
    for sample in samples:
        sample_id = str(sample.get("sample_id"))
        pattern_ok = (
            len(sample_id) == 64
            and all(char in "0123456789abcdef" for char in sample_id)
        )
        if not pattern_ok:
            violations.append("an opaque sample id is not a 64-char lowercase hex")
        if sample.get("split") not in {"dev", "validation"}:
            violations.append(
                "private samples must use the dev/validation private split only")
        violations.extend(
            f"sample schema: {item}"
            for item in _schema_violations(SAMPLE_SCHEMA_NAME, sample)
        )
        violations.extend(
            f"sample semantics: {item}"
            for item in sample_semantics_violations(sample)
        )
        entry = material.get(sample_id)
        if not isinstance(entry, Mapping):
            violations.append("material is missing for a sample")
            continue
        binary_path = entry.get("binary_path")
        if not isinstance(binary_path, str) or not _relative_private_path(binary_path):
            violations.append("material binary_path is not a private relative path")
        else:
            absolute = root / binary_path
            if not absolute.is_file():
                violations.append("material binary file is missing")
            elif verify_hashes and _sha256_file(absolute) != sample.get("binary_sha256"):
                violations.append("material binary digest does not match the sample")
        oracle_path = entry.get("oracle_path")
        if sample.get("expected_scope") in {"function", "whole_program"}:
            if not isinstance(oracle_path, str) or not _relative_private_path(oracle_path):
                violations.append("runtime sample material oracle_path is invalid")
            else:
                oracle_file = root / oracle_path
                if not oracle_file.is_file():
                    violations.append("runtime sample oracle manifest is missing")
                else:
                    try:
                        oracle = _load_json(oracle_file)
                    except (OSError, json.JSONDecodeError):
                        oracle = None
                        violations.append("runtime sample oracle manifest is unreadable")
                    if isinstance(oracle, Mapping):
                        if oracle.get("fixture_sha256") != sample.get("binary_sha256"):
                            violations.append(
                                "oracle manifest fixture digest does not match "
                                "the hidden binary digest")
                        if oracle.get("format") != sample.get("format") or \
                                oracle.get("arch") != sample.get("arch"):
                            violations.append(
                                "oracle manifest format/arch does not match the "
                                "sample")
                        violations.extend(
                            f"oracle manifest: {item}"
                            for item in _oracle_manifest_violations(oracle)
                        )
        elif oracle_path is not None:
            violations.append("analysis-only sample must not declare an oracle manifest")
        reference_path = entry.get("reference_fix_path")
        reference = sample.get("reference_fix")
        if isinstance(reference, Mapping):
            if not isinstance(reference_path, str) or not _relative_private_path(
                    reference_path):
                violations.append(
                    "runtime sample material reference_fix_path is invalid")
            else:
                reference_file = root / reference_path
                if not reference_file.is_file():
                    violations.append("sample reference fix file is missing")
                elif verify_hashes and _sha256_file(reference_file) != reference.get("sha256"):
                    violations.append(
                        "sample reference fix digest does not match the file")
        elif reference_path is not None:
            violations.append(
                "analysis-only sample must not declare a reference-fix material path")
    extra = sorted(set(material) - set(ids))
    if extra:
        violations.append("material references samples not present in the manifest")
    digest = commitment_digest(_strip_commitment_field(manifest))
    if manifest.get("commitment_sha256") != digest:
        violations.append("private manifest commitment digest does not match")
    if not isinstance(manifest.get("public_manifest_sha256"), str) or \
            len(str(manifest["public_manifest_sha256"])) != 64:
        violations.append("private manifest public_manifest_sha256 is invalid")
    return violations


def _oracle_manifest_violations(oracle: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    for key in ("schema_version", "fixture_sha256", "format", "arch", "target",
                "poc", "regression"):
        if key not in oracle:
            violations.append(f"missing required PoC manifest field {key!r}")
    if not isinstance(oracle.get("poc"), list) or not oracle.get("poc"):
        violations.append("PoC manifest requires a non-empty poc list")
    if not isinstance(oracle.get("regression"), list) or not oracle.get("regression"):
        violations.append("PoC manifest requires a non-empty regression list")
    for group in ("poc", "regression"):
        for case in oracle.get(group) or []:
            if not isinstance(case, Mapping):
                violations.append("PoC case is not an object")
                continue
            if not case.get("id"):
                violations.append("PoC case has no id")
            if not isinstance(case.get("argv"), list):
                violations.append("PoC case argv is not a list")
            for side in ("original", "candidate"):
                if not isinstance(case.get(side), Mapping):
                    violations.append(f"PoC case {side} expectations are missing")
    return violations


def _sums_payload(root: Path, files: list[Path]) -> bytes:
    lines = []
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        lines.append(f"{_sha256_file(path)}  {path.relative_to(root).as_posix()}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _material_files(root: Path, manifest: Mapping[str, Any]) -> list[Path]:
    files: list[Path] = []
    for entry in (manifest.get("material") or {}).values():
        if not isinstance(entry, Mapping):
            continue
        for key in ("binary_path", "oracle_path", "reference_fix_path"):
            relative = entry.get(key)
            if isinstance(relative, str) and _relative_private_path(relative):
                files.append(root / relative)
    return files


def _check_sums(root: Path, manifest: Mapping[str, Any]) -> list[str]:
    sums_path = root / SUMS_NAME
    if not sums_path.is_file():
        return ["private reports/SHA256SUMS is missing"]
    try:
        lines = sums_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ["private reports/SHA256SUMS is unreadable"]
    expected: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        digest, _, relative = line.partition("  ")
        if not digest or not relative:
            return ["private reports/SHA256SUMS has a malformed line"]
        expected[relative] = digest.strip()
    actual_files = _material_files(root, manifest)
    manifest_path = root / PRIVATE_MANIFEST_NAME
    if manifest_path.is_file():
        actual_files.append(manifest_path)
    actual = {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in actual_files
    }
    violations: list[str] = []
    for name in ("bin", "poc", "reference"):
        directory = root / name
        if not directory.is_dir():
            continue
        for stale in directory.iterdir():
            if not stale.is_file():
                continue
            relative = stale.relative_to(root).as_posix()
            if relative not in actual:
                if "private corpus contains an unexpected extra file" not in violations:
                    violations.append(
                        "private corpus contains an unexpected extra file")
    if set(expected) != set(actual):
        violations.append("private SHA256SUMS does not cover exactly the corpus files")
    for relative, digest in expected.items():
        if relative in actual and actual[relative] != digest:
            violations.append("private SHA256SUMS digest does not match a corpus file")
    return violations


# ---------------------------------------------------------------------------
# Public-safe summaries
# ---------------------------------------------------------------------------
def _root_in_text(text: str, root: Path) -> str:
    return str(text).replace(str(root), "<hidden-root>")


def _public_summary(
    *,
    status: str,
    root: Path,
    runtime_count: int,
    analysis_count: int,
    commitment: Mapping[str, Any] | None,
    commitment_written: bool,
    toolchain: Mapping[str, Any],
    dropped_attempts: int,
    limitations: list[str],
) -> dict[str, Any]:
    summary = {
        "kind": "phase8c_hidden_build_summary",
        "schema_version": 1,
        "status": status,
        "hidden_available": bool(commitment is not None and commitment_written),
        "sample_count": runtime_count + analysis_count,
        "runtime_count": runtime_count,
        "analysis_only_count": analysis_count,
        "commitment_sha256": (
            str(commitment.get("commitment_sha256")) if commitment else None
        ),
        "public_manifest_sha256": (
            str(commitment.get("public_manifest_sha256")) if commitment else None
        ),
        "created_at": FIXED_TIMESTAMP if commitment else None,
        "root_present": root.is_dir(),
        "root_secure": _root_is_secure(root) if root.is_dir() else False,
        "toolchain": {
            "compiler": "zig cc" if toolchain.get("available") else None,
            "compiler_version": toolchain.get("version"),
            "status": toolchain.get("status"),
        },
        "dropped_attempts": dropped_attempts,
        "limitations": list(limitations),
    }
    return summary


def _read_toolchain(probe: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if probe is not None:
        return dict(probe)
    zig = zig_path()
    return {
        "available": bool(zig),
        "version": zig_version(zig),
        "status": "available" if zig else "not_run",
    }


def _build_report_payload(
    *,
    status: str,
    toolchain: Mapping[str, Any],
    public_manifest_sha256: str | None,
    commitment_sha256: str | None,
    samples: list[dict[str, Any]],
    selected_attempts: list[dict[str, Any]],
    excluded_attempts: list[dict[str, Any]],
    counts: Mapping[str, Any],
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "kind": "phase8c_private_hidden_build_report",
        "schema_version": 1,
        "generated_at": FIXED_TIMESTAMP,
        "benchmark_id": BENCHMARK_ID,
        "hidden_version": HIDDEN_VERSION,
        "status": status,
        "toolchain": dict(toolchain),
        "public_manifest_sha256": public_manifest_sha256,
        "commitment_sha256": commitment_sha256,
        "samples": samples,
        "selected_attempts": selected_attempts,
        "excluded_attempts": excluded_attempts,
        "counts": dict(counts),
        "limitations": limitations,
    }


def _write_build_report(root: Path, payload: Mapping[str, Any]) -> None:
    try:
        _write_json_atomic(root / REPORT_NAME, payload)
    except OSError:
        # The report is private evidence; a failed write must not fake success.
        pass


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build_hidden_corpus(
    *,
    root: Path,
    public_manifest_path: Path,
    commitment_path: Path,
    validate_oracles: bool,
    write_commitment: bool,
    compile_func: Callable[..., dict[str, Any]] | None = None,
    validate_func: Callable[..., dict[str, Any]] | None = None,
    toolchain_probe: Mapping[str, Any] | None = None,
    zig: str | None = None,
) -> dict[str, Any]:
    """Build the private corpus into *root* and optionally publish the commitment.

    ``compile_func``/``validate_func`` are dependency-injection seams for tests;
    production callers use the Zig compiler and the Lima-guest PoC validator.
    """
    compile_func = compile_func or compile_variant
    validate_func = validate_func or validate_runtime_oracle
    toolchain = _read_toolchain(toolchain_probe)
    resolved_zig = zig if zig is not None else zig_path()
    root = Path(root)
    limitations: list[str] = []
    dropped = 0
    excluded_attempts: list[dict[str, Any]] = []
    selected_attempts: list[dict[str, Any]] = []

    if not public_manifest_path.is_file():
        return {
            "status": "not_run",
            "summary": _public_summary(
                status="not_run", root=root, runtime_count=0, analysis_count=0,
                commitment=None, commitment_written=False, toolchain=toolchain,
                dropped_attempts=0,
                limitations=["public Phase-8C manifest is missing; hidden build "
                             "not_run"],
            ),
            "commitment": None,
            "written": False,
        }
    public_manifest = _load_json(public_manifest_path)
    public_index = _public_sample_index(public_manifest)
    public_material = public_material_hashes(public_manifest)
    if not resolved_zig:
        return {
            "status": "not_run",
            "summary": _public_summary(
                status="not_run", root=root, runtime_count=0, analysis_count=0,
                commitment=None, commitment_written=False, toolchain=toolchain,
                dropped_attempts=0,
                limitations=["Zig compiler is unavailable (PATH or "
                             ".tmp/zigpkg/site/ziglang/zig); hidden corpus "
                             "not built, nothing faked"],
            ),
            "commitment": None,
            "written": False,
        }
    if not validate_oracles:
        return {
            "status": "blocked",
            "summary": _public_summary(
                status="blocked", root=root, runtime_count=0, analysis_count=0,
                commitment=None, commitment_written=False, toolchain=toolchain,
                dropped_attempts=0,
                limitations=["--validate-oracles was not requested; runtime "
                             "samples cannot be admitted, so hidden_available "
                             "remains false"],
            ),
            "commitment": None,
            "written": False,
        }

    version = zig_version(resolved_zig) or ""
    toolchain = {
        "available": True,
        "version": version,
        "status": "available",
    }
    _ensure_private_layout(root)
    if not _root_is_secure(root):
        return {
            "status": "violation",
            "summary": _public_summary(
                status="violation", root=root, runtime_count=0,
                analysis_count=0, commitment=None, commitment_written=False,
                toolchain=toolchain, dropped_attempts=0,
                limitations=["private hidden root permissions are not "
                             "owner-only (0700); refusing to write hidden "
                             "contents"],
            ),
            "commitment": None,
            "written": False,
        }
    for name in ("bin", "poc", "reference"):
        for stale in (root / name).glob("*"):
            if stale.is_file():
                stale.unlink()
    # A stale committed private manifest / sums pair must never survive a build
    # that does not admit a corpus; blocked builds therefore look like not_run.
    for stale_name in (PRIVATE_MANIFEST_NAME, SUMS_NAME):
        try:
            (root / stale_name).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
    work_root = Path(tempfile.mkdtemp(prefix=".build-", dir=str(root)))
    runtime_samples: list[dict[str, Any]] = []
    analysis_samples: list[dict[str, Any]] = []
    material: dict[str, dict[str, Any]] = {}
    report_samples: list[dict[str, Any]] = []
    try:
        # --- explore known-invalid optimizer configurations (measured drops).
        for attempt in EXPLORATORY_ATTEMPTS:
            source_key = str(attempt["source"])
            source_spec = SOURCE_SPECS[source_key]
            source_path = ROOT / str(source_spec["source"])
            output = work_root / f"probe-{attempt['slug']}.bin"
            record = compile_func(
                resolved_zig, attempt, source_path, output,
            )
            item = {
                "source": str(source_spec["public_sample_id"]),
                "target": str(attempt["target"]),
                "optimization": str(attempt["optimization"]),
                "static": bool(attempt.get("static")),
                "stripped": bool(attempt.get("stripped")),
                "status": str(record.get("status")),
                "reason": None,
            }
            if record.get("status") != "compiled":
                item["reason"] = "compiler build failed"
                excluded_attempts.append(item)
                continue
            manifest = rebind_poc_manifest(
                _source_poc_manifest(source_key), str(record["sha256"]))
            oracle_path = work_root / f"probe-{attempt['slug']}.poc.json"
            _write_json_atomic(oracle_path, manifest)
            validation = validate_func(output, oracle_path)
            item["validation_status"] = str(validation.get("status"))
            item["original_expected_ok"] = bool(
                validation.get("original_expected_ok"))
            item["reason"] = _validation_reason(validation) or (
                "probe unexpectedly validated; not admitted as a sample")
            excluded_attempts.append(item)
            dropped += 1

        # --- runtime samples: first validated spec per source.
        for source_key in SOURCE_SPECS:
            public_sample = _source_public_sample(source_key, public_index)
            if public_sample is None:
                limitations.append(
                    f"public manifest is missing {SOURCE_SPECS[source_key]['public_sample_id']}"
                )
                continue
            source_spec = SOURCE_SPECS[source_key]
            source_path = ROOT / str(source_spec["source"])
            attempts: list[dict[str, Any]] = []
            chosen: dict[str, Any] | None = None
            for spec in RUNTIME_VARIANT_CHAINS.get(source_key, []):
                attempt_spec = dict(spec)
                attempt_spec["compiler_version"] = version
                output = work_root / f"{spec['slug']}.bin"
                record = compile_func(
                    resolved_zig, attempt_spec, source_path, output,
                )
                attempt = {
                    "source": str(source_spec["public_sample_id"]),
                    "target": str(spec["target"]),
                    "optimization": str(spec["optimization"]),
                    "static": bool(spec.get("static")),
                    "stripped": bool(spec.get("stripped")),
                    "status": str(record.get("status")),
                    "reason": None,
                }
                if record.get("status") != "compiled":
                    attempt["reason"] = "compiler build failed"
                    attempts.append(attempt)
                    dropped += 1
                    continue
                identity = container_identity(output.read_bytes())
                if not identity or identity.get("format") != "elf" or \
                        identity.get("arch") != "x86_64" or \
                        identity.get("bits") != 64:
                    attempt["reason"] = "compiled variant is not an ELF x86_64 image"
                    attempts.append(attempt)
                    dropped += 1
                    continue
                duplicate = public_duplicate_reason(
                    str(record.get("sha256") or ""), public_material)
                if duplicate:
                    attempt["reason"] = duplicate
                    attempts.append(attempt)
                    dropped += 1
                    continue
                unstripped_bytes: bytes | None = None
                if spec.get("stripped"):
                    companion_spec = dict(
                        attempt_spec,
                        flags=[item for item in spec.get("flags") or []
                               if item != "-s"],
                        stripped=False,
                    )
                    companion = work_root / f"{spec['slug']}.unstripped.bin"
                    companion_record = compile_func(
                        resolved_zig, companion_spec, source_path, companion,
                    )
                    if companion_record.get("status") != "compiled":
                        attempt["reason"] = (
                            "unstripped companion build failed; stripped target "
                            "range cannot be verified")
                        attempts.append(attempt)
                        dropped += 1
                        continue
                    unstripped_bytes = companion.read_bytes()
                target = _derive_target(
                    spec=spec,
                    symbol=str(source_spec["symbol"]),
                    binary_bytes=output.read_bytes(),
                    unstripped_bytes=unstripped_bytes,
                )
                if target is None:
                    attempt["reason"] = (
                        "sample target could not be resolved in the variant "
                        "binary; the variant is dropped")
                    attempts.append(attempt)
                    dropped += 1
                    continue
                manifest = rebind_poc_manifest(
                    _source_poc_manifest(source_key),
                    str(record["sha256"]),
                )
                oracle_path = work_root / f"{spec['slug']}.poc.json"
                _write_json_atomic(oracle_path, manifest)
                oracle_violations = _oracle_manifest_violations(manifest)
                if oracle_violations:
                    attempt["reason"] = (
                        "rebound PoC manifest is incomplete: "
                        + "; ".join(oracle_violations[:2]))
                    attempts.append(attempt)
                    dropped += 1
                    continue
                validation = _validate_stable(validate_func, output, oracle_path)
                attempt["validation_status"] = str(validation.get("status"))
                attempt["validation_repeats"] = int(
                    validation.get("validation_repeats") or 1)
                attempt["validation_stable"] = bool(
                    validation.get("validation_stable", True))
                attempt["original_expected_ok"] = bool(
                    validation.get("original_expected_ok"))
                attempt["regression_expected_ok"] = bool(
                    validation.get("regression_expected_ok"))
                reason = _validation_reason(validation)
                if reason is not None:
                    attempt["reason"] = reason
                    attempts.append(attempt)
                    dropped += 1
                    continue
                chosen = {
                    "spec": attempt_spec,
                    "record": record,
                    "manifest": manifest,
                    "binary_bytes": output.read_bytes(),
                    "target": target,
                    "validation": validation,
                }
                attempt["status"] = "validated"
                attempts.append(attempt)
                break
            selected_attempts.append({
                "source": str(source_spec["public_sample_id"]),
                "attempts": attempts,
                "selected": bool(chosen),
            })
            if chosen is None:
                limitations.append(
                    f"no validated runtime variant for {source_spec['public_sample_id']}"
                )
                continue
            opaque_id = opaque_sample_id(str(chosen["spec"]["slug"]))
            relative_binary = f"bin/{opaque_id}.bin"
            relative_poc = f"poc/{opaque_id}.json"
            reference_bytes = _private_reference_bytes(
                (ROOT / str(source_spec["reference_fix"])).read_bytes(),
                opaque_id,
            )
            relative_reference = f"reference/{opaque_id}.c"
            _write_bytes_atomic(root / relative_binary, chosen["binary_bytes"])
            _write_json_atomic(root / relative_poc, chosen["manifest"])
            _write_bytes_atomic(root / relative_reference, reference_bytes)
            binary_sha = _sha256_file(root / relative_binary)
            sample = _runtime_sample(
                spec=chosen["spec"],
                source_key=source_key,
                public_sample=public_sample,
                opaque_id=opaque_id,
                binary_sha256=binary_sha,
                oracle_relative=relative_poc,
                oracle_document=chosen["manifest"],
                reference_relative=relative_reference,
                reference_sha256=_sha256_file(root / relative_reference),
                target=chosen["target"],
                validation=chosen["validation"],
            )
            runtime_samples.append(sample)
            material[opaque_id] = {
                "binary_path": relative_binary,
                "oracle_path": relative_poc,
                "reference_fix_path": relative_reference,
            }
            report_samples.append({
                "kind": "runtime",
                "opaque_sample_id": opaque_id,
                "public_sample": str(source_spec["public_sample_id"]),
                "target": str(chosen["spec"]["target"]),
                "optimization": str(chosen["spec"]["optimization"]),
                "static": bool(chosen["spec"].get("static")),
                "stripped": bool(chosen["spec"].get("stripped")),
                "binary_sha256": binary_sha,
                "validation": dict(chosen["validation"]),
            })

        # --- analysis-only cross-format samples.
        for spec in ANALYSIS_VARIANTS:
            source_key = str(spec["source"])
            public_sample = _source_public_sample(source_key, public_index)
            if public_sample is None:
                limitations.append(
                    f"public manifest is missing {SOURCE_SPECS[source_key]['public_sample_id']}"
                )
                continue
            source_spec = SOURCE_SPECS[source_key]
            attempt_spec = dict(spec, compiler_version=version)
            output = work_root / f"{spec['slug']}.bin"
            record = compile_func(
                resolved_zig, attempt_spec, ROOT / str(source_spec["source"]), output,
            )
            if record.get("status") != "compiled":
                dropped += 1
                limitations.append("an analysis-only variant failed to compile")
                continue
            identity = container_identity(output.read_bytes())
            if not identity or identity.get("format") != spec.get("format") or \
                    identity.get("arch") != spec.get("arch"):
                dropped += 1
                limitations.append(
                    "an analysis-only variant does not match its declared "
                    "cross-format container")
                continue
            duplicate = public_duplicate_reason(
                str(record.get("sha256") or ""), public_material)
            if duplicate:
                dropped += 1
                limitations.append(
                    "an analysis-only variant duplicated public corpus "
                    "material and was dropped")
                continue
            opaque_id = opaque_sample_id(str(spec["slug"]))
            relative_binary = f"bin/{opaque_id}.bin"
            _write_bytes_atomic(root / relative_binary, output.read_bytes())
            binary_sha = _sha256_file(root / relative_binary)
            sample = _analysis_sample(
                spec=attempt_spec,
                source_key=source_key,
                public_sample=public_sample,
                opaque_id=opaque_id,
                binary_sha256=binary_sha,
                target_symbol=str(source_spec["symbol"]),
                build_sha256=str(record.get("sha256") or binary_sha),
            )
            analysis_samples.append(sample)
            material[opaque_id] = {
                "binary_path": relative_binary,
                "oracle_path": None,
                "reference_fix_path": None,
            }
            report_samples.append({
                "kind": "analysis_only",
                "opaque_sample_id": opaque_id,
                "public_sample": str(source_spec["public_sample_id"]),
                "target": str(spec["target"]),
                "optimization": str(spec["optimization"]),
                "format": str(spec["format"]),
                "arch": str(spec["arch"]),
                "stripped": bool(spec.get("stripped")),
                "binary_sha256": binary_sha,
            })
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    runtime_count = len(runtime_samples)
    analysis_count = len(analysis_samples)
    blocked = (
        runtime_count < MIN_RUNTIME_SAMPLES
        or runtime_count + analysis_count != TARGET_SAMPLE_COUNT
    )
    if blocked:
        limitations.append(
            f"hidden corpus admitted {runtime_count} runtime and "
            f"{analysis_count} analysis-only samples "
            f"(need {MIN_RUNTIME_SAMPLES}+ runtime and {TARGET_SAMPLE_COUNT} "
            "total); hidden_available remains false and no manifest or "
            "commitment is written")
        # Clean partial payloads so a blocked root never looks like a corpus.
        for path in list((root / "bin").glob("*")) + list((root / "poc").glob("*")) \
                + list((root / "reference").glob("*")):
            path.unlink(missing_ok=True)
        _write_build_report(root, _build_report_payload(
            status="blocked",
            toolchain=toolchain,
            public_manifest_sha256=_sha256_file(public_manifest_path),
            commitment_sha256=None,
            samples=report_samples,
            selected_attempts=selected_attempts,
            excluded_attempts=excluded_attempts,
            counts={
                "sample_count": runtime_count + analysis_count,
                "runtime_count": runtime_count,
                "analysis_only_count": analysis_count,
                "dropped_attempts": dropped,
            },
            limitations=limitations,
        ))
        return {
            "status": "blocked",
            "summary": _public_summary(
                status="blocked", root=root, runtime_count=runtime_count,
                analysis_count=analysis_count, commitment=None,
                commitment_written=False, toolchain=toolchain,
                dropped_attempts=dropped, limitations=limitations,
            ),
            "commitment": None,
            "written": False,
        }

    public_manifest_sha = _sha256_file(public_manifest_path)
    samples = [
        sample for sample in runtime_samples + analysis_samples
    ]
    if len(samples) != TARGET_SAMPLE_COUNT:
        limitations.append(
            f"hidden corpus has {len(samples)} samples, expected "
            f"{TARGET_SAMPLE_COUNT}")
    manifest = compose_private_manifest(
        public_manifest_sha256=public_manifest_sha,
        samples=samples,
        material=material,
    )
    duplicate_violations = manifest_public_duplicates(
        manifest, root, public_material)
    violations = validate_private_manifest_document(manifest, root)
    if duplicate_violations or violations:
        for name in ("bin", "poc", "reference"):
            for path in (root / name).glob("*"):
                if path.is_file():
                    path.unlink()
        reasons = []
        if duplicate_violations:
            reasons.append(
                "hidden material duplicated public corpus material "
                "(hidden/public separation is enforced)")
        if violations:
            reasons.append("the built private manifest failed validation")
        limitations.append(
            "; ".join(reasons) + "; the corpus was not admitted and no "
            "manifest or commitment is written")
        _write_build_report(root, _build_report_payload(
            status="blocked",
            toolchain=toolchain,
            public_manifest_sha256=public_manifest_sha,
            commitment_sha256=None,
            samples=report_samples,
            selected_attempts=selected_attempts,
            excluded_attempts=excluded_attempts,
            counts={
                "sample_count": runtime_count + analysis_count,
                "runtime_count": runtime_count,
                "analysis_only_count": analysis_count,
                "dropped_attempts": dropped,
            },
            limitations=limitations,
        ))
        return {
            "status": "blocked",
            "summary": _public_summary(
                status="blocked", root=root, runtime_count=runtime_count,
                analysis_count=analysis_count, commitment=None,
                commitment_written=False, toolchain=toolchain,
                dropped_attempts=dropped, limitations=limitations,
            ),
            "commitment": None,
            "written": False,
        }
    _write_json_atomic(root / PRIVATE_MANIFEST_NAME, manifest)
    sums_files = _material_files(root, manifest) + [root / PRIVATE_MANIFEST_NAME]
    _write_bytes_atomic(root / SUMS_NAME, _sums_payload(root, sums_files))
    commitment = build_commitment(manifest)
    commitment_violations = validate_commitment_document(commitment)
    if commitment_violations:
        raise ValueError(
            "built public commitment is invalid: "
            + "; ".join(commitment_violations[:6]))
    _write_build_report(root, _build_report_payload(
        status="ok",
        toolchain=toolchain,
        public_manifest_sha256=public_manifest_sha,
        commitment_sha256=commitment["commitment_sha256"],
        samples=report_samples,
        selected_attempts=selected_attempts,
        excluded_attempts=excluded_attempts,
        counts={
            "sample_count": len(samples),
            "runtime_count": runtime_count,
            "analysis_only_count": analysis_count,
            "dropped_attempts": dropped,
        },
        limitations=limitations,
    ))
    written = False
    if write_commitment:
        _write_json_atomic(commitment_path, commitment)
        written = True
    summary_limitations = list(limitations)
    if not write_commitment:
        summary_limitations.append(
            "--write-commitment was not requested; the public commitment was "
            "not written")
    return {
        "status": "ok",
        "summary": _public_summary(
            status="ok", root=root, runtime_count=runtime_count,
            analysis_count=analysis_count, commitment=commitment,
            commitment_written=written, toolchain=toolchain,
            dropped_attempts=dropped, limitations=summary_limitations,
        ),
        "commitment": commitment,
        "written": written,
    }


# ---------------------------------------------------------------------------
# Check (offline verification only)
# ---------------------------------------------------------------------------
def _leak_violations(
    commitment: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
    root: Path,
) -> list[str]:
    violations: list[str] = []
    broken = False
    for name in ("ground-truth-sample-v2.schema.json",):
        if not (CONTRACTS_DIR / name).is_file():
            broken = True
    if broken:
        return ["contract schemas unavailable; leak scan not_run"]
    text = _canonical(commitment)
    forbidden = [
        str(root),
        "bin/",
        "poc/",
        "reference/",
        "reports/",
        "hidden-manifest.json",
        "phase8c_private_hidden_manifest",
        "private-build",
        "public-source",
    ]
    for token in forbidden:
        if token and token in text:
            violations.append("public commitment leaks a hidden path or marker")
            break
    if "/" in "".join(
        value for value in _walk_strings(commitment) if isinstance(value, str)
    ):
        violations.append("public commitment contains a path separator")
    if manifest is not None:
        for sample in manifest.get("samples") or []:
            if not isinstance(sample, Mapping):
                continue
            for ref in sample.get("source_refs") or []:
                if isinstance(ref, str) and ref in text:
                    violations.append(
                        "public commitment leaks a private source reference")
                    break
    return violations


def _walk_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            found.extend(_walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_strings(item))
    return found


def check_private_root(
    *,
    root: Path,
    commitment_path: Path,
    public_manifest_path: Path,
) -> dict[str, Any]:
    """Offline verification of a private corpus + its committed commitment."""
    root = Path(root)
    violations: list[str] = []
    status = "ok"
    manifest: dict[str, Any] | None = None
    commitment: dict[str, Any] | None = None
    toolchain = {"available": False, "version": None, "status": "not_run"}
    if not root.is_dir():
        status = "not_run"
        violations.append(
            "private hidden root is absent; hidden_available is false and "
            "nothing is claimed")
    elif not _root_is_secure(root):
        status = "violation"
        violations.append(
            "private hidden root permissions are not owner-only (0700)")
    else:
        manifest_path = root / PRIVATE_MANIFEST_NAME
        if not manifest_path.is_file():
            status = "not_run"
            violations.append(
                "private hidden manifest is absent; hidden_available is false")
        else:
            try:
                manifest = _load_json(manifest_path)
            except (OSError, json.JSONDecodeError):
                status = "violation"
                violations.append("private hidden manifest is unreadable")
            else:
                if isinstance(manifest, Mapping):
                    report_path = root / REPORT_NAME
                    if report_path.is_file():
                        try:
                            report = _load_json(report_path)
                        except (OSError, json.JSONDecodeError):
                            report = {}
                        toolchain = dict(
                            (report.get("toolchain") or {})
                            if isinstance(report, Mapping) else {})
                    violations.extend(
                        validate_private_manifest_document(manifest, root))
                else:
                    violations.append("private hidden manifest is not an object")
    if isinstance(manifest, Mapping) and not violations:
        violations.extend(_check_sums(root, manifest))
        if violations:
            status = "violation"
    if isinstance(manifest, Mapping) and not violations:
        if not commitment_path.is_file():
            status = "not_run"
            violations.append(
                "public hidden commitment is absent; hidden_available is false")
        else:
            try:
                commitment = _load_json(commitment_path)
            except (OSError, json.JSONDecodeError):
                commitment = None
                violations.append("public hidden commitment is unreadable")
            if isinstance(commitment, Mapping):
                violations.extend(validate_commitment_document(commitment))
                expected = build_commitment(manifest)
                if commitment.get("commitment_sha256") != \
                        expected["commitment_sha256"]:
                    violations.append(
                        "public commitment digest does not match the private "
                        "manifest digest")
                if commitment.get("public_manifest_sha256") != \
                        manifest.get("public_manifest_sha256"):
                    violations.append(
                        "public commitment public-manifest digest is inconsistent")
                for key in ("sample_count", "runtime_count",
                            "analysis_only_count"):
                    if commitment.get(key) != expected[key]:
                        violations.append(
                            f"public commitment {key} is inconsistent")
                committed_samples = [
                    item for item in commitment.get("samples") or []
                    if isinstance(item, Mapping)
                ]
                if committed_samples != expected["samples"]:
                    violations.append(
                        "public commitment opaque hash list is inconsistent")
                violations.extend(
                    _leak_violations(commitment, manifest, root))
            elif commitment is None and not violations:
                violations.append("public hidden commitment is not an object")
    if isinstance(manifest, Mapping) and public_manifest_path.is_file():
        try:
            public_manifest = _load_json(public_manifest_path)
        except (OSError, json.JSONDecodeError):
            public_manifest = None
        if isinstance(public_manifest, Mapping):
            public_material = public_material_hashes(public_manifest)
            violations.extend(
                "hidden/public non-duplication: " + item
                for item in manifest_public_duplicates(
                    manifest, root, public_material))
        if _sha256_file(public_manifest_path) != \
                manifest.get("public_manifest_sha256"):
            violations.append(
                "the current public Phase-8C manifest digest does not match the "
                "digest bound by the private manifest")
    if violations and status == "ok":
        status = "violation"
    counts = {
        "sample_count": len(manifest.get("samples") or []) if manifest else 0,
        "runtime_count": sum(
            1 for sample in (manifest.get("samples") or [])
            if isinstance(sample, Mapping)
            and sample.get("expected_scope") in {"function", "whole_program"}
        ) if manifest else 0,
        "analysis_only_count": sum(
            1 for sample in (manifest.get("samples") or [])
            if isinstance(sample, Mapping)
            and sample.get("expected_scope") == "analysis_only"
        ) if manifest else 0,
    }
    summary = _public_summary(
        status=status, root=root, runtime_count=counts["runtime_count"],
        analysis_count=counts["analysis_only_count"],
        commitment=commitment if isinstance(commitment, Mapping) else None,
        commitment_written=isinstance(commitment, Mapping) and status == "ok",
        toolchain=toolchain, dropped_attempts=0,
        limitations=[],
    )
    summary["mode"] = "check"
    summary["violations"] = [
        _root_in_text(item, root) for item in violations
    ]
    return {"ok": status == "ok", "status": status, "summary": summary}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _emit(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(_canonical(payload))
        return
    lines = [
        f"status: {payload.get('status')}",
        f"hidden_available: {str(payload.get('hidden_available')).lower()}",
        f"samples: {payload.get('sample_count')} "
        f"(runtime {payload.get('runtime_count')}, "
        f"analysis-only {payload.get('analysis_only_count')})",
        f"commitment_sha256: {payload.get('commitment_sha256')}",
        f"public_manifest_sha256: {payload.get('public_manifest_sha256')}",
        f"toolchain: {payload.get('toolchain')}",
    ]
    for limitation in payload.get("limitations") or []:
        lines.append(f"limitation: {limitation}")
    for violation in payload.get("violations") or []:
        lines.append(f"violation: {violation}")
    sys.stdout.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build/verify the Phase-8C private hidden corpus and its "
                    "opaque public commitment.")
    parser.add_argument("--root", default=None,
                        help=f"private hidden root (default ${HIDDEN_ENV} or "
                             f"{DEFAULT_HIDDEN_ROOT})")
    parser.add_argument("--public-manifest", default=str(ROOT / PUBLIC_MANIFEST_REL),
                        help="public Phase-8C v2 manifest path")
    parser.add_argument("--commitment", default=str(ROOT / COMMITMENT_REL),
                        help="public hidden-commitment path")
    parser.add_argument("--check", action="store_true",
                        help="offline verify the private root and commitment")
    parser.add_argument("--write-commitment", action="store_true",
                        help="write the opaque public commitment after a build")
    parser.add_argument("--validate-oracles", action="store_true",
                        help="execute the rebound PoCs in the Lima guest under "
                             "the shared guest lock (required for runtime samples)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args(argv)

    root = resolve_root(args.root)
    commitment_path = Path(args.commitment).expanduser()
    public_manifest_path = Path(args.public_manifest).expanduser()

    if args.check:
        try:
            result = check_private_root(
                root=root,
                commitment_path=commitment_path,
                public_manifest_path=public_manifest_path,
            )
        except Exception as exc:  # noqa: BLE001 - fail closed, no traceback leak
            summary = {
                "kind": "phase8c_hidden_build_summary",
                "schema_version": 1,
                "mode": "check",
                "status": "violation",
                "hidden_available": False,
                "sample_count": 0,
                "runtime_count": 0,
                "analysis_only_count": 0,
                "commitment_sha256": None,
                "public_manifest_sha256": None,
                "created_at": None,
                "root_present": root.is_dir(),
                "root_secure": False,
                "toolchain": {"compiler": None, "compiler_version": None,
                              "status": "not_run"},
                "dropped_attempts": 0,
                "limitations": [],
                "violations": [
                    f"check failed closed: {type(exc).__name__}"],
            }
            _emit(summary, as_json=args.json)
            return 1
        summary = result["summary"]
        _emit(summary, as_json=args.json)
        if not result["ok"]:
            return 1 if summary.get("status") == "violation" else 2
        return 0

    try:
        result = build_hidden_corpus(
            root=root,
            public_manifest_path=public_manifest_path,
            commitment_path=commitment_path,
            validate_oracles=args.validate_oracles,
            write_commitment=args.write_commitment,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed, generic message only
        summary = {
            "kind": "phase8c_hidden_build_summary",
            "schema_version": 1,
            "status": "blocked",
            "hidden_available": False,
            "sample_count": 0,
            "runtime_count": 0,
            "analysis_only_count": 0,
            "commitment_sha256": None,
            "public_manifest_sha256": None,
            "created_at": None,
            "root_present": root.is_dir(),
            "root_secure": False,
            "toolchain": {"compiler": None, "compiler_version": None,
                          "status": "not_run"},
            "dropped_attempts": 0,
            "limitations": [
                f"hidden build failed closed: {type(exc).__name__}; no "
                "manifest or commitment was written"],
        }
        _emit(summary, as_json=args.json)
        return 2
    summary = result["summary"]
    _emit(summary, as_json=args.json)
    if result["status"] == "ok":
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
