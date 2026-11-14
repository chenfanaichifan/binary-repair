"""Acceptance intelligence: A01-A08 dimensions and the AM01-AM20 mismatch model.

The matcher is a **pure function**: it performs no I/O, no network access, no
clock reads and never mutates its inputs.  Callers hand it a *task* (what the
repair task claims) and an *acceptance* (what the evidence actually proves), and
it returns a deterministic, JSON-serializable decision.

Fail-closed by construction: ``verified`` is True only when no mismatch is
detected, every required evidence reference is present and intact, the model
identity is *exactly* the requested model (a legitimate declared alias is the
only exception), and independence is satisfied.  A served-model-only,
unknown or mismatched model identity can never masquerade as verified.

Mismatch classes (20):

===== ============================ ======== ===============================
id    title                        severity required action
===== ============================ ======== ===============================
AM01  target SHA mismatch          critical reject: task target SHA changed
AM02  tree SHA mismatch            critical reject: gated tree differs
AM03  container format mismatch    high     reject: format differs
AM04  arch/ABI mismatch            high     reject: arch or ABI differs
AM05  scope overclaim              critical reject: evidence scope weaker
AM06  static/dynamic evidence gap  high     reject: required evidence mode missing
AM07  whole-program claim unsupported critical reject: no whole-program evidence
AM08  evidence hash mismatch       critical reject: evidence bytes differ
AM09  served-model identity        critical reject: served-only is not requested
AM10  unknown model identity       critical reject: identity unknown
AM11  mismatched model identity    critical reject: served != requested
AM12  invalid model alias          high     reject: undeclared alias
AM13  required method missing      high     reject: method not evidenced
AM14  environment mismatch         high     reject: required environment differs
AM15  only-positive evidence       critical reject: no regression/negative case
AM16  insufficient statistics      high     reject: repeats/confidence below bar
AM17  tool version drift           medium   reject: tool versions differ
AM18  independence violation       critical reject: self/shared-source review
AM19  unsupported extra claim      high     reject: claim exceeds task contract
AM20  evidence incomplete          critical reject: required evidence missing
===== ============================ ======== ===============================
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1
TASK_SCOPES = ("vulnerability", "function", "module", "whole_program")
SCOPE_RANK = {name: index for index, name in enumerate(TASK_SCOPES)}
EVIDENCE_MODES = ("static", "dynamic")
MODEL_IDENTITY_STATUSES = ("exact", "alias", "served-model-only", "unknown",
                           "mismatch")
DECISIONS = ("verified", "rejected")
RESIDUAL_RISKS = ("low", "medium", "high", "critical")

#: A01-A08 acceptance dimensions (each maps to the mismatch classes it guards).
ACCEPTANCE_DIMENSIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "A01", "title": "identity (target/tree/format/arch/ABI)",
        "task_fields": ("target_sha", "tree_sha", "format", "arch", "abi"),
        "acceptance_fields": ("target", "format", "arch", "abi"),
        "mismatch_ids": ("AM01", "AM02", "AM03", "AM04", "AM20"),
    },
    {
        "id": "A02", "title": "scope (vulnerability/function/module/whole_program)",
        "task_fields": ("scope",),
        "acceptance_fields": ("scope", "claims.scope"),
        "mismatch_ids": ("AM05", "AM07", "AM19"),
    },
    {
        "id": "A03", "title": "methods and evidence modes",
        "task_fields": ("required_methods", "required_evidence_modes"),
        "acceptance_fields": ("methods", "evidence[].methods", "evidence[].mode"),
        "mismatch_ids": ("AM06", "AM13"),
    },
    {
        "id": "A04", "title": "environment",
        "task_fields": ("required_environment",),
        "acceptance_fields": ("environment", "evidence[].environment"),
        "mismatch_ids": ("AM14", "AM20"),
    },
    {
        "id": "A05", "title": "model identity",
        "task_fields": ("model_identity",),
        "acceptance_fields": ("model_identity",),
        "mismatch_ids": ("AM09", "AM10", "AM11", "AM12"),
    },
    {
        "id": "A06", "title": "evidence integrity (refs/hashes)",
        "task_fields": ("evidence_refs",),
        "acceptance_fields": ("evidence",),
        "mismatch_ids": ("AM08", "AM15", "AM20"),
    },
    {
        "id": "A07", "title": "regression and statistics",
        "task_fields": ("requires_regression", "required_repeats",
                        "required_tool_versions"),
        "acceptance_fields": ("evidence[].regression", "evidence[].repeats",
                              "evidence[].tool_versions", "only_positive"),
        "mismatch_ids": ("AM15", "AM16", "AM17"),
    },
    {
        "id": "A08", "title": "independence and claims",
        "task_fields": ("model_identity.independence_required",),
        "acceptance_fields": ("independence", "claims"),
        "mismatch_ids": ("AM18", "AM19"),
    },
)

#: AM01-AM20 mismatch registry.
MISMATCH_RULES: tuple[dict[str, Any], ...] = (
    {"id": "AM01", "code": "target_sha_mismatch", "severity": "critical",
     "required_actions": ("reject_target_sha_mismatch",)},
    {"id": "AM02", "code": "tree_sha_mismatch", "severity": "critical",
     "required_actions": ("reject_tree_sha_mismatch",)},
    {"id": "AM03", "code": "format_mismatch", "severity": "high",
     "required_actions": ("reject_format_mismatch",)},
    {"id": "AM04", "code": "arch_abi_mismatch", "severity": "high",
     "required_actions": ("reject_arch_abi_mismatch",)},
    {"id": "AM05", "code": "scope_overclaim", "severity": "critical",
     "required_actions": ("reject_scope_overclaim",)},
    {"id": "AM06", "code": "evidence_mode_mismatch", "severity": "high",
     "required_actions": ("collect_required_evidence_mode",)},
    {"id": "AM07", "code": "whole_program_claim_unsupported",
     "severity": "critical",
     "required_actions": ("reject_whole_program_claim",)},
    {"id": "AM08", "code": "evidence_hash_mismatch", "severity": "critical",
     "required_actions": ("reject_evidence_hash_mismatch",)},
    {"id": "AM09", "code": "served_model_identity", "severity": "critical",
     "required_actions": ("reject_served_model_identity",)},
    {"id": "AM10", "code": "unknown_model_identity", "severity": "critical",
     "required_actions": ("reject_unknown_model_identity",)},
    {"id": "AM11", "code": "mismatched_model_identity", "severity": "critical",
     "required_actions": ("reject_mismatched_model_identity",)},
    {"id": "AM12", "code": "invalid_model_alias", "severity": "high",
     "required_actions": ("reject_invalid_model_alias",)},
    {"id": "AM13", "code": "required_method_missing", "severity": "high",
     "required_actions": ("collect_required_method_evidence",)},
    {"id": "AM14", "code": "environment_mismatch", "severity": "high",
     "required_actions": ("reject_environment_mismatch",)},
    {"id": "AM15", "code": "only_positive_evidence", "severity": "critical",
     "required_actions": ("add_regression_negative_case",)},
    {"id": "AM16", "code": "insufficient_statistics", "severity": "high",
     "required_actions": ("increase_repeats_or_confidence",)},
    {"id": "AM17", "code": "tool_version_drift", "severity": "medium",
     "required_actions": ("reject_tool_version_drift",)},
    {"id": "AM18", "code": "independence_violation", "severity": "critical",
     "required_actions": ("require_independent_review",)},
    {"id": "AM19", "code": "unsupported_claim", "severity": "high",
     "required_actions": ("reject_unsupported_claim",)},
    {"id": "AM20", "code": "evidence_incomplete", "severity": "critical",
     "required_actions": ("collect_complete_evidence",)},
)

MISMATCH_BY_ID = {rule["id"]: rule for rule in MISMATCH_RULES}
MISMATCH_IDS = tuple(rule["id"] for rule in MISMATCH_RULES)
DIMENSION_BY_ID = {dim["id"]: dim for dim in ACCEPTANCE_DIMENSIONS}

#: Evidence record fields that must be present for a complete acceptance.
REQUIRED_EVIDENCE_FIELDS = (
    "evidence_id", "sha256", "mode", "scope", "methods", "environment",
    "author", "reviewer", "regression", "repeats", "tool_versions",
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _scope_rank(scope: Any) -> int:
    return SCOPE_RANK.get(str(scope or ""), -1)


def _identity_mode(value: Any) -> str:
    """Normalize an evidence mode hint to static/dynamic (or '')."""
    text = str(value or "").lower()
    if "dynamic" in text or "run" in text:
        return "dynamic"
    if "static" in text:
        return "static"
    return ""


class AcceptanceModelMatcher:
    """Pure, deterministic task-vs-acceptance mismatch matcher."""

    @staticmethod
    def match(task: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
        task = _as_dict(task)
        acceptance = _as_dict(acceptance)
        task_id = _text(task.get("task_id"))
        target = _as_dict(acceptance.get("target"))
        evidence = [_as_dict(item) for item in _as_list(
            acceptance.get("evidence"))]
        refs = [_as_dict(item) for item in _as_list(task.get("evidence_refs"))]
        identity = _as_dict(acceptance.get("model_identity"))
        task_identity = _as_dict(task.get("model_identity"))
        independence = _as_dict(acceptance.get("independence"))
        claims = _as_dict(acceptance.get("claims"))
        environment = _as_dict(acceptance.get("environment"))
        required_environment = _as_dict(task.get("required_environment"))
        required_methods = [_text(item) for item in _as_list(
            task.get("required_methods"))]
        acceptance_methods = {_text(item) for item in _as_list(
            acceptance.get("methods"))}
        for item in evidence:
            acceptance_methods.update(_text(value) for value in _as_list(
                item.get("methods")))
        evidence_modes = {_identity_mode(item.get("mode")) for item in evidence}
        evidence_modes.discard("")
        required_modes = {_identity_mode(item) for item in _as_list(
            task.get("required_evidence_modes"))}
        required_modes.discard("")

        mismatches: list[str] = []
        reasons: dict[str, list[str]] = {}

        def flag(mismatch_id: str, reason: str) -> None:
            if mismatch_id not in MISMATCH_BY_ID:
                raise ValueError(f"unknown mismatch id {mismatch_id!r}")
            if mismatch_id not in mismatches:
                mismatches.append(mismatch_id)
            reasons.setdefault(mismatch_id, []).append(reason)

        # A01 identity -----------------------------------------------------
        expected_target_sha = _text(task.get("target_sha"))
        acceptance_target_sha = _text(target.get("sha256")
                                      or acceptance.get("target_sha"))
        if not acceptance_target_sha or not expected_target_sha:
            flag("AM20", "target SHA is missing from the acceptance")
        elif acceptance_target_sha != expected_target_sha:
            flag("AM01",
                 f"target SHA {acceptance_target_sha} != task {expected_target_sha}")
        expected_tree_sha = _text(task.get("tree_sha"))
        acceptance_tree_sha = _text(target.get("tree_sha")
                                    or acceptance.get("tree_sha"))
        if not acceptance_tree_sha or not expected_tree_sha:
            flag("AM20", "tree SHA is missing from the acceptance")
        elif acceptance_tree_sha != expected_tree_sha:
            flag("AM02",
                 f"tree SHA {acceptance_tree_sha} != task {expected_tree_sha}")
        expected_format = _text(task.get("format"))
        acceptance_format = _text(target.get("format")
                                  or acceptance.get("format"))
        if not acceptance_format or not expected_format:
            flag("AM20", "container format is missing from the acceptance")
        elif acceptance_format != expected_format:
            flag("AM03",
                 f"format {acceptance_format} != task {expected_format}")
        expected_arch = _text(task.get("arch"))
        acceptance_arch = _text(target.get("arch") or acceptance.get("arch"))
        expected_abi = _text(task.get("abi"))
        acceptance_abi = _text(target.get("abi") or acceptance.get("abi"))
        if not acceptance_arch or not expected_arch:
            flag("AM20", "arch is missing from the acceptance")
        elif acceptance_arch != expected_arch:
            flag("AM04",
                 f"arch {acceptance_arch} != task {expected_arch}")
        if expected_abi and _text(acceptance_abi) and acceptance_abi != expected_abi:
            flag("AM04",
                 f"ABI {acceptance_abi} != task {expected_abi}")

        # A02 scope --------------------------------------------------------
        task_scope = _text(task.get("scope"))
        acceptance_scope = _text(acceptance.get("scope"))
        evidence_scopes = {_text(item.get("scope")) for item in evidence}
        evidence_scopes.discard("")
        if not acceptance_scope:
            flag("AM20", "acceptance scope is missing")
        elif _scope_rank(acceptance_scope) > _scope_rank(task_scope):
            flag("AM05",
                 f"acceptance scope {acceptance_scope} overclaims task scope "
                 f"{task_scope}")
        claims_scope = _text(claims.get("scope"))
        whole_program_claimed = (
            task_scope == "whole_program"
            or acceptance_scope == "whole_program"
            or claims_scope == "whole_program"
        )
        if whole_program_claimed and "whole_program" not in evidence_scopes:
            flag("AM07",
                 "whole-program claim has no whole-program evidence "
                 f"(evidence scopes={sorted(evidence_scopes)})")

        # A03 methods / modes ---------------------------------------------
        missing_methods = [method for method in required_methods
                           if method not in acceptance_methods]
        if missing_methods:
            flag("AM13", f"required method(s) not evidenced: {missing_methods}")
        missing_modes = sorted(required_modes - evidence_modes)
        if missing_modes:
            flag("AM06",
                 f"required evidence mode(s) missing: {missing_modes} "
                 f"(evidence modes={sorted(evidence_modes)})")

        # A04 environment --------------------------------------------------
        for key, expected in sorted(required_environment.items()):
            actual = environment.get(key)
            if actual is None:
                for item in evidence:
                    item_environment = _as_dict(item.get("environment"))
                    if key in item_environment:
                        actual = item_environment[key]
                        break
            if actual is None:
                flag("AM20", f"required environment field {key!r} is missing")
            elif _text(actual) != _text(expected):
                flag("AM14",
                     f"environment {key}={actual!r} != task {expected!r}")

        # A05 model identity ----------------------------------------------
        identity_status = _text(identity.get("status"))
        requested = _text(task_identity.get("requested"))
        allowed_aliases = {_text(item) for item in _as_list(
            task_identity.get("allowed_aliases"))}
        identity_requested = _text(identity.get("requested"))
        identity_served = _text(identity.get("served")
                                or identity.get("model"))
        if not identity or not identity_status:
            flag("AM10", "model identity status is unknown/missing")
        elif identity_status not in MODEL_IDENTITY_STATUSES:
            flag("AM10",
                 f"model identity status {identity_status!r} is not a known "
                 "acceptance state")
        elif identity_status == "served-model-only":
            flag("AM09",
                 "served-model-only identity cannot verify the requested model "
                 f"(requested={requested or '?'} served={identity_served or '?'})")
        elif identity_status == "unknown":
            flag("AM10", "model identity is unknown")
        elif identity_status == "mismatch":
            flag("AM11",
                 f"model identity mismatch (served={identity_served or '?'} "
                 f"requested={identity_requested or requested or '?'})")
        elif identity_status == "exact":
            if identity_served != identity_requested or (
                    requested and identity_requested != requested):
                flag("AM11",
                     "exact identity does not match requested model "
                     f"(requested={identity_requested or '?'} "
                     f"served={identity_served or '?'} task={requested or '?'})")
        elif identity_status == "alias":
            if (identity_served not in allowed_aliases
                    or identity_requested != requested
                    or identity_served == identity_requested):
                flag("AM12",
                     "alias identity is invalid: "
                     f"served={identity_served or '?'} "
                     f"allowed={sorted(allowed_aliases)} "
                     f"requested={identity_requested or '?'}")

        # A06 evidence integrity ------------------------------------------
        if not evidence:
            flag("AM20", "acceptance carries no evidence records")
        for item in evidence:
            missing_fields = [
                field for field in REQUIRED_EVIDENCE_FIELDS
                if field not in item or item.get(field) in (None, "", [])
            ]
            if missing_fields:
                flag("AM20",
                     f"evidence {item.get('evidence_id') or '?'} missing "
                     f"fields {missing_fields}")
        evidence_by_id = {_text(item.get("evidence_id")): item
                          for item in evidence if _text(item.get("evidence_id"))}
        ref_by_id = {_text(item.get("evidence_id")): item for item in refs
                     if _text(item.get("evidence_id"))}
        for evidence_id, ref in sorted(ref_by_id.items()):
            actual = evidence_by_id.get(evidence_id)
            if actual is None:
                flag("AM20", f"required evidence {evidence_id} is missing")
                continue
            expected_sha = _text(ref.get("sha256"))
            actual_sha = _text(actual.get("sha256"))
            if not actual_sha or (expected_sha and actual_sha != expected_sha):
                flag("AM08",
                     f"evidence {evidence_id} sha256 {actual_sha or '?'} != "
                     f"expected {expected_sha or '?'}")
        if _text(acceptance.get("evidence_manifest_sha256")):
            expected_manifest = _text(task.get("expected_evidence_manifest"))
            actual_manifest = _text(acceptance.get("evidence_manifest_sha256"))
            if expected_manifest and actual_manifest != expected_manifest:
                flag("AM08",
                     "evidence manifest sha256 does not match the task's "
                     "expected manifest")

        # A07 regression / statistics / tool versions ---------------------
        requires_regression = bool(
            task.get("requires_regression",
                     "regression_suite" in required_methods)
        )
        has_regression = any(bool(item.get("regression")) for item in evidence)
        positive_only = bool(acceptance.get("only_positive")) or (
            bool(evidence) and all(not bool(item.get("regression"))
                                   for item in evidence))
        if requires_regression and (positive_only or not has_regression):
            flag("AM15",
                 "task requires a regression/negative case but the acceptance "
                 "is only-positive")
        required_repeats = task.get("required_repeats")
        if required_repeats is not None:
            try:
                required_repeats_int = int(required_repeats)
            except (TypeError, ValueError):
                required_repeats_int = 0
            for item in evidence:
                try:
                    repeats = int(item.get("repeats") or 0)
                except (TypeError, ValueError):
                    repeats = 0
                if repeats < required_repeats_int:
                    flag("AM16",
                         f"evidence {item.get('evidence_id') or '?'} repeats="
                         f"{repeats} < required {required_repeats_int}")
                    break
        required_versions = _as_dict(task.get("required_tool_versions"))
        if required_versions:
            combined_versions: dict[str, Any] = {}
            for item in evidence:
                combined_versions.update(_as_dict(item.get("tool_versions")))
            combined_versions.update(_as_dict(acceptance.get("tool_versions")))
            for tool, expected in sorted(required_versions.items()):
                actual = combined_versions.get(tool)
                if actual is None or _text(actual) != _text(expected):
                    flag("AM17",
                         f"tool {tool} version {actual!r} != required "
                         f"{expected!r}")

        # A08 independence and claims ------------------------------------
        if not independence:
            flag("AM20", "independence record is missing from the acceptance")
        else:
            authors = {_text(item) for item in _as_list(
                independence.get("authors"))}
            reviewers = {_text(item) for item in _as_list(
                independence.get("reviewers"))}
            authors.discard("")
            reviewers.discard("")
            evidence_pairs = [
                (_text(item.get("author")), _text(item.get("reviewer")))
                for item in evidence
            ]
            self_review_evidence = [
                author for author, reviewer in evidence_pairs
                if author and author == reviewer
            ]
            if (bool(independence.get("self_review"))
                    or bool(independence.get("shared_source"))
                    or (authors & reviewers)
                    or self_review_evidence):
                flag("AM18",
                     "independence is not satisfied "
                     f"(self_review={bool(independence.get('self_review'))}, "
                     f"shared_source={bool(independence.get('shared_source'))}, "
                     f"overlap={sorted(authors & reviewers)}, "
                     f"self_reviewed_evidence={self_review_evidence[:3]})")
        extra_claims = [_text(item) for item in _as_list(
            claims.get("extra_claims"))]
        if extra_claims:
            flag("AM19", f"claims exceed the task contract: {extra_claims}")
        claims_scope = _text(claims.get("scope"))
        if claims_scope and _scope_rank(claims_scope) > _scope_rank(task_scope):
            flag("AM19",
                 f"claims scope {claims_scope} overclaims task scope "
                 f"{task_scope}")
        if not claims:
            flag("AM20", "claims record is missing from the acceptance")

        detected = sorted(set(mismatches))
        verified = not detected
        required_actions = sorted({
            action for mismatch_id in detected
            for action in MISMATCH_BY_ID[mismatch_id]["required_actions"]
        })
        severities = [MISMATCH_BY_ID[mismatch_id]["severity"]
                      for mismatch_id in detected]
        if not detected:
            residual_risk = "low"
        elif "critical" in severities:
            residual_risk = "critical"
        elif "high" in severities:
            residual_risk = "high"
        else:
            residual_risk = "medium"
        reason_lines = [
            f"{mismatch_id}: {MISMATCH_BY_ID[mismatch_id]['code']}: "
            + "; ".join(reasons[mismatch_id])
            for mismatch_id in detected
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "decision": "verified" if verified else "rejected",
            "mismatches": detected,
            "required_actions": required_actions,
            "verified": verified,
            "residual_risk": residual_risk,
            "reasons": reason_lines,
        }


def match(task: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    """Module-level convenience wrapper around the pure matcher."""
    return AcceptanceModelMatcher.match(task, acceptance)
