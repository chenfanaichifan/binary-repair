#!/usr/bin/env python3
"""Real 12-case provider matrix with target-strict measurement evidence.

For every hard case (``fixtures/hard-cases/cases.json``) this script records:

1. ``baseline_whole_image`` - deterministic pipeline, whole-image policy
   (the explicit ``allow_whole_image=True`` opt-in is used as soon as the
   safe-default policy lands; before that the historical whole-image call is the
   baseline and the record says so);
2. ``baseline_target_strict`` - ``repair_any(target=<case target>,
   require_target=True)`` with the resolved target scope, the re-derived
   ``target_scope_check`` and ``target_in_scope`` (every produced action inside
   the target; an empty action list is not "in scope");
3. ``reference_fix`` - the declared reference fix: assembly references are
   injected into the case target and accepted only by the native/emulated
   PoC+regression runner; C source references have no compiled artifact in
   ``cases.json`` and are recorded honestly as ``source_only``;
4. ``ai_target`` - the real provider target-assembly mode (or the scripted
   reference client with ``--client reference``): model call, injected
   assembly, PoC gate, provider/model/usage/latency/cost fields and the
   target-scope check.

The run is bounded (wall clock and provider-call budget) and stops the AI phase
safely on auth/quota/network errors, recording the partial evidence honestly.
The provider key, prompt and raw model response are never printed or stored.

Artifacts written under ``--out``::

    README.md
    summary.json
    per-case/<case-id>.json
    SHA256SUMS

Example::

    .venv/bin/python scripts/run_provider_matrix.py \
        --out artifacts/provider-matrix-2026-11-14 \
        --client real --repeats 1 --max-seconds 2700 --max-calls 40

Exit code is 0 when the matrix completed (even if the provider was honestly
recorded as unavailable and only deterministic/reference evidence was
produced); 2 on a script/setup failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import run_hard_benchmark as hb  # noqa: E402

CASES_PATH = ROOT / "fixtures" / "hard-cases" / "cases.json"
DEFAULT_MAX_SECONDS = 45 * 60
DEFAULT_MAX_CALLS = 40
COST_BASIS = "provider API exposes token usage only; no price table configured"
ARTIFACT_KIND = "provider_matrix"
SCHEMA_VERSION = 1
#: Provider failures that mean "stop the AI phase, keep deterministic evidence".
FATAL_PROVIDER_ERRORS = frozenset({
    "_ProviderHTTPError", "TimeoutError", "ConnectionError", "httpx.TimeoutException",
    "httpx.TransportError", "OSError",
})


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_cases(case_id: str = "") -> list[dict[str, Any]]:
    """Load cases in cases.json order; ``--case`` accepts a comma-separated list."""
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = list(payload["cases"])
    selected = [item.strip() for item in case_id.split(",") if item.strip()]
    if selected:
        cases = [case for case in cases if case["id"] in selected]
    return cases


class _RecordingClient:
    """Transparent client proxy that remembers the typed error of a call.

    The shared AI call helper catches provider exceptions and only keeps the
    exception class name; the proxy preserves the HTTP status (401/402/429/...)
    for the honest provider-unavailable record without changing any behaviour.
    """

    def __init__(self, client: Any) -> None:
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "calls", 0)
        object.__setattr__(self, "last_error", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_client"), name)

    def chat_json(self, messages: Any, **kwargs: Any) -> Any:
        object.__setattr__(self, "calls", self.calls + 1)
        object.__setattr__(self, "last_error", None)
        try:
            return self._client.chat_json(messages, **kwargs)
        except Exception as exc:  # noqa: BLE001 - re-raised after typing
            object.__setattr__(self, "last_error", {
                "class": type(exc).__name__,
                "status": getattr(exc, "status", None),
            })
            raise


def _classify_provider_error(exc: BaseException) -> dict[str, Any]:
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return {
            "status": "unavailable",
            "error": f"{type(exc).__name__}({status})",
            "error_class": type(exc).__name__,
            "http_status": status,
        }
    return {
        "status": "unavailable",
        "error": type(exc).__name__,
        "error_class": type(exc).__name__,
        "http_status": None,
    }


def _preflight(client: Any) -> dict[str, Any]:
    """One tiny provider call to classify auth/quota/network availability."""
    started = time.perf_counter()
    try:
        raw = client.chat_json(
            [
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": "Return {\"ok\": true}."},
            ],
            max_tokens=8,
            thinking=False,
        )
    except Exception as exc:  # noqa: BLE001 - recorded honestly
        info = _classify_provider_error(exc)
        info.update({
            "ok": False,
            "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
            "model_returned": None,
            "usage": None,
        })
        return info
    usage = getattr(raw, "usage", None)
    return {
        "ok": True,
        "status": "ok",
        "error": None,
        "error_class": None,
        "http_status": None,
        "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
        "model_returned": getattr(raw, "model", None),
        "usage": usage if isinstance(usage, dict) else None,
    }


def _provider_setup(args: argparse.Namespace) -> dict[str, Any]:
    """Build the provider client and non-secret provider metadata.

    Never raises and never fabricates a client: ``client_from_env`` returning
    ``None`` is recorded as ``provider_status="unavailable"``.
    """
    setup: dict[str, Any] = {
        "client": None,
        "recording": None,
        "provider_config": None,
        "provider_status": "not_requested",
        "unavailable_reason": None,
        "preflight": None,
        "calls": 0,
    }
    if args.client == "reference":
        setup["provider_status"] = "reference"
        setup["provider_metadata"] = hb._provider_metadata(None, "reference")
        setup["provider_metadata"].update({
            "status": "reference",
            "provider": "reference",
            "model_requested": "reference-assembly",
            "configured": True,
        })
        return setup
    provider_config = hb._provider_config_metadata()
    setup["provider_config"] = provider_config
    from app.services.assistant_llm import client_from_env

    base_client = client_from_env()
    if base_client is None:
        metadata = hb._provider_metadata(None, "real")
        metadata.update({
            "status": "unavailable",
            "provider": provider_config.get("provider"),
            "configured": bool(provider_config.get("configured")),
            "errors": list(provider_config.get("errors") or []),
            "model_requested": provider_config.get("model"),
        })
        setup.update({
            "provider_metadata": metadata,
            "provider_status": "unavailable",
            "unavailable_reason": "llm_client_not_configured",
        })
        return setup
    recording = _RecordingClient(base_client)
    metadata = hb._provider_metadata(base_client, "real")
    metadata.update({
        "status": "ok",
        "provider": provider_config.get("provider"),
        "configured": bool(provider_config.get("configured")),
        "errors": list(provider_config.get("errors") or []),
        "model_configured": provider_config.get("model"),
        "provider_config": provider_config,
    })
    setup.update({"client": recording, "recording": recording,
                  "provider_metadata": metadata, "provider_status": "ok"})
    if args.preflight:
        check = _preflight(recording)
        setup["preflight"] = check
        setup["calls"] = 1
        if not check.get("ok"):
            setup["provider_status"] = "unavailable"
            setup["unavailable_reason"] = f"provider_error: {check.get('error')}"
            setup["client"] = None
            metadata["status"] = "unavailable"
            metadata["error"] = check.get("error")
    return setup


# ---------------------------------------------------------------------------
# Phase 1: deterministic baselines + reference fix
# ---------------------------------------------------------------------------


def _deterministic_whole_image(
    data: bytes, *, supported: bool,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"verify": True}
    if supported:
        kwargs["allow_whole_image"] = True
    started = time.perf_counter()
    outcome = hb.repair_any(data, **kwargs)
    elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
    record = hb._baseline_record(outcome, elapsed_ms)
    record["allow_whole_image_requested"] = True
    record["allow_whole_image_supported"] = supported
    return record


def _deterministic_target_strict(
    data: bytes, case: dict[str, Any],
) -> dict[str, Any]:
    strict = hb._baseline_target_strict(data, case["target"])
    # cases.json omits the strict expectation when it equals the whole-image
    # baseline expectation; the fallback is therefore the declared baseline.
    expected = (
        case.get("baseline_expected_target_strict")
        or case.get("baseline_expected")
    )
    strict["expected"] = expected
    strict["expected_source"] = (
        "baseline_expected_target_strict"
        if case.get("baseline_expected_target_strict")
        else "baseline_expected (strict field omitted in cases.json)"
    )
    strict["matches_expected"] = strict.get("disposition") == expected
    strict["target_policy"] = "target_strict"
    return strict


def _reference_fix(
    data: bytes, case: dict[str, Any], poc: dict[str, Any],
) -> dict[str, Any]:
    reference = ROOT / case["reference_fix"]
    record: dict[str, Any] = {
        "attempted": True,
        "reference_fix": case["reference_fix"],
        "kind": reference.suffix.lstrip(".") or "unknown",
        "status": "not_attempted",
        "verified": None,
        "reason": None,
    }
    if not reference.is_file():
        record.update({"status": "missing", "reason": "reference fix file is missing"})
        return record
    if reference.suffix != ".S":
        record.update({
            "status": "source_only",
            "reason": (
                "reference fix is source code with no compiled reference artifact "
                "declared in cases.json; it is recorded but not PoC-executed"
            ),
        })
        return record
    assembly = reference.read_text(encoding="utf-8")
    applied = hb._apply_assembly_and_evaluate(data, case, poc, assembly, [])
    scope, scope_check, in_scope = hb._ai_target_scope(
        data, case, applied["injection"],
    )
    candidate = applied["candidate"]
    gate = candidate.get("gate")
    if applied["patched"] is None:
        status = "injection_failed"
    elif gate == "pass":
        status = "verified"
    else:
        status = "gate_fail"
    record.update({
        "status": status,
        "verified": gate == "pass",
        "reason": (applied["injection"] or {}).get("error"),
        "assembly_sha256": _sha_text(assembly),
        "injection": applied["injection"],
        "target_scope": scope,
        "target_scope_check": scope_check,
        "target_in_scope": in_scope,
        "poc_gate": gate,
        "poc_status": candidate.get("poc_status"),
        "runner": candidate.get("runner"),
        "candidate_sha256": candidate.get("candidate_sha256"),
        "elapsed_ms": applied["elapsed_ms"],
    })
    return record


# ---------------------------------------------------------------------------
# Phase 2: provider AI target attempts
# ---------------------------------------------------------------------------


def _ai_target_attempt(
    client: Any,
    data: bytes,
    case: dict[str, Any],
    poc: dict[str, Any],
    *,
    contract_level: str,
    repeat: int,
) -> dict[str, Any]:
    """One real/scripted provider target-mode attempt (model call + PoC gate)."""
    prompt = hb._ai_prompt_attempt(client, data, case, contract_level, False)
    ai = prompt["ai"]
    attempt: dict[str, Any] = {
        "repeat": repeat,
        "attempted": True,
        "status": ai.get("status"),
        "error": ai.get("error"),
        "model_requested": ai.get("model_requested") or getattr(client, "model", None),
        "model_returned": ai.get("model"),
        "model_identity_ok": ai.get("model_identity_ok"),
        "usage": ai.get("usage"),
        "latency_ms": ai.get("latency_ms"),
        "request_id": ai.get("request_id"),
        "provider_calls": 1,
        "seed": None,
        "seed_supported": False,
        "cost": None,
        "cost_basis": COST_BASIS,
        "assembly_returned": prompt["assembly"] is not None,
        "assembly_sha256": (
            _sha_text(prompt["assembly"]) if prompt["assembly"] is not None else None
        ),
        "injection": None,
        "target_scope": None,
        "target_scope_check": "not_run",
        "target_in_scope": False,
        "poc_gate": None,
        "poc_status": None,
        "runner": None,
        "verified": False,
        "candidate_sha256": None,
        "checks_summary": {
            "poc_gate": None,
            "poc_status": None,
            "runner": None,
            "tier": None,
            "verified": False,
        },
        "elapsed_ms": prompt["elapsed_ms"],
    }
    last_error = getattr(client, "last_error", None)
    if isinstance(last_error, dict):
        attempt["provider_error"] = dict(last_error)
    if prompt["assembly"] is not None:
        applied = hb._apply_assembly_and_evaluate(
            data, case, poc, prompt["assembly"], [],
        )
        scope, scope_check, in_scope = hb._ai_target_scope(
            data, case, applied["injection"],
        )
        candidate = applied["candidate"]
        poc_evidence = candidate.get("poc") or {}
        attempt.update({
            "injection": applied["injection"],
            "target_scope": scope,
            "target_scope_check": scope_check,
            "target_in_scope": in_scope,
            "poc_gate": candidate.get("gate"),
            "poc_status": candidate.get("poc_status"),
            "runner": candidate.get("runner"),
            "verified": candidate.get("gate") == "pass",
            "candidate_sha256": candidate.get("candidate_sha256"),
            "elapsed_ms": prompt["elapsed_ms"] + applied["elapsed_ms"],
            "checks_summary": {
                "poc_gate": candidate.get("gate"),
                "poc_status": candidate.get("poc_status"),
                "runner": candidate.get("runner"),
                "tier": poc_evidence.get("tier"),
                "verified": candidate.get("gate") == "pass",
                "candidate_sha256": candidate.get("candidate_sha256"),
                "empty_assembly": not bool(prompt["assembly"].strip()),
            },
        })
    return attempt


def _reference_ai_attempt(
    data: bytes, case: dict[str, Any], poc: dict[str, Any],
) -> dict[str, Any]:
    """Scripted reference 'provider' attempt (no network, no model call)."""
    reference = ROOT / case["reference_fix"]
    attempt: dict[str, Any] = {
        "repeat": 0,
        "attempted": True,
        "status": "reference_source_only",
        "error": None,
        "model_requested": "reference-assembly",
        "model_returned": "reference-assembly",
        "model_identity_ok": True,
        "usage": None,
        "latency_ms": 0,
        "request_id": None,
        "provider_calls": 0,
        "seed": None,
        "seed_supported": False,
        "cost": None,
        "cost_basis": COST_BASIS,
        "assembly_returned": False,
        "assembly_sha256": None,
        "injection": None,
        "target_scope": None,
        "target_scope_check": "not_run",
        "target_in_scope": False,
        "poc_gate": None,
        "poc_status": None,
        "runner": None,
        "verified": False,
        "candidate_sha256": None,
        "checks_summary": {"poc_gate": None, "poc_status": None,
                           "runner": None, "tier": None, "verified": False},
        "elapsed_ms": 0,
    }
    if not reference.is_file() or reference.suffix != ".S":
        return attempt
    assembly = reference.read_text(encoding="utf-8")
    applied = hb._apply_assembly_and_evaluate(data, case, poc, assembly, [])
    scope, scope_check, in_scope = hb._ai_target_scope(
        data, case, applied["injection"],
    )
    candidate = applied["candidate"]
    poc_evidence = candidate.get("poc") or {}
    attempt.update({
        "status": "reference",
        "assembly_returned": True,
        "assembly_sha256": _sha_text(assembly),
        "injection": applied["injection"],
        "target_scope": scope,
        "target_scope_check": scope_check,
        "target_in_scope": in_scope,
        "poc_gate": candidate.get("gate"),
        "poc_status": candidate.get("poc_status"),
        "runner": candidate.get("runner"),
        "verified": candidate.get("gate") == "pass",
        "candidate_sha256": candidate.get("candidate_sha256"),
        "elapsed_ms": applied["elapsed_ms"],
        "checks_summary": {
            "poc_gate": candidate.get("gate"),
            "poc_status": candidate.get("poc_status"),
            "runner": candidate.get("runner"),
            "tier": poc_evidence.get("tier"),
            "verified": candidate.get("gate") == "pass",
            "candidate_sha256": candidate.get("candidate_sha256"),
        },
    })
    return attempt


# ---------------------------------------------------------------------------
# Records / aggregates / artifacts
# ---------------------------------------------------------------------------


def _case_record(
    case: dict[str, Any],
    *,
    provider: dict[str, Any],
    seed: int | None,
    whole_image_supported: bool,
) -> dict[str, Any]:
    data = (ROOT / case["binary"]).read_bytes()
    poc = json.loads((ROOT / case["poc"]).read_text(encoding="utf-8"))
    started = time.perf_counter()
    whole = _deterministic_whole_image(data, supported=whole_image_supported)
    strict = _deterministic_target_strict(data, case)
    reference = _reference_fix(data, case, poc)
    elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "case_id": case["id"],
        "family": case.get("family"),
        "case": case,
        "input_sha256": _sha_bytes(data),
        "recorded_at": _now_iso(),
        "provider": provider,
        "model": provider.get("model_requested"),
        "seed": seed,
        "seed_supported": False,
        "cost": None,
        "cost_basis": COST_BASIS,
        "elapsed_ms": elapsed_ms,
        "target_policy": {
            "whole_image_baseline": whole.get("target_policy") or "whole_image",
            "target_strict_baseline": "target_strict",
            "ai_target": "target",
        },
        "target_scope": strict.get("target_scope"),
        "target_scope_check": strict.get("target_scope_check") or "not_run",
        "target_in_scope": bool(strict.get("target_in_scope")),
        "baseline_whole_image": whole,
        "baseline": whole,  # compatibility alias
        "baseline_target_strict": strict,
        "reference_fix": reference,
        "ai_target": {
            "attempted": False,
            "status": "not_attempted",
            "error": None,
            "repeats": 0,
            "verified": False,
            "checks_summary": {},
            "candidate_sha256": None,
            "provider": provider,
            "model_requested": provider.get("model_requested"),
            "model_returned": None,
            "seed": seed,
            "seed_supported": False,
            "cost": None,
            "cost_basis": COST_BASIS,
            "usage": None,
            "request_id": None,
            "elapsed_ms": None,
            "target_policy": "target",
            "target_scope": strict.get("target_scope"),
            "target_scope_check": strict.get("target_scope_check") or "not_run",
            "target_in_scope": False,
            "attempts": [],
        },
        "inconclusive_reasons": [],
        "limitations": [],
    }
    record["ai_result"] = record["ai_target"]
    return record


def _summarize_ai(
    record: dict[str, Any],
    attempts: list[dict[str, Any]],
    *,
    status: str,
    error: str | None,
    provider: dict[str, Any],
    seed: int | None,
) -> None:
    chosen = None
    for attempt in attempts:
        if attempt.get("verified"):
            chosen = attempt
            break
    if chosen is None and attempts:
        chosen = attempts[-1]
    ai_target = record["ai_target"]
    ai_target.update({
        "attempted": bool(attempts),
        "status": status,
        "error": error,
        "repeats": len(attempts),
        "attempts": attempts,
        "provider": provider,
        "seed": seed,
    })
    if chosen is not None:
        ai_target.update({
            "verified": bool(chosen.get("verified")),
            "checks_summary": dict(chosen.get("checks_summary") or {}),
            "candidate_sha256": chosen.get("candidate_sha256"),
            "model_requested": chosen.get("model_requested"),
            "model_returned": chosen.get("model_returned"),
            "model_identity_ok": chosen.get("model_identity_ok"),
            "usage": chosen.get("usage"),
            "request_id": chosen.get("request_id"),
            "latency_ms": chosen.get("latency_ms"),
            "elapsed_ms": chosen.get("elapsed_ms"),
            "target_scope": chosen.get("target_scope") or ai_target.get("target_scope"),
            "target_scope_check": chosen.get("target_scope_check") or "not_run",
            "target_in_scope": bool(chosen.get("target_in_scope")),
        })
    record["ai_result"] = ai_target
    # Top-level target fields prefer the AI target-mode measurement (the only
    # mode that produces actions for these hard cases) and fall back to the
    # deterministic strict baseline.
    record["target_scope"] = ai_target.get("target_scope") or record.get("target_scope")
    record["target_scope_check"] = ai_target.get("target_scope_check") or "not_run"
    record["target_in_scope"] = bool(ai_target.get("target_in_scope"))


def _record_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    strict = record["baseline_target_strict"]
    if not strict.get("matches_expected"):
        reasons.append(
            "target_strict_expectation_mismatch:"
            f"{strict.get('disposition')}!={strict.get('expected')}"
        )
    whole = record["baseline_whole_image"]
    reasons.append(f"whole_image:{whole.get('disposition')}")
    reference = record["reference_fix"]
    if reference.get("status") == "source_only":
        reasons.append("reference:source_only")
    elif reference.get("status") not in {"verified"}:
        reasons.append(f"reference:{reference.get('status')}")
    ai = record["ai_target"]
    if not ai.get("attempted"):
        reasons.append(f"ai_not_attempted:{ai.get('status')}")
    elif not ai.get("verified"):
        poc_gate = (ai.get("checks_summary") or {}).get("poc_gate")
        reasons.append(
            "ai:" + str(ai.get("status") or "unknown")
            + (f"/{poc_gate}" if poc_gate else "")
        )
    return reasons


def _aggregate(records: list[dict[str, Any]], *, elapsed_ms: int) -> dict[str, Any]:
    cases = len(records)
    strict = [r["baseline_target_strict"] for r in records]
    strict_matches = sum(1 for item in strict if item.get("matches_expected"))
    strict_resolved = sum(1 for item in strict if item.get("target_scope"))
    strict_in_scope = sum(1 for item in strict if item.get("target_in_scope"))
    ai_attempts = sum(
        len(r["ai_target"].get("attempts") or []) for r in records
    )
    ai_called = sum(
        1 for r in records
        for attempt in (r["ai_target"].get("attempts") or [])
        if attempt.get("provider_calls")
    )
    ai_verified = sum(1 for r in records if r["ai_target"].get("verified"))
    ai_in_scope = sum(1 for r in records if r["ai_target"].get("target_in_scope"))
    reference_evaluated = sum(
        1 for r in records
        if r["reference_fix"].get("status") != "source_only"
        and r["reference_fix"].get("status") != "missing"
        and r["reference_fix"].get("attempted")
    )
    reference_verified = sum(
        1 for r in records if r["reference_fix"].get("verified") is True
    )
    reference_source_only = sum(
        1 for r in records if r["reference_fix"].get("status") == "source_only"
    )
    reasons: Counter[str] = Counter()
    for record in records:
        reasons.update(record.get("inconclusive_reasons") or [])
    return {
        "cases": cases,
        "baseline_whole_image_verified": sum(
            1 for r in records if r["baseline_whole_image"].get("verified")
        ),
        "baseline_target_strict_verified": sum(
            1 for item in strict if item.get("verified")
        ),
        "baseline_target_strict_expected_matches": strict_matches,
        "target_strict_pass_rate": (strict_matches / cases) if cases else 0.0,
        "target_scope_resolved": strict_resolved,
        "target_scope_resolved_rate": (strict_resolved / cases) if cases else 0.0,
        "target_in_scope": strict_in_scope,
        "target_in_scope_rate": (strict_in_scope / cases) if cases else 0.0,
        "ai_attempts": ai_attempts,
        "ai_called": ai_called,
        "ai_target_verified": ai_verified,
        "ai_target_verified_rate": (ai_verified / cases) if cases else 0.0,
        "ai_target_in_scope": ai_in_scope,
        "ai_target_in_scope_rate": (ai_in_scope / cases) if cases else 0.0,
        "reference_evaluated": reference_evaluated,
        "reference_verified": reference_verified,
        "reference_source_only": reference_source_only,
        "inconclusive_failure_reasons": dict(sorted(reasons.items())),
        "elapsed_ms": elapsed_ms,
        "cost_total": None,
        "cost_basis": COST_BASIS,
    }


def _case_row(record: dict[str, Any]) -> dict[str, Any]:
    strict = record["baseline_target_strict"]
    return {
        "case_id": record["case_id"],
        "family": record.get("family"),
        "input_sha256": record.get("input_sha256"),
        "baseline_whole_image_disposition": record["baseline_whole_image"].get("disposition"),
        "baseline_target_strict_disposition": strict.get("disposition"),
        "baseline_target_strict_expected": strict.get("expected"),
        "baseline_target_strict_matches_expected": bool(strict.get("matches_expected")),
        "target_scope_resolved": strict.get("target_scope") is not None,
        "target_in_scope": bool(record.get("target_in_scope")),
        "target_scope_check": record.get("target_scope_check"),
        "reference_status": record["reference_fix"].get("status"),
        "reference_verified": record["reference_fix"].get("verified"),
        "ai_status": record["ai_target"].get("status"),
        "ai_verified": bool(record["ai_target"].get("verified")),
        "ai_target_in_scope": bool(record["ai_target"].get("target_in_scope")),
        "ai_candidate_sha256": record["ai_target"].get("candidate_sha256"),
        "cost": record.get("cost"),
        "elapsed_ms": record.get("elapsed_ms"),
        "inconclusive_reasons": list(record.get("inconclusive_reasons") or []),
    }


def _render_readme(summary: dict[str, Any]) -> str:
    provider = summary.get("provider") or {}
    aggregate = summary.get("aggregate") or {}
    lines = [
        "# Provider matrix - 12 hard cases (target-strict measurement)",
        "",
        f"Generated: `{summary.get('generated_at')}`",
        "",
        "## Run",
        "",
        "```",
        str(summary.get("command")),
        "```",
        "",
        f"- provider run mode: `{provider.get('requested')}`",
        f"- provider: `{provider.get('provider')}` / configured model `{provider.get('model_requested')}`",
        f"- model returned by provider: `{provider.get('model_returned')}` (identity_ok={provider.get('model_identity_ok')})",
        f"- provider status: `{summary.get('provider_status')}`"
        + (f" ({summary.get('unavailable_reason')})" if summary.get("unavailable_reason") else ""),
        f"- seed: `{summary.get('seed')}` (seed_supported={summary.get('seed_supported')})",
        f"- cost: `{summary.get('cost', {}).get('total') if isinstance(summary.get('cost'), dict) else None}`"
        f" - {COST_BASIS}",
        f"- repeats per case: `{summary.get('repeats')}` / contract level `{summary.get('contract_level')}`",
        f"- elapsed: `{summary.get('elapsed_ms')}` ms"
        + (f"; provider calls `{summary.get('budget', {}).get('calls_used')}`"
           f" (budget `{summary.get('budget', {}).get('max_calls')}` calls /"
           f" `{summary.get('budget', {}).get('max_seconds')}` s)" if summary.get("budget") else ""),
        "",
        "## Per-case matrix",
        "",
        "| case | whole-image | target-strict | strict expected | target scope | AI status | AI verified | AI in scope | AI sha256 | ref |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summary.get("cases") or []:
        lines.append(
            "| {case_id} | {baseline_whole_image_disposition} | "
            "{baseline_target_strict_disposition} | "
            "{baseline_target_strict_matches_expected} | "
            "{target_scope_resolved} | {ai_status} | {ai_verified} | "
            "{ai_target_in_scope} | {ai_sha} | "
            "{reference_status}/{reference_verified} |".format(
                **{**row, "ai_sha": (row.get("ai_candidate_sha256") or "-")[:12]}
            )
        )
    lines += [
        "",
        "## Aggregates",
        "",
        "| metric | value |",
        "|---|---|",
    ]
    for key in (
        "cases", "baseline_whole_image_verified", "baseline_target_strict_verified",
        "baseline_target_strict_expected_matches", "target_strict_pass_rate",
        "target_scope_resolved", "target_scope_resolved_rate", "target_in_scope",
        "target_in_scope_rate", "ai_target_verified", "ai_target_verified_rate",
        "ai_target_in_scope", "ai_target_in_scope_rate", "reference_evaluated",
        "reference_verified", "reference_source_only",
    ):
        lines.append(f"| {key} | {aggregate.get(key)} |")
    lines += [
        "| elapsed_ms | {} |".format(aggregate.get("elapsed_ms")),
        "| cost_total | {} |".format(aggregate.get("cost_total")),
        "",
        "## Inconclusive / failure reasons",
        "",
        "```json",
        json.dumps(aggregate.get("inconclusive_failure_reasons") or {}, indent=2),
        "```",
        "",
        "## Definitions",
        "",
        "- `baseline_whole_image`: deterministic pipeline run under the whole-image policy "
        "(`allow_whole_image=True` when the safe-default policy is available; historical "
        "whole-image behaviour otherwise).",
        "- `baseline_target_strict`: `repair_any(target=<case target>, require_target=True)`; "
        "records the resolved target scope and whether every produced action is inside it. "
        "The hard cases are deliberately outside the deterministic templates, so the expected "
        "target-strict disposition is `analysis_only` with no actions (empty action lists are "
        "not counted as in scope).",
        "- `target_strict_pass_rate` = cases whose deterministic target-strict disposition "
        "matches `fixtures/hard-cases/cases.json` `baseline_expected_target_strict` "
        "(falling back to `baseline_expected` when that field is omitted), divided by cases.",
        "- `target_in_scope_rate` = deterministic target-strict baselines whose actions all fall "
        "inside the resolved target scope, divided by cases (0.0 when no actions are produced).",
        "- `ai_target`: real provider (or `--client reference` scripted) target-assembly mode; "
        "accepted only by the native/emulated PoC+regression runner. `ai_target_in_scope_rate` "
        "measures how often the injected repair stayed on the declared target function.",
        "- Reference fixes declared as C source have no compiled reference artifact in "
        "`cases.json`; they are recorded as `source_only` and counted separately, never as a pass.",
        "",
        "## Honesty / limitations",
        "",
        "- The provider key, prompts and raw model responses are never stored or printed.",
        "- Cost is not exposed by the provider API; token usage and wall-clock time are recorded "
        "instead and `cost` is `null` (never a fabricated zero).",
        "- The seed is recorded but the shared provider client does not marshal a seed to the API "
        "(`seed_supported=false`).",
        "- PoC/regression execution uses the native/qemu/Lima guest runner; when no runner is "
        "available the PoC evidence is recorded as `unavailable` and is never counted as verified.",
        "- A provider auth/quota/network failure stops the AI phase and is recorded with its typed "
        "error; the deterministic/reference evidence for every case is still produced.",
        "",
    ]
    if summary.get("limitations"):
        lines.append("Run-specific limitations:")
        lines.extend(f"- {item}" for item in summary["limitations"])
        lines.append("")
    return "\n".join(lines)


def _write_artifacts(
    out: Path,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[Path]:
    per_case_dir = out / "per-case"
    per_case_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for record in records:
        path = per_case_dir / f"{record['case_id']}.json"
        path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + chr(10),
            encoding="utf-8",
        )
        written.append(path)
    readme = out / "README.md"
    readme.write_text(_render_readme(summary) + chr(10), encoding="utf-8")
    written.append(readme)
    summary_path = out / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + chr(10),
        encoding="utf-8",
    )
    written.append(summary_path)
    return written


def write_sha256sums(out: Path, files: list[Path]) -> Path:
    lines = []
    for path in sorted(files):
        rel = path.relative_to(out).as_posix()
        lines.append(f"{_sha_bytes(path.read_bytes())}  {rel}")
    target = out / "SHA256SUMS"
    target.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return target


def parse_sha256sums(path: Path) -> dict[str, str]:
    """Parse a sha256sum-format file into ``{relative_path: sha256}``."""
    entries: dict[str, str] = {}
    if not path.is_file():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ValueError(f"malformed SHA256SUMS line: {line!r}")
        digest, name = parts
        entries[name.strip().lstrip("*")] = digest
    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_budget(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "max_seconds": int(args.max_seconds),
        "max_calls": int(args.max_calls),
        "calls_used": 0,
        "seconds_used": 0.0,
        "stopped_early": False,
        "stopped_reason": None,
    }


def _budget_exhausted(budget: dict[str, Any], started: float) -> str | None:
    elapsed = time.monotonic() - started
    budget["seconds_used"] = round(elapsed, 3)
    if elapsed >= float(budget["max_seconds"]):
        return "wall_clock_budget_exhausted"
    if int(budget["calls_used"]) >= int(budget["max_calls"]):
        return "provider_call_budget_exhausted"
    return None


def run_matrix(args: argparse.Namespace) -> int:
    started = time.monotonic()
    cases = _load_cases(args.case)
    if not cases:
        print(json.dumps({"error": "no cases selected"}, ensure_ascii=False))
        return 2
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    budget = _build_budget(args)
    setup = _provider_setup(args)
    client = setup.get("client")
    provider_meta = dict(setup.get("provider_metadata") or {})
    provider_status = str(setup.get("provider_status") or "not_requested")
    unavailable_reason = setup.get("unavailable_reason")
    budget["calls_used"] += int(setup.get("calls") or 0)
    preflight = setup.get("preflight")

    # Snapshot the pipeline capability once so the whole artifact is internally
    # consistent even if the worktree is edited by another teammate mid-run.
    whole_image_supported = hb.repair_any_supports_allow_whole_image()

    # Phase 1: deterministic baselines + reference fixes for every case.
    records: list[dict[str, Any]] = []
    for case in cases:
        try:
            record = _case_record(
                case, provider=provider_meta, seed=args.seed,
                whole_image_supported=whole_image_supported,
            )
        except Exception as exc:  # noqa: BLE001 - record, never crash the matrix
            record = {
                "schema_version": SCHEMA_VERSION,
                "case_id": case["id"],
                "family": case.get("family"),
                "case": case,
                "input_sha256": None,
                "recorded_at": _now_iso(),
                "provider": provider_meta,
                "model": provider_meta.get("model_requested"),
                "seed": args.seed,
                "cost": None,
                "cost_basis": COST_BASIS,
                "error": f"{type(exc).__name__}: {exc}",
                "baseline_target_strict": {"attempted": False, "disposition": "error",
                                           "verified": False, "actions": [],
                                           "target_scope": None, "target_in_scope": False,
                                           "target_scope_check": "failed"},
                "baseline_whole_image": {"attempted": False, "disposition": "error",
                                         "verified": False},
                "reference_fix": {"attempted": False, "status": "error"},
                "ai_target": {"attempted": False, "status": "error",
                              "attempts": [], "verified": False},
                "inconclusive_reasons": ["case_setup_error"],
                "limitations": [f"{type(exc).__name__}: {exc}"],
            }
        records.append(record)

    # Phase 2: provider AI target attempts (bounded; stops safely).
    stop_reason: str | None = (
        None if provider_status in {"ok", "reference"}
        else f"provider_{provider_status}: {unavailable_reason}"
    )
    if provider_status == "reference":
        for record in records:
            case = record["case"]
            data = (ROOT / case["binary"]).read_bytes()
            poc = json.loads((ROOT / case["poc"]).read_text(encoding="utf-8"))
            attempts = [_reference_ai_attempt(data, case, poc)]
            _summarize_ai(
                record, attempts,
                status="reference",
                error=None,
                provider=provider_meta,
                seed=args.seed,
            )
    elif provider_status == "ok" and client is not None:
        repeats = max(1, int(args.repeats))
        for record in records:
            case = record["case"]
            attempts: list[dict[str, Any]] = []
            status = "not_attempted"
            error: str | None = None
            if stop_reason is not None:
                status = "not_attempted"
                error = stop_reason
            else:
                data = (ROOT / case["binary"]).read_bytes()
                poc = json.loads((ROOT / case["poc"]).read_text(encoding="utf-8"))
                for repeat in range(repeats):
                    exhausted = _budget_exhausted(budget, started)
                    if exhausted is not None:
                        stop_reason = exhausted
                        budget["stopped_early"] = True
                        budget["stopped_reason"] = exhausted
                        status = "not_attempted"
                        error = exhausted
                        break
                    attempt = _ai_target_attempt(
                        client, data, case, poc,
                        contract_level=args.contract_level, repeat=repeat,
                    )
                    budget["calls_used"] += 1
                    attempts.append(attempt)
                    last = attempt.get("provider_error") or {}
                    status = str(attempt.get("status") or "error")
                    error = attempt.get("error")
                    if attempt.get("verified"):
                        break
                    if (
                        str(last.get("class") or "") in FATAL_PROVIDER_ERRORS
                        or status in {"error", "unavailable", "identity_mismatch"}
                    ):
                        stop_reason = (
                            "provider_error: "
                            f"{last.get('class') or status}"
                            + (f"({last['status']})" if last.get("status") else "")
                        )
                        budget["stopped_early"] = True
                        budget["stopped_reason"] = stop_reason
                        break
            _summarize_ai(
                record, attempts,
                status=status,
                error=error,
                provider=provider_meta,
                seed=args.seed,
            )
    else:
        for record in records:
            ai_target = record["ai_target"]
            ai_target.update({
                "attempted": False,
                "status": "unavailable",
                "error": unavailable_reason or f"provider_{provider_status}",
                "attempts": [],
                "repeats": 0,
            })
            record["ai_result"] = ai_target

    # Per-case reasons / limitations, then aggregates and artifacts.
    for record in records:
        record["inconclusive_reasons"] = _record_reasons(record)
        if record.get("error"):
            record["limitations"].append(record["error"])
        if provider_status != "ok" and provider_status != "reference":
            record["limitations"].append(
                f"provider {provider_status}: {unavailable_reason}"
            )
        if record["ai_target"].get("status") == "not_attempted" and stop_reason:
            record["limitations"].append(f"AI phase stopped: {stop_reason}")
    served_models = sorted({
        str(record["ai_target"].get("model_returned"))
        for record in records
        if record["ai_target"].get("model_returned")
    })
    attempted_identity = [
        record["ai_target"].get("model_identity_ok")
        for record in records
        if record["ai_target"].get("attempted")
    ]
    if any(value is False for value in attempted_identity):
        model_identity_ok: bool | None = False
    elif attempted_identity and all(value is True for value in attempted_identity):
        model_identity_ok = True
    else:
        model_identity_ok = None
    model_returned = (
        served_models[0] if len(served_models) == 1
        else ("/".join(served_models) if served_models else None)
    )
    if served_models:
        provider_meta["model_returned"] = model_returned
        provider_meta["served_models"] = served_models
        provider_meta["model_identity_ok"] = model_identity_ok
    budget["seconds_used"] = round(time.monotonic() - started, 3)
    if budget["stopped_reason"] is None and stop_reason is not None:
        budget["stopped_reason"] = stop_reason
        budget["stopped_early"] = True
    elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
    aggregate = _aggregate(records, elapsed_ms=elapsed_ms)
    limitations = []
    if provider_status != "ok":
        limitations.append(
            f"provider was not usable for the AI phase: {provider_status} "
            f"({unavailable_reason or 'no reason recorded'}); deterministic and "
            "reference evidence only"
        )
    if not whole_image_supported:
        limitations.append(
            "allow_whole_image was not available in the on-disk pipeline at run "
            "start; the whole-image baseline is the historical whole-image call "
            "and the per-case record says so (allow_whole_image_supported=false)"
        )
    if budget["stopped_early"]:
        limitations.append(
            f"AI phase stopped early: {budget['stopped_reason']}"
        )
    if aggregate["reference_source_only"]:
        limitations.append(
            f"{aggregate['reference_source_only']} C-source reference fixes have "
            "no compiled reference artifact declared in cases.json and were not "
            "PoC-executed (source_only)"
        )
    if provider_status == "ok":
        model_returned = None
        for record in records:
            if record["ai_target"].get("model_returned"):
                model_returned = record["ai_target"]["model_returned"]
                break
        ids = {
            bool(record["ai_target"].get("model_identity_ok"))
            for record in records if record["ai_target"].get("attempted")
        }
        if ids == {False}:
            limitations.append(
                "provider returned a different model than requested "
                f"(model_requested={provider_meta.get('model_requested')!r}, "
                f"model_returned={model_returned!r}); results are recorded as served, "
                "identity check false, and are not excluded"
            )
        elif served_models:
            limitations.append(
                f"provider served model(s) {served_models!r} for requested "
                f"{provider_meta.get('model_requested')!r}; recorded as served"
            )
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": ARTIFACT_KIND,
        "generated_at": _now_iso(),
        "command": " ".join([Path(sys.argv[0]).name, *sys.argv[1:]]),
        "provider": {
            **provider_meta,
            "preflight": preflight,
        },
        "provider_status": provider_status,
        "unavailable_reason": unavailable_reason,
        "provider_tag": args.provider_tag or None,
        "seed": args.seed,
        "seed_supported": False,
        "repeats": max(1, int(args.repeats)),
        "contract_level": args.contract_level,
        "cases_selected": [case["id"] for case in cases],
        "preflight": preflight,
        "cost": {"total": None, "currency": None, "basis": COST_BASIS},
        "cost_basis": COST_BASIS,
        "elapsed_ms": elapsed_ms,
        "budget": budget,
        "capabilities": {
            "allow_whole_image": bool(whole_image_supported),
            "whole_image_baseline_note": (
                "explicit allow_whole_image opt-in"
                if whole_image_supported
                else "explicit allow_whole_image not on disk at run start; "
                     "historical whole-image call used and recorded"
            ),
        },
        "target_policy": {
            "whole_image_baseline": "whole_image",
            "target_strict_baseline": "target_strict",
            "ai_target": "target" if args.client == "real" else "reference",
        },
        "aggregate": aggregate,
        # Top-level aliases (authoritative values; see aggregate for the full set).
        "target_strict_pass_rate": aggregate["target_strict_pass_rate"],
        "target_in_scope_rate": aggregate["target_in_scope_rate"],
        "ai_target_verified_rate": aggregate["ai_target_verified_rate"],
        "cases": [_case_row(record) for record in records],
        "limitations": limitations,
        "notes": [
            "cost is null because the provider API exposes token usage but no price "
            "table is configured; never a fabricated zero",
            "the seed is recorded but not marshalled by the shared provider client",
            "provider key/prompt/raw response are never stored",
            "deterministic baselines run on the host; PoC/regression execution goes "
            "through the native/qemu/Lima guest runner",
        ],
    }
    files = _write_artifacts(out, summary, records)
    sha_path = write_sha256sums(out, files)
    print(json.dumps({
        "out": str(out),
        "provider_status": provider_status,
        "aggregate": {k: aggregate[k] for k in (
            "cases", "target_strict_pass_rate", "target_in_scope_rate",
            "ai_target_verified", "ai_target_verified_rate",
            "reference_verified", "reference_source_only",
        )},
        "sha256sums": str(sha_path),
        "elapsed_ms": elapsed_ms,
    }, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Real 12-case provider matrix with target-strict measurement.",
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--client", choices=("real", "reference"), default="real")
    ap.add_argument("--case", default="")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--contract-level", choices=("full", "generic", "none"), default="full")
    ap.add_argument("--max-seconds", type=int, default=DEFAULT_MAX_SECONDS)
    ap.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    ap.add_argument("--preflight", dest="preflight", action="store_true", default=True)
    ap.add_argument("--no-preflight", dest="preflight", action="store_false")
    ap.add_argument("--provider-tag", default="")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    if args.repeats < 1:
        args.repeats = 1
    if args.max_seconds < 1 or args.max_calls < 1:
        print(json.dumps({"error": "max-seconds/max-calls must be positive"}, ensure_ascii=False))
        return 2
    return run_matrix(args)


if __name__ == "__main__":
    raise SystemExit(main())
