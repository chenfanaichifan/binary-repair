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
        "mismatch_ids": ("AM01", "AM02", "AM03", "AM04", "AM20", "AM24"),
    },
    {
        "id": "A02", "title": "scope (vulnerability/function/module/whole_program)",
        "task_fields": ("scope",),
        "acceptance_fields": ("scope", "claims.scope"),
        "mismatch_ids": ("AM05", "AM07", "AM19", "AM21", "AM22", "AM25",
                          "AM26"),
    },
    {
        "id": "A03", "title": "methods and evidence modes",
        "task_fields": ("required_methods", "required_evidence_modes"),
        "acceptance_fields": ("methods", "evidence[].methods", "evidence[].mode"),
        "mismatch_ids": ("AM06", "AM13", "AM22", "AM27"),
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
        "mismatch_ids": ("AM08", "AM15", "AM20", "AM23", "AM28"),
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
    {"id": "AM21", "code": "repair_scope_mismatch", "severity": "critical",
     "required_actions": ("reject_repair_scope_mismatch",)},
    {"id": "AM22", "code": "semantic_scope_mismatch", "severity": "high",
     "required_actions": ("collect_semantic_scope_evidence",)},
    {"id": "AM23", "code": "oracle_quality_insufficient",
     "severity": "critical",
     "required_actions": ("require_independent_oracle",)},
    {"id": "AM24", "code": "benchmark_version_mismatch",
     "severity": "high",
     "required_actions": ("reject_benchmark_version_mismatch",)},
    {"id": "AM25", "code": "candidate_layout_mismatch",
     "severity": "critical",
     "required_actions": ("reject_candidate_layout_mismatch",)},
    {"id": "AM26", "code": "unauthorized_associated_change",
     "severity": "critical",
     "required_actions": ("reject_unauthorized_associated_change",)},
    {"id": "AM27", "code": "abi_evidence_incomplete",
     "severity": "high",
     "required_actions": ("collect_derived_abi_evidence",)},
    {"id": "AM28", "code": "oracle_metadata_incomplete",
     "severity": "high",
     "required_actions": ("collect_oracle_metadata",)},
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

        # A09 repair scope ------------------------------------------------
        task_target_scope = _as_dict(task.get("target_scope"))
        repair_scope = _as_dict(acceptance.get("repair_scope"))
        claimed_policy = _text(repair_scope.get("policy"))
        task_policy = _text(task_target_scope.get("policy"))
        task_scope_text = _text(task.get("scope"))
        if claimed_policy:
            if claimed_policy in {"whole_image", "whole_program"} and (
                    task_policy == "target_scoped"
                    or task_scope_text in {"function", "vulnerability"}):
                flag("AM21",
                     f"repair scope {claimed_policy!r} exceeds the declared "
                     f"target scope {task_policy or task_scope_text!r}")
            elif task_policy == "target_scoped" and claimed_policy not in {
                    "target_scoped"}:
                flag("AM21",
                     f"repair scope {claimed_policy!r} contradicts the target "
                     "scope policy 'target_scoped'")
        target_name = _text(task_target_scope.get("name"))
        modified_functions = [_text(item) for item in _as_list(
            repair_scope.get("modified_functions"))]
        if target_name and modified_functions:
            outside = sorted({name for name in modified_functions
                              if name and name != target_name})
            if outside:
                flag("AM21",
                     f"modified functions {outside} are outside the declared "
                     f"target function {target_name!r}")
        target_va = task_target_scope.get("va")
        target_end = task_target_scope.get("end")
        if isinstance(target_va, int) and isinstance(target_end, int):
            for action in _as_list(repair_scope.get("actions")):
                action = _as_dict(action)
                site = action.get("va", action.get("site_va"))
                if isinstance(site, int) and not (target_va <= site < target_end):
                    flag("AM21",
                         f"repair action at {site:#x} is outside target range "
                         f"[{target_va:#x}, {target_end:#x})")
                    break

        # A10 semantic scope ---------------------------------------------
        semantic_scope = _as_dict(task.get("semantic_scope"))
        semantic_coverage = _as_dict(acceptance.get("semantic_coverage"))
        required_semantics = {
            key: [_text(item) for item in _as_list(semantic_scope.get(key))]
            for key in ("required_inputs", "required_paths", "required_behaviors")
        }
        if any(required_semantics.values()):
            coverage_fields = {
                "required_inputs": "inputs",
                "required_paths": "paths",
                "required_behaviors": "behaviors",
            }
            for required_key, required_values in required_semantics.items():
                if not required_values:
                    continue
                covered = {_text(item) for item in _as_list(
                    semantic_coverage.get(coverage_fields[required_key]))}
                missing = [value for value in required_values
                           if value not in covered]
                if missing:
                    flag("AM22",
                         f"semantic coverage misses {required_key}: {missing}")
            if semantic_coverage.get("complete") is False:
                flag("AM22", "semantic coverage is explicitly incomplete")

        # A11 oracle quality ---------------------------------------------
        oracle = _as_dict(acceptance.get("oracle"))
        oracle_kind = _text(oracle.get("kind"))
        if oracle_kind:
            if oracle_kind in {"reference_fix", "generator_self_report", "none"}:
                flag("AM23",
                     f"oracle kind {oracle_kind!r} is not an independent "
                     "oracle")
            elif oracle.get("independent") is False:
                flag("AM23",
                     f"oracle kind {oracle_kind!r} is not independent")
        if bool(task.get("requires_independent_oracle")):
            if not oracle_kind or oracle_kind in {
                    "reference_fix", "generator_self_report", "none"}:
                flag("AM23",
                     "task requires an independent oracle but the acceptance "
                     "does not provide one")

        # A12 benchmark version ------------------------------------------
        task_benchmark = _as_dict(task.get("benchmark"))
        acceptance_benchmark = _as_dict(acceptance.get("benchmark"))
        claims_benchmark = _as_dict(claims.get("benchmark"))
        task_version = _text(task_benchmark.get("version")
                             or task.get("benchmark_version"))
        task_sample_set = _text(task_benchmark.get("sample_set_sha256")
                                or task.get("benchmark_sample_set_sha256"))
        if task_version or task_sample_set:
            observed = {}
            for label, source in (("acceptance", acceptance_benchmark),
                                  ("claims", claims_benchmark)):
                observed[label] = {
                    "version": _text(source.get("version")),
                    "sample_set_sha256": _text(
                        source.get("sample_set_sha256")),
                }
            if not observed["acceptance"]["version"] and not observed[
                    "claims"]["version"]:
                flag("AM24",
                     "task declares a benchmark version but the acceptance "
                     "does not record one")
            for label, record in observed.items():
                if task_version and record["version"] and record[
                        "version"] != task_version:
                    flag("AM24",
                         f"{label} benchmark version {record['version']!r} != "
                         f"task {task_version!r}")
                if task_sample_set and record["sample_set_sha256"] and record[
                        "sample_set_sha256"] != task_sample_set:
                    flag("AM24",
                         f"{label} benchmark sample set does not match the "
                         "task commitment")

        # A13 candidate layout (plan/candidate consistency) ----------------
        plan = _as_dict(task.get("patch_plan"))
        layout = _as_dict(acceptance.get("layout_evidence")) or _as_dict(
            acceptance.get("candidate_layout"))
        if plan:
            plan_sha = _text(plan.get("plan_sha256")
                             or plan.get("patch_plan_sha256"))
            layout_sha = _text(layout.get("patch_plan_sha256")
                               or layout.get("plan_sha256"))
            if not layout:
                flag("AM25", "a patch plan was exchanged but no candidate "
                             "layout evidence is present")
            else:
                if plan_sha and layout_sha and plan_sha != layout_sha:
                    flag("AM25",
                         f"candidate layout plan sha {layout_sha} != plan "
                         f"{plan_sha}")
                plan_candidate_sha = _text(plan.get("candidate_sha256"))
                acceptance_candidate_sha = _text(
                    acceptance.get("candidate_sha256"))
                if (plan_candidate_sha and acceptance_candidate_sha
                        and plan_candidate_sha != acceptance_candidate_sha):
                    flag("AM25",
                         "candidate sha does not match the declared plan")
                if layout.get("replay_ok") is not True:
                    flag("AM25",
                         "candidate layout replay is not declared successful")
                ranges = [_as_dict(item) for item in _as_list(
                    layout.get("changed_ranges"))]
                for operation in _as_list(plan.get("operations")):
                    operation = _as_dict(operation)
                    reason = _text(operation.get("reason"))
                    expected_kind = (
                        "associated"
                        if reason in {"rodata_message", "header_update",
                                      "relocation"}
                        else _text(operation.get("kind"))
                    )
                    offset = operation.get("original_offset")
                    size = operation.get("size")
                    covered = any(
                        item.get("kind") == expected_kind
                        and item.get("original_offset") == offset
                        and item.get("size") == size
                        for item in ranges
                    )
                    if not covered:
                        flag("AM25",
                             "plan operation "
                             f"(kind={expected_kind}, offset={offset}, "
                             f"size={size}) is missing from the candidate "
                             "layout ranges")
                plan_cave = _as_dict(plan.get("cave"))
                if plan_cave:
                    layout_cave = _as_dict(layout.get("cave"))
                    if not layout_cave:
                        flag("AM25",
                             "plan declares a cave but the layout evidence "
                             "does not")
                    elif (layout_cave.get("va") != plan_cave.get("va")
                          or layout_cave.get("size") != plan_cave.get("size")):
                        flag("AM25",
                             "layout cave does not match the plan cave")
                plan_relocations = [_as_dict(item) for item in _as_list(
                    plan.get("relocations"))]
                if plan_relocations:
                    layout_relocations = [_as_dict(item) for item in _as_list(
                        layout.get("relocations"))]
                    layout_offsets = {
                        (item.get("offset"), item.get("size"))
                        for item in layout_relocations
                    }
                    for relocation in plan_relocations:
                        if (relocation.get("offset"),
                                relocation.get("size")) not in layout_offsets:
                            flag("AM25",
                                 "plan relocation is missing from the "
                                 "candidate layout evidence")

        # A14 authorized associated changes --------------------------------
        associated = [
            _as_dict(item) for item in _as_list(
                acceptance.get("associated_changes")
                or layout.get("associated_changes")
            )
        ]
        if acceptance.get("associated_changes_authorized") is False:
            flag("AM26", "associated changes are explicitly unauthorized")
        if associated:
            authority = _as_dict(task.get("authority")) or _as_dict(
                acceptance.get("authority"))
            authorized = [
                _as_dict(item) for item in _as_list(
                    authority.get("authorized_changes")
                    or task.get("authorized_changes")
                    or acceptance.get("authorized_changes")
                )
            ]
            for change in associated:
                if not _text(change.get("authorization_ref")):
                    flag("AM26",
                         "associated change has no authorization_ref")
                    continue
                if not authorized:
                    flag("AM26",
                         "associated change is declared without any authority "
                         "record")
                    continue
                kind = _text(change.get("kind"))
                change_offset = change.get("file_offset")
                change_size = change.get("size")
                change_va = change.get("va")
                change_end = change.get("end")
                matched = False
                for allowed in authorized:
                    if _text(allowed.get("kind")) != kind:
                        continue
                    if (isinstance(change_offset, int)
                            and isinstance(change_size, int)
                            and isinstance(allowed.get("file_offset"), int)
                            and isinstance(allowed.get("size"), int)):
                        allowed_start = allowed["file_offset"]
                        allowed_stop = allowed_start + allowed["size"]
                        if (change_offset >= allowed_start
                                and change_offset + change_size
                                <= allowed_stop):
                            matched = True
                            break
                    if (isinstance(change_va, int)
                            and isinstance(change_end, int)
                            and isinstance(allowed.get("va"), int)
                            and isinstance(allowed.get("end"), int)):
                        if (change_va >= allowed["va"]
                                and change_end <= allowed["end"]):
                            matched = True
                            break
                if not matched:
                    flag("AM26",
                         f"associated change kind={kind!r} at "
                         f"offset={change_offset}/va={change_va} is outside "
                         "the authorized ranges")

        # A15 derived ABI evidence -----------------------------------------
        executable_changes = [
            item for item in _as_list(layout.get("changed_ranges"))
            if _as_dict(item).get("kind") in {"write", "insert", "replace"}
        ]
        requires_abi = bool(
            task.get("requires_abi_evidence")
            or acceptance.get("abi_required")
            or executable_changes
        )
        if requires_abi:
            abi_blocks = [
                _as_dict(item) for item in _as_list(
                    acceptance.get("abi_blocks")
                    or layout.get("abi_blocks")
                )
            ]
            abi_evidence = _as_dict(acceptance.get("abi_evidence"))
            if not abi_blocks and not abi_evidence:
                flag("AM27",
                     "executable modification has no derivable ABI evidence")
            for block in abi_blocks:
                if (not _text(block.get("function"))
                        or not isinstance(block.get("va"), int)
                        or not isinstance(block.get("size"), int)
                        or _text(block.get("arch")) not in
                        {"x86_64", "i386", "arm64"}):
                    flag("AM27",
                         "ABI evidence block is not independently derivable")
            if abi_evidence:
                if abi_evidence.get("derived") is False:
                    flag("AM27",
                         "ABI evidence is declared as not independently "
                         "derived")
                if (not _text(abi_evidence.get("arch"))
                        or not isinstance(abi_evidence.get("va"), int)):
                    flag("AM27",
                         "ABI evidence is missing arch/va derivation facts")

        # A16 oracle metadata / independent execution ----------------------
        oracle_evidence = _as_dict(acceptance.get("oracle_evidence"))
        if oracle_evidence:
            runner = _text(oracle_evidence.get("runner"))
            tier = _text(oracle_evidence.get("tier"))
            manifest_sha = _text(oracle_evidence.get("manifest_sha256"))
            status = _text(oracle_evidence.get("status"))
            evidence_sha = _text(oracle_evidence.get("evidence_sha256"))
            expected = _as_dict(oracle_evidence.get("expected"))
            if not runner:
                flag("AM28", "oracle_evidence has no runner")
            if tier not in {"native_run", "emulated_run", "static_only"}:
                flag("AM28",
                     f"oracle_evidence tier {tier!r} is not a runnable tier")
            if len(manifest_sha) != 64 or any(
                    char not in "0123456789abcdef" for char in manifest_sha):
                flag("AM28",
                     "oracle_evidence manifest_sha256 is missing/invalid")
            if status != "executed":
                flag("AM28",
                     "oracle was not independently executed "
                     f"(status={status or 'missing'!r})")
            if not evidence_sha:
                flag("AM28",
                     "executed oracle has no evidence_sha256")
            for field in ("expected_original", "expected_candidate"):
                if expected.get(field) in (None, ""):
                    flag("AM28",
                         f"oracle_evidence is missing expected.{field}")

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
