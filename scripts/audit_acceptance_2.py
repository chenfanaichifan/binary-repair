#!/usr/bin/env python3
"""Build/check the deterministic Phase-8D Acceptance 2.0 audit artifact.

The artifact contains the L0-L7 registry, positive/negative and False
Accept/False Reject case families, a rule/evidence/scope/oracle/state mutation
campaign, historical replay facts and honest residual gaps.  It is additive to
the historical AM01-AM28 audit and never rewrites that artifact.

Usage:
    python scripts/audit_acceptance_2.py --write
    python scripts/audit_acceptance_2.py --check
    python scripts/audit_acceptance_2.py --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import acceptance_2 as a2  # noqa: E402

SCHEMA_VERSION = 2
KIND = "phase8d_acceptance_2"
GENERATED_AT = "2026-11-17T00:00:00Z"
ARTIFACT_DIR = ROOT / "artifacts" / "phase8d-acceptance-2-2026-11-17"
LEGACY_REPORT = ROOT / "artifacts" / "acceptance-model-audit-2026-11-16" / "report.json"
HEX = {name: ch * 64 for name, ch in
       (("target", "a"), ("tree", "b"), ("evidence_static", "c"),
        ("evidence_dynamic", "d"), ("candidate", "e"), ("oracle", "f"))}


def _base_case(case_id: str, expected: str, *, layout: str = "resized",
               scope: str = "function") -> dict[str, Any]:
    candidate_sha = HEX["candidate"]
    plan = {
        "target_sha256": candidate_sha,
        "operations": [
            {"kind": "replace", "original_offset": 16, "size": 6,
             "before_hex": "e80000000000", "after_hex": "e80000000090"},
            {"kind": "insert", "original_offset": 64, "size": 16,
             "before_hex": "", "after_hex": "90" * 16},
        ],
    }
    acceptance = {
        "target": {
            "sha256": HEX["target"], "tree_sha": HEX["tree"],
            "format": "elf", "arch": "x86_64", "abi": "sysv",
        },
        "scope": scope,
        "candidate": {
            "present": True,
            "sha256": candidate_sha,
            "layout": layout,
            "patch_plan": plan if layout != "same_length" else None,
            "replay": {"byte_exact": True, "replayed_sha256": candidate_sha},
            "resolved_scope": {"kind": "va_range", "va": 0x401000,
                               "end": 0x401200},
            "changed_ranges": [{"va": 0x401010, "end": 0x401040},
                               {"va": 0x401080, "end": 0x401090}],
            "associated_changes": [
                {"kind": "rodata_message", "va": 0x402000, "end": 0x402020,
                 "authorization_ref": "contract:capacity-message"}
            ],
            "associated_changes_authorized": True,
            "abi": {"blocks": [{"va": 0x401100, "size": 48,
                                "arch": "x86_64"}], "derived": True},
            "control_flow": {"branch_targets": "resolved",
                             "call_targets": "allowed"},
            "cave": {"present": layout in {"cave", "relocated"},
                     "executable": True},
        },
        "oracle": {
            "executed": True, "independent": True,
            "generator_verdict_used": False,
            "original_vulnerable": True, "candidate_eliminated": True,
            "runner": "limactl", "tier": "emulated_run",
        },
        "semantic": {
            "cases": 4, "executed": True, "preserved": True,
            "claim": "bounded", "equivalence_claimed": False,
        },
        "regression": {
            "cases": 3, "executed": True, "passed": True,
            "boundary_cases": 2, "boundary_passed": True,
        },
        "environment": {"reproducible": True, "repeats": 3,
                        "identity": "reference-host-phase8d"},
        "evidence": [
            {"evidence_id": "ev-static",
             "sha256": HEX["evidence_static"], "mode": "static",
             "scope": scope, "independent": True, "provenance": "recorded"},
            {"evidence_id": "ev-dynamic",
             "sha256": HEX["evidence_dynamic"], "mode": "dynamic",
             "scope": scope, "independent": True, "provenance": "recorded"},
        ],
        "independence": {
            "authors": ["alice"], "reviewers": ["bob"],
            "self_review": False, "shared_source": False,
        },
        "claims": {"scope": scope, "whole_image": False,
                   "analysis_only": scope == "analysis_only",
                   "verified": False},
        "state": {"status": "verified", "inconclusive": False},
    }
    task = {
        "task_id": f"task-{case_id}",
        "target_sha": HEX["target"], "tree_sha": HEX["tree"],
        "format": "elf", "arch": "x86_64", "abi": "sysv",
        "scope": scope, "benchmark_version": "phase8d",
        "candidate_sha256": candidate_sha, "candidate_present": True,
        "candidate_layout": layout, "required_repeats": 3,
        "required_methods": ["static_analysis", "dynamic_reproduction",
                             "regression_suite"],
    }
    return {"case_id": case_id, "expected_decision": expected,
            "task": task, "acceptance": acceptance}


def _analysis_only_case() -> dict[str, Any]:
    case = _base_case("analysis-only-no-candidate", "analysis_only",
                      scope="analysis_only")
    candidate = case["acceptance"]["candidate"]
    candidate["present"] = False
    candidate["sha256"] = None
    candidate["patch_plan"] = None
    candidate["replay"] = {"byte_exact": False, "replayed_sha256": ""}
    candidate["resolved_scope"] = {}
    candidate["changed_ranges"] = []
    candidate["associated_changes"] = []
    candidate["abi"] = None
    candidate["control_flow"] = {}
    candidate["cave"] = {"present": False, "executable": False}
    case["task"]["candidate_present"] = False
    case["task"]["candidate_sha256"] = None
    case["acceptance"]["claims"] = {
        "scope": "analysis_only", "whole_image": False,
        "analysis_only": True, "verified": False,
    }
    case["acceptance"]["state"] = {"status": "analysis_only",
                                   "inconclusive": False}
    return case


def _not_run_case() -> dict[str, Any]:
    case = _base_case("not-run-oracle-unknown", "not_run")
    case["acceptance"]["oracle"]["executed"] = None
    return case


def _inconclusive_case() -> dict[str, Any]:
    case = _base_case("inconclusive-conflicting-evidence", "inconclusive")
    case["acceptance"]["state"] = {"status": "inconclusive",
                                   "inconclusive": True}
    return case


def _false_reject_gap() -> dict[str, Any]:
    """Correct new layout, but ABI metadata is not derivable yet.

    The expected decision is not_run, not a fabricated verified: this is the
    residual False Reject capability gap the report records honestly.
    """
    case = _base_case("correct-new-layout-unknown-abi", "not_run", layout="cave")
    case["acceptance"]["candidate"]["abi"] = None
    return case


def _false_reject_gap_two() -> dict[str, Any]:
    case = _base_case("correct-candidate-inconclusive", "inconclusive")
    case["acceptance"]["state"] = {"status": "inconclusive",
                                   "inconclusive": True}
    case["acceptance"]["semantic"]["claim"] = "bounded"
    return case


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = [
        _base_case("positive-same-length", "verified", layout="same_length"),
        _base_case("positive-new-layout", "verified"),
        _base_case("positive-new-layout-cave", "verified", layout="cave"),
        _analysis_only_case(),
        _not_run_case(),
        _inconclusive_case(),
        _false_reject_gap(),
        _false_reject_gap_two(),
    ]
    cases.extend([
        _base_case("invalid-no-plan", "rejected"),
        _base_case("invalid-scope-inflation", "rejected"),
        _base_case("invalid-generator-verdict", "rejected"),
        _base_case("invalid-abi-missing", "rejected"),
        _base_case("invalid-analysis-only-verified", "rejected"),
        _base_case("invalid-not-run-verified", "rejected"),
        _base_case("invalid-whole-image-claim", "rejected"),
        _base_case("invalid-regression-missing", "rejected"),
        _base_case("invalid-evidence-tampered", "rejected"),
        _base_case("invalid-associated-unauthorized", "rejected"),
    ])
    by_id = {case["case_id"]: case for case in cases}
    by_id["invalid-no-plan"]["acceptance"]["candidate"]["patch_plan"] = None
    by_id["invalid-scope-inflation"]["acceptance"]["scope"] = "whole_program"
    by_id["invalid-scope-inflation"]["acceptance"]["claims"]["scope"] = "whole_program"
    by_id["invalid-generator-verdict"]["acceptance"]["oracle"].update(
        {"independent": False, "generator_verdict_used": True})
    by_id["invalid-abi-missing"]["acceptance"]["candidate"]["abi"] = {
        "blocks": [], "derived": False}
    by_id["invalid-analysis-only-verified"]["task"]["scope"] = "analysis_only"
    by_id["invalid-analysis-only-verified"]["acceptance"]["scope"] = "analysis_only"
    by_id["invalid-analysis-only-verified"]["acceptance"]["claims"].update(
        {"scope": "analysis_only", "analysis_only": True, "verified": True})
    by_id["invalid-analysis-only-verified"]["acceptance"]["state"] = {
        "status": "analysis_only", "inconclusive": False}
    by_id["invalid-not-run-verified"]["acceptance"]["state"] = {
        "status": "not_run", "inconclusive": False}
    by_id["invalid-not-run-verified"]["acceptance"]["claims"]["verified"] = True
    by_id["invalid-whole-image-claim"]["acceptance"]["claims"]["whole_image"] = True
    by_id["invalid-regression-missing"]["acceptance"]["regression"] = {
        "cases": 0, "executed": False, "passed": False,
        "boundary_cases": 0, "boundary_passed": False}
    by_id["invalid-evidence-tampered"]["acceptance"]["evidence"][0]["sha256"] = "bad"
    by_id["invalid-associated-unauthorized"]["acceptance"]["candidate"][
        "associated_changes_authorized"] = False
    return sorted(cases, key=lambda case: case["case_id"])


def _legacy_replay_facts() -> dict[str, Any]:
    if not LEGACY_REPORT.is_file():
        return {"available": False, "reason": "legacy acceptance report missing"}
    legacy = json.loads(LEGACY_REPORT.read_text(encoding="utf-8"))
    return {
        "available": True,
        "source_case_count": legacy.get("case_count"),
        "covered_am_classes": legacy.get("covered_am_classes"),
        "legacy_schema_version": legacy.get("schema_version"),
        "legacy_verified_claims": legacy.get("verified_claims"),
        "policy": "read-only historical facts; no legacy verified claim is upgraded",
    }


def _historical_replay(base: dict[str, Any]) -> dict[str, Any]:
    replay = a2.replay_historical(base, registry_version="1.0.0")
    facts = _legacy_replay_facts()
    return {
        "legacy": facts,
        "replay": {
            "case_id": replay["case_id"],
            "decision": replay["decision"],
            "upgraded": replay["upgraded"],
            "historical_note": replay["historical_note"],
            "reasons": replay["reasons"],
        },
        "ok": (
            replay["decision"] in {"not_run", "rejected"}
            and replay["verified"] is False
            and replay["upgraded"] is False
        ),
    }


def build_artifact() -> dict[str, Any]:
    cases = build_cases()
    summary = a2.summarize_cases(cases)
    base = next(case for case in cases
                if case["case_id"] == "positive-new-layout")
    mutations = a2.run_mutations(base)
    historical = _historical_replay(base)
    gaps = [
        {
            "case_id": "correct-new-layout-unknown-abi",
            "expected": "not_run",
            "observed": next(row["decision"] for row in summary["cases"]
                             if row["case_id"] == "correct-new-layout-unknown-abi"),
            "reason": "ABI metadata is not derivable; the detector refuses a "
                      "verified claim rather than guessing an ABI block",
        },
        {
            "case_id": "correct-candidate-inconclusive",
            "expected": "inconclusive",
            "observed": next(row["decision"] for row in summary["cases"]
                             if row["case_id"] == "correct-candidate-inconclusive"),
            "reason": "the acceptance state is explicitly inconclusive; "
                      "a correct candidate cannot be promoted by this audit alone",
        },
        {
            "case_id": "whole-image-semantic-equivalence",
            "expected": "unsupported",
            "observed": "not modelled as verified",
            "reason": "full semantic equivalence is undecidable in general; "
                      "Acceptance 2.0 keeps whole_image non-promotable",
        },
    ]
    cases_ok = summary["ok"] and not summary["false_accept_cases"] \
        and not summary["false_reject_cases"]
    mutation_ok = (mutations["detection_rate"] == 1.0
                   and mutations["false_accepts"] == 0)
    no_false_promotion = not any(
        row["decision"] in {"not_run", "inconclusive", "analysis_only"}
        and row["verified"] for row in summary["cases"])
    report = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "generated_at": GENERATED_AT,
        "registry": a2.build_registry(),
        "layers": list(a2.LAYER_SPECS),
        "cases": summary["cases"],
        "case_count": summary["case_count"],
        "matched": summary["matched"],
        "false_accept_cases": summary["false_accept_cases"],
        "false_reject_cases": summary["false_reject_cases"],
        "false_reject_gaps": gaps,
        "mutation_results": mutations,
        "historical_replay": historical,
        "summary": {
            "ok": bool(cases_ok and mutation_ok and historical["ok"]
                       and no_false_promotion),
            "cases_ok": bool(cases_ok),
            "mutation_detection_rate": mutations["detection_rate"],
            "mutation_false_accepts": mutations["false_accepts"],
            "historical_replay_ok": historical["ok"],
            "no_false_promotion": bool(no_false_promotion),
            "false_accepts": len(summary["false_accept_cases"]),
            "false_rejects": len(summary["false_reject_cases"]),
            "not_run_cases": sum(1 for row in summary["cases"]
                                 if row["decision"] == "not_run"),
            "inconclusive_cases": sum(1 for row in summary["cases"]
                                      if row["decision"] == "inconclusive"),
            "analysis_only_cases": sum(1 for row in summary["cases"]
                                       if row["decision"] == "analysis_only"),
        },
        "limitations": [
            "Acceptance 2.0 is a pure rule/mutation audit, not a replacement "
            "for an independent binary verifier; verified means the declared "
            "rules passed, not that arbitrary semantic equivalence was proved.",
            "The L0-L7 rules are deterministic and offline; no network or AI "
            "provider is used.",
            "Correct-but-new-layout candidates with unavailable ABI/unknown "
            "semantic state are reported not_run/inconclusive, not verified; "
            "these remain measured False Reject capability gaps.",
            "Whole-image/full semantic equivalence is not modelled as a "
            "verifiable claim; the audit never promotes it.",
            "Rule mutation coverage is finite and cannot prove the rule set "
            "complete; it only proves the tested mutations were detected.",
            "Historical AM01-AM28 cases are replayed as facts and old-version "
            "evidence is never silently upgraded to the new registry.",
        ],
    }
    schema_path = ROOT / "contracts" / "acceptance-2.schema.json"
    if schema_path.is_file():
        try:
            import jsonschema  # type: ignore
            jsonschema.validate(report, json.loads(schema_path.read_text()))
        except ImportError:
            pass
    return report


def build_cases_artifact() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "kind": "phase8d_acceptance_2_cases",
            "generated_at": GENERATED_AT, "case_count": len(build_cases()),
            "cases": build_cases()}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_files() -> dict[str, bytes]:
    report = build_artifact()
    cases = build_cases_artifact()
    files: dict[str, bytes] = {
        "cases.json": (json.dumps(cases, indent=2, sort_keys=True) + "\n").encode(),
        "report.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
    }
    summary = report["summary"]
    files["README.md"] = (
        "# Phase-8D Acceptance 2.0 audit\n\n"
        f"- generated_at: `{GENERATED_AT}` (fixed)\n"
        f"- layers: {len(report['layers'])} (L0-L7)\n"
        f"- cases: {report['case_count']}; matched: {report['matched']}; "
        f"false accepts: {summary['false_accepts']}; "
        f"false rejects: {summary['false_rejects']}\n"
        f"- mutation detection: {summary['mutation_detection_rate']} "
        f"(false accepts: {summary['mutation_false_accepts']})\n"
        f"- not_run/inconclusive/analysis_only: "
        f"{summary['not_run_cases']}/{summary['inconclusive_cases']}/"
        f"{summary['analysis_only_cases']}\n"
        f"- historical replay ok: {summary['historical_replay_ok']}; "
        f"no false promotion: {summary['no_false_promotion']}\n\n"
        "This artifact is additive to the historical AM01-AM28 audit. It does "
        "not redefine old cases, distribute hidden data, or promote capability. "
        "The False Reject gaps are listed in `report.json`.\n"
    ).encode()
    sums = []
    for name in ("cases.json", "report.json", "README.md"):
        sums.append(f"{_sha(files[name])}  {name}\n")
    files["SHA256SUMS"] = "".join(sums).encode()
    return files


def write_files(out: Path = ARTIFACT_DIR) -> list[str]:
    files = build_files()
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    return sorted(files)


def check_files(out: Path = ARTIFACT_DIR) -> list[str]:
    files = build_files()
    problems: list[str] = []
    for name, data in files.items():
        path = out / name
        if not path.is_file():
            problems.append(f"missing {name}")
        elif path.read_bytes() != data:
            problems.append(f"fresh build differs from committed {name}")
    sums = out / "SHA256SUMS"
    if sums.is_file():
        listed = {}
        for line in sums.read_text().splitlines():
            if line.strip():
                digest, name = line.split(None, 1)
                listed[name.strip()] = digest
        for name, digest in listed.items():
            path = out / name
            if not path.is_file():
                problems.append(f"SHA256SUMS lists missing {name}")
            elif _sha(path.read_bytes()) != digest:
                problems.append(f"SHA256SUMS digest mismatch {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        written = write_files()
        print(json.dumps({"ok": True, "files": written}, indent=2))
        return 0
    if args.check:
        problems = check_files()
        print(json.dumps({"ok": not problems, "problems": problems[:20]},
                         indent=2, ensure_ascii=False))
        return 0 if not problems else 1
    report = build_artifact()
    print(json.dumps({"ok": report["summary"]["ok"],
                      "summary": report["summary"],
                      "mutation_results": report["mutation_results"]},
                     indent=2, ensure_ascii=False))
    return 0 if report["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
