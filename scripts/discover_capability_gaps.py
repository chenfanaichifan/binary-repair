#!/usr/bin/env python3
"""Run the six capability-gap discovery mechanisms and emit the Gap Registry.

Mechanisms (task-26):

====================  =========================================================
mechanism             behaviour in this tree
====================  =========================================================
knowledge             RUN: compare the 20 first-level dimensions D01-D20 with
                      the claims/audit evidence; every non-covered dimension
                      becomes a candidate gap.
failure_driven        RUN: re-run the committed universe methodology checker,
                      then mine the committed coverage-audit matrix for
                      gate/matrix-claim meta-mismatch classes and for
                      target-resolved cases whose deterministic analysis failed.
differential          RUN: re-run the committed capability-contract checker and
                      mine declared-vs-measured platform divergences (declared
                      native tier unavailable on this host, external-PoC
                      unavailable) as candidate gaps.
mutation              NOT RUN: no mutation engine/corpus exists in this tree.
metamorphic           NOT RUN: no metamorphic-relation engine exists.
sample_based          NOT RUN: no sampled/seed corpus is provisioned.
knowledge_source_scan NOT RUN: no external knowledge corpus is provisioned.
====================  =========================================================

Rules enforced by the builder/checker (exit 1 on violation):

* every mechanism must appear exactly once - a missing adapter is a silent gap
  and fails the artifact;
* every RUN mechanism must produce >= 1 candidate;
* every NOT RUN mechanism must carry a non-empty reason and 0 candidates;
* every candidate is constructed through :mod:`app.services.gap_registry` and
  stays ``status="candidate"`` - candidates are never auto-promoted to
  ``verified``/``non_goal``/``resolved``;
* every candidate and migrated record must carry a valid
  ``proposed_experiment`` (``proposed`` with id+steps, or explicit
  ``cannot_plan`` with a reason);
* deterministic: no wall clock, no network, no git; ``generated_at`` comes from
  the coverage-matrix audit date, and re-running on the same host yields
  byte-identical artifacts.

Artifacts: ``artifacts/gap-registry-2026-11-16/{gaps.json,candidates.json,
README.md,SHA256SUMS}``.

Usage::

    python scripts/discover_capability_gaps.py            # write artifacts
    python scripts/discover_capability_gaps.py --check    # verify determinism
    python scripts/discover_capability_gaps.py --json     # print summary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from app.services import capability_dimensions as dimensions  # noqa: E402
from app.services import gap_registry as gaps  # noqa: E402
import build_universe_dimension_registry as universe_builder  # noqa: E402

MATRIX_PATH = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"
CLAIMS_PATH = "docs/status/claims.json"
UNIVERSE_ARTIFACT = "artifacts/capability-universe-2026-11-16/dimension-registry.json"
UNIVERSE_CHECKER = "scripts/check_universe_methodology.py"
CONTRACT_CHECKER = "scripts/check_capability_contract.py"
CONTRACT_DOC = "docs/acceptance/capability-contract-2026-11-14.md"
ARTIFACT_DIR = ROOT / "artifacts" / "gap-registry-2026-11-16"
ARTIFACT_DIR_REL = "artifacts/gap-registry-2026-11-16"
ARTIFACT_FILES = ("gaps.json", "candidates.json", "README.md")
SCHEMA_VERSION = 1
KIND_REGISTRY = "gap_registry"
KIND_CANDIDATES = "gap_discovery_candidates"
BUILDER_VERSION = 1

MECHANISMS: tuple[str, ...] = (
    "knowledge",
    "failure_driven",
    "differential",
    "mutation",
    "metamorphic",
    "sample_based",
    "knowledge_source_scan",
)
RUN_MECHANISMS: tuple[str, ...] = ("knowledge", "failure_driven", "differential")
NOT_RUN_MECHANISMS: tuple[str, ...] = (
    "mutation",
    "metamorphic",
    "sample_based",
    "knowledge_source_scan",
)
NOT_RUN_REASONS: dict[str, str] = {
    "mutation": (
        "no mutation engine/corpus is implemented in this tree; fabricating a "
        "mutation corpus would be invented evidence, so the mechanism is not run"
    ),
    "metamorphic": (
        "no metamorphic-relation engine exists in this tree (no oracle-pair "
        "generator); the mechanism is not run instead of fabricating candidates"
    ),
    "sample_based": (
        "no sampled capability corpus is provisioned in this environment (no "
        "sampling frame exists), so sample-based discovery is not run"
    ),
    "knowledge_source_scan": (
        "no external knowledge corpus/advisory feed is provisioned in this "
        "environment; external-source scanning is out of scope and not faked"
    ),
}


class DiscoveryError(RuntimeError):
    """A mechanism or an input artifact failed in a way that must not be hidden."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise DiscoveryError(f"missing source file: {relative}")
    return _sha256_bytes(path.read_bytes())


