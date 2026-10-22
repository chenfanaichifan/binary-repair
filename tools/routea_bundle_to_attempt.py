"""Convert Member 3's Route A result bundle into the worker attempt bundle.

M3's `result-bundle-DRYRUN.json` is a rich host-side collector output with
`gates.V0..V5`. Member 1's worker consumes a smaller per-attempt JSON:

    {"route": "route_a", "candidate_sha256": "...",
     "results": {"V0": "passed", ...},
     "evidence": {"V0": "...", ...},
     "details": {"V0": "...", ...}}

This adapter never computes an outcome. It only maps raw gate statuses:
pass -> passed, fail -> failed, not_run -> not_run, inconclusive -> inconclusive,
unsupported -> unsupported. Missing evidence is recorded in `details`.

Usage:
    python tools/routea_bundle_to_attempt.py \
        app/interfaces/route-a/result-bundle-DRYRUN.json out.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

STATUS_MAP = {
    "pass": "passed",
    "passed": "passed",
    "fail": "failed",
    "failed": "failed",
    "not_run": "not_run",
    "inconclusive": "inconclusive",
    "unsupported": "unsupported",
}


def _evidence_paths(entries: list[dict[str, Any]]) -> list[str]:
    paths = []
    for entry in entries:
        role = entry.get("role")
        path = entry.get("relative_path")
        if path:
            paths.append(f"{role}:{path}" if role else str(path))
    return paths


def convert(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError("bundle must be an object")
    route = bundle.get("route")
    if route not in ("A", "a", "route_a"):
        raise ValueError(f"expected a Route A bundle, got route={route!r}")
    identity = bundle.get("identity") or {}
    candidate = identity.get("candidate_sha256")
    if not isinstance(candidate, str) or len(candidate) != 64:
        raise ValueError("bundle identity.candidate_sha256 must be 64 hex characters")
    int(candidate, 16)

    gates = bundle.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("bundle gates must be an object")

    results: dict[str, str] = {}
    evidence: dict[str, str] = {}
    details: dict[str, str] = {}
    for gate_id in ("V0", "V1", "V2", "V3", "V4", "V5"):
        gate = gates.get(gate_id) or {}
        raw = str(gate.get("status") or "not_run").lower()
        if raw not in STATUS_MAP:
            raise ValueError(f"unknown {gate_id} status: {raw!r}")
        results[gate_id] = STATUS_MAP[raw]
        paths = _evidence_paths(gate.get("evidence") or [])
        if paths:
            evidence[gate_id] = "; ".join(paths)
        missing = gate.get("missing") or []
        if missing:
            details[gate_id] = "; ".join(str(item) for item in missing)

    return {
        "route": "route_a",
        "candidate_sha256": candidate,
        "results": results,
        "evidence": evidence,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route A result bundle -> worker attempt bundle")
    parser.add_argument("bundle", type=pathlib.Path, help="M3 result-bundle JSON")
    parser.add_argument("out", type=pathlib.Path, help="worker per-attempt JSON to write")
    parser.add_argument("--status", type=pathlib.Path, default=None, help="optional status.json (unused for outcome)")
    args = parser.parse_args(argv)

    payload = json.loads(args.bundle.read_text(encoding="utf-8"))
    if args.status is not None:
        # Read it to make the caller's intent explicit; it intentionally has no outcome.
        json.loads(args.status.read_text(encoding="utf-8"))
    converted = convert(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(converted, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(
        "mapped host dry-run bundle -> worker attempt bundle "
        f"(candidate {converted['candidate_sha256'][:12]}..., "
        f"{sum(1 for value in converted['results'].values() if value == 'passed')} passed)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
