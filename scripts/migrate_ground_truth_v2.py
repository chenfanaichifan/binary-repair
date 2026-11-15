#!/usr/bin/env python3
"""Migrate the Phase-8A benchmark v1 manifest to the Phase-8C v2 contract.

The migration is deterministic and offline: it reads the committed v1
manifest, maps every sample losslessly for the fields v1 records (id, binary
digest, split, target, oracle declaration, reference fix path, source/evidence
refs), and represents unknown v2 environment/behavior fields as explicit null
plus a limitation instead of guessing them. It emits:

* a v2 public manifest conforming to ``contracts/benchmark-manifest-v2.schema.json``
  (samples conform to ``contracts/ground-truth-sample-v2.schema.json``);
* a migration report with the field mapping, preserved/derived/unknown fields
  and the per-sample lossless matrix.

No network, no git, no wall clock: ``generated_at`` is copied from v1 (fixed
constant) and the output bytes are canonical JSON.

Usage::

    python scripts/migrate_ground_truth_v2.py --json          # summarize
    python scripts/migrate_ground_truth_v2.py --write --out DIR
    python scripts/migrate_ground_truth_v2.py --check --out DIR
    python scripts/migrate_ground_truth_v2.py --check         # determinism only

Exit codes: 0 ok, 1 migration/tamper violation, 2 unusable input/usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V1 = ROOT / "benchmark" / "phase8-v1" / "manifest.json"
FIXED_GENERATED_AT = "2026-11-16T00:00:00Z"
MIGRATION_KIND = "ground_truth_v2_migration_report"
MANIFEST_KIND = "ground_truth_benchmark_v2"
DEFAULT_BENCHMARK_ID = "phase8-v1-migrated-v2"
CWE_RE = re.compile(r"CWE-[0-9]{1,4}")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Deterministic family derivation for the known v1 samples (the v1 class text
#: is preserved verbatim in vulnerability_subtype; the family is a v2 grouping).
FAMILY_BY_SAMPLE: Mapping[str, str] = {
    "cwe121-public": "stack_buffer_overflow",
    "hard-multicall": "non_template",
    "hard-nonconst": "non_template",
    "hard-sprintf": "non_template",
    "heap-canary": "heap_buffer_overflow",
    "heap-capacity-x86_64": "heap_capacity",
    "inline-loop": "non_template",
    "negative-control": "negative_control",
    "stack-memcpy-x86": "stack_buffer_overflow",
    "stack-strcpy-x86": "stack_buffer_overflow",
    "stack-strcpy-x86_64": "stack_buffer_overflow",
    "uaf-noinput": "uaf",
}

DEFAULT_FAMILY = "non_template"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value) if value is not None else ""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return None


def _canonical(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _limitation_once(limitations: list[str], text: str) -> None:
    if text and text not in limitations:
        limitations.append(text)


def _family_for(sample: Mapping[str, Any]) -> str:
    sample_id = _text(sample.get("sample_id"))
    if sample_id in FAMILY_BY_SAMPLE:
        return FAMILY_BY_SAMPLE[sample_id]
    text = _text(sample.get("vulnerability_class")).lower()
    if "use-after-free" in text or "uaf" in text:
        return "uaf"
    if "capacity" in text:
        return "heap_capacity"
    if "negative control" in text:
        return "negative_control"
    if "heap" in text:
        return "heap_buffer_overflow"
    if "cwe-121" in text or "stack" in text:
        return "stack_buffer_overflow"
    return DEFAULT_FAMILY


def _migrate_sample(sample: Mapping[str, Any],
                    environment: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(v2_sample, per-sample migration facts)``."""
    limitations: list[str] = []
    derived: list[str] = []
    unknown: list[str] = []
    sample_id = _text(sample.get("sample_id"))
    expected_analysis = _as_dict(sample.get("expected_analysis"))
    target = _as_dict(sample.get("target"))
    oracle = _as_dict(sample.get("oracle"))
    env = _as_dict(environment)

    compiler_version = _text(env.get("compiler")) or None
    compiler = None
    optimization_level = _text(env.get("opt")) or None
    if compiler_version:
        unknown.append("compiler")
        _limitation_once(
            limitations,
            "v1 environment metadata records only a toolchain version "
            f"({compiler_version}); the compiler name is null, not guessed")
    else:
        reason = _text(env.get("compiler_unavailable_reason"))
        _limitation_once(
            limitations,
            reason or "v1 did not record a compiler; the field is null")
        unknown.append("compiler")
    if optimization_level is None:
        reason = _text(env.get("opt_unavailable_reason"))
        _limitation_once(
            limitations,
            reason or "v1 did not record an optimization level; null")
        unknown.append("optimization_level")

    for field in ("abi", "linking_mode", "stripping_status"):
        unknown.append(field)
        _limitation_once(
            limitations,
            f"v1 did not record {field}; the v2 field is null, not guessed")

    vulnerability_class = _text(sample.get("vulnerability_class"))
    cwe_match = CWE_RE.search(vulnerability_class)
    cwe = cwe_match.group(0) if cwe_match else None
    if cwe is None:
        unknown.append("cwe")
        _limitation_once(limitations,
                         "v1 did not record a CWE id; null, not guessed")
    family = _family_for(sample)
    derived.extend(["vulnerability_family"])
    _limitation_once(
        limitations,
        "vulnerability_family is a deterministic v2 grouping derived from the "
        "v1 sample/class; the original class text is preserved in "
        "vulnerability_subtype")

    target_digest = _text(sample.get("sha256"))
    reference_fix_path = sample.get("reference_fix")
    reference_fix = None
    if isinstance(reference_fix_path, str) and reference_fix_path:
        reference_sha = None
        relative = reference_fix_path
        if not relative.startswith(("/", "\\")):
            reference_sha = _sha256_file(ROOT / relative)
        if reference_sha is None:
            unknown.append("reference_fix.sha256")
            _limitation_once(
                limitations,
                "reference_fix digest is unavailable for "
                f"{reference_fix_path}; sha256 is null")
        reference_fix = {"path": reference_fix_path, "sha256": reference_sha}
    else:
        unknown.append("reference_fix")
        _limitation_once(limitations,
                         "v1 has no reference fix for this sample; null")

    root_cause_statement = _text(expected_analysis.get("root_cause"))
    if not root_cause_statement:
        root_cause_statement = vulnerability_class or (
            f"root cause not recorded for {sample_id}")
        derived.append("root_cause.statement")
    evidence_refs = [_text(item) for item in _as_list(
        sample.get("evidence_refs")) if _text(item)]
    if not evidence_refs:
        evidence_refs = [_text(item) for item in _as_list(
            sample.get("source_refs")) if _text(item)]
        derived.append("root_cause.evidence_refs")
    if not evidence_refs:
        evidence_refs = [f"benchmark/phase8-v1/manifest.json#{sample_id}"]
        derived.append("root_cause.evidence_refs")

    oracle_kinds = [_text(item) for item in _as_list(oracle.get("kinds"))]
    oracle_kinds = [item for item in oracle_kinds if item]
    oracle_kind = oracle_kinds[0] if oracle_kinds else "analysis_only"
    if not oracle_kinds:
        unknown.append("oracle.kinds")
        _limitation_once(limitations,
                         "v1 oracle has no kind; analysis_only is recorded")
    regression_case_ids = [_text(item) for item in _as_list(
        sample.get("negative_cases")) if _text(item)]
    derived.append("oracle.regression_case_ids")

    semantic_regression = {
        "required": bool(regression_case_ids),
        "case_ids": list(regression_case_ids),
    }
    derived.append("semantic_regression")

    affected_function = _text(expected_analysis.get("function")) or None
    if affected_function is None:
        affected_function = _text(target.get("function")) or _text(
            target.get("symbol")) or None
        if affected_function:
            derived.append("affected_function")

    for field in ("trigger_conditions", "affected_ranges"):
        unknown.append(field)
        _limitation_once(
            limitations,
            f"v1 did not record {field}; the v2 field is empty, not guessed")
    for field in ("expected_original_behavior", "expected_fixed_behavior",
                  "confidence"):
        unknown.append(field)
        _limitation_once(
            limitations,
            f"v1 did not record {field}; the v2 field is null, not guessed")

    v2_sample: dict[str, Any] = {
        "sample_id": sample_id,
        "sample_version": 2,
        "binary_sha256": target_digest,
        "format": _text(sample.get("format")),
        "arch": _text(sample.get("arch")),
        "bits": sample.get("bits"),
        "endian": _text(sample.get("endian")),
        "abi": None,
        "compiler": compiler,
        "compiler_version": compiler_version,
        "optimization_level": optimization_level,
        "linking_mode": None,
        "stripping_status": None,
        "vulnerability_family": family,
        "vulnerability_subtype": vulnerability_class or family,
        "cwe": cwe,
        "expected_scope": _text(sample.get("expected_scope")),
        "target": dict(target),
        "root_cause": {
            "statement": root_cause_statement,
            "evidence_refs": evidence_refs,
        },
        "trigger_conditions": [],
        "affected_function": affected_function,
        "affected_ranges": [],
        "oracle": {
            "kind": oracle_kind,
            "kinds": oracle_kinds or [oracle_kind],
            "manifest_path": oracle.get("manifest_path"),
            "expected_original": oracle.get("expected_original"),
            "expected_candidate": oracle.get("expected_candidate"),
            "regression_case_ids": regression_case_ids,
        },
        "reference_fix": reference_fix,
        "expected_original_behavior": None,
        "expected_fixed_behavior": None,
        "semantic_regression": semantic_regression,
        "expected_patch_properties": dict(_as_dict(
            sample.get("expected_patch_properties"))),
        "negative_cases": [_text(item) for item in _as_list(
            sample.get("negative_cases")) if _text(item)],
        "split": _text(sample.get("split")),
        "source_refs": [_text(item) for item in _as_list(
            sample.get("source_refs")) if _text(item)],
        "evidence_refs": [_text(item) for item in _as_list(
            sample.get("evidence_refs")) if _text(item)],
        "confidence": None,
        "limitations": limitations,
    }
    facts = {
        "sample_id": sample_id,
        "preserved": [
            "sample_id", "binary_sha256", "format", "arch", "bits", "endian",
            "split", "target", "oracle.kind", "oracle.kinds",
            "oracle.manifest_path", "oracle.expected_original",
            "oracle.expected_candidate", "reference_fix.path",
            "source_refs", "evidence_refs",
        ],
        "derived": sorted(set(derived)),
        "unknown": sorted(set(unknown)),
        "limitations": limitations,
    }
    return v2_sample, facts


