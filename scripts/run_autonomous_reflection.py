#!/usr/bin/env python3
"""Run the reflection engine over committed audit artifacts.

The script reads the committed phase-7 audit artifacts (no network, no LLM,
no dynamic probes), builds one reflection record per observed failure/unknown,
and writes a deterministic evidence bundle:

    artifacts/autonomous-reflection-2026-11-16/
        reflection.json    records + inputs + not_run + summary + limitations
        README.md          human-readable contract and current state
        SHA256SUMS         sha256 of reflection.json and README.md

Missing or unreadable inputs are **never fabricated**: they are recorded as
explicit ``not_run`` entries with a reason, the remaining readable inputs are
still processed honestly, and the process exits ``2`` (not_run) instead of
pretending success.  Exit codes:

* ``0`` all inputs read, every record valid, and (in ``--check`` mode) the
  committed bundle matches a fresh build;
* ``1`` a contract violation (question missing, invalid decision, ``verified``
  not false, candidate without evidence, artifact tampered/mismatched);
* ``2`` one or more required inputs are missing/unreadable (explicit not_run,
  no data invented).

The reflection engine never repairs, never promotes capability and always
records ``verified: false``; see ``app/services/reflection_engine.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import reflection_engine as engine  # noqa: E402

OUTPUT_DIR = Path("artifacts/autonomous-reflection-2026-11-16")
REFLECTION_JSON = "reflection.json"
README = "README.md"
SHA256SUMS = "SHA256SUMS"

INPUT_SPECS: tuple[dict[str, str], ...] = (
    {
        "key": "gap_candidates",
        "path": "artifacts/gap-registry-2026-11-16/candidates.json",
        "label": "Gap Registry candidate records",
    },
    {
        "key": "acceptance_audit",
        "path": "artifacts/acceptance-model-audit-2026-11-16/report.json",
        "label": "Acceptance-model audit report",
    },
    {
        "key": "coverage_matrix",
        "path": "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json",
        "label": "Capability-gap audit coverage matrix",
    },
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def read_input(root: Path, relative: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Read one JSON input, returning ``(payload, info)`` without inventing data."""
    path = root / relative
    info: dict[str, Any] = {
        "path": relative,
        "sha256": None,
        "status": "not_run",
        "reason": "",
    }
    if not path.is_file():
        info["reason"] = "input artifact does not exist in this checkout"
        return None, info
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        info["reason"] = f"input artifact is unreadable or invalid JSON: {type(exc).__name__}"
        return None, info
    info["sha256"] = _sha256_bytes(raw)
    info["status"] = "read"
    return payload, info


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _first_list(payload: Any, keys: Iterable[str]) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            values = payload.get(key)
            if isinstance(values, list):
                return values
    return []


def _evidence_ref(kind: str, ref: str, note: str = "", sha256: str | None = None) -> engine.EvidenceRef:
    return engine.EvidenceRef(kind=kind, ref=ref, sha256=sha256, note=note)




def _gap_category_hint(category: str, discovery_source: str) -> str:
    """Map a Gap Registry category to a reflection hint (never a default)."""
    if category == "case_target_analysis_failure":
        return "capability"
    if category in {"audit_meta_mismatch_regression", "platform_capability_differential"}:
        return "evaluation"
    if category == "universe_dimension_gap":
        return "knowledge"
    if discovery_source == "failure_driven":
        return "evaluation"
    if discovery_source == "knowledge":
        return "knowledge"
    return "unknown"

