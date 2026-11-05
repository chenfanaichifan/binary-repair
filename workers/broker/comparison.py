"""Screening-test comparison across routes (T7.3, M3).

Given the raw behaviour observations of the original binary and of each route's
candidate, this module produces the side-by-side comparison the repair screen
shows: for every frozen test case, what did each binary do, and which cases
changed.

It executes nothing. Observations come from the guest
(``workers/broker/guest_behaviour.py``); this module only arranges and judges
them with the same frozen oracle Route A and Route B are judged by, so the
comparison is like-for-like (code_patterns.md: "Route cards must not imply that
a smaller patch is automatically safer" — so this module never ranks).

Fail-closed rules, inherited from the oracle and stated here because they matter
for a comparison specifically:

* a route with no observations is ``not_run``; it is never shown as equivalent
  to the original;
* "same behaviour as the original" is measured case by case, never inferred from
  a matching hash or a matching size;
* a route that leaves the invalid cases failing is reported as still vulnerable,
  even if its diff is smaller.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

# The oracle is the single judge for both routes. It lives beside this module
# rather than under fixtures/, because helpers/public/.../tests/ is a FROZEN
# fixture directory (its SHA256SUMS pins the manifests, and adding code there
# would put the freeze in question). Routing the import through the package also
# removes the sys.path surgery the first draft used.
#
# Manifests themselves still come from the frozen fixture and are passed in by
# the caller, so the comparison cannot drift from the contract.
ORACLE_MODULE = "workers.broker.v3_oracle"


class RouteCaseView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_code: int | None = None
    result: str = "not_run"          # passed / failed / not_run
    mismatches: tuple[str, ...] = ()


class CaseComparison(BaseModel):
    """One frozen case, as seen through every route."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    kind: str
    expected_return_code: int
    original: RouteCaseView
    routes: dict[str, RouteCaseView] = Field(default_factory=dict)
    # Did any route change this case relative to the original's observed result?
    changed_by: tuple[str, ...] = ()


class RouteSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: str
    candidate_sha256: str | None = None
    v3_result: str = "not_run"       # passed / failed / not_run
    passed: int = 0
    failed: int = 0
    not_run: int = 0
    # Valid cases still reproduce the original byte for byte.
    valid_behaviour_preserved: bool | None = None
    # Invalid cases the route now rejects as the contract requires.
    repaired_invalid_cases: tuple[str, ...] = ()
    # Invalid cases the route leaves failing (i.e. still vulnerable).
    still_failing_invalid_cases: tuple[str, ...] = ()


class ComparisonRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    gate: str = "V3"
    fixture: str = ""
    original_sha256: str | None = None
    cases: tuple[CaseComparison, ...] = ()
    routes: dict[str, RouteSummary] = Field(default_factory=dict)
    # Deliberately absent: any ranking. Recorded explicitly so a consumer cannot
    # mistake the absence for an oversight.
    ranking: None = None
    note: str = (
        "No ranking is produced. A smaller diff or a higher pass count does not "
        "imply a safer repair; read the per-case rows and the route summaries."
    )
    limitations: tuple[str, ...] = ()


def _observations_from(raw: Mapping[str, Any]) -> dict[str, tuple[int, bytes, bytes]]:
    """Turn a guest observation file into {case_id: (rc, stdout, stderr)}."""
    out: dict[str, tuple[int, bytes, bytes]] = {}
    for case in raw.get("cases") or ():
        if "error" in case:
            continue  # absent observation stays absent
        out[str(case["case_id"])] = (
            int(case["return_code"]),
            bytes.fromhex(case["stdout_hex"]),
            bytes.fromhex(case["stderr_hex"]),
        )
    return out


def _judge(manifests: list[str], observations: Mapping[str, tuple[int, bytes, bytes]]):
    """Run the frozen oracle, imported from this package (no sys.path surgery)."""
    try:  # normal case: imported as workers.broker.comparison
        from . import v3_oracle  # noqa: PLC0415 - deliberate lazy import
    except ImportError:  # pragma: no cover - direct script / loose-file use
        import v3_oracle  # type: ignore[no-redef]

    obs = {
        case_id: v3_oracle.Observation(return_code=rc, stdout=out, stderr=err)
        for case_id, (rc, out, err) in observations.items()
    }
    return v3_oracle.evaluate_files(manifests, obs)


