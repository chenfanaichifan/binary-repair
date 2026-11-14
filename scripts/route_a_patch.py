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
    ap.add_argument("--resolve-gaps", action="store_true",
                    help="classify calls and apply reviewed syscall stubs; fail on unknown symbols")
    args = ap.parse_args()
    try:
        from patcherex2 import ModifyFunctionPatch, Patcherex
    except ImportError:
        print("patcherex2 is not installed in this interpreter", file=sys.stderr)
        return 2
    raw_symbols = json.loads(args.symbols) if args.symbols.strip() else {}
    symbols = {str(k): int(v, 16) if isinstance(v, str) else int(v) for k, v in raw_symbols.items()}
    code = args.c_source.read_text()
    if args.resolve_gaps:
        from routeb.symbol_resolver import apply_stubs, resolve
        resolution = resolve(code, set(symbols), target_name=args.function)
        if not resolution.ok:
            print(json.dumps({"ok": False, "reason": "unresolved_symbols",
                              "unresolved": resolution.unresolved,
                              "stubs": resolution.stubs}, ensure_ascii=False), file=sys.stderr)
            return 3
        code = apply_stubs(code, resolution)
        print(json.dumps({"symbol_resolution": resolution.to_dict()}, ensure_ascii=False), file=sys.stderr)
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