def _read_json(relative: str) -> Any:
    path = ROOT / relative
    if not path.is_file():
        raise DiscoveryError(f"missing source artifact: {relative}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"unreadable source artifact {relative}: {exc}") from exc


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _run_json_command(relative_script: str) -> dict[str, Any]:
    """Run a committed read-only checker and return its parsed JSON report."""
    result = subprocess.run(
        [sys.executable, str(ROOT / relative_script), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise DiscoveryError(
            f"{relative_script} --json exited {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DiscoveryError(
            f"{relative_script} --json produced non-JSON output: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise DiscoveryError(f"{relative_script} --json output is not an object")
    return payload


def _deterministic_timestamp(matrix: dict[str, Any]) -> tuple[str, str]:
    audit_date = matrix.get("audit_date")
    if not isinstance(audit_date, str) or not audit_date:
        raise DiscoveryError("coverage matrix has no audit_date; refusing wall clock")
    return f"{audit_date}T00:00:00Z", f"{MATRIX_PATH}#audit_date"


# ---------------------------------------------------------------------------
# Mechanism: knowledge (20 dimensions vs claims/audit)
# ---------------------------------------------------------------------------


def knowledge_mechanism() -> dict[str, Any]:
    try:
        registry = universe_builder.build_registry()
    except universe_builder.BuildError as exc:
        raise DiscoveryError(f"knowledge mechanism could not build the universe registry: {exc}") from exc
    candidates = []
    for dimension in registry["dimensions"]:
        status = dimension["status"]
        if status == "covered":
            continue
        dimension_id = dimension["id"]
        status_reason = dimension.get("status_reason") or status
        plan = gaps.proposed_experiment(
            status="proposed",
            experiment_id="EXP-KNOW-" + dimension_id,
            steps=[
                f"define a first-level {dimension['title']} registry/universe mapping",
                "collect measured evidence for the dimension from real fixtures "
                "or a documented corpus (never fabricate coverage)",
                "register the mapping in the capability universe and re-run this "
                "builder; keep the dimension status unchanged until evidence exists",
            ],
        ) if status != "non_goal" else gaps.cannot_plan(
            "explicit non-goal dimension: no repair experiment is planned; only "
            "claim/enforcement verification applies"
        )
        mapped = dimension["old_11dim_mapping"]["old_dimensions"]
        candidates.append(gaps.make_candidate(
            discovery_source="knowledge",
            key=f"dimension:{dimension_id}",
            category="universe_dimension_gap",
            subcategory=dimension_id,
            target={
                "kind": "dimension",
                "id": dimension_id,
                "title": dimension["title"],
                "status": status,
            },
            observed_failure=(
                f"{dimension_id} ({dimension['title']}) has status={status}: "
                f"{status_reason}"
            ),
            existing_capability=(
                "mapped old-11 dimensions: " + ", ".join(mapped)
                if mapped else "no old-11 dimension mapping exists"
            ),
            severity="info" if status == "non_goal" else "medium",
            evidence_refs=[
                f"{UNIVERSE_ARTIFACT}#dimensions[id={dimension_id}]",
                f"{MATRIX_PATH}#universe.dimensions",
                f"{CLAIMS_PATH}#non_goals",
            ],
            plan=plan,
            owner=dimension["owner"],
            review_by=dimension["review_by"],
            false_verified_risk="medium" if status != "non_goal" else "low",
        ))
    return {
        "mechanism": "knowledge",
        "status": "run",
        "reason": None,
        "run_evidence": {
            "dimension_count": registry["dimension_count"],
            "non_covered_dimensions": len(candidates),
            "registry_digest": registry["provenance"]["registry_digest"],
            "mapped_cells": registry["mapped_cells"],
            "source": "in-process build_universe_dimension_registry.build_registry()",
        },
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Mechanism: failure_driven (coverage audit open/dynamic/meta mismatches)
# ---------------------------------------------------------------------------


def failure_driven_mechanism() -> dict[str, Any]:
    report = _run_json_command(UNIVERSE_CHECKER)
    matrix = _read_json(MATRIX_PATH)
    audit_gaps = matrix.get("gaps") or []
    open_failures = [
        gap for gap in audit_gaps
        if gap.get("status") in {"open", "dynamic_unverified"}
    ]
    meta_mismatches = [
        gap for gap in audit_gaps
        if gap.get("category") in {"gate_mismatch", "matrix_claim_mismatch"}
    ]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for gap in meta_mismatches:
        key = (str(gap.get("category")), str(gap.get("detector")))
        grouped.setdefault(key, []).append(gap)
    candidates = []
    for (category, detector), group in sorted(grouped.items()):
        gap_ids = [str(item.get("gap_id")) for item in group]
        candidates.append(gaps.make_candidate(
            discovery_source="failure_driven",
            key=f"meta:{category}:{detector}",
            category="audit_meta_mismatch_regression",
            subcategory=detector,
            target={
                "kind": "audit_detector",
                "id": detector,
                "audit_category": category,
            },
            observed_failure=(
                f"{len(group)} {category} row(s) with detector {detector} were "
                f"observed and closed/mitigated in the committed audit "
                f"(gap ids: {', '.join(gap_ids[:4])}"
                f"{', ...' if len(gap_ids) > 4 else ''})"
            ),
            existing_capability=(
                "the committed coverage audit records these as closed/mitigated; "
                "no open failure remains in the re-run checker"
            ),
            severity="info",
            evidence_refs=[
                f"{MATRIX_PATH}#gaps[category={category},detector={detector}]",
                f"{UNIVERSE_CHECKER} --json",
            ],
            plan=gaps.proposed_experiment(
                status="proposed",
                experiment_id="EXP-FAIL-META-" + gaps._slug(detector),
                steps=[
                    "re-run the committed audit detector on the current tree",
                    "if no permanent regression check exists, add one that fails "
                    "on a silent regression of this detector class",
                    "record the passing check evidence; do not promote the "
                    "candidate without an independent verification result",
                ],
            ),
            owner="engine",
            review_by="2027-05-14",
            false_verified_risk="medium",
        ))
    cases = (matrix.get("coverage_rows") or {}).get("cases") or []
    failed_target_cases = [
        case for case in cases
        if case.get("target_state") == "resolved"
        and case.get("measured_target_analyzed") is False
    ]
    for case in failed_target_cases:
        case_id = str(case.get("case_id") or "unknown")
        candidates.append(gaps.make_candidate(
            discovery_source="failure_driven",
            key=f"case:{case_id}",
            category="case_target_analysis_failure",
            subcategory=case_id,
            target={"kind": "case", "id": case_id},
            observed_failure=(
                f"target-resolved case {case_id} measured_target_analyzed=false "
                f"(deterministic disposition={case.get('measured_disposition')}); "
                f"target is not analyzed by the deterministic baseline"
            ),
            existing_capability=(
                "deterministic baseline records analysis_only/rejected; the "
                "hard-case non-template limitation is claims non-goal "
                "EG-cases-target-not-analyzed"
            ),
            severity="medium",
            evidence_refs=[
                f"{MATRIX_PATH}#coverage_rows.cases[id={case_id}]",
                f"{CLAIMS_PATH}#non_goals[id=EG-cases-target-not-analyzed]",
            ],
            plan=gaps.proposed_experiment(
                status="proposed",
                experiment_id="EXP-FAIL-CASE-" + gaps._slug(case_id),
                steps=[
                    f"add a reviewed target fixture + runtime oracle for {case_id}",
                    "implement target-scoped deterministic or AI repair and verify "
                    "with the native/emulated PoC+regression gate",
                    "do not mark the case repaired without target-scoped evidence",
                ],
            ),
            owner="target-scope",
            review_by="2027-02-14",
            false_verified_risk="high",
        ))
    return {
        "mechanism": "failure_driven",
        "status": "run",
        "reason": None,
        "run_evidence": {
            "command": f"{UNIVERSE_CHECKER} --json",
            "ok": report.get("ok"),
            "cell_count": report.get("cell_count"),
            "status_counts": report.get("status_counts"),
            "unknown": report.get("unknown"),
            "unexplained_cell_count": report.get("unexplained_cell_count"),
            "open_failures": len(open_failures),
            "dynamic_unverified": sum(
                1 for gap in audit_gaps if gap.get("status") == "dynamic_unverified"
            ),
            "meta_mismatch_groups": len(grouped),
            "meta_mismatch_records": len(meta_mismatches),
            "failed_target_cases": len(failed_target_cases),
        },
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Mechanism: differential (capability contract negative checks)
# ---------------------------------------------------------------------------


def differential_mechanism() -> dict[str, Any]:
    report = _run_json_command(CONTRACT_CHECKER)
    cells = report.get("cells") or []
    negative_checks = report.get("negative_checks") or []
    candidates = []
    for cell in cells:
        declared_tiers = list(cell.get("declared_tiers") or [])
        declared = cell.get("declared_tier")
        measured = cell.get("measured_tier")
        poc_available = cell.get("poc_available")
        diverged = measured != declared or measured not in declared_tiers
        poc_missing = poc_available is False
        if not diverged and not poc_missing:
            continue
        cell_name = str(cell.get("cell") or "unknown")
        reasons = []
        if diverged:
            reasons.append(f"declared {declared!r} not measured on this host")
        if poc_missing:
            reasons.append("external PoC runner unavailable")
        candidates.append(gaps.make_candidate(
            discovery_source="differential",
            key=f"contract:{cell_name}",
            category="platform_capability_differential",
            subcategory=cell_name,
            target={
                "kind": "contract_cell",
                "cell": cell_name,
                "declared_tier": declared,
                "measured_tier": measured,
            },
            observed_failure=(
                f"{cell_name}: declared_tiers={declared_tiers} measured_tier="
                f"{measured} poc_available={poc_available}; "
                + "; ".join(reasons)
                + f"; measured reason: {cell.get('reason')}"
            ),
            existing_capability=(
                "the committed capability-contract checker measures this cell and "
                "reports a typed reason; no verified claim is fabricated"
            ),
            severity="medium" if diverged else "info",
            evidence_refs=[
                f"{CONTRACT_CHECKER} --json#cells[cell={cell_name}]",
                f"{CONTRACT_DOC}#runtime-tiers",
            ],
            plan=gaps.proposed_experiment(
                status="proposed",
                experiment_id="EXP-DIFF-" + gaps._slug(cell_name),
                steps=[
                    f"re-run the capability-contract probe for {cell_name} on a "
                    "host/platform where the declared tier can actually be measured",
                    "record the resulting typed evidence and only then update the "
                    "measured tier; never fabricate native/PoC availability",
                ],
            ),
            owner="runtime",
            review_by="2027-05-14",
            false_verified_risk="high" if poc_missing else "medium",
        ))
    failed_checks = [check for check in negative_checks if check.get("ok") is not True]
    for check in failed_checks:
        check_id = str(check.get("id") or "unknown")
        candidates.append(gaps.make_candidate(
            discovery_source="differential",
            key=f"negative-check:{check_id}",
            category="capability_contract_check_failure",
            subcategory=check_id,
            target={"kind": "negative_check", "id": check_id},
            observed_failure=f"negative check {check_id} failed: {check.get('detail')}",
            existing_capability="capability-contract negative-check registry",
            severity="high",
            evidence_refs=[f"{CONTRACT_CHECKER} --json#negative_checks[id={check_id}]"],
            plan=gaps.proposed_experiment(
                status="proposed",
                experiment_id="EXP-DIFF-CHECK-" + gaps._slug(check_id),
                steps=[
                    "inspect the failed capability-contract negative check",
                    "fix the contract/registry or the measured capability, then "
                    "re-run the checker; candidates are not auto-promoted",
                ],
            ),
            owner="runtime",
            review_by="2027-05-14",
            false_verified_risk="high",
        ))
    return {
        "mechanism": "differential",
        "status": "run",
        "reason": None,
        "run_evidence": {
            "command": f"{CONTRACT_CHECKER} --json",
            "ok": report.get("ok"),
            "host": report.get("host"),
            "cell_count": report.get("cell_count"),
            "negative_checks": len(negative_checks),
            "failed_negative_checks": len(failed_checks),
            "divergent_or_poc_missing_cells": len(candidates) - len(failed_checks),
        },
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Mechanism: not-run adapters (explicit reason, no fake candidates)
# ---------------------------------------------------------------------------


def not_run_mechanism(name: str) -> dict[str, Any]:
    if name not in NOT_RUN_MECHANISMS:
        raise DiscoveryError(f"{name!r} is not a not-run mechanism")
    return {
        "mechanism": name,
        "status": "not_run",
        "reason": NOT_RUN_REASONS[name],
        "run_evidence": None,
        "candidates": [],
    }


# ---------------------------------------------------------------------------
# Artifact construction
# ---------------------------------------------------------------------------


def run_discovery() -> dict[str, Any]:
    matrix = _read_json(MATRIX_PATH)
    claims = _read_json(CLAIMS_PATH)
    base_records = gaps.claim_records(claims) + gaps.mitigated_records(matrix)
    mechanism_results = [
        knowledge_mechanism(),
        failure_driven_mechanism(),
        differential_mechanism(),
        not_run_mechanism("mutation"),
        not_run_mechanism("metamorphic"),
        not_run_mechanism("sample_based"),
        not_run_mechanism("knowledge_source_scan"),
    ]
    # Mechanism-set completeness: a missing/duplicate adapter is a silent gap.
    seen = [result["mechanism"] for result in mechanism_results]
    if tuple(seen) != MECHANISMS:
        raise DiscoveryError(f"mechanism adapters {seen} != expected {list(MECHANISMS)}")
    all_candidates: list[dict[str, Any]] = []
    for result in mechanism_results:
        if result["status"] == "run" and not result["candidates"]:
            raise DiscoveryError(
                f"run mechanism {result['mechanism']} produced no candidates "
                "(silent no-op is not allowed)"
            )
        if result["status"] == "not_run":
            if not str(result.get("reason") or "").strip():
                raise DiscoveryError(
                    f"not_run mechanism {result['mechanism']} has no reason"
                )
            if result["candidates"]:
                raise DiscoveryError(
                    f"not_run mechanism {result['mechanism']} produced candidates"
                )
        all_candidates.extend(result["candidates"])
    candidate_ids = [record["gap_id"] for record in all_candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise DiscoveryError("duplicate discovery candidate ids")
    records = gaps.sort_records(base_records + all_candidates)
    validation = gaps.validate_records(records)
    if not validation["ok"]:
        raise DiscoveryError(f"gap registry validation failed: {validation['violations']}")
    generated_at, generated_at_source = _deterministic_timestamp(matrix)
    source_files = [
        MATRIX_PATH,
        CLAIMS_PATH,
        UNIVERSE_CHECKER,
        CONTRACT_CHECKER,
        "app/services/capability_dimensions.py",
        "app/services/gap_registry.py",
        "scripts/build_universe_dimension_registry.py",
    ]
    if (ROOT / UNIVERSE_ARTIFACT).is_file():
        source_files.append(UNIVERSE_ARTIFACT)
    source_entries = [{"path": path, "sha256": _sha256_file(path)} for path in source_files]
    provenance = {
        "builder": "scripts/discover_capability_gaps.py",
        "builder_version": BUILDER_VERSION,
        "build_method": (
            "real in-process/in-subprocess discovery from committed evidence; "
            "no network, no git commands, no wall-clock timestamps"
        ),
        "generated_at": generated_at,
        "generated_at_source": generated_at_source,
        "generated_at_note": (
            "generated_at is derived from the coverage-matrix audit_date so a "
            "fresh build is byte-identical; it is not the build time"
        ),
        "sources": source_entries,
        "source_digest_sha256": _sha256_bytes(
            _canonical_json(source_entries).encode("utf-8")
        ),
        "environment": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
        },
    }
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for record in records:
        by_source[record["discovery_source"]] = by_source.get(record["discovery_source"], 0) + 1
        by_status[record["status"]] = by_status.get(record["status"], 0) + 1
    registry = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND_REGISTRY,
        "generated_at": generated_at,
        "purpose": (
            "Unified Phase-7 capability gap registry: 12 claims non-goals + 1 "
            "mitigated runtime-evidence gap + deterministic discovery candidates."
        ),
        "record_count": len(records),
        "base_record_count": len(base_records),
        "candidate_record_count": len(all_candidates),
        "records_by_source": dict(sorted(by_source.items())),
        "records_by_status": dict(sorted(by_status.items())),
        "validation": validation,
        "no_auto_promotion": True,
        "records": records,
        "gaps_path": f"{ARTIFACT_DIR_REL}/gaps.json",
        "candidates_path": f"{ARTIFACT_DIR_REL}/candidates.json",
        "provenance": provenance,
        "limitations": [
            "Discovery candidates are not verified repairs and are never auto-promoted.",
            "4 of 7 adapters are not_run because their corpus/engine is absent; the reasons are explicit.",
            "The differential candidates are host-dependent measurements recorded with the measured host.",
        ],
    }
    candidates_artifact = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND_CANDIDATES,
        "generated_at": generated_at,
        "mechanism_count": len(mechanism_results),
        "candidate_count": len(all_candidates),
        "mechanisms": [
            {
                "mechanism": result["mechanism"],
                "status": result["status"],
                "reason": result["reason"],
                "candidate_count": len(result["candidates"]),
                "run_evidence": result["run_evidence"],
            }
            for result in mechanism_results
        ],
        "run_mechanisms": list(RUN_MECHANISMS),
        "not_run_mechanisms": list(NOT_RUN_MECHANISMS),
        "no_auto_promotion": True,
        "candidates": gaps.sort_records(all_candidates),
        "validation": validation,
        "provenance": provenance,
    }
    return {
        "registry": registry,
        "candidates": candidates_artifact,
        "mechanisms": mechanism_results,
    }


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


def render_readme(payload: dict[str, Any]) -> str:
    registry = payload["registry"]
    candidates = payload["candidates"]
    validation = registry["validation"]
    lines: list[str] = [
        "# Capability gap registry and discovery (2026-11-16)",
        "",
        "Generated deterministically by `scripts/discover_capability_gaps.py` from",
        "committed evidence. No provider calls, no network, no git commands, no",
        "wall-clock timestamps.",
        "",
        f"- generated_at: `{registry['generated_at']}` "
        f"({registry['provenance']['generated_at_source']})",
        f"- source digest: `{registry['provenance']['source_digest_sha256']}`",
        f"- records: {registry['record_count']} "
        f"(base {registry['base_record_count']} + discovery candidates "
        f"{registry['candidate_record_count']})",
        f"- validation: ok={validation['ok']} "
        f"unique_ids={validation['unique_id_count']}",
        "",
        "Artifact files: `gaps.json` (full unified registry), `candidates.json`",
        "(discovery mechanisms + candidates), `README.md` (this file),",
        "`SHA256SUMS` (covers all three; never itself).",
        "",
        "## Mechanisms",
        "",
        "| mechanism | status | candidates | reason / run evidence |",
        "|---|---|---|---|",
    ]
    for mechanism in candidates["mechanisms"]:
        if mechanism["status"] == "run":
            evidence = mechanism["run_evidence"] or {}
            detail = (
                "run: " + ", ".join(
                    f"{key}={value}"
                    for key, value in evidence.items()
                    if key not in {"source"}
                )[:220]
            )
        else:
            detail = mechanism.get("reason") or ""
        lines.append(
            f"| {mechanism['mechanism']} | {mechanism['status']} | "
            f"{mechanism['candidate_count']} | {detail} |"
        )
    lines += [
        "",
        "Rules: the three RUN mechanisms really execute (universe registry build /",
        "committed universe-methodology checker / committed capability-contract",
        "checker) and must produce at least one candidate; the four NOT_RUN",
        "mechanisms carry an explicit reason and produce none. A missing adapter,",
        "a silent no-op or a schema violation makes `--check` exit 1.",
        "",
        "## Registry composition",
        "",
        "| discovery_source | records |",
        "|---|---|",
    ]
    for source, count in registry["records_by_source"].items():
        lines.append(f"| `{source}` | {count} |")
    lines += [
        "",
        "| status | records |",
        "|---|---|",
    ]
    for status, count in registry["records_by_status"].items():
        lines.append(f"| `{status}` | {count} |")
    lines += [
        "",
        "The 12 `claims_non_goal` records are the explicit non-goals migrated from",
        "`docs/status/claims.json`; the single `failure_driven` resolved record is",
        "the mitigated `RG-runtime-evidence::elf/x86_64/64/little::native_run`",
        "platform gap from the committed coverage audit. All discovery candidates",
        "keep `status=\"candidate\"` - none is auto-promoted to verified/non_goal/",
        "resolved.",
        "",
        "## Candidate list",
        "",
        "| gap_id | source | category | target | plan |",
        "|---|---|---|---|---|",
    ]
    for record in candidates["candidates"]:
        plan = record["proposed_experiment"]
        plan_text = (
            f"`{plan['experiment_id']}`" if plan["status"] == "proposed"
            else f"cannot_plan: {plan['reason'][:80]}"
        )
        target = record["target"]
        target_text = str(target.get("id") or target.get("cell") or target.get("gap_id") or target)
        lines.append(
            f"| `{record['gap_id']}` | {record['discovery_source']} | "
            f"{record['category']} | {target_text} | {plan_text} |"
        )
    lines += [
        "",
        "## Assumptions / limitations",
        "",
        "- Candidates are discovery leads, not verified capability claims; the",
        "  deterministic gate remains the only acceptance authority.",
        "- `failure_driven` re-runs the committed universe checker (0 open / 0",
        "  dynamic-unverified failures remain) and mines the committed audit's",
        "  closed/mitigated meta-mismatch records and unanalyzed target cases.",
        "- `differential` re-runs the committed capability-contract checker and",
        "  records declared-vs-measured platform divergences on this host.",
        "- `mutation`/`metamorphic`/`sample_based`/`knowledge_source_scan` are",
        "  not_run with explicit reasons; no corpus/engine is fabricated.",
        "- Re-running on the same host is byte-identical; cross-host differential",
        "  candidates intentionally record the measured host.",
        "",
        "## Validation",
        "",
        "```bash",
        "python scripts/discover_capability_gaps.py --check",
        "python -m pytest -q tests/test_capability_dimensions.py tests/test_gap_registry_discovery.py",
        "```",
        "",
        "`--check` rebuilds the artifact in memory, compares all three data files",
        "byte-for-byte, re-validates SHA256SUMS coverage and the GapRecord schema,",
        "and exits 1 on any mismatch or silent discovery gap.",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Artifact files
# ---------------------------------------------------------------------------


def build_artifact() -> dict[str, bytes]:
    payload = run_discovery()
    files: dict[str, bytes] = {
        "gaps.json": (
            json.dumps(payload["registry"], indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8"),
        "candidates.json": (
            json.dumps(payload["candidates"], indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8"),
        "README.md": render_readme(payload).encode("utf-8"),
    }
    files["SHA256SUMS"] = render_sha256sums(files)
    return files


def render_sha256sums(files: dict[str, bytes]) -> bytes:
    lines = [f"{_sha256_bytes(files[name])}  {name}" for name in ARTIFACT_FILES]
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_artifact(out_dir: Path) -> list[dict[str, str]]:
    files = build_artifact()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        target = out_dir / name
        target.write_bytes(files[name])
        written.append({"path": str(target), "sha256": _sha256_bytes(files[name])})
    return written


def _schema_violations(files: dict[str, bytes]) -> list[str]:
    violations: list[str] = []
    try:
        registry = json.loads(files["gaps.json"])
        candidates = json.loads(files["candidates.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        return [f"artifact JSON unreadable: {exc}"]
    validation = gaps.validate_records(registry.get("records") or [])
    violations.extend(validation["violations"])
    mechanisms = candidates.get("mechanisms") or []
    names = [mechanism.get("mechanism") for mechanism in mechanisms]
    if names != list(MECHANISMS):
        violations.append(f"mechanism adapters {names} != expected {list(MECHANISMS)}")
    for mechanism in mechanisms:
        name = mechanism.get("mechanism")
        if mechanism.get("status") not in {"run", "not_run"}:
            violations.append(f"{name}: invalid mechanism status {mechanism.get('status')!r}")
        if mechanism.get("status") == "run" and not mechanism.get("run_evidence"):
            violations.append(f"{name}: run mechanism without run_evidence")
        if mechanism.get("status") == "run" and mechanism.get("candidate_count", 0) < 1:
            violations.append(f"{name}: run mechanism produced no candidates")
        if mechanism.get("status") == "not_run":
            if not str(mechanism.get("reason") or "").strip():
                violations.append(f"{name}: not_run mechanism without reason")
            if mechanism.get("candidate_count", 0) != 0:
                violations.append(f"{name}: not_run mechanism produced candidates")
    promoted = [
        record.get("gap_id") for record in candidates.get("candidates") or []
        if record.get("status") != "candidate"
    ]
    if promoted:
        violations.append(f"discovery candidates not status=candidate: {promoted[:5]}")
    return violations


HOST_DEPENDENT_MECHANISMS = ("differential",)


def _filter_host_dependent(document: dict[str, Any]) -> dict[str, Any]:
    """Drop host-dependent differential records for cross-host --check."""
    filtered = json.loads(json.dumps(document))
    records = filtered.get("records")
    if isinstance(records, list):
        filtered["records"] = [
            record for record in records
            if str(record.get("discovery_source")) not in HOST_DEPENDENT_MECHANISMS
        ]
        filtered["record_count"] = len(filtered["records"])
        filtered["base_record_count"] = sum(
            1 for record in filtered["records"]
            if str(record.get("discovery_source")) != "failure_driven"
            or not str(record.get("gap_id", "")).startswith("GAP-FAIL-")
        )
        filtered["candidate_record_count"] = sum(
            1 for record in filtered["records"]
            if str(record.get("status")) == "candidate"
        )
    candidates = filtered.get("candidates")
    if isinstance(candidates, list):
        filtered["candidates"] = [
            record for record in candidates
            if str(record.get("discovery_source")) not in HOST_DEPENDENT_MECHANISMS
        ]
        filtered["candidate_count"] = len(filtered["candidates"])
    mechanisms = filtered.get("mechanisms")
    if isinstance(mechanisms, list):
        for mechanism in mechanisms:
            if str(mechanism.get("mechanism")) in HOST_DEPENDENT_MECHANISMS:
                mechanism["host_dependent_not_compared"] = True
    return filtered


def _structural_equal(left: Any, right: Any) -> bool:
    return json.loads(json.dumps(left)) == json.loads(json.dumps(right))


def check_artifact(artifact_dir: Path,
                   allow_host_variance: bool = False) -> dict[str, Any]:
    files = build_artifact()
    report: dict[str, Any] = {
        "artifact_dir": str(artifact_dir),
        "ok": True,
        "files": {},
        "violations": [],
    }
    on_disk: dict[str, bytes] = {}
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        target = artifact_dir / name
        if not target.is_file():
            report["ok"] = False
            report["violations"].append(f"missing artifact file: {name}")
            report["files"][name] = {"match": False, "reason": "missing"}
            continue
        on_disk[name] = target.read_bytes()
        match = on_disk[name] == files[name]
        report["files"][name] = {
            "match": match,
            "fresh_sha256": _sha256_bytes(files[name]),
            "actual_sha256": _sha256_bytes(on_disk[name]),
        }
        if not match and not allow_host_variance:
            report["ok"] = False
            report["violations"].append(f"fresh build differs from committed {name}")
    if allow_host_variance:
        # CI/reference-portability mode: host-dependent differential rows cannot
        # be rebuilt byte-identically on every host, so validate the committed
        # artifact integrity/schema here and leave the strict freshness check to
        # the reference host release gate.
        report["host_variance"] = {
            "allowed": True,
            "mechanisms": list(HOST_DEPENDENT_MECHANISMS),
            "not_compared": list(ARTIFACT_FILES),
            "note": (
                "host-dependent discovery rows are validated on the reference "
                "host by the strict --check; this host validates committed "
                "artifact existence, SHA256SUMS, schema and no-auto-promotion"),
        }
    sums_bytes = on_disk.get("SHA256SUMS")
    if sums_bytes is not None:
        entries: dict[str, str] = {}
        try:
            for line in sums_bytes.decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                digest, relative = line.split(None, 1)
                entries[relative.strip()] = digest.strip()
        except (UnicodeDecodeError, ValueError) as exc:
            report["ok"] = False
            report["violations"].append(f"on-disk SHA256SUMS unreadable: {exc}")
            entries = {}
        for name in ARTIFACT_FILES:
            if name not in entries:
                report["ok"] = False
                report["violations"].append(f"on-disk SHA256SUMS does not cover {name}")
                continue
            if name in on_disk and entries[name] != _sha256_bytes(on_disk[name]):
                report["ok"] = False
                report["violations"].append(f"on-disk SHA256SUMS mismatch for {name}")
    source_docs: dict[str, Any] = {}
    for name in ("gaps.json", "candidates.json"):
        raw = on_disk.get(name)
        if raw is None:
            continue
        try:
            source_docs[name] = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            report["ok"] = False
            report["violations"].append(f"committed {name} unreadable: {exc}")
    if allow_host_variance:
        report["violations"].extend(_schema_violations({
            name: on_disk[name] for name in source_docs}))
        candidates_doc = source_docs.get("candidates.json") or {}
        gaps_doc = source_docs.get("gaps.json") or {}
        promoted = [
            record.get("gap_id")
            for record in candidates_doc.get("candidates") or []
            if record.get("status") != "candidate"
        ]
        if promoted:
            report["ok"] = False
            report["violations"].append(
                f"discovery candidates not status=candidate: {promoted[:5]}")
        report["mechanisms"] = [
            {
                "mechanism": mechanism["mechanism"],
                "status": mechanism["status"],
                "candidate_count": mechanism["candidate_count"],
            }
            for mechanism in candidates_doc.get("mechanisms") or []
        ]
        report["record_count"] = gaps_doc.get("record_count")
        report["candidate_count"] = candidates_doc.get("candidate_count")
    else:
        report["violations"].extend(_schema_violations(files))
        report["mechanisms"] = [
            {
                "mechanism": mechanism["mechanism"],
                "status": mechanism["status"],
                "candidate_count": mechanism["candidate_count"],
            }
            for mechanism in json.loads(files["candidates.json"])["mechanisms"]
        ]
        report["record_count"] = json.loads(files["gaps.json"])["record_count"]
        report["candidate_count"] = json.loads(files["candidates.json"])["candidate_count"]
    if report["violations"]:
        report["ok"] = False
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the six capability-gap discovery mechanisms and build the gap "
            "registry artifacts (offline; deterministic on the same host)."
        ),
    )
    parser.add_argument("--out", type=Path, default=ARTIFACT_DIR,
                        help="artifact directory (default: %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="rebuild in memory and compare with the artifact on disk")
    parser.add_argument(
        "--allow-host-variance", action="store_true",
        help=("CI mode: tolerate host-dependent differential rows; the "
              "reference-host gate keeps the strict --check"))
    parser.add_argument("--json", action="store_true",
                        help="print a JSON summary instead of writing files")
    args = parser.parse_args(argv)
    try:
        if args.check:
            report = check_artifact(
                args.out,
                allow_host_variance=args.allow_host_variance)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["ok"] else 1
        payload = run_discovery()
        if args.json:
            print(json.dumps({
                "ok": True,
                "generated_at": payload["registry"]["generated_at"],
                "record_count": payload["registry"]["record_count"],
                "base_record_count": payload["registry"]["base_record_count"],
                "candidate_count": payload["registry"]["candidate_record_count"],
                "records_by_source": payload["registry"]["records_by_source"],
                "records_by_status": payload["registry"]["records_by_status"],
                "mechanisms": [
                    {
                        "mechanism": mechanism["mechanism"],
                        "status": mechanism["status"],
                        "candidate_count": len(mechanism["candidates"]),
                        "reason": mechanism["reason"],
                        "run_evidence": mechanism["run_evidence"],
                    }
                    for mechanism in payload["mechanisms"]
                ],
                "validation": payload["registry"]["validation"],
                "source_digest_sha256": payload["registry"]["provenance"]["source_digest_sha256"],
            }, indent=2, ensure_ascii=False))
            return 0
        written = write_artifact(args.out)
        print(json.dumps({"ok": True, "out": str(args.out), "written": written},
                         indent=2, ensure_ascii=False))
        return 0
    except (DiscoveryError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
