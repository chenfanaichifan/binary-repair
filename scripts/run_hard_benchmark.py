#!/usr/bin/env python3
"""Hard-case AI increment benchmark (real provider, target-function mode).

Deterministic baseline and AI assembly-target repair are run on cases whose
sink is deliberately outside the deterministic analyzer's templates.  The only
acceptance authority is the native/qemu PoC+regression runner.  The script also
supports --reference to validate the harness with a known-good assembly fix.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_assembly_repair import (  # noqa: E402
    ASM_MAX_TOKENS, ASM_SYSTEM_PROMPT, _assemble, _assembly_packet,
    _apply_call_relocations, _assemble_with_relocations, _disassemble_function,
    _inject_blob, _patch_binary_call_relocations, _redirect_function,
    _validate_assembly_text, _validate_code,
)
from app.services.ai_binary_repair import _ai_base, _call_model, _sha  # noqa: E402
from app.services.binary_pipeline import repair_any  # noqa: E402
from app.services.containers import detect_container  # noqa: E402
from app.services.poc_runner import run_poc  # noqa: E402
from app.services.repair.analyzer import Sink  # noqa: E402
from app.services.repair.call_targets import discover_allowed_calls  # noqa: E402
from app.services.repair.writer import repair_with_sinks  # noqa: E402


def _target_va(container: Any, target: str) -> int | None:
    symbols = getattr(container, "symbols", {}) or {}
    for va, name in symbols.items():
        if name == target:
            return int(va)
    for va, name in symbols.items():
        if target in str(name):
            return int(va)
    return None


def _scope_end(scope: Any) -> int | None:
    if not isinstance(scope, dict):
        return None
    end = scope.get("end")
    if isinstance(end, int) and not isinstance(end, bool):
        return end
    return None


def _actions_in_target_scope(actions: list[dict[str, Any]], scope: Any) -> bool:
    """Whether every produced action has a numeric site_va inside the scope.

    An empty action list is not "in scope": target-strict mode only passes when
    a candidate actually produced actions, and all of them belong to the target.
    """
    if not actions or not isinstance(scope, dict):
        return False
    start = scope.get("va")
    end = _scope_end(scope)
    if not isinstance(start, int) or isinstance(start, bool) or end is None:
        return False
    if end <= start:
        return False
    for action in actions:
        if not isinstance(action, dict):
            return False
        site = action.get("site_va")
        if not isinstance(site, int) or isinstance(site, bool):
            return False
        if not start <= site < end:
            return False
    return True


def repair_any_supports_allow_whole_image() -> bool:
    """Whether the on-disk pipeline already has the explicit whole-image opt-in."""
    try:
        return "allow_whole_image" in inspect.signature(repair_any).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return False


def _target_policy_of(outcome: Any) -> str | None:
    """Target policy recorded by the pipeline (or inferred conservatively)."""
    report = getattr(outcome, "report", None)
    universal = getattr(report, "universal", None)
    if isinstance(universal, dict):
        policy = universal.get("target_policy")
        if isinstance(policy, str) and policy:
            return policy
    return None


def _gate_summary(report: Any) -> dict[str, Any]:
    """Compact deterministic-gate summary for a produced report."""
    verification = getattr(report, "verification", None) or {}
    packet = verification.get("packet") or {}
    gate = verification.get("gate") or {}
    checks = [item for item in packet.get("checks") or [] if isinstance(item, dict)]
    return {
        "gate_success": bool(gate.get("success")),
        "gate_outcome": gate.get("outcome"),
        "reason": gate.get("reason"),
        "required_checks": gate.get("required_checks"),
        "required_not_run": gate.get("required_not_run"),
        "failed_checks": [c.get("id") for c in checks if c.get("status") == "failed"],
        "not_run_checks": [c.get("id") for c in checks if c.get("status") == "not_run"],
        "tier": verification.get("tier"),
        "engine": verification.get("engine"),
        "scope": packet.get("scope"),
    }


def _baseline_record(outcome: Any, elapsed_ms: int) -> dict[str, Any]:
    """Serializable deterministic whole-image baseline record."""
    report = outcome.report
    candidate = outcome.candidate
    return {
        "attempted": True,
        "disposition": report.disposition,
        "status": report.status,
        "verified": bool(outcome.verified),
        "error": report.error,
        "target_policy": _target_policy_of(outcome),
        "candidate_available": bool(report.candidate_available),
        "candidate_sha256": (
            hashlib.sha256(candidate).hexdigest() if candidate is not None else None
        ),
        "patched_sha256": report.patched_sha256 or None,
        "actions": [dict(action) for action in report.actions],
        "checks_summary": _gate_summary(report),
        "elapsed_ms": elapsed_ms,
    }


def _provider_metadata(client: Any, requested: str) -> dict[str, Any]:
    """Non-secret provider/model metadata (never the key, prompt or response)."""
    meta: dict[str, Any] = {
        "requested": requested,
        "client_class": None,
        "provider": None,
        "model_requested": None,
        "base_url": None,
        "configured": None,
        "errors": [],
    }
    if client is None:
        return meta
    meta["client_class"] = type(client).__name__
    meta["provider"] = (
        getattr(client, "provider_name", None)
        or getattr(client, "ai_provider", None)
        or getattr(client, "provider", None)
    )
    meta["model_requested"] = getattr(client, "model", None)
    base_url = getattr(client, "base_url", None)
    meta["base_url"] = str(base_url) if base_url else None
    return meta


def _provider_config_metadata() -> dict[str, Any]:
    """Non-secret provider config for the real-provider runs."""
    try:
        from app.services.assistant_llm import provider_config

        cfg = provider_config()
    except Exception as exc:  # noqa: BLE001 - record, never crash
        return {"configured": False, "errors": [f"{type(exc).__name__}"], "provider": None}
    return {
        "provider": cfg.get("provider"),
        "title": cfg.get("title"),
        "base_url": cfg.get("base_url"),
        "model": cfg.get("model"),
        "configured": bool(cfg.get("configured")),
        "errors": [str(item) for item in cfg.get("errors") or []],
    }


def _target_scope_of(data: bytes, target: str) -> dict[str, Any] | None:
    """Resolve the declared case target to its half-open VA scope."""
    try:
        from app.services.containers import detect_container, resolve_function_scope

        scope = resolve_function_scope(detect_container(data), target)
    except Exception:  # noqa: BLE001 - unknown scope is evidence, not a crash
        return None
    if not isinstance(scope, dict):
        return None
    return {
        "name": scope.get("name"),
        "va": scope.get("va"),
        "end": scope.get("end"),
        "source": scope.get("source"),
    }


def _baseline_target_strict(data: bytes, target: str) -> dict[str, Any]:
    """Deterministic baseline under strict target mode.

    Calls the deterministic pipeline with the declared benchmark target and
    ``require_target=True``: the result records the resolved target scope and
    whether every produced action stayed inside it.  This is the target-strict
    counterpart of ``baseline`` (which is the historical whole-image result).
    """
    started = time.perf_counter()
    try:
        outcome = repair_any(data, target=target, require_target=True, verify=True)
    except Exception as exc:  # noqa: BLE001 - record, never crash the benchmark
        return {
            "attempted": True,
            "disposition": "error",
            "verified": False,
            "error": f"{type(exc).__name__}: {exc}",
            "target_scope": None,
            "target_in_scope": False,
            "target_scope_check": "failed",
            "target_policy": "target_strict",
            "actions": [],
            "candidate_sha256": None,
            "checks_summary": {},
            "elapsed_ms": max(0, int((time.perf_counter() - started) * 1000)),
        }
    report = outcome.report
    scope = report.universal.get("target_scope")
    actions = [dict(action) for action in report.actions]
    packet = (report.verification or {}).get("packet") or {}
    check_status = None
    for check in packet.get("checks") or []:
        if check.get("id") == "patch.target_scope":
            check_status = check.get("status")
            break
    resolved = _target_scope_of(data, target)
    recorded_scope = dict(scope) if isinstance(scope, dict) else resolved
    # The production predicate must be re-derived from the actual bytes: scope
    # resolution plus every produced action inside it.  An empty action list is
    # not "in scope" (see _actions_in_target_scope), which is exactly why the
    # deterministic baseline reports target_in_scope=false on hard cases.
    in_scope = _actions_in_target_scope(actions, recorded_scope)
    if check_status is None:
        check_status = "passed" if in_scope else (
            "not_run" if not actions else "failed"
        )
    candidate = outcome.candidate
    return {
        "attempted": True,
        "disposition": report.disposition,
        "status": report.status,
        "verified": bool(outcome.verified),
        "error": report.error,
        "target_policy": "target_strict",
        "target_scope": recorded_scope,
        "target_in_scope": in_scope,
        "target_scope_check": check_status,
        "candidate_sha256": (
            hashlib.sha256(candidate).hexdigest() if candidate is not None else None
        ),
        "patched_sha256": report.patched_sha256 or None,
        "actions": actions,
        "checks_summary": _gate_summary(report),
        "elapsed_ms": max(0, int((time.perf_counter() - started) * 1000)),
    }


def _inject_target(data: bytes, target: str, capacity: int, assembly: str,
                   allowed_calls: list[Any] | None = None) -> tuple[bytes | None, dict[str, Any]]:
    allowed_calls = list(allowed_calls or [])
    container = detect_container(data)
    va = _target_va(container, target)
    if va is None:
        return None, {"error": f"target {target!r} not found"}
    sink = Sink(
        kind="unbounded_copy", arch=container.arch, function_va=va,
        capacity=capacity, patchable=True,
    )
    try:
        clean = _validate_assembly_text(assembly, container.arch, allowed_calls)
        if allowed_calls:
            code, relocs = _assemble_with_relocations(clean, container.arch)
        else:
            code, relocs = _assemble(clean, container.arch), []
    except Exception as exc:  # noqa: BLE001
        return None, {"error": f"assembly validation: {type(exc).__name__}: {exc}"}
    patched, cave_va, method = _inject_blob(container, data, code)
    if patched is None or cave_va is None:
        return None, {"error": f"injection failed: {method}"}
    try:
        if relocs:
            patched = _patch_binary_call_relocations(
                patched, cave_va, container.arch, code, relocs, allowed_calls,
            )
            resolved = _apply_call_relocations(
                code, container.arch, int(cave_va), relocs, allowed_calls,
            )
            _validate_code(resolved, container.arch, allowed_calls, base_va=int(cave_va))
        else:
            _validate_code(code, container.arch)
    except Exception as exc:  # noqa: BLE001
        return None, {"error": f"call relocation: {type(exc).__name__}: {exc}"}
    patched = _redirect_function(patched, container, sink, cave_va)
    if patched is None:
        return None, {"error": "function entry redirect failed"}
    return patched, {
        "target_va": hex(va), "cave_va": hex(cave_va), "method": method,
        "code_bytes": len(code), "assembly_sha256": hashlib.sha256(clean.encode()).hexdigest(),
        "call_targets": [getattr(item, "to_dict", lambda: {})() for item in allowed_calls],
        "call_relocations": len(relocs),
    }


def _prompt_packet(data: bytes, target: str, capacity: int, contract: str,
                   contract_level: str = "full",
                   allowed_calls: list[Any] | None = None,
                   callee_context: dict[str, Any] | None = None) -> dict[str, Any]:
    container = detect_container(data)
    va = _target_va(container, target)
    if va is None:
        raise ValueError(f"target not found: {target}")
    sink = Sink(kind="unbounded_copy", arch=container.arch, function_va=va,
                capacity=capacity, patchable=True)
    listing = _disassemble_function(data, container, sink)
    allowed_calls = list(allowed_calls or [])
    packet = _assembly_packet(data, container, sink, listing, allowed_calls)
    packet["target_function"] = target
    if callee_context is not None:
        packet["callee_context"] = callee_context
    call_rule = (
        "no external calls, syscalls, privileged instructions or indirect jumps"
        if not allowed_calls else
        "only direct calls to the exact target addresses in allowed_calls are allowed; "
        "no other calls, syscalls, privileged instructions or indirect jumps"
    )
    if contract_level == "full":
        packet["hard_case_contract"] = contract
        packet["rules"] = [
            "return a complete replacement function assembly",
            "preserve the calling convention and write at most capacity-1 bytes plus NUL",
            "preserve the observable behaviour for valid inputs",
            call_rule,
            "terminate with ret",
        ]
    elif contract_level == "generic":
        packet["hard_case_contract"] = (
            "Repair the vulnerability in the target function while preserving its "
            "normal observable behaviour."
        )
        packet["rules"] = [
            "return a complete replacement function assembly",
            "preserve the calling convention and observable behaviour",
            call_rule,
            "terminate with ret",
        ]
        packet["sink"] = {"kind": "unbounded_copy"}
    else:  # none: target and disassembly only; no repair-strategy contract
        packet.pop("hard_case_contract", None)
        packet["sink"] = {"kind": "unbounded_copy"}
        packet["rules"] = [
            "return a complete replacement function assembly",
            call_rule,
            "terminate with ret",
        ]
    return packet


def _baseline_target_attempt(data: bytes, target: str, capacity: int, poc: dict) -> dict[str, Any]:
    """Give the deterministic writer the same target/function hint.

    It is still template-driven; the attempt is recorded rather than claimed.
    """
    container = detect_container(data)
    va = _target_va(container, target)
    if va is None:
        return {"attempted": False, "reason": "target not found"}
    sink = Sink(kind="unbounded_copy", arch=container.arch, function_va=va,
                capacity=capacity, patchable=True)
    try:
        result = repair_with_sinks(data, container, [sink])
    except Exception as exc:  # noqa: BLE001
        return {"attempted": True, "verified": False,
                "reason": f"{type(exc).__name__}: {exc}"}
    if result.patched is None:
        return {"attempted": True, "verified": False,
                "reason": result.limitations[-1] if result.limitations else "no candidate"}
    evidence = _evaluate(data, result.patched, poc, {})
    return {
        "attempted": True,
        "verified": evidence.get("gate") == "pass",
        "gate": evidence.get("gate"),
        "reason": "",
    }


def _fake_client(assembly: str) -> Any:
    class FakeClient:
        model = "scripted-reference"
        ai_mode = "scripted"

        def chat_json(self, messages, **kwargs):
            return SimpleNamespace(
                content=json.dumps({"schema_version": 1, "assembly": assembly}),
                model=self.model, usage={}, request_id="reference",
            )
    return FakeClient()


def _evaluate(data: bytes, patched: bytes | None, poc: dict, case: dict) -> dict:
    if patched is None:
        return {"gate": "no_candidate", "poc_status": "not_run"}
    evidence = run_poc(data, patched, poc)
    return {
        "gate": "pass" if evidence.passed else "fail",
        "poc_status": evidence.status,
        "runner": evidence.runner,
        "candidate_sha256": _sha(patched),
        "poc": evidence.to_dict(),
    }


def _ai_prompt_attempt(
    client: Any,
    data: bytes,
    case: dict[str, Any],
    contract_level: str,
    allow_calls_flag: bool,
    callee_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One real/scripted model call for the target assembly repair.

    Only the non-secret metadata returned by the shared call helper is kept:
    provider/model identity, usage, latency, request id and the typed error
    class.  The raw prompt and raw response are never stored.
    """
    from app.services.ai_binary_repair import _ai_base

    ai_meta: dict[str, Any] = _ai_base("hard_target_asm")
    allowed_calls: list[Any] = []
    if allow_calls_flag:
        container = detect_container(data)
        target_va = _target_va(container, case["target"])
        if target_va is not None:
            allowed_calls = discover_allowed_calls(data, container, target_va)
    packet = _prompt_packet(
        data, case["target"], int(case["capacity"]), case["contract"],
        contract_level, allowed_calls, callee_context,
    )
    started = time.perf_counter()
    parsed, error = _call_model(
        client, system_prompt=ASM_SYSTEM_PROMPT, packet=packet,
        max_tokens=ASM_MAX_TOKENS, ai=ai_meta,
    )
    assembly = None
    if parsed is not None and isinstance(parsed.get("assembly"), str):
        assembly = parsed["assembly"]
        ai_meta["status"] = "accepted"
    else:
        ai_meta["status"] = ai_meta.get("status") or "invalid"
        ai_meta["error"] = error or ai_meta.get("error")
    return {
        "ai": ai_meta,
        "assembly": assembly,
        "error": ai_meta.get("error"),
        "allowed_calls": [item.to_dict() for item in allowed_calls],
        "elapsed_ms": max(0, int((time.perf_counter() - started) * 1000)),
    }


