"""Acceptance 2.0: additive L0-L7 acceptance layers and rule mutation audit.

This module is deliberately additive to the historical AM01-AM28 acceptance
model.  It does not rewrite that registry, its 62-case matrix or any committed
claim.  It evaluates a richer case envelope (task + acceptance evidence) through
eight explicit layers and returns a fail-closed decision:

* ``verified`` only when every required rule passed and the registry digest and
  version are canonical;
* ``not_run``/``inconclusive``/``analysis_only`` are never promoted to verified;
* any failed required rule yields ``rejected`` even if other rules are unknown;
* missing/unknown evidence yields ``not_run`` rather than a fabricated pass.

The mutation runner deliberately breaks rules, evidence, scope, oracle and state
inputs and records whether the detector fired.  It is a rule/mutation audit, not
a proof that the underlying binary verifier is correct.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 2
REGISTRY_VERSION = "2.0.0"
SUPPORTED_REGISTRY_VERSIONS = ("2.0.0",)
SUPPORTED_BENCHMARK_VERSIONS = ("phase8c", "phase8d")
DECISIONS = ("verified", "rejected", "not_run", "inconclusive", "analysis_only")
HEX64 = set("0123456789abcdef")

LAYER_SPECS: tuple[dict[str, str], ...] = (
    {"id": "L0", "title": "input identity and basic integrity"},
    {"id": "L1", "title": "structural/target/scope integrity"},
    {"id": "L2", "title": "patch plan and byte replay integrity"},
    {"id": "L3", "title": "ABI and control-flow integrity"},
    {"id": "L4", "title": "vulnerability elimination"},
    {"id": "L5", "title": "semantic preservation"},
    {"id": "L6", "title": "regression and robustness"},
    {"id": "L7", "title": "evidence, independence and non-promotion"},
)

RULE_SPECS: tuple[dict[str, Any], ...] = (
    {"id": "L0.required_sections", "layer": "L0", "required": True,
     "severity": "critical", "title": "task and acceptance sections are present"},
    {"id": "L0.identity_hashes", "layer": "L0", "required": True,
     "severity": "critical", "title": "identity hashes are well formed"},
    {"id": "L0.registry_version", "layer": "L0", "required": True,
     "severity": "critical", "title": "acceptance registry version is known"},
    {"id": "L1.target_identity", "layer": "L1", "required": True,
     "severity": "critical", "title": "target identity matches the task"},
    {"id": "L1.scope_policy", "layer": "L1", "required": True,
     "severity": "critical", "title": "scope is not inflated"},
    {"id": "L1.analysis_only_state", "layer": "L1", "required": True,
     "severity": "critical", "title": "analysis_only is never a verified claim"},
    {"id": "L2.candidate_present", "layer": "L2", "required": True,
     "severity": "critical", "title": "candidate bytes and digest are present"},
    {"id": "L2.patch_plan", "layer": "L2", "required": True,
     "severity": "critical", "title": "layout-changing candidate has a plan"},
    {"id": "L2.replay_exact", "layer": "L2", "required": True,
     "severity": "critical", "title": "plan replay reproduces candidate bytes"},
    {"id": "L2.target_scope", "layer": "L2", "required": True,
     "severity": "critical", "title": "changed ranges stay in resolved scope"},
    {"id": "L2.associated_changes", "layer": "L2", "required": True,
     "severity": "critical", "title": "associated changes are authorized"},
    {"id": "L3.abi_blocks", "layer": "L3", "required": True,
     "severity": "critical", "title": "derived ABI blocks are available"},
    {"id": "L3.control_flow", "layer": "L3", "required": True,
     "severity": "critical", "title": "control-flow targets are resolved/allowed"},
    {"id": "L4.oracle_executed", "layer": "L4", "required": True,
     "severity": "critical", "title": "independent oracle executed"},
    {"id": "L4.original_vulnerable", "layer": "L4", "required": True,
     "severity": "critical", "title": "original vulnerability was observed"},
    {"id": "L4.candidate_eliminated", "layer": "L4", "required": True,
     "severity": "critical", "title": "candidate no longer triggers the oracle"},
    {"id": "L4.independent_oracle", "layer": "L4", "required": True,
     "severity": "critical", "title": "oracle is independent of the generator"},
    {"id": "L5.semantic_cases", "layer": "L5", "required": True,
     "severity": "high", "title": "semantic cases were executed"},
    {"id": "L5.semantic_preserved", "layer": "L5", "required": True,
     "severity": "critical", "title": "semantic behaviour is preserved"},
    {"id": "L5.bounded_claim", "layer": "L5", "required": True,
     "severity": "high", "title": "semantic claim is bounded"},
    {"id": "L6.regression", "layer": "L6", "required": True,
     "severity": "high", "title": "regression cases pass"},
    {"id": "L6.robustness", "layer": "L6", "required": True,
     "severity": "high", "title": "boundary, environment and repeats pass"},
    {"id": "L7.evidence_refs", "layer": "L7", "required": True,
     "severity": "critical", "title": "evidence references and hashes exist"},
    {"id": "L7.independence", "layer": "L7", "required": True,
     "severity": "critical", "title": "review independence is present"},
    {"id": "L7.no_state_promotion", "layer": "L7", "required": True,
     "severity": "critical", "title": "not_run/inconclusive/analysis_only not promoted"},
    {"id": "L7.claims", "layer": "L7", "required": True,
     "severity": "critical", "title": "claims stay within the declared scope"},
    {"id": "L7.registry_integrity", "layer": "L7", "required": True,
     "severity": "critical", "title": "rule registry digest is canonical"},
)

_LAYER_BY_ID = {layer["id"]: layer for layer in LAYER_SPECS}
_RULE_BY_ID = {rule["id"]: rule for rule in RULE_SPECS}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def registry_descriptor(registry: Sequence[Mapping[str, Any]] | None = None):
    """Return the declarative, JSON-serializable rule registry."""
    source = RULE_SPECS if registry is None else registry
    return [
        {key: rule[key] for key in ("id", "layer", "required", "severity",
                                    "title")}
        for rule in source
    ]


CANONICAL_REGISTRY_SHA256 = hashlib.sha256(
    _canonical_json(registry_descriptor()).encode("utf-8")).hexdigest()


def registry_digest(registry: Sequence[Mapping[str, Any]] | None = None) -> str:
    return hashlib.sha256(
        _canonical_json(registry_descriptor(registry)).encode("utf-8")
    ).hexdigest()


def build_registry() -> dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "supported_versions": list(SUPPORTED_REGISTRY_VERSIONS),
        "digest": CANONICAL_REGISTRY_SHA256,
        "layers": list(LAYER_SPECS),
        "rules": registry_descriptor(),
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _hex64(value: Any) -> bool:
    text = _text(value).strip().lower()
    return len(text) == 64 and all(ch in HEX64 for ch in text)


def _status(status: str, detail: str = "") -> tuple[str, str]:
    return status, detail


def _case_task(case: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(case.get("task"))


def _case_acceptance(case: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(case.get("acceptance"))


def _candidate(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(acceptance.get("candidate"))


def _patch(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(_candidate(acceptance).get("patch"))


def _oracle(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(acceptance.get("oracle"))


def _semantic(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(acceptance.get("semantic"))


def _regression(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(acceptance.get("regression"))


def _state(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(acceptance.get("state"))


def _claims(acceptance: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(acceptance.get("claims"))


def _scope_rank(scope: Any) -> int:
    return {"analysis_only": 0, "vulnerability": 1, "function": 2,
            "module": 3, "whole_program": 4}.get(_text(scope), -1)


def _is_analysis_only(case: Mapping[str, Any]) -> bool:
    task = _case_task(case)
    acceptance = _case_acceptance(case)
    return (_text(task.get("scope")) == "analysis_only"
            or _text(acceptance.get("scope")) == "analysis_only"
            or bool(_claims(acceptance).get("analysis_only")))


# ---------------------------------------------------------------------------
# Rule predicates.  Each returns (status, detail); status is passed/failed/
# not_run.  Missing evidence is not_run; contradictory evidence is failed.
# ---------------------------------------------------------------------------


def _r0_sections(case: Mapping[str, Any]) -> tuple[str, str]:
    if not _text(case.get("case_id")):
        return _status("failed", "case_id is missing")
    if not _case_task(case) or not _case_acceptance(case):
        return _status("failed", "task or acceptance section is missing")
    return _status("passed")


def _r0_hashes(case: Mapping[str, Any]) -> tuple[str, str]:
    task = _case_task(case)
    candidate = _candidate(_case_acceptance(case))
    for field in ("target_sha", "tree_sha"):
        if not _hex64(task.get(field)):
            return _status("failed", f"task {field} is not a 64-hex digest")
    if candidate.get("present") is True and not _hex64(candidate.get("sha256")):
        return _status("failed", "candidate sha256 is not a 64-hex digest")
    return _status("passed")


def _r0_version(case: Mapping[str, Any]) -> tuple[str, str]:
    task = _case_task(case)
    version = _text(task.get("benchmark_version"))
    if not version:
        return _status("not_run", "benchmark version is unknown")
    if version not in SUPPORTED_BENCHMARK_VERSIONS:
        return _status("failed", f"unsupported benchmark version {version!r}")
    return _status("passed")


def _r1_target(case: Mapping[str, Any]) -> tuple[str, str]:
    task = _case_task(case)
    acceptance = _case_acceptance(case)
    target = _dict(acceptance.get("target"))
    for key in ("sha256", "tree_sha", "format", "arch", "abi"):
        expected = _text(task.get(key if key != "sha256" else "target_sha"))
        actual = _text(target.get(key if key != "sha256" else "sha256"))
        if not expected or not actual:
            return _status("not_run", f"target/acceptance {key} is missing")
        if expected != actual:
            return _status("failed", f"target {key} {actual!r} != {expected!r}")
    return _status("passed")


def _r1_scope(case: Mapping[str, Any]) -> tuple[str, str]:
    task = _case_task(case)
    acceptance = _case_acceptance(case)
    task_scope = _text(task.get("scope"))
    acceptance_scope = _text(acceptance.get("scope"))
    claims_scope = _text(_claims(acceptance).get("scope"))
    if _scope_rank(task_scope) < 0:
        return _status("failed", f"unknown task scope {task_scope!r}")
    if _scope_rank(acceptance_scope) > _scope_rank(task_scope):
        return _status("failed", "acceptance scope overclaims task scope")
    if claims_scope and _scope_rank(claims_scope) > _scope_rank(task_scope):
        return _status("failed", "claims scope overclaims task scope")
    return _status("passed")


def _r1_analysis_only(case: Mapping[str, Any]) -> tuple[str, str]:
    if not _is_analysis_only(case):
        return _status("passed")
    acceptance = _case_acceptance(case)
    if _candidate(acceptance).get("present") is True:
        return _status("failed", "analysis_only case carries a candidate")
    if bool(_claims(acceptance).get("verified")):
        return _status("failed", "analysis_only case claims verified")
    return _status("passed")


def _r2_candidate(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    candidate = _candidate(_case_acceptance(case))
    if candidate.get("present") is not True:
        return _status("failed", "candidate bytes are missing")
    if not _hex64(candidate.get("sha256")):
        return _status("failed", "candidate sha256 is malformed")
    return _status("passed")


def _r2_plan(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    candidate = _candidate(_case_acceptance(case))
    layout = _text(candidate.get("layout")) or "same_length"
    plan = _dict(candidate.get("patch_plan"))
    if layout in {"resized", "insert", "cave", "relocated"}:
        if not plan:
            return _status("failed", f"{layout} candidate has no patch plan")
        if not _list(plan.get("operations")):
            return _status("failed", "patch plan has no operations")
    return _status("passed")


def _r2_replay(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    replay = _dict(_candidate(_case_acceptance(case)).get("replay"))
    if replay.get("byte_exact") is not True:
        return _status("failed", "patch replay is not byte-exact")
    if _text(replay.get("replayed_sha256")) != _text(
            _candidate(_case_acceptance(case)).get("sha256")):
        return _status("failed", "replayed digest does not bind candidate")
    return _status("passed")


def _r2_scope(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    candidate = _candidate(_case_acceptance(case))
    scope = _dict(candidate.get("resolved_scope"))
    va, end = scope.get("va"), scope.get("end")
    if not isinstance(va, int) or not isinstance(end, int) or end <= va:
        return _status("failed", "resolved target scope is missing/invalid")
    for change in _list(candidate.get("changed_ranges")):
        item = _dict(change)
        cva, cend = item.get("va"), item.get("end")
        if not isinstance(cva, int) or not isinstance(cend, int):
            return _status("failed", "changed range is malformed")
        if cva < va or cend > end:
            return _status("failed", "changed range exceeds resolved target scope")
    return _status("passed")


def _r2_associated(case: Mapping[str, Any]) -> tuple[str, str]:
    candidate = _candidate(_case_acceptance(case))
    associated = _list(candidate.get("associated_changes"))
    if associated and candidate.get("associated_changes_authorized") is not True:
        return _status("failed", "associated changes are not authorized")
    return _status("passed")


def _r3_abi(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    raw_abi = _candidate(_case_acceptance(case)).get("abi")
    if raw_abi is None:
        return _status("not_run", "ABI evidence metadata is missing")
    abi = _dict(raw_abi)
    if abi.get("blocks") is None:
        return _status("not_run", "ABI evidence blocks are missing")
    blocks = [_dict(item) for item in _list(abi.get("blocks"))]
    if not blocks:
        return _status("failed", "no ABI evidence blocks")
    if abi.get("derived") is not True:
        return _status("failed", "ABI blocks are not derived")
    if not any(isinstance(item.get("size"), int) and item["size"] > 0
               for item in blocks):
        return _status("failed", "ABI block has no positive size")
    return _status("passed")


def _r3_cf(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    candidate = _candidate(_case_acceptance(case))
    control = _dict(candidate.get("control_flow"))
    if _text(control.get("branch_targets")) not in {"resolved", "allowed"}:
        return _status("failed", "branch targets are unresolved/not allowed")
    if _text(control.get("call_targets")) not in {"resolved", "allowed"}:
        return _status("failed", "call targets are unresolved/not allowed")
    if bool(_dict(candidate.get("cave")).get("present")):
        if bool(_dict(candidate.get("cave")).get("executable")) is not True:
            return _status("failed", "code cave is not executable")
    return _status("passed")


def _r4_executed(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    oracle = _oracle(_case_acceptance(case))
    if oracle.get("executed") is None:
        return _status("not_run", "oracle execution status is unknown")
    if oracle.get("executed") is not True:
        return _status("failed", "oracle did not execute")
    if not _text(oracle.get("runner")) or not _text(oracle.get("tier")):
        return _status("not_run", "oracle runner/tier is missing")
    return _status("passed")


def _r4_original(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    value = _oracle(_case_acceptance(case)).get("original_vulnerable")
    if value is None:
        return _status("not_run", "original vulnerability observation is missing")
    return (_status("passed") if value is True
            else _status("failed", "original vulnerability was not observed"))


def _r4_eliminated(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    value = _oracle(_case_acceptance(case)).get("candidate_eliminated")
    if value is None:
        return _status("not_run", "candidate elimination observation is missing")
    return (_status("passed") if value is True
            else _status("failed", "candidate still triggers the oracle"))


def _r4_independent(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    oracle = _oracle(_case_acceptance(case))
    if oracle.get("independent") is not True:
        return _status("failed", "oracle is not independent")
    if oracle.get("generator_verdict_used") is True:
        return _status("failed", "generator verdict was used as the oracle")
    return _status("passed")


def _r5_cases(case: Mapping[str, Any]) -> tuple[str, str]:
    semantic = _semantic(_case_acceptance(case))
    if _is_analysis_only(case):
        return _status("passed")
    cases = semantic.get("cases")
    if cases is None:
        return _status("not_run", "semantic case count is unknown")
    if not isinstance(cases, int) or cases <= 0:
        return _status("failed", "no semantic preservation cases")
    if semantic.get("executed") is not True:
        return _status("failed", "semantic cases were not executed")
    return _status("passed")


def _r5_preserved(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    value = _semantic(_case_acceptance(case)).get("preserved")
    if value is None:
        return _status("not_run", "semantic preservation result is unknown")
    return (_status("passed") if value is True
            else _status("failed", "semantic behaviour changed"))


def _r5_bounded(case: Mapping[str, Any]) -> tuple[str, str]:
    semantic = _semantic(_case_acceptance(case))
    if _text(semantic.get("claim")) != "bounded":
        return _status("failed", "semantic claim is not bounded")
    if semantic.get("equivalence_claimed") is True:
        return _status("failed", "full semantic-equivalence claim is unsupported")
    return _status("passed")


def _r6_regression(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    regression = _regression(_case_acceptance(case))
    cases = regression.get("cases")
    if not isinstance(cases, int) or cases <= 0:
        return _status("failed", "no regression cases")
    if regression.get("executed") is not True:
        return _status("failed", "regression cases were not executed")
    if regression.get("passed") is not True:
        return _status("failed", "regression cases failed")
    return _status("passed")


def _r6_robustness(case: Mapping[str, Any]) -> tuple[str, str]:
    if _is_analysis_only(case):
        return _status("passed")
    regression = _regression(_case_acceptance(case))
    boundary = regression.get("boundary_cases")
    if not isinstance(boundary, int) or boundary <= 0:
        return _status("failed", "no boundary/negative cases")
    if regression.get("boundary_passed") is not True:
        return _status("failed", "boundary/negative cases failed")
    environment = _dict(_case_acceptance(case).get("environment"))
    if environment.get("reproducible") is not True:
        return _status("failed", "environment is not reproducible")
    task = _case_task(case)
    repeats = environment.get("repeats")
    required = task.get("required_repeats", 1)
    if not isinstance(repeats, int) or not isinstance(required, int) \
            or repeats < required:
        return _status("failed", "repeat count is below the task requirement")
    return _status("passed")


def _r7_evidence(case: Mapping[str, Any]) -> tuple[str, str]:
    evidence = [_dict(item) for item in _list(
        _case_acceptance(case).get("evidence"))]
    if not evidence:
        return _status("failed", "no evidence records")
    ids = set()
    for item in evidence:
        evidence_id = _text(item.get("evidence_id"))
        if not evidence_id or evidence_id in ids:
            return _status("failed", "evidence id is missing or duplicated")
        ids.add(evidence_id)
        if not _hex64(item.get("sha256")):
            return _status("failed", "evidence sha256 is malformed")
        if _text(item.get("mode")) not in {"static", "dynamic"}:
            return _status("failed", "evidence mode is invalid")
    return _status("passed")


def _r7_independence(case: Mapping[str, Any]) -> tuple[str, str]:
    independence = _dict(_case_acceptance(case).get("independence"))
    authors = {_text(item) for item in _list(independence.get("authors"))}
    reviewers = {_text(item) for item in _list(independence.get("reviewers"))}
    authors.discard("")
    reviewers.discard("")
    if not authors or not reviewers:
        return _status("failed", "author/reviewer independence is missing")
    if independence.get("self_review") is True:
        return _status("failed", "self review is not independent")
    if independence.get("shared_source") is True:
        return _status("failed", "shared-source review is not independent")
    if authors & reviewers:
        return _status("failed", "author is also a reviewer")
    return _status("passed")


def _r7_no_promotion(case: Mapping[str, Any]) -> tuple[str, str]:
    acceptance = _case_acceptance(case)
    state = _state(acceptance)
    claims = _claims(acceptance)
    status = _text(state.get("status"))
    if status in {"not_run", "inconclusive", "analysis_only"} \
            and claims.get("verified") is True:
        return _status("failed", f"{status} state claims verified")
    if _is_analysis_only(case) and claims.get("verified") is True:
        return _status("failed", "analysis_only claims verified")
    return _status("passed")


def _r7_claims(case: Mapping[str, Any]) -> tuple[str, str]:
    task = _case_task(case)
    claims = _claims(_case_acceptance(case))
    if claims.get("whole_image") is True:
        return _status("failed", "unsupported whole_image claim")
    scope = _text(claims.get("scope"))
    if scope and _scope_rank(scope) > _scope_rank(_text(task.get("scope"))):
        return _status("failed", "claim exceeds task scope")
    if claims.get("analysis_only") is True and claims.get("verified") is True:
        return _status("failed", "analysis_only verified claim")
    return _status("passed")


def _r7_registry(case: Mapping[str, Any]) -> tuple[str, str]:
    # The canonical digest/version check is enforced by evaluate(); this rule
    # exists so a mutated registry has an explicit observable failure.
    return _status("passed")


RULE_PREDICATES = {
    "L0.required_sections": _r0_sections,
    "L0.identity_hashes": _r0_hashes,
    "L0.registry_version": _r0_version,
    "L1.target_identity": _r1_target,
    "L1.scope_policy": _r1_scope,
    "L1.analysis_only_state": _r1_analysis_only,
    "L2.candidate_present": _r2_candidate,
    "L2.patch_plan": _r2_plan,
    "L2.replay_exact": _r2_replay,
    "L2.target_scope": _r2_scope,
    "L2.associated_changes": _r2_associated,
    "L3.abi_blocks": _r3_abi,
    "L3.control_flow": _r3_cf,
    "L4.oracle_executed": _r4_executed,
    "L4.original_vulnerable": _r4_original,
    "L4.candidate_eliminated": _r4_eliminated,
    "L4.independent_oracle": _r4_independent,
    "L5.semantic_cases": _r5_cases,
    "L5.semantic_preserved": _r5_preserved,
    "L5.bounded_claim": _r5_bounded,
    "L6.regression": _r6_regression,
    "L6.robustness": _r6_robustness,
    "L7.evidence_refs": _r7_evidence,
    "L7.independence": _r7_independence,
    "L7.no_state_promotion": _r7_no_promotion,
    "L7.claims": _r7_claims,
    "L7.registry_integrity": _r7_registry,
}


def _decision_for(case: Mapping[str, Any], failed: list[str],
                  not_run: list[str], registry_ok: bool) -> tuple[str, str]:
    if failed:
        return "rejected", "failed required rules: " + ", ".join(failed)
    if not_run:
        return "not_run", "required rules lack evidence: " + ", ".join(not_run)
    if _is_analysis_only(case):
        return "analysis_only", "analysis-only scope is never verified"
    state = _state(_case_acceptance(case))
    status = _text(state.get("status"))
    if status == "inconclusive":
        return "inconclusive", "acceptance state is explicitly inconclusive"
    if status == "not_run":
        return "not_run", "acceptance state is explicitly not_run"
    if status == "analysis_only":
        return "analysis_only", "acceptance state is analysis_only"
    if not registry_ok:
        return "rejected", "rule registry digest/version is not canonical"
    return "verified", "all required layers passed"


def evaluate(case: Mapping[str, Any], *,
             registry: Sequence[Mapping[str, Any]] | None = None,
             registry_version: str = REGISTRY_VERSION) -> dict[str, Any]:
    """Evaluate one acceptance case through L0-L7, fail closed."""
    case = _dict(case)
    registry = tuple(registry or RULE_SPECS)
    registry_ok = (registry_digest(registry) == CANONICAL_REGISTRY_SHA256)
    version_ok = registry_version in SUPPORTED_REGISTRY_VERSIONS
    if not version_ok:
        return {
            "schema_version": SCHEMA_VERSION,
            "case_id": _text(case.get("case_id")),
            "registry_version": _text(registry_version),
            "decision": "not_run",
            "verified": False,
            "layers": [],
            "rules": [],
            "failed_rules": [],
            "not_run_rules": [],
            "reasons": [f"unsupported acceptance registry version "
                        f"{registry_version!r}; historical replay is not "
                        f"upgraded"],
            "registry_ok": False,
        }
    rule_rows: list[dict[str, Any]] = []
    failed: list[str] = []
    not_run: list[str] = []
    for spec in registry:
        rule_id = _text(spec.get("id"))
        predicate = RULE_PREDICATES.get(rule_id)
        if predicate is None:
            failed.append(rule_id or "<unknown>")
            rule_rows.append({
                "id": rule_id or "<unknown>",
                "layer": _text(spec.get("layer") or "L7"),
                "status": "failed",
                "detail": "rule has no implementation",
            })
            continue
        status, detail = predicate(case)
        if rule_id == "L7.registry_integrity" and not registry_ok:
            status, detail = "failed", "rule registry digest is not canonical"
        row = {
            "id": rule_id,
            "layer": _text(spec.get("layer") or "L7"),
            "required": bool(spec.get("required", True)),
            "status": status,
            "detail": detail,
        }
        rule_rows.append(row)
        if status == "failed" and bool(spec.get("required", True)):
            failed.append(rule_id)
        elif status == "not_run" and bool(spec.get("required", True)):
            not_run.append(rule_id)
    decision, reason = _decision_for(case, failed, not_run, registry_ok)
    layer_rows = []
    for layer in LAYER_SPECS:
        rules = [row for row in rule_rows if row["layer"] == layer["id"]]
        statuses = [row["status"] for row in rules]
        if "failed" in statuses:
            status = "failed"
        elif "not_run" in statuses:
            status = "not_run"
        else:
            status = "passed"
        layer_rows.append({
            "id": layer["id"],
            "title": layer["title"],
            "status": status,
            "rules": [row["id"] for row in rules],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": _text(case.get("case_id")),
        "registry_version": registry_version,
        "decision": decision,
        "verified": decision == "verified",
        "layers": layer_rows,
        "rules": rule_rows,
        "failed_rules": sorted(set(failed)),
        "not_run_rules": sorted(set(not_run)),
        "reasons": [reason],
        "registry_ok": registry_ok,
    }


def replay_historical(case: Mapping[str, Any], *,
                      registry_version: str = "1.0.0") -> dict[str, Any]:
    """Replay an older case without upgrading it to a current pass."""
    result = evaluate(case, registry_version=registry_version)
    result["replayed"] = True
    result["upgraded"] = False
    result["historical_note"] = (
        "historical replay: legacy acceptance registries are replayed as not_run, never promoted")
    return result


# ---------------------------------------------------------------------------
# Mutation runner
# ---------------------------------------------------------------------------

MUTATION_SPECS: tuple[dict[str, Any], ...] = (
    {"id": "M-rule-required-disabled", "family": "rule",
     "expected_rule": "L7.registry_integrity",
     "description": "disable a required patch rule in the registry"},
    {"id": "M-evidence-refs-missing", "family": "evidence",
     "expected_rule": "L7.evidence_refs",
     "description": "remove all evidence records"},
    {"id": "M-evidence-hash-tampered", "family": "evidence",
     "expected_rule": "L7.evidence_refs",
     "description": "replace an evidence digest with a malformed value"},
    {"id": "M-scope-inflation", "family": "scope",
     "expected_rule": "L1.scope_policy",
     "description": "inflate the acceptance scope to whole_program"},
    {"id": "M-analysis-only-verified", "family": "state",
     "expected_rule": "L7.no_state_promotion",
     "description": "claim verified on an analysis_only state"},
    {"id": "M-not-run-verified", "family": "state",
     "expected_rule": "L7.no_state_promotion",
     "description": "claim verified on a not_run state"},
    {"id": "M-inconclusive-verified", "family": "state",
     "expected_rule": "L7.no_state_promotion",
     "description": "claim verified on an inconclusive state"},
    {"id": "M-oracle-not-run", "family": "oracle",
     "expected_rule": "L4.oracle_executed",
     "description": "remove the oracle execution evidence"},
    {"id": "M-oracle-self-verdict", "family": "oracle",
     "expected_rule": "L4.independent_oracle",
     "description": "use the generator verdict as the oracle"},
    {"id": "M-layout-no-plan", "family": "layout",
     "expected_rule": "L2.patch_plan",
     "description": "resized candidate without a patch plan"},
    {"id": "M-abi-missing", "family": "layout",
     "expected_rule": "L3.abi_blocks",
     "description": "layout candidate without ABI blocks"},
    {"id": "M-associated-unauthorized", "family": "scope",
     "expected_rule": "L2.associated_changes",
     "description": "unauthorized associated rodata/header change"},
    {"id": "M-regression-missing", "family": "regression",
     "expected_rule": "L6.regression",
     "description": "remove regression cases"},
    {"id": "M-independence-self-review", "family": "state",
     "expected_rule": "L7.independence",
     "description": "replace independent review with self review"},
)


def _mutate(base: Mapping[str, Any], mutation_id: str) -> dict[str, Any]:
    case = copy.deepcopy(dict(base))
    task = _case_task(case)
    acceptance = _case_acceptance(case)
    candidate = _candidate(acceptance)
    if mutation_id == "M-rule-required-disabled":
        return copy.deepcopy(dict(base))  # registry mutation is handled below
    if mutation_id == "M-evidence-refs-missing":
        acceptance["evidence"] = []
    elif mutation_id == "M-evidence-hash-tampered":
        acceptance["evidence"][0]["sha256"] = "not-a-digest"
    elif mutation_id == "M-scope-inflation":
        acceptance["scope"] = "whole_program"
        _claims(acceptance)["scope"] = "whole_program"
    elif mutation_id == "M-analysis-only-verified":
        task["scope"] = "analysis_only"
        acceptance["scope"] = "analysis_only"
        _claims(acceptance)["analysis_only"] = True
        _claims(acceptance)["verified"] = True
        _state(acceptance)["status"] = "analysis_only"
    elif mutation_id == "M-not-run-verified":
        _state(acceptance)["status"] = "not_run"
        _claims(acceptance)["verified"] = True
    elif mutation_id == "M-inconclusive-verified":
        _state(acceptance)["status"] = "inconclusive"
        _claims(acceptance)["verified"] = True
    elif mutation_id == "M-oracle-not-run":
        _oracle(acceptance)["executed"] = False
    elif mutation_id == "M-oracle-self-verdict":
        _oracle(acceptance)["independent"] = False
        _oracle(acceptance)["generator_verdict_used"] = True
    elif mutation_id == "M-layout-no-plan":
        candidate["layout"] = "resized"
        candidate["patch_plan"] = None
    elif mutation_id == "M-abi-missing":
        candidate["abi"] = {"blocks": [], "derived": False}
    elif mutation_id == "M-associated-unauthorized":
        candidate["associated_changes"] = [{"kind": "rodata_message",
                                             "va": 0x2000,
                                             "end": 0x2004}]
        candidate["associated_changes_authorized"] = False
    elif mutation_id == "M-regression-missing":
        acceptance["regression"] = {"cases": 0, "executed": False,
                                    "passed": False, "boundary_cases": 0,
                                    "boundary_passed": False}
    elif mutation_id == "M-independence-self-review":
        acceptance["independence"]["self_review"] = True
    return case


def run_mutations(base_case: Mapping[str, Any],
                  registry: Sequence[Mapping[str, Any]] | None = None,
                  registry_version: str = REGISTRY_VERSION) -> dict[str, Any]:
    registry = tuple(registry or RULE_SPECS)
    rows: list[dict[str, Any]] = []
    for spec in MUTATION_SPECS:
        mutation_id = spec["id"]
        if mutation_id == "M-rule-required-disabled":
            mutated = [copy.deepcopy(dict(rule)) for rule in registry]
            target = next(rule for rule in mutated
                          if rule["id"] == "L2.patch_plan")
            target["required"] = False
            case = copy.deepcopy(dict(base_case))
            result = evaluate(case, registry=mutated,
                              registry_version=registry_version)
        else:
            case = _mutate(base_case, mutation_id)
            result = evaluate(case, registry=registry,
                              registry_version=registry_version)
        failed = set(result.get("failed_rules") or [])
        not_run = set(result.get("not_run_rules") or [])
        detected = (result.get("decision") != "verified"
                    and (spec["expected_rule"] in failed
                         or spec["expected_rule"] in not_run))
        rows.append({
            "mutation_id": mutation_id,
            "family": spec["family"],
            "description": spec["description"],
            "expected_rule": spec["expected_rule"],
            "decision": result.get("decision"),
            "detected": detected,
            "detected_rules": sorted(failed | not_run),
            "false_accept": result.get("decision") == "verified",
            "reasons": result.get("reasons") or [],
        })
    total = len(rows)
    detected_count = sum(1 for row in rows if row["detected"])
    false_accepts = sum(1 for row in rows if row["false_accept"])
    by_family: dict[str, dict[str, int]] = {}
    for row in rows:
        family = row["family"]
        bucket = by_family.setdefault(family, {"total": 0, "detected": 0,
                                               "false_accept": 0})
        bucket["total"] += 1
        bucket["detected"] += int(row["detected"])
        bucket["false_accept"] += int(row["false_accept"])
    return {
        "schema_version": SCHEMA_VERSION,
        "total": total,
        "detected": detected_count,
        "detection_rate": detected_count / total if total else None,
        "false_accepts": false_accepts,
        "by_family": by_family,
        "mutations": rows,
    }


def summarize_cases(cases: Iterable[Mapping[str, Any]],
                    registry: Sequence[Mapping[str, Any]] | None = None) -> dict:
    results = [evaluate(case, registry=registry) for case in cases]
    expected = [_text(case.get("expected_decision")) for case in cases]
    ok = [result["decision"] == exp for result, exp in zip(results, expected)]
    false_accepts = [
        result["case_id"] for result, exp in zip(results, expected)
        if result["decision"] == "verified" and exp != "verified"
    ]
    false_rejects = [
        result["case_id"] for result, exp in zip(results, expected)
        if exp == "verified" and result["decision"] != "verified"
    ]
    return {
        "cases": results,
        "case_count": len(results),
        "matched": sum(1 for value in ok if value),
        "false_accept_cases": false_accepts,
        "false_reject_cases": false_rejects,
        "ok": not false_accepts and not false_rejects,
    }
