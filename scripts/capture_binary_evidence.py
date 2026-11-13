#!/usr/bin/env python3
"""Capture the v5 universal repair evidence bundle.

For every positive fixture this writes:

  scan-<name>.json        non-mutating analysis
  repair-<name>.json      full report v3 (gate, runtime cases, actions)
  <name>-fixed.<ext>      the repaired candidate

Negative controls are captured as ``negative-<name>.json``.  The script also
writes ``README.md`` and ``SHA256SUMS`` over everything it produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.binary_pipeline import repair_any, scan_binary

SESSION_DATE = "2026-11-13"

POSITIVE = [
    ("elf-i386", ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf", ".elf"),
    ("pe-i386", ROOT / "fixtures" / "pe" / "vuln-strcpy-x86.exe", ".exe"),
    ("elf-x86_64-strict", ROOT / "artifacts" / "vuln-elf" / "vuln.elf", ".elf"),
    ("macho-arm64", ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64", ".macho"),
    ("macho-x86_64", ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64", ".macho"),
    ("pe-x86_64", ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe", ".exe"),
    ("pe-arm64", ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe", ".exe"),
    ("elf-arm64", ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf", ".elf"),
]

NEGATIVE = [
    ("pe-i386-no-sink", ROOT / "fixtures" / "pe" / "i386-control.exe", None),
    ("pe-no-pattern", ROOT / "fixtures" / "pe" / "cli-64.exe", None),
    ("macho-no-pattern", ROOT / "fixtures" / "macho" / "3D_Image_Toolkit", None),
    ("unknown-bytes", None, None),
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=ROOT / "artifacts" / f"binary-universal-v5-{SESSION_DATE}")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, path, suffix in POSITIVE:
        if path is None or not path.is_file():
            rows.append({"fixture": name, "status": "missing"})
            continue
        data = path.read_bytes()
        scan = scan_binary(data)
        _write_json(out / f"scan-{name}.json", scan)
        outcome = repair_any(data, verify=True)
        report = outcome.report
        _write_json(out / f"repair-{name}.json", report.to_dict())
        candidate = None
        if outcome.download_allowed and outcome.candidate is not None:
            candidate = out / f"{name}-fixed{suffix}"
            candidate.write_bytes(outcome.candidate)
            candidate.chmod(0o755)
        gate = (report.verification or {}).get("gate") or {}
        rows.append({
            "fixture": name,
            "format": report.format,
            "arch": report.arch,
            "status": report.status,
            "disposition": report.disposition,
            "verified": bool(outcome.verified),
            "strategy": report.strategy,
            "tier": (report.verification or {}).get("tier"),
            "gate": gate.get("success"),
            "candidate": candidate.name if candidate else None,
            "candidate_sha256": _sha(candidate) if candidate else None,
        })
    for name, path, _suffix in NEGATIVE:
        data = b"this is not a native executable\n" if path is None else path.read_bytes()
        outcome = repair_any(data, verify=True)
        report = outcome.report
        payload = {
            "fixture": name,
            "candidate_available": outcome.candidate is not None,
            "download_allowed": outcome.download_allowed,
            "disposition": report.disposition,
            "status": report.status,
            "error": report.error,
            "report": report.to_dict(),
        }
        _write_json(out / f"negative-{name}.json", payload)
        rows.append({"fixture": name, "negative": True,
                     "candidate": outcome.candidate is not None,
                     "disposition": report.disposition,
                     "status": report.status})

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"# BinaryRepair v5 — universal repair evidence ({SESSION_DATE})",
        "",
        f"Generated: `{generated}` by `scripts/capture_binary_evidence.py`.",
        "",
        "| fixture | format/arch | disposition | verified | strategy | runtime tier | gate |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        if row.get("negative"):
            lines.append(
                f"| {row['fixture']} | negative control | {row['disposition']} | — | — | — | candidate={row['candidate']} |"
            )
        elif row.get("status") == "missing":
            lines.append(f"| {row['fixture']} | — | missing | — | — | — | — |")
        else:
            lines.append(
                f"| {row['fixture']} | {row['format']}/{row['arch']} | {row['disposition']} "
                f"| {row['verified']} | {row['strategy']} | {row['tier']} | {row['gate']} |"
            )
    lines.extend([
        "",
        "`repair-<fixture>.json` is the complete report v4: disposition, findings,",
        "actions, runtime cases and the deterministic gate.  `negative-*.json` records",
        "fail-closed behavior: no candidate is written for unsupported inputs.",
        "",
        "Runtime tiers: `native_run` = the candidate executed on this macOS host;",
        "`emulated_run` = Unicorn instruction-level execution.  Neither is a",
        "hardened guest or a Windows kernel run.",
        "",
    ])
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")

    sums = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{_sha(path)}  {path.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "fixtures": len(POSITIVE),
                      "negatives": len(NEGATIVE)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
