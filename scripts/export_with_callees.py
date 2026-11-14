#!/usr/bin/env python3
"""Export a Ghidra function plus its direct callee context (Route B/P2).

The default single-function `routeb/ghidra/export.sh` remains unchanged.  This
wrapper reuses it for the target and each named direct callee, then writes a
JSON context that a repair prompt can include without inventing symbols.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "routeb" / "ghidra" / "export.sh"


def _run(binary: Path, function: str, outdir: Path) -> tuple[Path | None, Path | None]:
    proc = subprocess.run(
        ["bash", str(EXPORT), str(binary), function, str(outdir)],
        cwd=ROOT.parent, capture_output=True, text=True, timeout=300,
        env=os.environ,
    )
    c = outdir / f"{function}.c"
    meta = outdir / f"{function}.c.meta.txt"
    if proc.returncode != 0 or not c.is_file() or not meta.is_file():
        print(f"skip {function}: rc={proc.returncode} {proc.stderr[-200:]}", file=sys.stderr)
        return None, None
    return c, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--function", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.binary = args.binary.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    c, meta = _run(args.binary, args.function, args.out)
    if c is None or meta is None:
        return 2
    meta_text = meta.read_text()
    callees_line = next((line for line in meta_text.splitlines() if line.startswith("callees=")), "")
    names = [n for n in callees_line.partition("=")[2].split() if n]
    context = {
        "schema_version": 1,
        "binary_sha256": __import__("hashlib").sha256(args.binary.read_bytes()).hexdigest(),
        "target": args.function,
        "target_c": c.name,
        "target_meta": meta.name,
        "callees": [],
        "missing_or_external": [],
    }
    for name in names:
        child = args.out / "callees" / name
        child.mkdir(parents=True, exist_ok=True)
        cc, cm = _run(args.binary, name, child)
        if cc is None or cm is None:
            context["missing_or_external"].append(name)
            continue
        context["callees"].append({
            "name": name,
            "c": str(cc.relative_to(args.out)),
            "meta": str(cm.relative_to(args.out)),
        })
    (args.out / f"{args.function}.context.json").write_text(
        json.dumps(context, indent=2) + "\n"
    )
    print(json.dumps({
        "out": str(args.out / f"{args.function}.context.json"),
        "callees": [item["name"] for item in context["callees"]],
        "missing_or_external": context["missing_or_external"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
