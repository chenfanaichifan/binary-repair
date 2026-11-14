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
    ap.add_argument("--allow-fputs-stderr", action="store_true",
                    help="rewrite fputs(x, stderr) to the reviewed br_fputs write stub")
    ap.add_argument("--callee-context", type=Path, default=None,
                    help="export_with_callees JSON carrying measured symbol addresses")
    ap.add_argument("--meta-out", type=Path, default=None,
                    help="write typed patch-failure metadata when patching fails")
    args = ap.parse_args()
    try:
        from patcherex2 import ModifyFunctionPatch, Patcherex
    except ImportError:
        print("patcherex2 is not installed in this interpreter", file=sys.stderr)
        return 2
    raw_symbols = json.loads(args.symbols) if args.symbols.strip() else {}
    symbols = {str(k): int(v, 16) if isinstance(v, str) else int(v) for k, v in raw_symbols.items()}
    context_symbols: dict[str, int] = {}
    if args.callee_context is not None:
        context = json.loads(args.callee_context.read_text())
        for name, value in (context.get("symbols") or {}).items():
            try:
                context_symbols[str(name)] = int(value, 16) if isinstance(value, str) else int(value)
            except (TypeError, ValueError):
                continue
    inventory = None
    try:
        from app.services.repair.elf_symbols import available_symbols
        inventory = available_symbols(args.binary.read_bytes())
    except Exception as exc:  # noqa: BLE001 - auto symbols are optional
        print(json.dumps({"auto_symbols_error": f"{type(exc).__name__}: {exc}"}),
              file=sys.stderr)
    auto_symbols = inventory.by_name if inventory is not None else {}
    symbols = {**auto_symbols, **symbols, **context_symbols}
    code = args.c_source.read_text()
    if args.resolve_gaps:
        from routeb.symbol_resolver import apply_stubs, resolve
        resolution = resolve(code, set(symbols), target_name=args.function,
                             allow_fputs_stderr=args.allow_fputs_stderr)
        if not resolution.ok:
            reason = "blocked_symbols" if resolution.blocked else "unresolved_symbols"
            print(json.dumps({"ok": False, "reason": reason,
                              "unresolved": resolution.unresolved,
                              "blocked": resolution.blocked,
                              "stubs": resolution.stubs}, ensure_ascii=False), file=sys.stderr)
            return 3
        code = apply_stubs(code, resolution)
        print(json.dumps({"symbol_resolution": resolution.to_dict()}, ensure_ascii=False), file=sys.stderr)
    failure: dict[str, object] | None = None
    try:
        p = Patcherex(str(args.binary))
        p.patches.append(ModifyFunctionPatch(args.function, code, symbols=symbols))
        p.apply_patches()
        p.save_binary(str(args.out))
    except Exception as exc:  # noqa: BLE001 - classify, never claim success
        text = f"{type(exc).__name__}: {exc}"
        lowered = text.lower()
        if "undefined symbol" in lowered or "undefined reference" in lowered:
            error_class = "undefined_symbol"
        elif "clang" in lowered or "compilation" in lowered or "compile" in lowered:
            error_class = "compile_error"
        elif "out of" in lowered or "relocation" in lowered:
            error_class = "space_or_relocation"
        else:
            error_class = "unknown"
        failure = {
            "schema_version": 1,
            "function": args.function,
            "binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest(),
            "c_source_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "symbols": {k: hex(v) for k, v in sorted(symbols.items())},
            "error_class": error_class,
            "error": text,
        }
        if args.meta_out is not None:
            args.meta_out.write_text(json.dumps(failure, indent=2) + "\n")
        print(json.dumps({"ok": False, **failure}, ensure_ascii=False), file=sys.stderr)
        return 4
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