def _lossless_for_sample(v1_sample: Mapping[str, Any],
                         v2_sample: Mapping[str, Any]) -> bool:
    """Whether every v1-recorded value is preserved in the v2 sample."""
    v1_oracle = _as_dict(v1_sample.get("oracle"))
    v2_oracle = _as_dict(v2_sample.get("oracle"))
    checks = [
        _text(v1_sample.get("sample_id")) == _text(v2_sample.get("sample_id")),
        _text(v1_sample.get("sha256")) == _text(v2_sample.get("binary_sha256")),
        _text(v1_sample.get("format")) == _text(v2_sample.get("format")),
        _text(v1_sample.get("arch")) == _text(v2_sample.get("arch")),
        v1_sample.get("bits") == v2_sample.get("bits"),
        _text(v1_sample.get("endian")) == _text(v2_sample.get("endian")),
        _text(v1_sample.get("split")) == _text(v2_sample.get("split")),
        dict(_as_dict(v1_sample.get("target"))) == dict(
            _as_dict(v2_sample.get("target"))),
        _as_list(v1_oracle.get("kinds")) == _as_list(v2_oracle.get("kinds")),
        v1_oracle.get("manifest_path") == v2_oracle.get("manifest_path"),
        v1_oracle.get("expected_original") == v2_oracle.get(
            "expected_original"),
        v1_oracle.get("expected_candidate") == v2_oracle.get(
            "expected_candidate"),
        _as_list(v1_sample.get("source_refs")) == _as_list(
            v2_sample.get("source_refs")),
        _as_list(v1_sample.get("evidence_refs")) == _as_list(
            v2_sample.get("evidence_refs")),
    ]
    reference = v2_sample.get("reference_fix")
    v1_reference = v1_sample.get("reference_fix")
    if v1_reference is None:
        checks.append(reference is None)
    else:
        checks.append(
            isinstance(reference, Mapping)
            and reference.get("path") == v1_reference)
    return all(checks)