def _allowed_call_objects(call_targets: list[dict[str, Any]]) -> list[Any]:
    if not call_targets:
        return []
    from app.services.repair.call_targets import AllowedCall

    return [
        AllowedCall(
            name=item["name"],
            target_va=int(item["target_va"], 16),
            source=item["source"],
        )
        for item in call_targets
    ]


def _apply_assembly_and_evaluate(
    data: bytes,
    case: dict[str, Any],
    poc: dict[str, Any],
    assembly: str,
    call_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Inject the returned assembly at the case target and run the PoC gate."""
    started = time.perf_counter()
    patched, injection = _inject_target(
        data, case["target"], int(case["capacity"]), assembly,
        _allowed_call_objects(call_targets),
    )
    candidate = _evaluate(data, patched, poc, case)
    return {
        "injection": injection,
        "candidate": candidate,
        "patched": patched,
        "elapsed_ms": max(0, int((time.perf_counter() - started) * 1000)),
    }


def _ai_target_scope(
    data: bytes,
    case: dict[str, Any],
    injection: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str, bool]:
    """Re-derive whether the AI target injection stayed inside the declared target."""
    resolved = _target_scope_of(data, case["target"])
    injection = injection if isinstance(injection, dict) else {}
    target_va = injection.get("target_va")
    injected = bool(
        injection.get("cave_va") and not injection.get("error") and target_va
    )
    if resolved is None:
        return None, ("failed" if injected else "not_run"), False
    inside = False
    if injected:
        try:
            inside = int(str(target_va), 16) == int(resolved["va"])
        except (TypeError, ValueError):
            inside = False
    if injected:
        scope_check = "passed" if inside else "failed"
    else:
        scope_check = "not_run"
    return resolved, scope_check, inside


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--client", choices=("real", "reference"), default="real")
    ap.add_argument("--case", default="",
                    help="case id, or a comma-separated list of case ids")
    ap.add_argument("--contract-level", choices=("full", "generic", "none"), default="full")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--allow-calls", action="store_true",
                    help="allow only calls already present in the target function")
    ap.add_argument("--callee-context", type=Path, default=None,
                    help="optional export_with_callees JSON to include in the target prompt")
    ap.add_argument("--target-strict", action="store_true",
                    help="only count an AI increment when the injected target scope check passed")
    ap.add_argument("--provider-tag", default="",
                    help="non-secret run label recorded in the record/summary")
    ap.add_argument("--seed", type=int, default=None,
                    help="recorded seed (the shared provider client does not marshal a seed)")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    cases = json.loads((ROOT / "fixtures" / "hard-cases" / "cases.json").read_text())["cases"]
    selected_cases = [item.strip() for item in args.case.split(",") if item.strip()]
    if selected_cases:
        cases = [case for case in cases if case["id"] in selected_cases]
    callee_context = None
    if args.callee_context is not None:
        callee_context = json.loads(args.callee_context.read_text())
    client = None
    provider_config: dict[str, Any] | None = None
    if args.client == "real":
        from app.services.assistant_llm import client_from_env

        client = client_from_env()
        provider_config = _provider_config_metadata()
    provider = _provider_metadata(client, args.client)
    if provider_config is not None:
        provider["provider_config"] = provider_config
        provider["provider"] = provider.get("provider") or provider_config.get("provider")
        provider["configured"] = provider_config.get("configured")
        provider["errors"] = list(provider_config.get("errors") or [])
        provider["model_configured"] = provider_config.get("model")
    if args.client == "real" and client is None:
        provider["status"] = "unavailable"
        provider["error"] = "llm_client_not_configured"
    elif args.client == "reference":
        provider["status"] = "reference"
    else:
        provider["status"] = "ok"
    started_all = time.perf_counter()
    results = []
    for case in cases:
        case_started = time.perf_counter()
        data = (ROOT / case["binary"]).read_bytes()
        poc = json.loads((ROOT / case["poc"]).read_text())

        # Deterministic whole-image baseline.  After the safe-default policy
        # lands this needs the explicit opt-in; before it, the historical call is
        # the whole-image baseline itself and the record says so.
        baseline_kwargs: dict[str, Any] = {"verify": True}
        whole_image_supported = repair_any_supports_allow_whole_image()
        if whole_image_supported:
            baseline_kwargs["allow_whole_image"] = True
        baseline_started = time.perf_counter()
        baseline = repair_any(data, **baseline_kwargs)
        baseline_ms = max(0, int((time.perf_counter() - baseline_started) * 1000))
        baseline_record = _baseline_record(baseline, baseline_ms)
        baseline_record["allow_whole_image_requested"] = True
        baseline_record["allow_whole_image_supported"] = whole_image_supported

        strict = _baseline_target_strict(data, case["target"])
        # cases.json omits the strict expectation when it equals the whole-image
        # baseline expectation; fall back to the declared baseline in that case.
        strict["expected"] = (
            case.get("baseline_expected_target_strict")
            or case.get("baseline_expected")
        )
        strict["expected_source"] = (
            "baseline_expected_target_strict"
            if case.get("baseline_expected_target_strict")
            else "baseline_expected (strict field omitted in cases.json)"
        )
        strict["matches_expected"] = (
            strict.get("disposition") == strict["expected"]
        )

        record: dict[str, Any] = {
            "case": case,
            "input_sha256": _sha(data),
            "baseline": baseline_record,
            "baseline_whole_image": baseline_record,
            "baseline_increment_zero": not baseline.verified,
            "baseline_target_strict": strict,
            "baseline_target_aware": _baseline_target_attempt(
                data, case["target"], int(case["capacity"]), poc,
            ),
            "ai_blind": None,
        }
        if client is not None:
            from app.services.ai_binary_repair import ASM_PATH, ai_repair
            blind = ai_repair(data, path=ASM_PATH, client=client, verify=True)
            record["ai_blind"] = {
                "status": blind.ai.get("status"),
                "disposition": blind.report.disposition,
                "verified": blind.verified,
                "elapsed_ms": blind.ai.get("latency_ms"),
            }

        ai_attempts: list[dict[str, Any]] = []
        chosen: dict[str, Any] | None = None
        if args.client == "reference":
            reference = (ROOT / case["reference_fix"])
            assembly = None
            reference_meta = {
                "attempted": True,
                "kind": reference.suffix.lstrip(".") or "unknown",
                "reference_fix": case["reference_fix"],
            }
            if reference.suffix == ".S":
                assembly = reference.read_text(encoding="utf-8")
                reference_meta["status"] = "source_assembly"
            else:
                reference_meta.update({
                    "status": "source_only",
                    "reason": "reference fix is source code with no compiled reference artifact declared in cases.json",
                })
            if assembly is not None:
                applied = _apply_assembly_and_evaluate(data, case, poc, assembly, [])
                scope, scope_check, in_scope = _ai_target_scope(data, case, applied["injection"])
                chosen = {
                    "ai": {**_ai_meta_unused(), "status": "not_attempted"},
                    "injection": applied["injection"],
                    "candidate": applied["candidate"],
                    "target_scope": scope,
                    "target_scope_check": scope_check,
                    "target_in_scope": in_scope,
                    "elapsed_ms": applied["elapsed_ms"],
                    "usage": None,
                    "request_id": None,
                    "model_returned": None,
                    "model_requested": None,
                    "error": None,
                }
                reference_meta["candidate"] = applied["candidate"]
                reference_meta["injection"] = applied["injection"]
                reference_meta["verified"] = applied["candidate"].get("gate") == "pass"
                reference_meta["candidate_sha256"] = applied["candidate"].get("candidate_sha256")
                reference_meta["target_scope_check"] = scope_check
            else:
                reference_meta["verified"] = None
                reference_meta["candidate_sha256"] = None
            record["reference_fix"] = reference_meta
        else:
            repeats = max(1, int(args.repeats))
            for repeat in range(repeats):
                prompt = _ai_prompt_attempt(
                    client, data, case, args.contract_level, args.allow_calls,
                    callee_context,
                )
                attempt: dict[str, Any] = {
                    "repeat": repeat,
                    "model": prompt["ai"].get("model"),
                    "model_requested": prompt["ai"].get("model_requested"),
                    "status": prompt["ai"].get("status"),
                    "error": prompt["ai"].get("error"),
                    "usage": prompt["ai"].get("usage"),
                    "latency_ms": prompt["ai"].get("latency_ms"),
                    "request_id": prompt["ai"].get("request_id"),
                    "assembly_returned": prompt["assembly"] is not None,
                    "assembly_sha256": (
                        hashlib.sha256(prompt["assembly"].encode()).hexdigest()
                        if prompt["assembly"] is not None else None
                    ),
                    "allowed_calls": prompt["allowed_calls"],
                    "target_in_scope": False,
                    "target_scope_check": "not_run",
                    "target_scope": None,
                    "attempted": True,
                    "verified": False,
                }
                if prompt["assembly"] is not None:
                    applied = _apply_assembly_and_evaluate(
                        data, case, poc, prompt["assembly"], prompt["allowed_calls"],
                    )
                    scope, scope_check, in_scope = _ai_target_scope(
                        data, case, applied["injection"],
                    )
                    attempt.update({
                        "injection": applied["injection"],
                        "candidate": applied["candidate"],
                        "target_scope": scope,
                        "target_scope_check": scope_check,
                        "target_in_scope": in_scope,
                        "verified": applied["candidate"].get("gate") == "pass",
                        "elapsed_ms": prompt["elapsed_ms"] + applied["elapsed_ms"],
                    })
                    if chosen is None or attempt["verified"]:
                        chosen = {
                            "ai": prompt["ai"],
                            "injection": applied["injection"],
                            "candidate": applied["candidate"],
                            "target_scope": scope,
                            "target_scope_check": scope_check,
                            "target_in_scope": in_scope,
                            "elapsed_ms": attempt["elapsed_ms"],
                            "usage": prompt["ai"].get("usage"),
                            "request_id": prompt["ai"].get("request_id"),
                            "model_returned": prompt["ai"].get("model"),
                            "model_requested": prompt["ai"].get("model_requested"),
                            "error": prompt["ai"].get("error"),
                        }
                ai_attempts.append(attempt)
                if attempt["verified"]:
                    break
        record["ai_attempts"] = ai_attempts
        if chosen is None:
            if ai_attempts:
                last = ai_attempts[-1]
                chosen = {
                    "ai": {"status": last.get("status"), "error": last.get("error")},
                    "injection": last.get("injection") or {},
                    "candidate": last.get("candidate") or {"gate": "not_attempted", "poc_status": "not_run"},
                    "target_scope": last.get("target_scope"),
                    "target_scope_check": last.get("target_scope_check") or "not_run",
                    "target_in_scope": bool(last.get("target_in_scope")),
                    "elapsed_ms": last.get("elapsed_ms") or last.get("latency_ms"),
                    "usage": last.get("usage"),
                    "request_id": last.get("request_id"),
                    "model_returned": last.get("model"),
                    "model_requested": last.get("model_requested"),
                    "error": last.get("error"),
                }
            else:
                chosen = {
                    "ai": {"status": "not_attempted", "error": "no target assembly attempt"},
                    "injection": {},
                    "candidate": {"gate": "not_attempted", "poc_status": "not_run"},
                    "target_scope": strict.get("target_scope"),
                    "target_scope_check": strict.get("target_scope_check") or "not_run",
                    "target_in_scope": False,
                    "elapsed_ms": 0,
                    "usage": None,
                    "request_id": None,
                    "model_returned": None,
                    "model_requested": None,
                    "error": None,
                }
        candidate = chosen.get("candidate") or {}
        record["injection"] = chosen.get("injection") or {}
        record["candidate"] = candidate
        record["ai"] = chosen.get("ai") or {"status": "not_attempted"}
        record["ai_target"] = {
            "attempted": bool(ai_attempts) or args.client == "reference",
            "status": record["ai"].get("status") or "not_attempted",
            "error": chosen.get("error") or record["ai"].get("error"),
            "repeats": max(1, int(args.repeats)),
            "verified": bool(candidate.get("gate") == "pass"),
            "checks_summary": {
                "poc_gate": candidate.get("gate"),
                "poc_status": candidate.get("poc_status"),
                "runner": candidate.get("runner"),
                "candidate_sha256": candidate.get("candidate_sha256"),
            },
            "candidate_sha256": candidate.get("candidate_sha256"),
            "provider": provider,
            "model_requested": chosen.get("model_requested") or provider.get("model_requested"),
            "model_returned": chosen.get("model_returned"),
            "seed": args.seed,
            "seed_supported": False,
            "cost": None,
            "cost_basis": "provider API exposes token usage only; no price table configured",
            "usage": chosen.get("usage"),
            "request_id": chosen.get("request_id"),
            "elapsed_ms": chosen.get("elapsed_ms"),
            "target_policy": "target" if args.client != "reference" else "reference",
            "target_scope": chosen.get("target_scope") or strict.get("target_scope"),
            "target_scope_check": chosen.get("target_scope_check") or "not_run",
            "target_in_scope": bool(chosen.get("target_in_scope")),
            "attempts": ai_attempts,
        }
        record["ai_result"] = record["ai_target"]
        record.update({
            "provider": provider,
            "provider_tag": args.provider_tag or None,
            "model": provider.get("model_requested"),
            "seed": args.seed,
            "seed_supported": False,
            "cost": None,
            "cost_basis": "provider API exposes token usage only; no price table configured",
            "elapsed_ms": max(0, int((time.perf_counter() - case_started) * 1000)),
            "target_policy": {
                "whole_image_baseline": baseline_record.get("target_policy") or "whole_image",
                "target_strict_baseline": "target_strict",
                "ai_target": "target" if args.client != "reference" else "reference",
            },
            "target_scope": record["ai_target"]["target_scope"],
            "target_scope_check": record["ai_target"]["target_scope_check"],
            "target_in_scope": record["ai_target"]["target_in_scope"],
        })
        gate_pass = candidate.get("gate") == "pass"
        strict_ok = (
            (not args.target_strict)
            or record["ai_target"]["target_scope_check"] == "passed"
        )
        record["ai_increment"] = bool(not baseline.verified and gate_pass and strict_ok)
        record["contract_level"] = args.contract_level
        record["repeats"] = max(1, int(args.repeats))
        results.append(record)
        print(json.dumps({
            "case": case["id"],
            "baseline": baseline_record["disposition"],
            "baseline_target_strict": strict.get("disposition"),
            "target_strict_matches": strict.get("matches_expected"),
            "ai_status": record["ai_target"]["status"],
            "ai_gate": candidate.get("gate"),
            "ai_target_in_scope": record["ai_target"]["target_in_scope"],
            "increment": record["ai_increment"],
        }, ensure_ascii=False), flush=True)

    target_strict_expected_matches = sum(
        1 for r in results if r["baseline_target_strict"].get("matches_expected")
    )
    target_strict_in_scope = sum(
        1 for r in results if r["baseline_target_strict"].get("target_in_scope")
    )
    summary = {
        "schema_version": 1,
        "provider": args.client,
        "provider_metadata": provider,
        "provider_tag": args.provider_tag or None,
        "seed": args.seed,
        "seed_supported": False,
        "cost": None,
        "cost_basis": "provider API exposes token usage only; no price table configured",
        "cases": results,
        "baseline_verified": sum(1 for r in results if r["baseline"]["verified"]),
        "ai_verified": sum(1 for r in results if r.get("candidate", {}).get("gate") == "pass"),
        "ai_increment": sum(1 for r in results if r["ai_increment"]),
        "baseline_target_aware_verified": sum(
            1 for r in results if r["baseline_target_aware"].get("verified")
        ),
        "baseline_target_strict_analysis_only": sum(
            1 for r in results
            if r["baseline_target_strict"].get("disposition") == "analysis_only"
        ),
        "baseline_target_strict_verified": sum(
            1 for r in results if r["baseline_target_strict"].get("verified")
        ),
        "baseline_target_strict_out_of_scope_actions": sum(
            1 for r in results
            if r["baseline_target_strict"].get("actions")
            and not r["baseline_target_strict"].get("target_in_scope")
        ),
        "baseline_target_strict_expected_matches": target_strict_expected_matches,
        "baseline_target_strict_expected_match_rate": (
            target_strict_expected_matches / len(results) if results else 0.0
        ),
        "baseline_target_strict_target_in_scope": target_strict_in_scope,
        "baseline_target_strict_target_in_scope_rate": (
            target_strict_in_scope / len(results) if results else 0.0
        ),
        "target_strict_enforced": bool(args.target_strict),
        "ai_target_verified": sum(
            1 for r in results if r["ai_target"].get("verified")
        ),
        "ai_target_in_scope": sum(
            1 for r in results if r["ai_target"].get("target_in_scope")
        ),
        "ai_blind_verified": sum(
            1 for r in results if (r.get("ai_blind") or {}).get("verified")
        ),
        "reference_evaluated": sum(
            1 for r in results if (r.get("reference_fix") or {}).get("attempted")
            and (r.get("reference_fix") or {}).get("status") != "source_only"
        ),
        "reference_verified": sum(
            1 for r in results if (r.get("reference_fix") or {}).get("verified") is True
        ),
        "reference_source_only": sum(
            1 for r in results
            if (r.get("reference_fix") or {}).get("status") == "source_only"
        ),
        "elapsed_ms": max(0, int((time.perf_counter() - started_all) * 1000)),
        "note": (
            "baseline is deterministic; AI target assembly is accepted only by "
            "native/qemu PoC+regression. baseline_target_strict calls "
            "repair_any(target=<case target>, require_target=True) and records "
            "the resolved target_scope plus target_in_scope (every produced "
            "action inside the target; empty action lists are not in scope). "
            "baseline_target_aware receives the same target/capacity hint; "
            "ai_blind uses the public AI path without target. "
            "allow_calls only permits direct calls already present in the target function."
        ),
        "evaluation_note": (
            "deterministic baselines run on the host; PoC evaluation and the "
            "unstripped x86-64 target execution run in the Linux guest (Lima) via "
            "the poc/guest runner. Provider prompts/responses are never stored."
        ),
        "contract_level": args.contract_level,
        "repeats": max(1, int(args.repeats)),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + chr(10))
    print(json.dumps({"out": str(out), **{k: summary[k] for k in ("baseline_verified", "ai_verified", "ai_increment")}}, ensure_ascii=False))
    return 0


def _ai_meta_unused() -> dict[str, Any]:
    """Minimal reference-mode AI metadata placeholder (no model was called)."""
    return {
        "schema_version": 1,
        "path": "hard_target_asm",
        "requested": False,
        "called": False,
        "mode": "reference",
        "provider": "reference",
        "model": "reference-assembly",
        "status": "not_attempted",
        "latency_ms": 0,
        "error": None,
        "usage": None,
        "request_id": None,
        "authority": "deterministic_gate",
    }


if __name__ == "__main__":
    raise SystemExit(main())