def observe_gap_candidates(payload: dict[str, Any], path: str) -> list[engine.FailureObservation]:
    """One observation per Gap Registry candidate (no default capability hint)."""
    candidates = _first_list(payload, ("candidates", "gaps", "records"))
    observations: list[engine.FailureObservation] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        gap_id = str(candidate.get("gap_id") or candidate.get("id") or f"candidate-{index}")
        evidence_values = _as_list(candidate.get("evidence_refs") or candidate.get("evidence"))
        evidence: list[engine.EvidenceRef] = []
        for item in evidence_values:
            if isinstance(item, dict):
                ref = str(item.get("ref") or item.get("path") or item.get("gap_id") or "")
                sha = item.get("sha256") if isinstance(item.get("sha256"), str) else None
                kind = str(item.get("kind") or ("gap" if ref == gap_id else "artifact"))
                if ref:
                    evidence.append(_evidence_ref(kind, ref, sha256=sha))
            elif str(item).strip():
                text = str(item).strip()
                kind = "infrastructure" if text.startswith(("probe:", "runner:")) else "artifact"
                evidence.append(_evidence_ref(kind, text))
        target_value = candidate.get("target")
        target: dict[str, Any] = target_value if isinstance(target_value, dict) else {}
        pointer = str(
            target.get("cell")
            or target.get("id")
            or target.get("kind")
            or candidate.get("cell")
            or candidate.get("target")
            or ""
        )
        category = str(candidate.get("category") or "")
        hint = _gap_category_hint(category, str(candidate.get("discovery_source") or ""))
        refs = [value for value in (pointer, gap_id) if value]
        metadata: dict[str, Any] = {
            "failure_type": hint if evidence else "unknown",
            "capability_id": pointer,
            "source_artifact": path,
            "category": category,
        }
        samples = _as_list(candidate.get("samples"))
        if not samples:
            sample_value = candidate.get("subcategory") or pointer
            samples = [sample_value] if sample_value else []
        if samples:
            metadata["samples"] = [str(sample) for sample in samples]
        expected = str(
            candidate.get("expected")
            or "the recorded capability gap is resolved with committed, independently "
               "verifiable evidence"
        )
        observed = str(
            candidate.get("observed_failure")
            or candidate.get("observed")
            or candidate.get("status")
            or "candidate recorded without a measured observation"
        )
        observations.append(engine.FailureObservation(
            source=f"gap-registry:{path}#{gap_id}",
            expected=expected,
            observed=observed,
            evidence=evidence,
            refs=refs,
            observation_id=f"gap-{gap_id}",
            metadata=metadata,
        ))
    return observations


def observe_acceptance_audit(payload: dict[str, Any], path: str) -> list[engine.FailureObservation]:
    """One observation per acceptance-audit case; these are evaluation mismatches."""
    cases = _first_list(payload, ("results", "cases", "findings", "mismatches"))
    observations: list[engine.FailureObservation] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id") or case.get("id") or f"case-{index}")
        mismatches = case.get("expected_mismatches") or case.get("mismatches") or []
        if isinstance(mismatches, str):
            mismatches = [mismatches]
        mismatch_ids = [str(item) for item in _as_list(mismatches) if str(item).strip()]
        if not mismatch_ids:
            continue
        expected = str(case.get("expected") or "the matcher reports no acceptance mismatch")
        observed = "acceptance mismatch ids: " + ", ".join(mismatch_ids)
        evidence = [
            _evidence_ref("artifact", f"{path}#{case_id}", note="acceptance audit case")
            for _ in [0]
        ]
        evidence.extend(
            _evidence_ref("gap", mismatch_id, note="acceptance mismatch class")
            for mismatch_id in mismatch_ids
        )
        observations.append(engine.FailureObservation(
            source=f"acceptance-audit:{path}#{case_id}",
            expected=expected,
            observed=observed,
            evidence=evidence,
            refs=[case_id, *mismatch_ids],
            observation_id=f"acceptance-{case_id}",
            metadata={
                "failure_type": "evaluation",
                "source_artifact": path,
                "samples": mismatch_ids,
            },
        ))
    return observations


def observe_coverage_matrix(payload: dict[str, Any], path: str) -> list[engine.FailureObservation]:
    """One observation per open/dynamic/mitigated audit gap (closed/non-goal skipped)."""
    gaps = _first_list(payload, ("gaps", "rows"))
    observations: list[engine.FailureObservation] = []
    for index, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            continue
        status = str(gap.get("status") or "")
        if status not in {"open", "dynamic_unverified", "mitigated"}:
            continue
        category = str(gap.get("category") or "")
        gap_id = str(gap.get("gap_id") or f"gap-{index}")
        if category == "non_goal":
            continue
        if category == "engine_gap":
            hint = "capability"
        elif category in {"gate_mismatch", "matrix_claim_mismatch", "oracle_gap"}:
            hint = "evaluation"
        elif category == "runtime_gap":
            hint = "infrastructure"
        else:
            hint = "unknown"
        evidence: list[engine.EvidenceRef] = []
        for item in _as_list(gap.get("evidence")):
            text = str(item).strip()
            if not text:
                continue
            if text.startswith(("probe:", "runner:", "runner ")) or "lima" in text.lower():
                kind = "infrastructure"
            elif text.startswith(("artifact:", "module:", "census:")):
                kind = "artifact"
            else:
                kind = "log"
            evidence.append(_evidence_ref(kind, text))
        refs = [gap_id]
        lead_ref = gap.get("lead_ref")
        if isinstance(lead_ref, str) and lead_ref:
            refs.append(lead_ref)
        metadata: dict[str, Any] = {
            "failure_type": hint if evidence else "unknown",
            "source_artifact": path,
            "category": category,
        }
        if hint == "capability" and evidence:
            metadata["capability_id"] = category
        observations.append(engine.FailureObservation(
            source=f"coverage-audit:{path}#{gap_id}",
            expected=str(gap.get("expected") or f"{category} gap is closed with committed evidence"),
            observed=str(gap.get("symptom") or gap.get("observed") or status),
            evidence=evidence,
            refs=refs,
            observation_id=f"coverage-{gap_id}",
            metadata=metadata,
        ))
    return observations


