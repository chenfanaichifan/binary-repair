#!/usr/bin/env python3
"""Coverage regression gate for the binary-repair product.

Deterministic, bounded, no network. Two modes:

``--static-only`` (default, used by CI)
    Builds the static capability audit (``coverage_audit.build_audit(
    include_probes=False)``) and asserts the documented invariants. Fast and
    host-portable: it does not run fixtures or the guest runtime.

``--local``
    Also runs the bounded dynamic audit probes and requires the real-guest
    acceptance capture ``artifacts/coverage-closure-2026-11-14/acceptance.json``
    to exist with ``"passed": true``.

Assertions (any violation exits non-zero and prints a summary):

1. the audit itself is healthy: no ``GM-detector-error::*`` rows;
2. no high-severity open gap;
3. open gap ids are a subset of the explicit ``ALLOWED_OPEN`` residual set
   documented below (no silent acceptance of new open gaps);
4. every measured ``non_goal`` audit gap id is mapped in
   ``docs/status/claims.json`` (``non_goals``) or in
   ``docs/acceptance/non-goals-2026-11-14.md`` (no unmapped non-goal);
5. the claims document parses and its ``non_goals`` entries have
   ``id``/``category``/``enforcement``/``claim``;
6. in ``--local`` mode the acceptance capture exists and passed. In
   ``--local`` mode the allowlist must also be tight: an allowed id that is not
   measured open is a violation (so closed gaps are removed from the allowlist).

Status is measured by the audit, never hard-coded here: this script only
decides which measured states are acceptable for a release.
"""
from __future__ import annotations

import argparse
import datetime as _datetime
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_DIR = ROOT / "artifacts" / "capability-gap-audit-2026-11-14"
ACCEPTANCE = ROOT / "artifacts" / "coverage-closure-2026-11-14" / "acceptance.json"
CLAIMS = ROOT / "docs" / "status" / "claims.json"
NON_GOALS_DOC = ROOT / "docs" / "acceptance" / "non-goals-2026-11-14.md"

#: Residual open gaps this release may ship with. Keep this explicit and tiny;
#: remove an id as soon as its detector closes it (``--local`` enforces that the
#: list is tight, so an id that is no longer measured open must be removed).
#:
#: Current residual set: EMPTY. The baseline open set
#: (EG-target-scope, OG-wrong-function-candidate, RG-external-poc::macho/x86_64)
#: closed by measurement on the integrated tree:
#: - EG-target-scope / OG-wrong-function-candidate: repair_any(target,
#:   require_target) + unified patch.target_scope are exposed AND a target-mode
#:   probe kept every patch action inside the declared function;
#: - RG-external-poc::macho/x86_64: the runtime capability probe declares
#:   external PoC unavailable on arm64 hosts with an explicit reason and the PoC
#:   runner selects no runner consistently.
#: Re-adding an id here is a release decision and must state its rationale.
ALLOWED_OPEN: tuple[str, ...] = ()

REQUIRED_CLAIM_NON_GOAL_KEYS = (
    "id", "category", "enforcement", "claim", "owner", "review_by",
    "productization_criteria", "fallback",
)
REVIEW_BY_MAX = _datetime.date(2027, 5, 14)
GAP_STATUSES = ("open", "dynamic_unverified", "mitigated", "closed", "non_goal")
UNIVERSE_STATUSES = ("verified", "supported", "non_goal", "unavailable", "unknown")


def _load_json(path: Path) -> tuple[Any | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path}: {type(exc).__name__}: {exc}"


def load_claims(path: Path = CLAIMS) -> tuple[dict[str, Any] | None, list[str]]:
    payload, error = _load_json(path)
    if error:
        return None, [f"claims.json unavailable/invalid: {error}"]
    if not isinstance(payload, dict):
        return None, [f"claims.json is not a JSON object: {path}"]
    return payload, []