def build_migration(v1_path: Path = DEFAULT_V1) -> dict[str, Any]:
    """Build the migrated manifest and report deterministically."""
    raw = Path(v1_path).read_bytes()
    v1 = json.loads(raw)
    if not isinstance(v1, Mapping):
        raise ValueError("v1 manifest is not a JSON object")
    v1_samples = [_as_dict(item) for item in _as_list(v1.get("samples"))]
    if not v1_samples:
        raise ValueError("v1 manifest has no samples")
    environment = _as_dict(v1.get("environment_metadata"))
    migrated = []
    facts = []
    for sample in v1_samples:
        v2_sample, sample_facts = _migrate_sample(
            sample, _as_dict(environment.get(_text(sample.get("sample_id")))))
        sample_facts["lossless"] = _lossless_for_sample(sample, v2_sample)
        migrated.append(v2_sample)
        facts.append(sample_facts)
    split_counts: dict[str, int] = {"dev": 0, "validation": 0}
    for sample in migrated:
        split = _text(sample.get("split"))
        split_counts[split] = split_counts.get(split, 0) + 1
    generated_at = _text(v1.get("generated_at")) or FIXED_GENERATED_AT
    v1_sha = _sha256_bytes(raw)
    manifest_limitations = [
        "hidden corpus is not provisioned in this checkout; hidden commitment "
        "counts are zero and no hidden contents are represented",
        "migrated from phase8-v1; this is a lossless contract migration, not a "
        "new benchmark claim",
    ]
    manifest = {
        "schema_version": 2,
        "kind": MANIFEST_KIND,
        "benchmark_id": DEFAULT_BENCHMARK_ID,
        "generated_at": generated_at,
        "hidden_available": False,
        "samples": migrated,
        "sample_count": len(migrated),
        "split_counts": split_counts,
        "hidden_commitment": {
            "ref": None,
            "commitment_sha256": None,
            "counts": {
                "sample_count": 0,
                "runtime_count": 0,
                "analysis_only_count": 0,
            },
        },
        "provenance": {
            "builder": "scripts/migrate_ground_truth_v2.py",
            "source_digest_sha256": v1_sha,
            "source_manifest": str(Path(v1_path).relative_to(ROOT))
            if Path(v1_path).is_absolute() and Path(v1_path).is_relative_to(ROOT)
            else str(v1_path),
            "migration_report_sha256": None,
        },
        "limitations": manifest_limitations,
    }
    manifest_text = _canonical(manifest)
    manifest_sha = _sha256_bytes(manifest_text.encode("utf-8"))
    lossless = all(item["lossless"] for item in facts)
    report = {
        "schema_version": 1,
        "kind": MIGRATION_KIND,
        "generated_by": "scripts/migrate_ground_truth_v2.py",
        "source_manifest": str(v1_path),
        "source_manifest_sha256": v1_sha,
        "source_generated_at": generated_at,
        "sample_count": len(v1_samples),
        "migrated_count": len(migrated),
        "lossless_count": sum(1 for item in facts if item["lossless"]),
        "lossless_note": (
            "lossless means every v1-recorded identity/digest/split/target/"
            "oracle/reference-path/source/evidence value is preserved; v2-only "
            "environment/behavior fields unknown to v1 are explicit null plus "
            "a limitation"),
        "preserved_fields": sorted({
            field for facts_item in facts for field in facts_item["preserved"]
        }),
        "derived_fields": sorted({
            field for facts_item in facts for field in facts_item["derived"]
        }),
        "unknown_fields": sorted({
            field for facts_item in facts for field in facts_item["unknown"]
        }),
        "samples": facts,
        "manifest_sha256": manifest_sha,
        "limitations": manifest_limitations + [
            "unknown environment/behavior fields are explicit null plus a "
            "limitation; nothing was guessed",
            "the five field list in preserved_fields is the lossless check: all "
            "v1 identities/oracles/reference/evidence values are carried over",
        ],
        "lossless": lossless,
    }
    return {"manifest": manifest, "report": report,
            "manifest_text": manifest_text,
            "manifest_sha256": manifest_sha}


