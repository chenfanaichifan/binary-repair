#!/usr/bin/env python3
"""Compile the labeled C seeds into a local binary corpus for static analysis.

This is a synthetic local corpus, not BinPool/CveBinarySheet. It never executes
the binaries. Used to exercise binary parsing/feature extraction on this host.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "data" / "overflow-corpus" / "seeds"


def main() -> None:
    out = ROOT / "var" / "binary-corpus"
    out.mkdir(parents=True, exist_ok=True)
    labels = json.loads((ROOT / "data" / "overflow-corpus" / "labels.json").read_text(encoding="utf-8"))
    rows = []
    for item in labels:
        src = SEEDS / item["file"]
        for opt in ("O0", "O3"):
            target = out / f"{item['id']}_{opt}"
            proc = subprocess.run(
                ["clang", f"-{opt}", "-g", "-w", str(src), "-o", str(target)],
                text=True, capture_output=True, timeout=60,
            )
            rows.append({
                "id": item["id"], "cwe": item["cwe"], "optimization": opt,
                "source": str(src), "binary": str(target) if proc.returncode == 0 else None,
                "compile_ok": proc.returncode == 0,
                "stderr": proc.stderr.strip()[:500],
            })
            print(item["id"], opt, "OK" if proc.returncode == 0 else "FAIL")
    (out / "manifest.json").write_text(json.dumps({
        "schema": 1, "kind": "synthetic-local", "rows": rows,
        "limits": ["Not BinPool/CveBinarySheet; host Mach-O arm64; static features only."],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
