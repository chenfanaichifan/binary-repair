#!/usr/bin/env python3
"""Acceptance-model audit matrix.

Builds the deterministic committed matrix
``artifacts/acceptance-model-audit-2026-11-16/cases.json`` (>= 40 cases: positive
baselines + at least one negative case per AM01-AM20 class, each annotated with
``expected_mismatches``), runs the pure
``app.services.acceptance_models.AcceptanceModelMatcher`` over it, and writes
``report.json`` / ``README.md`` / ``SHA256SUMS``.

The matrix is deterministic: no network, no clock, no host probes.  ``--check``
recomputes the matrix and report from the committed cases and fails on any
tampering (case content or report content) or checksum mismatch.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.acceptance_models import (  # noqa: E402
    ACCEPTANCE_DIMENSIONS,
    MISMATCH_IDS,
    MISMATCH_RULES,
    AcceptanceModelMatcher,
)

SCHEMA_VERSION = 1
ARTIFACT_DIR = ROOT / "artifacts" / "acceptance-model-audit-2026-11-16"
GENERATED_BY = "scripts/audit_acceptance_models.py"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64
HEX_E = "e" * 64

BASE_TASK: dict[str, Any] = {
    "task_id": "acceptance-matrix",
    "target_sha": HEX_A,
    "tree_sha": HEX_B,
    "format": "elf",
    "arch": "x86_64",
    "abi": "sysv",
    "scope": "function",
    "required_methods": ["static_analysis", "dynamic_reproduction",
                         "regression_suite"],
    "required_evidence_modes": ["static", "dynamic"],
    "required_environment": {"platform": "linux", "arch": "x86_64",
                             "runtime_tier": "emulated_run"},
    "model_identity": {"requested": "deepseek-chat",
                       "allowed_aliases": ["deepseek-flash"]},
    "requires_regression": True,
    "required_repeats": 3,
    "required_tool_versions": {"gate": "1.0.0"},
    "evidence_refs": [
        {"evidence_id": "ev-1", "sha256": HEX_C},
        {"evidence_id": "ev-2", "sha256": HEX_D},
    ],
    "expected_evidence_manifest": HEX_E,
}

BASE_ACCEPTANCE: dict[str, Any] = {
    "target": {
        "sha256": HEX_A,
        "tree_sha": HEX_B,
        "format": "elf",
        "arch": "x86_64",
        "abi": "sysv",
    },
    "format": "elf",
    "arch": "x86_64",
    "abi": "sysv",
    "scope": "function",
    "methods": ["static_analysis", "dynamic_reproduction", "regression_suite"],
    "environment": {"platform": "linux", "arch": "x86_64",
                    "runtime_tier": "emulated_run"},
    "model_identity": {"status": "exact", "requested": "deepseek-chat",
                       "served": "deepseek-chat"},
    "evidence": [
        {
            "evidence_id": "ev-1",
            "sha256": HEX_C,
            "mode": "static",
            "scope": "function",
            "methods": ["static_analysis"],
            "environment": {"platform": "linux", "arch": "x86_64",
                            "runtime_tier": "emulated_run"},
            "author": "alice",
            "reviewer": "bob",
            "regression": False,
            "repeats": 3,
            "tool_versions": {"gate": "1.0.0"},
        },
        {
            "evidence_id": "ev-2",
            "sha256": HEX_D,
            "mode": "dynamic",
            "scope": "function",
            "methods": ["dynamic_reproduction", "regression_suite"],
            "environment": {"platform": "linux", "arch": "x86_64",
                            "runtime_tier": "emulated_run"},
            "author": "alice",
            "reviewer": "bob",
            "regression": True,
            "repeats": 3,
            "tool_versions": {"gate": "1.0.0"},
        },
    ],
    "evidence_manifest_sha256": HEX_E,
    "independence": {"authors": ["alice"], "reviewers": ["bob"],
                     "self_review": False, "shared_source": False},
    "claims": {"scope": "function", "extra_claims": []},
}


def _case(task: dict[str, Any], acceptance: dict[str, Any],
          case_id: str, purpose: str,
          expected_mismatches: list[str]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "purpose": purpose,
        "expected_decision": "verified" if not expected_mismatches else "rejected",
        "expected_mismatches": sorted(expected_mismatches),
        "task": task,
        "acceptance": acceptance,
    }


def _mutated(mutator: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    task = copy.deepcopy(BASE_TASK)
    acceptance = copy.deepcopy(BASE_ACCEPTANCE)
    mutator(task, acceptance)
    return task, acceptance


def build_cases() -> list[dict[str, Any]]:
    """Build the deterministic audit matrix (>= 40 cases, AM01-AM20 covered)."""
    cases: list[dict[str, Any]] = []

    # --- positive baselines ------------------------------------------------
    task, acceptance = _mutated(lambda task, acceptance: None)
    cases.append(_case(task, acceptance, "positive-exact-identity",
                       "complete exact-identity acceptance verifies", []))
    task, acceptance = _mutated(lambda task, acceptance: None)
    acceptance["model_identity"] = {
        "status": "alias", "requested": "deepseek-chat",
        "served": "deepseek-flash",
    }
    cases.append(_case(task, acceptance, "positive-declared-alias",
                       "a declared model alias is verified", []))
    task, acceptance = _mutated(
        lambda task, acceptance: task.update({"scope": "whole_program"}))
    acceptance["scope"] = "whole_program"
    acceptance["claims"]["scope"] = "whole_program"
    for item in acceptance["evidence"]:
        item["scope"] = "whole_program"
    cases.append(_case(task, acceptance, "positive-whole-program",
                       "whole-program task with whole-program evidence verifies",
                       []))
    task, acceptance = _mutated(lambda task, acceptance: None)
    task.update({
        "scope": "function",
        "required_methods": ["static_analysis"],
        "required_evidence_modes": ["static"],
        "requires_regression": False,
        "required_repeats": 1,
        "evidence_refs": [{"evidence_id": "ev-1", "sha256": HEX_C}],
    })
    task.pop("expected_evidence_manifest", None)
    acceptance["methods"] = ["static_analysis"]
    acceptance["evidence"] = [acceptance["evidence"][0]]
    acceptance.pop("evidence_manifest_sha256", None)
    cases.append(_case(task, acceptance, "positive-static-only",
                       "static-only task with static evidence verifies", []))

    # --- AM01-AM20 primary negative cases ---------------------------------
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update(
            {"sha256": "f" * 64}))
    cases.append(_case(task, acceptance, "negative-am01-target-sha",
                       "target SHA spoof is rejected", ["AM01"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update(
            {"tree_sha": "f" * 64}))
    cases.append(_case(task, acceptance, "negative-am02-tree-sha",
                       "tree SHA spoof is rejected", ["AM02"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update({"format": "pe"}))
    cases.append(_case(task, acceptance, "negative-am03-format",
                       "container format spoof is rejected", ["AM03"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update({"arch": "arm64"}))
    cases.append(_case(task, acceptance, "negative-am04-arch",
                       "arch spoof is rejected", ["AM04"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({"scope": "module"}))
    cases.append(_case(task, acceptance, "negative-am05-scope-overclaim",
                       "module experience cannot claim a function task",
                       ["AM05"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["evidence"][1].update(
            {"mode": "static"}))
    cases.append(_case(task, acceptance, "negative-am06-static-dynamic",
                       "missing dynamic evidence mode is rejected", ["AM06"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    task["scope"] = "whole_program"
    acceptance["scope"] = "whole_program"
    acceptance["claims"]["scope"] = "whole_program"
    cases.append(_case(task, acceptance, "negative-am07-whole-program",
                       "single-function evidence cannot claim whole program",
                       ["AM07"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["evidence"][0].update(
            {"sha256": "0" * 64}))
    cases.append(_case(task, acceptance, "negative-am08-evidence-hash",
                       "tampered evidence hash is rejected", ["AM08"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({
            "model_identity": {"status": "served-model-only",
                               "requested": "deepseek-chat",
                               "served": "deepseek-chat"}}))
    cases.append(_case(task, acceptance, "negative-am09-served-only",
                       "served-model-only identity cannot verify requested",
                       ["AM09"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({
            "model_identity": {"status": "unknown"}}))
    cases.append(_case(task, acceptance, "negative-am10-unknown-identity",
                       "unknown model identity is rejected", ["AM10"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({
            "model_identity": {"status": "mismatch",
                               "requested": "deepseek-chat",
                               "served": "deepseek-flash"}}))
    cases.append(_case(task, acceptance, "negative-am11-mismatched-identity",
                       "mismatched model identity is rejected", ["AM11"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({
            "model_identity": {"status": "alias", "requested": "deepseek-chat",
                               "served": "gpt-unregistered"}}))
    cases.append(_case(task, acceptance, "negative-am12-invalid-alias",
                       "undeclared model alias is rejected", ["AM12"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    acceptance["methods"] = [method for method in acceptance["methods"]
                             if method != "dynamic_reproduction"]
    acceptance["evidence"][1]["methods"] = ["regression_suite"]
    cases.append(_case(task, acceptance, "negative-am13-method-missing",
                       "required method without evidence is rejected",
                       ["AM13"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["environment"].update(
            {"platform": "darwin"}))
    cases.append(_case(task, acceptance, "negative-am14-environment",
                       "environment spoof is rejected", ["AM14"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    acceptance["only_positive"] = True
    acceptance["evidence"][1]["regression"] = False
    cases.append(_case(task, acceptance, "negative-am15-only-positive",
                       "only-positive evidence cannot satisfy regression",
                       ["AM15"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["evidence"][0].update({"repeats": 1}))
    cases.append(_case(task, acceptance, "negative-am16-statistics",
                       "insufficient repeats are rejected", ["AM16"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    for item in acceptance["evidence"]:
        item["tool_versions"]["gate"] = "0.9.9"
    cases.append(_case(task, acceptance, "negative-am17-tool-version",
                       "tool version drift is rejected", ["AM17"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["independence"].update(
            {"self_review": True}))
    cases.append(_case(task, acceptance, "negative-am18-independence",
                       "self-review independence violation is rejected",
                       ["AM18"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["claims"].update(
            {"extra_claims": ["whole_repository_secure"]}))
    cases.append(_case(task, acceptance, "negative-am19-extra-claim",
                       "claims beyond the task contract are rejected",
                       ["AM19"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["evidence"][0].pop("author"))
    cases.append(_case(task, acceptance, "negative-am20-evidence-incomplete",
                       "incomplete evidence record is rejected", ["AM20"]))

    # --- additional variants (distinct evidence for the same classes) -----
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update(
            {"sha256": "1" * 64}))
    cases.append(_case(task, acceptance, "variant-am01-target-sha-other",
                       "any target SHA deviation is rejected", ["AM01"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update(
            {"tree_sha": "2" * 64}))
    cases.append(_case(task, acceptance, "variant-am02-tree-sha-other",
                       "any tree SHA deviation is rejected", ["AM02"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update({"format": "macho"}))
    cases.append(_case(task, acceptance, "variant-am03-format-macho",
                       "Mach-O acceptance cannot verify an ELF task", ["AM03"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["target"].update({"abi": "cdecl"}))
    cases.append(_case(task, acceptance, "variant-am04-abi",
                       "ABI spoof is rejected with the arch class", ["AM04"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    task["scope"] = "vulnerability"
    acceptance["scope"] = "whole_program"
    acceptance["claims"]["scope"] = "vulnerability"
    for item in acceptance["evidence"]:
        item["scope"] = "whole_program"
    cases.append(_case(task, acceptance, "variant-am05-vulnerability-scope",
                       "whole-program evidence cannot claim a vulnerability task",
                       ["AM05"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    acceptance["claims"]["scope"] = "whole_program"
    cases.append(_case(task, acceptance, "variant-am07-claim-scope",
                       "whole-program claim without whole-program evidence",
                       ["AM07", "AM19"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["evidence"][1].update(
            {"sha256": "3" * 64}))
    cases.append(_case(task, acceptance, "variant-am08-evidence-hash-2",
                       "second evidence hash tamper is rejected", ["AM08"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({
            "model_identity": {"status": "served-model-only",
                               "requested": "deepseek-chat",
                               "served": "deepseek-flash"}}))
    cases.append(_case(task, acceptance, "variant-am09-served-different",
                       "served-only different model cannot verify requested",
                       ["AM09"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.pop("model_identity"))
    cases.append(_case(task, acceptance, "variant-am10-no-identity",
                       "missing identity record is unknown", ["AM10"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({
            "model_identity": {"status": "exact",
                               "requested": "deepseek-chat",
                               "served": "deepseek-flash"}}))
    cases.append(_case(task, acceptance, "variant-am11-exact-but-served",
                       "exact status with a different served model is rejected",
                       ["AM11"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance.update({
            "model_identity": {"status": "alias", "requested": "other-model",
                               "served": "deepseek-flash"}}))
    cases.append(_case(task, acceptance, "variant-am12-alias-requested",
                       "alias for a different requested model is invalid",
                       ["AM12"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    acceptance["methods"] = [method for method in acceptance["methods"]
                             if method != "static_analysis"]
    acceptance["evidence"][0]["methods"] = ["dynamic_reproduction"]
    cases.append(_case(task, acceptance, "variant-am13-static-method-missing",
                       "missing static method evidence is rejected", ["AM13"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["environment"].update(
            {"runtime_tier": "native_run"}))
    cases.append(_case(task, acceptance, "variant-am14-runtime-tier",
                       "runtime tier claim mismatch is rejected", ["AM14"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    acceptance["only_positive"] = True
    acceptance["evidence"][1]["regression"] = False
    acceptance["evidence"][0]["regression"] = False
    cases.append(_case(task, acceptance, "variant-am15-positive-only-flag",
                       "only_positive acceptance is rejected", ["AM15"]))
    task, acceptance = _mutated(
        lambda task, acceptance: task.update({"required_repeats": 5}))
    cases.append(_case(task, acceptance, "variant-am16-repeats-bar",
                       "higher repeat bar is rejected when evidence is thin",
                       ["AM16"]))
    task, acceptance = _mutated(lambda task, acceptance: None)
    acceptance["tool_versions"] = {"gate": "2.0.0"}
    cases.append(_case(task, acceptance, "variant-am17-acceptance-version",
                       "acceptance-level tool version drift is rejected",
                       ["AM17"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["independence"].update(
            {"shared_source": True}))
    cases.append(_case(task, acceptance, "variant-am18-shared-source",
                       "shared-source independence violation is rejected",
                       ["AM18"]))
    task, acceptance = _mutated(
        lambda task, acceptance: acceptance["claims"].update(
            {"scope": "module"}))
    cases.append(_case(task, acceptance, "variant-am19-claim-scope",
                       "claim scope overclaim is rejected", ["AM19"]))
    task, acceptance = _mutated(
        lambda task, acceptance: task["evidence_refs"].append(
            {"evidence_id": "ev-3", "sha256": HEX_A}))
    cases.append(_case(task, acceptance, "variant-am20-extra-ref",
                       "task evidence reference without acceptance evidence",
                       ["AM20"]))

    cases.sort(key=lambda case: case["case_id"])
    return cases


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the matcher over the matrix and compute recall/precision."""
    results: list[dict[str, Any]] = []
    expected_instances = 0
    detected_expected = 0
    detected_instances = 0
    false_positives = 0
    failures: list[str] = []
    for case in cases:
        expected = sorted(str(item) for item in case.get(
            "expected_mismatches", []))
        expected_decision = str(case.get("expected_decision", ""))
        result = AcceptanceModelMatcher.match(case.get("task", {}),
                                              case.get("acceptance", {}))
        detected = sorted(str(item) for item in result.get("mismatches", []))
        expected_instances += len(expected)
        detected_instances += len(detected)
        detected_expected += len(set(expected) & set(detected))
        extra = sorted(set(detected) - set(expected))
        missing = sorted(set(expected) - set(detected))
        false_positives += len(extra)
        case_ok = (not extra and not missing
                   and str(result.get("decision")) == expected_decision)
        if not case_ok:
            failures.append(
                f"{case.get('case_id')}: expected={expected} "
                f"detected={detected} decision={result.get('decision')}")
        results.append({
            "case_id": str(case.get("case_id", "")),
            "purpose": str(case.get("purpose", "")),
            "expected_mismatches": expected,
            "detected_mismatches": detected,
            "expected_decision": expected_decision,
            "decision": str(result.get("decision", "")),
            "ok": case_ok,
        })
    recall = (detected_expected / expected_instances
              if expected_instances else 0.0)
    precision = (1.0 - (false_positives / detected_instances)
                 if detected_instances else 0.0)
    covered = sorted({
        mismatch_id for case in cases
        for mismatch_id in case.get("expected_mismatches", [])
        if str(mismatch_id) in MISMATCH_IDS
    })
    negative_cases = [case for case in cases
                      if case.get("expected_mismatches")]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "case_count": len(cases),
        "positive_case_count": len(cases) - len(negative_cases),
        "negative_case_count": len(negative_cases),
        "expected_mismatch_instances": expected_instances,
        "detected_expected_instances": detected_expected,
        "detected_mismatch_instances": detected_instances,
        "false_positives": false_positives,
        "recall": round(recall, 6),
        "precision": round(precision, 6),
        "covered_am_classes": covered,
        "ok": not failures,
        "failures": failures,
        "cases": results,
        "dimensions": [dim["id"] for dim in ACCEPTANCE_DIMENSIONS],
        "mismatch_classes": list(MISMATCH_IDS),
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _matrix_payload(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "case_count": len(cases),
        "cases": cases,
    }


