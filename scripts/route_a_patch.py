#!/usr/bin/env python3
"""Generic function-level Route A patch via Patcherex2.

This is the small backend adapter used by the CWE121 experiment.  It requires
patcherex2 in the active interpreter (separate venv recommended).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--function", required=True)
    ap.add_argument("--c-source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--symbols", default="{}", help='JSON object, e.g. {"printLine":"0x401380"}')
    args = ap.parse_args()
    try:
        from patcherex2 import ModifyFunctionPatch, Patcherex
    except ImportError:
        print("patcherex2 is not installed in this interpreter", file=sys.stderr)
        return 2
    raw_symbols = json.loads(args.symbols) if args.symbols.strip() else {}
    symbols = {str(k): int(v, 16) if isinstance(v, str) else int(v) for k, v in raw_symbols.items()}
    code = args.c_source.read_text()
    p = Patcherex(str(args.binary))
    p.patches.append(ModifyFunctionPatch(args.function, code, symbols=symbols))
    p.apply_patches()
    p.save_binary(str(args.out))
    args.out.chmod(0o755)
    print(json.dumps({
        "out": str(args.out),
        "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
        "function": args.function,
        "symbols": sorted(symbols),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
