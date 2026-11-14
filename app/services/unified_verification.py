"""Deterministic gate for the container-neutral repair pipeline (v4).

The gate never trusts the engine report on its own: it re-derives hashes from
the actual bytes, requires a successful container reparse, requires at least one
recorded repair action, and requires evidence whose model is *declared* by the
repair matrix.  ``static_only`` candidates are explicitly ``not_verified`` and
must not be surfaced as success.

Evidence models are declared once in
``app.services.repair_matrix.EVIDENCE_PROFILES``; this module only enforces
them.  When a caller does not declare a profile, the declared resolver
``repair_matrix.resolve_profile`` derives the backward-compatible default, and
``profile.declared`` records that the profile was derived rather than declared.

Required checks added by the acceptance-model harmonization (all fail closed):

* ``profile.declared``       - the evidence profile is known.
* ``profile.evidence``       - supplied evidence matches the declared sources
                               (the anti-oracle-mismatch gate).
* ``profile.required_checks``- every check the profile requires exists and passed.
* ``patch.capacity``         - optional legacy compatibility: capacity-check
                               rewrites re-derived from the raw bytes.
* ``patch.rewrite``          - every recorded rewrite action re-derived from the
                               original/candidate bytes.
* ``container.cell``         - the supplied matrix cell matches the container.
* ``runtime.cell_tier``      - the runtime tier is declared for the cell.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from app.services.ai_adjudication import GateResult
from app.services.repair_matrix import (
    REPAIR_CELLS,
    RUNTIME_TIERS,
    is_known_profile,
    profile_evidence_sources,
    profile_required_checks,
    resolve_profile,
    supported_pairs,
)
from app.services.runtime.evidence import RuntimeEvidence

CHECK_PASSED = "passed"
CHECK_FAILED = "failed"
CHECK_NOT_RUN = "not_run"

#: The only runtime tiers that count as execution evidence (``static_only`` is
#: never a verified success).
EXECUTABLE_TIERS = frozenset({"native_run", "emulated_run"})


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


def _hex_at(data: bytes | None, offset: int, size: int) -> str | None:
    if data is None or offset < 0 or size <= 0:
        return None
    chunk = data[offset:offset + size]
    if len(chunk) != size:
        return None
    return chunk.hex()


def _rewrite_check(
    check_id: str,
    title: str,
    actions: list[dict[str, Any]],
    original: bytes,
    candidate: bytes | None,
) -> dict[str, Any]:
    """Re-derive every recorded byte rewrite from the raw original/candidate.

    The engine report is never trusted on its own: the original slice must equal
    the recorded ``before_hex`` and the candidate slice must equal the recorded
    ``after_hex`` for every recorded action.  A tampered, stale or empty action
    list fails closed.
    """
    verified = 0
    sites: list[int] = []
    substitutions: list[str] = []
    problems: list[str] = []
    for index, action in enumerate(actions):
        try:
            offset = int(action.get("offset"))
            size = int(action.get("size"))
        except (TypeError, ValueError):
            problems.append(f"action[{index}] has an invalid offset/size")
            continue
        if isinstance(action.get("offset"), bool) or isinstance(action.get("size"), bool):
            problems.append(f"action[{index}] has an invalid offset/size")
            continue
        before = str(action.get("before_hex") or "").lower()
        after = str(action.get("after_hex") or "").lower()
        if offset < 0 or size <= 0 or len(before) != size * 2 or len(after) != size * 2:
            problems.append(f"action[{index}] has an invalid offset/size/hex shape")
            continue
        original_hex = _hex_at(original, offset, size)
        candidate_hex = _hex_at(candidate, offset, size)
        if original_hex != before:
            problems.append(
                f"action[{index}] original bytes at 0x{offset:x} do not match before_hex"
            )
        if candidate_hex != after:
            problems.append(
                f"action[{index}] candidate bytes at 0x{offset:x} do not match after_hex"
            )
        if original_hex == before and candidate_hex == after:
            verified += 1
        site_va = action.get("site_va")
        if isinstance(site_va, int) and not isinstance(site_va, bool):
            sites.append(site_va)
        bad = action.get("bad_capacity")
        good = action.get("good_capacity")
        if bad and good:
            substitutions.append(f"{bad}->{good}")
    if not actions:
        problems.append("no rewrite action was recorded")
    detail = f"actions={len(actions)} verified={verified}"
    if sites:
        detail += " sites=" + ",".join(hex(site) for site in sites)
    if substitutions:
        detail += " registers=" + ",".join(substitutions)
    if problems:
        detail += "; " + "; ".join(problems[:3])
    return _check(
        check_id,
        title,
        CHECK_FAILED if problems else CHECK_PASSED,
        detail,
    )


def _capacity_actions(capacity: Any) -> list[dict[str, Any]] | None:
    """Normalise a legacy ``capacity`` payload to its rewrite action list."""
    if capacity is None:
        return None
    if isinstance(capacity, dict):
        raw = capacity.get("actions")
    elif isinstance(capacity, list):
        raw = capacity
    else:
        raw = None
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _evidence_profile(
    *,
    profile: str,
    runtime: RuntimeEvidence | None,
    external_poc: dict[str, Any] | None,
    rewrite_actions: list[dict[str, Any]] | None,
    capacity: dict[str, Any] | None,
) -> tuple[str, bool]:
    """Return ``(effective_profile, declared_explicitly)``.

    A caller that does not declare a profile gets the registry's declared
    backward-compatible default (``repair_matrix.resolve_profile``); the derived
    flag keeps that visible in ``profile.declared``.
    """
    declared = str(profile or "").strip()
    if declared:
        return declared, True
    derived = resolve_profile(
        has_runtime=runtime is not None,
        has_external_poc=external_poc is not None,
        has_rewrite_actions=bool(rewrite_actions),
        capacity=capacity is not None,
    )
    return derived, False


def _required_checks_check(
    effective: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Enforce every check id the declared profile requires."""
    required_ids = profile_required_checks(effective)
    if not is_known_profile(effective):
        return _check(
            "profile.required_checks",
            "Every check required by the declared evidence profile passed",
            CHECK_FAILED,
            f"unknown evidence profile {effective!r}",
        )
    by_id = {str(item["id"]): item for item in checks}
    failed = [
        check_id for check_id in required_ids
        if check_id in by_id and by_id[check_id]["status"] == CHECK_FAILED
    ]
    not_passed = [
        check_id for check_id in required_ids
        if check_id not in by_id or by_id[check_id]["status"] != CHECK_PASSED
    ]
    if failed:
        return _check(
            "profile.required_checks",
            "Every check required by the declared evidence profile passed",
            CHECK_FAILED,
            f"profile={effective} failed={failed} missing_or_not_run="
            f"{[item for item in not_passed if item not in failed]}",
        )
    if not_passed:
        return _check(
            "profile.required_checks",
            "Every check required by the declared evidence profile passed",
            CHECK_NOT_RUN,
            f"profile={effective} missing_or_not_run={not_passed}",
        )
    return _check(
        "profile.required_checks",
        "Every check required by the declared evidence profile passed",
        CHECK_PASSED,
        f"profile={effective} checks={len(required_ids)}",
    )


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
    profile: str = "",
    rewrite_actions: list[dict[str, Any]] | None = None,
    cell: dict[str, Any] | None = None,
    capacity: dict[str, Any] | None = None,
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

    # The legacy ``capacity`` payload keeps the reviewed capacity-check action
    # list; when the caller does not pass an explicit ``rewrite_actions`` list
    # the same actions are the declared rewrite evidence.
    capacity_actions = _capacity_actions(capacity)
    effective_rewrite = (
        rewrite_actions if rewrite_actions is not None else capacity_actions
    )
    external_status = ""
    poc_cases: list[dict[str, Any]] = []
    external_available = False
    if external_poc is not None:
        external_status = str(external_poc.get("status") or "not_run")
        poc_cases = [
            case for case in (external_poc.get("poc") or [])
            if isinstance(case, dict)
        ]
        external_available = external_status in {"pass", "fail"}
    effective, declared_explicitly = _evidence_profile(
        profile=profile,
        runtime=runtime,
        external_poc=external_poc,
        rewrite_actions=effective_rewrite,
        capacity=capacity,
    )
    sources = tuple(profile_evidence_sources(effective))

    if runtime is None and external_available and "external_poc" in sources:
        # The declared evidence model for this profile is the external PoC
        # differential; a runner that was unavailable stays not_run (no
        # fabricated runtime evidence).
        external_tier = str(external_poc.get("tier") or "unknown")
        external_runner = str(external_poc.get("runner") or "external-poc")
        tier_ok = external_tier in EXECUTABLE_TIERS
        differential_passed = external_status == "pass"
        checks.append(_check(
            "runtime.evidence", "Runtime evidence exists for the candidate",
            CHECK_PASSED if differential_passed else CHECK_FAILED,
            f"runner={external_runner} tier={external_tier} source=poc_manifest",
        ))
        checks.append(_check(
            "runtime.tier", "Runtime evidence is native or emulated (not static-only)",
            CHECK_PASSED if tier_ok else CHECK_NOT_RUN,
            f"tier={external_tier} runner={external_runner} source=poc_manifest",
        ))
        checks.append(_check(
            "runtime.contract", "All runtime cases stay inside the capacity",
            CHECK_PASSED if differential_passed else CHECK_FAILED,
            f"poc differential status={external_status} tier={external_tier} "
            f"runner={external_runner}",
        ))
        runtime_tier = external_tier if tier_ok else "static_only"
        runtime_verdict = external_status
    elif runtime is None:
        checks.append(_check(
            "runtime.evidence", "Runtime evidence exists for the candidate",
            CHECK_NOT_RUN,
            "no runtime runner was selected"
            + (f" (poc status={external_status})" if external_poc is not None else ""),
        ))
        if external_poc is not None:
            # A supplied-but-unavailable PoC keeps the derived runtime checks
            # not_run rather than absent, so the gate stays inconclusive.
            external_tier = str(external_poc.get("tier") or "unknown")
            checks.append(_check(
                "runtime.tier", "Runtime evidence is native or emulated (not static-only)",
                CHECK_NOT_RUN,
                f"tier={external_tier or 'none'} source=poc_manifest status={external_status}",
            ))
            checks.append(_check(
                "runtime.contract", "All runtime cases stay inside the capacity",
                CHECK_NOT_RUN,
                f"poc differential status={external_status}",
            ))
        runtime_tier = "static_only"
        runtime_verdict = "not_run"
    else:
        tier_ok = runtime.tier in EXECUTABLE_TIERS
        checks.append(_check(
            "runtime.evidence", "Runtime evidence exists for the candidate",
            CHECK_PASSED if runtime.cases else CHECK_NOT_RUN,
            f"tier={runtime.tier} engine={runtime.engine} cases={len(runtime.cases)}",
        ))
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
        regression = [
            case for case in (external_poc.get("regression") or [])
            if isinstance(case, dict)
        ]
        original_cases = [c for c in poc_cases if c.get("executable") == "original"]
        candidate_cases = [c for c in poc_cases if c.get("executable") == "candidate"]

        # A missing runner is unavailable evidence, not a failed differential:
        # keep those checks not_run so the gate stays inconclusive (never a
        # fabricated pass, never a mislabelled rejection).
        def _poc_status(ok: bool) -> str:
            # Without an executed differential (runner unavailable) there is no
            # evidence to claim either way: stay not_run, never FAILED and never
            # a fabricated pass.
            if not external_available:
                return CHECK_NOT_RUN
            return CHECK_PASSED if ok else CHECK_FAILED

        checks.append(_check(
            "poc.native.available",
            "PoC manifest was executed by a native/qemu runner",
            CHECK_PASSED if external_available else CHECK_NOT_RUN,
            f"status={external_status} runner={external_poc.get('runner') or 'none'}",
        ))
        original_fails = bool(original_cases) and all(
            bool(case.get("expected_ok")) for case in original_cases
        )
        checks.append(_check(
            "poc.native.original_failure",
            "The original binary fails the supplied PoC",
            _poc_status(original_fails),
            f"cases={len(original_cases)} status={external_status}",
        ))
        candidate_passes = bool(candidate_cases) and all(
            bool(case.get("expected_ok")) for case in candidate_cases
        )
        checks.append(_check(
            "poc.native.candidate_pass",
            "The candidate passes the supplied PoC",
            _poc_status(candidate_passes),
            f"cases={len(candidate_cases)} status={external_status}",
        ))
        regression_ok = bool(regression) and all(
            bool(case.get("expected_ok")) for case in regression
        )
        no_input = external_poc.get("no_input") is True
        if not external_available:
            regression_status = CHECK_NOT_RUN
            regression_detail = f"cases={len(regression)} status={external_status}"
        elif no_input and bool(poc_cases):
            # Declared no-input model (UAF etc.): the PoC differential is the
            # whole oracle, so an empty regression list is not a failure.
            regression_status = CHECK_PASSED
            regression_detail = (
                f"not_applicable_no_input cases={len(regression)} "
                f"status={external_status}"
            )
        else:
            regression_status = CHECK_PASSED if regression_ok else CHECK_FAILED
            regression_detail = f"cases={len(regression)} status={external_status}"
        checks.append(_check(
            "poc.native.regression",
            "Original and candidate agree on regression inputs",
            regression_status,
            regression_detail,
        ))
        signature = str(external_poc.get("stdout_signature") or "not_run")
        if not external_available:
            signature_status = CHECK_NOT_RUN
        else:
            if signature == "not_run":
                # Backward compatibility for retained evidence from before the
                # explicit field: derive it from the regression observations.
                original_reg = [c for c in regression if c.get("executable") == "original"]
                candidate_reg = [c for c in regression if c.get("executable") == "candidate"]
                if original_reg and len(original_reg) == len(candidate_reg):
                    signature = (
                        "matched"
                        if all(a.get("stdout_hex") == b.get("stdout_hex")
                               for a, b in zip(original_reg, candidate_reg))
                        else "mismatch"
                    )
                else:
                    signature = "not_applicable"
            signature_status = (
                CHECK_PASSED if signature in {"matched", "not_applicable"}
                else CHECK_FAILED
            )
        checks.append(_check(
            "poc.native.stdout_signature",
            "Candidate preserves the original stdout signature on regressions",
            signature_status,
            f"signature={signature}",
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

    # --- declared evidence model (appended so historical check ids/statuses
    # and failure reasons for old callers stay unchanged) -------------------
    profile_known = is_known_profile(effective)
    if declared_explicitly:
        declared_detail = f"profile={effective} source=declared"
    else:
        declared_detail = f"profile={effective} source=derived (no explicit declaration)"
    checks.append(_check(
        "profile.declared",
        "The acceptance evidence profile is declared and known",
        CHECK_PASSED if profile_known else CHECK_FAILED,
        declared_detail,
    ))

    supplied: set[str] = set()
    if runtime is not None and runtime.tier in EXECUTABLE_TIERS:
        supplied.add("runtime")
    if external_available:
        supplied.add("external_poc")
    if effective_rewrite:
        supplied.add("rewrite_actions")
    declared_sources = set(sources)
    missing_sources = sorted(declared_sources - supplied)
    extra_sources = sorted(supplied - declared_sources)
    if not profile_known:
        evidence_status = CHECK_FAILED
        evidence_detail = f"unknown evidence profile {effective!r}"
    elif extra_sources:
        evidence_status = CHECK_FAILED
        evidence_detail = (
            f"profile={effective} supplied undeclared evidence sources="
            f"{extra_sources} (declared={sorted(declared_sources)})"
        )
    elif missing_sources:
        evidence_status = CHECK_NOT_RUN
        evidence_detail = (
            f"profile={effective} declared evidence unavailable="
            f"{missing_sources} (declared={sorted(declared_sources)})"
        )
    else:
        evidence_status = CHECK_PASSED
        evidence_detail = (
            f"profile={effective} sources={sorted(declared_sources)}"
        )
    checks.append(_check(
        "profile.evidence",
        "Supplied evidence matches the declared acceptance evidence sources",
        evidence_status,
        evidence_detail,
    ))

    if capacity is not None:
        checks.append(_rewrite_check(
            "patch.capacity",
            "The reviewed capacity-check rewrite matches the original and "
            "candidate bytes",
            capacity_actions or [],
            original,
            candidate,
        ))
    if effective_rewrite is not None:
        checks.append(_rewrite_check(
            "patch.rewrite",
            "Every recorded rewrite action re-derives from the original and "
            "candidate bytes",
            effective_rewrite,
            original,
            candidate,
        ))
    if cell is not None:
        cell_key = "/".join(
            str(cell.get(key, "")) for key in ("container", "arch", "bits", "endian")
        )
        known_cells = {item.key for item in REPAIR_CELLS}
        cell_ok = bool(
            cell_key in known_cells
            and str(cell.get("container")) == format_name
            and str(cell.get("arch")) == arch
        )
        checks.append(_check(
            "container.cell",
            "The supplied repair cell matches the container and the repair matrix",
            CHECK_PASSED if cell_ok else CHECK_FAILED,
            f"cell={cell_key} container={format_name}/{arch}"
            + ("" if cell_key in known_cells else " not a declared repair cell"),
        ))
    if cell is not None and runtime_tier in RUNTIME_TIERS and runtime_tier != "static_only":
        cell_tiers = tuple(str(item) for item in (cell.get("runtime_tiers") or ()))
        tier_in_cell = runtime_tier in cell_tiers
        checks.append(_check(
            "runtime.cell_tier",
            "The runtime evidence tier is declared for the repair cell",
            CHECK_PASSED if tier_in_cell else CHECK_FAILED,
            f"tier={runtime_tier} cell_tiers={list(cell_tiers)}",
        ))
    checks.append(_required_checks_check(effective, checks))

    failed = [check for check in checks if check["status"] == CHECK_FAILED]
    not_run = [check for check in checks if check["status"] == CHECK_NOT_RUN]
    success = not failed and not not_run
    statement = (
        "Repair is verified within the stated scope: container reparse, "
        "reviewed patch action and evidence from the declared acceptance "
        "profile. This is not a whole-program proof."
    )
    packet = {
        "schema_version": 2,
        "scope": {
            "format": format_name,
            "arch": arch,
            "runtime_tier": runtime_tier,
            "runtime_verdict": runtime_verdict,
            "profile": effective,
            "profile_declared": declared_explicitly,
            "evidence_sources": sorted(declared_sources),
            "statement": statement,
        },
        "checks": checks,
        "actions": actions,
        "runtime": runtime.to_dict() if runtime is not None else None,
    }
    if poc is not None:
        packet["poc"] = poc
    if external_poc is not None:
        packet["poc_native"] = external_poc
    if capacity is not None:
        packet["capacity"] = capacity
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