def _readme(report: dict[str, Any]) -> str:
    lines = [
        "# Acceptance-model audit matrix (2026-11-16)",
        "",
        "Deterministic matrix for the A01-A08 acceptance dimensions and the",
        "AM01-AM20 mismatch model (`app/services/acceptance_models.py`).",
        "",
        f"- cases: **{report['case_count']}** "
        f"(positive {report['positive_case_count']}, negative "
        f"{report['negative_case_count']})",
        f"- AM classes covered by a negative case: "
        f"{len(report['covered_am_classes'])}/20 "
        f"({', '.join(report['covered_am_classes'])})",
        f"- recall: **{report['recall']}**, precision: "
        f"**{report['precision']}**, ok: **{report['ok']}**",
        "",
        "## Cases",
        "",
        "| case | purpose | expected | detected | decision | ok |",
        "|---|---|---|---|---|---|",
    ]
    for case in report["cases"]:
        lines.append(
            "| {case} | {purpose} | {expected} | {detected} | {decision} | {ok} |"
            .format(
                case=case["case_id"], purpose=case["purpose"],
                expected=", ".join(case["expected_mismatches"]) or "-",
                detected=", ".join(case["detected_mismatches"]) or "-",
                decision=case["decision"],
                ok="yes" if case["ok"] else "NO",
            ))
    lines.extend([
        "",
        "## Reproduce",
        "",
        "```",
        "python scripts/audit_acceptance_models.py --write",
        "python scripts/audit_acceptance_models.py --check",
        "python scripts/audit_acceptance_models.py --json",
        "```",
        "",
        "`--check` recomputes the matrix and report from the committed "
        "`cases.json`, compares them byte-for-byte (canonical JSON) and "
        "verifies `SHA256SUMS`; any tampering or a missed/extra mismatch "
        "exits non-zero.",
        "",
    ])
    return "\n".join(lines)


