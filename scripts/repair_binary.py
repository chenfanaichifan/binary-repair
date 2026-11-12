#!/usr/bin/env python3
"""Direct binary repair CLI: ELF bytes in, patched ELF bytes out."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.binary_repair_engine import repair_elf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path, nargs="?")
    ap.add_argument("--report", type=Path)
    ap.add_argument("--scan-only", action="store_true")
    args = ap.parse_args()
    data = args.input.read_bytes()
    if args.scan_only:
        from app.services.binary_repair_engine import scan_elf
        print(json.dumps(scan_elf(data), indent=2))
        return 0
    if args.output is None:
        print("output is required unless --scan-only is used", file=sys.stderr)
        return 2
    patched, report = repair_elf(data)
    if patched is None:
        print(json.dumps({"supported": False, "report": report.to_dict()}, indent=2))
        return 2
    args.output.write_bytes(patched)
    args.output.chmod(0o755)
    payload = {"supported": True, "mode": report.mode, "report": report.to_dict()}
    if args.report:
        args.report.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
