#!/usr/bin/env python3
"""Convert M3 v4_harness output to the product's only V4 schema.

The harness owns exploration; this adapter owns the mapping. It does not write a
second evidence shape and does not assign a gate verdict.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.domain.v4 import V4EvidenceError, from_v4_harness, write_v4_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/v4_harness_to_evidence.py")
    parser.add_argument("--input", required=True, type=Path, help="v4_harness output JSON")
    parser.add_argument("--output", required=True, type=Path, help="typed V4Evidence JSON")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        evidence = from_v4_harness(data)
        write_v4_evidence(args.output, evidence)
    except (OSError, ValueError, json.JSONDecodeError, V4EvidenceError) as exc:
        print(f"v4_harness_to_evidence: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "output": str(args.output),
                "candidate_sha256": evidence.candidate_sha256,
                "original_sha256": evidence.original_sha256,
                "claimed_scope": evidence.claimed_scope,
                "score": {
                    "known_good": evidence.calibration.known_good,
                    "known_bad": evidence.calibration.known_bad,
                    "known_bad_rejected": evidence.calibration.known_bad_rejected,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
