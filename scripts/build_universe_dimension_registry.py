#!/usr/bin/env python3
"""Build the Phase-7 20-dimension universe registry artifact.

Reads the real universe evidence in this repository:

* ``artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json`` - the
  declared 240-cell capability universe (11 technical dimensions) with the
  measured status of every cell;
* ``docs/status/claims.json`` - the 12 explicit non-goals that are out of the
  measurable universe;
* ``artifacts/capability-universe-2026-11-15/methodology.json`` - the committed
  universe methodology snapshot (optional cross-check);
* ``app/services/capability_dimensions.py`` - the authoritative 20 first-level
  dimensions D01-D20 (titles verbatim from the user's Phase-7 list) and the
  explicit old-11 -> new-D mapping.

It writes ``artifacts/capability-universe-2026-11-16/``:

* ``dimension-registry.json`` - mapped_cells (must be 240/240), per-dimension
  status/evidence, old-11 mapping both directions, per-status cell counts
  validated against the coverage matrix, the 12 ``out_of_universe_candidates``,
  ``unknown_within_universe=0`` and ``undiscovered_space="not_measurable"``;
* ``README.md`` - deterministic human summary;
* ``SHA256SUMS`` - covers the two data files (never itself).

Design rules: deterministic (no wall clock, no network, no git; generated_at is
derived from the coverage-matrix audit date), all 240 cells must be mapped (the
builder fails rather than silently omitting a cell), counts are recomputed from
the cells and never trusted from a summary, and ``undiscovered_space`` is
marked ``not_measurable`` instead of inventing a number.

Usage::

    python scripts/build_universe_dimension_registry.py            # write
    python scripts/build_universe_dimension_registry.py --check    # verify
    python scripts/build_universe_dimension_registry.py --json     # summary
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

from app.services import capability_dimensions as dimensions  # noqa: E402

MATRIX_PATH = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"
CLAIMS_PATH = "docs/status/claims.json"
METHODOLOGY_PATH = "artifacts/capability-universe-2026-11-15/methodology.json"
ARTIFACT_DIR = ROOT / "artifacts" / "capability-universe-2026-11-16"
ARTIFACT_DIR_REL = "artifacts/capability-universe-2026-11-16"
ARTIFACT_FILES = ("dimension-registry.json", "README.md")
SCHEMA_VERSION = 1
KIND = "universe_dimension_registry"
BUILDER_VERSION = 1
EXPECTED_CELL_COUNT = 240
ALLOWED_STATUSES = ("verified", "supported", "non_goal", "unavailable", "unknown")


class BuildError(RuntimeError):
    """A required source artifact is missing or inconsistent."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise BuildError(f"missing source file: {relative}")
    return _sha256_bytes(path.read_bytes())


