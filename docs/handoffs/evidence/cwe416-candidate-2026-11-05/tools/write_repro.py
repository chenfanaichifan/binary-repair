#!/usr/bin/env python3
"""Record the two reproducibility measurements as one artifact.

1. The original fixture binary is rebuilt from source twice; both builds must
   equal each other and the shipped ``original.elf``.
2. The five-byte edit is applied twice from the same input; both candidates must
   be byte-identical.

Neither measurement executes anything. A symptom-level replay is V3, not V5.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-original", type=Path, required=True)
    ap.add_argument("--rebuild-1", type=Path, required=True)
    ap.add_argument("--rebuild-2", type=Path, required=True)
    ap.add_argument("--patch-1", type=Path, required=True)
    ap.add_argument("--patch-2", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    fixture = sha256(args.fixture_original)
    builds = [sha256(args.rebuild_1), sha256(args.rebuild_2)]
    patches = [sha256(args.patch_1), sha256(args.patch_2)]
    source_ok = builds[0] == builds[1] == fixture
    patch_ok = patches[0] == patches[1]

    payload = {
        "gate": "V5",
        "kind": "reproducibility",
        "state": "measured",
        "runs": 2,
        "source_rebuild": {
            "command": "SUPPORT=<fixture>/support sh build.sh <tmp>.elf",
            "sha256": builds,
            "fixture_original_sha256": fixture,
            "byte_identical": source_ok,
        },
        "patch_replay": {
            "command": "python3 patch_candidate.py --original original.elf --out <tmp>.elf",
            "sha256": patches,
            "byte_identical": patch_ok,
        },
        "pass": source_ok and patch_ok,
        "does_not_prove": [
            "that a rebuilt binary is bit-identical on a different toolchain or libc",
            "anything about behaviour; the replay is manifest-repaired.json",
        ],
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": payload["pass"], "source_rebuild": builds,
                      "patch_replay": patches}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
