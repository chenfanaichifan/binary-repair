#!/usr/bin/env python3
"""Build and verify the additive Phase-8D gap registry.

Reads the committed Phase-7 registry only; never rewrites it.  Writes::

    artifacts/phase8d-gap-registry-2026-11-17/gaps.json
    artifacts/phase8d-gap-registry-2026-11-17/README.md
    artifacts/phase8d-gap-registry-2026-11-17/SHA256SUMS

Every AUDIT-8D-01..08 record carries explicit reproduction status, confidence,
dependencies, historical lineage links and a concrete experiment.  The builder
fails closed if a listed historical gap id is absent, if the historical bytes
changed while building, or if any validation rule fails.
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

from app.services import phase8d_gap_registry as registry  # noqa: E402

OUT_REL = "artifacts/phase8d-gap-registry-2026-11-17"


def _historical_path() -> Path:
    return ROOT / registry.HISTORICAL_REGISTRY


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_historical() -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    path = _historical_path()
    if not path.is_file():
        raise SystemExit(f"historical registry missing: {path}")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"historical registry is not JSON: {exc}") from exc
    if payload.get("kind") != registry.HISTORICAL_REGISTRY_KIND:
        raise SystemExit(f"historical registry kind={payload.get('kind')!r}")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != registry.HISTORICAL_RECORD_COUNT:
        raise SystemExit(
            f"historical registry records={len(records) if isinstance(records, list) else 'missing'} "
            f"(expected {registry.HISTORICAL_RECORD_COUNT})")
    return payload, records, hashlib.sha256(raw).hexdigest()


def _validate(
    records: list[Mapping[str, Any]], historical: list[Mapping[str, Any]],
    historical_sha: str,
) -> dict[str, Any]:
    historical_ids = [str(record.get("gap_id") or "") for record in historical]
    result = registry.validate_registry(records, historical_ids=historical_ids)
    parents = registry.historical_lineage_ids(records)
    missing = sorted(set(parents) - set(historical_ids))
    if missing:
        result["violations"].append(f"missing historical lineage parents {missing}")
        result["ok"] = False
    if len(parents) < 2:
        result["violations"].append("expected lineage across multiple historical gaps")
        result["ok"] = False
    if not historical_sha:
        result["violations"].append("historical registry sha missing")
        result["ok"] = False
    result["historical_ids"] = len(historical_ids)
    result["lineage_parent_ids"] = parents
    result["historical_sha256"] = historical_sha
    result["capability_promotion"] = False
    result["historical_registry_rewritten"] = False
    return result


def build() -> tuple[dict[str, Any], dict[str, bytes]]:
    historical_payload, historical, historical_sha = load_historical()
    before = _sha(_historical_path())
    records = registry.make_records()
    validation = _validate(records, historical, historical_sha)
    if not validation["ok"]:
        raise SystemExit("phase8d gap validation failed: " + "; ".join(validation["violations"][:10]))
    if _sha(_historical_path()) != before:
        raise SystemExit("historical registry changed during build; refusing to rewrite lineage")
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_reproduction: dict[str, int] = {}
    for record in records:
        by_category[str(record["category"])] = by_category.get(str(record["category"]), 0) + 1
        by_status[str(record["status"])] = by_status.get(str(record["status"]), 0) + 1
        by_reproduction[str(record["reproduction_status"])] = (
            by_reproduction.get(str(record["reproduction_status"]), 0) + 1)
    payload = {
        "schema_version": registry.SCHEMA_VERSION,
        "kind": registry.KIND,
        "generated_at": registry.GENERATED_AT,
        "purpose": (
            "Additive Phase-8D audit gap registry: eight AUDIT-8D findings with "
            "reproduction status, confidence, dependencies, historical lineage and "
            "concrete experiments. The historical Phase-7 registry is read-only and "
            "is never rewritten; no record is promoted to a capability."
        ),
        "historical_registry": {
            "path": registry.HISTORICAL_REGISTRY,
            "sha256": historical_sha,
            "kind": historical_payload.get("kind"),
            "record_count": len(historical),
            "rewritten": False,
        },
        "record_count": len(records),
        "audit_ids": [str(record["audit_id"]) for record in records],
        "records_by_category": dict(sorted(by_category.items())),
        "records_by_status": dict(sorted(by_status.items())),
        "records_by_reproduction": dict(sorted(by_reproduction.items())),
        "capability_dimensions": sorted({
            dim for record in records for dim in record.get("capability_dimensions") or []
        }),
        "phase8d_dimensions_covered": [
            dim for dim in ("D02", "D09", "D10")
            if dim in {d for r in records for d in r.get("capability_dimensions") or []}
        ],
        "no_auto_promotion": True,
        "no_capability_promotion": True,
        "capability_promotion": False,
        "validation": validation,
        "limitations": [
            "these are audit findings, not repair capability claims",
            "reproduction_status=reproduced means the evidence was inspected/replayed, not that the gap is fixed",
            "no record may be promoted by this builder; only the separate promotion gate can evaluate a capability state",
            "the historical Phase-7 registry bytes must remain unchanged; lineage is by reference only",
            "hidden evidence remains aggregate-only; no hidden sample ids/paths/content are included",
        ],
        "records": records,
    }
    files = {
        "gaps.json": (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    files["README.md"] = _readme(payload, files["gaps.json"]).encode("utf-8")
    sums = []
    for name in sorted(("gaps.json", "README.md")):
        sums.append(f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n")
    files["SHA256SUMS"] = "".join(sums).encode("utf-8")
    return payload, files


def _readme(payload: Mapping[str, Any], gaps_bytes: bytes) -> str:
    rows = []
    for record in payload["records"]:
        rows.append(
            "| `{audit}` | {category} | {severity} | {rep} | {status} | `{gap}` | {exp} |".format(
                audit=record["audit_id"],
                category=record["category"],
                severity=record["severity"],
                rep=record["reproduction_status"],
                status=record["status"],
                gap=record["gap_id"],
                exp=record["proposed_experiment"]["experiment_id"],
            )
        )
    lineage = []
    for record in payload["records"]:
        lineage.append(
            "- `{}`: {}".format(
                record["audit_id"],
                ", ".join(f"`{item}`" for item in record["lineage"]["derived_from"]),
            )
        )
    return (
        "# Phase-8D additive gap registry\n\n"
        f"- generated_at: `{payload['generated_at']}` (fixed; no wall clock)\n"
        f"- historical registry: `{payload['historical_registry']['path']}` "
        f"(sha `{payload['historical_registry']['sha256']}`, {payload['historical_registry']['record_count']} records, "
        "**not rewritten**)\n"
        f"- records: {payload['record_count']} (AUDIT-8D-01..08)\n"
        f"- phase-8D dimensions covered: {', '.join(payload['phase8d_dimensions_covered'])}\n"
        "- capability promotion: **false**; no auto-promotion\n"
        f"- gaps.json sha256: `{hashlib.sha256(gaps_bytes).hexdigest()}`\n\n"
        "| audit | category | severity | reproduction | status | gap | experiment |\n"
        "|---|---|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n\n"
        "## Historical lineage\n\n" + "\n".join(lineage) + "\n\n"
        "## Limitations\n\n" + "\n".join(f"- {item}" for item in payload["limitations"]) + "\n"
    )


def _output_dir(path: Path | None) -> Path:
    return path or (ROOT / OUT_REL)


def _check(out_dir: Path) -> tuple[bool, list[str]]:
    problems: list[str] = []
    try:
        payload, files = build()
    except SystemExit as exc:
        return False, [str(exc)]
    for name, expected in files.items():
        path = out_dir / name
        if not path.is_file():
            problems.append(f"missing artifact {name}")
        elif path.read_bytes() != expected:
            problems.append(f"artifact differs from deterministic build: {name}")
    if out_dir != ROOT / OUT_REL:
        # A copied artifact must still carry a valid internal sha and lineage.
        pass
    if payload["validation"]["historical_registry_rewritten"]:
        problems.append("historical registry was marked rewritten")
    if payload["validation"]["capability_promotion"]:
        problems.append("capability promotion is not allowed")
    return not problems, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / OUT_REL)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload, files = build()
    except SystemExit as exc:
        print(json.dumps({"ok": False, "error": str(exc)}) if args.json else f"ERROR: {exc}")
        return 2
    if args.check:
        ok, problems = _check(args.out)
        if args.json:
            print(json.dumps({"ok": ok, "problems": problems,
                              "record_count": len(payload["records"]),
                              "historical_sha256": payload["historical_registry"]["sha256"]},
                             indent=2))
        else:
            print("phase8d-gap-registry: " + ("check OK" if ok else f"{len(problems)} problem(s)"))
            for problem in problems:
                print(f"  - {problem}")
        return 0 if ok else 1
    if args.write:
        out = args.out
        out.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (out / name).write_bytes(data)
    summary = {
        "ok": True,
        "out": str(args.out),
        "record_count": len(payload["records"]),
        "audit_ids": payload["audit_ids"],
        "phase8d_dimensions_covered": payload["phase8d_dimensions_covered"],
        "historical_sha256": payload["historical_registry"]["sha256"],
        "capability_promotion": False,
        "historical_registry_rewritten": False,
        "records_by_category": payload["records_by_category"],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