def write_artifacts(cases: list[dict[str, Any]], report: dict[str, Any],
                    artifact_dir: Path = ARTIFACT_DIR) -> dict[str, Any]:
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)
    cases_path = target / "cases.json"
    report_path = target / "report.json"
    readme_path = target / "README.md"
    cases_path.write_text(_canonical_json(_matrix_payload(cases)),
                          encoding="utf-8")
    report_path.write_text(_canonical_json(report), encoding="utf-8")
    readme_path.write_text(_readme(report), encoding="utf-8")
    entries = []
    for path in (cases_path, report_path, readme_path):
        entries.append(f"{_sha256_bytes(path.read_bytes())}  {path.name}")
    sums_path = target / "SHA256SUMS"
    sums_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
    return {
        "artifact_dir": str(target),
        "cases": str(cases_path),
        "report": str(report_path),
        "readme": str(readme_path),
        "sums": str(sums_path),
        "sha256": {
            "cases.json": entries[0].split()[0],
            "report.json": entries[1].split()[0],
            "README.md": entries[2].split()[0],
        },
    }


def _verify_sums(artifact_dir: Path) -> list[str]:
    sums_path = Path(artifact_dir) / "SHA256SUMS"
    if not sums_path.is_file():
        return [f"missing SHA256SUMS: {sums_path}"]
    problems: list[str] = []
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2:
            problems.append(f"malformed SHA256SUMS line: {line!r}")
            continue
        expected, name = parts[0], parts[1]
        target = Path(artifact_dir) / name
        if not target.is_file():
            problems.append(f"artifact missing: {name}")
            continue
        actual = _sha256_bytes(target.read_bytes())
        if actual != expected:
            problems.append(f"sha256 mismatch for {name}")
    return problems


