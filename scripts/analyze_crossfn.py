#!/usr/bin/env python3
"""M2 cross-function analysis CLI (read-only; Phase-9 E-01/E-02/E-03 prototype).

Evidence tool, NOT a repair tool: it never writes a patch, never produces a
candidate, never calls a model/provider and is not wired into repair_any or any
gate.  Output is analysis evidence plus explicit limitations/unknowns.

Usage:
  scripts/analyze_crossfn.py --elf fixtures/crossfn/crossfn_param.elf --json
  scripts/analyze_crossfn.py --elf BIN --json --out evidence.json
  scripts/analyze_crossfn.py --elf BIN --json --functions main,wrapper,copy_payload
  scripts/analyze_crossfn.py --elf BIN                 # human summary

Exit codes:
  0 = analysis completed (even when capacities remain unknown)
  2 = input file missing/unreadable or empty
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.analysis.cfg import build_cfg
from app.services.analysis.dataflow import analyze_crossfn
from app.services.containers import detect_container


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _selected_functions(cfg, names: list[str]) -> list[dict]:
    wanted = {name.strip() for name in names if name.strip()}
    selected = []
    missing = []
    for name in sorted(wanted):
        function = next((item for item in cfg.functions if item.name == name), None)
        if function is None:
            missing.append(name)
            continue
        selected.append(function.to_dict(include_instructions=True))
    return selected, missing


def _human_summary(payload: dict, path: Path) -> str:
    lines = [
        f"input: {path}",
        f"container: {payload['format']}/{payload['arch']}/{payload['bits']} bits",
        f"sinks: {len(payload['sinks'])}",
    ]
    for sink in payload["sinks"]:
        destination = sink["destination"]
        lines.append(
            f"- 0x{sink['site_va']:x} {sink['callee']} in "
            f"{sink['function']['name'] or hex(sink['function']['va'])}: "
            f"origin={destination['origin']} capacity={destination['capacity']} "
            f"source={destination['capacity_source']} "
            f"agreement={destination['agreement']} "
            f"resolution={destination['resolution']}"
        )
        for path_entry in destination["paths"]:
            caller = path_entry.get("caller") or {}
            lines.append(
                f"    path caller={caller.get('name')} origin="
                f"{path_entry['origin']} capacity={path_entry['capacity']} "
                f"source={path_entry['capacity_source']} "
                f"resolution={path_entry['resolution']}"
            )
    limitations = payload.get("limitations") or []
    lines.append(f"limitations: {len(limitations)}")
    for text in limitations[:10]:
        lines.append(f"  ! {text}")
    lines.append("NOTE: analysis evidence only; no repair candidate is produced.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only cross-function analysis prototype (M2/Phase-9).",
    )
    parser.add_argument("--elf", required=True, help="input binary (ELF/PE/Mach-O)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON evidence to stdout")
    parser.add_argument("--out", default=None,
                        help="write the JSON evidence to this path as well")
    parser.add_argument("--functions", default="",
                        help="comma-separated function names whose CFG blocks/"
                             "instructions are embedded in the JSON")
    args = parser.parse_args(argv)

    path = Path(args.elf)
    if not path.is_file():
        print(f"error: input not found: {path}", file=sys.stderr)
        return 2
    data = path.read_bytes()
    if not data:
        print(f"error: empty input: {path}", file=sys.stderr)
        return 2
    container = detect_container(data)
    payload = analyze_crossfn(data, container=container)
    payload["input"] = {
        "path": str(path),
        "sha256": _sha256(data),
        "size": len(data),
    }
    if args.functions:
        cfg = build_cfg(data, container=container)
        selected, missing = _selected_functions(
            cfg, args.functions.split(","))
        payload["cfg_functions"] = selected
        if missing:
            payload["input"]["functions_not_found"] = missing
    encoded = json.dumps(payload, indent=2, sort_keys=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(_human_summary(payload, path))
        if args.out:
            print(f"json evidence written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
