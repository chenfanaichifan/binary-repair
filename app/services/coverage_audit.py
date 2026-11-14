"""Self-discovery coverage and capability-gap audit for the binary repair product.

The audit is measurement-only.  It imports the real product modules (never a
copy of their tables), probes the real pipeline on the shipped fixtures, and
derives gap rows from what it measures.  Nothing here re-implements a repair or
accepts a candidate; the module runs no network I/O and never executes a
host-native Linux ELF by itself (``repair_any(..., verify=True)`` uses only the
product's own acceptance runtimes: Unicorn emulation, the native Mach-O runner,
or the declared guest runner).

Two questions are answered per run:

* repair-capability gaps: a matrix cell, sink class or strategy that the
  declared matrix advertises but the engine cannot actually produce on the
  shipped evidence;
* acceptance-model mismatches: a candidate/gate/evidence-model combination
  whose declared checks cannot be satisfied by the evidence the pipeline can
  supply for that cell, format, architecture or host.

Every gap row is re-derived on each run, so a gap that the team closes later
flips to ``closed`` (or ``mitigated``) instead of staying hard-coded as open.
The static taxonomy below only names detectors and categories; statuses always
come from imports and probes.

Public API::

    audit = build_audit()                 # full static census + bounded probes
    audit = build_audit(include_probes=False)  # fast static census only
    report_md = render_gap_report(audit)
    written = write_artifacts(audit)      # coverage-matrix.json, gap-report.md, SHA256SUMS
"""
from __future__ import annotations

import glob
import hashlib
import importlib
import inspect
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

AUDIT_DATE = "2026-11-14"
SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = "artifacts/capability-gap-audit-2026-11-14"
MAX_FIXTURE_BYTES = 20 * 1024 * 1024
DEFAULT_BUDGET_SECONDS = 240.0
MAX_BENCHMARK_ARTIFACTS = 40
MAX_TEXT_DETAIL = 180

GAP_CATEGORIES = (
    "engine_gap",
    "gate_mismatch",
    "oracle_gap",
    "runtime_gap",
    "matrix_claim_mismatch",
    "non_goal",
)
GAP_STATUSES = ("open", "closed", "mitigated", "non_goal")
GAP_SEVERITIES = ("high", "medium", "low", "info")
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}
STATUS_RANK = {"open": 0, "mitigated": 1, "closed": 2, "non_goal": 3}
CATEGORY_RANK = {name: index for index, name in enumerate(GAP_CATEGORIES)}

FIXTURE_GLOBS = (
    "fixtures/elf/*",
    "fixtures/pe/*",
    "fixtures/macho/*",
    "fixtures/public/*/original.elf",
    "fixtures/hard-cases/*.elf",
)
LEGACY_ARTIFACT_INPUTS = ("artifacts/vuln-elf/vuln.elf",)
CASES_PATH = "fixtures/hard-cases/cases.json"
POC_GLOB = "fixtures/poc/*.json"
CLAIMS_PATH = "docs/status/claims.json"
LIMITATIONS_PATH = "docs/acceptance/LIMITATIONS.md"
README_PATH = "README.md"
BENCHMARK_GLOBS = (
    "artifacts/*/summary.json",
    "artifacts/*/aggregate.json",
)
LEGACY_TEMPLATE_CANDIDATES = (
    "app/data/vuln-strict-fixed.elf",
    "data/vuln-strict-fixed.elf",
)

MODULE_PATHS = {
    "repair_matrix": "app/services/repair_matrix.py",
    "binary_pipeline": "app/services/binary_pipeline.py",
    "unified_verification": "app/services/unified_verification.py",
    "binary_verification": "app/services/binary_verification.py",
    "analyzer": "app/services/repair/analyzer.py",
    "analyzer_i386": "app/services/repair/analyzer_i386.py",
    "writer": "app/services/repair/writer.py",
    "emulated": "app/services/runtime/emulated.py",
    "macho_native": "app/services/runtime/macho_native.py",
    "poc_runner": "app/services/poc_runner.py",
    "guest_runner": "app/services/guest_runner.py",
    "capacity": "app/services/repair/capacity.py",
    "ai_binary_repair": "app/services/ai_binary_repair.py",
    "ai_assembly_repair": "app/services/ai_assembly_repair.py",
    "ai_patch_validation": "app/services/ai_patch_validation.py",
}

# Analyzer emission paths per architecture, measured from analyzer source text.
# Used only to distinguish "declared but unimplemented" from "implemented but
# unexercised by fixtures"; the matrix/analyzer tables themselves are imported.
ANALYZER_KIND_MARKERS = {
    "unbounded_copy": "unbounded_copy",
    "immediate_length": "immediate_length",
    "memcpy_length": "memcpy_length",
    "syscall_length": "syscall_length",
    "checked_copy": "checked_copy",
    "capacity_check_mismatch": "capacity_check_mismatch",
}

