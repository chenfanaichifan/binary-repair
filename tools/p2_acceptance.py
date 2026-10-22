#!/usr/bin/env python3
"""P2 acceptance check for a completed controller job.

This does not execute anything. It waits for a real job to reach ``finished`` and
asserts that the controller snapshot exposes two route verdicts and their
obligations. Exit 0 only when the snapshot is complete.

Usage:
  python tools/p2_acceptance.py --job-id <id> [--base-url http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base.rstrip("/") + path, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--poll", type=float, default=2.0)
    args = parser.parse_args(argv)

    deadline = time.monotonic() + args.timeout
    while True:
        snapshot = _get(args.base_url, f"/api/jobs/{args.job_id}")
        if snapshot.get("phase") == "finished":
            break
        if time.monotonic() >= deadline:
            print(f"p2_acceptance: job {args.job_id} did not finish", file=sys.stderr)
            print(json.dumps({"phase": snapshot.get("phase"), "routes": snapshot.get("routes")}, indent=2))
            return 1
        time.sleep(args.poll)

    errors: list[str] = []
    if snapshot.get("demo") is not False:
        errors.append("snapshot demo is not false")
    if not snapshot.get("verdict"):
        errors.append("snapshot verdict missing")

    for key in ("A", "B"):
        route = (snapshot.get("routes") or {}).get(key) or {}
        if route.get("outcome") is None:
            errors.append(f"route {key} has no outcome")
        if not route.get("verdict"):
            errors.append(f"route {key} verdict missing")
        obligations = route.get("obligations") or []
        kinds = {item.get("kind") for item in obligations}
        if len(obligations) != 6 or kinds != {
            "identity",
            "structure",
            "interface",
            "behaviour",
            "symbolic",
            "reproducibility",
        }:
            errors.append(f"route {key} obligations incomplete: {sorted(kinds)}")
        if {item.get("result") for item in obligations} == {"not_run"}:
            # All-not_run is a valid honest outcome, not an acceptance failure.
            pass

    summary = {
        "job_id": args.job_id,
        "phase": snapshot.get("phase"),
        "verdict": snapshot.get("verdict"),
        "routes": {
            key: {
                "outcome": (snapshot.get("routes", {}).get(key) or {}).get("outcome"),
                "obligations": len((snapshot.get("routes", {}).get(key) or {}).get("obligations") or []),
            }
            for key in ("A", "B")
        },
    }
    print(json.dumps(summary, indent=2))
    if errors:
        for error in errors:
            print(f"p2_acceptance: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
