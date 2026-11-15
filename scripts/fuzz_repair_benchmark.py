#!/usr/bin/env python3
"""Deterministic differential input harness (no network, no AFL).

This is supplemental evidence: the PoC/regression gate remains the acceptance
owner.  It mutates declared argv bytes and compares original/candidate outcome.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def mutate(base: list[str], rng: random.Random, count: int) -> list[list[str]]:
    out = []
    alphabet = b"ABC0123456789%n{}[]\x00"
    for _ in range(count):
        argv = list(base)
        if not argv:
            argv = [""]
        index = rng.randrange(len(argv))
        raw = argv[index].encode("utf-8", "replace")
        extra = bytes(rng.choice(alphabet) for _ in range(rng.randrange(1, 8)))
        argv[index] = (raw + extra).decode("utf-8", "replace")
        out.append(argv)
    return out


def build_cases(case: dict[str, Any], count: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    base = list((case.get("poc") or [{}])[0].get("argv") or [])
    rows = []
    for index, argv in enumerate(mutate(base, rng, count), 1):
        rows.append({"id": f"fuzz-{index}", "argv": argv})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    manifest = json.loads(args.cases.read_text())
    report = {"schema_version": 1, "kind": "deterministic_fuzz_plan",
              "seed": args.seed, "count": args.count, "cases": []}
    for case in manifest.get("cases") or []:
        report["cases"].append({"case_id": case["id"],
                                "inputs": build_cases(case, args.count, args.seed)})
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "fuzz.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"out": str(args.out), "cases": len(report["cases"]),
                      "inputs": len(report["cases"]) * args.count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
