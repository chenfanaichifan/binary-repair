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
#: list is tight). Rationale for the current entries:
#: - EG-target-scope / OG-wrong-function-candidate: target selection + gate
#:   target-identity proof (target-scope workstream); closed only by measured
#:   target-mode probe evidence.
#: - RG-external-poc::macho/x86_64: external PoC is declared unavailable on
#:   arm64 hosts (platform limitation); closed only when the capability probe
#:   and the runner agree with an explicit reason.
ALLOWED_OPEN: tuple[str, ...] = (
    "EG-target-scope",
    "OG-wrong-function-candidate",
    "RG-external-poc::macho/x86_64",
)

REQUIRED_CLAIM_NON_GOAL_KEYS = ("id", "category", "enforcement", "claim")


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
    """Validate the structured non_goals list and return its ids."""
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
        missing = [key for key in REQUIRED_CLAIM_NON_GOAL_KEYS
                   if not str(entry.get(key, "") or "").strip()]
        if missing:
            violations.append(
                f"claims.json non_goals[{index}] missing fields: {missing}"
            )
        entry_id = str(entry.get("id", "") or "")
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
            "allowlist": list(allowed_open),
        }
    gaps = audit.get("gaps")
    if not isinstance(gaps, list):
        return {
            "violations": ["audit document has no 'gaps' list"],
            "open_gap_ids": [],
            "non_goal_gap_ids": [],
            "allowlist": list(allowed_open),
        }
    rows = [gap for gap in gaps if isinstance(gap, dict)]
    gap_ids = [str(gap.get("gap_id", "")) for gap in rows]
    open_ids = sorted(str(gap.get("gap_id", "")) for gap in rows
                      if gap.get("status") == "open")
    non_goal_ids = sorted(str(gap.get("gap_id", "")) for gap in rows
                          if gap.get("status") == "non_goal")

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
        measured = set(non_goal_ids)
        stale_claims = sorted(claims_ids - measured - set(open_ids))
        if stale_claims:
            violations.append(
                "claims.json non_goals lists id(s) that are not measured as "
                f"non_goal/open audit rows: {stale_claims}"
            )
    summary = {
        "gap_count": len(rows),
        "open_gap_ids": open_ids,
        "non_goal_gap_ids": non_goal_ids,
        "allowed_open": list(allowed_open),
        "mapped_non_goal_count": len(non_goal_ids) - len(unmapped),
        "claims_non_goal_count": len(claims_ids),
        "violations": violations,
    }
    return summary


def _build_audit(local: bool) -> tuple[dict[str, Any] | None, str]:
    try:
        from app.services import coverage_audit
    except Exception as exc:  # noqa: BLE001 - reported as a gate violation
        return None, f"cannot import coverage_audit: {type(exc).__name__}: {exc}"
    try:
        return coverage_audit.build_audit(include_probes=local), ""
    except Exception as exc:  # noqa: BLE001
        return None, f"audit build failed: {type(exc).__name__}: {exc}"


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
    if local:
        violations.extend(check_acceptance(args.acceptance))
    summary["mode"] = mode
    summary["violations"] = violations
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "coverage-gate: mode={mode} gaps={gap_count} open={open} "
            "non_goals={non_goals} mapped={mapped} claims_entries={claims} "
            "allowed={allowed} violations={violations}".format(
                mode=mode,
                gap_count=summary.get("gap_count", 0),
                open=summary.get("open_gap_ids", []),
                non_goals=summary.get("non_goal_gap_ids", []),
                mapped=summary.get("mapped_non_goal_count", 0),
                claims=summary.get("claims_non_goal_count", 0),
                allowed=summary.get("allowed_open", []),
                violations=len(violations),
            )
        )
        for violation in violations:
            print(f"VIOLATION: {violation}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
