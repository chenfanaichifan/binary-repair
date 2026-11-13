"""Deterministic gate for the container-neutral repair pipeline (v4).

The gate never trusts the engine report on its own: it re-derives hashes from
the actual bytes, requires a successful container reparse, requires at least one
recorded repair action, and requires runtime evidence whose tier is
``native_run`` or ``emulated_run``.  ``static_only`` candidates are explicitly
``not_verified`` and must not be surfaced as success.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from app.services.ai_adjudication import GateResult
from app.services.repair_matrix import supported_pairs
from app.services.runtime.evidence import RuntimeEvidence

CHECK_PASSED = "passed"
CHECK_FAILED = "failed"
CHECK_NOT_RUN = "not_run"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class UnifiedVerification:
    packet: dict[str, Any]
    gate: GateResult


def _check(check_id: str, title: str, status: str, detail: str) -> dict[str, Any]:
    return {"id": check_id, "title": title, "status": status,
            "required": True, "detail": detail}


def build(
    *,
    format_name: str,
    arch: str,
    original: bytes,
    candidate: bytes | None,
    actions: list[dict[str, Any]],
    runtime: RuntimeEvidence | None,
    reparse_ok: bool,
    original_sha256: str,
    patched_sha256: str,
    poc: dict[str, Any] | None = None,
    external_poc: dict[str, Any] | None = None,
) -> UnifiedVerification:
    checks: list[dict[str, Any]] = []
    supported = (format_name, arch) in supported_pairs()
    checks.append(_check(
        "format", "Container and architecture are in the repair matrix",
        CHECK_PASSED if supported else CHECK_FAILED,
        f"{format_name}/{arch}",
    ))
    present = candidate is not None and len(candidate) > 0
    checks.append(_check(
        "candidate.present", "A repaired candidate was produced",
        CHECK_PASSED if present else CHECK_FAILED,
        f"candidate_bytes={len(candidate) if candidate else 0}",
    ))
    original_ok = original_sha256 == _sha(original)
    checks.append(_check(
        "candidate.identity.original", "The report hash matches the input bytes",
        CHECK_PASSED if original_ok else CHECK_FAILED,
        "hash matches input" if original_ok else "hash mismatch",
    ))
    patched_ok = bool(
        present and candidate is not None
        and patched_sha256 == _sha(candidate)
        and patched_sha256 != original_sha256
    )
    checks.append(_check(
        "candidate.identity.patched",
        "The candidate hash matches the produced bytes and differs from the input",
        CHECK_PASSED if patched_ok else CHECK_FAILED,
        "candidate hash matches produced bytes" if patched_ok else "hash mismatch or unchanged",
    ))
    checks.append(_check(
        "container.reparse", "The patched candidate re-parses as the same container",
        CHECK_PASSED if reparse_ok else CHECK_FAILED,
        "reparse ok" if reparse_ok else "reparse failed",
    ))
    checks.append(_check(
        "repair.action", "At least one repair action was applied",
        CHECK_PASSED if actions else CHECK_FAILED,
        f"actions={len(actions)}",
    ))
    if runtime is None:
        checks.append(_check(
            "runtime.evidence", "Runtime evidence exists for the candidate",
            CHECK_NOT_RUN, "no runtime runner was selected",
        ))
        runtime_tier = "static_only"
        runtime_verdict = "not_run"
    else:
        tier_ok = runtime.tier in {"native_run", "emulated_run"}
        checks.append(_check(
            "runtime.tier", "Runtime evidence is native or emulated (not static-only)",
            CHECK_PASSED if tier_ok else CHECK_NOT_RUN,
            f"tier={runtime.tier} engine={runtime.engine}",
        ))
        checks.append(_check(
            "runtime.contract", "All runtime cases stay inside the capacity",
            CHECK_PASSED if runtime.verdict == "pass" else CHECK_FAILED,
            f"verdict={runtime.verdict} cases={len(runtime.cases)}",
        ))
        runtime_tier = runtime.tier
        runtime_verdict = runtime.verdict

    if external_poc is not None:
        external_status = str(external_poc.get("status") or "not_run")
        poc_cases = [
            case for case in (external_poc.get("poc") or [])
            if isinstance(case, dict)
        ]
        regression = [
            case for case in (external_poc.get("regression") or [])
            if isinstance(case, dict)
        ]
        original_cases = [c for c in poc_cases if c.get("executable") == "original"]
        candidate_cases = [c for c in poc_cases if c.get("executable") == "candidate"]
        available = external_status in {"pass", "fail"}
        checks.append(_check(
            "poc.native.available",
            "PoC manifest was executed by a native/qemu runner",
            CHECK_PASSED if available else CHECK_NOT_RUN,
            f"status={external_status} runner={external_poc.get('runner') or 'none'}",
        ))
        original_fails = bool(original_cases) and all(
            bool(case.get("expected_ok")) for case in original_cases
        )
        checks.append(_check(
            "poc.native.original_failure",
            "The original binary fails the supplied PoC",
            CHECK_PASSED if original_fails else CHECK_FAILED,
            f"cases={len(original_cases)}",
        ))
        candidate_passes = bool(candidate_cases) and all(
            bool(case.get("expected_ok")) for case in candidate_cases
        )
        checks.append(_check(
            "poc.native.candidate_pass",
            "The candidate passes the supplied PoC",
            CHECK_PASSED if candidate_passes else CHECK_FAILED,
            f"cases={len(candidate_cases)}",
        ))
        regression_ok = bool(regression) and all(
            bool(case.get("expected_ok")) for case in regression
        )
        checks.append(_check(
            "poc.native.regression",
            "Original and candidate agree on regression inputs",
            CHECK_PASSED if regression_ok else CHECK_FAILED,
            f"cases={len(regression)}",
        ))

    if poc is not None:
        original_verdict = str(poc.get("original_verdict") or "not_run")
        candidate_verdict = str(poc.get("candidate_verdict") or "not_run")
        inputs = poc.get("inputs") or []
        original_fails = original_verdict == "fail" and bool(inputs)
        candidate_passes = candidate_verdict == "pass"
        checks.append(_check(
            "poc.original_fails",
            "The original binary fails the PoC/reproduction cases",
            CHECK_PASSED if original_fails else CHECK_FAILED,
            f"original_verdict={original_verdict} inputs={len(inputs)}",
        ))
        checks.append(_check(
            "poc.candidate_passes",
            "The repaired candidate passes the same PoC/reproduction cases",
            CHECK_PASSED if candidate_passes else CHECK_FAILED,
            f"candidate_verdict={candidate_verdict}",
        ))

    failed = [check for check in checks if check["status"] == CHECK_FAILED]
    not_run = [check for check in checks if check["status"] == CHECK_NOT_RUN]
    success = not failed and not not_run
    packet = {
        "schema_version": 2,
        "scope": {
            "format": format_name,
            "arch": arch,
            "runtime_tier": runtime_tier,
            "runtime_verdict": runtime_verdict,
            "statement": (
                "Repair is verified within the stated scope: container reparse, "
                "reviewed patch action and native/emulated runtime cases. "
                "This is not a whole-program proof."
            ),
        },
        "checks": checks,
        "actions": actions,
        "runtime": runtime.to_dict() if runtime is not None else None,
    }
    if poc is not None:
        packet["poc"] = poc
    if external_poc is not None:
        packet["poc_native"] = external_poc
    if success:
        outcome = "success_within_scope"
    elif failed:
        outcome = "rejected"
    else:
        outcome = "inconclusive"
    packet["report_sha256"] = hashlib.sha256(_canonical(packet)).hexdigest()
    gate = GateResult(
        success=success,
        outcome=outcome,
        reason="" if success else (failed[0]["detail"] if failed else "runtime evidence incomplete"),
        required_checks=len(checks),
        required_not_run=len(not_run),
        evidence_sha256=packet["report_sha256"],
    )
    return UnifiedVerification(packet=packet, gate=gate)


def gate_dict(verification: UnifiedVerification) -> dict[str, Any]:
    return asdict(verification.gate)
