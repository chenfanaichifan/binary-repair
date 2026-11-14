#!/usr/bin/env python3
"""Capability-universe methodology checker.

The capability universe in the coverage audit is only meaningful if it is
*derived from a registry* (not hand-written) and if every declared capability
appears somewhere.  This checker builds a canonical registry snapshot from the
real sources:

* ``app.services.repair_matrix``: ``REPAIR_CELLS``, ``SINK_CLASSES``,
  ``STRATEGY_PROFILES``, ``EVIDENCE_PROFILES``;
* ``app.services.coverage_audit``: the ``UNIVERSE_*`` taxonomy constants.

It then validates the live universe document (or an injected one) against that
snapshot:

1. every value of the 11 universe dimensions is a registry value or a
   documented synthetic sentinel (``(all)`` / ``(any)`` / legacy whole-image
   markers);
2. every registry entry (cell, sink class, strategy, runtime tier, evidence
   profile) appears at least once in the universe cells;
3. the ``unknown`` status is counted from the cells (and release requires 0);
4. every unexplained cell is reported explicitly, never silently accepted.

Output (deterministic, no network)::

    {"ok": bool, "dimensions": {...}, "registry_sha256": str,
     "cell_count": int, "unknown": int, "missing_registry_entries": [...],
     "unexplained_cells": [...], "unknown_rules": [...]}

Modes: ``--json`` prints the report, ``--check`` exits 0/1, and
``--write-artifact [DIR]`` writes ``methodology.json`` + ``SHA256SUMS`` to
``artifacts/capability-universe-2026-11-15``.
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

SCHEMA_VERSION = 1
ARTIFACT_DIR = ROOT / "artifacts" / "capability-universe-2026-11-15"

#: Synthetic sentinels that are structurally documented in the universe builder.
#: They are not capabilities; they mark the aggregate whole-program row and the
#: legacy whole-image marker pair.  The methodology doc lists them explicitly.
DIMENSION_SENTINELS: dict[str, tuple[str, ...]] = {
    "container": ("(all)",),
    "arch": ("(all)",),
    "bits": ("(all)",),
    "endian": ("(all)",),
    "strategy": ("(all)", "(any)", "(none)", "(legacy_whole_image)"),
    "sink_class": ("(all)", "(any)", "(none)", "(legacy_whole_image)",
                   "(whole_image_legacy)"),
    "destination_kind": ("(all)", "(any)"),
    "evidence_profile": ("(all)", "(any)"),
    "runtime_tier": ("(all)", "(any)", "unavailable"),
    "provider": ("(all)", "(any)"),
    "proof_scope": ("(all)", "(any)"),
}

DIMENSIONS = (
    "container", "arch", "bits", "endian", "strategy", "sink_class",
    "destination_kind", "evidence_profile", "runtime_tier", "provider",
    "proof_scope",
)

UNKNOWN_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "unknown.status_semantics",
        "rule": (
            "A universe cell is status=unknown only when the registry has no "
            "mapping for it; release requires unknown==0 and the gate fails "
            "otherwise.  Unexplained (unregistered) cells are reported "
            "separately and also fail the methodology check."
        ),
    },
    {
        "id": "unknown.registry_authority",
        "rule": (
            "The registry (REPAIR_CELLS/SINK_CLASSES/STRATEGY_PROFILES/"
            "EVIDENCE_PROFILES/UNIVERSE_*) is the only allowed source of "
            "dimension values; synthetic sentinels are documented structural "
            "markers, not capabilities."
        ),
    },
    {
        "id": "unknown.denominator",
        "rule": (
            "cell_count, unknown and the status counts are recomputed from the "
            "cells; the document's own summary is never trusted on its own."
        ),
    },
    {
        "id": "unknown.reverse_coverage",
        "rule": (
            "Every registry entry must appear at least once, otherwise a "
            "declared capability would be invisible to the universe "
            "(missing_registry_entries)."
        ),
    },
)


def _canonical(value: Any) -> Any:
    """Canonical JSON value (tuples -> lists, dict keys sorted as strings)."""
    if isinstance(value, dict):
        return {str(key): _canonical(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _sha256_json(value: Any) -> str:
    payload = json.dumps(_canonical(value), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_registry() -> dict[str, Any]:
    """Canonical registry snapshot derived from the real sources."""
    from app.services import coverage_audit
    from app.services.repair_matrix import (
        EVIDENCE_PROFILES,
        REPAIR_CELLS,
        SINK_CLASSES,
        STRATEGY_PROFILES,
    )

    cells = []
    for cell in REPAIR_CELLS:
        cells.append({
            "container": str(cell.container),
            "arch": str(cell.arch),
            "bits": int(cell.bits),
            "endian": str(cell.endian),
            "strategies": [str(item) for item in cell.strategies],
            "runtime_tiers": [str(item) for item in cell.runtime_tiers],
            "sink_classes": [str(item) for item in cell.sink_classes],
        })
    sink_classes = {
        str(name): _canonical(meta)
        for name, meta in sorted(SINK_CLASSES.items())
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "repair_matrix": {
            "cells": cells,
            "sink_classes": sink_classes,
            "strategy_profiles": {
                str(name): str(value)
                for name, value in sorted(STRATEGY_PROFILES.items())
            },
            "evidence_profiles": {
                str(name): _canonical(meta)
                for name, meta in sorted(EVIDENCE_PROFILES.items())
            },
        },
        "universe_taxonomy": {
            "statuses": [str(item) for item in coverage_audit.UNIVERSE_STATUSES],
            "destination_kinds": [
                str(item) for item in coverage_audit.UNIVERSE_DESTINATION_KINDS],
            "proof_scopes": [
                str(item) for item in coverage_audit.UNIVERSE_PROOF_SCOPES],
            "providers": [
                str(item) for item in coverage_audit.UNIVERSE_PROVIDERS],
            "dimensions": list(DIMENSIONS),
            "sentinels": {
                name: list(values)
                for name, values in DIMENSION_SENTINELS.items()
            },
        },
    }


def registry_allowed_values(registry: dict[str, Any]) -> dict[str, set[str]]:
    """Registry-derived allowed value set for each of the 11 dimensions."""
    repair = registry.get("repair_matrix") if isinstance(
        registry.get("repair_matrix"), dict) else {}
    taxonomy = registry.get("universe_taxonomy") if isinstance(
        registry.get("universe_taxonomy"), dict) else {}
    cells = [cell for cell in repair.get("cells", []) if isinstance(cell, dict)]
    allowed: dict[str, set[str]] = {name: set() for name in DIMENSIONS}
    for cell in cells:
        allowed["container"].add(str(cell.get("container", "")))
        allowed["arch"].add(str(cell.get("arch", "")))
        allowed["bits"].add(str(cell.get("bits", "")))
        allowed["endian"].add(str(cell.get("endian", "")))
        for strategy in cell.get("strategies", []):
            allowed["strategy"].add(str(strategy))
        for tier in cell.get("runtime_tiers", []):
            allowed["runtime_tier"].add(str(tier))
        for sink in cell.get("sink_classes", []):
            allowed["sink_class"].add(str(sink))
    for name in repair.get("sink_classes", {}):
        allowed["sink_class"].add(str(name))
    for name in repair.get("strategy_profiles", {}):
        allowed["strategy"].add(str(name))
    for profile_name in repair.get("strategy_profiles", {}).values():
        allowed["evidence_profile"].add(str(profile_name))
    for name in repair.get("evidence_profiles", {}):
        allowed["evidence_profile"].add(str(name))
    for tier in taxonomy.get("statuses", []):
        del tier  # statuses are not a dimension value
    for kind in taxonomy.get("destination_kinds", []):
        allowed["destination_kind"].add(str(kind))
    for scope in taxonomy.get("proof_scopes", []):
        allowed["proof_scope"].add(str(scope))
    for provider in taxonomy.get("providers", []):
        allowed["provider"].add(str(provider))
    sentinels = taxonomy.get("sentinels") if isinstance(
        taxonomy.get("sentinels"), dict) else DIMENSION_SENTINELS
    for dimension in DIMENSIONS:
        for sentinel in sentinels.get(dimension, []):
            allowed[dimension].add(str(sentinel))
    allowed["strategy"].add("(legacy_whole_image)")
    allowed["sink_class"].add("(legacy_whole_image)")
    return allowed


def _registry_required_entries(registry: dict[str, Any]) -> dict[str, list[str]]:
    repair = registry.get("repair_matrix") if isinstance(
        registry.get("repair_matrix"), dict) else {}
    cells = [cell for cell in repair.get("cells", []) if isinstance(cell, dict)]
    strategies: set[str] = set(repair.get("strategy_profiles", {}))
    sinks: set[str] = set(repair.get("sink_classes", {}))
    tiers: set[str] = set()
    profiles: set[str] = set(repair.get("evidence_profiles", {}))
    cell_keys: set[str] = set()
    for cell in cells:
        for strategy in cell.get("strategies", []):
            strategies.add(str(strategy))
        for sink in cell.get("sink_classes", []):
            sinks.add(str(sink))
        for tier in cell.get("runtime_tiers", []):
            tiers.add(str(tier))
        cell_keys.add("{}/{}/{}/{}".format(
            cell.get("container"), cell.get("arch"), cell.get("bits"),
            cell.get("endian")))
    return {
        "cell": sorted(cell_keys),
        "strategy": sorted(strategies),
        "sink_class": sorted(sinks),
        "runtime_tier": sorted(tiers),
        "evidence_profile": sorted(profiles),
    }


def _cell_label(index: int, cell: dict[str, Any]) -> str:
    return (
        f"cells[{index}]="
        f"{cell.get('container')}/{cell.get('arch')}/"
        f"{cell.get('bits')}/{cell.get('endian')}"
        f" strategy={cell.get('strategy')} sink={cell.get('sink_class')}"
        f" tier={cell.get('runtime_tier')} profile={cell.get('evidence_profile')}"
        f" provider={cell.get('provider')} scope={cell.get('proof_scope')}"
    )


def _default_universe() -> dict[str, Any]:
    from app.services import coverage_audit

    audit = coverage_audit.build_audit(include_probes=False)
    return audit.get("universe") if isinstance(audit.get("universe"), dict) else {}


def evaluate_methodology(universe: dict[str, Any] | None = None,
                         registry: dict[str, Any] | None = None
                         ) -> dict[str, Any]:
    """Validate one universe document against the canonical registry."""
    registry = registry or build_registry()
    registry_sha256 = _sha256_json(registry)
    if universe is None:
        universe = _default_universe()
    cells = [cell for cell in universe.get("cells", [])
             if isinstance(cell, dict)]
    allowed = registry_allowed_values(registry)
    required = _registry_required_entries(registry)
    observed: dict[str, set[str]] = {name: set() for name in DIMENSIONS}
    dimension_counts: dict[str, dict[str, int]] = {
        name: {} for name in DIMENSIONS}
    status_counts: dict[str, int] = {}
    unexplained: list[str] = []
    cell_statuses: list[str] = []
    for index, cell in enumerate(cells):
        status = str(cell.get("status", ""))
        cell_statuses.append(status)
        status_counts[status] = status_counts.get(status, 0) + 1
        cell_unexplained = False
        for dimension in DIMENSIONS:
            value = str(cell.get(dimension, ""))
            observed[dimension].add(value)
            dimension_counts[dimension][value] = (
                dimension_counts[dimension].get(value, 0) + 1)
            if value not in allowed[dimension]:
                cell_unexplained = True
                unexplained.append(
                    f"{_cell_label(index, cell)}: unregistered "
                    f"{dimension}={value!r}")
        if cell_unexplained:
            continue
    missing: list[str] = []
    for dimension in ("cell", "strategy", "sink_class", "runtime_tier",
                      "evidence_profile"):
        for value in required.get(dimension, []):
            if dimension == "cell":
                present = any(
                    "{}/{}/{}/{}".format(
                        str(cell.get("container")), str(cell.get("arch")),
                        str(cell.get("bits")), str(cell.get("endian")))
                    == value for cell in cells)
            else:
                present = value in observed[dimension]
            if not present:
                missing.append(f"{dimension}:{value}")
    unknown = sum(1 for status in cell_statuses if status == "unknown")
    summary_unknown = universe.get("unknown")
    if isinstance(summary_unknown, int) and summary_unknown != unknown:
        missing.append(
            f"summary.unknown:{summary_unknown} != computed {unknown}")
    declared_count = universe.get("cell_count")
    if isinstance(declared_count, int) and declared_count != len(cells):
        missing.append(
            f"summary.cell_count:{declared_count} != computed {len(cells)}")
    problems = bool(unexplained or missing or unknown)
    dimensions = {}
    for dimension in DIMENSIONS:
        dimensions[dimension] = {
            "values": sorted(observed[dimension]),
            "allowed": sorted(allowed[dimension]),
            "counts": dict(sorted(dimension_counts[dimension].items())),
        }
    return {
        "ok": not problems,
        "schema_version": SCHEMA_VERSION,
        "dimensions": dimensions,
        "registry_sha256": registry_sha256,
        "registry": registry,
        "cell_count": len(cells),
        "unknown": unknown,
        "status_counts": dict(sorted(status_counts.items())),
        "missing_registry_entries": missing,
        "unexplained_cells": unexplained[:100],
        "unexplained_cell_count": len(unexplained),
        "unknown_rules": [dict(rule) for rule in UNKNOWN_RULES],
        "host": "static-audit (no probes; deterministic)",
    }


def write_artifact(report: dict[str, Any],
                   artifact_dir: Path = ARTIFACT_DIR) -> dict[str, Any]:
    """Write methodology.json + SHA256SUMS deterministically."""
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/check_universe_methodology.py",
        "registry_sha256": report["registry_sha256"],
        "registry": report["registry"],
        "methodology": {
            "dimensions": report["dimensions"],
            "unknown_rules": report["unknown_rules"],
            "host": report["host"],
        },
        "check": {
            "ok": report["ok"],
            "cell_count": report["cell_count"],
            "unknown": report["unknown"],
            "status_counts": report["status_counts"],
            "missing_registry_entries": report["missing_registry_entries"],
            "unexplained_cells": report["unexplained_cells"],
            "unexplained_cell_count": report["unexplained_cell_count"],
        },
    }
    methodology_path = target / "methodology.json"
    methodology_path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    digest = hashlib.sha256(methodology_path.read_bytes()).hexdigest()
    sums_path = target / "SHA256SUMS"
    sums_path.write_text(f"{digest}  methodology.json\n", encoding="utf-8")
    return {
        "artifact_dir": str(target),
        "methodology_path": str(methodology_path),
        "methodology_sha256": digest,
        "sums_path": str(sums_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="check the capability-universe methodology/registry")
    parser.add_argument("--json", action="store_true",
                        help="print the full report")
    parser.add_argument("--check", action="store_true",
                        help="exit 0 iff the methodology check passes")
    parser.add_argument("--write-artifact", nargs="?", const=str(ARTIFACT_DIR),
                        default=None, metavar="DIR",
                        help="write methodology.json + SHA256SUMS to DIR")
    args = parser.parse_args(argv)
    report = evaluate_methodology()
    if args.write_artifact is not None:
        artifact = write_artifact(report, Path(args.write_artifact))
        report["artifact"] = artifact
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    elif args.check:
        print(
            "universe-methodology: ok={ok} registry_sha256={sha} "
            "cells={cells} unknown={unknown} missing={missing} "
            "unexplained={unexplained}".format(
                ok=report["ok"], sha=report["registry_sha256"],
                cells=report["cell_count"], unknown=report["unknown"],
                missing=len(report["missing_registry_entries"]),
                unexplained=report["unexplained_cell_count"],
            )
        )
        for item in report["unexplained_cells"][:6]:
            print(f"UNEXPLAINED: {item}")
        for item in report["missing_registry_entries"][:6]:
            print(f"UNREGISTERED: {item}")
    else:
        print(
            "universe-methodology: ok={ok} cells={cells} unknown={unknown} "
            "registry_sha256={sha}".format(
                ok=report["ok"], cells=report["cell_count"],
                unknown=report["unknown"],
                sha=report["registry_sha256"]))
    if args.check:
        return 0 if report["ok"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
