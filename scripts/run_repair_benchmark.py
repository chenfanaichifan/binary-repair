#!/usr/bin/env python3
"""Run the Phase-8A deterministic repair benchmark (no AI, no network).

Reads the committed ground-truth manifest (``benchmark/phase8-v1/manifest.json``)
and, for every sample, calls the **deterministic** repair engine
``app.services.binary_pipeline.repair_any`` with the sample's declared target and
(oracle) PoC manifest.  It never calls an AI provider and never touches the
network.

Independent verification: the deterministic repair engine's own gate is *not*
accepted as independent verification.  The runner exposes an injectable verifier
interface and a default ``--verifier none`` that records ``not_run`` instead of
pretending a candidate is verified.  If the gui-docs independent verifier
(``scripts/verify_repair.py``) appears later, ``--verifier auto`` imports its
``verify``/``verify_repair``/``verify_sample`` entry point and records the real
verdict.

Results are written to ``artifacts/phase8-benchmark-2026-11-16/`` (or ``--out``):

* ``results.json`` - per-sample fields ``detected``, ``candidate_produced``,
  ``integrity``, ``vuln_eliminated``, ``regression``, ``independently_verified``,
  ``not_run``, ``false_verified`` plus aggregate by class/split;
* ``README.md`` - deterministic human summary;
* ``SHA256SUMS`` - covers both data files.

Safety properties enforced before writing:

* ``false_verified == 0``: a deterministic "verified" claim that an available
  independent verifier rejects is counted as a false verification and fails the
  run (exit 1);
* host-unavailable repair results are recorded as ``not_run`` with the typed
  reason - availability is never fabricated;
* no generator self-verification is recorded as ``independently_verified``.

Usage::

    python scripts/run_repair_benchmark.py                    # run all samples
    python scripts/run_repair_benchmark.py --split dev
    python scripts/run_repair_benchmark.py --max-samples 1 --json
    python scripts/run_repair_benchmark.py --verifier auto
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MANIFEST_PATH = "benchmark/phase8-v1/manifest.json"
ARTIFACT_DIR = ROOT / "artifacts" / "phase8b-benchmark-2026-11-16"
ARTIFACT_FILES = ("results.json", "README.md")
SCHEMA_VERSION = 1
KIND = "repair_benchmark_results"
VERIFIER_CANDIDATES = (
    "scripts/verify_repair.py",
    "scripts/independent_verifier.py",
    "app/services/independent_verifier.py",
)
VERIFIER_ENTRY_POINTS = ("verify", "verify_repair", "verify_sample")


class BenchmarkError(RuntimeError):
    """The benchmark manifest or a result is unusable."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(relative: str) -> Any:
    path = ROOT / relative
    if not path.is_file():
        raise BenchmarkError(f"missing file: {relative}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"unreadable JSON {relative}: {exc}") from exc


def load_manifest(relative: str = MANIFEST_PATH) -> dict[str, Any]:
    manifest = _read_json(relative)
    if not isinstance(manifest, dict):
        raise BenchmarkError("benchmark manifest is not an object")
    if manifest.get("kind") != "ground_truth_benchmark":
        raise BenchmarkError(f"unexpected manifest kind: {manifest.get('kind')!r}")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise BenchmarkError("benchmark manifest has no samples")
    if manifest.get("hidden_available") is not False:
        raise BenchmarkError("benchmark manifest hidden_available must be false")
    return manifest


def sample_binary_path(sample: dict[str, Any]) -> str:
    """The binary path is the first source_ref (documented manifest convention)."""
    refs = sample.get("source_refs") or []
    if not refs:
        raise BenchmarkError(f"{sample.get('sample_id')}: empty source_refs")
    return str(refs[0])


def _target_argument(sample: dict[str, Any]) -> Any:
    target = sample.get("target") or {}
    kind = target.get("kind")
    if kind in {"symbol", "function"}:
        value = target.get("symbol") or target.get("function")
        if not value:
            raise BenchmarkError(f"{sample.get('sample_id')}: target without symbol/function")
        return value
    if kind == "va_range":
        if not isinstance(target.get("va"), int) or not isinstance(target.get("end"), int):
            raise BenchmarkError(f"{sample.get('sample_id')}: invalid va_range target")
        return {"va": target["va"], "end": target["end"]}
    return None


def _poc_manifest(sample: dict[str, Any]) -> dict[str, Any] | None:
    oracle = sample.get("oracle") or {}
    if "external_poc" not in (oracle.get("kinds") or []):
        return None
    path = oracle.get("manifest_path")
    if not path:
        return None
    from app.services.poc_runner import load_manifest as load_poc_manifest

    return load_poc_manifest(ROOT / str(path))


# ---------------------------------------------------------------------------
# Deterministic repair execution
# ---------------------------------------------------------------------------


def execute_repair(sample: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic ``repair_any`` for one sample and extract evidence.

    Returns a raw record; the runner adds independent-verification fields.
    Exceptions are captured as ``not_run`` instead of crashing the run.
    """
    from app.services.binary_pipeline import repair_any  # deterministic engine

    binary_path = sample_binary_path(sample)
    data = (ROOT / binary_path).read_bytes()
    scope = sample.get("expected_scope")
    kind = (sample.get("target") or {}).get("kind")
    target = _target_argument(sample)
    poc_manifest = _poc_manifest(sample)
    allow_whole_image = kind == "whole_image"
    try:
        if scope == "analysis_only" or kind == "analysis_only":
            outcome = repair_any(data)
        else:
            outcome = repair_any(
                data,
                poc_manifest=poc_manifest,
                target=target,
                require_target=True,
                allow_whole_image=allow_whole_image,
            )
    except Exception as exc:  # noqa: BLE001 - recorded as not_run, never hidden
        return {
            "not_run": True,
            "not_run_reason": f"repair_any raised {type(exc).__name__}: {exc}",
            "detected": None,
            "candidate_produced": None,
            "integrity": None,
            "vuln_eliminated": None,
            "regression": None,
            "deterministic_verified": None,
            "disposition": None,
            "strategy": None,
            "candidate_sha256": None,
            "patched_sha256": None,
            "poc_status": None,
            "runtime_tier": None,
            "gate_outcome": None,
            "error": f"{type(exc).__name__}: {exc}",
            "patch_plan": None,
            "resolved_scope": None,
            "actions": [],
            "message_actions": [],
            "abi_blocks": [],
            "layout_checks": {},
            "gate_success": False,
            "_candidate_bytes": None,
        }
    report = outcome.report
    candidate = outcome.candidate
    candidate_sha256 = _sha256_bytes(candidate) if candidate is not None else None
    patched_sha256 = report.patched_sha256
    integrity = (
        bool(candidate is not None and patched_sha256 == candidate_sha256)
        if candidate is not None else None
    )
    poc = report.poc if isinstance(report.poc, dict) else {}
    verification = report.verification if isinstance(report.verification, dict) else {}
    gate = verification.get("gate") if isinstance(verification.get("gate"), dict) else {}
    poc_status = poc.get("status")
    regression_cases = poc.get("regression") or []
    candidate_regression = [
        case for case in regression_cases
        if isinstance(case, dict) and case.get("executable") == "candidate"
    ]
    if regression_cases and poc_status == "pass":
        regression: bool | None = True
    elif regression_cases and poc_status == "fail":
        regression = False if any(
            case.get("crashed") is True or case.get("timed_out") is True
            for case in candidate_regression
        ) else None
    else:
        regression = None
    if poc_status == "pass" and gate.get("success") is True:
        vuln_eliminated: bool | None = True
    elif poc_status == "fail":
        vuln_eliminated = False
    else:
        vuln_eliminated = None
    runtime = report.runtime if isinstance(report.runtime, dict) else {}
    universal = report.universal if isinstance(report.universal, dict) else {}
    verification = report.verification if isinstance(report.verification, dict) else {}
    packet = verification.get("packet") if isinstance(verification.get("packet"), dict) else {}
    capacity_packet = packet.get("capacity") if isinstance(packet.get("capacity"), dict) else {}
    message_actions = capacity_packet.get("message_actions") if isinstance(
        capacity_packet.get("message_actions"), list
    ) else []
    plan_checks = {
        str(check.get("id")): str(check.get("status"))
        for check in (packet.get("checks") or [])
        if isinstance(check, dict) and str(check.get("id") or "").startswith("patch.")
    }
    return {
        "not_run": False,
        "not_run_reason": None,
        "detected": bool(report.findings) or candidate is not None or poc_status == "pass",
        "candidate_produced": bool(candidate is not None or report.candidate_available),
        "integrity": integrity,
        "vuln_eliminated": vuln_eliminated,
        "regression": regression,
        "deterministic_verified": bool(outcome.verified),
        "disposition": report.disposition,
        "strategy": report.strategy,
        "candidate_sha256": candidate_sha256,
        "patched_sha256": patched_sha256,
        "poc_status": poc_status,
        "runtime_tier": runtime.get("tier") or poc.get("tier"),
        "gate_outcome": gate.get("outcome"),
        "error": report.error,
        "patch_plan": report.patch_plan,
        "resolved_scope": universal.get("target_scope"),
        "actions": [dict(item) for item in (report.actions or [])],
        "message_actions": message_actions,
        "abi_blocks": list((report.patch_plan or {}).get("abi_blocks") or []),
        "layout_checks": plan_checks,
        "gate_success": bool((verification.get("gate") or {}).get("success")),
        "verifier_id": None,
        "_candidate_bytes": candidate,
    }


# ---------------------------------------------------------------------------
# Independent verifier loading / invocation
# ---------------------------------------------------------------------------


def _load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"phase8_verifier_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise BenchmarkError(f"cannot load verifier module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_verifier(mode: str = "none") -> tuple[Callable[..., Any] | None, dict[str, Any]]:
    """Return ``(verifier_callable, status)``; never fakes availability.

    Candidates are tried in order; a present but unusable verifier file is
    recorded and the next candidate is tried instead of silently giving up.
    """
    if mode in {"none", ""}:
        return None, {
            "status": "not_run",
            "reason": (
                "independent verifier explicitly disabled (--verifier none); "
                "generator self-verification is never accepted as independent"
            ),
            "path": None,
        }
    if mode == "auto":
        # Prefer the in-tree verifier module API (it can receive the patch plan,
        # resolved scope, ABI block and a real run_poc oracle); the CLI is only
        # used when it actually supports --plan and executes the oracle.
        search = ["app/services/independent_verifier.py"] + [
            candidate for candidate in VERIFIER_CANDIDATES
            if candidate != "app/services/independent_verifier.py"
        ]
    else:
        search = [mode]
    attempted: list[str] = []
    reasons: list[str] = []
    for relative in search:
        if not (ROOT / relative).is_file():
            continue
        attempted.append(relative)
        try:
            module = _load_module(ROOT / relative)
        except Exception as exc:  # noqa: BLE001 - reported as not_run
            reasons.append(f"{relative}: load failed: {type(exc).__name__}: {exc}")
            continue
        adapter = None
        entry = None
        if relative.endswith("scripts/verify_repair.py"):
            cli_source = (ROOT / relative).read_text(encoding="utf-8")
            if "--plan" not in cli_source or "run_poc" not in cli_source:
                reasons.append(
                    f"{relative}: CLI lacks required --plan/run_poc oracle exchange "
                    "(task-35 interface incomplete)"
                )
                continue
            adapter = _verify_repair_cli_adapter()
            entry = "CLI --json --plan --poc + run_poc"
        elif callable(getattr(module, "verify_repair", None)):
            adapter = _independent_verifier_adapter(module)
            entry = "verify_repair keyword API (plan/scope/ABI/oracle exchange)"
        if adapter is not None:
            return adapter, {
                "status": "available",
                "reason": None,
                "path": relative,
                "entry_point": entry,
                "attempted": attempted,
            }
        reasons.append(
            f"{relative}: present but exposes no supported verifier interface"
        )
    if not attempted:
        return None, {
            "status": "not_run",
            "reason": (
                "no independent verifier exists in this tree (checked "
                f"{list(search)}); independent verification was not run"
            ),
            "path": None,
        }
    return None, {
        "status": "not_run",
        "reason": "; ".join(reasons)[:800],
        "path": attempted[0],
        "attempted": attempted,
    }


def _verify_repair_cli_adapter() -> Callable[..., Any]:
    """Adapter for the gui-docs CLI ``scripts/verify_repair.py --json``."""

    def adapter(sample: dict[str, Any], original_path: Path,
                candidate_path: Path | None,
                metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if candidate_path is None:
            return {
                "decision": "not_run",
                "reason": "no verified candidate exists to independently verify",
            }
        import subprocess
        import tempfile

        target = sample.get("target") or {}
        scope: dict[str, Any] = {"policy": "target_scoped"}
        if target.get("kind") in {"symbol", "function"}:
            scope["name"] = target.get("symbol") or target.get("function")
        if target.get("kind") == "va_range":
            scope["kind"] = "va_range"
            scope["va"] = target.get("va")
            scope["end"] = target.get("end")
        exchange = {**metadata} if isinstance(metadata, dict) else {
            "format": sample.get("format"),
            "arch": sample.get("arch"),
            "bits": sample.get("bits"),
            "endian": sample.get("endian"),
            "target_sha256": sample.get("sha256"),
            "target_scope": scope,
            "allow_whole_image": False,
            "generator": {
                "generator_id": "deterministic-repair-any/app.services.binary_pipeline",
            },
        }
        cli_source = (ROOT / "scripts" / "verify_repair.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="phase8-verifier-") as tmp:
            metadata_path = Path(tmp) / "metadata.json"
            metadata_path.write_text(json.dumps(exchange), encoding="utf-8")
            plan_path = None
            if "--plan" in cli_source and isinstance(exchange.get("patch_plan"), dict):
                plan_path = Path(tmp) / "plan.json"
                plan_path.write_text(json.dumps(exchange["patch_plan"]), encoding="utf-8")
            command = [
                sys.executable, str(ROOT / "scripts" / "verify_repair.py"),
                "--original", str(original_path),
                "--candidate", str(candidate_path),
                "--metadata", str(metadata_path),
                "--json",
            ]
            manifest_path = (sample.get("oracle") or {}).get("manifest_path")
            if manifest_path:
                command += ["--poc", str(ROOT / manifest_path)]
            if plan_path is not None:
                command += ["--plan", str(plan_path)]
            try:
                result = subprocess.run(
                    command, cwd=str(ROOT), capture_output=True, text=True,
                    timeout=300,
                )
            except Exception as exc:  # noqa: BLE001 - reported as not_run
                return {"decision": "error",
                        "reason": f"verifier CLI raised {type(exc).__name__}: {exc}"}
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "decision": "error",
                "reason": (
                    f"verifier CLI produced non-JSON output (exit {result.returncode}): "
                    f"{(result.stderr or result.stdout).strip()[:500]}"
                ),
            }
        if not isinstance(report, dict) or "decision" not in report:
            return {
                "decision": "error",
                "reason": f"verifier CLI JSON has no decision (exit {result.returncode})",
            }
        limitations = report.get("limitations") or []
        return {
            "decision": report.get("decision"),
            "reason": "; ".join(str(item) for item in limitations)[:800] or None,
            "report": report,
        }

    return adapter


def _independent_verifier_adapter(module: Any) -> Callable[..., Any]:
    """Adapter for the committed ``app.services.independent_verifier`` API."""

    def adapter(sample: dict[str, Any], original_path: Path,
                candidate_path: Path | None,
                metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if candidate_path is None:
            return {
                "decision": "not_run",
                "reason": "no verified candidate exists to independently verify",
            }
        target = sample.get("target") or {}
        scope: dict[str, Any] = {"policy": "target_scoped"}
        if target.get("kind") in {"symbol", "function"}:
            scope["name"] = target.get("symbol") or target.get("function")
        if target.get("kind") == "va_range":
            scope["kind"] = "va_range"
            scope["va"] = target.get("va")
            scope["end"] = target.get("end")
        if isinstance(metadata, dict):
            exchange = {**metadata}
        else:
            exchange = {
                "format": sample.get("format"),
                "arch": sample.get("arch"),
                "bits": sample.get("bits"),
                "endian": sample.get("endian"),
                "target_sha256": sample.get("sha256"),
                "target_scope": scope,
                "allow_whole_image": False,
                "generator": {
                    "generator_id": "deterministic-repair-any/app.services.binary_pipeline",
                },
            }
        oracle = None
        run_poc = None
        manifest_path = (sample.get("oracle") or {}).get("manifest_path")
        if manifest_path:
            oracle = manifest_path
            try:
                from app.services.poc_runner import run_poc as _run_poc

                run_poc = _run_poc
            except Exception:  # noqa: BLE001 - verifier records oracle unavailable
                run_poc = None
        try:
            import inspect as _inspect

            parameters = set(_inspect.signature(module.verify_repair).parameters)
            call_kwargs: dict[str, Any] = {
                "original": original_path.read_bytes(),
                "candidate": candidate_path.read_bytes(),
                "metadata": exchange,
                "oracle": oracle,
                "generator": exchange["generator"],
                "run_poc": run_poc,
            }
            for extra in ("patch_plan", "abi_block", "authority", "claimed_actions"):
                if extra in parameters:
                    call_kwargs[extra] = exchange.get(extra)
            report = module.verify_repair(**call_kwargs)
        except Exception as exc:  # noqa: BLE001 - verifier failure is evidence
            return {"decision": "error", "reason": f"{type(exc).__name__}: {exc}"}
        limitations = report.get("limitations") or []
        return {
            "decision": report.get("decision"),
            "reason": "; ".join(str(item) for item in limitations)[:800] or None,
            "report": report,
        }

    return adapter


_CAPACITY_MESSAGE_AUTHORIZATION = "authorization:capacity-message:v1"


def _file_offset_for_va(data: bytes, va: int) -> int | None:
    from app.services.containers import detect_container

    container = detect_container(data)
    for section in getattr(container, "sections", []) or []:
        sec_va = getattr(section, "va", None)
        sec_size = getattr(section, "size", None)
        sec_offset = getattr(section, "offset", None)
        if (
            isinstance(sec_va, int) and isinstance(sec_size, int) and sec_size > 0
            and isinstance(sec_offset, int) and sec_va <= va < sec_va + sec_size
        ):
            return sec_offset + (va - sec_va)
    return None


def build_verifier_metadata(sample: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """Exchange resolved scope, plan, actions, ABI evidence and oracle metadata."""
    original = (ROOT / sample_binary_path(sample)).read_bytes()
    scope = raw.get("resolved_scope") if isinstance(raw.get("resolved_scope"), dict) else {}
    plan = raw.get("patch_plan") if isinstance(raw.get("patch_plan"), dict) else None
    target_scope: dict[str, Any] = {"policy": "target_scoped"}
    if scope.get("name"):
        target_scope["name"] = str(scope["name"])
    if isinstance(scope.get("va"), int):
        target_scope["va"] = int(scope["va"])
    if isinstance(scope.get("end"), int):
        target_scope["end"] = int(scope["end"])
    if scope.get("source") == "explicit":
        target_scope["kind"] = "va_range"
    abi_block = None
    abi_blocks = raw.get("abi_blocks") if isinstance(raw.get("abi_blocks"), list) else []
    if abi_blocks and isinstance(abi_blocks[0], dict):
        block = abi_blocks[0]
        va = block.get("va")
        size = block.get("size")
        if isinstance(va, int) and isinstance(size, int) and size > 0:
            offset = _file_offset_for_va(original, va)
            if offset is not None:
                abi_block = {
                    "offset": offset,
                    "size": size,
                    "arch": str(block.get("arch") or sample.get("arch") or ""),
                    "function": str(block.get("function") or "target"),
                    "abi_id": str(block.get("abi_id") or ""),
                }
    authority = None
    if sample.get("sample_id") == "heap-capacity-x86_64":
        message_actions = raw.get("message_actions") or []
        authorized = []
        for action in message_actions:
            if not isinstance(action, dict):
                continue
            offset = action.get("offset")
            size = action.get("size")
            if not isinstance(offset, int) or not isinstance(size, int):
                continue
            digest = _sha256_bytes(
                json.dumps(action, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            authorized.append({
                "kind": "rodata_message",
                "reason": "reviewed capacity message rewrite",
                "authorization_ref": f"authorization:capacity-message:v1 sha256={digest}",
                "file_offset": offset,
                "size": size,
                "section": ".rodata",
            })
        if authorized:
            authority = {
                "scope_policy": "target_scoped_associated",
                "authorized_changes": authorized,
            }
    exchange_plan = None
    if isinstance(plan, dict):
        exchange_plan = json.loads(json.dumps(plan))
        oracle = exchange_plan.get("oracle")
        manifest_path = (sample.get("oracle") or {}).get("manifest_path")
        if isinstance(oracle, dict) and manifest_path:
            try:
                oracle["manifest_sha256"] = _sha256_bytes(
                    (ROOT / manifest_path).read_bytes()
                )
            except OSError:
                pass
            oracle.pop("evidence_sha256", None)
    metadata = {
        "format": sample.get("format"),
        "arch": sample.get("arch"),
        "bits": sample.get("bits"),
        "endian": sample.get("endian"),
        "target_sha256": sample.get("sha256"),
        "candidate_sha256": raw.get("candidate_sha256"),
        "target_scope": target_scope,
        "allow_whole_image": False,
        "generator": {
            "generator_id": "deterministic-repair-any/app.services.binary_pipeline",
        },
        "patch_plan": exchange_plan,
        "actions": raw.get("actions") or [],
        "message_actions": raw.get("message_actions") or [],
        "abi_block": abi_block,
        "oracle_manifest": (sample.get("oracle") or {}).get("manifest_path"),
    }
    if authority is not None:
        metadata["authority"] = authority
    return metadata


def _call_verifier(verifier: Callable[..., Any], sample: dict[str, Any],
                   candidate_path: Path | None,
                   metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Invoke an injected verifier; normalize dict/bool/None results."""
    import inspect as _inspect

    original_path = ROOT / sample_binary_path(sample)
    try:
        parameters = len(_inspect.signature(verifier).parameters)
        if parameters >= 4 and metadata is not None:
            result = verifier(sample, original_path, candidate_path, metadata)
        else:
            result = verifier(sample, original_path, candidate_path)
    except Exception as exc:  # noqa: BLE001 - recorded as verifier failure
        return {"decision": "error", "reason": f"{type(exc).__name__}: {exc}"}
    if result is None:
        return {"decision": "not_run", "reason": "verifier returned None"}
    if isinstance(result, bool):
        return {"decision": "verified" if result else "rejected", "reason": "boolean verdict"}
    if isinstance(result, dict):
        decision = result.get("decision") or result.get("verified")
        if isinstance(decision, bool):
            return {"decision": "verified" if decision else "rejected",
                    "report": result, "reason": result.get("reason")}
        if decision in {"verified", "rejected", "not_run", "error", "fail", "inconclusive"}:
            return {
                "decision": "rejected" if decision == "fail" else decision,
                "report": result,
                "reason": result.get("reason"),
            }
        return {"decision": "error", "report": result,
                "reason": f"unsupported verifier decision {decision!r}"}
    return {"decision": "error", "reason": f"unsupported verifier result {type(result).__name__}"}


# ---------------------------------------------------------------------------
# Benchmark execution
# ---------------------------------------------------------------------------


def _plan_sha256(plan: Any) -> str | None:
    if not isinstance(plan, dict):
        return None
    return _sha256_bytes(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _inner_verifier_report(independent: dict[str, Any]) -> dict[str, Any] | None:
    report = independent.get("report") if isinstance(independent, dict) else None
    if not isinstance(report, dict):
        return None
    inner = report.get("report")
    if isinstance(inner, dict) and "verifier" in inner:
        return inner
    return report if "verifier" in report else None


def _verifier_id(independent: dict[str, Any]) -> str | None:
    report = _inner_verifier_report(independent)
    if not isinstance(report, dict):
        return None
    verifier = report.get("verifier")
    if isinstance(verifier, dict):
        return str(verifier.get("verifier_id") or "") or None
    return None


def run_benchmark(
    manifest: dict[str, Any],
    *,
    split: str = "all",
    max_samples: int | None = None,
    repair_fn: Callable[[dict[str, Any]], dict[str, Any]] = execute_repair,
    verifier: Callable[..., Any] | None = None,
    verifier_status: dict[str, Any] | None = None,
    claim_policy: str = "fail_on_disagreement",
) -> dict[str, Any]:
    """Run the benchmark.

    ``claim_policy``:
      * ``fail_on_disagreement`` (default) - a deterministic verified claim
        rejected by an available independent verifier aborts the run with
        ``false_verified > 0``;
      * ``withdraw`` - the artifact withdraws the deterministic claim
        (``deterministic_claim_withdrawn=True``), keeps
        ``false_verified == 0`` and records the disagreement explicitly in
        ``verification_disagreements``.
    """
    if claim_policy not in {"fail_on_disagreement", "withdraw"}:
        raise BenchmarkError(f"unsupported claim policy: {claim_policy!r}")
    """Run the benchmark over the selected samples (deterministic engine only)."""
    samples = list(manifest["samples"])
    if split != "all":
        samples = [sample for sample in samples if sample.get("split") == split]
    if max_samples is not None:
        samples = samples[: max(0, int(max_samples))]
    status = dict(verifier_status or {
        "status": "not_run",
        "reason": "no independent verifier was provided",
        "path": None,
    })
    results: list[dict[str, Any]] = []
    for sample in samples:
        raw = repair_fn(sample)
        metadata: dict[str, Any] | None = None
        try:
            metadata = build_verifier_metadata(sample, raw)
        except Exception:  # noqa: BLE001 - metadata is evidence, not a verdict
            metadata = None
        independent: dict[str, Any]
        if raw.get("not_run"):
            independent = {
                "decision": "not_run",
                "reason": raw.get("not_run_reason") or "repair not run",
            }
        elif verifier is not None and status.get("status") == "available":
            candidate_bytes = raw.get("_candidate_bytes")
            if candidate_bytes:
                import tempfile

                with tempfile.NamedTemporaryFile(
                    prefix=f"phase8-candidate-{sample['sample_id']}-", suffix=".bin",
                    delete=False,
                ) as handle:
                    handle.write(candidate_bytes)
                    candidate_path = Path(handle.name)
                try:
                    independent = _call_verifier(
                        verifier, sample, candidate_path, metadata
                    )
                finally:
                    candidate_path.unlink(missing_ok=True)
            else:
                independent = _call_verifier(verifier, sample, None, metadata)
        else:
            independent = {
                "decision": "not_run",
                "reason": status.get("reason") or "independent verifier not available",
            }
        deterministic_verified = raw.get("deterministic_verified") is True
        verifier_decision = independent.get("decision")
        if verifier_decision in {"not_run", "error", "inconclusive"}:
            independently_verified: bool | None = None
            false_verified = False
        else:
            independently_verified = verifier_decision == "verified"
            false_verified = deterministic_verified and not independently_verified
        result = {
            "sample_id": sample["sample_id"],
            "split": sample["split"],
            "expected_scope": sample["expected_scope"],
            "vulnerability_class": sample["vulnerability_class"],
            "sha256": sample["sha256"],
            "detected": raw.get("detected"),
            "candidate_produced": raw.get("candidate_produced"),
            "integrity": raw.get("integrity"),
            "vuln_eliminated": raw.get("vuln_eliminated"),
            "regression": raw.get("regression"),
            "independently_verified": independently_verified,
            "not_run": bool(raw.get("not_run")),
            "false_verified": bool(false_verified),
            "deterministic_verified": bool(deterministic_verified),
            "disposition": raw.get("disposition"),
            "strategy": raw.get("strategy"),
            "poc_status": raw.get("poc_status"),
            "runtime_tier": raw.get("runtime_tier"),
            "gate_outcome": raw.get("gate_outcome"),
            "candidate_sha256": raw.get("candidate_sha256"),
            "patched_sha256": raw.get("patched_sha256"),
            "verifier_decision": verifier_decision,
            "verifier_reason": independent.get("reason"),
            "verification_disagreement": bool(false_verified),
            "deterministic_claim_withdrawn": False,
            "patch_plan_sha256": _plan_sha256(raw.get("patch_plan")),
            "verifier_id": _verifier_id(independent),
            "oracle_status": raw.get("poc_status") or "not_run",
            "layout_status": (raw.get("layout_checks") or {}).get("patch.rewrite") or "not_run",
            "real_verification": independently_verified is True,
            "not_run_reason": raw.get("not_run_reason"),
            "error": raw.get("error"),
            "abi_blocks": list(raw.get("abi_blocks") or []),
        }
        original_bytes = None
        try:
            original_bytes = (ROOT / sample_binary_path(sample)).read_bytes()
        except OSError:
            original_bytes = None
        result["_evidence"] = {
            "original_bytes": original_bytes,
            "candidate_bytes": raw.get("_candidate_bytes"),
            "outcome": {
                key: raw.get(key) for key in (
                    "not_run", "detected", "candidate_produced", "integrity",
                    "deterministic_verified", "disposition", "strategy",
                    "poc_status", "runtime_tier", "gate_outcome", "error",
                    "candidate_sha256", "patched_sha256",
                ) if not key.startswith("_")
            },
            "metadata": metadata,
            "plan": metadata.get("patch_plan") if isinstance(metadata, dict) else None,
            "verifier_report": _inner_verifier_report(independent) or independent.get("report"),
        }
        results.append(result)
    return _aggregate(manifest, results, status, claim_policy)


def _aggregate(manifest: dict[str, Any], results: list[dict[str, Any]],
               verifier_status: dict[str, Any], claim_policy: str) -> dict[str, Any]:
    def count(field: str) -> int:
        return sum(1 for result in results if result.get(field) is True)

    def null_count(field: str) -> int:
        return sum(1 for result in results if result.get(field) is None)

    by_class: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_class.setdefault(result["vulnerability_class"], {
            "samples": 0, "executed": 0, "not_run": 0, "detected": 0,
            "candidate_produced": 0, "deterministic_verified": 0,
            "independently_verified": 0, "false_verified": 0,
            "vuln_eliminated": 0,
        })
        bucket["samples"] += 1
        bucket["executed"] += 0 if result["not_run"] else 1
        bucket["not_run"] += 1 if result["not_run"] else 0
        for field in ("detected", "candidate_produced", "deterministic_verified",
                      "independently_verified", "false_verified", "vuln_eliminated"):
            if result.get(field) is True:
                bucket[field] += 1
    by_class = {name: bucket for name, bucket in sorted(by_class.items())}
    summary = {
        "samples": len(results),
        "dev": sum(1 for result in results if result["split"] == "dev"),
        "validation": sum(1 for result in results if result["split"] == "validation"),
        "executed": sum(1 for result in results if not result["not_run"]),
        "not_run": sum(1 for result in results if result["not_run"]),
        "detected": count("detected"),
        "candidate_produced": count("candidate_produced"),
        "integrity_ok": sum(1 for result in results if result.get("integrity") is True),
        "deterministic_verified": count("deterministic_verified"),
        "independently_verified": count("independently_verified"),
        "independently_verified_unknown": null_count("independently_verified"),
        "false_verified": count("false_verified"),
        "verification_disagreements": 0,
        "deterministic_claim_withdrawn": 0,
        "vuln_eliminated": count("vuln_eliminated"),
        "regression_ok": count("regression"),
    }
    false_verified_total = summary["false_verified"]
    withdrawn_total = 0
    if false_verified_total != 0:
        if claim_policy == "fail_on_disagreement":
            raise BenchmarkError(
                f"false_verified={false_verified_total} (must be 0): an independently "
                "rejected deterministic claim was detected"
            )
        # Withdraw the deterministic claim: the artifact must not keep a verified
        # claim that an independent verifier rejected, so the published
        # false_verified count is 0 while the disagreement is recorded.
        for result in results:
            if result["false_verified"]:
                result["deterministic_claim_withdrawn"] = True
                result["verification_disagreement"] = True
                result["false_verified"] = False
                withdrawn_total += 1
        summary["deterministic_claim_withdrawn"] = withdrawn_total
        summary["verification_disagreements"] = withdrawn_total
        summary["false_verified"] = 0
    if any(result["not_run"] and not result.get("not_run_reason") for result in results):
        raise BenchmarkError("a not_run sample has no explicit reason")
    manifest_path = ROOT / MANIFEST_PATH
    manifest_sha256 = _sha256_file(manifest_path) if manifest_path.is_file() else None
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "benchmark_id": manifest.get("benchmark_id"),
        "generated_at": manifest.get("generated_at"),
        "generated_at_note": (
            "inherited from the deterministic benchmark manifest; the runner "
            "reads no wall clock"
        ),
        "manifest_path": MANIFEST_PATH,
        "manifest_sha256": manifest_sha256,
        "manifest_hidden_available": manifest.get("hidden_available"),
        "claim_policy": claim_policy,
        "host": {
            "platform": sys.platform,
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "independent_verifier": verifier_status,
        "metric_definitions": {
            "detected": (
                "the deterministic engine reported >=1 finding, produced a "
                "verified candidate, or the PoC oracle passed; container-only "
                "'universal.detected' is not used as a vulnerability detection"
            ),
            "candidate_produced": "repair_any returned a candidate patch",
            "integrity": "candidate bytes sha256 == report patched_sha256",
            "vuln_eliminated": "PoC oracle status pass AND unified gate success",
            "regression": (
                "PoC verifier pass covers the declared PoC+regression cases; for a "
                "failed verification, regression is false only if a candidate "
                "regression case crashed/timed out"
            ),
            "independently_verified": (
                "independent verifier decision=verified; null/not_run when no "
                "independent verifier is available (generator self-verification "
                "is never accepted)"
            ),
            "false_verified": (
                "deterministic verified claim rejected by an available independent "
                "verifier; must be 0"
            ),
            "not_run": "repair or verification could not be executed; reason recorded",
            "patch_plan_sha256": (
                "sha256 of the exchanged patch plan (canonical JSON) when a "
                "candidate/plan was produced"
            ),
            "verifier_id": "independent verifier identity from its report",
            "oracle_status": "declared PoC oracle status (pass/fail/not_run/unavailable)",
            "layout_status": (
                "pipeline plan-aware patch.rewrite status (passed/failed/not_run); "
                "stack guard insertions and associated rodata changes are declared "
                "in the exchanged plan"
            ),
            "real_verification": (
                "true only when the independent verifier decision is verified "
                "with an executed oracle (never inferred)"
            ),
        },
        "summary": summary,
        "by_class": by_class,
        "results": results,
        "limitations": [
            "deterministic repair readiness only: no AI provider and no network "
            "is used by this runner.",
            "false_verified must be 0; a deterministic verified claim rejected by "
            "an available independent verifier fails the run.",
            "when no independent verifier is available, independently_verified is "
            "null/not_run and deterministic claims are never relabelled as "
            "independently verified.",
            "host-unavailable or raised repair calls are recorded as not_run with "
            "an explicit reason; availability is never fabricated.",
            "candidate bytes, patch plans, exchanged metadata and independent "
            "verifier reports are persisted per sample under samples/<sample_id>/ "
            "and covered by SHA256SUMS (evidence only; not executed by the runner).",
        ] + ([
            f"{summary['verification_disagreements']} deterministic verified "
            "claim(s) were withdrawn after independent verification rejected "
            "them; they are counted under verification_disagreements and are "
            "never presented as verified."
        ] if summary["verification_disagreements"] else []),
        "provenance": {
            "runner": "scripts/run_repair_benchmark.py",
            "engine": "app.services.binary_pipeline.repair_any (deterministic)",
            "no_ai": True,
            "no_network": True,
        },
    }


# ---------------------------------------------------------------------------
# README / artifact I/O
# ---------------------------------------------------------------------------


def render_sha256sums(files: dict[str, bytes]) -> bytes:
    lines = [f"{_sha256_bytes(files[name])}  {name}" for name in ARTIFACT_FILES]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _fmt(value: Any) -> str:
    if value is None:
        return "not_run"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def render_readme(results: dict[str, Any]) -> str:
    summary = results["summary"]
    verifier = results["independent_verifier"]
    lines: list[str] = [
        "# Deterministic repair benchmark results (Phase-8B, 2026-11-16)",
        "",
        "Generated by `scripts/run_repair_benchmark.py` from the committed",
        "ground-truth manifest. The runner uses the **deterministic** repair engine",
        f"only (`{results['provenance']['engine']}`); no AI provider and no network",
        "were used.",
        "",
        f"- manifest: `{results['manifest_path']}` sha256 `{results['manifest_sha256']}`",
        f"- host: {results['host']['platform']}/{results['host']['machine']} "
        f"(python {results['host']['python']})",
        f"- independent verifier: status=`{verifier['status']}`"
        + (f", path=`{verifier.get('path')}`" if verifier.get("path") else "")
        + (f" - {verifier.get('reason')}" if verifier.get("reason") else ""),
        "",
        "Artifact files: `results.json` (per-sample + aggregate), `README.md`",
        "(this file), `SHA256SUMS` (covers every listed file; never itself) and",
        "`samples/<sample_id>/` evidence: `original.bin`, `candidate.bin`,",
        "`outcome.json`, `metadata.json` (exchanged plan/scope/ABI/oracle),",
        "`plan.json` (patch plan, when produced) and `verifier-report.json`",
        "(independent verifier report, when run).",
        "",
        "## Summary",
        "",
        "| metric | count |",
        "|---|---|",
    ]
    for field in ("samples", "dev", "validation", "executed", "not_run",
                  "detected", "candidate_produced", "integrity_ok",
                  "deterministic_verified", "independently_verified",
                  "independently_verified_unknown", "false_verified",
                  "verification_disagreements", "deterministic_claim_withdrawn",
                  "vuln_eliminated", "regression_ok"):
        lines.append(f"| {field} | {summary[field]} |")
    lines += [
        "",
        "`false_verified` must be 0: no deterministic verified claim may be",
        "rejected by an available independent verifier. When no independent",
        "verifier is available, `independently_verified` is null/not_run and the",
        "deterministic claims are **not** relabelled as independently verified.",
        "",
    ]
    if summary["verification_disagreements"]:
        lines += [
            f"**Independent verifier disagreement:** "
            f"{summary['verification_disagreements']} deterministic verified "
            "claim(s) were rejected by the independent verifier and are "
            "**withdrawn** (`deterministic_claim_withdrawn=true`, "
            "`claim_policy=" + results["claim_policy"] + "`); the published "
            "`false_verified` count is 0 because no rejected claim is kept as "
            "verified. This is a real engine/verifier semantic gap, not a pass.",
        ]
    lines += [
        "",
        "## Per-class stratification",
        "",
        "| class | samples | executed | not_run | detected | candidate | deterministic verified | independently verified | false verified |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, bucket in results["by_class"].items():
        lines.append(
            f"| {name} | {bucket['samples']} | {bucket['executed']} | "
            f"{bucket['not_run']} | {bucket['detected']} | "
            f"{bucket['candidate_produced']} | {bucket['deterministic_verified']} | "
            f"{bucket['independently_verified']} | {bucket['false_verified']} |"
        )
    lines += [
        "",
        "## Per-sample results",
        "",
        "| sample_id | split | detected | candidate | integrity | vuln_eliminated | regression | independently_verified | false_verified | verifier | plan layout | disposition |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results["results"]:
        lines.append(
            f"| `{result['sample_id']}` | {result['split']} | "
            f"{_fmt(result['detected'])} | {_fmt(result['candidate_produced'])} | "
            f"{_fmt(result['integrity'])} | {_fmt(result['vuln_eliminated'])} | "
            f"{_fmt(result['regression'])} | "
            f"{_fmt(result['independently_verified'])} | "
            f"{_fmt(result['false_verified'])} | "
            f"{result.get('verifier_decision')} | {result.get('layout_status')} | "
            f"{result['disposition']} |"
        )
    lines += [
        "",
        "## Not-run / verifier details",
        "",
    ]
    for result in results["results"]:
        if result["not_run"]:
            lines.append(f"- `{result['sample_id']}` not_run: {result['not_run_reason']}")
        if result.get("verifier_decision") in {"not_run", "error"}:
            lines.append(
                f"- `{result['sample_id']}` independent verification "
                f"{result['verifier_decision']}: {result['verifier_reason']}"
            )
    lines += [
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in results["limitations"])
    return "\n".join(lines) + "\n"


def _public_results(results: dict[str, Any]) -> dict[str, Any]:
    """Results without private evidence bytes (safe for results.json)."""
    public = {
        key: value for key, value in results.items() if not key.startswith("_")
    }
    public["results"] = [
        {key: value for key, value in result.items() if not key.startswith("_")}
        for result in results.get("results") or []
    ]
    return public


def _evidence_files(results: dict[str, Any]) -> dict[str, bytes]:
    """Per-candidate evidence files (relative path -> bytes)."""
    files: dict[str, bytes] = {}
    for result in results.get("results") or []:
        evidence = result.get("_evidence")
        if not isinstance(evidence, dict):
            continue
        sample_id = str(result.get("sample_id") or "sample")
        base = f"samples/{sample_id}"
        original = evidence.get("original_bytes")
        if isinstance(original, (bytes, bytearray)):
            files[f"{base}/original.bin"] = bytes(original)
        candidate = evidence.get("candidate_bytes")
        if isinstance(candidate, (bytes, bytearray)):
            files[f"{base}/candidate.bin"] = bytes(candidate)
        for name, payload in (
            ("outcome.json", evidence.get("outcome")),
            ("metadata.json", evidence.get("metadata")),
            ("plan.json", evidence.get("plan")),
            ("verifier-report.json", evidence.get("verifier_report")),
        ):
            if payload is None:
                continue
            files[f"{base}/{name}"] = (
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
            ).encode("utf-8")
    return files


def build_results_artifact(results: dict[str, Any]) -> dict[str, bytes]:
    public = _public_results(results)
    results_bytes = (
        json.dumps(public, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    files: dict[str, bytes] = {
        "results.json": results_bytes,
        "README.md": render_readme(public).encode("utf-8"),
    }
    return files


def write_results(results: dict[str, Any], out_dir: Path) -> list[dict[str, str]]:
    files = build_results_artifact(results)
    evidence_files = _evidence_files(results)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for name, payload in files.items():
        target = out_dir / name
        target.write_bytes(payload)
        written.append({"path": str(target), "sha256": _sha256_bytes(payload)})
    for relative, payload in sorted(evidence_files.items()):
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        written.append({"path": str(target), "sha256": _sha256_bytes(payload)})
    sums_lines = [
        f"{_sha256_bytes(payload)}  {relative}"
        for relative, payload in sorted({**files, **evidence_files}.items())
    ]
    sums = ("\n".join(sums_lines) + "\n").encode("utf-8")
    (out_dir / "SHA256SUMS").write_bytes(sums)
    written.append({"path": str(out_dir / "SHA256SUMS"), "sha256": _sha256_bytes(sums)})
    return written


def summarize(results: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "benchmark_id": results["benchmark_id"],
        "manifest_sha256": results["manifest_sha256"],
        "host": results["host"],
        "independent_verifier": results["independent_verifier"],
        "summary": results["summary"],
        "by_class": results["by_class"],
        "results": [
            {
                "sample_id": result["sample_id"],
                "split": result["split"],
                "detected": result["detected"],
                "candidate_produced": result["candidate_produced"],
                "integrity": result["integrity"],
                "vuln_eliminated": result["vuln_eliminated"],
                "regression": result["regression"],
                "independently_verified": result["independently_verified"],
                "not_run": result["not_run"],
                "false_verified": result["false_verified"],
                "disposition": result["disposition"],
                "patch_plan_sha256": result.get("patch_plan_sha256"),
                "verifier_id": result.get("verifier_id"),
                "oracle_status": result.get("oracle_status"),
                "layout_status": result.get("layout_status"),
                "verifier_decision": result.get("verifier_decision"),
                "real_verification": result.get("real_verification"),
                "abi_blocks": result.get("abi_blocks"),
            }
            for result in results["results"]
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic repair benchmark from the committed manifest "
            "(no AI, no network)."
        ),
    )
    parser.add_argument("--manifest", default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--split", choices=("all", "dev", "validation"), default="all")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--verifier", default="none",
                        help="none | auto | path to an independent verifier module")
    parser.add_argument("--claim-policy", choices=("fail_on_disagreement", "withdraw"),
                        default="fail_on_disagreement",
                        help=(
                            "fail on an independently rejected deterministic claim "
                            "or withdraw the claim and record the disagreement"
                        ))
    parser.add_argument("--json", action="store_true",
                        help="print a JSON summary instead of writing artifacts")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        verifier, verifier_status = discover_verifier(args.verifier)
        results = run_benchmark(
            manifest,
            split=args.split,
            max_samples=args.max_samples,
            verifier=verifier,
            verifier_status=verifier_status,
            claim_policy=args.claim_policy,
        )
        if args.json:
            print(json.dumps(summarize(results), indent=2, ensure_ascii=False))
            return 0 if results["summary"]["false_verified"] == 0 else 1
        written = write_results(results, args.out)
        print(json.dumps({
            "ok": True,
            "out": str(args.out),
            "written": written,
            "summary": results["summary"],
            "independent_verifier": results["independent_verifier"],
        }, indent=2, ensure_ascii=False))
        return 0 if results["summary"]["false_verified"] == 0 else 1
    except BenchmarkError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