def claims_non_goal_ids(claims: dict[str, Any] | None) -> tuple[set[str], list[str]]:
    """Validate the structured non_goals list (incl. productization fields)."""
    if not isinstance(claims, dict):
        return set(), ["claims.json is missing; non_goal mapping cannot be checked"]
    entries = claims.get("non_goals")
    if not isinstance(entries, list) or not entries:
        return set(), [
            "claims.json has no non-empty structured 'non_goals' list"
        ]
    ids: set[str] = set()
    violations: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            violations.append(f"claims.json non_goals[{index}] is not an object")
            continue
        entry_id = str(entry.get("id", "") or "")
        missing = [key for key in REQUIRED_CLAIM_NON_GOAL_KEYS
                   if not str(entry.get(key, "") or "").strip()]
        if missing:
            violations.append(
                f"claims.json non_goals[{index}] ({entry_id or '?'}) missing "
                f"fields: {missing}"
            )
        review_by = str(entry.get("review_by", "") or "")
        if review_by:
            try:
                review_date = _datetime.date.fromisoformat(review_by)
            except ValueError:
                violations.append(
                    f"claims.json non_goals[{index}] ({entry_id or '?'}) "
                    f"review_by is not an ISO date: {review_by!r}"
                )
            else:
                if review_date > REVIEW_BY_MAX:
                    violations.append(
                        f"claims.json non_goals[{index}] ({entry_id or '?'}) "
                        f"review_by {review_by} is after {REVIEW_BY_MAX}"
                    )
        if not entry_id:
            continue
        if entry_id in ids:
            violations.append(f"claims.json non_goals lists duplicate id {entry_id!r}")
        ids.add(entry_id)
    return ids, violations


def check_acceptance(path: Path = ACCEPTANCE) -> list[str]:
    """--local: the real-guest acceptance capture must exist and have passed."""
    payload, error = _load_json(path)
    if error:
        return [f"acceptance capture unavailable: {error}"]
    if not isinstance(payload, dict):
        return [f"acceptance capture is not a JSON object: {path}"]
    if payload.get("passed") is not True:
        return [f"acceptance capture did not pass: passed={payload.get('passed')!r}"]
    failures = payload.get("failures")
    if isinstance(failures, list) and failures:
        return [f"acceptance capture lists failures: {failures[:3]}"]
    return []


def _universe_violations(audit: dict[str, Any],
                         claims_ids: set[str],
                         local: bool) -> tuple[list[str], dict[str, Any]]:
    violations: list[str] = []
    universe = audit.get("universe")
    if not isinstance(universe, dict):
        return (["audit document has no capability 'universe' object"], {})
    cells = universe.get("cells")
    if not isinstance(cells, list) or not cells:
        violations.append("capability universe has no cells")
        cells = []
    try:
        unknown = int(universe.get("unknown", -1))
    except (TypeError, ValueError):
        unknown = -1
    if unknown != 0:
        violations.append(f"capability universe unknown count is {unknown}, not 0")
    counts = universe.get("counts") if isinstance(universe.get("counts"), dict) else {}
    recomputed = {status: 0 for status in UNIVERSE_STATUSES}
    missing_reason: list[str] = []
    unmapped: list[str] = []
    bad_status: list[str] = []
    dimensions = universe.get("dimensions") if isinstance(
        universe.get("dimensions"), dict) else {}
    for row in cells:
        if not isinstance(row, dict):
            violations.append("capability universe has a non-object cell")
            continue
        status = str(row.get("status", ""))
        if status not in UNIVERSE_STATUSES:
            bad_status.append(status or "(missing)")
        recomputed[status] = recomputed.get(status, 0) + 1
        reason = str(row.get("reason", "") or "").strip()
        if status in {"non_goal", "unavailable"} and not reason:
            missing_reason.append(str(row.get("cell", "?")))
        non_goal_id = str(row.get("claims_non_goal_id", "") or "")
        if non_goal_id and non_goal_id not in claims_ids:
            unmapped.append(non_goal_id)
    if bad_status:
        violations.append(
            f"capability universe has invalid statuses: {sorted(set(bad_status))}")
    if missing_reason:
        violations.append(
            "capability universe non_goal/unavailable cells without an explicit "
            f"reason: {sorted(set(missing_reason))[:6]}")
    if unmapped:
        violations.append(
            "capability universe non_goal cells reference ids missing from "
            f"claims.json non_goals: {sorted(set(unmapped))}")
    if int(universe.get("unmapped_non_goal_ids") and len(
            universe.get("unmapped_non_goal_ids")) or 0) > 0:
        violations.append(
            "capability universe self-reports unmapped non-goal ids: "
            f"{universe.get('unmapped_non_goal_ids')}")
    if int(universe.get("missing_reason_count", 0) or 0) > 0:
        violations.append(
            "capability universe self-reports cells without a reason: "
            f"{universe.get('missing_reason_cells')}")
    if counts and recomputed != {status: int(counts.get(status, 0) or 0)
                                 for status in UNIVERSE_STATUSES}:
        violations.append(
            "capability universe status counts disagree with the cells "
            f"(declared={counts}, recomputed={recomputed})")
    # Dimension coverage: every declared dimension value must appear in a cell.
    def _row_value(row: dict[str, Any], dimension: str) -> str:
        if dimension == "container":
            return str(row.get("container", ""))
        if dimension == "arch":
            return str(row.get("arch", ""))
        if dimension == "bits":
            return str(row.get("bits", ""))
        if dimension == "endian":
            return str(row.get("endian", ""))
        return str(row.get(dimension, ""))

    for dimension, values in dimensions.items():
        if not isinstance(values, list):
            continue
        present = {_row_value(row, dimension) for row in cells
                   if isinstance(row, dict)}
        missing_values = [value for value in values
                          if str(value) not in present]
        if missing_values:
            violations.append(
                f"capability universe dimension {dimension} has values absent "
                f"from every cell: {missing_values}")
    summary = {
        "ok": not violations,
        "unknown": unknown,
        "cell_count": len(cells),
        "counts": {status: recomputed.get(status, 0)
                   for status in UNIVERSE_STATUSES},
        "non_goal_count": recomputed.get("non_goal", 0),
        "unavailable_count": recomputed.get("unavailable", 0),
        "unmapped_non_goal_ids": sorted(set(unmapped)),
        "missing_reason_count": len(missing_reason),
        "dimension_count": len(dimensions),
    }
    return violations, summary