def build_bundle(root: Path) -> dict[str, Any]:
    """Build the deterministic reflection bundle payload (no writes)."""
    inputs: dict[str, dict[str, Any]] = {}
    not_run: list[dict[str, Any]] = []
    observations: list[engine.FailureObservation] = []
    builders = {
        "gap_candidates": observe_gap_candidates,
        "acceptance_audit": observe_acceptance_audit,
        "coverage_matrix": observe_coverage_matrix,
    }
    for spec in INPUT_SPECS:
        payload, info = read_input(root, spec["path"])
        inputs[spec["key"]] = {**info, "label": spec["label"]}
        if payload is None:
            not_run.append({
                "input": spec["key"],
                "path": spec["path"],
                "reason": info["reason"],
            })
            continue
        observations.extend(builders[spec["key"]](payload, spec["path"]))
    observations = sorted(observations, key=lambda item: (item.source, item.observation_id))
    records = [engine.reflect(observation) for observation in observations]
    violations: list[str] = []
    for record in records:
        violations.extend(engine.validate_record(record))
    failure_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}
    for record in records:
        failure_counts[record["failure_type"]] = failure_counts.get(record["failure_type"], 0) + 1
        decision_counts[record["capability_decision"]] = decision_counts.get(record["capability_decision"], 0) + 1
    limitations = [
        "reflection records are analysis inputs, not verification: verified is always false",
        "a candidate decision only proposes a bounded experiment; it never promotes a capability",
        "no network/LLM is used; only committed artifacts are read",
        "missing inputs are recorded as explicit not_run entries and are never fabricated",
    ]
    if not records:
        limitations.append(
            "no observation was derivable from the readable inputs; the reflection bundle "
            "is empty rather than inventing failures"
        )
    payload: dict[str, Any] = {
        "schema_version": engine.SCHEMA_VERSION,
        "kind": "autonomous_reflection",
        "engine": "app/services/reflection_engine.py",
        "contract": {
            "questions": list(engine.QUESTION_IDS),
            "question_count": len(engine.QUESTION_IDS),
            "capability_decisions": list(engine.CAPABILITY_DECISIONS),
            "failure_types": list(engine.FAILURE_TYPES),
            "verified": False,
        },
        "inputs": {key: inputs[key] for key in sorted(inputs)},
        "not_run": sorted(not_run, key=lambda item: item["input"]),
        "records": sorted(records, key=lambda item: item["reflection_id"]),
        "summary": {
            "records": len(records),
            "questions_per_record": len(engine.QUESTION_IDS),
            "verified_true_count": sum(1 for record in records if record["verified"] is not False),
            "failure_type_counts": {key: failure_counts[key] for key in sorted(failure_counts)},
            "capability_decision_counts": {
                key: decision_counts[key] for key in sorted(decision_counts)
            },
            "candidate_records": [
                record["reflection_id"]
                for record in records
                if record["capability_decision"] == "candidate"
            ],
        },
        "violations": violations,
        "limitations": limitations,
    }
    return payload


