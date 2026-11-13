#!/usr/bin/env python3
"""Direct binary repair CLI: format-detecting, fail-closed byte rewrite.

Examples:
  scripts/repair_binary.py input.elf output.elf --report report.json
  scripts/repair_binary.py input.exe --scan-only --backend pe
  scripts/repair_binary.py input.macho output.macho --strategy cave --verify
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.binary_pipeline import repair_binary, scan_binary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path, nargs="?")
    ap.add_argument("--report", type=Path)
    ap.add_argument("--scan-only", action="store_true")
    ap.add_argument("--backend", choices=("auto", "elf", "pe", "macho"), default="auto")
    ap.add_argument("--strategy", default="auto")
    ap.add_argument("--verify", dest="verify", action="store_true", default=True)
    ap.add_argument("--no-verify", dest="verify", action="store_false")
    args = ap.parse_args()

    data = args.input.read_bytes()
    if args.scan_only:
        payload = scan_binary(data)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.output is None:
        print("output is required unless --scan-only is used", file=sys.stderr)
        return 2

    patched, report = repair_binary(
        data, backend=args.backend, strategy=args.strategy, verify=args.verify
    )
    payload = report.to_dict()
    if patched is None:
        print(json.dumps({"supported": False, "report": payload}, indent=2, ensure_ascii=False))
        return 2

    args.output.write_bytes(patched)
    if report.format == "elf":
        args.output.chmod(0o755)
    if args.report:
        args.report.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "supported": True,
        "format": report.format,
        "arch": report.arch,
        "backend": report.backend,
        "strategy": report.strategy,
        "status": report.status,
        # legacy top-level keys used by earlier consumers/tests
        "mode": report.mode,
        "capacity": report.capacity,
        "report": payload,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