def evaluate(audit: dict[str, Any] | None, claims: dict[str, Any] | None,
             non_goals_doc: str, *, allowed_open: tuple[str, ...] = ALLOWED_OPEN,
             local: bool = False) -> dict[str, Any]:
    """Evaluate one audit document; return summary + violations (deterministic)."""
    violations: list[str] = []
    if not isinstance(audit, dict):
        return {
            "violations": ["audit document is not an object"],
            "open_gap_ids": [],
            "non_goal_gap_ids": [],
            "dynamic_unverified_gap_ids": [],
            "dynamic_unverified_count": 0,
            "allowlist": list(allowed_open),
        }
    gaps = audit.get("gaps")
    if not isinstance(gaps, list):
        return {
            "violations": ["audit document has no 'gaps' list"],
            "open_gap_ids": [],
            "non_goal_gap_ids": [],
            "dynamic_unverified_gap_ids": [],
            "dynamic_unverified_count": 0,
            "allowlist": list(allowed_open),
        }
    rows = [gap for gap in gaps if isinstance(gap, dict)]
    gap_ids = [str(gap.get("gap_id", "")) for gap in rows]
    invalid_status = [str(gap.get("status", "")) for gap in rows
                      if str(gap.get("status", "")) not in GAP_STATUSES]
    if invalid_status:
        violations.append(
            f"audit gaps have invalid statuses: {sorted(set(invalid_status))}")
    open_ids = sorted(str(gap.get("gap_id", "")) for gap in rows
                      if gap.get("status") == "open")
    non_goal_ids = sorted(str(gap.get("gap_id", "")) for gap in rows
                          if gap.get("status") == "non_goal")
    dynamic_ids = sorted(str(gap.get("gap_id", "")) for gap in rows
                         if gap.get("status") == "dynamic_unverified")

    detector_errors = sorted(
        gap_id for gap_id in gap_ids if gap_id.startswith("GM-detector-error::")
    )
    if detector_errors:
        violations.append(
            f"audit detector errors present: {detector_errors}"
        )
    high_open = sorted(
        str(gap.get("gap_id", "")) for gap in rows
        if gap.get("status") == "open" and gap.get("severity") == "high"
    )
    if high_open:
        violations.append(f"high-severity open gaps present: {high_open}")
    unexpected_open = [gap_id for gap_id in open_ids if gap_id not in allowed_open]
    if unexpected_open:
        violations.append(
            "open gap id(s) not in the documented ALLOWED_OPEN allowlist: "
            f"{unexpected_open} (allowed={list(allowed_open)})"
        )
    if local:
        stale_allowlist = [gap_id for gap_id in allowed_open
                           if gap_id not in open_ids]
        if stale_allowlist:
            violations.append(
                "ALLOWED_OPEN still lists id(s) that are no longer measured open: "
                f"{stale_allowlist}; tighten the allowlist"
            )
        if dynamic_ids:
            violations.append(
                "--local requires dynamic_unverified_count==0 before release "
                f"claims; still dynamic_unverified: {dynamic_ids}")

    claims_ids, claim_violations = claims_non_goal_ids(claims)
    violations.extend(claim_violations)
    doc_text = str(non_goals_doc or "")
    unmapped = [
        gap_id for gap_id in non_goal_ids
        if gap_id not in claims_ids and gap_id not in doc_text
    ]
    if unmapped:
        violations.append(
            f"non_goal audit id(s) not mapped to claims.json non_goals or the "
            f"non-goals doc: {unmapped}"
        )
    if local:
        if claims_ids != set(non_goal_ids):
            stale = sorted(claims_ids - set(non_goal_ids))
            missing = sorted(set(non_goal_ids) - claims_ids)
            violations.append(
                "--local claims/non_goal id mismatch: claims-only="
                f"{stale} audit-only={missing}")
    else:
        # Static mode has dynamic_unverified rows for probe-only non-goals: a
        # claims id that is not a static non_goal must be excused by one.
        stale_claims = sorted(
            claims_ids - set(non_goal_ids) - set(dynamic_ids))
        if stale_claims:
            violations.append(
                "claims.json non_goals lists id(s) measured neither as non_goal "
                f"nor dynamic_unverified in static mode: {stale_claims}")
    universe_violations, universe_summary = _universe_violations(
        audit, claims_ids, local)
    violations.extend(universe_violations)
    summary = {
        "gap_count": len(rows),
        "open_gap_ids": open_ids,
        "non_goal_gap_ids": non_goal_ids,
        "dynamic_unverified_gap_ids": dynamic_ids,
        "dynamic_unverified_count": len(dynamic_ids),
        "allowed_open": list(allowed_open),
        "mapped_non_goal_count": len(non_goal_ids) - len(unmapped),
        "claims_non_goal_count": len(claims_ids),
        "universe": universe_summary,
        "violations": violations,
    }
    return summary


