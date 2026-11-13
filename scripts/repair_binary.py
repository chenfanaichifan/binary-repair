#!/usr/bin/env python3
"""Direct binary repair CLI: format-detecting, fail-closed byte rewrite.

Examples:
  scripts/repair_binary.py input.elf output.elf --report report.json
  scripts/repair_binary.py input.exe --scan-only --backend pe
  scripts/repair_binary.py input.macho output.macho --strategy guard --verify
  scripts/repair_binary.py --batch samples/ --out repaired/ --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.binary_pipeline import repair_any, scan_binary
from app.services.ai_binary_repair import AI_PATHS, ai_repair

SUFFIX = {"elf": ".elf", "pe": ".exe", "macho": ".macho"}


def _write_candidate(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o755)


def _repair_one(source: Path, output: Path | None, args) -> dict:
    data = source.read_bytes()
    if args.scan_only:
        return {"input": str(source), "scan": scan_binary(data)}
    if output is None:
        return {"input": str(source), "error": "output is required unless --scan-only is used"}
    if getattr(args, "ai_path", None):
        from app.services.assistant_llm import client_from_env

        ai_outcome = ai_repair(
            data, path=str(args.ai_path), client=client_from_env(),
            verify=args.verify, allow_static_only=args.allow_static_only,
        )
        report = ai_outcome.report
        payload = report.to_dict()
        if args.report:
            args.report.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if ai_outcome.candidate is None or not ai_outcome.download_allowed:
            return {
                "input": str(source),
                "supported": False,
                "path": args.ai_path,
                "disposition": report.disposition,
                "verified": False,
                "status": report.status,
                "error": report.error,
                "ai": ai_outcome.ai,
                "report": payload,
            }
        _write_candidate(output, ai_outcome.candidate)
        return {
            "input": str(source),
            "output": str(output),
            "supported": True,
            "path": args.ai_path,
            "verified": bool(ai_outcome.verified),
            "disposition": report.disposition,
            "format": report.format,
            "arch": report.arch,
            "strategy": report.strategy,
            "status": report.status,
            "mode": report.mode,
            "capacity": report.capacity,
            "delivery": payload.get("delivery", {}),
            "ai": ai_outcome.ai,
            "warnings": list(report.warnings),
            "report": payload,
        }
    outcome = repair_any(
        data,
        backend=args.backend,
        strategy=args.strategy,
        verify=args.verify,
        allow_static_only=args.allow_static_only,
    )
    report = outcome.report
    payload = report.to_dict()
    if args.report:
        args.report.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if outcome.candidate is None or not outcome.download_allowed:
        return {
            "input": str(source),
            "supported": False,
            "disposition": report.disposition,
            "verified": False,
            "status": report.status,
            "error": report.error,
            "report": payload,
        }
    _write_candidate(output, outcome.candidate)
    return {
        "input": str(source),
        "output": str(output),
        "supported": True,
        "verified": bool(outcome.verified),
        "disposition": report.disposition,
        "format": report.format,
        "arch": report.arch,
        "backend": report.backend,
        "strategy": report.strategy,
        "status": report.status,
        # legacy top-level keys used by earlier consumers/tests
        "mode": report.mode,
        "capacity": report.capacity,
        "delivery": payload.get("delivery", {}),
        "warnings": list(report.warnings),
        "report": payload,
    }


def _batch(source_dir: Path, out_dir: Path, args) -> int:
    counts = {
        "verified": 0, "static_only": 0, "analysis_only": 0,
        "unsupported": 0, "rejected": 0, "invalid": 0, "error": 0,
    }
    records = []
    for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
        if any(part.startswith(".") for part in source.relative_to(source_dir).parts):
            continue
        data = source.read_bytes()
        if args.scan_only:
            record = {"input": str(source), "scan": scan_binary(data)}
            counts["verified"] += 1
            records.append(record)
            if args.json:
                print(json.dumps(record, ensure_ascii=False))
            else:
                print(f"{'scan':12} {record['input']}")
            continue
        outcome = repair_any(
            data, backend=args.backend, strategy=args.strategy,
            verify=args.verify, allow_static_only=args.allow_static_only,
        )
        report = outcome.report
        suffix = SUFFIX.get(report.format, ".bin")
        target = out_dir / (source.stem + "-fixed" + suffix)
        disposition = report.disposition
        if outcome.candidate is None or not outcome.download_allowed:
            record = {
                "input": str(source), "format": report.format,
                "arch": report.arch, "status": report.status,
                "disposition": disposition,
                "error": report.error or (report.limitations[-1] if report.limitations else ""),
            }
            key = disposition if disposition in counts else "error"
            counts[key] += 1
        else:
            _write_candidate(target, outcome.candidate)
            record = {
                "input": str(source), "output": str(target),
                "format": report.format, "arch": report.arch,
                "strategy": report.strategy, "status": report.status,
                "disposition": disposition,
                "verified": bool(outcome.verified),
                "verification_tier": (report.verification or {}).get("tier"),
            }
            counts["verified" if outcome.verified else "static_only"] += 1
        records.append(record)
        if args.json:
            print(json.dumps(record, ensure_ascii=False))
        else:
            status = record.get("disposition") or "scan"
            print(f"{status:16} {record['input']}")
    summary = dict(counts)
    summary["ok"] = counts["verified"] + counts["static_only"]
    print(json.dumps({"summary": summary, "files": len(records)}, ensure_ascii=False))
    return 0 if counts["error"] == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, nargs="?")
    ap.add_argument("output", type=Path, nargs="?")
    ap.add_argument("--report", type=Path)
    ap.add_argument("--scan-only", action="store_true")
    ap.add_argument("--backend", choices=("auto", "elf", "pe", "macho"), default="auto")
    ap.add_argument("--strategy", default="auto")
    ap.add_argument("--ai-path", choices=AI_PATHS,
                    help="run one AI direct-binary path (ai_plan or ai_bytes)")
    ap.add_argument("--verify", dest="verify", action="store_true", default=True)
    ap.add_argument("--no-verify", dest="verify", action="store_false")
    ap.add_argument("--allow-static-only", action="store_true",
                    help="write a candidate even when runtime evidence is missing")
    ap.add_argument("--batch", type=Path, help="repair every file in a directory")
    ap.add_argument("--out", type=Path, help="output directory for --batch")
    ap.add_argument("--json", action="store_true", help="one JSON record per file")
    args = ap.parse_args()

    if args.batch is not None:
        if args.ai_path:
            print("--ai-path is single-file only; do not combine with --batch", file=sys.stderr)
            return 2
        if not args.batch.is_dir():
            print("--batch must be a directory", file=sys.stderr)
            return 2
        out_dir = args.out or (args.batch / "repaired")
        return _batch(args.batch, out_dir, args)

    if args.input is None:
        print("input is required unless --batch is used", file=sys.stderr)
        return 2
    record = _repair_one(args.input, args.output, args)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    if "scan" in record:
        return 0
    return 0 if record.get("output") else 2


if __name__ == "__main__":
    raise SystemExit(main())