# Static taxonomy of the known gap inventory this audit was asked to verify.
# lead_ref values refer to .tmp/team/lead-gap-notes.md ids; they are labels, not
# statuses.
KNOWN_LEAD_GAPS = {
    "EG-capacity-strategy": "G1",
    "EG-heap-destination": "G2",
    "OG-heap-destination-oracle": "G3",
    "GM-gate-no-input": "G4",
    "GM-gate-poc-unavailable": "G5",
    "GM-profile-registry": "G6",
    "GM-gate-cell": "G7",
    "GM-gate-runtime-tier": "G8",
    "GM-legacy-gate-poc-manifest": "G9",
    "GM-legacy-gate-profile": "G25",
    "RG-external-poc::macho/x86_64": "G17",
    "MM-runtime-tier-vocabulary": "G19",
    "NG-ai-leaf-only": "G20",
    "EG-cases-target-not-analyzed": "G12",
    "OG-wrong-function-candidate": "G22",
    "MM-claims-capacity-stale": "G16",
    "MM-docs-capacity-missing": "G27",
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text(rel: str) -> str:
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _source_line(rel: str, needle: str) -> str:
    """Return ``rel:line`` for the first literal occurrence, or ``rel``."""
    text = _read_text(rel)
    if not text:
        return f"{rel} (unreadable)"
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return f"{rel}:{index}"
    return f"{rel} (marker absent)"


def _source_has(rel: str, needle: str) -> bool:
    return needle in _read_text(rel)


def _json_load(rel: str) -> Any:
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _load_module(name: str) -> tuple[Any | None, str | None]:
    try:
        return importlib.import_module(name), None
    except Exception as exc:  # noqa: BLE001 - mid-flight modules are evidence
        return None, f"{type(exc).__name__}: {exc}"


def _truncate(text: Any, limit: int = MAX_TEXT_DETAIL) -> str:
    value = str(text or "")
    return value[:limit]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _signature_params(func: Callable[..., Any]) -> list[str]:
    try:
        return sorted(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return []


def _host_arch() -> str:
    machine = platform.machine().lower()
    return {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)


def _which(name: str) -> str:
    return shutil.which(name) or ""


# ---------------------------------------------------------------------------
# census: repair matrix
# ---------------------------------------------------------------------------

def _census_matrix() -> dict[str, Any]:
    module, error = _load_module("app.services.repair_matrix")
    census: dict[str, Any] = {
        "module": "app.services.repair_matrix",
        "source": MODULE_PATHS["repair_matrix"],
        "status": "ok" if module is not None else "module_not_ready",
        "error": error,
    }
    if module is None:
        return census
    cells = []
    for cell in getattr(module, "REPAIR_CELLS", ()):
        entry = {
            "container": str(getattr(cell, "container", "?")),
            "arch": str(getattr(cell, "arch", "?")),
            "bits": getattr(cell, "bits", None),
            "endian": str(getattr(cell, "endian", "?")),
            "strategies": [str(item) for item in getattr(cell, "strategies", ())],
            "runtime_tiers": [str(item) for item in getattr(cell, "runtime_tiers", ())],
            "sink_classes": [str(item) for item in getattr(cell, "sink_classes", ())],
        }
        entry["key"] = (
            f"{entry['container']}/{entry['arch']}/{entry['bits']}/{entry['endian']}"
        )
        cells.append(entry)
    cells.sort(key=lambda item: item["key"])
    sink_classes = {}
    for name, meta in _as_dict(getattr(module, "SINK_CLASSES", {})).items():
        sink_classes[str(name)] = {
            "strategy": str(_as_dict(meta).get("strategy", "")),
            "description": str(_as_dict(meta).get("description", "")),
        }
    profiles = {}
    for name, meta in _as_dict(getattr(module, "EVIDENCE_PROFILES", {})).items():
        meta_dict = _as_dict(meta)
        profiles[str(name)] = {
            "description": str(meta_dict.get("description", "")),
            "evidence_sources": [str(item) for item in _as_list(meta_dict.get("evidence_sources"))],
            "required_checks": [str(item) for item in _as_list(meta_dict.get("required_checks"))],
            "legacy_required_checks": [
                str(item) for item in _as_list(meta_dict.get("legacy_required_checks"))
            ],
        }
    strategy_profiles = {
        str(key): str(value)
        for key, value in _as_dict(getattr(module, "STRATEGY_PROFILES", {})).items()
    }
    strategies: set[str] = set(sink_classes[name]["strategy"] for name in sink_classes)
    for cell in cells:
        strategies.update(cell["strategies"])
    strategies.discard("")
    runtime_tiers = {str(key): str(value) for key, value in
                     _as_dict(getattr(module, "RUNTIME_TIERS", {})).items()}
    census.update({
        "schema_version": getattr(module, "SCHEMA_VERSION", None),
        "cells": cells,
        "cell_keys": [cell["key"] for cell in cells],
        "sink_classes": dict(sorted(sink_classes.items())),
        "strategies": sorted(strategies),
        "strategy_profiles": dict(sorted(strategy_profiles.items())),
        "evidence_profiles": dict(sorted(profiles.items())),
        "has_evidence_profiles": bool(profiles),
        "runtime_tiers": dict(sorted(runtime_tiers.items())),
        "dispositions": [str(item) for item in getattr(module, "DISPOSITIONS", ())],
        "non_goals": [str(item) for item in getattr(module, "_NON_GOALS", ())],
        "profile_helpers": sorted(
            name for name in (
                "resolve_profile", "is_known_profile", "profile_required_checks",
                "profile_evidence_sources", "profile_for_strategy",
            )
            if hasattr(module, name)
        ),
    })
    return census


# ---------------------------------------------------------------------------
# census: verification gates (enumerated by calling the real builders)
# ---------------------------------------------------------------------------

_ORIGINAL = b"\x00" * 16
_CANDIDATE = b"\x01" + b"\x00" * 15
_ACTIONS = [{"kind": "immediate", "offset": 0, "before": 0, "after": 1}]


def _dummy_runtime() -> Any:
    case = SimpleNamespace(input_len=1, to_dict=lambda: {"input_len": 1})
    return SimpleNamespace(
        tier="emulated_run",
        engine="audit-unicorn",
        verdict="pass",
        cases=[case],
        to_dict=lambda: {
            "tier": "emulated_run",
            "engine": "audit-unicorn",
            "verdict": "pass",
            "cases": [{"input_len": 1}],
        },
    )


def _dummy_external_poc(*, no_input: bool | None, status: str = "pass",
                        regression_mismatch: bool = False) -> dict[str, Any]:
    regression = [] if no_input is not None else [
        {"executable": "original", "expected_ok": True, "stdout_hex": "aa"},
        {
            "executable": "candidate",
            "expected_ok": not regression_mismatch,
            "stdout_hex": "bb" if regression_mismatch else "aa",
        },
    ]
    signature = "not_applicable" if no_input is not None else (
        "mismatch" if regression_mismatch else "matched"
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "runner": "audit",
        "tier": "emulated_run",
        "stdout_signature": signature,
        "original_sha256": _sha_bytes(_ORIGINAL),
        "candidate_sha256": _sha_bytes(_CANDIDATE),
        "poc": [
            {"executable": "original", "expected_ok": True},
            {"executable": "candidate", "expected_ok": True},
        ],
        "regression": regression,
        "limitations": [],
    }
    if no_input is not None:
        payload["no_input"] = bool(no_input)
    return payload


def _dummy_poc() -> dict[str, Any]:
    return {
        "kind": "capacity_overflow_differential",
        "engine": "audit-unicorn",
        "tier": "emulated_run",
        "inputs": [1],
        "original_verdict": "fail",
        "candidate_verdict": "pass",
        "original_cases": [{"input_len": 1}],
    }


_UNIFIED_BASE = {
    "format_name": "elf",
    "arch": "x86_64",
    "original": _ORIGINAL,
    "candidate": _CANDIDATE,
    "actions": _ACTIONS,
    "runtime": None,
    "reparse_ok": True,
    "original_sha256": _sha_bytes(_ORIGINAL),
    "patched_sha256": _sha_bytes(_CANDIDATE),
}

_MATCH_CELL = {
    "container": "elf",
    "arch": "x86_64",
    "bits": 64,
    "endian": "little",
    "runtime_tiers": ["emulated_run"],
}

_REWRITE_OK = [{"offset": 0, "size": 1, "before_hex": "00", "after_hex": "01"}]
_REWRITE_TAMPERED = [{"offset": 0, "size": 1, "before_hex": "ff", "after_hex": "01"}]


def _gate_scenarios() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("minimal", {}),
        (
            "runtime_only",
            {"runtime": _dummy_runtime()},
        ),
        (
            "external_only",
            {"external_poc": _dummy_external_poc(no_input=None)},
        ),
        (
            "full_evidence",
            {
                "runtime": _dummy_runtime(),
                "external_poc": _dummy_external_poc(no_input=None),
                "poc": _dummy_poc(),
            },
        ),
        (
            "no_input_declared",
            {"external_poc": _dummy_external_poc(no_input=True)},
        ),
        (
            "empty_regression_undeclared",
            {"external_poc": _dummy_external_poc(no_input=None)},
        ),
        (
            "poc_unavailable",
            {"external_poc": {
                **_dummy_external_poc(no_input=None, status="unavailable"),
                "runner": "",
                "limitations": ["no runner for this host"],
            }},
        ),
        (
            "regression_mismatch",
            {"external_poc": _dummy_external_poc(no_input=None,
                                                 regression_mismatch=True)},
        ),
        ("unknown_profile", {"profile": "__audit_unknown_profile__"}),
        ("cell_position", {"cell": dict(_MATCH_CELL)}),
        (
            "cell_mismatch",
            {"cell": {"container": "pe", "arch": "i386", "bits": 32,
                      "endian": "little", "runtime_tiers": ["emulated_run"]}},
        ),
        (
            "cell_tier_mismatch",
            {
                "runtime": _dummy_runtime(),
                "cell": {"container": "elf", "arch": "x86_64", "bits": 64,
                         "endian": "little", "runtime_tiers": ["native_run"]},
            },
        ),
        ("rewrite_valid", {"rewrite_actions": [dict(item) for item in _REWRITE_OK]}),
        (
            "rewrite_tampered",
            {"rewrite_actions": [dict(item) for item in _REWRITE_TAMPERED]},
        ),
    ]


def _census_unified_gate(matrix: dict[str, Any]) -> dict[str, Any]:
    module, error = _load_module("app.services.unified_verification")
    census: dict[str, Any] = {
        "module": "app.services.unified_verification",
        "source": MODULE_PATHS["unified_verification"],
        "status": "ok" if module is not None else "module_not_ready",
        "error": error,
    }
    if module is None:
        return census
    build = getattr(module, "build", None)
    if not callable(build):
        census["status"] = "module_not_ready"
        census["error"] = "build() not callable"
        return census
    params = _signature_params(build)
    census["parameters"] = params
    census["extra_kwargs_supported"] = {
        name: name in params for name in ("profile", "rewrite_actions", "cell")
    }
    profiles = sorted(_as_dict(matrix.get("evidence_profiles")))
    preferred_profile = ""
    if "emulated_instruction" in profiles:
        preferred_profile = "emulated_instruction"
    elif profiles:
        preferred_profile = profiles[0]
    scenarios = _gate_scenarios()
    if preferred_profile:
        scenarios.append((
            "declared_profile",
            {
                "runtime": _dummy_runtime(),
                "profile": preferred_profile,
                "cell": dict(_MATCH_CELL),
            },
        ))
    results: dict[str, Any] = {}
    observed_ids: set[str] = set()
    profile_check_ids: set[str] = set()
    for name, extra in scenarios:
        kwargs = dict(_UNIFIED_BASE)
        kwargs.update(extra)
        accepted = {key: value for key, value in kwargs.items()
                    if key in params or key in _UNIFIED_BASE}
        passed = sorted(key for key in extra if key in params)
        try:
            verification = build(**accepted)
            packet = _as_dict(getattr(verification, "packet", {}))
            gate = _as_dict(getattr(verification, "gate", None) and
                            vars(verification.gate))
            checks = []
            for check in _as_list(packet.get("checks")):
                item = _as_dict(check)
                check_id = str(item.get("id", ""))
                observed_ids.add(check_id)
                if check_id.startswith("profile.") or check_id.startswith("patch."):
                    profile_check_ids.add(check_id)
                checks.append({
                    "id": check_id,
                    "status": str(item.get("status", "")),
                    "detail": _truncate(item.get("detail")),
                })
            results[name] = {
                "outcome": str(gate.get("outcome", "")),
                "success": bool(gate.get("success")),
                "reason": _truncate(gate.get("reason")),
                "checks": checks,
                "extra_kwargs_passed": passed,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - mid-flight gate is evidence
            results[name] = {
                "outcome": "error",
                "success": False,
                "reason": "",
                "checks": [],
                "extra_kwargs_passed": passed,
                "error": f"{type(exc).__name__}: {_truncate(exc)}",
            }
    census["scenarios"] = dict(sorted(results.items()))
    census["check_ids"] = sorted(observed_ids)
    census["profile_check_ids"] = sorted(profile_check_ids)
    full = results.get("full_evidence") or {}
    failed = [item["id"] for item in _as_list(full.get("checks"))
              if item.get("status") == "failed"]
    not_run = [item["id"] for item in _as_list(full.get("checks"))
               if item.get("status") == "not_run"]
    census["best_case"] = {
        "scenario": "full_evidence",
        "outcome": full.get("outcome", ""),
        "success": bool(full.get("success")),
        "failed": sorted(failed),
        "not_run": sorted(not_run),
    }
    return census


def _legacy_report(*, mode: str, strict: bool, capacity: int,
                   patched: bytes, template: bytes | None) -> Any:
    cases = []
    for size in (0, 1, capacity):
        cases.append({
            "input_len": size, "exit_code": 0, "stdout_len": max(1, size),
            "stderr_len": 0, "stack_sentinel_intact": True, "error": None,
        })
    cases.append({
        "input_len": capacity + 1, "exit_code": 1, "stdout_len": 0,
        "stderr_len": 1, "stack_sentinel_intact": True, "error": None,
    })
    original = b"\x02" * 16
    return SimpleNamespace(
        mode=mode,
        strict=strict,
        capacity=capacity,
        original_sha256=_sha_bytes(original),
        patched_sha256=_sha_bytes(patched),
        format="elf64-little",
        arch="x86_64",
        supported=True,
        strategy="strict-template" if strict else "immediate",
        offsets=[] if strict else [0],
        findings=[] if strict else [{"kind": "code_cave"}],
        runtime={"available": True, "engine": "unicorn-x86-64", "cases": cases},
        backend="elf",
        status="patched",
        limitations=[],
    )


def _census_legacy_gate() -> dict[str, Any]:
    module, error = _load_module("app.services.binary_verification")
    census: dict[str, Any] = {
        "module": "app.services.binary_verification",
        "source": MODULE_PATHS["binary_verification"],
        "status": "ok" if module is not None else "module_not_ready",
        "error": error,
    }
    if module is None:
        return census
    build = getattr(module, "build_verification", None)
    if not callable(build):
        census["status"] = "module_not_ready"
        census["error"] = "build_verification() not callable"
        return census
    params = _signature_params(build)
    census["parameters"] = params
    census["accepts_external_poc"] = any(
        name in params for name in ("external_poc", "poc", "poc_manifest")
    )
    template = None
    template_path = str(getattr(module, "STRICT_TEMPLATE", "") or "")
    for candidate in LEGACY_TEMPLATE_CANDIDATES:
        try:
            path = ROOT / candidate
            if path.is_file():
                template = path.read_bytes()
                template_path = candidate
                break
        except OSError:
            continue
    scenarios: dict[str, Any] = {}
    observed: set[str] = set()
    for name, mode, strict in (
        ("bounds_only", "bounds-only", False),
        ("strict_template", "strict", True),
    ):
        if strict and template is None:
            scenarios[name] = {"outcome": "unavailable", "error": "reviewed template missing"}
            continue
        patched = template if strict else b"\x03" * 16
        report = _legacy_report(mode=mode, strict=strict, capacity=16,
                                patched=patched, template=template)
        try:
            verification = build(report, original=b"\x02" * 16, patched=patched)
            packet = _as_dict(getattr(verification, "packet", {}))
            gate = _as_dict(vars(verification.gate))
            checks = []
            for check in _as_list(packet.get("checks")):
                item = _as_dict(check)
                check_id = str(item.get("id", ""))
                observed.add(check_id)
                checks.append({
                    "id": check_id,
                    "status": str(item.get("status", "")),
                    "detail": _truncate(item.get("detail")),
                })
            scenarios[name] = {
                "outcome": str(gate.get("outcome", "")),
                "success": bool(gate.get("success")),
                "checks": checks,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            scenarios[name] = {
                "outcome": "error",
                "success": False,
                "checks": [],
                "error": f"{type(exc).__name__}: {_truncate(exc)}",
            }
    census["template"] = template_path if template is not None else ""
    census["template_present"] = template is not None
    census["scenarios"] = dict(sorted(scenarios.items()))
    census["check_ids"] = sorted(observed)
    return census


def _census_ai_paths() -> dict[str, Any]:
    census: dict[str, Any] = {}
    for name in ("ai_binary_repair", "ai_assembly_repair", "ai_patch_validation"):
        module, error = _load_module(f"app.services.{name}")
        entry: dict[str, Any] = {
            "status": "ok" if module is not None else "module_not_ready",
            "error": error,
            "source": MODULE_PATHS[name],
        }
        if module is not None:
            entry["routes_through_finish_candidate"] = hasattr(module, "finish_candidate")
            entry["whitelist_constants"] = sorted(
                item for item in dir(module)
                if item.isupper() and any(
                    token in item for token in ("ALLOW", "WHITELIST", "LEAF", "FORBID")
                )
            )
            source = _read_text(MODULE_PATHS[name])
            entry["leaf_only_mentions"] = source.lower().count("leaf")
        census[name] = entry
    return census


# ---------------------------------------------------------------------------
# census: runtime evidence sources
# ---------------------------------------------------------------------------

def _poc_runner_selection(format_name: str, arch: str) -> dict[str, Any]:
    """Measure which external-PoC runner the product selects for a pair."""
    result: dict[str, Any] = {
        "format": format_name,
        "arch": arch,
        "available": False,
        "runner": "",
        "tier": "",
        "source": "",
        "detail": "",
    }
    guest, guest_error = _load_module("app.services.guest_runner")
    if guest is not None and hasattr(guest, "find_guest_runner"):
        try:
            selection = guest.find_guest_runner(arch)
        except Exception as exc:  # noqa: BLE001
            result["detail"] = f"find_guest_runner error: {_truncate(exc)}"
            selection = None
        if selection is not None:
            result.update({
                "available": True,
                "runner": str(getattr(selection, "kind", "")),
                "tier": str(getattr(selection, "tier", "")),
                "source": "app.services.guest_runner.find_guest_runner",
                "detail": str(getattr(selection, "tool", "")),
            })
            return result
        result["detail"] = guest_error or "no native/qemu/lima runner"
    # Fallback for the pre-Lima runner API.
    poc, poc_error = _load_module("app.services.poc_runner")
    if poc is not None:
        selector = getattr(poc, "_select_runner", None) or getattr(poc, "_runner_for", None)
        if callable(selector):
            try:
                selection = selector(format_name, arch)
            except Exception as exc:  # noqa: BLE001
                result["detail"] = f"poc runner error: {_truncate(exc)}"
                selection = None
            if selection is not None:
                if isinstance(selection, tuple):
                    kind, tool = str(selection[0]), str(selection[1])
                else:
                    kind = str(getattr(selection, "kind", ""))
                    tool = str(getattr(selection, "tool", ""))
                tier = str(getattr(selection, "tier", "")) if not isinstance(
                    selection, tuple) else ("native_run" if kind == "native" else "emulated_run")
                result.update({
                    "available": True,
                    "runner": kind,
                    "tier": tier,
                    "source": "app.services.poc_runner private runner selector",
                    "detail": tool,
                })
                return result
            result["detail"] = poc_error or "poc runner selector returned None"
    return result


def _runtime_module_support(module_name: str, rel_path: str) -> dict[str, Any]:
    module, error = _load_module(module_name)
    source = _read_text(rel_path)
    return {
        "module": module_name,
        "source": rel_path,
        "status": "ok" if module is not None else "module_not_ready",
        "error": error,
        "source_bytes": len(source),
        "supports": {
            "elf": "elf" in source,
            "pe": "pe" in source,
            "macho": "macho" in source,
            "x86_64": "x86_64" in source,
            "i386": "i386" in source,
            "arm64": "arm64" in source,
        },
    }


def _census_runtime(matrix: dict[str, Any]) -> dict[str, Any]:
    emulated = _runtime_module_support(
        "app.services.runtime.emulated", MODULE_PATHS["emulated"]
    )
    macho, macho_error = _load_module("app.services.runtime.macho_native")
    macho_info: dict[str, Any] = {
        "module": "app.services.runtime.macho_native",
        "source": MODULE_PATHS["macho_native"],
        "status": "ok" if macho is not None else "module_not_ready",
        "error": macho_error,
        "available": False,
        "host_supported": False,
    }
    if macho is not None:
        available = getattr(macho, "available", None)
        if callable(available):
            try:
                macho_info["available"] = bool(available())
            except Exception as exc:  # noqa: BLE001
                macho_info["error"] = f"{type(exc).__name__}: {_truncate(exc)}"
        macho_info["host_supported"] = (
            sys.platform == "darwin" and _host_arch() in {"arm64", "x86_64"}
        )
    sources: list[dict[str, Any]] = []
    cells = _as_list(matrix.get("cells"))
    pairs = sorted({(str(cell.get("container")), str(cell.get("arch"))) for cell in cells})
    for container, arch in pairs:
        sources.append({
            "format": container,
            "arch": arch,
            "source": "runtime_native",
            "runtime_tier": "native_run",
            "available": bool(container == "macho" and macho_info["available"]),
            "detail": "macho_native.available()" if container == "macho"
                      else "native execution is not declared for this container",
        })
        sources.append({
            "format": container,
            "arch": arch,
            "source": "runtime_emulated",
            "runtime_tier": "emulated_run",
            "available": bool(
                container in {"elf", "pe"}
                and emulated["supports"].get(arch, False)
            ),
            "detail": "Unicorn instruction-level emulation",
        })
        selection = _poc_runner_selection(container, arch)
        sources.append({
            "format": container,
            "arch": arch,
            "source": "external_poc",
            "runtime_tier": selection["tier"],
            "available": bool(selection["available"]),
            "runner": selection["runner"],
            "selector": selection["source"],
            "detail": selection["detail"],
        })
    sources.sort(key=lambda item: (item["format"], item["arch"], item["source"]))
    host = {
        "platform": sys.platform,
        "machine": platform.machine(),
        "arch": _host_arch(),
        "python": platform.python_version(),
        "limactl": _which("limactl"),
        "qemu_x86_64": _which("qemu-x86_64"),
        "qemu_aarch64": _which("qemu-aarch64"),
        "codesign": _which("codesign"),
    }
    return {
        "host": host,
        "emulated": emulated,
        "macho_native": macho_info,
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# census: fixtures, cases, PoC manifests, claims, docs, benchmarks
# ---------------------------------------------------------------------------

def _read_bytes(ctx: dict[str, Any], path: Path) -> bytes | None:
    cache = ctx.setdefault("_data_cache", {})
    key = str(path)
    if key in cache:
        return cache[key]
    try:
        data = path.read_bytes()
    except OSError:
        return None
    cache[key] = data
    return data


def _detect_container(data: bytes) -> Any:
    containers, _error = _load_module("app.services.containers")
    if containers is None:
        return None
    try:
        return containers.detect_container(data)
    except Exception:  # noqa: BLE001
        return None


def _cell_key_for(format_name: str, arch: str, bits: Any) -> str:
    return f"{format_name}/{arch}/{bits}/little"


def _fixture_inputs(include_legacy_artifact: bool = True) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in FIXTURE_GLOBS:
        for raw in sorted(glob.glob(str(ROOT / pattern))):
            path = Path(raw)
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            entries.append({"path": rel, "source": "fixtures"})
    if include_legacy_artifact:
        for rel in LEGACY_ARTIFACT_INPUTS:
            path = ROOT / rel
            if path.is_file() and rel not in seen:
                seen.add(rel)
                entries.append({"path": rel, "source": "artifact"})
    entries.sort(key=lambda item: (item["source"] != "fixtures", item["path"]))
    return entries


def _census_fixtures(ctx: dict[str, Any], include_legacy_artifact: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in _fixture_inputs(include_legacy_artifact):
        rel = entry["path"]
        path = ROOT / rel
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        row: dict[str, Any] = {
            "probe_id": f"fixture:{rel}",
            "path": rel,
            "source": entry["source"],
            "bytes": size,
            "sha256": "",
            "format": "unknown",
            "arch": "unknown",
            "bits": None,
            "endian": "unknown",
            "cell": None,
            "skipped_over_size": size > MAX_FIXTURE_BYTES,
            "detect_limitations": [],
        }
        if size < 0 or size > MAX_FIXTURE_BYTES:
            rows.append(row)
            continue
        data = _read_bytes(ctx, path)
        if data is None:
            row["detect_limitations"] = ["unreadable"]
            rows.append(row)
            continue
        row["sha256"] = _sha_bytes(data)
        container = _detect_container(data)
        if container is not None:
            row.update({
                "format": str(getattr(container, "format", "unknown")),
                "arch": str(getattr(container, "arch", "unknown")),
                "bits": getattr(container, "bits", None),
                "endian": str(getattr(container, "endian", "unknown")),
                "detect_limitations": [
                    _truncate(item) for item in _as_list(getattr(container, "limitations", []))[:4]
                ],
            })
            if row["bits"] is not None and row["endian"] == "little":
                row["cell"] = _cell_key_for(row["format"], row["arch"], row["bits"])
        rows.append(row)
    return rows


def _census_cases(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _json_load(CASES_PATH)
    rows: list[dict[str, Any]] = []
    for case in _as_list(_as_dict(payload).get("cases")):
        item = _as_dict(case)
        binary = str(item.get("binary", ""))
        path = ROOT / binary
        target = str(item.get("target", ""))
        target_va = None
        target_state = "binary_missing"
        data = _read_bytes(ctx, path) if path.is_file() else None
        if data is not None:
            container = _detect_container(data)
            if container is not None:
                symbols = _as_dict(getattr(container, "symbols", {}))
                for va, name in symbols.items():
                    if str(name) == target:
                        try:
                            target_va = int(va)
                        except (TypeError, ValueError):
                            target_va = None
                        break
                target_state = "resolved" if target_va is not None else "symbol_missing"
        rows.append({
            "case_id": str(item.get("id", "")),
            "binary": binary,
            "target": target,
            "target_va": hex(target_va) if target_va is not None else None,
            "target_state": target_state,
            "capacity": item.get("capacity"),
            "family": str(item.get("family", "")),
            "baseline_expected": str(item.get("baseline_expected", "")),
            "poc_manifest": str(item.get("poc", "")),
            "measured_disposition": "",
            "measured_strategy": "",
            "measured_target_analyzed": None,
            "measured_wrong_function_actions": None,
        })
    rows.sort(key=lambda item: item["case_id"])
    return rows


def _census_poc_manifests(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fixtures = {row["sha256"]: row["path"] for row in _as_list(ctx["fixtures"])
                if row.get("sha256")}
    for raw in sorted(glob.glob(str(ROOT / POC_GLOB))):
        path = Path(raw)
        rel = path.relative_to(ROOT).as_posix()
        payload = _json_load(rel)
        entry: dict[str, Any] = {
            "path": rel,
            "sha256": _sha_bytes(_read_bytes(ctx, path) or b""),
            "valid_json": isinstance(payload, dict),
            "fixture_sha256": "",
            "matched_fixture": "",
            "format": "",
            "arch": "",
            "poc_cases": 0,
            "regression_cases": 0,
            "no_input_field": False,
            "runner_available": False,
            "runner": "",
            "runner_tier": "",
        }
        if isinstance(payload, dict):
            fixture_sha = str(payload.get("fixture_sha256", ""))
            entry.update({
                "fixture_sha256": fixture_sha,
                "matched_fixture": fixtures.get(fixture_sha, ""),
                "format": str(payload.get("format", "")),
                "arch": str(payload.get("arch", "")),
                "poc_cases": len(_as_list(payload.get("poc"))),
                "regression_cases": len(_as_list(payload.get("regression"))),
                "no_input_field": "no_input" in payload,
            })
            selection = _poc_runner_selection(entry["format"], entry["arch"])
            entry.update({
                "runner_available": selection["available"],
                "runner": selection["runner"],
                "runner_tier": selection["tier"],
            })
        rows.append(entry)
    rows.sort(key=lambda item: item["path"])
    return rows


def _census_claims(ctx: dict[str, Any]) -> dict[str, Any]:
    payload = _json_load(CLAIMS_PATH)
    text = _read_text(CLAIMS_PATH)
    return {
        "path": CLAIMS_PATH,
        "present": payload is not None,
        "sha256": _sha_text(text) if text else "",
        "bytes": len(text),
        "scope": str(_as_dict(payload).get("scope", "")),
        "declared_matrix": str(_as_dict(payload).get("declared_matrix", "")),
        "product_paths": [str(item) for item in _as_list(_as_dict(payload).get("product_paths"))],
        "research_paths": [str(item) for item in _as_list(_as_dict(payload).get("research_paths"))],
        "explicitly_unimplemented": [
            str(item) for item in _as_list(_as_dict(payload).get("explicitly_unimplemented"))
        ],
        "implemented_count": len(_as_list(_as_dict(payload).get("implemented"))),
        "latest_verified_ci": _as_dict(_as_dict(payload).get("latest_verified_ci")),
        "text_lower": text.lower(),
    }


def _census_docs(ctx: dict[str, Any]) -> dict[str, Any]:
    limitations = _read_text(LIMITATIONS_PATH)
    headings = [line.strip() for line in limitations.splitlines() if line.startswith("## ")]
    keywords = ("heap", "uaf", "loop", "sprintf", "native poc", "mach-o", "pe ",
                "capacity", "profile", "leaf")
    lowered = limitations.lower()
    readme = _read_text(README_PATH)
    matrix_lines = [
        _truncate(line.strip(), 200) for line in readme.splitlines()
        if any(token in line for token in ("ELF", "PE", "Mach-O", "x86-64", "x86_64", "arm64"))
    ][:20]
    return {
        "limitations": {
            "path": LIMITATIONS_PATH,
            "sha256": _sha_text(limitations) if limitations else "",
            "bytes": len(limitations),
            "headings": headings,
            "keyword_hits": {token: lowered.count(token) for token in keywords},
        },
        "readme": {
            "path": README_PATH,
            "sha256": _sha_text(readme) if readme else "",
            "bytes": len(readme),
            "matrix_lines": matrix_lines,
        },
    }


def _census_benchmarks(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in BENCHMARK_GLOBS:
        for raw in sorted(glob.glob(str(ROOT / pattern))):
            path = Path(raw)
            rel = path.relative_to(ROOT).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            payload = _json_load(rel)
            rows.append({
                "path": rel,
                "sha256": _sha_bytes(_read_bytes(ctx, path) or b""),
                "json_object": isinstance(payload, dict),
                "top_level_keys": sorted(str(key) for key in payload)[:20]
                if isinstance(payload, dict) else [],
            })
            if len(rows) >= MAX_BENCHMARK_ARTIFACTS:
                break
        if len(rows) >= MAX_BENCHMARK_ARTIFACTS:
            break
    rows.sort(key=lambda item: item["path"])
    return rows


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------

def _analyze_fixture(ctx: dict[str, Any], rel: str, data: bytes) -> dict[str, Any]:
    row: dict[str, Any] = {
        "probe_id": f"analyze:{rel}",
        "path": rel,
        "status": "ok",
        "error": None,
        "sinks": [],
        "kinds": [],
        "patchable": 0,
        "destination_kinds": [],
        "cell": None,
        "limitations": [],
    }
    analyzer, error = _load_module("app.services.repair.analyzer")
    if analyzer is None:
        row["status"] = "module_not_ready"
        row["error"] = error
        return row
    container = _detect_container(data)
    if container is not None:
        row["cell"] = _cell_key_for(
            str(getattr(container, "format", "unknown")),
            str(getattr(container, "arch", "unknown")),
            getattr(container, "bits", None),
        )
    try:
        analysis = analyzer.analyze(data)
    except Exception as exc:  # noqa: BLE001 - probe failure is evidence
        row["status"] = "probe_error"
        row["error"] = f"{type(exc).__name__}: {_truncate(exc)}"
        return row
    sinks = []
    for sink in _as_list(getattr(analysis, "sinks", [])):
        item = {
            "kind": str(getattr(sink, "kind", "")),
            "callee": str(getattr(sink, "callee", "")),
            "capacity": getattr(sink, "capacity", None),
            "destination_kind": str(getattr(sink, "destination_kind", "stack")),
            "patchable": bool(getattr(sink, "patchable", False)),
            "function_va": str(getattr(sink, "function_va", "") or ""),
        }
        sinks.append(item)
    row["sinks"] = sinks
    row["kinds"] = sorted({item["kind"] for item in sinks})
    row["patchable"] = sum(1 for item in sinks if item["patchable"])
    row["destination_kinds"] = sorted({item["destination_kind"] for item in sinks})
    row["limitations"] = [
        _truncate(item) for item in _as_list(getattr(analysis, "limitations", []))[:5]
    ]
    return row


def _extract_probe_row(report: Any, outcome: Any, *, probe_id: str, path: str,
                       source: str, requested_strategy: str,
                       verify: bool) -> dict[str, Any]:
    verification = _as_dict(getattr(report, "verification", {}))
    packet = _as_dict(verification.get("packet"))
    scope = _as_dict(packet.get("scope"))
    gate = _as_dict(verification.get("gate"))
    if not gate:
        gate = _as_dict(packet.get("gate"))
    checks = []
    for item in _as_list(packet.get("checks")):
        item_dict = _as_dict(item)
        checks.append({
            "id": str(item_dict.get("id", "")),
            "status": str(item_dict.get("status", "")),
        })
    runtime = _as_dict(getattr(report, "runtime", {}))
    matrix = _as_dict(getattr(report, "matrix", {}))
    findings = []
    for item in _as_list(getattr(report, "findings", [])):
        item_dict = _as_dict(item)
        findings.append({
            "kind": str(item_dict.get("kind", "")),
            "callee": str(item_dict.get("callee", "")),
            "address": str(item_dict.get("address", "")),
            "capacity": item_dict.get("capacity"),
            "destination_kind": str(item_dict.get("destination_kind", "")),
        })
    actions = []
    for item in _as_list(getattr(report, "actions", [])):
        item_dict = _as_dict(item)
        actions.append({
            "kind": str(item_dict.get("kind", "")),
            "site": str(item_dict.get("site", "")),
            "callee": str(item_dict.get("callee", "")),
            "capacity": item_dict.get("capacity"),
            "method": str(item_dict.get("method", "")),
        })
    profile = str(packet.get("profile", "") or scope.get("profile", "")
                  or verification.get("profile", "") or "")
    if not profile:
        for check in checks:
            detail = ""
            for raw in _as_list(packet.get("checks")):
                if str(_as_dict(raw).get("id", "")) == check["id"]:
                    detail = str(_as_dict(raw).get("detail", ""))
                    break
            match = re.search(r"profile=([A-Za-z0-9_.-]+)", detail)
            if match:
                profile = match.group(1)
                break
    checks_not_passed = sorted(
        check["id"] for check in checks if check["status"] != "passed"
    )
    limitations = [
        _truncate(item) for item in _as_list(getattr(report, "limitations", []))[:6]
    ]
    return {
        "probe_id": probe_id,
        "path": path,
        "source": source,
        "verify": verify,
        "requested_strategy": requested_strategy,
        "status": "ok",
        "error": None,
        "format": str(getattr(report, "format", "")),
        "arch": str(getattr(report, "arch", "")),
        "cell": str(matrix.get("cell") or ""),
        "disposition": str(getattr(report, "disposition", "")),
        "report_status": str(getattr(report, "status", "")),
        "strategy": str(getattr(report, "strategy", "")),
        "supported": bool(getattr(report, "supported", False)),
        "candidate": bool(getattr(outcome, "candidate", None)),
        "verified": bool(getattr(outcome, "verified", False)),
        "download_allowed": bool(getattr(outcome, "download_allowed", False)),
        "capacity": getattr(report, "capacity", None),
        "gate_outcome": str(gate.get("outcome", "")),
        "gate_success": bool(gate.get("success", False)),
        "gate_reason": _truncate(gate.get("reason")),
        "checks": checks,
        "checks_not_passed": checks_not_passed,
        "profile": profile,
        "runtime_tier": str(scope.get("runtime_tier", "")
                            or verification.get("tier", "")
                            or runtime.get("tier", "")),
        "runtime_verdict": str(scope.get("runtime_verdict", "")
                               or runtime.get("verdict", "")),
        "runtime_engine": str(runtime.get("engine", "")
                             or verification.get("engine", "")),
        "findings": findings,
        "actions": actions,
        "limitations": limitations,
        "error": _truncate(getattr(report, "error", "")),
    }


def _probe_repair(ctx: dict[str, Any], rel: str, source: str, data: bytes, *,
                  strategy: str, verify: bool, probe_id: str) -> dict[str, Any]:
    pipeline, error = _load_module("app.services.binary_pipeline")
    if pipeline is None or not hasattr(pipeline, "repair_any"):
        return {
            "probe_id": probe_id,
            "path": rel,
            "source": source,
            "verify": verify,
            "requested_strategy": strategy,
            "status": "module_not_ready",
            "error": error or "repair_any unavailable",
        }
    try:
        outcome = pipeline.repair_any(
            data,
            strategy=strategy,
            verify=verify,
            allow_static_only=True,
        )
    except Exception as exc:  # noqa: BLE001 - mid-flight pipeline is evidence
        return {
            "probe_id": probe_id,
            "path": rel,
            "source": source,
            "verify": verify,
            "requested_strategy": strategy,
            "status": "probe_error",
            "error": f"{type(exc).__name__}: {_truncate(exc)}",
        }
    report = getattr(outcome, "report", None)
    if report is None:
        return {
            "probe_id": probe_id,
            "path": rel,
            "source": source,
            "verify": verify,
            "requested_strategy": strategy,
            "status": "probe_error",
            "error": "outcome.report missing",
        }
    return _extract_probe_row(report, outcome, probe_id=probe_id, path=rel,
                              source=source, requested_strategy=strategy,
                              verify=verify)


def _budget_exceeded(ctx: dict[str, Any]) -> bool:
    started = ctx.get("_started")
    budget = ctx.get("_budget_seconds")
    if started is None or budget is None:
        return False
    return (time.monotonic() - started) > float(budget)


def _run_probes(ctx: dict[str, Any]) -> None:
    fixtures = _as_list(ctx["fixtures"])
    probes: list[dict[str, Any]] = []
    analysis_rows: list[dict[str, Any]] = []
    max_probes = ctx.get("_max_fixture_probes")
    probe_targets = [row for row in fixtures
                     if not row.get("skipped_over_size") and row.get("sha256")]
    if max_probes is not None:
        probe_targets = probe_targets[: int(max_probes)]
    skipped = 0
    for row in probe_targets:
        rel = str(row["path"])
        data = _read_bytes(ctx, ROOT / rel)
        if data is None:
            continue
        if _budget_exceeded(ctx):
            skipped += 1
            analysis_rows.append({"probe_id": f"analyze:{rel}", "path": rel,
                                  "status": "skipped_budget", "error": None})
            probes.append({"probe_id": f"fixture:{rel}", "path": rel,
                           "source": row["source"], "status": "skipped_budget",
                           "error": None})
            continue
        analysis_rows.append(_analyze_fixture(ctx, rel, data))
        probes.append(_probe_repair(
            ctx, rel, str(row["source"]), data,
            strategy="auto", verify=True, probe_id=f"fixture:{rel}",
        ))
    # Strategy selection probes: request every declared strategy of the cell on
    # the first fixture that maps to that cell, static-only (no execution).
    strategy_rows: list[dict[str, Any]] = []
    analyses = {row["path"]: row for row in analysis_rows if row.get("cell")}
    matrix_cells = {str(cell.get("key")): cell
                    for cell in _as_list(_as_dict(ctx.get("matrix")).get("cells"))}
    first_by_cell: dict[str, str] = {}
    for row in analysis_rows:
        cell = row.get("cell")
        if cell and cell not in first_by_cell and row.get("status") == "ok":
            first_by_cell[str(cell)] = str(row["path"])
    if ctx.get("_include_strategy_probes", True):
        for cell_key in sorted(first_by_cell):
            cell = _as_dict(matrix_cells.get(cell_key))
            data = _read_bytes(ctx, ROOT / first_by_cell[cell_key])
            if data is None:
                continue
            for strategy in _as_list(cell.get("strategies")):
                if _budget_exceeded(ctx):
                    break
                strategy_rows.append(_probe_repair(
                    ctx, first_by_cell[cell_key], "strategy_probe", data,
                    strategy=str(strategy), verify=False,
                    probe_id=f"strategy:{cell_key}:{strategy}",
                ))
    # Capacity probes are explicit because the strategy may be declared by the
    # engine/profile registry before the matrix lists it.
    capacity_rows: list[dict[str, Any]] = []
    capacity_paths = sorted({
        str(row["path"]) for row in fixtures
        if "capacity" in str(row["path"]).lower()
    })
    for rel in capacity_paths:
        data = _read_bytes(ctx, ROOT / rel)
        if data is None:
            continue
        if _budget_exceeded(ctx):
            capacity_rows.append({"probe_id": f"capacity:{rel}", "path": rel,
                                  "status": "skipped_budget", "requested_strategy": "capacity",
                                  "verify": True, "error": None})
            continue
        capacity_rows.append(_probe_repair(
            ctx, rel, "capacity_probe", data,
            strategy="capacity", verify=True, probe_id=f"capacity:{rel}",
        ))
    ctx["probes"] = {
        "fixtures": probes,
        "analysis": analysis_rows,
        "strategies": strategy_rows,
        "capacity": capacity_rows,
        "skipped_budget": skipped,
    }


def _apply_probe_results(ctx: dict[str, Any]) -> None:
    probes = _as_dict(ctx.get("probes"))
    by_path: dict[str, dict[str, Any]] = {}
    for row in _as_list(probes.get("fixtures")):
        if row.get("status") == "ok":
            by_path[str(row["path"])] = row
    analysis_by_path = {
        str(row["path"]): row for row in _as_list(probes.get("analysis"))
        if row.get("status") == "ok"
    }
    # Cases: measured disposition, target reachability and wrong-function risk.
    containers, _error = _load_module("app.services.containers")
    for case in _as_list(ctx.get("cases")):
        path = str(case.get("binary", ""))
        probe = by_path.get(path)
        if probe:
            case["measured_disposition"] = probe.get("disposition", "")
            case["measured_strategy"] = probe.get("strategy", "")
        analysis = analysis_by_path.get(path)
        target_va = case.get("target_va")
        if analysis is not None and target_va:
            target_int = int(str(target_va), 16)
            patchable = [sink for sink in _as_list(analysis.get("sinks"))
                         if _as_dict(sink).get("patchable")]
            case["measured_target_analyzed"] = any(
                str(_as_dict(sink).get("function_va", "")) == str(target_int)
                for sink in patchable
            )
            data = _read_bytes(ctx, ROOT / path)
            if data is not None and containers is not None:
                container = _detect_container(data)
                if container is not None:
                    symbols = _as_dict(getattr(container, "symbols", {}))
                    starts = sorted(int(va) for va in symbols
                                    if str(va).isdigit() or _is_int_like(va))
                    upper = None
                    for value in starts:
                        if value > target_int:
                            upper = value
                            break
                    addresses = []
                    for finding in _as_list(probe.get("findings") if probe else []):
                        address = str(_as_dict(finding).get("address", ""))
                        if address.startswith("0x"):
                            try:
                                addresses.append(int(address, 16))
                            except ValueError:
                                continue
                    if addresses and upper is not None:
                        case["measured_wrong_function_actions"] = all(
                            not (target_int <= address < upper) for address in addresses
                        )
    ctx["cases"] = _as_list(ctx.get("cases"))


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# capability measurement
# ---------------------------------------------------------------------------

def _measure_capability(ctx: dict[str, Any]) -> dict[str, Any]:
    matrix = _as_dict(ctx.get("matrix"))
    probes = _as_dict(ctx.get("probes"))
    analysis_rows = _as_list(probes.get("analysis"))
    capacity_rows = _as_list(probes.get("capacity"))
    strategies = {str(item) for item in _as_list(matrix.get("strategies"))}
    sink_classes = _as_dict(matrix.get("sink_classes"))
    profiles = _as_dict(matrix.get("evidence_profiles"))
    module, module_error = _load_module("app.services.repair.capacity")
    pipeline_source = _read_text(MODULE_PATHS["binary_pipeline"])
    capacity_declared = (
        "capacity" in strategies
        or "capacity" in {str(_as_dict(meta).get("strategy")) for meta in sink_classes.values()}
        or "native_poc_rewrite" in profiles
    )
    capacity_wired = any(token in pipeline_source for token in (
        "repair.capacity", "capacity_engine", "capacity_check_mismatch",
    )) and "TODO(lead-capacity)" not in pipeline_source
    capacity_observed = any(
        row.get("status") == "ok" and (
            str(row.get("strategy")) == "capacity"
            or any(str(_as_dict(action).get("kind")) in {"rewrite", "capacity"}
                   for action in _as_list(row.get("actions")))
            or any("capacity" in str(_as_dict(finding).get("kind"))
                   for finding in _as_list(row.get("findings")))
        )
        for row in capacity_rows
    )
    emitted_kinds = sorted({
        str(kind) for row in analysis_rows
        for kind in _as_list(_as_dict(row).get("kinds"))
    })
    emitted_destinations = sorted({
        str(kind) for row in analysis_rows
        for kind in _as_list(_as_dict(row).get("destination_kinds"))
    })
    sink_field = False
    analyzer, _analyzer_error = _load_module("app.services.repair.analyzer")
    if analyzer is not None:
        try:
            sink_field = "destination_kind" in getattr(analyzer.Sink, "__dataclass_fields__", {})
        except Exception:  # noqa: BLE001
            sink_field = "destination_kind" in inspect.getsource(analyzer)
    heap_emitted = "heap" in emitted_destinations
    heap_documented = "heap" in _read_text(MODULE_PATHS["analyzer"]).lower()
    heap_supported = sink_field and (heap_emitted or heap_documented)
    pipeline_handles_destination = "destination_kind" in pipeline_source
    unified_source = _read_text(MODULE_PATHS["unified_verification"])
    unified_handles_profile = "profile" in unified_source
    loop_targets = [
        case for case in _as_list(ctx.get("cases"))
        if "loop" in str(case.get("family", "")).lower()
    ]
    sprintf_supported = False
    if analyzer is not None:
        tokens = [str(item) for item in getattr(analyzer, "COPY_TOKENS", ())]
        sprintf_supported = any("sprintf" in token for token in tokens)
    return {
        "capacity": {
            "declared": bool(capacity_declared),
            "module": module is not None,
            "module_error": module_error,
            "module_path": MODULE_PATHS["capacity"],
            "wired_in_pipeline": bool(capacity_wired),
            "observed": bool(capacity_observed),
            "fixtures": [row["path"] for row in _as_list(ctx.get("fixtures"))
                         if "capacity" in str(row.get("path", "")).lower()],
            "manifest": str(ROOT / "fixtures/poc/marcx-capacity.json")
            if (ROOT / "fixtures/poc/marcx-capacity.json").is_file() else "",
        },
        "heap": {
            "sink_field": bool(sink_field),
            "analyzer_documents_heap": bool(heap_documented),
            "emitted_destination_kinds": emitted_destinations,
            "emitted_heap_sink": bool(heap_emitted),
            "pipeline_handles_destination_kind": bool(pipeline_handles_destination),
            "unified_gate_handles_profile": bool(unified_handles_profile),
            "supported": bool(heap_supported),
        },
        "analyzer": {
            "emitted_kinds": emitted_kinds,
            "sink_classes_declared": sorted(str(name) for name in sink_classes),
        },
        "loop": {
            "targets": [case.get("case_id") for case in loop_targets],
            "any_target_analyzed": any(
                bool(case.get("measured_target_analyzed")) for case in loop_targets
            ),
        },
        "sprintf": {"supported": bool(sprintf_supported)},
    }


# ---------------------------------------------------------------------------
# gap rows
# ---------------------------------------------------------------------------

def _gap(gap_id: str, category: str, symptom: str, evidence: list[str],
         severity: str, status: str, next_step: str, detector: str,
         *, novel: bool = False) -> dict[str, Any]:
    if category not in GAP_CATEGORIES:
        raise ValueError(f"unknown gap category: {category}")
    if status not in GAP_STATUSES:
        raise ValueError(f"unknown gap status: {status}")
    if severity not in GAP_SEVERITIES:
        raise ValueError(f"unknown gap severity: {severity}")
    cleaned = []
    for item in evidence:
        text = str(item).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return {
        "gap_id": gap_id,
        "category": category,
        "symptom": symptom,
        "evidence": cleaned,
        "severity": severity,
        "status": status,
        "next_step": next_step,
        "detector": detector,
        "lead_ref": KNOWN_LEAD_GAPS.get(gap_id, ""),
        "novel": bool(novel),
    }


def _status_rank(status: str) -> int:
    return STATUS_RANK.get(status, 99)


def _merge_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for gap in gaps:
        existing = merged.get(gap["gap_id"])
        if existing is None:
            merged[gap["gap_id"]] = gap
            continue
        for item in gap["evidence"]:
            if item not in existing["evidence"]:
                existing["evidence"].append(item)
        if SEVERITY_RANK[gap["severity"]] < SEVERITY_RANK[existing["severity"]]:
            existing["severity"] = gap["severity"]
        if _status_rank(gap["status"]) < _status_rank(existing["status"]):
            existing["status"] = gap["status"]
        existing["novel"] = bool(existing["novel"] or gap["novel"])
    rows = list(merged.values())
    rows.sort(key=lambda item: (CATEGORY_RANK[item["category"]],
                                SEVERITY_RANK[item["severity"]],
                                item["gap_id"]))
    return rows


def _gap_engine_capacity(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    capability = _as_dict(ctx["capability"]).get("capacity", {})
    declared = bool(capability.get("declared"))
    module = bool(capability.get("module"))
    wired = bool(capability.get("wired_in_pipeline"))
    observed = bool(capability.get("observed"))
    evidence = [
        f"census:matrix.strategies={_as_dict(ctx.get('matrix')).get('strategies')}",
        _source_line(MODULE_PATHS["repair_matrix"], "SINK_CLASSES"),
        _source_line(MODULE_PATHS["binary_pipeline"], "capacity_engine"),
        f"module:app.services.repair.capacity status="
        f"{'ok' if module else 'module_not_ready'}",
        f"artifact:{capability.get('manifest') or 'no capacity manifest'}",
    ]
    for row in _as_list(_as_dict(ctx.get("probes")).get("capacity")):
        evidence.append(
            f"probe:{row.get('probe_id')} status={row.get('status')} "
            f"disposition={row.get('disposition')} strategy={row.get('strategy')}"
        )
    if observed:
        status = "closed"
        symptom = (
            "capacity strategy is declared and a capacity rewrite candidate was "
            "measured on a capacity fixture"
        )
        next_step = "keep the capacity regression test and re-run after integration"
    elif declared and module and wired:
        status = "mitigated"
        symptom = (
            "capacity strategy is declared and the pipeline seam is wired, but no "
            "capacity rewrite candidate was measured on the capacity fixtures"
        )
        next_step = "check the capacity engine trigger conditions on the fixtures"
    elif declared or module or wired:
        status = "open"
        symptom = (
            "capacity-check repair is only partially integrated: "
            f"declared={declared} engine_module={module} pipeline_wired={wired}"
        )
        next_step = (
            "declare the capacity strategy/sink class in repair_matrix, wire the "
            "capacity engine into repair_any with profile native_poc_rewrite, and "
            "re-measure"
        )
    else:
        status = "open"
        symptom = (
            "capacity-check repair capability absent: no declared strategy, no "
            "engine module, no pipeline path"
        )
        next_step = "restore app/services/repair/capacity.py and wire it into repair_any"
    return [_gap(
        "EG-capacity-strategy", "engine_gap", symptom, evidence,
        "high", status, next_step, "engine_capacity", novel=not observed,
    )]


def _gap_engine_heap(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    heap = _as_dict(_as_dict(ctx["capability"]).get("heap"))
    supported = bool(heap.get("supported"))
    sinking = bool(heap.get("sink_field"))
    evidence = [
        _source_line(MODULE_PATHS["analyzer"], "destination_kind"),
        f"census:destination_kinds={heap.get('emitted_destination_kinds')}",
        f"census:pipeline_handles_destination_kind="
        f"{heap.get('pipeline_handles_destination_kind')}",
    ]
    if supported:
        status = "closed"
        symptom = (
            "heap destination capacity recovery is present in the analyzer "
            f"(sink_field={sinking}, emitted={heap.get('emitted_heap_sink')})"
        )
        next_step = "keep heap negative controls; the gate profile must stay native_poc"
    else:
        status = "open"
        symptom = (
            "heap/global copy destinations have no recovered capacity: the "
            "analyzer only models stack frame geometry, so heap overflow fixtures "
            "stay analysis-only (Lead G2)"
        )
        next_step = (
            "add Sink.destination_kind and same-function malloc/calloc capacity "
            "recovery, then re-measure"
        )
    return [_gap(
        "EG-heap-destination", "engine_gap", symptom, evidence,
        "high" if not supported else "info", status, next_step,
        "engine_heap", novel=not supported,
    )]


def _gap_sink_classes(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = _as_dict(ctx.get("matrix"))
    declared = _as_dict(matrix.get("sink_classes"))
    capability = _as_dict(ctx["capability"])
    emitted = set(_as_list(_as_dict(capability.get("analyzer")).get("emitted_kinds")))
    analysis_source = _read_text(MODULE_PATHS["analyzer"])
    i386_source = _read_text(MODULE_PATHS["analyzer_i386"])
    gaps: list[dict[str, Any]] = []
    emitter_source = {
        "unbounded_copy": "analyzer.py",
        "memcpy_length": "analyzer.py + analyzer_i386.py",
        "syscall_length": "analyzer.py x86_64 only",
        "checked_copy": "analyzer.py x86_64/arm64 only",
        "immediate_length": "",
        "capacity_check_mismatch": "capacity.py (separate engine)",
    }
    arch_emitters = {
        "x86_64": {"unbounded_copy", "memcpy_length", "syscall_length", "checked_copy"},
        "i386": {"unbounded_copy", "memcpy_length"},
        "arm64": {"unbounded_copy", "memcpy_length", "checked_copy"},
    }
    for kind in sorted(declared):
        meta = _as_dict(declared[kind])
        if kind == "immediate_length":
            has_emitter = ANALYZER_KIND_MARKERS[kind] in analysis_source
            status = "open" if not has_emitter else "closed"
            gaps.append(_gap(
                "EG-sink-class-dead-immediate_length", "engine_gap",
                "repair_matrix declares sink class immediate_length but no "
                "analyzer path emits it (read_or_write_length findings live in the "
                "legacy engine only), so the class is a dead declaration",
                [
                    _source_line(MODULE_PATHS["repair_matrix"], '"immediate_length"'),
                    _source_line(MODULE_PATHS["analyzer"], "immediate_length"),
                    f"census:emitted_kinds={sorted(emitted)}",
                ],
                "high" if not has_emitter else "info",
                status,
                "remove the class from repair_matrix or implement an analyzer path",
                "engine_sink_classes", novel=not has_emitter,
            ))
            continue
        if kind == "capacity_check_mismatch":
            continue
        declared_arches = sorted({
            str(cell.get("arch")) for cell in _as_list(matrix.get("cells"))
            if kind in _as_list(cell.get("sink_classes"))
        })
        for arch in declared_arches:
            if kind in arch_emitters.get(arch, set()):
                continue
            gaps.append(_gap(
                f"EG-sink-class-not-emittable::{kind}::{arch}", "engine_gap",
                f"repair_matrix declares sink class {kind} for {arch} cells but "
                f"the {arch} analyzer has no emission path (emitter: "
                f"{emitter_source.get(kind) or 'none'})",
                [
                    _source_line(MODULE_PATHS["repair_matrix"], f'"{kind}"'),
                    _source_line(
                        MODULE_PATHS["analyzer_i386"] if arch == "i386"
                        else MODULE_PATHS["analyzer"],
                        kind if arch != "arm64" else "checked_copy",
                    ),
                    f"census:emitted_kinds={sorted(emitted)}",
                ],
                "medium", "open",
                f"declare the class only for cells that can emit it, or add the "
                f"{arch} analyzer path",
                "engine_sink_classes", novel=True,
            ))
    return gaps


def _gap_strategy_request(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = _as_dict(ctx.get("matrix"))
    cells = {str(cell.get("key")): cell
             for cell in _as_list(matrix.get("cells"))}
    mismatched = []
    for row in _as_list(_as_dict(ctx.get("probes")).get("strategies")):
        if row.get("status") != "ok":
            continue
        cell = cells.get(str(row.get("cell")))
        if cell is None:
            continue
        requested = str(row.get("requested_strategy", ""))
        if requested not in _as_list(cell.get("strategies")):
            continue
        delivered = str(row.get("strategy", ""))
        disposition = str(row.get("disposition", ""))
        if disposition in {"static_only_patch", "verified_patch", "not_verified"} \
                and delivered and delivered != requested:
            mismatched.append((row.get("probe_id"), requested, delivered))
    evidence = [
        f"probe:{probe_id} requested={requested} delivered={delivered}"
        for probe_id, requested, delivered in mismatched[:8]
    ]
    status = "open" if mismatched else "closed"
    symptom = (
        f"{len(mismatched)} strategy-select probe(s) were accepted by the matrix "
        "but the pipeline delivered a different strategy; only the legacy path "
        "rejects a mismatched requested strategy"
        if mismatched else
        "every requested matrix strategy either matched the delivered strategy "
        "or was rejected"
    )
    return [_gap(
        "EG-strategy-request-not-honored", "engine_gap", symptom,
        evidence or ["census:no strategy-select mismatch measured"],
        "medium" if mismatched else "info", status,
        "reject or annotate requested strategies that the produced action does "
        "not honor (finish_candidate strategy check)",
        "engine_strategy_request", novel=bool(mismatched),
    )]


def _gap_target_scope(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    pipeline, error = _load_module("app.services.binary_pipeline")
    params = _signature_params(getattr(pipeline, "repair_any", lambda: None)) \
        if pipeline is not None else []
    has_target = any(name in params for name in ("target", "function", "target_va"))
    cases = _as_list(ctx.get("cases"))
    not_analyzed = [case for case in cases if case.get("measured_target_analyzed") is False]
    wrong_function = [case for case in cases
                      if case.get("measured_wrong_function_actions") is True]
    evidence = [
        f"census:repair_any parameters={params}",
        _source_line(MODULE_PATHS["binary_pipeline"], "def repair_any"),
    ]
    for case in wrong_function[:6]:
        evidence.append(
            f"probe:{case.get('binary')} patched actions outside declared target "
            f"{case.get('target')} ({case.get('target_va')})"
        )
    status = "closed" if has_target else "open"
    symptom = (
        "repair_any has no caller-declared target selector; the engine patches "
        "the first patchable sink anywhere in the image. Measured: "
        f"{len(not_analyzed)}/{len(cases)} declared benchmark targets have no "
        f"patchable deterministic sink and {len(wrong_function)} fixture(s) were "
        "patched outside the declared target function"
    )
    return [_gap(
        "EG-target-scope", "engine_gap", symptom,
        evidence,
        "medium", status,
        "add an optional target/function selector or a target-identity gate "
        "check so a whole-image patch cannot be reported as repairing the "
        "declared function",
        "engine_target_scope", novel=True,
    )]


def _gap_heap_oracle(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    heap = _as_dict(_as_dict(ctx["capability"]).get("heap"))
    sink_field = bool(heap.get("sink_field"))
    pipeline_ok = bool(heap.get("pipeline_handles_destination_kind"))
    gate_ok = bool(heap.get("unified_gate_handles_profile"))
    evidence = [
        _source_line(MODULE_PATHS["analyzer"], "destination_kind"),
        _source_line(MODULE_PATHS["binary_pipeline"], "destination_kind"),
        _source_line(MODULE_PATHS["unified_verification"], "profile"),
    ]
    if sink_field and pipeline_ok and gate_ok:
        status = "closed"
        symptom = (
            "non-stack destinations are declared in the sink model, routed to an "
            "external-PoC profile and no longer judged by the stack/Unicorn oracle"
        )
        next_step = "keep the heap/non-stack negative control in the gate tests"
    elif sink_field and (pipeline_ok or gate_ok):
        status = "mitigated"
        symptom = (
            "destination_kind exists but the oracle routing is incomplete: "
            f"pipeline={pipeline_ok} gate_profile={gate_ok}"
        )
        next_step = "route non-stack sinks through native_poc and set runtime=None"
    else:
        status = "open"
        symptom = (
            "the runtime oracle is stack-capacity specific (Unicorn stack cases / "
            "legacy boundary cases); heap and global destinations cannot be judged "
            "by it, yet the pipeline selects it for every produced sink (Lead G3)"
        )
        next_step = (
            "add Sink.destination_kind and select the external-PoC evidence "
            "profile (runtime=None) for non-stack destinations"
        )
    return [_gap(
        "OG-heap-destination-oracle", "oracle_gap", symptom, evidence,
        "high" if not sink_field else "medium", status, next_step,
        "oracle_destinations", novel=not sink_field,
    )]


def _unified_scenario(ctx: dict[str, Any], name: str) -> dict[str, Any]:
    return _as_dict(_as_dict(_as_dict(ctx.get("gates")).get("unified")).get(
        "scenarios")).get(name, {})


def _check_status(scenario: dict[str, Any], check_id: str) -> str:
    for check in _as_list(scenario.get("checks")):
        item = _as_dict(check)
        if str(item.get("id", "")) == check_id:
            return str(item.get("status", ""))
    return "absent"


def _gap_gate_profiles(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    unified = _as_dict(_as_dict(ctx.get("gates")).get("unified"))
    matrix = _as_dict(ctx.get("matrix"))
    profiles = _as_dict(matrix.get("evidence_profiles"))
    params = _as_list(unified.get("parameters"))
    supports_profile = "profile" in params
    supports_rewrite = "rewrite_actions" in params
    supports_cell = "cell" in params
    declared = bool(profiles)
    evidence = [
        _source_line(MODULE_PATHS["repair_matrix"], "EVIDENCE_PROFILES"),
        _source_line(MODULE_PATHS["unified_verification"], "profile.declared"),
        f"census:build parameters={params}",
        f"census:evidence_profiles={sorted(profiles)}",
    ]
    if declared and supports_profile:
        status = "closed"
        symptom = (
            f"declared evidence-profile registry with {len(profiles)} profile(s) "
            "and the unified gate enforces the declared profile"
        )
        next_step = "keep the profile/evidence mismatch test"
    elif declared or supports_profile:
        status = "mitigated"
        symptom = (
            f"profile wall is partially integrated: registry={declared} "
            f"build_profile_kwarg={supports_profile}"
        )
        next_step = "add the missing half of the profile/evidence integration"
    else:
        status = "open"
        symptom = (
            "no declared evidence-profile registry: the unified gate uses one "
            "implicit acceptance model for every strategy, container and "
            "destination kind, so capacity/heap/native-PoC evidence cannot be "
            "expressed by the gate (Lead G6)"
        )
        next_step = (
            "declare repair_matrix.EVIDENCE_PROFILES and add profile/evidence/"
            "required_checks checks to unified_verification.build"
        )
    gaps = [_gap(
        "GM-profile-registry", "gate_mismatch", symptom, evidence,
        "high" if not declared else "info", status, next_step,
        "gate_profiles", novel=not declared,
    )]
    # Unknown profile must fail closed when the registry exists.
    unknown = _unified_scenario(ctx, "unknown_profile")
    checks = {str(_as_dict(item).get("id")) for item in _as_list(unknown.get("checks"))}
    unknown_failed = str(unknown.get("outcome")) == "rejected" or (
        "profile.declared" in checks
        and _check_status(unknown, "profile.declared") == "failed"
    )
    gaps.append(_gap(
        "GM-profile-evidence-enforcement", "gate_mismatch",
        (
            "an unknown evidence profile fails closed in the unified gate"
            if unknown_failed else
            "an unknown/mismatched evidence profile is not rejected: the gate "
            "has no profile-evidence enforcement to measure"
        ),
        [
            f"gate-scenario:unknown_profile={_truncate(unknown.get('outcome'))} "
            f"profile.declared={_check_status(unknown, 'profile.declared')}",
        ],
        "info" if unknown_failed else "high",
        "closed" if unknown_failed else ("mitigated" if declared else "open"),
        "verify unknown and mismatched profiles fail closed" if not unknown_failed
        else "keep the negative profile test",
        "gate_profile_enforcement", novel=not unknown_failed,
    ))
    # Declared profile check ids must exist and be satisfiable.
    observed_ids = {str(item) for item in _as_list(unified.get("check_ids"))}
    for profile_name in sorted(profiles):
        meta = _as_dict(profiles[profile_name])
        required = [str(item) for item in _as_list(meta.get("required_checks"))]
        missing = [item for item in required if item not in observed_ids]
        gaps.append(_gap(
            f"GM-profile-check-missing::{profile_name}", "gate_mismatch",
            (
                f"profile {profile_name} requires gate check id(s) that the gate "
                f"never emits: {missing}"
                if missing else
                f"every check required by profile {profile_name} is emitted by the "
                "unified gate"
            ),
            [f"census:profile={profile_name} required={required}",
             f"census:observed_check_ids={sorted(observed_ids)}"],
            "high" if missing else "info",
            "open" if missing else "closed",
            "fix the profile/check-id mismatch" if missing
            else "keep the registry and gate in sync",
            "gate_profile_checks",
        ))
    return gaps


def _gap_gate_cell_tier(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    unified = _as_dict(_as_dict(ctx.get("gates")).get("unified"))
    params = _as_list(unified.get("parameters"))
    cell_supported = "cell" in params
    cell_mismatch = _unified_scenario(ctx, "cell_mismatch")
    cell_status = _check_status(cell_mismatch, "container.cell")
    tier_mismatch = _unified_scenario(ctx, "cell_tier_mismatch")
    tier_status = _check_status(tier_mismatch, "runtime.cell_tier")
    cell_enforced = cell_supported and cell_status == "failed"
    tier_enforced = cell_supported and tier_status == "failed"
    gaps = [_gap(
        "GM-gate-cell", "gate_mismatch",
        (
            "the unified gate validates the exact matrix cell (container/arch/bits/"
            "endian) and rejects a mismatched cell"
            if cell_enforced else
            "the unified gate never validates the exact matrix cell: only the "
            "(format, arch) pair via supported_pairs() is checked, so bitness/"
            "endian are not part of the acceptance claim (Lead G7)"
        ),
        [
            f"census:build parameters={params}",
            f"gate-scenario:cell_mismatch outcome={_truncate(cell_mismatch.get('outcome'))} "
            f"container.cell={cell_status}",
            _source_line(MODULE_PATHS["repair_matrix"], "supported_pairs"),
        ],
        "info" if cell_enforced else "high",
        "closed" if cell_enforced else "open",
        "keep container.cell enforced" if cell_enforced else
        "add a container.cell required check to unified_verification.build",
        "gate_cell", novel=not cell_enforced,
    ), _gap(
        "GM-gate-runtime-tier", "gate_mismatch",
        (
            "the unified gate rejects a runtime tier that the exact cell does not "
            "declare"
            if tier_enforced else
            "matrix cells declare runtime_tiers but the gate accepts any native/"
            "emulated tier; host availability is not part of the acceptance packet "
            "(Lead G8)"
        ),
        [
            f"gate-scenario:cell_tier_mismatch "
            f"outcome={_truncate(tier_mismatch.get('outcome'))} "
            f"runtime.cell_tier={tier_status}",
            _source_line(MODULE_PATHS["unified_verification"], "runtime.tier"),
        ],
        "info" if tier_enforced else "medium",
        "closed" if tier_enforced else "open",
        "keep runtime.cell_tier enforced" if tier_enforced else
        "declare cell runtime_tiers in the gate and check the supplied tier",
        "gate_cell_tier", novel=not tier_enforced,
    )]
    return gaps


def _gap_gate_rewrite(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    unified = _as_dict(_as_dict(ctx.get("gates")).get("unified"))
    params = _as_list(unified.get("parameters"))
    supports_rewrite = "rewrite_actions" in params
    tampered = _unified_scenario(ctx, "rewrite_tampered")
    valid = _unified_scenario(ctx, "rewrite_valid")
    failed_ids = sorted(
        str(_as_dict(check).get("id")) for check in _as_list(tampered.get("checks"))
        if _as_dict(check).get("status") == "failed"
    )
    rewrite_checks = [item for item in failed_ids
                      if item.startswith("patch.rewrite") or item.startswith("patch.capacity")]
    tamper_detected = supports_rewrite and bool(rewrite_checks)
    valid_passed = supports_rewrite and not any(
        _as_dict(check).get("status") != "passed" for check in _as_list(valid.get("checks"))
    )
    status = "closed" if tamper_detected and valid_passed else "open"
    return [_gap(
        "GM-gate-rewrite", "gate_mismatch",
        (
            "in-place rewrite actions are re-derived from the actual original/"
            "candidate bytes and a tampered action fails the gate"
            if status == "closed" else
            "the gate never re-derives rewrite actions from bytes: it trusts the "
            "action list (count only), so a capacity/rewrite candidate has no "
            "byte-level patch verification (Lead G1)"
        ),
        [
            f"census:build parameters={params}",
            f"gate-scenario:rewrite_tampered failed={failed_ids}",
            f"gate-scenario:rewrite_valid outcome={_truncate(valid.get('outcome'))}",
            _source_line(MODULE_PATHS["unified_verification"], "repair.action"),
        ],
        "high" if status == "open" else "info", status,
        "keep patch.rewrite/patch.capacity re-derivation" if status == "closed"
        else "add a rewrite-action re-derivation check (before/after hex vs bytes)",
        "gate_rewrite", novel=status == "open",
    )]


def _gap_gate_no_input(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    declared = _unified_scenario(ctx, "no_input_declared")
    undeclared = _unified_scenario(ctx, "empty_regression_undeclared")
    declared_status = _check_status(declared, "poc.native.regression")
    undeclared_status = _check_status(undeclared, "poc.native.regression")
    signature_declared = _check_status(declared, "poc.native.stdout_signature")
    poc_runner, _error = _load_module("app.services.poc_runner")
    runner_support = False
    if poc_runner is not None:
        try:
            evidence_cls = getattr(poc_runner, "PocEvidence")
            runner_support = "no_input" in getattr(evidence_cls, "__dataclass_fields__", {})
        except Exception:  # noqa: BLE001
            runner_support = False
    closed = declared_status == "passed" and undeclared_status == "failed"
    evidence = [
        f"gate-scenario:no_input_declared poc.native.regression={declared_status}",
        f"gate-scenario:empty_regression_undeclared "
        f"poc.native.regression={undeclared_status}",
        f"gate-scenario:no_input_declared "
        f"poc.native.stdout_signature={signature_declared}",
        _source_line(MODULE_PATHS["unified_verification"], "poc.native.regression"),
        f"module:poc_runner no_input_field={runner_support}",
    ]
    return [_gap(
        "GM-gate-no-input", "gate_mismatch",
        (
            "a declared no-input/UAF manifest passes poc.native.regression as "
            "not_applicable_no_input while an undeclared empty regression list "
            "still fails"
            if closed else
            "documented no-input/UAF manifests (empty regression list) fail "
            "poc.native.regression: the gate treats an empty regression list as a "
            "hard failure instead of the declared no-input evidence model (Lead G4)"
        ),
        evidence,
        "info" if closed else "high", "closed" if closed else "open",
        "keep the declared/undeclared no-input pair" if closed else
        "add manifest-level no_input, record it in PocEvidence and map an empty "
        "declared regression to not_applicable_no_input",
        "gate_no_input", novel=not closed,
    )]


def _gap_gate_poc_unavailable(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    scenario = _unified_scenario(ctx, "poc_unavailable")
    outcome = str(scenario.get("outcome", ""))
    failed = sorted(
        str(_as_dict(check).get("id")) for check in _as_list(scenario.get("checks"))
        if _as_dict(check).get("status") == "failed"
    )
    fixed = outcome in {"inconclusive", "unavailable"} and not failed
    return [_gap(
        "GM-gate-poc-unavailable", "gate_mismatch",
        (
            "an unavailable external-PoC runner keeps the gate inconclusive "
            "instead of rejecting the candidate"
            if fixed else
            "an unavailable external-PoC runner turns poc.native.* checks into "
            "FAILED and the outcome into 'rejected' instead of 'inconclusive', so "
            "missing evidence is misreported as a failed repair (Lead G5)"
        ),
        [
            f"gate-scenario:poc_unavailable outcome={outcome} failed={failed}",
            _source_line(MODULE_PATHS["unified_verification"], "poc.native.available"),
        ],
        "info" if fixed else "high", "closed" if fixed else "open",
        "keep unavailable evidence as not_run/inconclusive" if fixed else
        "make unavailable evidence not_run (never FAILED) and keep the outcome "
        "inconclusive",
        "gate_poc_unavailable", novel=not fixed,
    )]


def _gap_gate_legacy(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    legacy = _as_dict(_as_dict(ctx.get("gates")).get("legacy"))
    ids = {str(item) for item in _as_list(legacy.get("check_ids"))}
    profile_enforced = "profile.declared" in ids and "profile.required_checks" in ids
    accepts_poc = bool(legacy.get("accepts_external_poc"))
    pipeline_source = _read_text(MODULE_PATHS["binary_pipeline"])
    legacy_manifest_routed = (
        "poc_manifest" in pipeline_source
        and "_from_elf_legacy" in pipeline_source
        and "run_poc" in pipeline_source
    )
    gaps = [_gap(
        "GM-legacy-gate-profile", "gate_mismatch",
        (
            "the legacy quick-repair gate enforces the declared evidence profile "
            "and its required checks"
            if profile_enforced else
            "the legacy quick-repair gate has no declared evidence profile: its "
            "check set is mode-specific and predates the profile registry, so the "
            "same repair class is accepted by two different evidence models "
            "(Lead G25)"
        ),
        [
            f"census:legacy_check_ids={sorted(ids)}",
            f"census:legacy_accepts_external_poc={accepts_poc}",
            _source_line(MODULE_PATHS["binary_verification"], "profile.declared"),
        ],
        "info" if profile_enforced else "medium",
        "closed" if profile_enforced else "open",
        "keep legacy profile checks" if profile_enforced else
        "derive a profile from the report mode and enforce its required checks "
        "in binary_verification.build_verification",
        "gate_legacy_profile", novel=not profile_enforced,
    ), _gap(
        "GM-legacy-gate-poc-manifest", "gate_mismatch",
        (
            "legacy ELF x86-64 repairs consume the supplied PoC manifest either "
            "through the legacy gate or through explicit routing to the unified "
            "gate"
            if accepts_poc or legacy_manifest_routed else
            "the legacy ELF x86-64 pipeline path ignores a supplied PoC manifest: "
            "repair_any routes manifest-bearing non-generic inputs to repair_elf "
            "and build_verification has no external-PoC parameter, so evidence is "
            "silently dropped (Lead G9)"
        ),
        [
            f"census:legacy_build_parameters={_as_list(legacy.get('parameters'))}",
            f"census:pipeline_legacy_manifest_routed={legacy_manifest_routed}",
            _source_line(MODULE_PATHS["binary_pipeline"], "_from_elf_legacy"),
            _source_line(MODULE_PATHS["binary_verification"], "def build_verification"),
        ],
        "info" if (accepts_poc or legacy_manifest_routed) else "medium",
        "closed" if (accepts_poc or legacy_manifest_routed) else "open",
        "keep manifest routing explicit" if (accepts_poc or legacy_manifest_routed) else
        "route manifest-bearing repairs through the unified gate or add external "
        "PoC evidence to the legacy gate",
        "gate_legacy_poc", novel=not (accepts_poc or legacy_manifest_routed),
    )]
    return gaps


def _gap_gate_scenarios(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    unified = _as_dict(_as_dict(ctx.get("gates")).get("unified"))
    legacy = _as_dict(_as_dict(ctx.get("gates")).get("legacy"))
    errors = []
    for name, result in sorted(_as_dict(unified.get("scenarios")).items()):
        error = str(_as_dict(result).get("error") or "")
        if error:
            errors.append(f"unified scenario {name}: {error}")
    for name, result in sorted(_as_dict(legacy.get("scenarios")).items()):
        error = str(_as_dict(result).get("error") or "")
        if error:
            errors.append(f"legacy scenario {name}: {error}")
    probe_errors = [
        f"{row.get('probe_id')}: {row.get('error')}"
        for row in _as_list(_as_dict(ctx.get("probes")).get("fixtures"))
        if row.get("status") == "probe_error"
    ]
    return [_gap(
        "GM-gate-scenario-execution", "gate_mismatch",
        (
            "every gate census scenario and fixture probe executed without a "
            "module/signature error"
            if not errors and not probe_errors else
            "the audit could not exercise part of the acceptance model: "
            f"{len(errors)} gate scenario error(s), {len(probe_errors)} probe "
            "error(s) (see evidence; a mid-flight module is recorded as "
            "module_not_ready instead of crashing the audit)"
        ),
        (errors + probe_errors)[:8] or ["census:no gate/probe execution errors"],
        "info" if not errors and not probe_errors else "medium",
        "closed" if not errors and not probe_errors else "open",
        "re-run after the affected modules settle",
        "gate_scenario_execution",
    )]


def _gap_runtime_sources(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = _as_dict(ctx.get("matrix"))
    runtime = _as_dict(ctx.get("runtime"))
    sources = _as_list(runtime.get("sources"))
    host = _as_dict(runtime.get("host"))
    macho = _as_dict(runtime.get("macho_native"))
    gaps: list[dict[str, Any]] = []
    for cell in _as_list(matrix.get("cells")):
        key = str(cell.get("key"))
        container = str(cell.get("container"))
        arch = str(cell.get("arch"))
        for tier in _as_list(cell.get("runtime_tiers")):
            tier = str(tier)
            candidates = [
                row for row in sources
                if _as_dict(row).get("format") == container
                and _as_dict(row).get("arch") == arch
                and _as_dict(row).get("runtime_tier") == tier
            ]
            available = any(bool(_as_dict(row).get("available")) for row in candidates)
            if available:
                continue
            if tier == "native_run" and container == "macho":
                detail = (
                    "macho_native.available()="
                    f"{macho.get('available')} host_supported="
                    f"{macho.get('host_supported')}"
                )
                status = "open"
                next_step = (
                    "run the audit on a macOS host with codesign, or mark the "
                    "Mach-O cells as platform-gated in the report"
                )
                severity = "high"
            else:
                detail = f"no runtime source for {container}/{arch} tier {tier}"
                status = "open"
                next_step = "add a runtime source or remove the declared tier"
                severity = "medium"
            gaps.append(_gap(
                f"RG-runtime-evidence::{key}::{tier}", "runtime_gap",
                f"matrix cell {key} declares runtime tier {tier} but no measured "
                f"runtime source can produce it on this host ({detail})",
                [
                    f"census:runtime_sources={len(candidates)} candidate(s)",
                    f"census:host={host.get('platform')}/{host.get('arch')}",
                    _source_line(MODULE_PATHS["repair_matrix"], "runtime_tiers"),
                ],
                severity, status, next_step, "runtime_sources",
            ))
    # External PoC evidence source per (format, arch).
    for row in sources:
        item = _as_dict(row)
        if item.get("source") != "external_poc" or item.get("available"):
            continue
        container = str(item.get("format"))
        arch = str(item.get("arch"))
        pair = f"{container}/{arch}"
        documented_non_goal = (
            (container == "pe")
            or (container == "macho" and arch == "i386")
        )
        if documented_non_goal:
            gaps.append(_gap(
                f"RG-external-poc::<doc>::{pair}", "non_goal",
                f"external PoC execution is unavailable for {pair}; this matches "
                "the documented limitation that PE and 32-bit Mach-O PoC execution "
                "remain unavailable",
                [
                    f"census:runner={item.get('selector') or 'none'}",
                    _source_line(CLAIMS_PATH, "PE and 32-bit Mach-O"),
                ],
                "info", "non_goal",
                "keep the documented non-goal; do not fabricate PoC evidence",
                "runtime_sources",
            ))
            continue
        status = "open"
        if container == "macho" and bool(macho.get("available")):
            symptom = (
                f"native Mach-O runtime can execute {arch} on this host "
                f"({host.get('arch')}) but the external-PoC runner selects none: "
                "the two acceptance paths disagree about what this cell can prove"
            )
            next_step = (
                "teach the PoC runner the same arch-translation the native runner "
                "uses, or declare external PoC unavailable for this cell"
            )
            severity = "low"
        elif container == "elf":
            symptom = (
                f"external PoC evidence is unavailable for {pair}: shipped PoC "
                "manifests for this cell cannot be executed through the product "
                f"runner on this host ({host.get('platform')}/{host.get('arch')})"
            )
            next_step = (
                "wire the declared guest runner (Lima/qemu) into poc_runner or "
                "document the host requirement"
            )
            severity = "medium"
        else:
            symptom = f"external PoC evidence is unavailable for {pair}"
            next_step = "document or provide a runner"
            severity = "medium"
        gaps.append(_gap(
            f"RG-external-poc::{pair}", "runtime_gap", symptom,
            [
                f"census:selector={item.get('selector') or 'none'}",
                f"census:host={host.get('platform')}/{host.get('arch')}",
                f"census:limactl={host.get('limactl') or 'none'}",
            ],
            severity, status, next_step, "runtime_sources", novel=True,
        ))
    return gaps


def _gap_oracle_wrong_function(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    wrong = [case for case in _as_list(ctx.get("cases"))
             if case.get("measured_wrong_function_actions") is True]
    not_analyzed = [case for case in _as_list(ctx.get("cases"))
                    if case.get("measured_target_analyzed") is False]
    evidence = [
        f"probe:{case.get('binary')} findings outside target "
        f"{case.get('target')} ({case.get('target_va')})"
        for case in wrong[:8]
    ]
    evidence += [
        f"probe:{case.get('binary')} no patchable sink in target "
        f"{case.get('target')}"
        for case in not_analyzed[:8]
    ]
    status = "open" if wrong else "closed"
    return [_gap(
        "OG-wrong-function-candidate", "oracle_gap",
        (
            "no fixture produced a candidate whose patch actions all fall outside "
            "the declared benchmark target function"
            if not wrong else
            f"{len(wrong)} fixture(s) produced byte patches outside the declared "
            "benchmark target function (whole-image scan): the gate/judge can "
            "only reject them by unrelated boundary semantics; nothing proves "
            "the patch repairs the declared defect"
        ),
        evidence or ["census:no wrong-function action measured"],
        "medium" if wrong else "info", status,
        "bind candidate actions to a declared target function or reject "
        "out-of-target patch sites",
        "oracle_wrong_function", novel=bool(wrong),
    )]


def _gap_cases(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    cases = _as_list(ctx.get("cases"))
    mismatched = [
        case for case in cases
        if case.get("baseline_expected")
        and case.get("measured_disposition")
        and case.get("baseline_expected") != case.get("measured_disposition")
    ]
    not_analyzed = [
        case for case in cases if case.get("measured_target_analyzed") is False
    ]
    documented = [
        case for case in not_analyzed
        if any(token in str(case.get("family", "")).lower() for token in (
            "loop", "semantic", "heap", "uaf", "non-template"))
    ]
    gaps = [_gap(
        "MM-case-baseline-mismatch", "matrix_claim_mismatch",
        (
            "every measured benchmark disposition matches its declared "
            "baseline_expected"
            if not mismatched else
            f"{len(mismatched)} of {len(cases)} hard-case benchmark dispositions "
            "differ from their declared baseline_expected"
        ),
        [
            f"probe:{case.get('binary')} expected={case.get('baseline_expected')} "
            f"measured={case.get('measured_disposition')}"
            for case in mismatched[:8]
        ] or ["census:no benchmark disposition mismatch measured"],
        "high" if mismatched else "info",
        "open" if mismatched else "closed",
        "reconcile the benchmark expectations with the deterministic engine"
        if mismatched else "keep the baseline table in sync",
        "cases_baseline",
    ), _gap(
        "EG-cases-target-not-analyzed", "engine_gap",
        (
            f"{len(not_analyzed)} of {len(cases)} declared hard-case targets have "
            "no patchable deterministic sink in the target function; the declared "
            "baseline matches this for the documented non-template families, so "
            "these are AI-benchmark/non-goal cases, not hidden successes"
            if not_analyzed else
            "every declared hard-case target has a patchable deterministic sink"
        ),
        [
            f"probe:{case.get('binary')} target={case.get('target')} "
            f"state={case.get('target_state')}"
            for case in not_analyzed[:10]
        ] or ["census:no target-reachability gap measured"],
        "info" if documented else ("medium" if not_analyzed else "info"),
        "non_goal" if not_analyzed and documented else (
            "open" if not_analyzed else "closed"),
        "keep these cases in the AI/non-goal evidence set; do not claim "
        "deterministic success" if not_analyzed else "no action",
        "cases_target",
    )]
    return gaps


def _gap_claims_docs(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    claims = _as_dict(ctx.get("claims"))
    docs = _as_dict(ctx.get("docs"))
    limitations = _as_dict(docs.get("limitations"))
    capability = _as_dict(ctx.get("capability"))
    capacity = _as_dict(capability.get("capacity"))
    heap = _as_dict(capability.get("heap"))
    claims_text = str(claims.get("text_lower", ""))
    unimplemented = " | ".join(
        str(item) for item in _as_list(claims.get("explicitly_unimplemented"))
    ).lower()
    keyword_capability = {
        "heap": heap.get("supported") or heap.get("sink_field"),
        "uaf": False,
        "sprintf": _as_dict(capability.get("sprintf")).get("supported"),
        "loop": _as_dict(capability.get("loop")).get("any_target_analyzed"),
        "capacity": capacity.get("observed"),
    }
    gaps: list[dict[str, Any]] = []
    for keyword, supported in sorted(keyword_capability.items()):
        if not supported or keyword not in unimplemented:
            continue
        gaps.append(_gap(
            f"MM-claims-unimplemented::{keyword}", "matrix_claim_mismatch",
            f"claims.json lists '{keyword}' under explicitly_unimplemented but the "
            "audit measured a supporting capability; the claim is stale",
            [
                _source_line(CLAIMS_PATH, keyword),
                f"census:capability.{keyword}=True",
            ],
            "medium", "open",
            "update claims.json from the measured audit",
            "claims_docs", novel=True,
        ))
    # The committed capacity engine must not be described as unmerged work.
    stale_capacity = bool(capacity.get("module")) and any(
        token in claims_text for token in (
            "not merged", "unpushed", "not merged/pushed", "isolated of unpushed",
            "isolated unpushed",
        )
    ) and "capacity" in claims_text
    gaps.append(_gap(
        "MM-claims-capacity-stale", "matrix_claim_mismatch",
        (
            "claims.json no longer describes the capacity engine as unmerged/"
            "unpushed work"
            if not stale_capacity else
            "claims.json still describes the capacity repair as isolated/"
            "unmerged work while app/services/repair/capacity.py and its fixtures "
            "are part of the committed baseline"
        ),
        [
            _source_line(CLAIMS_PATH, "capacity"),
            f"module:app.services.repair.capacity "
            f"status={'ok' if capacity.get('module') else 'missing'}",
        ],
        "low" if not stale_capacity else "medium",
        "closed" if not stale_capacity else "open",
        "regenerate claims.json from the measured audit" if stale_capacity
        else "keep claims current",
        "claims_docs", novel=stale_capacity,
    ))
    capacity_documented = "capacity" in str(limitations.get("keyword_hits", {})).lower() \
        and int(_as_dict(limitations.get("keyword_hits")).get("capacity", 0)) > 0
    gaps.append(_gap(
        "MM-docs-capacity-missing", "matrix_claim_mismatch",
        (
            "LIMITATIONS.md mentions the capacity repair"
            if capacity_documented else
            "app/services/repair/capacity.py ships as a repair strategy but "
            "docs/acceptance/LIMITATIONS.md does not describe its scope or its "
            "native-PoC evidence requirement"
        ),
        [
            _source_line(LIMITATIONS_PATH, "capacity"),
            f"artifact:{MODULE_PATHS['capacity']}",
            f"census:limitations_keyword_hits={_as_dict(limitations.get('keyword_hits'))}",
        ],
        "low", "closed" if capacity_documented else "open",
        "keep the acceptance doc in sync" if capacity_documented
        else "document the capacity strategy, its profile and its PoC requirement",
        "claims_docs", novel=not capacity_documented,
    ))
    # Non-goals in the matrix: consistent -> non_goal, contradicted -> mismatch.
    non_goal_capability = {
        "heap": heap.get("supported") or heap.get("sink_field"),
        "sprintf": _as_dict(capability.get("sprintf")).get("supported"),
        "use-after-free": False,
        "loop": _as_dict(capability.get("loop")).get("any_target_analyzed"),
        "arm32": False,
        "riscv": False,
        "big-endian": False,
        "32-bit mach-o": False,
        "fat mach-o": False,
        "windows": False,
    }
    for index, text in enumerate(
            _as_list(_as_dict(ctx.get("matrix")).get("non_goals")), start=1):
        lowered = str(text).lower()
        contradicted = sorted(
            keyword for keyword, supported in non_goal_capability.items()
            if supported and keyword in lowered
        )
        if contradicted:
            gaps.append(_gap(
                f"MM-non-goal-{index}", "matrix_claim_mismatch",
                f"matrix non-goal {index} claims '{keyword_join(contradicted)}' is "
                "out of scope but the audit measured code support for it",
                [
                    f"census:matrix.non_goals[{index - 1}]=" + _truncate(text, 120),
                    f"census:capability={ {key: bool(value) for key, value in sorted(non_goal_capability.items()) if value} }",
                ],
                "medium", "open",
                "update the non-goal wording or remove support for the claim",
                "claims_docs", novel=True,
            ))
        else:
            gaps.append(_gap(
                f"NG-non-goal-{index}", "non_goal",
                "documented non-goal remains unsupported by the engine",
                [f"census:matrix.non_goals[{index - 1}]=" + _truncate(text, 120)],
                "info", "non_goal",
                "keep the documented non-goal honest",
                "claims_docs",
            ))
    return gaps


def keyword_join(items: list[str]) -> str:
    return ", ".join(items)


def _gap_runtime_vocabulary(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = _as_dict(ctx.get("matrix"))
    declared = set(_as_dict(matrix.get("runtime_tiers")))
    measured: dict[str, str] = {}
    for rel in (MODULE_PATHS["emulated"], MODULE_PATHS["macho_native"],
                MODULE_PATHS["poc_runner"], MODULE_PATHS["guest_runner"]):
        text = _read_text(rel)
        for match in re.finditer(r'tier\s*=\s*"([a-z_]+)"', text):
            measured.setdefault(match.group(1), rel)
    measured.pop("static_only", None)  # declared tier vocabulary
    undeclared = sorted(set(measured) - declared - {"native_run", "emulated_run"})
    rows = []
    for value in undeclared:
        rows.append(_gap(
            f"MM-runtime-tier-vocabulary::{value}", "matrix_claim_mismatch",
            f"runtime modules report tier '{value}' which is not declared in "
            "repair_matrix.RUNTIME_TIERS; tier vocabulary drifts between the "
            "evidence source and the declared matrix (Lead G19)",
            [
                f"module:{measured[value]} uses tier={value}",
                f"census:runtime_tiers={sorted(declared)}",
            ],
            "low", "open",
            "declare an 'unavailable' tier or map it to not_run in the report",
            "runtime_vocabulary", novel=True,
        ))
    if not rows:
        rows.append(_gap(
            "MM-runtime-tier-vocabulary::none", "matrix_claim_mismatch",
            "every runtime tier literal used by the runtime modules is declared "
            "in repair_matrix.RUNTIME_TIERS",
            ["census:runtime tier vocabulary consistent"],
            "info", "closed",
            "keep the vocabulary in sync",
            "runtime_vocabulary",
        ))
    return rows


def _gap_matrix_coverage(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = _as_dict(ctx.get("matrix"))
    fixtures = _as_list(ctx.get("fixtures"))
    probes = _as_dict(ctx.get("probes"))
    analysis_rows = _as_list(probes.get("analysis"))
    gaps: list[dict[str, Any]] = []
    cell_fixture_counts: dict[str, int] = {}
    for row in analysis_rows:
        cell = str(row.get("cell") or "")
        if cell:
            cell_fixture_counts[cell] = cell_fixture_counts.get(cell, 0) + 1
    for cell in _as_list(matrix.get("cells")):
        key = str(cell.get("key"))
        if cell_fixture_counts.get(key, 0) == 0:
            fixture_bytes = [
                row.get("path") for row in fixtures
                if str(row.get("cell") or "") == key
            ]
            gaps.append(_gap(
                f"MM-cell-no-fixture::{key}", "matrix_claim_mismatch",
                f"matrix cell {key} is declared but no shipped fixture exercises "
                "it in the audit census",
                [
                    f"census:cell={key}",
                    f"census:detected_fixtures={fixture_bytes}",
                ],
                "medium", "open",
                "add a fixture for the cell or drop the cell",
                "matrix_coverage",
            ))
    declared_sinks = _as_dict(matrix.get("sink_classes"))
    emitted = sorted({
        str(kind) for row in analysis_rows
        for kind in _as_list(_as_dict(row).get("kinds"))
    })
    for kind in sorted(declared_sinks):
        if kind in emitted or kind == "capacity_check_mismatch":
            continue
        gaps.append(_gap(
            f"MM-sink-class-unexercised::{kind}", "matrix_claim_mismatch",
            f"declared sink class {kind} is not emitted by any shipped fixture in "
            "the audit analysis census",
            [f"census:emitted_kinds={emitted}",
             f"census:declared_sink_classes={sorted(declared_sinks)}"],
            "low", "open",
            "add a fixture that exercises the class or mark it as untested",
            "matrix_coverage",
        ))
    # Strategy evidence: which declared cell strategies were measured?
    measured_strategies: dict[str, set[str]] = {}
    for row in _as_list(probes.get("fixtures")) + _as_list(probes.get("strategies")):
        if row.get("status") != "ok":
            continue
        cell = str(row.get("cell") or "")
        if cell:
            measured_strategies.setdefault(cell, set()).add(str(row.get("strategy", "")))
    for cell in _as_list(matrix.get("cells")):
        key = str(cell.get("key"))
        for strategy in _as_list(cell.get("strategies")):
            if str(strategy) in measured_strategies.get(key, set()):
                continue
            gaps.append(_gap(
                f"MM-strategy-unexercised::{key}::{strategy}",
                "matrix_claim_mismatch",
                f"cell {key} declares strategy {strategy} but no audit probe of "
                "that cell delivered it",
                [
                    f"census:measured_strategies[{key}]="
                    f"{sorted(measured_strategies.get(key, set()))}",
                    f"probe:strategy:{key}:{strategy}",
                ],
                "low", "open",
                "add fixture evidence for the declared strategy",
                "matrix_coverage",
            ))
    return gaps


def _gap_ai_paths(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    gates = _as_dict(_as_dict(ctx.get("gates")).get("ai"))
    docs = _as_dict(ctx.get("docs"))
    claims = _as_dict(ctx.get("claims"))
    leaf_documented = (
        "leaf" in str(_as_dict(docs.get("limitations")).get("keyword_hits", {})).lower()
        and int(_as_dict(_as_dict(docs.get("limitations")).get("keyword_hits")).get("leaf", 0)) > 0
    ) or "leaf-only" in str(claims.get("text_lower", ""))
    rows = []
    for name in sorted(gates):
        entry = _as_dict(gates[name])
        if entry.get("status") != "ok":
            continue
        if entry.get("routes_through_finish_candidate") and entry.get("leaf_only_mentions"):
            if leaf_documented:
                rows.append(_gap(
                    f"NG-ai-leaf-only::{name}", "non_goal",
                    f"{name} accepts only a leaf/whitelist machine-code block (no "
                    "calls); the limitation is documented, so it is an honest "
                    "non-goal rather than an undeclared capability gap",
                    [
                        f"module:app.services.{name} "
                        f"whitelist={entry.get('whitelist_constants')}",
                        _source_line(LIMITATIONS_PATH, "leaf-only"),
                    ],
                    "info", "non_goal",
                    "keep the leaf-only limitation documented",
                    "ai_paths",
                ))
            else:
                rows.append(_gap(
                    f"MM-ai-leaf-only::{name}", "matrix_claim_mismatch",
                    f"{name} only accepts a leaf/whitelist machine-code block but "
                    "the leaf-only restriction is not documented in the acceptance "
                    "docs or claims",
                    [f"module:app.services.{name}",
                     _source_line(CLAIMS_PATH, "AI")],
                    "low", "open",
                    "document the leaf-only limitation",
                    "ai_paths", novel=True,
                ))
    if not rows:
        rows.append(_gap(
            "NG-ai-leaf-only::none", "non_goal",
            "no AI path in this build carries a leaf-only machine-code whitelist; "
            "nothing to report",
            ["census:ai_paths leaf-only not measured"],
            "info", "non_goal",
            "re-check after AI-path changes",
            "ai_paths",
        ))
    return rows


def _gap_manifests(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    manifests = _as_list(ctx.get("poc_manifests"))
    unrunnable = [row for row in manifests if not row.get("runner_available")]
    no_input_empty = [
        row for row in manifests
        if row.get("regression_cases") == 0 and not row.get("no_input_field")
    ]
    evidence = [
        f"artifact:{row.get('path')} format={row.get('format')}/"
        f"{row.get('arch')} runner={'yes' if row.get('runner_available') else 'no'}"
        for row in manifests
    ]
    gaps = [_gap(
        "RG-poc-manifests-unrunnable", "runtime_gap",
        (
            "every shipped PoC manifest has a measurable runner"
            if not unrunnable else
            f"{len(unrunnable)} of {len(manifests)} shipped PoC manifests have no "
            "measurable runner on this host; their fixtures cannot be accepted "
            "through the external-PoC evidence model"
        ),
        evidence or ["census:no PoC manifests"],
        "info" if not unrunnable else "medium",
        "closed" if not unrunnable else "open",
        "wire the declared guest runner or document host requirements",
        "manifests",
    ), _gap(
        "GM-manifest-no-input-model", "gate_mismatch",
        (
            "every empty-regression PoC manifest declares the no-input model"
            if not no_input_empty else
            f"{len(no_input_empty)} PoC manifest(s) have an empty regression list "
            "without a no_input declaration; if they are used as acceptance "
            "evidence the gate has no way to represent the no-input model"
        ),
        [
            f"artifact:{row.get('path')} regression_cases=0 no_input_field=False"
            for row in no_input_empty[:8]
        ] or ["census:no empty-regression manifest"],
        "info" if not no_input_empty else "medium",
        "closed" if not no_input_empty else "open",
        "declare no_input:true for legitimate no-input manifests",
        "manifests", novel=not no_input_empty,
    )]
    return gaps


def _gap_module_readiness(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    modules = _as_dict(ctx.get("modules"))
    not_ready = sorted(
        name for name, entry in modules.items()
        if _as_dict(entry).get("status") != "ok"
    )
    return [_gap(
        "GM-module-readiness", "gate_mismatch",
        (
            "all audited product modules imported cleanly"
            if not not_ready else
            "the audit could not import module(s) that the census needs: "
            f"{not_ready}; their census entries are recorded as module_not_ready "
            "(mid-flight state is tolerated, but the audit evidence for them is "
            "incomplete)"
        ),
        [
            f"module:{name}: "
            f"{_as_dict(modules.get(name)).get('error') or 'ok'}"
            for name in not_ready[:10]
        ] or ["census:all audit modules imported"],
        "info" if not not_ready else "high",
        "closed" if not not_ready else "open",
        "re-run after the affected modules settle",
        "module_readiness",
    )]


# ---------------------------------------------------------------------------
# coverage rows
# ---------------------------------------------------------------------------

def _gate_check_rows(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    unified = _as_dict(_as_dict(ctx.get("gates")).get("unified"))
    scenarios = _as_dict(unified.get("scenarios"))
    matrix = _as_dict(ctx.get("matrix"))
    profile_required: dict[str, list[str]] = {}
    for name, meta in _as_dict(matrix.get("evidence_profiles")).items():
        for check_id in _as_list(_as_dict(meta).get("required_checks")):
            profile_required.setdefault(str(check_id), []).append(str(name))
    for check_id in sorted({str(item) for item in _as_list(unified.get("check_ids"))}):
        statuses: dict[str, int] = {}
        for scenario in scenarios.values():
            status = _check_status(_as_dict(scenario), check_id)
            if status != "absent":
                statuses[status] = statuses.get(status, 0) + 1
        rows.append({
            "gate": "unified",
            "check_id": check_id,
            "observed_in_scenarios": statuses,
            "required_by_profiles": sorted(profile_required.get(check_id, [])),
            "profile_or_patch_check": check_id.startswith(("profile.", "patch.")),
        })
    legacy = _as_dict(_as_dict(ctx.get("gates")).get("legacy"))
    legacy_required: dict[str, list[str]] = {}
    for name, meta in _as_dict(matrix.get("evidence_profiles")).items():
        for check_id in _as_list(_as_dict(meta).get("legacy_required_checks")):
            legacy_required.setdefault(str(check_id), []).append(str(name))
    for check_id in sorted({str(item) for item in _as_list(legacy.get("check_ids"))}):
        statuses: dict[str, int] = {}
        for scenario in _as_dict(legacy.get("scenarios")).values():
            status = _check_status(_as_dict(scenario), check_id)
            if status != "absent":
                statuses[status] = statuses.get(status, 0) + 1
        rows.append({
            "gate": "legacy",
            "check_id": check_id,
            "observed_in_scenarios": statuses,
            "required_by_profiles": sorted(legacy_required.get(check_id, [])),
            "profile_or_patch_check": check_id.startswith(("profile.", "patch.")),
        })
    rows.sort(key=lambda item: (item["gate"], item["check_id"]))
    return rows


def _coverage_rows(ctx: dict[str, Any]) -> dict[str, Any]:
    matrix = _as_dict(ctx.get("matrix"))
    probes = _as_dict(ctx.get("probes"))
    fixtures = _as_list(ctx.get("fixtures"))
    analysis_rows = _as_list(probes.get("analysis"))
    fixture_probes = _as_list(probes.get("fixtures"))
    analysis_by_path = {str(row.get("path")): row for row in analysis_rows
                        if row.get("status") == "ok"}
    probe_by_path = {str(row.get("path")): row for row in fixture_probes
                     if row.get("status") == "ok"}
    cells = []
    runtime_sources = _as_list(_as_dict(ctx.get("runtime")).get("sources"))
    for cell in _as_list(matrix.get("cells")):
        key = str(cell.get("key"))
        cell_probes = [row for row in fixture_probes
                       if str(row.get("cell")) == key]
        cell_analyses = [row for row in analysis_rows
                         if str(row.get("cell")) == key]
        measured_sinks = sorted({kind for row in cell_analyses
                                 for kind in _as_list(_as_dict(row).get("kinds"))})
        measured_strategies = sorted({str(row.get("strategy")) for row in cell_probes})
        profiles = sorted({str(row.get("profile")) for row in cell_probes
                           if row.get("profile")})
        cells.append({
            "cell": key,
            "container": cell.get("container"),
            "arch": cell.get("arch"),
            "bits": cell.get("bits"),
            "endian": cell.get("endian"),
            "declared_strategies": _as_list(cell.get("strategies")),
            "declared_sink_classes": _as_list(cell.get("sink_classes")),
            "declared_runtime_tiers": _as_list(cell.get("runtime_tiers")),
            "fixture_count": len([row for row in fixtures if row.get("cell") == key]),
            "fixtures": sorted(str(row.get("path")) for row in fixtures
                               if row.get("cell") == key),
            "measured_sink_classes": measured_sinks,
            "measured_strategies": measured_strategies,
            "measured_profiles": profiles,
            "probe_ids": sorted(str(row.get("probe_id")) for row in cell_probes),
        })
    sink_rows = []
    emitted = sorted({kind for row in analysis_rows
                      for kind in _as_list(_as_dict(row).get("kinds"))})
    for name, meta in _as_dict(matrix.get("sink_classes")).items():
        emitters = [path for path in ("app/services/repair/analyzer.py",
                                      "app/services/repair/analyzer_i386.py",
                                      "app/services/repair/capacity.py")
                    if f'"{name}"' in _read_text(path) or f"'{name}'" in _read_text(path)]
        sink_rows.append({
            "sink_class": name,
            "strategy": _as_dict(meta).get("strategy"),
            "declared_in_cells": sorted(
                str(cell.get("key")) for cell in _as_list(matrix.get("cells"))
                if name in _as_list(cell.get("sink_classes"))
            ),
            "analyzer_emission_markers": emitters,
            "emitted_by_audit_fixtures": name in emitted,
            "fixtures_emitting": sorted(
                str(row.get("path")) for row in analysis_rows
                if name in _as_list(_as_dict(row).get("kinds"))
            ),
        })
    strategy_rows = []
    for cell in _as_list(matrix.get("cells")):
        key = str(cell.get("key"))
        delivered = {str(row.get("strategy")) for row in fixture_probes
                     if str(row.get("cell")) == key}
        requested_rows = [row for row in _as_list(probes.get("strategies"))
                          if str(row.get("cell")) == key]
        for strategy in _as_list(cell.get("strategies")):
            strategy_rows.append({
                "cell": key,
                "strategy": str(strategy),
                "declared": True,
                "delivered_by_default_probe": str(strategy) in delivered,
                "requested_in_probe": any(
                    str(row.get("requested_strategy")) == str(strategy)
                    for row in requested_rows
                ),
                "request_probe_ids": sorted(
                    str(row.get("probe_id")) for row in requested_rows
                    if str(row.get("requested_strategy")) == str(strategy)
                ),
            })
    gate_profiles = []
    profiles = _as_dict(matrix.get("evidence_profiles"))
    if profiles:
        for name, meta in sorted(profiles.items()):
            profile_checks = [str(item) for item in _as_list(meta.get("required_checks"))]
            legacy_checks = [str(item) for item in _as_list(meta.get("legacy_required_checks"))]
            unified_ids = {str(item) for item in _as_list(
                _as_dict(_as_dict(ctx.get("gates")).get("unified")).get("check_ids"))}
            legacy_ids = {str(item) for item in _as_list(
                _as_dict(_as_dict(ctx.get("gates")).get("legacy")).get("check_ids"))}
            gate_profiles.append({
                "profile": name,
                "declared": True,
                "description": meta.get("description"),
                "evidence_sources": _as_list(meta.get("evidence_sources")),
                "required_checks": profile_checks,
                "legacy_required_checks": legacy_checks,
                "strategies": sorted(
                    key for key, value in _as_dict(matrix.get("strategy_profiles")).items()
                    if str(value) == name
                ),
                "unified_required_checks_missing": sorted(
                    item for item in profile_checks if item not in unified_ids
                ),
                "legacy_required_checks_missing": sorted(
                    item for item in legacy_checks if item not in legacy_ids
                ),
            })
    else:
        gate_profiles.append({
            "profile": "(implicit)",
            "declared": False,
            "description": "no EVIDENCE_PROFILES registry in repair_matrix; one "
                           "implicit acceptance model",
            "evidence_sources": [],
            "required_checks": [],
            "legacy_required_checks": [],
            "strategies": [],
            "unified_required_checks_missing": [],
            "legacy_required_checks_missing": [],
        })
    evidence_rows = []
    for source in runtime_sources:
        item = _as_dict(source)
        evidence_rows.append({
            "format": item.get("format"),
            "arch": item.get("arch"),
            "evidence_source": item.get("source"),
            "runtime_tier": item.get("runtime_tier"),
            "available": bool(item.get("available")),
            "runner": item.get("runner", ""),
            "detail": item.get("detail", ""),
            "cells": sorted(
                str(cell.get("key")) for cell in _as_list(matrix.get("cells"))
                if cell.get("container") == item.get("format")
                and cell.get("arch") == item.get("arch")
            ),
        })
    evidence_rows.sort(key=lambda item: (item["format"], item["arch"],
                                         item["evidence_source"]))
    return {
        "cells": cells,
        "sink_classes": sorted(sink_rows, key=lambda item: item["sink_class"]),
        "strategies": sorted(strategy_rows, key=lambda item: (item["cell"],
                                                              item["strategy"])),
        "gate_profiles": sorted(gate_profiles, key=lambda item: item["profile"]),
        "evidence_sources": evidence_rows,
        "gate_checks": _gate_check_rows(ctx),
        "cases": _as_list(ctx.get("cases")),
    }


# ---------------------------------------------------------------------------
# audit assembly
# ---------------------------------------------------------------------------

DETECTORS: tuple[tuple[str, Callable[[dict[str, Any]], list[dict[str, Any]]]], ...] = (
    ("engine_capacity", _gap_engine_capacity),
    ("engine_heap", _gap_engine_heap),
    ("engine_sink_classes", _gap_sink_classes),
    ("engine_strategy_request", _gap_strategy_request),
    ("engine_target_scope", _gap_target_scope),
    ("oracle_destinations", _gap_heap_oracle),
    ("gate_profiles", _gap_gate_profiles),
    ("gate_cell", _gap_gate_cell_tier),
    ("gate_rewrite", _gap_gate_rewrite),
    ("gate_no_input", _gap_gate_no_input),
    ("gate_poc_unavailable", _gap_gate_poc_unavailable),
    ("gate_legacy", _gap_gate_legacy),
    ("gate_scenario_execution", _gap_gate_scenarios),
    ("runtime_sources", _gap_runtime_sources),
    ("oracle_wrong_function", _gap_oracle_wrong_function),
    ("cases", _gap_cases),
    ("claims_docs", _gap_claims_docs),
    ("runtime_vocabulary", _gap_runtime_vocabulary),
    ("matrix_coverage", _gap_matrix_coverage),
    ("ai_paths", _gap_ai_paths),
    ("manifests", _gap_manifests),
    ("module_readiness", _gap_module_readiness),
)


def _module_statuses() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    for name in ("repair_matrix", "binary_pipeline", "unified_verification",
                 "binary_verification", "analyzer", "analyzer_i386", "writer",
                 "emulated", "macho_native", "poc_runner", "guest_runner",
                 "capacity", "ai_binary_repair", "ai_assembly_repair",
                 "ai_patch_validation", "containers", "runtime_evidence"):
        module, error = _load_module(f"app.services.{name}"
                                     if name != "runtime_evidence"
                                     else "app.services.runtime.evidence")
        statuses[name] = {
            "status": "ok" if module is not None else "module_not_ready",
            "error": error,
            "source": MODULE_PATHS.get(name, f"app/services/{name}.py"),
        }
    return dict(sorted(statuses.items()))


def _summarize(gaps: list[dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any]:
    counts_by_status: dict[str, int] = {status: 0 for status in GAP_STATUSES}
    counts_by_category: dict[str, int] = {name: 0 for name in GAP_CATEGORIES}
    counts_by_severity: dict[str, int] = {name: 0 for name in GAP_SEVERITIES}
    for gap in gaps:
        counts_by_status[gap["status"]] = counts_by_status.get(gap["status"], 0) + 1
        counts_by_category[gap["category"]] = counts_by_category.get(gap["category"], 0) + 1
        counts_by_severity[gap["severity"]] = counts_by_severity.get(gap["severity"], 0) + 1
    probes = _as_dict(ctx.get("probes"))
    return {
        "gap_count": len(gaps),
        "open_count": counts_by_status.get("open", 0),
        "mitigated_count": counts_by_status.get("mitigated", 0),
        "closed_count": counts_by_status.get("closed", 0),
        "non_goal_count": counts_by_status.get("non_goal", 0),
        "high_severity_open": sum(
            1 for gap in gaps
            if gap["status"] == "open" and gap["severity"] == "high"
        ),
        "by_status": dict(sorted(counts_by_status.items())),
        "by_category": dict(sorted(counts_by_category.items())),
        "by_severity": dict(sorted(counts_by_severity.items())),
        "open_gap_ids": sorted(gap["gap_id"] for gap in gaps
                               if gap["status"] == "open"),
        "mitigated_gap_ids": sorted(gap["gap_id"] for gap in gaps
                                    if gap["status"] == "mitigated"),
        "closed_gap_ids": sorted(gap["gap_id"] for gap in gaps
                                 if gap["status"] == "closed"),
        "probes": {
            "fixtures": len(_as_list(probes.get("fixtures"))),
            "analysis": len(_as_list(probes.get("analysis"))),
            "strategies": len(_as_list(probes.get("strategies"))),
            "capacity": len(_as_list(probes.get("capacity"))),
            "skipped_budget": int(probes.get("skipped_budget", 0) or 0),
        },
    }


def build_audit(*, include_probes: bool = True,
                include_legacy_artifact: bool = True,
                max_fixture_probes: int | None = None,
                budget_seconds: float = DEFAULT_BUDGET_SECONDS,
                include_strategy_probes: bool = True) -> dict[str, Any]:
    """Run the audit and return the deterministic coverage/gap document."""
    ctx: dict[str, Any] = {
        "_started": time.monotonic(),
        "_budget_seconds": float(budget_seconds),
        "_max_fixture_probes": max_fixture_probes,
        "_include_strategy_probes": bool(include_strategy_probes),
        "_data_cache": {},
    }
    ctx["modules"] = _module_statuses()
    ctx["matrix"] = _census_matrix()
    ctx["gates"] = {
        "unified": _census_unified_gate(ctx["matrix"]),
        "legacy": _census_legacy_gate(),
        "ai": _census_ai_paths(),
    }
    ctx["runtime"] = _census_runtime(ctx["matrix"])
    ctx["fixtures"] = _census_fixtures(ctx, include_legacy_artifact)
    ctx["cases"] = _census_cases(ctx)
    ctx["poc_manifests"] = _census_poc_manifests(ctx)
    ctx["claims"] = _census_claims(ctx)
    ctx["docs"] = _census_docs(ctx)
    ctx["benchmarks"] = _census_benchmarks(ctx)
    ctx["probes"] = {"fixtures": [], "analysis": [], "strategies": [],
                     "capacity": [], "skipped_budget": 0}
    if include_probes:
        _run_probes(ctx)
        _apply_probe_results(ctx)
    else:
        _apply_probe_results(ctx)
    ctx["capability"] = _measure_capability(ctx)
    gaps: list[dict[str, Any]] = []
    for _name, detector in DETECTORS:
        try:
            gaps.extend(detector(ctx))
        except Exception as exc:  # noqa: BLE001 - a detector must not kill the audit
            gaps.append(_gap(
                f"GM-detector-error::{_name}", "gate_mismatch",
                f"gap detector {_name} raised; its findings are missing from this "
                "run",
                [f"detector:{_name} error={type(exc).__name__}: {_truncate(exc)}"],
                "medium", "open",
                "fix the detector against the current module API",
                _name,
            ))
    gaps = _merge_gaps(gaps)
    coverage_rows = _coverage_rows(ctx)
    environment = {
        "platform": sys.platform,
        "machine": platform.machine(),
        "arch": _host_arch(),
        "python": platform.python_version(),
        "root": ".",
    }
    probes = _as_dict(ctx.get("probes"))
    rows_over_size = [
        row.get("path") for row in _as_list(ctx.get("fixtures"))
        if row.get("skipped_over_size")
    ]
    bounds = {
        "max_fixture_bytes": MAX_FIXTURE_BYTES,
        "budget_seconds": float(budget_seconds),
        "mode": "full" if include_probes else "static",
        "fixtures_total": len(_as_list(ctx.get("fixtures"))),
        "fixtures_probed": len([
            row for row in _as_list(probes.get("fixtures"))
            if row.get("status") == "ok"
        ]),
        "probes_skipped_budget": int(probes.get("skipped_budget", 0) or 0),
        "fixtures_skipped_over_size": rows_over_size,
        "network_access": False,
        "host_elf_execution": False,
        "notes": [
            "verify=True probes reuse the product's own acceptance runtimes "
            "(Unicorn emulation, native Mach-O runner); the audit adds no PoC "
            "execution and runs no host-native Linux ELF.",
            "budget is a safety guard: normally every fixture is probed; a "
            "budget-exhausted run marks the remaining probes skipped_budget.",
        ],
    }
    audit: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "audit_date": AUDIT_DATE,
        "generated_by": "app/services/coverage_audit.py",
        "mode": bounds["mode"],
        "environment": environment,
        "bounds": bounds,
        "census": {
            "matrix": ctx["matrix"],
            "gates": ctx["gates"],
            "runtime_sources": {
                "host": _as_dict(ctx["runtime"]).get("host"),
                "emulated": _as_dict(ctx["runtime"]).get("emulated"),
                "macho_native": _as_dict(ctx["runtime"]).get("macho_native"),
                "sources": _as_list(_as_dict(ctx["runtime"]).get("sources")),
            },
            "fixtures": ctx["fixtures"],
            "cases": ctx["cases"],
            "poc_manifests": ctx["poc_manifests"],
            "claims": ctx["claims"],
            "docs": ctx["docs"],
            "benchmarks": ctx["benchmarks"],
            "modules": ctx["modules"],
            "capability": ctx["capability"],
        },
        "coverage_rows": coverage_rows,
        "probes": {
            "fixtures": probes.get("fixtures", []),
            "analysis": probes.get("analysis", []),
            "strategies": probes.get("strategies", []),
            "capacity": probes.get("capacity", []),
        },
        "gaps": gaps,
        "summary": _summarize(gaps, ctx),
    }
    return audit


# ---------------------------------------------------------------------------
# render + write
# ---------------------------------------------------------------------------

def _md_escape(text: Any) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def _gap_table(gaps: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| gap_id | category | severity | status | symptom | evidence | next_step |",
        "|---|---|---|---|---|---|---|",
    ]
    for gap in gaps:
        evidence = "; ".join(gap["evidence"][:4])
        lines.append(
            "| `{gap_id}` | {category} | {severity} | {status} | {symptom} | "
            "{evidence} | {next_step} |".format(
                gap_id=_md_escape(gap["gap_id"]),
                category=_md_escape(gap["category"]),
                severity=_md_escape(gap["severity"]),
                status=_md_escape(gap["status"]),
                symptom=_md_escape(gap["symptom"]),
                evidence=_md_escape(_truncate(evidence, 420)),
                next_step=_md_escape(gap["next_step"]),
            )
        )
    return lines


def render_gap_report(audit: dict[str, Any]) -> str:
    """Render the human-readable markdown report for one audit document."""
    summary = _as_dict(audit.get("summary"))
    gaps = _as_list(audit.get("gaps"))
    environment = _as_dict(audit.get("environment"))
    bounds = _as_dict(audit.get("bounds"))
    rows = _as_dict(audit.get("coverage_rows"))
    census = _as_dict(audit.get("census"))
    open_gaps = [gap for gap in gaps if gap["status"] in {"open", "mitigated"}]
    settled = [gap for gap in gaps if gap["status"] in {"closed", "non_goal"}]
    lines = [
        "# Capability-gap audit (2026-11-14)",
        "",
        "Generated by `app/services/coverage_audit.py` (`"
        f"{audit.get('generated_by', '')}`); mode="
        f"`{audit.get('mode', '')}`. Every status below is re-derived by importing "
        "the real product modules and probing the real pipeline; nothing is a "
        "hard-coded gap list.",
        "",
        "## Summary",
        "",
        f"- gaps measured: **{summary.get('gap_count', 0)}** "
        f"(open {summary.get('open_count', 0)}, mitigated "
        f"{summary.get('mitigated_count', 0)}, closed "
        f"{summary.get('closed_count', 0)}, non_goal "
        f"{summary.get('non_goal_count', 0)})",
        f"- high-severity open gaps: **{summary.get('high_severity_open', 0)}**",
        f"- coverage rows: {len(_as_list(rows.get('cells')))} cells, "
        f"{len(_as_list(rows.get('sink_classes')))} sink classes, "
        f"{len(_as_list(rows.get('strategies')))} strategy entries, "
        f"{len(_as_list(rows.get('gate_profiles')))} gate profiles, "
        f"{len(_as_list(rows.get('evidence_sources')))} evidence sources, "
        f"{len(_as_list(rows.get('gate_checks')))} gate checks",
        "",
        "| status | count |",
        "|---|---|",
    ]
    for status in GAP_STATUSES:
        lines.append(f"| {status} | {_as_dict(summary.get('by_status')).get(status, 0)} |")
    lines.extend([
        "",
        "| category | count |",
        "|---|---|",
    ])
    for category in GAP_CATEGORIES:
        lines.append(
            f"| {category} | {_as_dict(summary.get('by_category')).get(category, 0)} |"
        )
    lines.extend(["", "## Open gaps (actionable)", ""])
    if open_gaps:
        lines.extend(_gap_table(open_gaps))
    else:
        lines.append("No open gaps were measured in this run.")
    lines.extend(["", "## Closed and non-goal records", ""])
    if settled:
        lines.extend(_gap_table(settled))
    else:
        lines.append("No closed or non-goal gap records in this run.")
    lines.extend(["", "## Coverage census (measured)", ""])
    cells = _as_list(rows.get("cells"))
    if cells:
        lines.extend([
            "| cell | declared strategies | measured sink classes | measured "
            "strategies | fixtures | declared runtime tiers |",
            "|---|---|---|---|---|---|",
        ])
        for cell in cells:
            lines.append("| {cell} | {strategies} | {sinks} | {measured} | "
                         "{fixtures} | {tiers} |".format(
                             cell=_md_escape(cell.get("cell")),
                             strategies=_md_escape(", ".join(
                                 str(item) for item in _as_list(
                                     cell.get("declared_strategies")))),
                             sinks=_md_escape(", ".join(
                                 str(item) for item in _as_list(
                                     cell.get("measured_sink_classes"))) or "-"),
                             measured=_md_escape(", ".join(
                                 str(item) for item in _as_list(
                                     cell.get("measured_strategies"))) or "-"),
                             fixtures=cell.get("fixture_count"),
                             tiers=_md_escape(", ".join(
                                 str(item) for item in _as_list(
                                     cell.get("declared_runtime_tiers")))),
                         ))
    sink_rows = _as_list(rows.get("sink_classes"))
    if sink_rows:
        lines.extend(["", "| sink class | strategy | emitted by audit fixtures | "
                          "fixtures | cells |", "|---|---|---|---|---|"])
        for row in sink_rows:
            lines.append("| {name} | {strategy} | {emitted} | {count} | {cells} |".format(
                name=_md_escape(row.get("sink_class")),
                strategy=_md_escape(row.get("strategy")),
                emitted="yes" if row.get("emitted_by_audit_fixtures") else "no",
                count=len(_as_list(row.get("fixtures_emitting"))),
                cells=_md_escape(", ".join(
                    str(item) for item in _as_list(row.get("declared_in_cells")))),
            ))
    evidence_rows = _as_list(rows.get("evidence_sources"))
    if evidence_rows:
        lines.extend(["", "| format/arch | evidence source | tier | available | "
                          "runner | cells |", "|---|---|---|---|---|---|"])
        for row in evidence_rows:
            lines.append("| {pair} | {source} | {tier} | {ok} | {runner} | {cells} |".format(
                pair=f"{row.get('format')}/{row.get('arch')}",
                source=_md_escape(row.get("evidence_source")),
                tier=_md_escape(row.get("runtime_tier")),
                ok="yes" if row.get("available") else "no",
                runner=_md_escape(row.get("runner") or "-"),
                cells=_md_escape(", ".join(
                    str(item) for item in _as_list(row.get("cells")))),
            ))
    lines.extend(["", "## Self-reflection: what the audit found that prose missed", ""])
    reflections = [gap for gap in gaps if gap.get("novel")]
    if not reflections:
        lines.append(
            "No audit-only finding was measured in this run: every measured gap "
            "row maps to a known inventory entry."
        )
    else:
        for gap in reflections:
            measured = "OPEN" if gap["status"] == "open" else gap["status"].upper()
            lines.append(
                f"- **{gap['gap_id']}** ({measured}, {gap['category']}): "
                f"{gap['symptom']} Evidence: "
                f"{'; '.join(gap['evidence'][:3]) or 'none recorded'}."
            )
    lines.extend([
        "",
        "## Method and bounds",
        "",
        f"- environment: {environment.get('platform')}/"
        f"{environment.get('machine')} python {environment.get('python')}",
        f"- fixtures: {bounds.get('fixtures_total')} found, "
        f"{bounds.get('fixtures_probed')} probed with `repair_any(verify=True)`, "
        f"{bounds.get('probes_skipped_budget')} skipped by the wall-clock budget, "
        f"{len(_as_list(bounds.get('fixtures_skipped_over_size')))} skipped over "
        f"{bounds.get('max_fixture_bytes')} bytes",
        f"- budget: {bounds.get('budget_seconds')}s; network access: "
        f"{bounds.get('network_access')}; host Linux-ELF execution: "
        f"{bounds.get('host_elf_execution')}",
        "- the census imports the real `repair_matrix`, gate builders, runtime "
        "modules, fixtures, PoC manifests, claims and acceptance docs; the "
        "dynamic probes call the real `repair_any`, `analyze`, gate builders and "
        "runner-selection helpers",
        "- a mid-flight module is recorded as `module_not_ready`; it never "
        "crashes the audit and is reported as an open evidence gap",
        "- statuses are measured: re-running after an integration flips the "
        "affected rows between open / mitigated / closed instead of keeping a "
        "stale list",
        "",
        "## Reproduction",
        "",
        "```",
        ".venv/bin/python scripts/audit_capability_coverage.py",
        ".venv/bin/python -m pytest tests/test_capability_audit.py -q",
        "```",
        "",
    ])
    return "\n".join(lines) + "\n"


def write_artifacts(audit: dict[str, Any],
                    output_dir: str | Path | None = None) -> dict[str, Any]:
    """Write coverage-matrix.json, gap-report.md and SHA256SUMS deterministically."""
    directory = Path(output_dir) if output_dir is not None else ROOT / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    matrix_path = directory / "coverage-matrix.json"
    report_path = directory / "gap-report.md"
    sums_path = directory / "SHA256SUMS"
    matrix_text = json.dumps(audit, indent=2, sort_keys=True,
                             ensure_ascii=False) + "\n"
    report_text = render_gap_report(audit)
    matrix_path.write_text(matrix_text, encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    matrix_sha = _sha_bytes(matrix_text.encode("utf-8"))
    report_sha = _sha_bytes(report_text.encode("utf-8"))
    sums_text = (
        f"{matrix_sha}  coverage-matrix.json\n"
        f"{report_sha}  gap-report.md\n"
    )
    sums_path.write_text(sums_text, encoding="utf-8")
    return {
        "directory": directory,
        "files": {
            "coverage-matrix.json": str(matrix_path),
            "gap-report.md": str(report_path),
            "SHA256SUMS": str(sums_path),
        },
        "sha256": {
            "coverage-matrix.json": matrix_sha,
            "gap-report.md": report_sha,
            "SHA256SUMS": _sha_bytes(sums_text.encode("utf-8")),
        },
    }


def known_gap_ids() -> tuple[str, ...]:
    """Stable gap ids whose detectors always emit a row (for tests/reviewers)."""
    return (
        "EG-capacity-strategy",
        "EG-heap-destination",
        "OG-heap-destination-oracle",
        "OG-wrong-function-candidate",
        "GM-gate-no-input",
        "GM-profile-registry",
        "GM-gate-cell",
        "GM-gate-runtime-tier",
        "GM-gate-rewrite",
        "GM-gate-poc-unavailable",
        "GM-legacy-gate-profile",
        "GM-legacy-gate-poc-manifest",
        "EG-sink-class-dead-immediate_length",
        "RG-poc-manifests-unrunnable",
    )


__all__ = [
    "AUDIT_DATE",
    "ARTIFACT_DIR",
    "GAP_CATEGORIES",
    "GAP_SEVERITIES",
    "GAP_STATUSES",
    "SCHEMA_VERSION",
    "build_audit",
    "known_gap_ids",
    "render_gap_report",
    "write_artifacts",
]
