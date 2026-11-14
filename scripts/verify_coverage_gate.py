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
   measured open is a violation (so closed gaps are removed from the allowlist);
7. stale-artifact check: committed ``artifacts/capability-gap-audit-2026-11-14``
   must match a live audit build (summary gap_count/by_status, universe
   cell_count/unknown, probe structure) and its ``SHA256SUMS`` must verify.
   Mismatch message: "committed audit artifacts are stale relative to the code;
   regenerate audit_capability_coverage.py". Exposed as ``stale_artifacts``;
   required in ``--local``/release mode.
8. claims measurement sync: ``claims.json`` ``audit_status`` must match the live
   measured summary field-for-field (gap_count, open, mitigated, non_goal,
   dynamic_unverified, universe cell_count/unknown) and claims non-goal ids must
   equal the measured non-goal ids (static mode accepts dynamic_unverified ids
   that the full audit measures). Exposed as ``claims_sync``; required in
   ``--local``/release mode.
9. provider identity: a provider matrix with ``provider_status=ok`` but
   ``model_identity_ok=false`` is recorded as a non-verified identity, never
   silently accepted as the requested model. Exposed as ``provider_identity``.
10. non-goal roadmap sync: the id set in
   ``docs/acceptance/non-goal-roadmap-2026-11-14.md`` must equal the
   claims/audit non-goal ids exactly (12/12). Exposed as ``roadmap_sync``; an
   id mismatch is always a violation, a missing roadmap document is tolerated
   explicitly in static mode and required in ``--local``/release mode.
11. evidence honesty helpers used by the meta-audit:
   ``check_release_evidence`` rejects release evidence whose
   ``frozen_sha != release_sha`` or whose recorded checks contradict its
   ``ok``/status counts, and requires audit-artifact + Lima provenance for
   release/nightly evidence; ``check_ci_evidence_claim`` rejects a local gate
   result claimed as CI evidence (a local run cannot satisfy a required hosted
   CI evidence slot).

