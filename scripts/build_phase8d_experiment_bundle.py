#!/usr/bin/env python3
"""Build/check the deterministic Phase-8D experiment evidence bundle (D08).

The bundle does not execute experiments. It binds the already-produced,
independent Phase-8D artifacts into one auditable record and verifies every
referenced file digest. A completed experiment never changes a capability
state; all records say promotion_effect=none.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "phase8d-experiments-2026-11-17"
KIND = "phase8d_experiment_bundle"
BASE_SHA = "f1bb1f41eba1e0be61be09cea56091e8a03a9896"
GENERATED_AT = "2026-11-17T00:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(relative: str, role: str) -> dict[str, str]:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"missing evidence: {relative}")
    return {"path": relative, "sha256": _sha(path), "role": role}


def _experiments() -> list[dict[str, Any]]:
    return [
        {
            "experiment_id": "EXP-8D-D00",
            "question": "Can the Phase-8C release identity and frozen evidence still be resolved after branch/tag consolidation?",
            "hypothesis": "The Phase-8C release commit and evidence tip are ancestor objects of the consolidated baseline, even if their refs were removed.",
            "method": "Resolve 4a7b2355 and ec503e4 by object id; verify ancestry of both in the Phase-8D baseline; record gate and CI references.",
            "status": "completed",
            "evidence": [_ref("artifacts/phase8d-baseline-2026-11-17/baseline.json", "D00 baseline facts")],
            "result": "Phase-8C release 4a7b2355 and evidence tip ec503e4 resolve and are ancestors of f1bb1f4; original refs were removed by consolidation and are explicitly recorded.",
            "limitations": ["This is object-level recovery, not a restored remote tag; no historical evidence is rewritten."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D01",
            "question": "What capability states and legal coverage denominators follow from the existing 20-dimension/240-cell catalog?",
            "hypothesis": "Legacy verified/supported cells represent declared coverage, not new independent verification; catalog-external space remains explicit unknown.",
            "method": "Deterministically map the existing dimensions/cells, public samples, hidden aggregate and M2 prototype into explicit capability units and legal transition rules.",
            "status": "completed",
            "evidence": [_ref("artifacts/phase8d-capability-universe-2026-11-17/registry.json", "capability universe registry")],
            "result": "297 capability units are recorded with explicit states and denominators; 2 independently verified public fixtures, 0 generalized and 0 promoted units; catalog-external space is recorded as unmeasurable/null, not zero.",
            "limitations": ["Coverage is declared-space coverage only; it cannot prove the global space of all binaries or vulnerabilities."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D02",
            "question": "Which Phase-8D gaps are still open and how are they linked to evidence and proposed experiments?",
            "hypothesis": "The audit gaps are open governance/analysis gaps, not closed implementation claims.",
            "method": "Build an additive registry for AUDIT-8D-01..08 with category, reproduction status, severity, dependencies, lineage and proposed experiments.",
            "status": "completed_open_gaps",
            "evidence": [_ref("artifacts/phase8d-gap-registry-2026-11-17/gaps.json", "Phase-8D gap registry")],
            "result": "All eight Phase-8D audit gaps are recorded as open with explicit evidence and proposed experiments; no gap is closed by a code change alone.",
            "limitations": ["Gap closure requires an executed experiment and independent evidence; this bundle only records planning and analysis."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D03",
            "question": "Can the acceptance model detect mutated rules, evidence, scope, oracle and state claims without false promotion?",
            "hypothesis": "An additive L0-L7 Acceptance 2.0 audit can detect all declared mutation families while retaining not_run/inconclusive for unprovable cases.",
            "method": "Run 14 deterministic mutations and positive/negative/False Reject/False Accept case families; replay historical acceptance facts without upgrading them.",
            "status": "completed",
            "evidence": [_ref("artifacts/phase8d-acceptance-2-2026-11-17/report.json", "Acceptance 2.0 report")],
            "result": "14/14 declared mutations were detected, 0 mutation false accepts, 0 false rejects in the declared fixtures, and 2 inconclusive cases remain explicit.",
            "limitations": ["A finite mutation campaign cannot prove acceptance-rule completeness; correct new-layout candidates remain an unmeasured False Reject area."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D04",
            "question": "Why did the independent verifier reject the deterministic heap-malloc candidate?",
            "hypothesis": "The candidate may be invalid, the patch plan may describe the wrong ABI region, or the verifier may lack a rule or evidence.",
            "method": "Re-run the deterministic repair, reconstruct candidate bytes, resolve raw branch/call/GOT/tail-call targets, compare plan ABI evidence with the injected cave, and rerun the independent verifier without changing rules.",
            "status": "completed_rejected",
            "evidence": [_ref("artifacts/phase8d-heap-malloc-abi-2026-11-17/abi-analysis.json", "heap-malloc ABI root-cause analysis")],
            "result": "The primary root cause is generator_plan_incorrect: plan.abi_blocks[0] declares the pre-existing target function, not the injected cave; abi_proof_insufficient also holds. The candidate remains independently rejected; no rule was relaxed.",
            "limitations": ["The ABI checker is conservative/static and does not resolve runtime GOT/PLT load behavior; the candidate remains unverified."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D05",
            "question": "At which pipeline stage do the six hidden runtime samples fail to produce candidates?",
            "hypothesis": "The zero-candidate result is attributable to an explicit stage/reason rather than an execution failure.",
            "method": "Run the private hidden lane with stage diagnostics, retain a private detailed report, and export only anonymous stage/reason distributions.",
            "status": "completed_zero_candidates",
            "evidence": [_ref("artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json", "anonymous hidden stage aggregate")],
            "result": "All six runtime samples execute, but the first blocking stage is detection_missed for all six; the hidden candidate and verified counts remain 0.",
            "limitations": ["No hidden sample id, path, bytes or raw report is exported; hidden generalisation is not established."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D06",
            "question": "Can a versioned external knowledge snapshot identify CWE changes without claiming implementation support?",
            "hypothesis": "CWE 5.0/Schema 8.0 introduces catalog and schema drift that can be normalized into capability candidates, but not support claims.",
            "method": "Fetch/commit a small normalized official CWE 5.0 snapshot with source/version/hash, parse it offline, map entries to capability groups, and record version/schema drift.",
            "status": "completed_candidates_only",
            "evidence": [_ref("artifacts/phase8d-external-knowledge-2026-11-17/external-knowledge.json", "external knowledge scan")],
            "result": "984 external entries were parsed (15 new relative to the recorded prior count), 232 capability candidates were mapped and 752 remain unmapped; no support is claimed.",
            "limitations": ["External catalog entries are candidate requirements, not binary-repair evidence; the live source count differs from the earlier audit snapshot (984 vs 956)."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D07",
            "question": "Does a real metamorphic/input-mutation run expose capability differences across compiler variants and input boundaries?",
            "hypothesis": "Same-source compiler variants and family-specific input mutations can expose explicit engine/oracle differences without fabricated candidates.",
            "method": "Run the deterministic engine and real guest oracle over four committed Phase-8C compiler variants and 11 input mutations; record differences and hold/not_run states.",
            "status": "completed_partial",
            "evidence": [
                _ref("artifacts/phase8d-discovery-2026-11-17/discovery.json", "metamorphic/input-mutation discovery"),
                _ref("artifacts/phase8d-discovery-registry-2026-11-17/registry.json", "additive discovery-mechanism registry"),
            ],
            "result": "Four variants were compared with 2 engine differences and 2 not_run/unsupported; 11/11 input mutations executed through the real oracle; no support is claimed.",
            "limitations": ["The existing seven-mechanism adapter registry was not rewritten; sample_based discovery remains not_run."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D09",
            "question": "Is the operational hidden isolation boundary internally consistent and free of public hidden material?",
            "hypothesis": "The private root, commitment, aggregate and tracked public files can be audited without exposing hidden content.",
            "method": "Check root ownership/permissions, commitment/aggregate consistency, tracked-file leaks and public aggregate shape; never copy hidden bytes.",
            "status": "completed_operational_only",
            "evidence": [_ref("artifacts/phase8d-hidden-isolation-2026-11-17/isolation.json", "hidden isolation audit")],
            "result": "The operational isolation audit passes its declared checks; it explicitly does not claim cryptographic isolation from same-UID or root readers.",
            "limitations": ["Same-UID/root readers can still read the private root; this is operational isolation, not encryption."],
            "promotion_effect": "none",
        },
        {
            "experiment_id": "EXP-8D-D10",
            "question": "Does the promotion gate reject every Phase-8C capability-state jump without evidence?",
            "hypothesis": "Public fixtures and hidden analysis-only/candidate states cannot be promoted to generalized/promoted under the gate's evidence requirements.",
            "method": "Evaluate four recorded Phase-8C transitions through the legal-state machine, evidence, hidden/holdout, regression and independent-approval rules.",
            "status": "completed_no_promotion",
            "evidence": [_ref("artifacts/phase8d-promotion-2026-11-17/promotion.json", "promotion gate evaluation")],
            "result": "4/4 evaluated transitions were denied; promoted_count=0, hidden_verified_count=0, and the withdrawn heap-malloc claim cannot become independently_verified.",
            "limitations": ["A gate denial is not evidence that a capability is impossible; it records insufficient evidence and preserves the state."],
            "promotion_effect": "none",
        },
    ]


def build_bundle() -> dict[str, Any]:
    experiments = _experiments()
    summary = {
        "experiment_count": len(experiments),
        "verified_true_count": 0,
        "capability_promotion": False,
        "false_verified_observed": 0,
        "not_run_count": sum(1 for item in experiments if item["status"] == "not_run"),
    }
    return {
        "schema_version": 1,
        "kind": KIND,
        "phase": "Phase-8D",
        "generated_at": GENERATED_AT,
        "baseline_sha": BASE_SHA,
        "experiments": experiments,
        "summary": summary,
        "provenance": {
            "builder": "scripts/build_phase8d_experiment_bundle.py",
            "execution": "binds previously produced artifacts; does not execute them",
            "hidden": "aggregate-only; no hidden bytes/ids/paths",
        },
        "limitations": [
            "The bundle binds evidence; it does not re-run the experiments or independently verify every claim.",
            "No experiment changes a capability state; all promotion_effect values are none.",
            "The Phase-8D audit gaps remain open until executed experiments and independent evidence close them.",
        ],
    }


def check_bundle() -> tuple[bool, list[str]]:
    path = OUT / "experiments.json"
    if not path.is_file():
        return False, ["missing experiments.json"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"unreadable experiments.json: {exc}"]
    problems: list[str] = []
    expected = build_bundle()
    if payload != expected:
        problems.append("experiments.json differs from deterministic builder output")
    for item in payload.get("experiments") or []:
        if item.get("promotion_effect") != "none":
            problems.append(f"{item.get('experiment_id')}: promotion_effect must be none")
        for ref in item.get("evidence") or []:
            target = ROOT / str(ref.get("path"))
            if not target.is_file():
                problems.append(f"{item.get('experiment_id')}: missing evidence {ref.get('path')}")
            elif _sha(target) != ref.get("sha256"):
                problems.append(f"{item.get('experiment_id')}: digest mismatch {ref.get('path')}")
    summary = payload.get("summary") or {}
    if summary.get("verified_true_count") != 0 or summary.get("capability_promotion") is not False:
        problems.append("bundle must not claim verified capability or promotion")
    return not problems, problems


def write_bundle() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build_bundle()
    path = OUT / "experiments.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    files = [path]
    sums = OUT / "SHA256SUMS"
    lines = [f"{_sha(p)}  {p.relative_to(OUT).as_posix()}" for p in sorted(files)]
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [*files, sums]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        written = write_bundle()
        payload = build_bundle()
        if args.json:
            print(json.dumps({"ok": True, "written": [str(p) for p in written]}, indent=2))
        else:
            print("phase8d-experiments: wrote", ", ".join(str(p) for p in written))
        return 0
    ok, problems = check_bundle()
    if args.json:
        print(json.dumps({"ok": ok, "problems": problems}, indent=2))
    else:
        print("phase8d-experiments: check OK" if ok else "phase8d-experiments: FAILED")
        for problem in problems:
            print(" -", problem)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