def render_readme(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    inputs = payload["inputs"]
    lines = [
        "# Autonomous reflection evidence (2026-11-16)",
        "",
        "Generated by `scripts/run_autonomous_reflection.py` from committed audit",
        "artifacts only (no network, no LLM, no dynamic probes).",
        "",
        "## Contract",
        "",
        f"- 12-question contract: {summary['questions_per_record']} questions per record,",
        "  each with `answer`/`evidence`/`status` (`answered` or `unknown`).",
        "- `verified` is always `false`; a reflection never verifies or repairs anything.",
        "- `capability_decision` is one of `analysis_only` / `candidate` / `not_run`.",
        "- No evidence => `not_run`; infrastructure failures never become capability gaps.",
        "- `experiment_plan` always carries samples, acceptance criteria, independent",
        "  verification and regression checks; it is `cannot_plan` when evidence is",
        "  insufficient (the reason is recorded).",
        "",
        "## Inputs",
        "",
        "| input | status | sha256 |",
        "|---|---|---|",
    ]
    for key in sorted(inputs):
        info = inputs[key]
        lines.append(
            f"| `{key}` ({info['path']}) | {info['status']} | "
            f"`{info['sha256'] or 'n/a'}` |"
        )
    not_run = payload["not_run"]
    lines.extend(["", "## Not run", ""])
    if not_run:
        for item in not_run:
            lines.append(f"- `{item['input']}`: {item['reason']}")
    else:
        lines.append("- none (all required inputs were readable)")
    lines.extend([
        "",
        "## Summary",
        "",
        f"- records: {summary['records']}",
        f"- failure types: {summary['failure_type_counts']}",
        f"- capability decisions: {summary['capability_decision_counts']}",
        f"- verified_true_count: {summary['verified_true_count']} (must be 0)",
        f"- candidate records: {summary['candidate_records'] or 'none'}",
        "",
        "## Safety",
        "",
        "This bundle is analysis evidence only. It does not claim a new repair",
        "capability, does not upgrade any verified disposition, and does not",
        "replace the release gate. A `candidate` is a bounded experiment proposal,",
        "never a verified patch.",
        "",
        "## Exit codes",
        "",
        "- 0: inputs readable, records valid (and committed bundle matches in --check)",
        "- 1: contract violation or tampered/mismatched committed bundle",
        "- 2: one or more required inputs missing/unreadable (explicit not_run; no data invented)",
        "",
    ])
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_bundle(out_dir: Path, payload: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / REFLECTION_JSON, payload)
    (out_dir / README).write_text(render_readme(payload) + "\n", encoding="utf-8")
    lines = []
    for name in (REFLECTION_JSON, README):
        lines.append(f"{_sha256_file(out_dir / name)}  {name}")
    (out_dir / SHA256SUMS).write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_bundle(out_dir: Path) -> list[str]:
    """Validate SHA256SUMS and the reflection payload contract of a bundle."""
    violations: list[str] = []
    sums_path = out_dir / SHA256SUMS
    if not sums_path.is_file():
        return [f"{out_dir / SHA256SUMS}: missing"]
    for raw in sums_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            violations.append(f"SHA256SUMS: cannot parse {line!r}")
            continue
        digest, name = parts
        target = out_dir / name.lstrip("*")
        if not target.is_file():
            violations.append(f"SHA256SUMS references missing file {name}")
        elif _sha256_file(target) != digest:
            violations.append(f"SHA256SUMS mismatch for {name}")
    reflection_path = out_dir / REFLECTION_JSON
    if not reflection_path.is_file():
        return violations + [f"{reflection_path}: missing"]
    try:
        payload = json.loads(reflection_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return violations + [f"{reflection_path}: invalid JSON: {exc}"]
    if payload.get("kind") != "autonomous_reflection":
        violations.append("reflection.json kind must be 'autonomous_reflection'")
    records = payload.get("records")
    if not isinstance(records, list):
        return violations + ["reflection.json records must be a list"]
    for record in records:
        violations.extend(engine.validate_record(record))
    summary = payload.get("summary") or {}
    if summary.get("verified_true_count") != 0:
        violations.append("summary.verified_true_count must be 0")
    return violations


def _comparable(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reflect over committed phase-7 audit artifacts (offline).",
    )
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root (default: this checkout; tests only)")
    parser.add_argument("--out", type=Path, default=None,
                        help=f"bundle directory (default: {OUTPUT_DIR})")
    parser.add_argument("--check", action="store_true",
                        help="verify the committed bundle against a fresh build; never writes")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    out_dir = (args.out or (root / OUTPUT_DIR)).resolve()
    payload = build_bundle(root)
    not_run = payload["not_run"]
    violations = list(payload["violations"])
    exit_code = 0
    if violations:
        exit_code = 1
    elif not_run:
        exit_code = 2
    if args.check:
        existing = out_dir / REFLECTION_JSON
        if not existing.is_file():
            violations.append(f"{existing}: committed bundle is missing")
            exit_code = 1
        else:
            try:
                committed = json.loads(existing.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                violations.append(f"{existing}: invalid JSON: {exc}")
                exit_code = 1
            else:
                if _comparable(committed) != _comparable(payload):
                    violations.append(
                        "committed reflection.json differs from a fresh build "
                        "(inputs or engine changed; regenerate the bundle)"
                    )
                    exit_code = 1
                for violation in verify_bundle(out_dir):
                    violations.append(violation)
                    exit_code = 1
        if exit_code == 1 and not violations:
            exit_code = 1
    else:
        write_bundle(out_dir, payload)
        if args.json:
            payload = {**payload, "written_to": str(out_dir)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(
            "autonomous-reflection: {result} records={records} "
            "candidates={candidates} not_run={not_run} violations={violations} "
            "verified_true={verified_true}".format(
                result="OK" if exit_code == 0 else "NOT_OK",
                records=payload["summary"]["records"],
                candidates=len(payload["summary"]["candidate_records"]),
                not_run=len(payload["not_run"]),
                violations=len(violations),
                verified_true=payload["summary"]["verified_true_count"],
            )
        )
        for violation in violations:
            print(f"  FAIL {violation}")
        for item in payload["not_run"]:
            print(f"  NOT_RUN {item['input']}: {item['reason']}")
    if exit_code == 2 and violations:
        return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