def check_artifacts(artifact_dir: Path = ARTIFACT_DIR) -> list[str]:
    """Recompute matrix/report from committed artifacts; detect tampering."""
    target = Path(artifact_dir)
    problems = _verify_sums(target)
    cases_path = target / "cases.json"
    report_path = target / "report.json"
    try:
        committed_cases = json.loads(cases_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return problems + [f"cases.json unreadable: {type(exc).__name__}: {exc}"]
    try:
        committed_report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return problems + [f"report.json unreadable: {type(exc).__name__}: {exc}"]
    expected_cases = build_cases()
    if committed_cases != _matrix_payload(expected_cases):
        problems.append(
            "cases.json is stale/tampered relative to the deterministic matrix")
    recomputed = evaluate_cases(expected_cases)
    if committed_report != recomputed:
        problems.append(
            "report.json is stale/tampered relative to a fresh recomputation")
    if recomputed["ok"] is not True:
        problems.extend(f"recompute failure: {item}"
                        for item in recomputed["failures"][:6])
    if recomputed["recall"] != 1.0 or recomputed["precision"] != 1.0:
        problems.append(
            f"recall={recomputed['recall']} precision="
            f"{recomputed['precision']} (must both be 1.0)")
    covered = set(recomputed["covered_am_classes"])
    missing_classes = [mismatch_id for mismatch_id in MISMATCH_IDS
                       if mismatch_id not in covered]
    if missing_classes:
        problems.append(f"AM classes without a negative case: {missing_classes}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="acceptance-model audit matrix (deterministic)")
    parser.add_argument("--write", action="store_true",
                        help="write cases.json/report.json/README.md/SHA256SUMS")
    parser.add_argument("--check", action="store_true",
                        help="verify committed artifacts (tamper detection)")
    parser.add_argument("--json", action="store_true",
                        help="print the report JSON")
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifacts(args.artifact_dir)
        if problems:
            for problem in problems:
                print(f"AUDIT-VIOLATION: {problem}")
            return 1
        print("acceptance-model-audit: check OK "
              "(cases/report recomputed; SHA256SUMS verified)")
        return 0
    cases = build_cases()
    report = evaluate_cases(cases)
    if args.write:
        # Only write when the matrix is clean; a red matrix must not look
        # committed and green.
        if report["ok"] is not True:
            print("AUDIT-VIOLATION: matrix is red; refusing to write artifacts")
            for failure in report["failures"][:10]:
                print(f"AUDIT-VIOLATION: {failure}")
            return 1
        artifact = write_artifacts(cases, report, args.artifact_dir)
        print("acceptance-model-audit: wrote {}".format(
            artifact["artifact_dir"]))
        print("cases_sha256={}".format(artifact["sha256"]["cases.json"]))
        print("report_sha256={}".format(artifact["sha256"]["report.json"]))
        print("readme_sha256={}".format(artifact["sha256"]["README.md"]))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    elif not args.write:
        print(
            "acceptance-model-audit: ok={ok} cases={cases} recall={recall} "
            "precision={precision} covered={covered}".format(
                ok=report["ok"], cases=report["case_count"],
                recall=report["recall"], precision=report["precision"],
                covered=len(report["covered_am_classes"]),
            )
        )
        for failure in report["failures"][:10]:
            print(f"AUDIT-VIOLATION: {failure}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
