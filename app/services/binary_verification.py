"""Structured verification report and deterministic gate for direct ELF repair.

The repair engine produces candidate bytes and an ad-hoc report.  This module
turns that report into the same reviewable packet a human sees, then asks the
existing acceptance rules (``app.domain.acceptance``) for the outcome.  It does
not add a second acceptance authority: every check is derived from engine bytes,
the recorded hashes, the reviewed strict template, or Unicorn runtime evidence.

The output is deliberately JSON-only and free of timestamps/paths.  A stable
``report_sha256`` binds the packet the reviewer saw to the evidence the gate
used.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from app.domain.acceptance import Obligation, decide_attempt_outcome
from app.domain.outcomes import CheckResult, Outcome, ReasonCode
from app.services.ai_adjudication import GateResult
from app.services.repair_matrix import is_known_profile, profile_legacy_required_checks

STRICT_TEMPLATE = Path(__file__).resolve().parents[1] / "data" / "vuln-strict-fixed.elf"
REQUIRED_INPUT_OFFSETS = (0, 1)
SCOPE_STATEMENT = (
    "Direct ELF64 x86-64 bytes; runtime evidence is Unicorn x86-64 emulation "
    "with modeled syscalls, not a host-kernel run. Success is within the stated "
    "scope only."
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _finding_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_dict"):
        return dict(item.to_dict())
    if isinstance(item, Mapping):
        return dict(item)
    return {"detail": str(item)}


def _runtime_of(report: Any) -> dict[str, Any]:
    verification = getattr(report, "verification", None)
    if isinstance(verification, Mapping):
        emulated = verification.get("emulated")
        if isinstance(emulated, Mapping) and emulated:
            return dict(emulated)
    runtime = getattr(report, "runtime", None)
    if isinstance(runtime, Mapping):
        return dict(runtime)
    return {}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _check(
    check_id: str,
    title: str,
    status: CheckResult,
    detail: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "required": required,
        "status": status.value,
        "detail": detail,
    }


def _check_status(checks: list[dict[str, Any]], check_id: str) -> str:
    for item in checks:
        if item["id"] == check_id:
            return str(item["status"])
    return "not_run"


def _limits(report: Any, *, strict: bool) -> list[str]:
    values = [str(item) for item in (getattr(report, "limitations", None) or [])]
    values.append(
        "Runtime evidence is Unicorn x86-64 emulation with modeled syscalls, "
        "not a host-kernel run."
    )
    values.append(
        "Runtime coverage is limited to four input sizes around the capacity; "
        "partial reads and other architectures are not covered."
    )
    values.append("Success is within the stated scope only; this is not a whole-program proof.")
    if strict:
        values.append(
            "Reviewed strict template: over-limit input is rejected and valid "
            "input is echoed exactly for the tested sizes."
        )
    elif str(getattr(report, "mode", "")) == "bounds-only":
        values.append(
            "The immediate read/write length was rewritten; short-read and "
            "disclosure semantics are not claimed."
        )
    return _dedupe(values)


def _claim(report: Any, *, strict: bool) -> str:
    mode = str(getattr(report, "mode", "") or "unsupported")
    if strict:
        return (
            "Over-limit input is rejected and valid input is echoed exactly for "
            "the tested sizes; the candidate matches the reviewed strict template."
        )
    if mode == "bounds-only":
        return (
            "The immediate read/write length is rewritten to the stack capacity; "
            "stack overflow is prevented for the modeled paths."
        )
    if mode == "cave":
        return "A reviewed code cave guards the copied string length."
    return "No supported repair claim."


@dataclass(frozen=True)
class Verification:
    """A reviewable packet plus the deterministic gate derived from it."""

    packet: dict[str, Any]
    gate: GateResult


def build_verification(
    report: Any,
    *,
    original: bytes,
    patched: bytes | None,
) -> Verification:
    """Build the structured report and gate for one engine result.

    ``original`` and ``patched`` are the actual bytes; hashes in ``report`` are
    never trusted on their own.  A mismatch becomes a failed check, not a
    success.
    """
    mode = str(getattr(report, "mode", "") or "unsupported")
    strict = bool(getattr(report, "strict", False)) or mode == "strict"
    capacity = getattr(report, "capacity", None)
    checks: list[dict[str, Any]] = []

    candidate_present = patched is not None and len(patched) > 0
    original_sha = str(getattr(report, "original_sha256", "") or "")
    patched_sha = str(getattr(report, "patched_sha256", "") or "")

    format_ok = (
        str(getattr(report, "format", "")) == "elf64-little"
        and str(getattr(report, "arch", "")) == "x86_64"
        and bool(getattr(report, "supported", False))
    )
    checks.append(_check(
        "format",
        "Input is a supported ELF64 little-endian x86-64 file",
        CheckResult.PASSED if format_ok else CheckResult.FAILED,
        f"format={getattr(report, 'format', '')} arch={getattr(report, 'arch', '')} "
        f"supported={bool(getattr(report, 'supported', False))}",
    ))

    checks.append(_check(
        "candidate.present",
        "A candidate byte sequence was produced",
        CheckResult.PASSED if candidate_present else CheckResult.FAILED,
        f"candidate_bytes={len(patched) if patched is not None else 0}",
    ))

    original_ok = (
        len(original_sha) == 64
        and original_sha == _sha(original)
    )
    checks.append(_check(
        "candidate.identity.original",
        "The report hash matches the input bytes",
        CheckResult.PASSED if original_ok else CheckResult.FAILED,
        "original hash matches input" if original_ok else "original hash does not match input",
    ))

    patched_ok = (
        candidate_present
        and len(patched_sha) == 64
        and patched is not None
        and patched_sha == _sha(patched)
        and patched_sha != original_sha
    )
    checks.append(_check(
        "candidate.identity.patched",
        "The candidate hash matches the produced bytes and differs from the input",
        CheckResult.PASSED if patched_ok else CheckResult.FAILED,
        (
            "candidate hash matches produced bytes"
            if patched_ok
            else "candidate hash mismatch, missing candidate, or unchanged bytes"
        ),
    ))

    template_bytes: bytes | None = None
    if STRICT_TEMPLATE.is_file():
        try:
            template_bytes = STRICT_TEMPLATE.read_bytes()
        except OSError:
            template_bytes = None

    offsets = [int(item) for item in (getattr(report, "offsets", None) or []) if isinstance(item, int)]
    findings = [_finding_dict(item) for item in (getattr(report, "findings", None) or [])]
    if strict:
        patch_ok = (
            candidate_present
            and strict
            and str(getattr(report, "strategy", "")) == "strict-template"
            and template_bytes is not None
            and patched is not None
            and _sha(patched) == _sha(template_bytes)
        )
        patch_detail = (
            "candidate matches the reviewed strict template"
            if patch_ok
            else "candidate is not the reviewed strict template"
        )
    elif mode == "bounds-only":
        patch_ok = bool(offsets) and all(
            0 <= offset and patched is not None and offset + 4 <= len(patched)
            for offset in offsets
        )
        patch_detail = (
            f"immediate offsets={offsets}"
            if patch_ok
            else "no in-range immediate patch offsets were recorded"
        )
    elif mode == "cave":
        patch_ok = (
            candidate_present
            and any(str(item.get("kind")) == "code_cave" for item in findings)
            and patched is not None
            and len(patched) >= len(original)
        )
        patch_detail = "reviewed code cave finding recorded" if patch_ok else "no reviewed code cave finding"
    else:
        patch_ok = False
        patch_detail = f"unsupported mode={mode}"

    checks.append(_check(
        "patch.scope",
        "The patch stays inside the reviewed byte range or template",
        CheckResult.PASSED if patch_ok else CheckResult.FAILED,
        patch_detail,
    ))

    runtime = _runtime_of(report)
    runtime_cases = runtime.get("cases") if isinstance(runtime.get("cases"), list) else []
    runtime_available = bool(runtime.get("available")) and bool(runtime_cases)
    runtime_detail = (
        f"engine={runtime.get('engine')} cases={len(runtime_cases)}"
        if runtime_available
        else f"runtime unavailable: {runtime.get('error') or 'no cases'}"
    )
    checks.append(_check(
        "runtime.available",
        "Runtime emulation evidence is present",
        CheckResult.PASSED if runtime_available else CheckResult.NOT_RUN,
        runtime_detail,
    ))

    expected_sizes: set[int] = set()
    if isinstance(capacity, int) and capacity > 0:
        expected_sizes = {0, 1, capacity, capacity + 1}
    case_by_size: dict[int, dict[str, Any]] = {}
    for item in runtime_cases:
        if isinstance(item, Mapping):
            try:
                case_by_size[int(item.get("input_len"))] = dict(item)
            except (TypeError, ValueError):
                continue
    missing_sizes = sorted(expected_sizes - set(case_by_size))
    case_errors = sorted(
        int(size) for size, item in case_by_size.items() if item.get("error")
    )
    if not runtime_available:
        cases_status = CheckResult.NOT_RUN
        cases_detail = "runtime evidence is not available"
    elif case_errors:
        cases_status = CheckResult.FAILED
        cases_detail = f"runtime errors at input sizes: {case_errors}"
    elif missing_sizes:
        cases_status = CheckResult.NOT_RUN
        cases_detail = f"missing runtime input sizes: {missing_sizes}"
    else:
        cases_status = CheckResult.PASSED
        cases_detail = f"runtime cases={sorted(case_by_size)}"
    checks.append(_check(
        "runtime.cases",
        "Boundary runtime cases are present and error-free",
        cases_status,
        cases_detail,
    ))

    if not runtime_available:
        no_overflow_status = CheckResult.NOT_RUN
        no_overflow_detail = "runtime evidence is not available"
    elif not runtime_cases:
        no_overflow_status = CheckResult.NOT_RUN
        no_overflow_detail = "no runtime cases"
    else:
        bad = [
            int(item.get("input_len"))
            for item in runtime_cases
            if isinstance(item, Mapping) and item.get("stack_sentinel_intact") is not True
        ]
        no_overflow_status = CheckResult.FAILED if bad else CheckResult.PASSED
        no_overflow_detail = (
            f"stack sentinel not intact at input sizes: {sorted(bad)}"
            if bad
            else "stack sentinel intact for every runtime case"
        )
    checks.append(_check(
        "runtime.no_overflow",
        "No runtime case damaged the stack sentinel",
        no_overflow_status,
        no_overflow_detail,
    ))

    if strict:
        if not isinstance(capacity, int) or capacity <= 0:
            boundary_status = CheckResult.NOT_RUN
            boundary_detail = "the stack capacity is unknown"
        elif case_errors:
            boundary_status = CheckResult.FAILED
            boundary_detail = f"runtime errors at input sizes: {case_errors}"
        elif not runtime_available or missing_sizes:
            boundary_status = CheckResult.NOT_RUN
            boundary_detail = "boundary cases are missing"
        else:
            bad: list[str] = []
            for size in (0, 1, capacity):
                case = case_by_size.get(int(size))
                if case is None or case.get("exit_code") != 0 or not isinstance(case.get("stdout_len"), int) or case.get("stdout_len") <= 0:
                    bad.append(f"{size}")
            over = case_by_size.get(int(capacity) + 1) if isinstance(capacity, int) else None
            if over is None or over.get("exit_code") in (0, None) or not isinstance(over.get("stderr_len"), int) or over.get("stderr_len") <= 0:
                bad.append(f"{capacity}+1")
            boundary_status = CheckResult.FAILED if bad else CheckResult.PASSED
            boundary_detail = (
                f"unexpected boundary behaviour at input sizes: {bad}"
                if bad
                else "valid sizes exit 0 with output; over-limit size rejects with stderr"
            )
        checks.append(_check(
            "runtime.boundary_semantics",
            "Strict boundary behaviour matches the reviewed contract",
            boundary_status,
            boundary_detail,
        ))

        template_ok = (
            template_bytes is not None
            and candidate_present
            and patched is not None
            and _sha(patched) == _sha(template_bytes)
            and strict
            and str(getattr(report, "strategy", "")) == "strict-template"
        )
        checks.append(_check(
            "strict.reviewed_template",
            "The candidate is the reviewed strict template",
            CheckResult.PASSED if template_ok else CheckResult.FAILED,
            (
                f"template_sha256={_sha(template_bytes)}"
                if template_ok and template_bytes is not None
                else "candidate does not match the reviewed strict template"
            ),
        ))

    # The legacy quick-repair gate uses the same declared acceptance-model
    # registry as the container-neutral gate.  The profile is fixed by the
    # engine mode (reviewed strict template vs emulated bounds repair); the
    # existing check ids/statuses above are unchanged and these are additive.
    legacy_profile = "strict_template" if strict else "emulated_instruction"
    checks.append(_check(
        "profile.declared",
        "The acceptance evidence profile is declared and known",
        (
            CheckResult.PASSED if is_known_profile(legacy_profile)
            else CheckResult.FAILED
        ),
        f"profile={legacy_profile} source=derived-from-mode",
    ))
    legacy_required = profile_legacy_required_checks(legacy_profile)
    legacy_status = {
        str(item["id"]): str(item["status"]) for item in checks
    }
    legacy_failed = [
        check_id for check_id in legacy_required
        if legacy_status.get(check_id) == CheckResult.FAILED.value
    ]
    legacy_not_passed = [
        check_id for check_id in legacy_required
        if legacy_status.get(check_id, CheckResult.NOT_RUN.value) != CheckResult.PASSED.value
    ]
    if legacy_failed:
        checks.append(_check(
            "profile.required_checks",
            "Every check required by the declared evidence profile passed",
            CheckResult.FAILED,
            f"profile={legacy_profile} failed={legacy_failed} "
            f"missing_or_not_run={[i for i in legacy_not_passed if i not in legacy_failed]}",
        ))
    elif legacy_not_passed:
        checks.append(_check(
            "profile.required_checks",
            "Every check required by the declared evidence profile passed",
            CheckResult.NOT_RUN,
            f"profile={legacy_profile} missing_or_not_run={legacy_not_passed}",
        ))
    else:
        checks.append(_check(
            "profile.required_checks",
            "Every check required by the declared evidence profile passed",
            CheckResult.PASSED,
            f"profile={legacy_profile} checks={len(legacy_required)}",
        ))

    missing = [
        {
            "check_id": item["id"],
            "status": item["status"],
            "reason": item["detail"],
        }
        for item in checks
        if item["required"] and item["status"] != CheckResult.PASSED.value
    ]
    required_checks = sum(1 for item in checks if item["required"])
    required_not_run = sum(
        1
        for item in checks
        if item["required"]
        and item["status"] in {
            CheckResult.NOT_RUN.value,
            CheckResult.UNKNOWN.value,
            CheckResult.TIMED_OUT.value,
        }
    )

    scope = {
        "format": str(getattr(report, "format", "")),
        "arch": str(getattr(report, "arch", "")),
        "mode": mode,
        "strategy": str(getattr(report, "strategy", "")),
        "capacity": capacity,
        "strict": strict,
        "claim": _claim(report, strict=strict),
        "statement": SCOPE_STATEMENT,
    }
    candidate = {
        "present": candidate_present,
        "original_sha256": original_sha,
        "patched_sha256": patched_sha,
        "size_bytes": len(patched) if patched is not None else 0,
        "patched_equals_original": bool(candidate_present and patched_sha == original_sha),
    }
    patch = {
        "mode": mode,
        "strategy": str(getattr(report, "strategy", "")),
        "strict": strict,
        "capacity": capacity,
        "offsets": offsets,
        "findings": findings,
        "template_sha256": _sha(template_bytes) if template_bytes is not None else None,
    }
    runtime_packet = {
        "available": runtime_available,
        "engine": runtime.get("engine"),
        "cases": [dict(item) for item in runtime_cases if isinstance(item, Mapping)],
        "error": runtime.get("error"),
    }
    limitations = _limits(report, strict=strict)

    body = {
        "schema_version": 1,
        "scope": scope,
        "candidate": candidate,
        "patch": patch,
        "runtime": runtime_packet,
        "checks": checks,
        "missing": missing,
        "limitations": limitations,
    }
    report_sha256 = _sha(_canonical(body))

    obligations = [
        Obligation(
            kind=str(item["id"]),
            required=bool(item["required"]),
            result=CheckResult(str(item["status"])),
            detail=str(item["detail"]),
        )
        for item in checks
    ]
    unsupported_reason: ReasonCode | None = None
    unsupported_detail = ""
    if not format_ok:
        unsupported_reason = ReasonCode.UNSUPPORTED_PROFILE
        unsupported_detail = "input is not a supported ELF64 little-endian x86-64 file"
    elif not candidate_present:
        unsupported_reason = ReasonCode.UNSUPPORTED_PROFILE
        last = str((getattr(report, "limitations", None) or [""])[-1])
        unsupported_detail = last or "no supported repair pattern produced a candidate"

    verdict = decide_attempt_outcome(
        obligations=obligations,
        candidate_sha256=patched_sha or None,
        reviewed_scope_sha256=report_sha256,
        unsupported_reason=unsupported_reason,
        unsupported_detail=unsupported_detail,
    )
    success = verdict.outcome is Outcome.SUCCESS_WITHIN_SCOPE
    if success:
        reason = "all_required_checks_passed"
    elif verdict.reason is not None:
        reason = verdict.reason.value
    else:
        reason = verdict.detail or verdict.outcome.value
    gate = GateResult(
        success=success,
        outcome=verdict.outcome.value,
        reason=reason,
        required_checks=required_checks,
        required_not_run=required_not_run,
        evidence_sha256=report_sha256 if success else None,
    )
    packet = {
        **body,
        "report_sha256": report_sha256,
        "gate": asdict(gate),
    }
    return Verification(packet=packet, gate=gate)


def check_statuses(verification: Verification) -> dict[str, str]:
    """Small helper for callers that need the per-check outcome."""
    return {
        str(item["id"]): str(item["status"])
        for item in verification.packet.get("checks", [])
        if isinstance(item, Mapping)
    }


__all__ = [
    "SCOPE_STATEMENT",
    "STRICT_TEMPLATE",
    "Verification",
    "build_verification",
    "check_statuses",
]