Status is measured by the audit, never hard-coded here: this script only
decides which measured states are acceptable for a release.
"""
from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_DIR = ROOT / "artifacts" / "capability-gap-audit-2026-11-14"
AUDIT_MATRIX = AUDIT_DIR / "coverage-matrix.json"
AUDIT_SUMS = AUDIT_DIR / "SHA256SUMS"
ACCEPTANCE = ROOT / "artifacts" / "coverage-closure-2026-11-14" / "acceptance.json"
PROVIDER_MATRIX = ROOT / "artifacts" / "provider-matrix-2026-11-14" / "summary.json"
CLAIMS = ROOT / "docs" / "status" / "claims.json"
NON_GOALS_DOC = ROOT / "docs" / "acceptance" / "non-goals-2026-11-14.md"
ROADMAP_DOC = ROOT / "docs" / "acceptance" / "non-goal-roadmap-2026-11-14.md"

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

#: Claims that are measured non_goal only on some hosts (Mach-O external PoC is
#: unavailable on Linux/arm64 CI but may be native on a matching macOS host).
#: Static mode must not treat the claim as stale when the host measures it as
#: supported, while CI still maps the ID when the host measures it as non_goal.
HOST_DEPENDENT_CLAIM_IDS = frozenset({
    "RG-external-poc::<doc>::macho/x86_64",
})

REQUIRED_CLAIM_NON_GOAL_KEYS = (
    "id", "category", "enforcement", "claim", "owner", "review_by",
    "productization_criteria", "fallback",
)
REVIEW_BY_MAX = _datetime.date(2027, 5, 14)
GAP_STATUSES = ("open", "dynamic_unverified", "mitigated", "closed", "non_goal")
UNIVERSE_STATUSES = ("verified", "supported", "non_goal", "unavailable", "unknown")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


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


STALE_ARTIFACT_MESSAGE = (
    "committed audit artifacts are stale relative to the code; regenerate "
    "audit_capability_coverage.py"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact_sums(audit_dir: Path = AUDIT_DIR) -> tuple[bool, list[str]]:
    """Verify artifacts/<...>/SHA256SUMS against the committed bytes."""
    sums_path = Path(audit_dir) / "SHA256SUMS"
    if not sums_path.is_file():
        return False, [f"artifact SHA256SUMS is missing: {sums_path}"]
    mismatches: list[str] = []
    try:
        lines = sums_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return False, [f"artifact SHA256SUMS unreadable: {type(exc).__name__}: {exc}"]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 2:
            mismatches.append(f"malformed SHA256SUMS line: {line!r}")
            continue
        expected, name = parts[0].lower(), parts[1].lstrip("*")
        target = Path(audit_dir) / name
        if not target.is_file():
            mismatches.append(f"artifact listed in SHA256SUMS is missing: {name}")
            continue
        try:
            actual = _sha256_file(target)
        except OSError as exc:
            mismatches.append(f"artifact unreadable: {name}: {exc}")
            continue
        if actual != expected:
            mismatches.append(
                f"artifact sha256 mismatch for {name}: expected {expected}, "
                f"actual {actual}")
    return (not mismatches), mismatches


def live_audit_counts(audit: dict[str, Any]) -> dict[str, Any]:
    """Stable measured counts used by stale-artifact and claims sync checks."""
    gaps = [gap for gap in audit.get("gaps", []) if isinstance(gap, dict)]
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    universe = audit.get("universe") if isinstance(audit.get("universe"), dict) else {}
    probes = audit.get("probes") if isinstance(audit.get("probes"), dict) else {}
    status_counts = {status: 0 for status in GAP_STATUSES}
    for gap in gaps:
        status = str(gap.get("status", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "mode": str(audit.get("mode") or "unknown"),
        "gap_count": int(summary.get("gap_count", len(gaps)) or 0),
        "open_count": status_counts.get("open", 0),
        "mitigated_count": status_counts.get("mitigated", 0),
        "closed_count": status_counts.get("closed", 0),
        "high_severity_open": sum(
            1 for gap in gaps
            if gap.get("status") == "open" and gap.get("severity") == "high"),
        "non_goal_count": status_counts.get("non_goal", 0),
        "dynamic_unverified_count": status_counts.get("dynamic_unverified", 0),
        "universe_cell_count": int(universe.get("cell_count", 0) or 0),
        "universe_unknown": int(universe.get("unknown", -1)),
        "by_status": status_counts,
        "probe_structure": {
            str(key): (len(value) if isinstance(value, list) else value)
            for key, value in sorted(probes.items())
        },
        "non_goal_ids": sorted(str(gap.get("gap_id", "")) for gap in gaps
                               if gap.get("status") == "non_goal"),
        "dynamic_unverified_ids": sorted(
            str(gap.get("gap_id", "")) for gap in gaps
            if gap.get("status") == "dynamic_unverified"),
    }


def check_stale_artifacts(live_audit: dict[str, Any] | None,
                          audit_dir: Path = AUDIT_DIR,
                          committed_override: dict[str, Any] | None = None,
                          verify_sums: bool = True) -> dict[str, Any]:
    """Committed audit artifacts must match a live build of the same tree."""
    mismatches: list[str] = []
    sums_ok, sums_mismatches = (verify_artifact_sums(audit_dir)
                                if verify_sums else (True, []))
    mismatches.extend(sums_mismatches)
    committed_path = Path(audit_dir) / "coverage-matrix.json"
    if committed_override is not None:
        committed = committed_override
        committed_sha = str(committed.get("_sha256", ""))
    else:
        committed, error = _load_json(committed_path)
        if error:
            return {
                "ok": False,
                "mismatches": [f"committed audit document unavailable: {error}"]
                              + mismatches,
                "committed_sha": "",
                "committed_sha_ok": sums_ok,
                "mode": "unknown",
            }
        committed_sha = ""
        try:
            committed_sha = _sha256_file(committed_path)
        except OSError:
            committed_sha = ""
    if not isinstance(committed, dict):
        return {
            "ok": False,
            "mismatches": ["committed audit document is not a JSON object"]
                          + mismatches,
            "committed_sha": committed_sha,
            "committed_sha_ok": sums_ok,
            "mode": "unknown",
        }
    committed_counts = live_audit_counts(committed)
    committed_mode = committed_counts["mode"]
    if not isinstance(live_audit, dict):
        mismatches.append("live audit build unavailable")
        live_counts: dict[str, Any] = {}
        live_mode = "unknown"
    else:
        live_counts = live_audit_counts(live_audit)
        live_mode = live_counts["mode"]
    mode_note = ""
    if live_counts:
        if committed_mode == live_mode:
            for field in ("gap_count",):
                if committed_counts[field] != live_counts[field]:
                    mismatches.append(
                        f"{field}: committed={committed_counts[field]} "
                        f"live={live_counts[field]}")
            committed_status = committed_counts["by_status"]
            live_status = live_counts["by_status"]
            for status in GAP_STATUSES:
                if committed_status.get(status, 0) != live_status.get(status, 0):
                    mismatches.append(
                        f"by_status.{status}: committed="
                        f"{committed_status.get(status, 0)} "
                        f"live={live_status.get(status, 0)}")
        else:
            mode_note = (
                f"committed mode={committed_mode} live mode={live_mode}: "
                "gap/status counts are mode-specific and are not compared; "
                "universe structure and SHA256SUMS are compared")
        for field in ("universe_cell_count", "universe_unknown"):
            if committed_counts[field] != live_counts[field]:
                mismatches.append(
                    f"{field}: committed={committed_counts[field]} "
                    f"live={live_counts[field]}")
        committed_probes = committed_counts["probe_structure"]
        live_probes = live_counts["probe_structure"]
        if not isinstance(committed_probes, dict):
            mismatches.append("committed probes are not an object")
        elif committed_mode == live_mode:
            for key in sorted(set(committed_probes) | set(live_probes)):
                if committed_probes.get(key, 0) != live_probes.get(key, 0):
                    mismatches.append(
                        f"probes.{key}: committed="
                        f"{committed_probes.get(key, 0)} "
                        f"live={live_probes.get(key, 0)}")
        elif set(committed_probes) != set(live_probes):
            mismatches.append(
                "probes structure differs between committed and live modes: "
                f"committed={sorted(committed_probes)} "
                f"live={sorted(live_probes)}")
        # Different audit modes are compared only on mode-invariant structure
        # (the committed release artifact is a full-mode build; static CI cannot
        # reproduce probe counts).  --local/release compares like-for-like.
    report = {
        "ok": not mismatches,
        "mismatches": mismatches,
        "committed_sha": committed_sha,
        "committed_sha_ok": sums_ok,
        "mode": committed_mode,
        "live_mode": live_mode,
        "mode_note": mode_note,
        "committed_summary": {
            "gap_count": committed_counts.get("gap_count"),
            "universe_cell_count": committed_counts.get("universe_cell_count"),
            "universe_unknown": committed_counts.get("universe_unknown"),
        },
    }
    return report


def _claim_status_value(audit_status: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in audit_status:
            return audit_status[name]
    return None


def check_claims_sync(live_audit: dict[str, Any] | None,
                      claims: dict[str, Any] | None) -> dict[str, Any]:
    """claims.json ``audit_status`` must equal the live measured audit summary.

    The block is mode-specific: static mode compares ``audit_status.static`` and
    the full/local audit compares ``audit_status.release``.  Both must always
    match the live measured universe cell count/unknown and the measured
    non-goal ids.  A missing block/field fails closed.
    """
    if not isinstance(claims, dict):
        return {"ok": False, "mode": "unknown", "block": "",
                "mismatches": ["claims.json missing; measurement sync cannot be "
                               "checked"],
                "audit_status_present": False}
    audit_status = claims.get("audit_status")
    if not isinstance(audit_status, dict):
        return {"ok": False, "mode": "unknown", "block": "",
                "mismatches": ["claims.json has no 'audit_status' block; live "
                               "audit measurement is not synchronised"],
                "audit_status_present": False}
    if not isinstance(live_audit, dict):
        return {"ok": False, "mode": "unknown", "block": "",
                "mismatches": ["live audit build unavailable"],
                "audit_status_present": True}
    live = live_audit_counts(live_audit)
    live_mode = live["mode"]
    block_name = "release" if live_mode == "full" else (
        "static" if live_mode == "static" else "")
    if not block_name:
        return {"ok": False, "mode": live_mode, "block": "",
                "mismatches": [
                    f"cannot select claims.audit_status block for live audit "
                    f"mode {live_mode!r}"],
                "audit_status_present": True}
    block = audit_status.get(block_name)
    if not isinstance(block, dict):
        return {"ok": False, "mode": live_mode, "block": block_name,
                "mismatches": [
                    f"claims.audit_status.{block_name} block is absent; field-"
                    "for-field measurement sync cannot be checked"],
                "audit_status_present": True}
    mismatches: list[str] = []
    expected = {
        "gap_count": live["gap_count"],
        "closed": live["closed_count"],
        "open": live["open_count"],
        "mitigated": live["mitigated_count"],
        "non_goal": live["non_goal_count"],
        "dynamic_unverified": live["dynamic_unverified_count"],
        "high_severity_open": live["high_severity_open"],
        "universe_cell_count": live["universe_cell_count"],
        "universe_unknown": live["universe_unknown"],
    }
    for field, live_value in expected.items():
        if field not in block:
            mismatches.append(
                f"claims.audit_status.{block_name}.{field} is absent "
                "(fail closed)")
            continue
        claimed = block.get(field)
        try:
            claimed_int = int(claimed)
        except (TypeError, ValueError):
            mismatches.append(
                f"claims.audit_status.{block_name}.{field} is not an integer: "
                f"{claimed!r}")
            continue
        if claimed_int != int(live_value):
            mismatches.append(
                f"claims.audit_status.{block_name}.{field}: claimed="
                f"{claimed_int} live={live_value}")
    claims_ids, _claim_violations = claims_non_goal_ids(claims)
    live_non_goal = set(live["non_goal_ids"])
    if live_mode == "full":
        stale = sorted(claims_ids - live_non_goal)
        missing = sorted(live_non_goal - claims_ids)
    else:
        # Static mode cannot measure probe-dependent claims non-goals: they are
        # dynamic_unverified.  Every claims id must be measured as non_goal or
        # dynamic_unverified, and every measured non_goal must be claimed (the
        # remaining dynamic_unverified rows are probe-only engine gaps, not
        # non-goals).
        dynamic_ids = set(live["dynamic_unverified_ids"])
        stale = sorted(claims_ids - live_non_goal - dynamic_ids)
        missing = sorted(live_non_goal - claims_ids)
    if stale or missing:
        mismatches.append(
            "claims.json non_goals ids != live audit non_goal ids"
            f"{' (static mode)' if live_mode != 'full' else ''}: "
            f"claims-only={stale} audit-only={missing}")
    artifacts_block = audit_status.get("artifacts")
    artifacts_note = ""
    if isinstance(artifacts_block, dict):
        expected_matrix_sha = ""
        try:
            expected_matrix_sha = _sha256_file(AUDIT_MATRIX)
        except OSError:
            expected_matrix_sha = ""
        claimed_sha = str(artifacts_block.get("coverage_matrix_sha256", "") or "")
        if claimed_sha and expected_matrix_sha and claimed_sha != expected_matrix_sha:
            mismatches.append(
                "claims.audit_status.artifacts.coverage_matrix_sha256 does not "
                "match the committed coverage-matrix.json sha256")
        if artifacts_block.get("sha256sums_valid") is False:
            mismatches.append(
                "claims.audit_status.artifacts.sha256sums_valid is false")
        artifacts_note = "artifacts block cross-checked"
    return {
        "ok": not mismatches,
        "mode": live_mode,
        "block": block_name,
        "mismatches": mismatches,
        "audit_status_present": True,
        "artifacts_note": artifacts_note,
        "live_counts": {key: live[key] for key in (
            "mode", "gap_count", "closed_count", "open_count",
            "mitigated_count", "non_goal_count", "dynamic_unverified_count",
            "high_severity_open", "universe_cell_count", "universe_unknown")},
    }




ROADMAP_ID_PATTERN = re.compile(
    r"(?:EG|NG|RG|GM)-[A-Za-z0-9_.:<>/\-]+")


def parse_roadmap_ids(text: str) -> list[str]:
    """Extract the non-goal ids written in roadmap table rows."""
    ids: set[str] = set()
    for value in re.findall(r"`([^`\n]+)`", str(text or "")):
        stripped = value.strip()
        if ROADMAP_ID_PATTERN.fullmatch(stripped):
            ids.add(stripped)
    for line in str(text or "").splitlines():
        if "|" not in line:
            continue
        for cell in line.split("|"):
            stripped = cell.strip().strip("`*")
            if ROADMAP_ID_PATTERN.fullmatch(stripped):
                ids.add(stripped)
    return sorted(ids)


def check_roadmap_sync(live_audit: dict[str, Any] | None,
                       claims: dict[str, Any] | None,
                       path: Path = ROADMAP_DOC) -> dict[str, Any]:
    """Roadmap doc ids must equal the claims/audit non-goal ids exactly."""
    claims_ids, _claim_violations = claims_non_goal_ids(claims)
    live = live_audit_counts(live_audit) if isinstance(live_audit, dict) else {}
    live_mode = str(live.get("mode", ""))
    # The roadmap is the 12-id claims/audit non-goal set.  Static mode cannot
    # measure probe-dependent non-goals (dynamic_unverified), so the measured
    # equality is only enforced on the full/local audit; in static mode every
    # *measured* non-goal id must still be present in the roadmap.
    measured_ids = set(live.get("non_goal_ids", []))
    dynamic_not_compared = sorted(live.get("dynamic_unverified_ids", [])) \
        if live_mode != "full" else []
    expected_ids = claims_ids or measured_ids
    roadmap = Path(path)
    if not roadmap.is_file():
        return {
            "ok": False,
            "present": False,
            "ids": [],
            "expected_ids": sorted(expected_ids),
            "dynamic_not_compared": dynamic_not_compared,
            "mismatches": [
                f"non-goal roadmap document is missing: {roadmap}"],
        }
    try:
        text = roadmap.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {
            "ok": False,
            "present": True,
            "ids": [],
            "expected_ids": sorted(expected_ids),
            "dynamic_not_compared": dynamic_not_compared,
            "mismatches": [
                f"non-goal roadmap document unreadable: "
                f"{type(exc).__name__}: {exc}"],
        }
    roadmap_ids = set(parse_roadmap_ids(text))
    mismatches: list[str] = []
    if claims_ids and roadmap_ids != claims_ids:
        mismatches.append(
            "roadmap ids != claims.json non_goal ids: "
            f"roadmap-only={sorted(roadmap_ids - claims_ids)} "
            f"claims-only={sorted(claims_ids - roadmap_ids)}")
    if measured_ids:
        if live_mode == "full":
            if roadmap_ids != measured_ids:
                mismatches.append(
                    "roadmap ids != measured audit non_goal ids: "
                    f"roadmap-only={sorted(roadmap_ids - measured_ids)} "
                    f"audit-only={sorted(measured_ids - roadmap_ids)}")
        else:
            missing_measured = sorted(measured_ids - roadmap_ids)
            if missing_measured:
                mismatches.append(
                    "roadmap ids missing measured audit non_goal ids: "
                    f"{missing_measured}")
    if not roadmap_ids:
        mismatches.append(
            "non-goal roadmap document contains no non-goal ids")
    return {
        "ok": not mismatches,
        "present": True,
        "ids": sorted(roadmap_ids),
        "expected_ids": sorted(expected_ids),
        "dynamic_not_compared": dynamic_not_compared,
        "mismatches": mismatches,
    }


def check_release_evidence(evidence: Any) -> dict[str, Any]:
    """Validate a release-gate evidence payload (identity/checks/provenance)."""
    payload = _as_dict(evidence)
    mismatches: list[str] = []
    for field in ("mode", "ok", "release_sha", "frozen_sha", "checks"):
        if field not in payload:
            mismatches.append(f"release evidence missing required field {field!r}")
    release_sha = str(payload.get("release_sha") or "")
    frozen_sha = str(payload.get("frozen_sha") or "")
    if release_sha and frozen_sha and release_sha != frozen_sha:
        mismatches.append(
            "release evidence frozen_sha != release_sha: "
            f"frozen={frozen_sha} release={release_sha}")
    checks = [_as_dict(item) for item in _as_list(payload.get("checks"))]
    failed_required = [
        str(check.get("id", "?")) for check in checks
        if _as_dict(check).get("required", True)
        and str(check.get("status", "")) != "passed"
    ]
    claimed_ok = payload.get("ok") is True
    if claimed_ok and failed_required:
        mismatches.append(
            "release evidence claims ok=true with non-passed required checks: "
            f"{failed_required[:6]}")
    if claimed_ok and _as_list(payload.get("violations")):
        mismatches.append(
            "release evidence claims ok=true but lists violations: "
            f"{_as_list(payload.get('violations'))[:3]}")
    status_counts = _as_dict(payload.get("status_counts"))
    if status_counts and checks:
        recomputed: dict[str, int] = {}
        for check in checks:
            status = str(check.get("status", ""))
            recomputed[status] = recomputed.get(status, 0) + 1
        for status, count in status_counts.items():
            if int(count or 0) != recomputed.get(str(status), 0):
                mismatches.append(
                    f"release evidence status_counts.{status}={count} but "
                    f"checks contain {recomputed.get(str(status), 0)}")
    provenance = _as_dict(payload.get("provenance"))
    artifact_digest = (
        provenance.get("artifact_sha256")
        or provenance.get("artifacts")
        or payload.get("artifact_sha256")
        or payload.get("artifacts")
    )
    lima_identity = (
        provenance.get("lima_identity")
        or provenance.get("runner")
        or payload.get("lima_identity")
    )
    mode = str(payload.get("mode", ""))
    if mode in {"release", "nightly"}:
        if not artifact_digest:
            mismatches.append(
                "release evidence provenance is missing the audit artifact "
                "digest (provenance.artifact_sha256/artifacts)")
        if not lima_identity:
            mismatches.append(
                "release evidence provenance is missing the Lima/guest "
                "identity (provenance.lima_identity/runner)")
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "mode": mode,
        "release_sha": release_sha,
        "frozen_sha": frozen_sha,
        "provenance": {
            "artifact_digest_present": bool(artifact_digest),
            "lima_identity_present": bool(lima_identity),
        },
    }


def check_ci_evidence_claim(evidence: Any) -> dict[str, Any]:
    """A local gate run can never satisfy a required CI evidence slot."""
    payload = _as_dict(evidence)
    mismatches: list[str] = []
    mode = str(payload.get("mode") or payload.get("source") or "")
    ci_run_url = str(payload.get("ci_run_url") or payload.get("run_url") or "")
    local_claimed = bool(payload.get("local_gate")
                         or payload.get("claimed_as_ci")
                         or payload.get("local_gate_result"))
    check_ids = [str(_as_dict(item).get("id", ""))
                 for item in _as_list(payload.get("checks"))]
    local_only_ids = [
        check_id for check_id in check_ids
        if "local" in check_id.lower()
    ]
    if mode in {"ci", "hosted-ci", "github-actions"}:
        if not ci_run_url:
            mismatches.append(
                "CI evidence must cite the hosted CI run URL; a local gate run "
                "cannot satisfy a required CI evidence slot")
        if local_only_ids:
            mismatches.append(
                "CI evidence includes local-only gate checks "
                f"{local_only_ids}; local results cannot be claimed as CI "
                "evidence")
    elif local_claimed or local_only_ids:
        mismatches.append(
            "local gate result is claimed as CI evidence; a local run cannot "
            "satisfy a required hosted-CI evidence slot")
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "mode": mode,
        "ci_run_url": ci_run_url,
        "local_only_check_ids": local_only_ids,
    }


def check_provider_identity(path: Path = PROVIDER_MATRIX) -> dict[str, Any]:
    """Provider identity must be recorded as non-verified on a model mismatch."""
    payload, error = _load_json(path)
    if error:
        return {"ok": False,
                "reason": f"provider matrix unavailable: {error}",
                "identity_verified": False,
                "identity_recorded": False,
                "mismatches": []}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "provider matrix is not a JSON object",
                "identity_verified": False, "identity_recorded": False,
                "mismatches": []}
    provider = payload.get("provider") if isinstance(
        payload.get("provider"), dict) else {}
    provider_status = str(payload.get("provider_status")
                          or provider.get("status") or "")
    identity_ok = provider.get("model_identity_ok",
                               provider.get("identity_ok"))
    requested = str(provider.get("model_requested")
                    or provider.get("requested_model") or "")
    returned = str(provider.get("model_returned")
                   or provider.get("returned_model") or "")
    mismatches: list[str] = []
    identity_verified = identity_ok is True
    identity_mismatch = provider_status == "ok" and identity_ok is False
    identity_recorded = True
    if identity_mismatch:
        mismatches.append(
            "provider_status=ok but model identity is not verified: "
            f"requested={requested or '?'} returned={returned or '?'}; recorded "
            "as NON-VERIFIED IDENTITY (never silently accepted as the requested "
            "provider model)")
    elif identity_ok is None:
        identity_recorded = False
        mismatches.append(
            "provider identity was not measured (model_identity_ok absent); "
            "cannot record it as verified or non-verified")
    # ok means "identity state is honestly recorded": a measured mismatch is a
    # pass for this check because it is explicitly non-verified (never accepted
    # silently); only an unmeasured/absent identity fails closed.
    return {
        "ok": identity_recorded,
        "identity_mismatch": identity_mismatch,
        "reason": "; ".join(mismatches) if mismatches else (
            "provider identity verified" if identity_verified
            else "provider identity not claimed"),
        "identity_verified": identity_verified,
        "identity_recorded": identity_recorded,
        "provider_status": provider_status,
        "model_requested": requested,
        "model_returned": returned,
        "mismatches": mismatches,
    }


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
    # Contract-literal fabrication: a cell claiming verified/supported must have
    # a measured runtime tier.  A declared tier that the runtime census does not
    # measure as available (and carries no explicit reason) is a fabricated
    # capability, not a contract statement.
    availability: dict[tuple[str, str, str], bool] = {}
    runtime_sources = _as_dict(
        _as_dict(audit.get("census")).get("runtime_sources")).get("sources")
    for source in _as_list(runtime_sources):
        item = _as_dict(source)
        key = (str(item.get("format", "")), str(item.get("arch", "")),
               str(item.get("runtime_tier", "")))
        availability[key] = availability.get(key, False) or bool(
            item.get("available"))
    fabricated: list[str] = []
    if availability:
        # Only judge fabrication when the live audit actually measured runtime
        # sources (a synthetic/partial audit document without the census cannot
        # be judged and is not silently passed as consistent for this facet).
        for row in cells:
            if not isinstance(row, dict):
                continue
            if str(row.get("status", "")) not in {"verified", "supported"}:
                continue
            tier = str(row.get("runtime_tier", ""))
            container = str(row.get("container", ""))
            arch = str(row.get("arch", ""))
            if not tier or container == "(all)" or arch == "(all)":
                continue
            key = (container, arch, tier)
            measured = availability.get(key)
            if measured is None:
                fabricated.append(
                    f"{container}/{arch}:{tier} (no runtime source measured)")
            elif not measured:
                fabricated.append(
                    f"{container}/{arch}:{tier} (runtime tier not measured "
                    "available)")
    if fabricated:
        violations.append(
            "capability universe fabricates capabilities: "
            f"{sorted(set(fabricated))[:8]}")
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
            claims_ids - set(non_goal_ids) - set(dynamic_ids)
            - HOST_DEPENDENT_CLAIM_IDS)
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


def run_meta_audit_check(live_audit: dict[str, Any] | None = None) -> dict[str, Any]:
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
        report = meta_audit.run_meta_audit(include_probes=False,
                                           live_audit=live_audit)
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
    meta_audit_report = run_meta_audit_check(audit)
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
    stale_report = check_stale_artifacts(audit)
    summary["stale_artifacts"] = stale_report
    if local and not stale_report["ok"]:
        violations.append(
            f"--local requires stale_artifacts.ok: {STALE_ARTIFACT_MESSAGE}; "
            f"mismatches={stale_report['mismatches']}")
    claims_sync_report = check_claims_sync(audit, claims)
    summary["claims_sync"] = claims_sync_report
    if local and not claims_sync_report["ok"]:
        violations.append(
            "--local requires claims_sync.ok; mismatches="
            f"{claims_sync_report['mismatches']}")
    roadmap_report = check_roadmap_sync(audit, claims)
    summary["roadmap_sync"] = roadmap_report
    if not roadmap_report["present"]:
        if local:
            violations.append(
                "--local requires the non-goal roadmap document; mismatches="
                f"{roadmap_report['mismatches']}")
    elif not roadmap_report["ok"]:
        violations.append(
            "roadmap_sync violation: "
            f"{roadmap_report['mismatches']}")
    provider_report = check_provider_identity()
    summary["provider_identity"] = provider_report
    if local and not provider_report["ok"]:
        violations.append(
            "--local requires provider identity to be recorded as non-verified "
            f"on mismatch; mismatches={provider_report['mismatches']}")
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
            "stale_ok={stale_ok} claims_sync_ok={sync_ok} "
            "roadmap_ok={roadmap_ok} roadmap_ids={roadmap_ids} "
            "provider_identity_verified={provider_verified} "
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
                stale_ok=stale_report.get("ok"),
                sync_ok=claims_sync_report.get("ok"),
                roadmap_ok=roadmap_report.get("ok"),
                roadmap_ids=len(_as_list(roadmap_report.get("ids"))),
                provider_verified=provider_report.get("identity_verified"),
                violations=len(violations),
            )
        )
        for violation in violations:
            print(f"VIOLATION: {violation}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
