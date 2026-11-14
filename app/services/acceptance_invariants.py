"""Acceptance invariant engine.

Machine-checkable invariants over repair packets / reports and over the
committed real-guest acceptance evidence.  The engine is deliberately
fail-closed: anything a reviewer would have to trust by prose is either measured
here or reported as an explicit violation/limitation.

Invariants (never hard-coded per case; derived from the packet/report contents):

1. a *verified* result has only passed required checks (no failed/not_run),
   a candidate sha, an evidence sha and a verified disposition;
2. a *rejected* result carries a reason or a failed check;
3. a *not_run* / unavailable PoC check cannot be verified or downloadable;
4. an inconclusive / analysis_only / unsupported result is never verified or
   downloadable (safe default included);
5. a declared target scope requires the ``patch.target_scope`` check and every
   action carrying ``site_va`` inside ``[va, end)``; a target-scoped verified
   result requires non-empty actions;
6. ``scope.target_policy`` values are one of ``target_scoped`` /
   ``whole_image`` / ``analysis_only``; analysis_only never verifies/downloads
   and whole_image/analysis_only never claim target identity;
7. rewrite actions are well formed and a verified result carries a passed
   ``patch.rewrite`` / ``patch.capacity`` check when rewrite actions exist;
8. manifest-bearing evidence is validated by the unified evidence-profile
   packets, never by legacy quick-gate check ids;
9. a downloadable result is a verified deterministic candidate whose required
   checks all passed.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = 1

TARGET_POLICIES = ("target_scoped", "whole_image", "analysis_only")
VERIFIED_DISPOSITIONS = ("verified_patch", "verified", "patched")
NON_DOWNLOAD_DISPOSITIONS = ("analysis_only", "not_verified", "unsupported",
                             "invalid", "rejected")
LEGACY_CHECK_PREFIXES = (
    "strict.",
    "patch.scope",
    "runtime.available",
    "runtime.cases",
    "runtime.no_overflow",
    "runtime.boundary_semantics",
)
UNIFIED_CHECK_PREFIXES = (
    "profile.",
    "poc.native.",
    "patch.target_scope",
    "patch.rewrite",
    "patch.capacity",
    "container.cell",
    "runtime.cell_tier",
    "runtime.scope",
)
REWRITE_REQUIRED_FIELDS = ("offset", "size", "before_hex", "after_hex")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            result = value.to_dict()
            if isinstance(result, dict):
                return result
        except Exception:  # noqa: BLE001 - target object is untrusted
            return {}
    if hasattr(value, "__dict__"):
        return {
            key: item for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _normalize(report_or_packet: Any) -> dict[str, Any]:
    """Flatten a report/report-dict/packet-dict into one invariant view."""
    report = _as_dict(report_or_packet)
    verification = _as_dict(report.get("verification"))
    packet = _as_dict(report.get("packet")) or _as_dict(
        verification.get("packet")) or {}
    gate = _as_dict(verification.get("gate")) or _as_dict(report.get("gate")) \
        or _as_dict(packet.get("gate"))
    scope = _as_dict(packet.get("scope")) or _as_dict(report.get("scope")) \
        or _as_dict(verification.get("scope"))
    universal = _as_dict(report.get("universal"))
    checks = [_as_dict(item) for item in (
        _as_list(packet.get("checks")) or _as_list(report.get("checks")))]
    actions = [_as_dict(item) for item in (
        _as_list(report.get("actions")) or _as_list(packet.get("actions")))]
    rewrite_actions = [
        _as_dict(item) for item in (
            _as_list(report.get("rewrite_actions"))
            or _as_list(packet.get("rewrite_actions"))
            or _as_list(packet.get("patch_actions")))
    ]
    decision = _as_dict(report.get("decision"))
    checks_provided = bool(packet.get("checks")) or bool(report.get("checks"))
    if not checks_provided:
        # Flattened acceptance summary records carry failed/not_run check id
        # lists and a target_scope_check status instead of a full check list.
        for failed_id in _as_list(report.get("checks_failed")):
            checks.append({"id": str(failed_id), "status": "failed",
                           "required": True, "summary_record": True})
        for not_run_id in _as_list(report.get("checks_not_run")):
            checks.append({"id": str(not_run_id), "status": "not_run",
                           "required": True, "summary_record": True})
        target_scope_check = str(report.get("target_scope_check", "") or "")
        if target_scope_check:
            checks.append({"id": "patch.target_scope",
                           "status": target_scope_check, "required": True,
                           "summary_record": True})
    poc = _as_dict(report.get("poc")) or _as_dict(packet.get("poc"))
    target_scope = (_as_dict(report.get("target_scope"))
                    or _as_dict(packet.get("target_scope"))
                    or _as_dict(scope.get("target_scope"))
                    or _as_dict(scope.get("target")))
    target_policy = str(
        report.get("target_policy")
        or packet.get("target_policy")
        or scope.get("target_policy")
        or universal.get("target_policy")
        or ""
    )
    disposition = str(report.get("disposition")
                      or packet.get("disposition")
                      or verification.get("disposition")
                      or "")
    verified: bool | None
    if "verified" in report and report.get("verified") is not None:
        verified = bool(report.get("verified"))
    elif "verified" in packet and packet.get("verified") is not None:
        verified = bool(packet.get("verified"))
    elif "success" in decision:
        verified = bool(decision.get("success"))
    elif isinstance(report.get("ok"), bool):
        verified = bool(report.get("ok"))
    elif "success" in gate:
        verified = bool(gate.get("success"))
    else:
        verified = None if not checks else all(
            str(check.get("status")) == "passed" for check in checks
        )
    download_allowed = (
        report.get("download_allowed")
        if "download_allowed" in report
        else packet.get("download_allowed")
    )
    gate_outcome = str(report.get("gate_outcome")
                       or decision.get("gate_outcome")
                       or gate.get("outcome")
                       or packet.get("gate_outcome")
                       or "")
    gate_success = (decision.get("success") if "success" in decision
                    else gate.get("success") if "success" in gate else None)
    profile = str(report.get("profile") or packet.get("profile")
                  or scope.get("profile") or "")
    candidate_sha = str(
        report.get("candidate_sha256")
        or report.get("patched_sha256")
        or packet.get("candidate_sha256")
        or packet.get("patched_sha256")
        or ""
    )
    evidence_sha = str(
        report.get("evidence_sha256")
        or decision.get("evidence_sha256")
        or packet.get("evidence_sha256")
        or packet.get("report_sha256")
        or gate.get("evidence_sha256")
        or ""
    )
    reason = str(report.get("error") or report.get("reason")
                 or decision.get("reason") or gate.get("reason") or "")
    poc_status = str(report.get("poc_status")
                     or (poc.get("status") if poc else "")
                     or "")
    with_manifest = bool(report.get("with_manifest")) or bool(poc) or bool(
        poc_status)
    return {
        "report": report,
        "packet": packet,
        "gate": gate,
        "scope": scope,
        "universal": universal,
        "checks": checks,
        "actions": actions,
        "rewrite_actions": rewrite_actions,
        "target_scope": target_scope,
        "target_policy": target_policy,
        "disposition": disposition,
        "verified": verified,
        "download_allowed": bool(download_allowed) if download_allowed is not None else False,
        "download_declared": download_allowed is not None,
        "gate_outcome": gate_outcome,
        "gate_success": gate_success,
        "profile": profile,
        "candidate_sha": candidate_sha,
        "evidence_sha": evidence_sha,
        "reason": reason,
        "poc_status": poc_status,
        "with_manifest": with_manifest,
        "summary_only": not checks_provided and not verification
                        and not _as_dict(packet.get("scope")),
        "checks_total": len(checks),
        "identity": str(report.get("case") or report.get("probe_id")
                        or report.get("fixture") or report.get("id") or ""),
    }


def _check_status(check: dict[str, Any]) -> str:
    return str(check.get("status", "") or "").strip().lower()


def _required(check: dict[str, Any]) -> bool:
    return bool(check.get("required", True))


def _check_ids(view: dict[str, Any]) -> set[str]:
    return {str(check.get("id", "")) for check in view["checks"]}


def _legacy_check_ids(view: dict[str, Any]) -> list[str]:
    return sorted(
        check_id for check_id in _check_ids(view)
        if any(check_id.startswith(prefix) for prefix in LEGACY_CHECK_PREFIXES)
    )


def _unified_check_ids(view: dict[str, Any]) -> list[str]:
    return sorted(
        check_id for check_id in _check_ids(view)
        if any(check_id.startswith(prefix) for prefix in UNIFIED_CHECK_PREFIXES)
    )


def _profile_required_checks(profile: str) -> list[str]:
    if not profile:
        return []
    try:
        from app.services.repair_matrix import EVIDENCE_PROFILES
    except Exception:  # noqa: BLE001 - mid-flight module: invariant is skipped
        return []
    entry = _as_dict(EVIDENCE_PROFILES.get(profile))
    return [str(item) for item in _as_list(entry.get("required_checks"))]


def check_packet(report_or_packet: Any) -> dict[str, Any]:
    """Check the packet/report acceptance invariants (fail closed)."""
    view = _normalize(report_or_packet)
    violations: list[str] = []
    limitations: list[str] = []
    summary_only = bool(view.get("summary_only"))
    identity = view["identity"] or "(unnamed packet)"
    checks = view["checks"]
    failed = [check for check in checks if _check_status(check) == "failed"]
    not_run = [check for check in checks if _check_status(check) in {"not_run",
                                                                     "skipped",
                                                                     "unavailable"}]
    required_failed = [check for check in failed if _required(check)]
    required_not_run = [check for check in not_run if _required(check)]
    verified = view["verified"]
    disposition = view["disposition"]
    gate_outcome = view["gate_outcome"]
    policy = view["target_policy"]
    ids = _check_ids(view)

    # 1. verified => passed required checks + candidate/evidence sha.
    if verified is True:
        if required_failed:
            violations.append(
                "verified packet has failed required checks: "
                f"{[str(check.get('id')) for check in required_failed]}")
        if required_not_run:
            violations.append(
                "verified packet has not_run required checks: "
                f"{[str(check.get('id')) for check in required_not_run]}")
        if not view["candidate_sha"] and not summary_only:
            violations.append("verified packet is missing a candidate sha256")
        if not view["evidence_sha"]:
            if summary_only:
                limitations.append(
                    "summary acceptance record has no evidence sha256 to "
                    "validate (packet-level capture required for release)")
            else:
                violations.append("verified packet is missing an evidence sha256")
        if disposition and disposition not in VERIFIED_DISPOSITIONS:
            violations.append(
                f"verified packet has non-verified disposition {disposition!r}")
        if view["gate_success"] is False:
            violations.append(
                "verified packet has gate.success=False")

    # 2. rejected => reason or failed check.
    if disposition == "rejected" or gate_outcome == "rejected":
        if not view["reason"] and not failed:
            violations.append(
                "rejected result has neither an explicit reason nor a failed "
                "check")

    # 3. not_run / unavailable PoC => never verified/downloadable.
    if not_run or view["poc_status"] in {"not_run", "unavailable"}:
        if verified is True:
            violations.append(
                "packet verified although a required check/PoC is not_run or "
                "unavailable")
        if view["download_allowed"]:
            violations.append(
                "packet allows download although a required check/PoC is "
                "not_run or unavailable")

    # 4. non-verified dispositions are never verified/downloadable.
    if disposition in NON_DOWNLOAD_DISPOSITIONS:
        if verified is True:
            violations.append(
                f"disposition {disposition!r} cannot be verified")
        if view["download_allowed"]:
            violations.append(
                f"disposition {disposition!r} cannot allow download")
    if gate_outcome in {"inconclusive", "rejected"}:
        if verified is True:
            violations.append(
                f"gate outcome {gate_outcome!r} cannot be verified")
        if view["download_allowed"]:
            violations.append(
                f"gate outcome {gate_outcome!r} cannot allow download")

    # 5. target policies and target identity.
    if policy and policy not in TARGET_POLICIES:
        violations.append(
            f"scope.target_policy {policy!r} is not one of {TARGET_POLICIES}")
    target_check_status = None
    for check in checks:
        if str(check.get("id", "")) == "patch.target_scope":
            target_check_status = _check_status(check)
    if policy in {"analysis_only", "whole_image"}:
        if target_check_status == "passed":
            violations.append(
                f"target_policy={policy} packet claims target identity via a "
                "passed patch.target_scope check")
        if policy == "analysis_only" and verified is True:
            violations.append(
                "target_policy=analysis_only packet cannot be verified")
        if policy == "analysis_only" and view["download_allowed"]:
            violations.append(
                "target_policy=analysis_only packet cannot allow download")
    target_scope = view["target_scope"]
    if target_scope:
        start = _int_or_none(target_scope.get("va"))
        end = _int_or_none(target_scope.get("end"))
        if start is None or end is None or end <= start:
            violations.append(
                "declared target_scope is malformed (needs integer va < end)")
        if target_check_status != "passed" and (
                (policy == "target_scoped") or verified is True):
            violations.append(
                "declared target_scope requires a passed patch.target_scope "
                f"check (got {target_check_status!r})")
        if (policy == "target_scoped" and verified is True
                and not view["actions"] and not summary_only):
            violations.append(
                "target-scoped verified packet has no measured patch actions")
        if summary_only and verified is True and not view["actions"]:
            limitations.append(
                "summary acceptance record has no action site_va list; "
                "in-scope ownership was validated from target_scope_check only")
        if start is not None and end is not None:
            for index, action in enumerate(view["actions"]):
                site = _int_or_none(action.get("site_va"))
                if site is None:
                    violations.append(
                        f"target-scoped action[{index}] has no numeric site_va")
                    continue
                if not (start <= site < end):
                    violations.append(
                        f"action[{index}] site_va={hex(site)} is outside the "
                        f"declared target scope [{hex(start)}, {hex(end)})")
    elif target_check_status == "passed":
        violations.append(
            "packet claims a passed patch.target_scope without a declared "
            "target scope")
    elif policy == "target_scoped":
        violations.append(
            "target_policy=target_scoped packet has no declared target scope")

    # 6. rewrite actions are well formed and gate-checked.
    if view["rewrite_actions"]:
        for index, action in enumerate(view["rewrite_actions"]):
            missing = [field for field in REWRITE_REQUIRED_FIELDS
                       if action.get(field) in (None, "")]
            if missing:
                violations.append(
                    f"rewrite action[{index}] is missing fields {missing}")
                continue
            offset = _int_or_none(action.get("offset"))
            size = _int_or_none(action.get("size"))
            if offset is None or offset < 0 or size is None or size <= 0:
                violations.append(
                    f"rewrite action[{index}] has invalid offset/size")
            before = str(action.get("before_hex", ""))
            after = str(action.get("after_hex", ""))
            if not re.fullmatch(r"[0-9a-fA-F]+", before) or len(before) % 2:
                violations.append(
                    f"rewrite action[{index}] before_hex is not hex bytes")
            if not re.fullmatch(r"[0-9a-fA-F]+", after) or len(after) % 2:
                violations.append(
                    f"rewrite action[{index}] after_hex is not hex bytes")
            if before and after and len(before) != len(after):
                violations.append(
                    f"rewrite action[{index}] before/after lengths differ")
        rewrite_status = any(
            str(check.get("id", "")) in {"patch.rewrite", "patch.capacity"}
            and _check_status(check) == "passed" for check in checks)
        if verified is True and not rewrite_status:
            violations.append(
                "verified packet has rewrite actions but no passed "
                "patch.rewrite/patch.capacity check")

    # 7. manifest evidence is validated by unified profiles, never legacy ids.
    if view["with_manifest"]:
        legacy_ids = _legacy_check_ids(view)
        if legacy_ids:
            violations.append(
                "manifest-bearing packet is validated by legacy quick-gate "
                f"check ids: {legacy_ids}")
        if not view["profile"]:
            violations.append(
                "manifest-bearing packet has no evidence profile: the "
                "manifest differential must be validated by a unified profile")
        elif verified is True and checks and not any(
                check_id.startswith(tuple(UNIFIED_CHECK_PREFIXES))
                for check_id in ids):
            violations.append(
                f"manifest-bearing packet profile {view['profile']!r} is not a "
                "unified evidence-profile packet")
        elif summary_only:
            limitations.append(
                "summary acceptance record cannot prove unified profile check "
                "ids (packet-level capture required for release)")

    # 8. profile-required checks must all pass on a verified packet.
    required_profile_checks = _profile_required_checks(view["profile"])
    if summary_only and verified is True and required_profile_checks:
        limitations.append(
            "summary acceptance record has no full check list; required "
            "profile checks were not re-validated")
        required_profile_checks = []
    if verified is True and required_profile_checks:
        passed_ids = {str(check.get("id", "")) for check in checks
                      if _check_status(check) == "passed"}
        missing = [check_id for check_id in required_profile_checks
                   if check_id not in passed_ids]
        if missing:
            violations.append(
                f"verified packet is missing required profile checks "
                f"{missing} for profile {view['profile']!r}")

    # 9. download => verified deterministic candidate, checks all passed.
    if view["download_allowed"]:
        if verified is not True:
            violations.append(
                "download is allowed for a result that is not verified")
        if disposition and disposition not in VERIFIED_DISPOSITIONS:
            violations.append(
                f"download is allowed for disposition {disposition!r}")
        if required_failed or required_not_run:
            violations.append(
                "download is allowed although required checks failed/not_run")
        if view["with_manifest"] and not view["profile"]:
            violations.append(
                "download is allowed for manifest evidence without a unified "
                "profile")

    return {
        "ok": not violations,
        "violations": violations,
        "limitations": list(dict.fromkeys(limitations)),
        "identity": identity,
        "checked": {
            "verified": verified,
            "disposition": disposition,
            "gate_outcome": gate_outcome,
            "target_policy": policy,
            "checks_total": len(checks),
            "actions_total": len(view["actions"]),
            "with_manifest": view["with_manifest"],
            "profile": view["profile"],
            "download_allowed": view["download_allowed"],
        },
    }


def _looks_like_packet(record: dict[str, Any]) -> bool:
    keys = set(record)
    markers = {"disposition", "verified", "checks", "gate_outcome",
               "download_allowed", "target_scope_check", "decision", "ok",
               "checks_failed", "checks_not_run", "poc_status",
               "target_policy", "with_manifest"}
    return bool(keys & markers)


def check_acceptance(acceptance: Any) -> dict[str, Any]:
    """Check every packet/record in a committed acceptance capture."""
    document = _as_dict(acceptance)
    records: list[tuple[str, dict[str, Any]]] = []
    for key in ("packets", "cases"):
        for index, item in enumerate(_as_list(document.get(key))):
            item_dict = _as_dict(item)
            if item_dict:
                records.append((f"{key}[{index}]", item_dict))
    if not records:
        for key, value in document.items():
            item_dict = _as_dict(value)
            if item_dict and _looks_like_packet(item_dict):
                records.append((key, item_dict))
    violations: list[str] = []
    limitations: list[str] = []
    if document:
        if document.get("passed") is True:
            failures = _as_list(document.get("failures"))
            if failures:
                violations.append(
                    f"acceptance capture says passed=true but lists failures: "
                    f"{failures[:3]}")
        elif document.get("passed") is False:
            violations.append("acceptance capture says passed=false")
        else:
            limitations.append(
                "acceptance capture has no top-level 'passed' boolean")
    else:
        violations.append("acceptance capture is empty or not an object")
    checked = 0
    for identity, record in records:
        result = check_packet(record)
        checked += 1
        for violation in result["violations"]:
            violations.append(f"{identity}: {violation}")
        for limitation in result.get("limitations", []):
            limitations.append(f"{identity}: {limitation}")
    if checked == 0 and document:
        limitations.append(
            "no packet-like acceptance records were found to validate")
    if checked and not violations:
        limitations.append(
            f"validated {checked} acceptance record(s) with the invariant engine")
    return {
        "ok": not violations,
        "violations": violations,
        "packets_checked": checked,
        "limitations": limitations,
        "schema_version": SCHEMA_VERSION,
    }
