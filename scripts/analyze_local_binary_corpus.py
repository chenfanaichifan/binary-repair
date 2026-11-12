#!/usr/bin/env python3
"""Inventory the synthetic local binary corpus with static features."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.binary_features import extract_features  # noqa: E402


def main() -> None:
    manifest_path = ROOT / "var" / "binary-corpus" / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit("run scripts/build_local_binary_corpus.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for item in manifest.get("rows", []):
        if not item.get("binary"):
            continue
        features = extract_features(item["binary"])
        features.update({"id": item["id"], "cwe": item["cwe"], "optimization": item["optimization"]})
        rows.append(features)
    out = ROOT / "knowledge" / "local_binary_features.json"
    out.write_text(json.dumps({
        "schema": 1, "kind": "synthetic-local", "rows": rows,
        "limits": ["Not BinPool/CveBinarySheet; Mach-O arm64 only; no execution."],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
