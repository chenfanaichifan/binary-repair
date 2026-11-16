#!/usr/bin/env python3
"""Evaluate Phase-8C evidence through the Phase-8D promotion gate.

This is a policy demonstration, not a capability promotion.  It reads committed
Phase-8C public results and hidden aggregate/commitment, builds explicit
capability-state records, and records denied transitions for:

* public fixture verified -> generalized (hidden has 0 verified);
* candidate -> independently verified for heap-malloc (independent rejection);
* hidden analysis-only -> candidate generated (hidden 0 candidates);
* independently verified -> promoted (skips generalized and lacks approval).

Writes ``artifacts/phase8d-promotion-2026-11-17``.  No record is promoted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import promotion_gate  # noqa: E402

OUT_REL = "artifacts/phase8d-promotion-2026-11-17"
GENERATED_AT = "2026-11-17T00:00:00Z"
KIND = "phase8d_promotion_evaluation"
PUBLIC_RESULTS = "benchmark/phase8c/results.json"
PUBLIC_MANIFEST = "benchmark/phase8c/manifest.json"
HIDDEN_AGGREGATE = "artifacts/phase8c-hidden-2026-11-16/aggregate.json"
HIDDEN_COMMITMENT = "benchmark/phase8c/hidden-commitment.json"
PUBLIC_BENCHMARK_DIR = "artifacts/phase8c-benchmark-2026-11-16"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sample(results: Mapping[str, Any], sample_id: str) -> Mapping[str, Any]:
    for item in results.get("samples") or []:
        if isinstance(item, Mapping) and item.get("sample_id") == sample_id:
            return item
    raise SystemExit(f"sample {sample_id!r} missing from public results")


def _verifier_report(sample_id: str) -> dict[str, Any]:
    path = ROOT / PUBLIC_BENCHMARK_DIR / "samples" / sample_id / "verifier-report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _evidence_refs(sample_id: str, report: Mapping[str, Any]) -> list[str]:
    refs = [
        f"{PUBLIC_MANIFEST}#samples[id={sample_id}]",
        f"{PUBLIC_RESULTS}#samples[id={sample_id}]",
    ]
    if report:
        refs.append(f"{PUBLIC_BENCHMARK_DIR}/samples/{sample_id}/verifier-report.json")
    return refs


def build_payload() -> dict[str, Any]:
    results = _load(PUBLIC_RESULTS)
    hidden = _load(HIDDEN_AGGREGATE)
    commitment = _load(HIDDEN_COMMITMENT)
    stack = _sample(results, "stack-strcpy-x86_64")
    heap = _sample(results, "heap-malloc")
    hidden_sha = _sha(ROOT / HIDDEN_AGGREGATE)
    commitment_sha = str(commitment.get("commitment_sha256") or "")
    disagreements_path = ROOT / PUBLIC_BENCHMARK_DIR / "disagreements.json"
    disagreements = (json.loads(disagreements_path.read_text(encoding="utf-8"))
                     if disagreements_path.is_file() else [])
    if not isinstance(disagreements, list):
        disagreements = []
    stack_report = _verifier_report("stack-strcpy-x86_64")
    heap_report = _verifier_report("heap-malloc")
    hidden_agg = hidden.get("aggregate") or {}
    hidden_denominator = hidden_agg.get("denominator") or {}
    hidden_verified = int(hidden_agg.get("verified_count") or 0)
    public_verified = int((results.get("aggregate") or {}).get("verified_count") or 0)
    public_refs = _evidence_refs("stack-strcpy-x86_64", stack_report)
    heap_refs = _evidence_refs("heap-malloc", heap_report)

    generalization = {
        "public_verified": public_verified >= 1,
        "public_verified_count": public_verified,
        "hidden_verified": hidden_verified > 0,
        "hidden_verified_count": hidden_verified,
        "holdout_verified": False,
        "regression_pass": bool(stack.get("regression") is True),
        "false_verified": int((results.get("aggregate") or {}).get("false_verified_count") or 0),
        "hidden_commitment_sha256": commitment_sha,
        "hidden_aggregate_sha256": hidden_sha,
        "evidence_refs": [
            *public_refs,
            f"{HIDDEN_AGGREGATE}#aggregate",
            f"{HIDDEN_COMMITMENT}#commitment_sha256",
        ],
        "no_unresolved_blockers": False,
        "hidden_denominator": hidden_denominator,
    }
    approval_missing = {
        "generalized_evidence_complete": True,
        "generalization": generalization,
    }
    stack_record = {
        "record_id": "phase8c-stack-strcpy-x86_64",
        "current_state": "independently_verified",
        "prior_state_evidence_complete": True,
        "prior_evidence_refs": public_refs,
        "state_history": [
            "discovered", "analysis_only", "candidate_generated",
            "independently_verified",
        ],
    }
    heap_record = {
        "record_id": "phase8c-heap-malloc",
        "current_state": "candidate_generated",
        "prior_state_evidence_complete": True,
        "prior_evidence_refs": heap_refs,
        "state_history": ["discovered", "analysis_only", "candidate_generated"],
    }
    hidden_record = {
        "record_id": "phase8c-hidden-runtime",
        "current_state": "analysis_only",
        "prior_state_evidence_complete": True,
        "prior_evidence_refs": [
            f"{HIDDEN_AGGREGATE}#aggregate",
            f"{HIDDEN_COMMITMENT}#samples",
        ],
    }
    decisions: list[dict[str, Any]] = []

    # 1) verified public fixture -> generalized: hidden has zero verified.
    decisions.append(promotion_gate.evaluate_transition(
        stack_record, target="generalized",
        evidence={"generalization": generalization},
    ))

    # 2) skip directly to promoted: illegal jump, no approval.
    decisions.append(promotion_gate.evaluate_transition(
        stack_record, target="promoted",
        evidence={
            "generalization": generalization,
            "approval": {},
            "generalized_evidence_complete": True,
        },
    ))

    # 3) heap-malloc candidate -> independently verified: independent rejected.
    heap_verification = {
        "decision": str((heap.get("verification") or {}).get("decision") or "not_run"),
        "independent": True,
        "oracle_executed": (heap.get("environment") or {}).get("oracle_status") == "executed",
        "false_verified": 0,
        "false_verified_internal": 1 if any(
            item.get("sample_id") == "heap-malloc" for item in disagreements) else 0,
        "regression_pass": bool(heap.get("regression") is True),
        "evidence_refs": [
            *heap_refs,
            f"{PUBLIC_BENCHMARK_DIR}/disagreements.json#0",
        ],
    }
    decisions.append(promotion_gate.evaluate_transition(
        heap_record, target="independently_verified",
        evidence={"verification": heap_verification},
    ))

    # 4) hidden analysis-only -> candidate generated: hidden produced 0 candidates.
    decisions.append(promotion_gate.evaluate_transition(
        hidden_record, target="candidate_generated",
        evidence={
            "candidate": {
                "candidate_sha256": None,
                "patch_plan_sha256": None,
                "integrity_evidence_refs": [],
            },
            "hidden_aggregate": {
                "sample_count": hidden_agg.get("sample_count"),
                "candidate_count": 0,
                "verified_count": hidden_verified,
                "status_counts": hidden_agg.get("status_counts"),
            },
        },
    ))

    denied = sum(1 for item in decisions if item["decision"] != "allowed")
    payload = {
        "schema_version": 1,
        "kind": KIND,
        "generated_at": GENERATED_AT,
        "purpose": "Evaluate Phase-8C evidence through the Phase-8D promotion gate; no capability promotion.",
        "policy": {
            "states": list(promotion_gate.STATES),
            "legal_next": promotion_gate.LEGAL_NEXT,
            "auto_promotion": False,
            "not_run_is_pass": False,
            "human_review_required_for": ["generalized", "promoted"],
            "hidden_and_holdout_required_for": ["generalized", "promoted"],
        },
        "inputs": {
            "public_results": {"path": PUBLIC_RESULTS, "sha256": _sha(ROOT / PUBLIC_RESULTS)},
            "public_manifest": {"path": PUBLIC_MANIFEST, "sha256": _sha(ROOT / PUBLIC_MANIFEST)},
            "hidden_aggregate": {"path": HIDDEN_AGGREGATE, "sha256": hidden_sha},
            "hidden_commitment": {"path": HIDDEN_COMMITMENT, "sha256": _sha(ROOT / HIDDEN_COMMITMENT)},
        },
        "summary": {
            "decision_count": len(decisions),
            "allowed_count": len(decisions) - denied,
            "denied_count": denied,
            "promoted_count": 0,
            "capability_promotion": False,
            "hidden_verified_count": hidden_verified,
            "public_verified_count": public_verified,
            "published_false_verified": (results.get("aggregate") or {}).get("false_verified_count"),
            "internal_withdrawn": len(disagreements),
        },
        "decisions": decisions,
        "limitations": [
            "no capability was promoted; all Phase-8C transitions above are denied",
            "the public fixture's verification is not hidden or holdout generalization evidence",
            "heap-malloc's independent ABI rejection is preserved; its deterministic claim is withdrawn",
            "hidden has 0 candidates and 0 independently verified samples; hidden generalisation is not established",
            "a promotion decision would also require independent human approval and a complete generalized evidence bundle",
            "not_run/blocked evidence is never treated as a pass",
        ],
        "capability_promotion": False,
        "verification_is_not_capability": True,
    }
    return payload


def build_artifacts() -> dict[str, bytes]:
    payload = build_payload()
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    summary = payload["summary"]
    readme = (
        "# Phase-8D promotion gate evaluation\n\n"
        f"- generated_at: `{payload['generated_at']}` (fixed)\n"
        f"- decisions: {summary['decision_count']} (allowed {summary['allowed_count']}, denied {summary['denied_count']})\n"
        f"- capability_promotion: **false**; promoted_count={summary['promoted_count']}\n"
        f"- public verified: {summary['public_verified_count']}; hidden verified: {summary['hidden_verified_count']}\n"
        f"- published false_verified: {summary['published_false_verified']}; internal withdrawn: {summary['internal_withdrawn']}\n\n"
        "| record | transition | decision | first violations |\n"
        "|---|---|---|---|\n"
        + "\n".join(
            "| `{}` | {} -> {} | {} | {} |".format(
                item["record_id"], item["from_state"], item["target_state"],
                item["decision"], "; ".join(item["violations"][:3]) or "-"
            )
            for item in payload["decisions"]
        )
        + "\n\n## Policy\n\n"
        "The gate permits only the next legal state and requires prior-state "
        "evidence, independently executed verification, hidden/holdout evidence, "
        "bounded regression, false_verified=0, and independent human approval at "
        "promotion. It has no auto-promotion path and never treats not_run as pass.\n\n"
        "## Limitations\n\n" + "\n".join(f"- {item}" for item in payload["limitations"]) + "\n"
    ).encode("utf-8")
    files = {"promotion.json": data, "README.md": readme}
    sums = []
    for name in sorted(("promotion.json", "README.md")):
        sums.append(f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n")
    files["SHA256SUMS"] = "".join(sums).encode("utf-8")
    return files


def check_artifact(out_dir: Path = ROOT / OUT_REL) -> list[str]:
    problems: list[str] = []
    files = build_artifacts()
    for name, expected in files.items():
        path = out_dir / name
        if not path.is_file():
            problems.append(f"missing {name}")
        elif path.read_bytes() != expected:
            problems.append(f"artifact differs from deterministic build: {name}")
    try:
        payload = json.loads((out_dir / "promotion.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - report a typed problem
        payload = {}
    if payload.get("capability_promotion") is not False:
        problems.append("capability_promotion must be false")
    if payload.get("summary", {}).get("promoted_count") != 0:
        problems.append("no promoted decision may be recorded")
    if payload.get("summary", {}).get("denied_count", 0) < 1:
        problems.append("expected at least one denied transition")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / OUT_REL)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifact(args.out)
        print(json.dumps({"ok": not problems, "problems": problems}, indent=2) if args.json
              else "phase8d-promotion: " + ("check OK" if not problems else f"{len(problems)} problem(s)"))
        return 0 if not problems else 1
    payload = build_payload()
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        for name, data in build_artifacts().items():
            (args.out / name).write_bytes(data)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"phase8d-promotion: decisions={len(payload['decisions'])} "
              f"denied={payload['summary']['denied_count']} promoted=0")
        for item in payload["decisions"]:
            print(f"  {item['record_id']}: {item['from_state']}->{item['target_state']} "
                  f"{item['decision']} ({item['violations'][0] if item['violations'] else '-'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