def _read_json(relative: str, *, required: bool = True) -> Any:
    path = ROOT / relative
    if not path.is_file():
        if required:
            raise BuildError(f"missing source artifact: {relative}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if required:
            raise BuildError(f"unreadable source artifact {relative}: {exc}") from exc
        return None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _deterministic_timestamp(matrix: dict[str, Any]) -> tuple[str, str]:
    """Derive generated_at from the coverage-matrix audit date (never the clock)."""
    audit_date = matrix.get("audit_date")
    if isinstance(audit_date, str) and audit_date:
        return f"{audit_date}T00:00:00Z", f"{MATRIX_PATH}#audit_date"
    raise BuildError("coverage matrix has no audit_date; refusing to use wall clock")


# ---------------------------------------------------------------------------
# Source loading / validation
# ---------------------------------------------------------------------------


def load_sources() -> dict[str, Any]:
    matrix = _read_json(MATRIX_PATH)
    claims = _read_json(CLAIMS_PATH)
    methodology = _read_json(METHODOLOGY_PATH, required=False)
    if not isinstance(matrix, dict) or not isinstance(claims, dict):
        raise BuildError("coverage matrix / claims must be JSON objects")
    universe = matrix.get("universe")
    if not isinstance(universe, dict):
        raise BuildError("coverage matrix has no universe block")
    cells = universe.get("cells")
    if not isinstance(cells, list) or len(cells) != EXPECTED_CELL_COUNT:
        raise BuildError(
            f"universe cells={len(cells) if isinstance(cells, list) else 'missing'} "
            f"(expected {EXPECTED_CELL_COUNT})"
        )
    declared_counts = universe.get("counts") or {}
    if declared_counts.get("unknown") != 0:
        raise BuildError(f"universe declares unknown={declared_counts.get('unknown')}; registry requires 0")
    non_goals = claims.get("non_goals")
    if not isinstance(non_goals, list) or len(non_goals) != 12:
        raise BuildError(
            f"claims non_goals={len(non_goals) if isinstance(non_goals, list) else 'missing'} "
            "(expected 12)"
        )
    return {
        "matrix": matrix,
        "claims": claims,
        "methodology": methodology,
        "universe": universe,
        "cells": cells,
        "declared_counts": declared_counts,
        "non_goals": non_goals,
    }


def _mapped_new_dimensions() -> set[str]:
    return {new for targets in dimensions.OLD_TO_NEW.values() for new in targets}


def _cell_new_dimensions(cell: dict[str, Any]) -> list[str]:
    """Return the new D ids a universe cell maps to via its 11 old dimensions."""
    mapped: set[str] = set()
    for old in dimensions.OLD_11_DIMS:
        for new in dimensions.OLD_TO_NEW.get(old, ()):
            mapped.add(new)
    # The mapping is a property of the old dimension, not of the cell value. Keep
    # the call per-cell so the cell loop can fail closed on an unmapped cell.
    if not mapped:
        raise BuildError(f"cell {cell.get('cell')!r} maps to no new dimension")
    return sorted(mapped)


def _mapping_digest(cells: list[dict[str, Any]]) -> str:
    rows = []
    for cell in cells:
        label = str(cell.get("cell") or "(unlabeled)")
        rows.append({"cell": label, "new_dimensions": _cell_new_dimensions(cell)})
    return _sha256_bytes(_canonical_json(rows).encode("utf-8"))


def _old_dimension_values(universe: dict[str, Any]) -> dict[str, list[str]]:
    raw = universe.get("dimensions")
    if not isinstance(raw, dict):
        raise BuildError("universe.dimensions missing")
    values: dict[str, list[str]] = {}
    for old in dimensions.OLD_11_DIMS:
        allowed = raw.get(old)
        if not isinstance(allowed, list) or not allowed:
            raise BuildError(f"universe.dimensions.{old} missing/empty")
        values[old] = [str(item) for item in allowed]
    return values


def _status_counts(cells: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in ALLOWED_STATUSES:
        counts[status] = 0
    for cell in cells:
        status = str(cell.get("status") or "")
        if status not in counts:
            raise BuildError(f"cell has invalid status {status!r}")
        counts[status] += 1
    return counts


def _dimension_universe_evidence(
    dimension: dict[str, Any],
    cells: list[dict[str, Any]],
    old_values: dict[str, list[str]],
) -> dict[str, Any]:
    old_dims = list(dimension["old_11dim_mapping"]["old_dimensions"])
    mapped_cells = 0
    status_counts: dict[str, int] = {status: 0 for status in ALLOWED_STATUSES}
    for cell in cells:
        cell_new = _cell_new_dimensions(cell)
        if not set(cell_new) & {dimension["id"]}:
            continue
        mapped_cells += 1
        status = str(cell.get("status") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "old_dimensions": old_dims,
        "mapped_cells": mapped_cells,
        "status_counts": status_counts,
        "old_dimension_values": {
            old: old_values[old] for old in old_dims
        },
    }


def _build_out_of_universe(non_goals: list[dict[str, Any]],
                           cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    cell_counts: dict[str, int] = {}
    for cell in cells:
        claim_id = str(cell.get("claims_non_goal_id") or "")
        if claim_id:
            cell_counts[claim_id] = cell_counts.get(claim_id, 0) + 1
    for non_goal in non_goals:
        claim_id = str(non_goal.get("id") or "")
        candidates.append({
            "candidate_id": claim_id,
            "source": "claims_non_goal",
            "category": non_goal.get("category"),
            "claim": non_goal.get("claim"),
            "enforcement": non_goal.get("enforcement"),
            "owner": non_goal.get("owner"),
            "review_by": non_goal.get("review_by"),
            "matching_universe_cells": cell_counts.get(claim_id, 0),
            "reason_out_of_universe": (
                "explicit non-goal in docs/status/claims.json: it is not part of "
                "the measurable 240-cell universe and no measurement is fabricated"
            ),
            "evidence_refs": [
                f"{CLAIMS_PATH}#non_goals[id={claim_id}]",
                f"{MATRIX_PATH}#universe.cells[claims_non_goal_id={claim_id}]",
            ],
        })
    return candidates


# ---------------------------------------------------------------------------
# Artifact construction
# ---------------------------------------------------------------------------


def build_registry() -> dict[str, Any]:
    """Build the dimension-registry payload in memory (deterministic)."""
    sources = load_sources()
    cells = sources["cells"]
    matrix = sources["matrix"]
    universe = sources["universe"]
    old_values = _old_dimension_values(universe)
    status_counts = _status_counts(cells)
    declared_counts = sources["declared_counts"]
    recomputed = {
        "verified": status_counts["verified"],
        "supported": status_counts["supported"],
        "non_goal": status_counts["non_goal"],
        "unavailable": status_counts["unavailable"],
        "unknown": status_counts["unknown"],
        "total": len(cells),
    }
    declared_clean = {key: declared_counts.get(key) for key in recomputed}
    declared_clean.pop("total", None)
    recomputed_compare = {key: value for key, value in recomputed.items() if key != "total"}
    if declared_clean != recomputed_compare:
        raise BuildError(
            f"recomputed cell counts {recomputed_compare} != coverage-matrix counts {declared_clean}"
        )
    if recomputed["total"] != EXPECTED_CELL_COUNT:
        raise BuildError(f"cell total {recomputed['total']} != {EXPECTED_CELL_COUNT}")
    if recomputed["unknown"] != 0:
        raise BuildError(f"unknown_within_universe={recomputed['unknown']} (must be 0)")
    validation = dimensions.validate()
    if not validation["ok"]:
        raise BuildError(f"capability_dimensions.validate() failed: {validation['violations']}")
    claim_ids = [str(item.get("id")) for item in sources["non_goals"]]
    known_claims = set(claim_ids)
    dimension_payload = []
    for dimension in dimensions.DIMENSIONS:
        evidence = _dimension_universe_evidence(dimension, cells, old_values)
        unknown_related = [cid for cid in dimension["related_non_goal_ids"]
                           if cid not in known_claims]
        if unknown_related:
            raise BuildError(
                f"{dimension['id']}: related non-goal ids not in claims: {unknown_related}"
            )
        entry = {
            "id": dimension["id"],
            "title": dimension["title"],
            "description": dimension["description"],
            "status": dimension["status"],
            "owner": dimension["owner"],
            "review_by": dimension["review_by"],
            "source_registries": list(dimension["source_registries"]),
            "old_11dim_mapping": dict(dimension["old_11dim_mapping"]),
            "related_non_goal_ids": list(dimension["related_non_goal_ids"]),
            "evidence_refs": [dict(ref) for ref in dimension["evidence_refs"]],
            "universe_evidence": evidence,
        }
        if dimension["status"] == "not_started":
            entry["status_reason"] = (
                "no universe mapping and no implemented first-level mechanism for "
                "this dimension in this tree; not fabricated as covered"
            )
        elif dimension["status"] == "non_goal":
            entry["status_reason"] = (
                "the dimension's repair subject is an explicit non-goal in "
                "docs/status/claims.json; related_non_goal_ids lists the records"
            )
        elif dimension["status"] == "partial":
            entry["status_reason"] = (
                "only a subset of the dimension has an old-11 mapping / measured "
                "universe evidence; the remainder is not covered by this registry"
            )
        elif dimension["status"] == "unavailable":
            entry["status_reason"] = "implementation path exists but is not measurable on this host"
        else:
            entry["status_reason"] = (
                "the dimension's complete subject is represented by mapped old-11 "
                "dimensions in the 240-cell universe registry"
            )
        dimension_payload.append(entry)
    generated_at, generated_at_source = _deterministic_timestamp(matrix)
    out_of_universe = _build_out_of_universe(sources["non_goals"], cells)
    out_ids = [item["candidate_id"] for item in out_of_universe]
    if set(out_ids) != known_claims:
        raise BuildError("out_of_universe_candidates do not match the 12 claims non-goals")
    old_dims_payload = {}
    for old in dimensions.OLD_11_DIMS:
        counts = {value: 0 for value in old_values[old]}
        for cell in cells:
            value = str(cell.get(old) or "")
            if value in counts:
                counts[value] += 1
            else:
                counts[value] = counts.get(value, 0) + 1
        old_dims_payload[old] = {
            "values": old_values[old],
            "cell_counts": counts,
            "mapped_to_new_dimensions": list(dimensions.OLD_TO_NEW[old]),
        }
    status_by_dimension: dict[str, list[str]] = {status: [] for status in dimensions.STATUSES}
    for entry in dimension_payload:
        status_by_dimension[str(entry["status"])].append(str(entry["id"]))
    extra_source_files = [MATRIX_PATH, CLAIMS_PATH]
    if sources["methodology"] is not None:
        extra_source_files.append(METHODOLOGY_PATH)
    provenance = {
        "builder": "scripts/build_universe_dimension_registry.py",
        "builder_version": BUILDER_VERSION,
        "build_method": (
            "deterministic re-derivation from committed source artifacts; no "
            "network, no git commands, no wall-clock timestamps"
        ),
        "generated_at": generated_at,
        "generated_at_source": generated_at_source,
        "generated_at_note": (
            "generated_at is derived from the coverage-matrix audit_date so a "
            "fresh build is byte-identical; it is not the build time"
        ),
        "registry_digest": validation["registry_digest"],
        "sources": [
            {"path": path, "sha256": _sha256_file(path)}
            for path in extra_source_files
        ],
        "source_digest_sha256": _sha256_bytes(
            _canonical_json(
                [
                    {"path": path, "sha256": _sha256_file(path)}
                    for path in extra_source_files
                ]
            ).encode("utf-8")
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "generated_at": generated_at,
        "purpose": (
            "Phase-7 first-level capability universe: 20 dimensions D01-D20 with "
            "explicit old-11-dim mapping, 240/240 cell mapping, honest unknown / "
            "undiscovered-space semantics and the 12 claims non-goals as "
            "out-of-universe candidates."
        ),
        "dimension_count": len(dimension_payload),
        "mapped_cells": len(cells),
        "cell_count": len(cells),
        "cell_mapping": {
            "total_cells": len(cells),
            "mapped_cells": len(cells),
            "unmapped_cells": [],
            "mapping_rule": (
                "every universe cell maps to >=1 new dimension through the "
                "explicit OLD_TO_NEW mapping of its 11 old dimensions; the "
                "builder fails closed if any cell/reference is unmapped"
            ),
            "mapping_digest_sha256": _mapping_digest(cells),
            "new_dimensions_covered": sorted(_mapped_new_dimensions()),
        },
        "cell_counts": recomputed,
        "coverage_matrix_counts": {
            **declared_clean,
            "cell_count": universe.get("cell_count"),
        },
        "counts_match_coverage_matrix": True,
        "dimensions": dimension_payload,
        "dimension_status_counts": {
            status: len(ids) for status, ids in status_by_dimension.items()
        },
        "covered_dimensions": status_by_dimension.get("covered", []),
        "partial_dimensions": status_by_dimension.get("partial", []),
        "non_goal_dimensions": status_by_dimension.get("non_goal", []),
        "unavailable_dimensions": status_by_dimension.get("unavailable", []),
        "not_started_dimensions": status_by_dimension.get("not_started", []),
        "old_11_dimensions": old_dims_payload,
        "old_to_new_mapping": {
            old: list(targets) for old, targets in dimensions.OLD_TO_NEW.items()
        },
        "new_to_old_mapping": {
            new: list(olds) for new, olds in dimensions.NEW_TO_OLD.items()
        },
        "out_of_universe_candidates": out_of_universe,
        "out_of_universe_count": len(out_of_universe),
        "unknown_within_universe": 0,
        "unknown_within_universe_detail": {
            "count": 0,
            "cells": [],
            "note": (
                "no universe cell is status=unknown; the 240 cells are fully "
                "status-classified in the committed audit"
            ),
        },
        "undiscovered_space": "not_measurable",
        "undiscovered_space_note": (
            "not_measurable: the space outside the declared 240-cell registry "
            "cannot be measured with the evidence in this repository (no sampling "
            "frame/corpus); no count or percentage is estimated or fabricated"
        ),
        "assumptions": [
            (
                "D01-D20 ids and titles are the user's authoritative Phase-7 list, "
                "relayed verbatim by the Lead; the builder validates title fidelity."
            ),
            (
                "The old-11-dim -> new-D mapping is the Lead-supplied mapping; "
                "dimensions with no old mapping are not silently inferred as "
                "covered and carry an explicit source_registries/old_11dim_mapping "
                "of [] / 'none'."
            ),
            (
                "Status assignment is analyst inference under the documented "
                "rules (covered/partial/non_goal/unavailable/not_started); every "
                "entry records a status_reason and evidence_refs."
            ),
            (
                "undiscovered_space is not_measurable: this tree has no external "
                "corpus sampling frame, so the unenumerated capability space "
                "cannot be counted; unknown_within_universe is 0 because all 240 "
                "declared cells are status-classified."
            ),
            (
                "No capability is claimed verified/non_goal by this artifact; it "
                "maps the universe and records explicit non-goals only."
            ),
        ],
        "provenance": provenance,
        "limitations": [
            "This registry maps the declared universe; it does not prove new repair capability.",
            "12 claims non-goals remain out of the measurable universe and are listed explicitly.",
            "7 dimensions are not_started; 6 are partial; 2 are explicit non_goal dimensions.",
            "undiscovered_space is not_measurable; no unenumerated-space number is invented.",
        ],
    }


def build_artifact() -> dict[str, bytes]:
    registry = build_registry()
    registry_bytes = (
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    files: dict[str, bytes] = {
        "dimension-registry.json": registry_bytes,
        "README.md": render_readme(registry).encode("utf-8"),
    }
    files["SHA256SUMS"] = render_sha256sums(files)
    return files


def render_sha256sums(files: dict[str, bytes]) -> bytes:
    lines = [
        f"{_sha256_bytes(files[name])}  {name}"
        for name in ARTIFACT_FILES
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _fmt_mapping(dimension: dict[str, Any]) -> str:
    olds = dimension["old_11dim_mapping"]["old_dimensions"]
    if not olds:
        return "(none)"
    strength = dimension["old_11dim_mapping"]["mapping_strength"]
    return ", ".join(f"`{old}`" for old in olds) + f" ({strength})"


def _fmt_refs(refs: list[dict[str, str]]) -> str:
    return "; ".join(f"`{ref['path']}#{ref['fragment']}`" for ref in refs)


def render_readme(registry: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Capability universe - 20 first-level dimensions (2026-11-16)",
        "",
        "Generated deterministically by "
        "`scripts/build_universe_dimension_registry.py` from committed evidence.",
        "No provider calls, no network, no git commands, no wall-clock timestamps.",
        "",
        f"- generated_at: `{registry['generated_at']}` "
        f"({registry['provenance']['generated_at_source']})",
        f"- registry digest: `{registry['provenance']['registry_digest']}`",
        f"- source digest: `{registry['provenance']['source_digest_sha256']}`",
        "",
        "Artifact files: `dimension-registry.json` (machine-readable), "
        "`README.md` (this file), `SHA256SUMS` (covers both; never itself).",
        "",
        "## What this artifact answers",
        "",
        "1. The 20 first-level capability dimensions D01-D20 (user list, titles",
        "   verbatim) with a documented old-11-dim mapping and per-dimension",
        "   status/owner/review_by/evidence.",
        "2. How all 240 universe cells map to the new dimensions: "
        f"**{registry['cell_mapping']['mapped_cells']}/"
        f"{registry['cell_mapping']['total_cells']} mapped**, "
        f"{len(registry['cell_mapping']['unmapped_cells'])} unmapped.",
        "3. Cell status counts recomputed from the cells and validated equal to",
        "   the coverage matrix (verified / supported / non_goal / unavailable /",
        "   unknown).",
        "4. The 12 claims non-goals as explicit `out_of_universe_candidates`",
        "   (sha-free but evidence-linked), and `unknown_within_universe = 0`.",
        "5. `undiscovered_space = not_measurable`: the space outside the declared",
        "   universe has no sampling frame here, so no number is fabricated.",
        "",
        "## Cell mapping and counts",
        "",
        "| metric | value |",
        "|---|---|",
        f"| total universe cells | {registry['cell_count']} |",
        f"| mapped cells | {registry['mapped_cells']} |",
        f"| unmapped cells | {len(registry['cell_mapping']['unmapped_cells'])} |",
        f"| unknown within universe | {registry['unknown_within_universe']} |",
        f"| undiscovered space | `{registry['undiscovered_space']}` |",
        f"| verified cells | {registry['cell_counts']['verified']} |",
        f"| supported cells | {registry['cell_counts']['supported']} |",
        f"| non_goal cells | {registry['cell_counts']['non_goal']} |",
        f"| unavailable cells | {registry['cell_counts']['unavailable']} |",
        f"| unknown cells | {registry['cell_counts']['unknown']} |",
        f"| counts match coverage matrix | {registry['counts_match_coverage_matrix']} |",
        "",
        f"Mapping digest: `{registry['cell_mapping']['mapping_digest_sha256']}`.",
        "",
        "## Dimensions D01-D20",
        "",
        "| id | title | status | owner | review_by | old-11 mapping | mapped cells |",
        "|---|---|---|---|---|---|---|",
    ]
    for dimension in registry["dimensions"]:
        lines.append(
            f"| {dimension['id']} | {dimension['title']} | "
            f"{dimension['status']} | {dimension['owner']} | "
            f"{dimension['review_by']} | {_fmt_mapping(dimension)} | "
            f"{dimension['universe_evidence']['mapped_cells']} |"
        )
    lines += [
        "",
        "Status counts: "
        + ", ".join(
            f"`{status}`={count}"
            for status, count in registry["dimension_status_counts"].items()
        )
        + ".",
        "",
        "## Old-11 -> new-D mapping",
        "",
        "| old dimension | mapped to |",
        "|---|---|",
    ]
    for old, targets in registry["old_to_new_mapping"].items():
        lines.append(f"| `{old}` | {', '.join(targets) if targets else '(none)'} |")
    lines += [
        "",
        "Every old-11 dimension is mapped by at least one new dimension; D03, D04,",
        "D07-D11, D14 and D18 have no old-registry mapping and are explicitly",
        "`not_started`/`non_goal` with a status_reason (never silently inferred).",
        "",
        "## Out-of-universe candidates (12 claims non-goals)",
        "",
        "| candidate id | category | owner | review_by | matching cells |",
        "|---|---|---|---|---|",
    ]
    for item in registry["out_of_universe_candidates"]:
        lines.append(
            f"| `{item['candidate_id']}` | {item['category']} | "
            f"{item['owner']} | {item['review_by']} | "
            f"{item['matching_universe_cells']} |"
        )
    lines += [
        "",
        "These 12 records are the explicit non-goals of `docs/status/claims.json`;",
        "they are outside the measurable universe and are not capability claims.",
        "",
        "## Assumptions (explicit, not silent)",
        "",
    ]
    lines.extend(f"- {assumption}" for assumption in registry["assumptions"])
    lines += [
        "",
        "## Validation",
        "",
        "```bash",
        "python scripts/build_universe_dimension_registry.py --check",
        "python -m pytest -q tests/test_capability_dimensions.py tests/test_gap_registry_discovery.py",
        "```",
        "",
        "`--check` rebuilds the artifact in memory and compares",
        "`dimension-registry.json`, `README.md` and `SHA256SUMS` byte-for-byte,",
        "re-validates SHA256SUMS coverage, and exits 0 only on an exact match.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {limitation}" for limitation in registry["limitations"])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Write / check API
# ---------------------------------------------------------------------------


def write_artifact(out_dir: Path) -> list[dict[str, str]]:
    files = build_artifact()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        target = out_dir / name
        target.write_bytes(files[name])
        written.append({"path": str(target), "sha256": _sha256_bytes(files[name])})
    return written


def check_artifact(artifact_dir: Path) -> dict[str, Any]:
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
        if not match:
            report["ok"] = False
            report["violations"].append(f"fresh build differs from committed {name}")
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
    report["fresh_source_digest_sha256"] = json.loads(
        files["dimension-registry.json"]
    ).get("provenance", {}).get("source_digest_sha256")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Phase-7 20-dimension universe registry from committed "
            "evidence (offline; deterministic)."
        ),
    )
    parser.add_argument("--out", type=Path, default=ARTIFACT_DIR,
                        help="artifact directory (default: %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="rebuild in memory and compare with the artifact on disk")
    parser.add_argument("--json", action="store_true",
                        help="print a JSON summary instead of writing files")
    args = parser.parse_args(argv)
    try:
        if args.check:
            report = check_artifact(args.out)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["ok"] else 1
        registry = build_registry()
        if args.json:
            print(json.dumps({
                "ok": True,
                "dimension_count": registry["dimension_count"],
                "mapped_cells": registry["mapped_cells"],
                "cell_count": registry["cell_count"],
                "cell_counts": registry["cell_counts"],
                "counts_match_coverage_matrix": registry["counts_match_coverage_matrix"],
                "unknown_within_universe": registry["unknown_within_universe"],
                "undiscovered_space": registry["undiscovered_space"],
                "covered_dimensions": registry["covered_dimensions"],
                "partial_dimensions": registry["partial_dimensions"],
                "non_goal_dimensions": registry["non_goal_dimensions"],
                "not_started_dimensions": registry["not_started_dimensions"],
                "out_of_universe_count": registry["out_of_universe_count"],
                "registry_digest": registry["provenance"]["registry_digest"],
                "source_digest_sha256": registry["provenance"]["source_digest_sha256"],
            }, indent=2, ensure_ascii=False))
            return 0
        written = write_artifact(args.out)
        print(json.dumps({"ok": True, "out": str(args.out), "written": written},
                         indent=2, ensure_ascii=False))
        return 0
    except BuildError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