def _summary(migration: Mapping[str, Any], ok: bool,
             violations: list[str]) -> dict[str, Any]:
    report = migration.get("report", {})
    return {
        "ok": ok,
        "sample_count": report.get("sample_count"),
        "migrated_count": report.get("migrated_count"),
        "lossless": report.get("lossless"),
        "manifest_sha256": migration.get("manifest_sha256"),
        "split_counts": migration.get("manifest", {}).get("split_counts"),
        "violations": violations,
    }


def _write_outputs(out_dir: Path, migration: Mapping[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    report_path = out_dir / "migration-report.json"
    manifest_path.write_text(migration["manifest_text"], encoding="utf-8")
    report_text = _canonical(migration["report"])
    report_path.write_text(report_text, encoding="utf-8")
    sums_lines = [
        f"{_sha256_bytes(manifest_path.read_bytes())}  manifest.json",
        f"{_sha256_bytes(report_path.read_bytes())}  migration-report.json",
    ]
    (out_dir / "SHA256SUMS").write_text("\n".join(sums_lines) + "\n",
                                       encoding="utf-8")
    return {
        "out_dir": str(out_dir),
        "manifest_sha256": sums_lines[0].split()[0],
        "report_sha256": sums_lines[1].split()[0],
    }


def _check_outputs(out_dir: Path, migration: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    manifest_path = out_dir / "manifest.json"
    report_path = out_dir / "migration-report.json"
    sums_path = out_dir / "SHA256SUMS"
    for path in (manifest_path, report_path, sums_path):
        if not path.is_file():
            problems.append(f"missing artifact: {path.name}")
    if problems:
        return problems
    if manifest_path.read_text(encoding="utf-8") != migration["manifest_text"]:
        problems.append("committed manifest.json differs from a fresh migration")
    if report_path.read_text(encoding="utf-8") != _canonical(
            migration["report"]):
        problems.append(
            "committed migration-report.json differs from a fresh migration")
    expected = {
        f"{_sha256_bytes(manifest_path.read_bytes())}  manifest.json",
        f"{_sha256_bytes(report_path.read_bytes())}  migration-report.json",
    }
    recorded = {line.strip() for line in sums_path.read_text(
        encoding="utf-8").splitlines() if line.strip()}
    if recorded != expected:
        problems.append("SHA256SUMS does not match manifest/report digests")
    return problems


def _default_ok(migration: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    report = migration["report"]
    if report.get("sample_count") != report.get("migrated_count"):
        problems.append("migrated count does not equal the v1 sample count")
    if report.get("sample_count") != 12:
        problems.append(
            f"expected 12 v1 samples, got {report.get('sample_count')}")
    manifest = migration["manifest"]
    if manifest.get("sample_count") != len(manifest.get("samples") or []):
        problems.append("v2 sample_count does not match the samples")
    ids = [sample.get("sample_id") for sample in manifest.get("samples") or []]
    if len(set(ids)) != len(ids):
        problems.append("duplicate sample ids in the migrated manifest")
    if manifest.get("hidden_available") is not False:
        problems.append("migrated public manifest must set hidden_available=false")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="migrate benchmark v1 manifest to the v2 contracts")
    parser.add_argument("--v1", type=Path, default=DEFAULT_V1,
                        help="v1 manifest path (default: benchmark/phase8-v1/manifest.json)")
    parser.add_argument("--out", type=Path, default=None,
                        help="output directory for --write/--check")
    parser.add_argument("--write", action="store_true",
                        help="write manifest.json/migration-report.json/SHA256SUMS")
    parser.add_argument("--check", action="store_true",
                        help="recompute and verify --out, or check determinism")
    parser.add_argument("--json", action="store_true", help="print JSON summary")
    args = parser.parse_args(argv)
    try:
        migration = build_migration(args.v1)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot build migration: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2
    violations: list[str] = []
    if args.write:
        if args.out is None:
            print("ERROR: --write requires --out", file=sys.stderr)
            return 2
        try:
            written = _write_outputs(args.out, migration)
        except OSError as exc:
            print(f"ERROR: cannot write outputs: {exc}", file=sys.stderr)
            return 2
        result = _summary(migration, True, [])
        result.update(written)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
        else:
            print("ground-truth-v2 migration: wrote {out}".format(
                out=written["out_dir"]))
            print("manifest_sha256={}".format(written["manifest_sha256"]))
            print("report_sha256={}".format(written["report_sha256"]))
        return 0
    if args.check:
        violations.extend(_default_ok(migration))
        if args.out is not None:
            violations.extend(_check_outputs(args.out, migration))
        else:
            second = build_migration(args.v1)
            if _canonical(second["manifest"]) != _canonical(migration["manifest"]):
                violations.append("migration manifest is not deterministic")
            if _canonical(second["report"]) != _canonical(migration["report"]):
                violations.append("migration report is not deterministic")
        summary = _summary(migration, not violations, violations)
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True))
        else:
            print(
                "ground-truth-v2 migration: ok={ok} samples={count} "
                "lossless={lossless} manifest_sha256={sha} violations={n}".format(
                    ok=not violations,
                    count=migration["report"].get("sample_count"),
                    lossless=migration["report"].get("lossless"),
                    sha=migration["manifest_sha256"],
                    n=len(violations),
                ))
            for problem in violations:
                print(f"MIGRATION-VIOLATION: {problem}")
        return 0 if not violations else 1
    summary = _summary(migration, True, [])
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(
            "ground-truth-v2 migration: samples={count} split_counts={splits} "
            "manifest_sha256={sha}".format(
                count=migration["report"].get("sample_count"),
                splits=json.dumps(migration["manifest"].get("split_counts"),
                                  sort_keys=True),
                sha=migration["manifest_sha256"],
            ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
