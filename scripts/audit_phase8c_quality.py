#!/usr/bin/env python3
"""Phase-8C C13: public/hidden quality audit.

Public-only mode (CI) validates the public corpus counts, v1->v2 migration,
v2 contracts, public evidence/SHA256SUMS, contamination/external artifacts and
hidden-content leak surfaces. Full mode additionally requires the explicit
``--hidden-root``, the hidden commitment and the C6 v2 results; missing
inputs are recorded as ``not_run`` and never faked as pass.

Artifacts: artifacts/phase8c-quality-2026-11-16/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
KIND = "phase8c_quality_audit"
PUBLIC = ROOT / "benchmark" / "phase8c"
PUBLIC_MANIFEST = PUBLIC / "manifest.json"
PUBLIC_SUMS = PUBLIC / "SHA256SUMS"
V1_MANIFEST = ROOT / "benchmark" / "phase8-v1" / "manifest.json"
ARTIFACT_DIR = ROOT / "artifacts" / "phase8c-quality-2026-11-16"
CONTAMINATION_ARTIFACT = (ROOT / "artifacts" /
                          "phase8c-contamination-2026-11-16" /
                          "contamination.json")
EXTERNAL_ARTIFACT = (ROOT / "artifacts" / "phase8c-external-2026-11-16" /
                     "external-ingestion.json")
V2_CONTRACTS = (
    "benchmark-manifest-v2.schema.json",
    "benchmark-results-v2.schema.json",
    "ground-truth-sample-v2.schema.json",
    "hidden-benchmark-commitment.schema.json",
)
EXPECTED_PUBLIC_CORE = 28
EXPECTED_PUBLIC_RUNTIME = 20
EXPECTED_PUBLIC_ANALYSIS = 8
MIN_HIDDEN_TOTAL = 8
MIN_HIDDEN_RUNTIME = 6
MIN_HIDDEN_ANALYSIS = 2
RUNTIME_KINDS = {"external_poc", "native", "emulated"}
HIDDEN_LEAK_PATTERNS = (
    ".binaryrepair",
    "phase8c-hidden",
    "PHASE8C_HIDDEN_ROOT",
)
DEFAULT_RESULTS_CANDIDATES = (
    ROOT / "artifacts" / "phase8c-benchmark-2026-11-16" / "results.json",
    ROOT / "artifacts" / "phase8c-results-2026-11-16" / "results.json",
    ROOT / "artifacts" / "phase8c-hidden-results-2026-11-16" / "results.json",
    ROOT / "artifacts" / "phase8c-hidden-2026-11-16" / "results.json",
)
DEFAULT_COMMITMENT = PUBLIC / "hidden-commitment.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(check_id: str, status: str, detail: str) -> dict[str, Any]:
    return {"id": check_id, "status": status, "detail": detail}


def _oracle_runtime(sample: dict[str, Any]) -> bool:
    oracle = sample.get("oracle") if isinstance(
        sample.get("oracle"), dict) else {}
    kinds = set(oracle.get("kinds") or [])
    if not kinds and oracle.get("kind"):
        kinds = {str(oracle["kind"])}
    return bool(kinds & RUNTIME_KINDS)


def _verify_sums_file(sums_path: Path, base: Path) -> list[str]:
    if not sums_path.is_file():
        return [f"missing {sums_path.relative_to(ROOT)}"]
    problems: list[str] = []
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2:
            problems.append(f"malformed SUMS line: {line!r}")
            continue
        expected, relative = parts[0], parts[1]
        path = base / relative
        if not path.is_file():
            problems.append(f"missing file {relative}")
        elif _sha256_file(path) != expected:
            problems.append(f"sha256 mismatch for {relative}")
    return problems


def _leak_scan(paths: list[Path]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in HIDDEN_LEAK_PATTERNS:
            if pattern in text:
                findings.append({"path": str(path.relative_to(ROOT)),
                                 "pattern": pattern})
    return findings


def _public_checks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    facts: dict[str, Any] = {}
    if not PUBLIC_MANIFEST.is_file():
        checks.append(_check("public-manifest", "fail",
                             "public manifest is missing"))
        return checks, facts
    try:
        manifest = _load_json(PUBLIC_MANIFEST)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        checks.append(_check("public-manifest", "fail",
                             f"manifest unreadable: {type(exc).__name__}"))
        return checks, facts
    samples = [sample for sample in manifest.get("samples", [])
               if isinstance(sample, dict)]
    core = [sample for sample in samples
            if not str(sample.get("sample_id", "")).startswith("variant-")]
    runtime = sum(1 for sample in core if _oracle_runtime(sample))
    analysis = len(core) - runtime
    split_counts = {"dev": sum(1 for sample in samples
                               if sample.get("split") == "dev"),
                    "validation": sum(1 for sample in samples
                                      if sample.get("split") == "validation")}
    facts.update({
        "manifest_path": str(PUBLIC_MANIFEST.relative_to(ROOT)),
        "manifest_sha256": _sha256_file(PUBLIC_MANIFEST),
        "sample_count": manifest.get("sample_count"),
        "actual_sample_count": len(samples),
        "split_counts": split_counts,
        "declared_split_counts": manifest.get("split_counts"),
        "core_count": len(core),
        "runtime_count": runtime,
        "analysis_only_count": analysis,
        "hidden_available": manifest.get("hidden_available"),
        "hidden_commitment": manifest.get("hidden_commitment"),
    })
    if manifest.get("sample_count") != len(samples):
        checks.append(_check("public-count", "fail",
                             "manifest sample_count != samples length"))
    else:
        checks.append(_check("public-count", "pass",
                             f"{len(samples)} samples"))
    if len(core) != EXPECTED_PUBLIC_CORE:
        checks.append(_check("public-core-count", "fail",
                             f"core {len(core)} != {EXPECTED_PUBLIC_CORE}"))
    else:
        checks.append(_check("public-core-count", "pass",
                             f"core {len(core)}"))
    if runtime != EXPECTED_PUBLIC_RUNTIME or analysis != (
            EXPECTED_PUBLIC_ANALYSIS):
        checks.append(_check(
            "public-runtime-analysis", "fail",
            f"runtime {runtime} != {EXPECTED_PUBLIC_RUNTIME} or analysis "
            f"{analysis} != {EXPECTED_PUBLIC_ANALYSIS}"))
    else:
        checks.append(_check("public-runtime-analysis", "pass",
                             f"{runtime} runtime / {analysis} analysis-only"))
    if manifest.get("split_counts") and manifest.get(
            "split_counts") != split_counts:
        checks.append(_check("public-split-counts", "fail",
                             "declared split_counts mismatch"))
    else:
        checks.append(_check("public-split-counts", "pass",
                             str(split_counts)))
    # v1 -> v2 migration.
    try:
        v1 = _load_json(V1_MANIFEST)
        public_by_id = {str(sample.get("sample_id")): sample
                        for sample in samples}
        migrated = 0
        missing: list[str] = []
        for sample in v1.get("samples", []):
            sample_id = str(sample.get("sample_id"))
            target = public_by_id.get(sample_id)
            if target is None:
                missing.append(sample_id)
                continue
            if target.get("binary_sha256") != sample.get("sha256"):
                missing.append(sample_id)
                continue
            migrated += 1
        facts["v1_migration"] = {"total": len(v1.get("samples", [])),
                                 "migrated": migrated, "missing": missing}
        if missing or migrated != 12:
            checks.append(_check("v1-migration", "fail",
                                 f"12/12 required; missing={missing}"))
        else:
            checks.append(_check("v1-migration", "pass", "12/12 lossless"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        checks.append(_check("v1-migration", "fail",
                             f"v1 manifest unreadable: {type(exc).__name__}"))
    # v2 contracts.
    present = [name for name in V2_CONTRACTS
               if (ROOT / "contracts" / name).is_file()]
    parsed = 0
    for name in present:
        try:
            _load_json(ROOT / "contracts" / name)
            parsed += 1
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    facts["v2_contracts"] = {"present": present,
                             "parsed": parsed,
                             "total": len(V2_CONTRACTS)}
    if parsed != len(V2_CONTRACTS):
        checks.append(_check("v2-contracts", "fail",
                             f"{parsed}/{len(V2_CONTRACTS)} parsed"))
    else:
        checks.append(_check("v2-contracts", "pass",
                             f"{parsed}/{len(V2_CONTRACTS)}"))
    # Public evidence SUMS.
    sums_problems = _verify_sums_file(PUBLIC_SUMS, PUBLIC)
    if sums_problems:
        checks.append(_check("public-sums", "fail",
                             "; ".join(sums_problems[:5])))
    else:
        checks.append(_check("public-sums", "pass",
                             "all corpus evidence hashes verify"))
    # Contamination verdict.
    try:
        contamination = _load_json(CONTAMINATION_ARTIFACT)
        facts["contamination"] = {
            "mode": contamination.get("mode"),
            "status": contamination.get("status"),
            "verdict": contamination.get("verdict"),
            "findings": len(contamination.get("exact_duplicates", []))
            + len(contamination.get("near_duplicates", [])),
        }
        if contamination.get("mode") != "public_only":
            checks.append(_check("contamination", "fail",
                                 "contamination artifact is not public-only"))
        elif contamination.get("verdict") == "contaminated":
            checks.append(_check("contamination", "fail",
                                 "public corpus is contaminated"))
        elif contamination.get("verdict") == "suspicious":
            checks.append(_check("contamination", "warning",
                                 "public corpus has suspicious findings"))
        else:
            checks.append(_check("contamination", "pass",
                                 "public contamination verdict clean"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        checks.append(_check("contamination", "not_run",
                             "contamination artifact absent"))
    # External ingestion/quarantine.
    try:
        external = _load_json(EXTERNAL_ARTIFACT)
        facts["external"] = {
            "status": external.get("status"),
            "accepted": external.get("accepted"),
            "rejected": external.get("rejected"),
            "merge": external.get("merge"),
        }
        merge = external.get("merge") or {}
        if merge.get("public_merge_performed") or merge.get(
                "hidden_merge_performed"):
            checks.append(_check("external-merge", "fail",
                                 "external ingestion merged without validation"))
        elif external.get("status") == "ok" and external.get("rejected"):
            checks.append(_check("external", "warning",
                                 f"{external['rejected']} rejected candidates"))
        else:
            checks.append(_check("external", "pass",
                                 f"status={external.get('status')}; no merge"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        checks.append(_check("external", "not_run",
                             "external ingestion artifact absent"))
    # Hidden leak scan of public files/reports.
    leaks = _leak_scan([
        PUBLIC_MANIFEST, PUBLIC / "README.md", PUBLIC / "PROVENANCE.json",
        CONTAMINATION_ARTIFACT.parent / "README.md",
        EXTERNAL_ARTIFACT.parent / "README.md",
    ])
    facts["leaks"] = leaks
    if leaks:
        checks.append(_check("hidden-leaks", "fail",
                             f"hidden paths in public files: {leaks[:5]}"))
    else:
        checks.append(_check("hidden-leaks", "pass",
                             "no hidden paths in public artifacts"))
    return checks, facts



def _hidden_checks(hidden_root: Path | None,
                   hidden_commitment: Path | None,
                   results_path: Path | None,
                   checks: list[dict[str, Any]],
                   facts: dict[str, Any],
                   contamination_path: Path | None = None) -> None:
    if hidden_root is None:
        checks.append(_check("hidden", "not_run",
                             "hidden root not supplied (public-only mode)"))
        return
    if not hidden_root.is_dir():
        checks.append(_check("hidden", "not_run",
                             "hidden root is missing or not a directory"))
        return
    commitment_path = hidden_commitment or DEFAULT_COMMITMENT
    if not commitment_path.is_file():
        checks.append(_check(
            "hidden-commitment", "not_run",
            "hidden commitment artifact is absent (C4/C6 not landed)"))
        return
    try:
        commitment = _load_json(commitment_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        checks.append(_check("hidden-commitment", "fail",
                             f"commitment unreadable: {type(exc).__name__}"))
        return
    required = ("sample_count", "runtime_count", "analysis_only_count",
                "commitment_sha256", "public_manifest_sha256", "samples")
    missing = [field for field in required if field not in commitment]
    if missing:
        checks.append(_check("hidden-commitment", "fail",
                             f"missing commitment fields: {missing}"))
        return
    facts["hidden_commitment"] = {
        "path": str(commitment_path.relative_to(ROOT))
        if commitment_path.is_relative_to(ROOT) else str(commitment_path),
        "sample_count": commitment.get("sample_count"),
        "runtime_count": commitment.get("runtime_count"),
        "analysis_only_count": commitment.get("analysis_only_count"),
        "commitment_sha256": commitment.get("commitment_sha256"),
        "public_manifest_sha256": commitment.get("public_manifest_sha256"),
        "samples": len(commitment.get("samples") or []),
    }
    count = int(commitment.get("sample_count") or 0)
    runtime = int(commitment.get("runtime_count") or 0)
    analysis = int(commitment.get("analysis_only_count") or 0)
    problems: list[str] = []
    if count < MIN_HIDDEN_TOTAL:
        problems.append(f"hidden total {count} < {MIN_HIDDEN_TOTAL}")
    if runtime < MIN_HIDDEN_RUNTIME:
        problems.append(f"hidden runtime {runtime} < {MIN_HIDDEN_RUNTIME}")
    if analysis < MIN_HIDDEN_ANALYSIS:
        problems.append(f"hidden analysis-only {analysis} < "
                        f"{MIN_HIDDEN_ANALYSIS}")
    if runtime + analysis != count:
        problems.append("runtime + analysis-only != sample_count")
    if len(commitment.get("samples") or []) != count:
        problems.append("commitment samples length != sample_count")
    public_sha = _sha256_file(PUBLIC_MANIFEST) if PUBLIC_MANIFEST.is_file() \
        else None
    if commitment.get("public_manifest_sha256") != public_sha:
        problems.append("commitment public_manifest_sha256 mismatch")
    if problems:
        checks.append(_check("hidden-counts", "fail", "; ".join(problems)))
    else:
        checks.append(_check("hidden-counts", "pass",
                             f"{count} samples = {runtime} runtime + "
                             f"{analysis} analysis-only"))
    # Public manifest must advertise the hidden commitment consistently.
    try:
        public_manifest = _load_json(PUBLIC_MANIFEST)
        declared = public_manifest.get("hidden_commitment")
        declared_sha = str((declared or {}).get("commitment_sha256")
                           if isinstance(declared, dict) else "")
        facts["public_hidden_commitment"] = declared
        if not declared_sha:
            checks.append(_check(
                "hidden-public-consistency", "warning",
                "public manifest does not advertise the hidden commitment yet "
                "(separate commitment artifact is validated)"))
        elif declared_sha != str(commitment.get("commitment_sha256")):
            checks.append(_check(
                "hidden-public-consistency", "fail",
                "public manifest hidden commitment does not match artifact"))
        else:
            checks.append(_check("hidden-public-consistency", "pass",
                                 "public manifest commitment matches"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        checks.append(_check("hidden-public-consistency", "fail",
                             "public manifest unreadable"))
    # Hidden contamination must have been audited separately (independent of
    # whether the hidden campaign already produced an aggregate).
    contamination_file = contamination_path or CONTAMINATION_ARTIFACT
    try:
        contamination = _load_json(contamination_file)
        if contamination.get("mode") != "hidden" or contamination.get(
                "status") != "ok":
            checks.append(_check(
                "hidden-contamination", "not_run",
                "hidden-mode contamination audit has not run"))
        elif contamination.get("verdict") == "contaminated":
            checks.append(_check("hidden-contamination", "fail",
                                 "hidden-mode contamination verdict contaminated"))
        else:
            checks.append(_check("hidden-contamination", "pass",
                                 f"verdict={contamination.get('verdict')}"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        checks.append(_check("hidden-contamination", "not_run",
                             "hidden contamination artifact absent"))
    # C6 v2 results (public aggregate + hidden aggregate when the hidden lane
    # has executed; hidden_aggregate=null is explicitly not_run, never pass).
    candidates = [results_path] if results_path is not None else \
        [path for path in DEFAULT_RESULTS_CANDIDATES if path.is_file()]
    if not candidates:
        checks.append(_check("results-v2", "not_run",
                             "C6 v2 results are absent"))
        return
    path = candidates[0]
    if not path.is_file():
        checks.append(_check("results-v2", "not_run",
                             "C6 v2 results are missing"))
        return
    try:
        results = _load_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        checks.append(_check("results-v2", "fail",
                             f"results unreadable: {type(exc).__name__}"))
        return
    facts["results"] = {"path": str(path.relative_to(ROOT))
                        if path.is_relative_to(ROOT) else str(path),
                        "sha256": _sha256_file(path)}
    problems: list[str] = []
    samples = results.get("samples")
    aggregate = results.get("aggregate")
    hidden_aggregate = results.get("hidden_aggregate")
    if not isinstance(samples, list):
        problems.append("results samples missing")
    if not isinstance(aggregate, dict):
        problems.append("results aggregate missing")
    status_counts: dict[str, int] = {}
    if isinstance(samples, list):
        for item in samples:
            if isinstance(item, dict):
                key = str(item.get("status") or "unknown")
                status_counts[key] = status_counts.get(key, 0) + 1
    denominator = 0
    if isinstance(aggregate, dict):
        raw_denominator = aggregate.get("denominator")
        if isinstance(raw_denominator, dict):
            denominator = int(raw_denominator.get("samples") or 0)
        elif isinstance(raw_denominator, int):
            denominator = raw_denominator
        denominator = denominator or int(aggregate.get("sample_count") or 0)
        false_verified = int(aggregate.get("false_verified_count",
                                           aggregate.get("false_verified", 0))
                             or 0)
        if false_verified != 0:
            problems.append(f"false_verified={false_verified} (must be 0)")
        if denominator != len(samples):
            problems.append(f"aggregate denominator {denominator} != "
                            f"samples {len(samples)}")
        executed = int(
            (raw_denominator or {}).get("executed", 0)
            if isinstance(raw_denominator, dict) else
            status_counts.get("executed", 0))
        if executed and executed != status_counts.get("executed", 0):
            problems.append("aggregate executed count does not match statuses")
    if problems:
        checks.append(_check("results-v2", "fail", "; ".join(problems)))
        return
    checks.append(_check(
        "results-v2", "pass",
        f"public denominator={denominator}, "
        f"statuses={status_counts}, false_verified=0"))
    if not isinstance(hidden_aggregate, dict):
        checks.append(_check(
            "hidden-aggregate", "not_run",
            "hidden_aggregate is null/absent (hidden lane has not executed)"))
        return
    hidden_problems: list[str] = []
    hidden_count = int(hidden_aggregate.get("sample_count")
                       or hidden_aggregate.get("samples") or 0)
    hidden_false = int(hidden_aggregate.get(
        "false_verified_count", hidden_aggregate.get("false_verified", 0))
        or 0)
    if hidden_false != 0:
        hidden_problems.append(f"hidden false_verified={hidden_false}")
    if hidden_count != int(commitment.get("sample_count") or 0):
        hidden_problems.append(
            f"hidden aggregate samples {hidden_count} != commitment "
            f"{commitment.get('sample_count')}")
    if hidden_aggregate.get("per_sample_ids_included") is True:
        hidden_problems.append("hidden aggregate includes per-sample ids")
    if hidden_problems:
        checks.append(_check("hidden-aggregate", "fail",
                             "; ".join(hidden_problems)))
    else:
        checks.append(_check(
            "hidden-aggregate", "pass",
            f"hidden samples={hidden_count}, false_verified=0"))


    # Hidden contamination must have been audited separately.



def audit(full: bool = False, hidden_root: Path | None = None,
          hidden_commitment: Path | None = None,
          results_path: Path | None = None,
          contamination_path: Path | None = None) -> dict[str, Any]:
    checks, facts = _public_checks()
    if full:
        _hidden_checks(hidden_root, hidden_commitment, results_path,
                       checks, facts, contamination_path)
    hard_fail = any(item["status"] == "fail" for item in checks)
    hidden_not_run = any(item["id"].startswith(("hidden", "results-v2"))
                         and item["status"] == "not_run" for item in checks)
    if hard_fail:
        status = "fail"
    elif full and hidden_not_run:
        status = "not_run"
    elif full:
        status = "ok"
    else:
        status = "ok_public_only"
    report = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "mode": "full" if full else "public_only",
        "status": status,
        "public_manifest": facts.get("manifest_path"),
        "public_manifest_sha256": facts.get("manifest_sha256"),
        "counts": {
            key: facts.get(key) for key in (
                "sample_count", "actual_sample_count", "split_counts",
                "core_count", "runtime_count", "analysis_only_count",
                "hidden_available")
        },
        "v1_migration": facts.get("v1_migration"),
        "v2_contracts": facts.get("v2_contracts"),
        "contamination": facts.get("contamination"),
        "external": facts.get("external"),
        "leaks": facts.get("leaks"),
        "hidden_commitment": facts.get("hidden_commitment"),
        "results": facts.get("results"),
        "checks": checks,
        "hidden_available": facts.get("hidden_available"),
        "limitations": [
            "public-only mode is CI-capable and performs no hidden run",
            "full mode requires explicit hidden root/commitment/results and "
            "records not_run instead of faking a pass",
            "contamination/quality checks are evidence validation, not a proof "
            "of corpus correctness",
            "no network/AI is used",
        ],
        "capability_claims": [],
    }
    return report


def _readme(report: dict[str, Any]) -> str:
    lines = [
        "# Phase-8C quality audit (2026-11-16)",
        "",
        f"Mode: `{report['mode']}`; status: **{report['status']}**",
        "",
        "| check | status | detail |",
        "|---|---|---|",
    ]
    for item in report["checks"]:
        lines.append("| {} | {} | {} |".format(
            item["id"], item["status"],
            str(item["detail"]).replace("|", "/")[:300]))
    lines.extend([
        "",
        "Public-only mode is CI-capable. Full mode requires the hidden "
        "root/commitment/results; missing inputs are `not_run`, never pass.",
        "",
        "## Reproduce",
        "",
        "```",
        "python scripts/audit_phase8c_quality.py --public-only --write",
        "python scripts/audit_phase8c_quality.py --public-only --check",
        "python scripts/audit_phase8c_quality.py --full --hidden-root PATH "
        "--write",
        "```",
        "",
    ])
    return "\n".join(lines)


def _verify_sums(target: Path) -> list[str]:
    sums = target / "SHA256SUMS"
    if not sums.is_file():
        return [f"missing SHA256SUMS: {sums}"]
    problems: list[str] = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2:
            problems.append(f"malformed SHA256SUMS line: {line!r}")
            continue
        expected, relative = parts[0], parts[1]
        path = (target / relative).resolve()
        if not path.is_file():
            problems.append(f"file missing: {relative}")
        elif _sha256_file(path) != expected:
            problems.append(f"sha256 mismatch for {relative}")
    return problems


def write_artifacts(report: dict[str, Any],
                    artifact_dir: Path = ARTIFACT_DIR) -> dict[str, Any]:
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "quality.json": _canonical(report),
        "README.md": _readme(report),
    }
    sums: dict[str, str] = {}
    for name, content in files.items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        sums[name] = _sha256_file(path)
    sums_path = target / "SHA256SUMS"
    sums_path.write_text("\n".join(
        f"{digest}  {name}" for name, digest in sorted(sums.items())),
        encoding="utf-8")
    return {"artifact_dir": str(target), "sha256": sums,
            "sums_sha256": _sha256_file(sums_path)}


def check_artifact(artifact_dir: Path = ARTIFACT_DIR) -> list[str]:
    target = Path(artifact_dir)
    problems = _verify_sums(target)
    try:
        committed = _load_json(target / "quality.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return problems + [f"quality.json unreadable: {exc}"]
    if committed.get("kind") != KIND:
        problems.append("wrong quality artifact kind")
    if committed.get("mode") != "public_only":
        problems.append("committed artifact must be public-only")
    fresh = audit()
    if committed != fresh:
        problems.append("quality.json stale/tampered vs fresh public audit")
    readme = target / "README.md"
    if not readme.is_file() or readme.read_text(
            encoding="utf-8") != _readme(fresh):
        problems.append("README.md stale/tampered")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--public-only", action="store_true", default=False)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--hidden-root", type=Path, default=None)
    parser.add_argument("--hidden-commitment", type=Path, default=None)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--contamination", type=Path, default=None,
                        help="hidden-mode contamination artifact (default: "
                             "the public-only artifact, in which case full "
                             "mode stays not_run)")
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifact(args.artifact_dir)
        if problems:
            for problem in problems:
                print(f"QUALITY-VIOLATION: {problem}")
            return 1
        print("quality-audit: check OK (public-only, deterministic, "
              "SHA256SUMS verified)")
        return 0
    report = audit(full=bool(args.full and not args.public_only),
                   hidden_root=args.hidden_root,
                   hidden_commitment=args.hidden_commitment,
                   results_path=args.results,
                   contamination_path=args.contamination)
    if args.write:
        if report["mode"] == "full" and report["status"] == "not_run":
            print(json.dumps({"status": "not_run",
                              "meaning": "hidden/commitment/results inputs "
                                         "are absent; nothing faked"},
                             indent=2))
            return 0
        artifacts = write_artifacts(report, args.artifact_dir)
        print(f"quality-audit: wrote {artifacts['artifact_dir']}")
        print(f"mode={report['mode']} status={report['status']}")
        for item in report["checks"]:
            print(f"- {item['id']}: {item['status']}")
        for name in sorted(artifacts["sha256"]):
            print(f"{name}_sha256={artifacts['sha256'][name]}")
        return 0 if report["status"] not in {"fail", "contaminated"} else 1
    print(json.dumps({
        "mode": report["mode"],
        "status": report["status"],
        "counts": report["counts"],
        "checks": [{item["id"]: item["status"]}
                   for item in report["checks"]],
        "hidden_commitment": report.get("hidden_commitment"),
        "results": report.get("results"),
    }, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if report["status"] not in {"fail", "contaminated"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