def _as_summary_universe(summary: dict[str, Any]) -> dict[str, Any]:
    value = summary.get("universe")
    return value if isinstance(value, dict) else {}


def _build_audit(local: bool) -> tuple[dict[str, Any] | None, str]:
    try:
        from app.services import coverage_audit
    except Exception as exc:  # noqa: BLE001 - reported as a gate violation
        return None, f"cannot import coverage_audit: {type(exc).__name__}: {exc}"
    try:
        return coverage_audit.build_audit(include_probes=local), ""
    except Exception as exc:  # noqa: BLE001
        return None, f"audit build failed: {type(exc).__name__}: {exc}"


def run_meta_audit_check() -> dict[str, Any]:
    """Run scripts/meta_audit.py in-process (deterministic, no network)."""
    try:
        scripts_dir = str(Path(__file__).resolve().parent)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import meta_audit
    except Exception as exc:  # noqa: BLE001 - surfaced as an honest failure
        return {
            "ok": False, "passed": False, "violations": [
                f"meta_audit unavailable: {type(exc).__name__}: {exc}"],
            "recall": 0.0, "precision": 0.0, "scenario_count": 0,
        }
    try:
        report = meta_audit.run_meta_audit(include_probes=False)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False, "passed": False, "violations": [
                f"meta_audit failed: {type(exc).__name__}: {exc}"],
            "recall": 0.0, "precision": 0.0, "scenario_count": 0,
        }
    return {
        "ok": bool(report.get("ok")),
        "passed": bool(report.get("ok")),
        "recall": report.get("recall", 0.0),
        "precision": report.get("precision", 0.0),
        "scenario_count": report.get("scenario_count", 0),
        "violations": list(report.get("violations", [])),
    }