def compare(
    *,
    manifests: list[str],
    original: Mapping[str, Any],
    routes: Mapping[str, Mapping[str, Any]],
    fixture: str = "",
) -> ComparisonRecord:
    """Build the comparison record.

    ``original`` and each entry of ``routes`` are guest observation payloads as
    written by ``guest_behaviour.py``. A route may be omitted entirely or carry
    no usable observations; both read as ``not_run``, never as "unchanged".
    """
    original_obs = _observations_from(original)
    original_suite = _judge(manifests, original_obs)
    original_by_case = {c.case_id: c for c in original_suite.cases}

    # Judge each route once and index the per-case results.
    route_suites: dict[str, Any] = {}
    route_obs: dict[str, dict[str, tuple[int, bytes, bytes]]] = {}
    for route, payload in routes.items():
        route_obs[route] = _observations_from(payload or {})
        route_suites[route] = _judge(manifests, route_obs[route])

    # Case ids and kinds come from the oracle's own view of the manifests, so the
    # comparison cannot drift from the contract.
    case_order = [(c.case_id, c.kind) for c in original_suite.cases]

    cases: list[CaseComparison] = []
    for case_id, kind in case_order:
        orig_case = original_by_case[case_id]
        view = {
            "return_code": original_obs.get(case_id, (None,))[0],
            "result": orig_case.result,
            "mismatches": orig_case.mismatches,
        }
        row = CaseComparison(
            case_id=case_id,
            kind=kind,
            expected_return_code=_expected_rc(manifests, case_id),
            original=RouteCaseView(**view),
        )
        changed: list[str] = []
        for route, suite in route_suites.items():
            case_result = next((c for c in suite.cases if c.case_id == case_id), None)
            if case_result is None:
                row.routes[route] = RouteCaseView(result="not_run")
                continue
            rc = route_obs[route].get(case_id, (None,))[0]
            row.routes[route] = RouteCaseView(
                return_code=rc,
                result=case_result.result,
                mismatches=case_result.mismatches,
            )
            # "Changed" means the observed exit code differs from the original's.
            # Result labels alone would call a still-vulnerable case "failed" on
            # both sides and hide that nothing moved.
            if rc is not None and view["return_code"] is not None and rc != view["return_code"]:
                changed.append(route)
        row.changed_by = tuple(changed)
        cases.append(row)

    summaries: dict[str, RouteSummary] = {}
    for route, suite in route_suites.items():
        invalid_ids = [cid for cid, kind in case_order if kind == "invalid"]
        valid_ids = [cid for cid, kind in case_order if kind == "valid"]
        case_map = {c.case_id: c for c in suite.cases}
        invalid_passed = tuple(
            cid for cid in invalid_ids if case_map.get(cid) and case_map[cid].result == "passed"
        )
        invalid_still = tuple(cid for cid in invalid_ids if cid not in invalid_passed)
        valid_all_passed = all(
            case_map.get(cid) is not None and case_map[cid].result == "passed"
            for cid in valid_ids
        ) if valid_ids else None
        summaries[route] = RouteSummary(
            route=route,
            candidate_sha256=(routes.get(route) or {}).get("binary_sha256"),
            v3_result=suite.result,
            passed=suite.passed,
            failed=suite.failed,
            not_run=suite.not_run,
            valid_behaviour_preserved=valid_all_passed,
            repaired_invalid_cases=invalid_passed,
            still_failing_invalid_cases=invalid_still,
        )

    limitations: list[str] = []
    for route, summary in summaries.items():
        if summary.candidate_sha256 is None:
            limitations.append(f"Route {route}: observation payload names no candidate hash.")
        if summary.v3_result == "not_run":
            limitations.append(f"Route {route}: no usable observations; shown as not_run.")
        if summary.still_failing_invalid_cases:
            limitations.append(
                f"Route {route}: invalid cases still failing "
                f"({', '.join(summary.still_failing_invalid_cases)}) — the defect is "
                "not repaired for those inputs."
            )
    if original_suite.result != "failed":
        limitations.append(
            "The original binary did not fail the invalid cases; the vulnerability "
            "is not demonstrated, so a 'repaired' result would be meaningless."
        )

    return ComparisonRecord(
        fixture=fixture,
        original_sha256=(original or {}).get("binary_sha256"),
        cases=tuple(cases),
        routes=summaries,
        limitations=tuple(limitations),
    )


_MANIFEST_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def _expected_rc(manifests: list[str], case_id: str) -> int:
    """Look up a case's contracted exit code in the frozen manifests."""
    for path in manifests:
        doc = _MANIFEST_CACHE.get(path)
        if doc is None:
            doc = json.loads(open(path, encoding="utf-8").read())
            doc = {str(c["id"]): c for c in doc.get("tests", [])}
            _MANIFEST_CACHE[path] = doc
        if case_id in doc:
            return int(doc[case_id]["expected"]["return_code"])
    raise KeyError(f"case {case_id!r} is not in any supplied manifest")


def load_observations(path: str) -> dict[str, Any]:
    """Read a guest observation payload from disk."""
    return json.loads(open(path, encoding="utf-8").read())


__all__ = [
    "CaseComparison",
    "ComparisonRecord",
    "RouteCaseView",
    "RouteSummary",
    "compare",
    "load_observations",
]
