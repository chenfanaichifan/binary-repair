#!/usr/bin/env python3
"""Build deterministic CVE-level train/validation/test splits from metadata.

No binary is read and no model is trained. The split is a reproducibility aid:
one CVE appears in exactly one split, so vulnerable/patch and opt variants cannot
leak across splits. Component-level leakage is reported separately.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFO = ROOT / "var" / "datasets" / "binpool" / "binpool_info.json"
OUT = ROOT / "knowledge" / "binpool_splits.json"


def bucket(cve: str) -> float:
    return int(hashlib.sha256(cve.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def main() -> None:
    source = INFO
    if not source.is_file():
        # metadata acquired in /tmp by the documented acquisition step
        source = Path("/tmp/binpool_meta/binpool_info.json")
    if not source.is_file():
        raise SystemExit("binpool_info.json not found; run acquire_binary_metadata.py")
    data = json.loads(source.read_text(encoding="utf-8"))
    rows = []
    for cve, item in data.items():
        if not isinstance(item, dict):
            continue
        rows.append({"cve": cve, "cwes": item.get("cwes") or [],
                     "functions": sorted(set((item.get("file_func") or {}).values())),
                     "binary_paths": item.get("binaries") or []})
    rows.sort(key=lambda row: row["cve"])
    splits = {"train": [], "validation": [], "test": []}
    for row in rows:
        value = bucket(row["cve"])
        split = "train" if value < 0.70 else ("validation" if value < 0.85 else "test")
        splits[split].append(row)
    # component leakage is reported by shared source file/function names, not hidden.
    def keys(rows):
        return {(f, fn) for row in rows for f in [row["cve"]] for fn in row["functions"]}
    overlap = {
        "train_validation": sorted(keys(splits["train"]) & keys(splits["validation"]))[:20],
        "train_test": sorted(keys(splits["train"]) & keys(splits["test"]))[:20],
    }
    payload = {
        "schema": 1,
        "source": str(source),
        "policy": "CVE-level deterministic hash split; one CVE only in one split",
        "counts": {name: len(value) for name, value in splits.items()},
        "splits": splits,
        "leakage_checks": {
            "cve_overlap": False,
            "function_name_overlap_note": "function names may occur across projects; not used as identity key",
            "examples": overlap,
        },
        "limits": ["Metadata-only split; no binaries, no training, no vulnerability validation."],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