def run_invariant_check(path: Path = ACCEPTANCE) -> dict[str, Any]:
    """Validate the committed acceptance evidence with the invariant engine."""
    document, error = _load_json(path)
    if error:
        return {"ok": False, "violations": [f"acceptance unavailable: {error}"],
                "packets_checked": 0, "limitations": []}
    try:
        from app.services import acceptance_invariants
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "violations": [
            f"acceptance_invariants unavailable: {type(exc).__name__}: {exc}"],
            "packets_checked": 0, "limitations": []}
    try:
        result = acceptance_invariants.check_acceptance(document)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "violations": [
            f"acceptance invariant check failed: {type(exc).__name__}: {exc}"],
            "packets_checked": 0, "limitations": []}
    return {
        "ok": bool(result.get("ok")),
        "violations": list(result.get("violations", [])),
        "packets_checked": int(result.get("packets_checked", 0) or 0),
        "limitations": list(result.get("limitations", [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="coverage regression gate (static by default, no network)"
    )
    parser.add_argument("--static-only", action="store_true",
                        help="static audit only (default; used by CI)")
    parser.add_argument("--local", action="store_true",
                        help="also run bounded probes and require the real-guest "
                             "acceptance capture to have passed")
    parser.add_argument("--audit-json", type=Path, default=None,
                        help="evaluate a saved audit JSON instead of building one")
    parser.add_argument("--claims", type=Path, default=CLAIMS)
    parser.add_argument("--non-goals", type=Path, default=NON_GOALS_DOC)
    parser.add_argument("--acceptance", type=Path, default=ACCEPTANCE)
    parser.add_argument("--json", action="store_true",
                        help="print the evaluation summary as JSON")
    args = parser.parse_args(argv)
    local = bool(args.local)

    if args.audit_json is not None:
        audit, error = _load_json(args.audit_json)
        if error:
            print(f"VIOLATION: audit snapshot unavailable: {error}")
            return 1
        mode = "snapshot"
    else:
        audit, error = _build_audit(local)
        mode = "local" if local else "static"
        if error:
            print(f"VIOLATION: {error}")
            return 1
    claims, claim_errors = load_claims(args.claims)
    try:
        doc_text = args.non_goals.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        doc_text = ""
        claim_errors.append(f"non-goals doc unavailable: {type(exc).__name__}: {exc}")
    summary = evaluate(audit, claims, doc_text, local=local)
    violations = list(claim_errors) + list(summary["violations"])
    acceptance_violations = check_acceptance(args.acceptance)
    summary["acceptance"] = {
        "ok": not acceptance_violations,
        "violations": list(acceptance_violations),
    }
    if local:
        violations.extend(acceptance_violations)
    meta_audit_report = run_meta_audit_check()
    summary["meta_audit"] = meta_audit_report
    if local and not meta_audit_report["ok"]:
        violations.append(
            "--local requires meta_audit.ok; violations="
            f"{meta_audit_report['violations']}")
    invariants_report = run_invariant_check(args.acceptance)
    summary["invariants"] = invariants_report
    if local and not invariants_report["ok"]:
        violations.append(
            "--local requires invariants.ok; violations="
            f"{invariants_report['violations']}")
    summary["mode"] = mode
    summary["ok"] = not violations
    summary["violations"] = violations
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "coverage-gate: mode={mode} gaps={gap_count} open={open} "
            "dynamic_unverified={dynamic} non_goals={non_goals} mapped={mapped} "
            "claims_entries={claims} allowed={allowed} "
            "universe_cells={cells} universe_unknown={unknown} "
            "universe_unmapped={unmapped} meta_ok={meta_ok} "
            "recall={recall} precision={precision} invariants_ok={inv_ok} "
            "invariant_packets={inv_packets} acceptance_ok={accept_ok} "
            "violations={violations}".format(
                mode=mode,
                gap_count=summary.get("gap_count", 0),
                open=summary.get("open_gap_ids", []),
                dynamic=summary.get("dynamic_unverified_count", 0),
                non_goals=summary.get("non_goal_gap_ids", []),
                mapped=summary.get("mapped_non_goal_count", 0),
                claims=summary.get("claims_non_goal_count", 0),
                allowed=summary.get("allowed_open", []),
                cells=_as_summary_universe(summary).get("cell_count", 0),
                unknown=_as_summary_universe(summary).get("unknown", 0),
                unmapped=_as_summary_universe(summary).get(
                    "unmapped_non_goal_ids", []),
                meta_ok=meta_audit_report.get("ok"),
                recall=meta_audit_report.get("recall"),
                precision=meta_audit_report.get("precision"),
                inv_ok=invariants_report.get("ok"),
                inv_packets=invariants_report.get("packets_checked"),
                accept_ok=summary.get("acceptance", {}).get("ok"),
                violations=len(violations),
            )
        )
        for violation in violations:
            print(f"VIOLATION: {violation}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
