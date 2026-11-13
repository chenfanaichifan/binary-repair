#!/usr/bin/env python3
"""Real-provider experiment for the two AI binary repair paths.

This is an exploratory measurement, not a CI test: it needs the operator's
configured provider and makes network calls.  It records only sanitized metadata
(status, model, latency, usage, disposition, hashes) — never the API key, raw
prompt, or raw model response.

The no-AI baseline is the deterministic v5 repair engine on the same fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_binary_repair import ASM_PATH, DIRECT_PATH, ai_repair  # noqa: E402
from app.services.binary_pipeline import repair_any  # noqa: E402

TASKS = (
    ("asm-i386-guard", ASM_PATH, ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf"),
    ("asm-x86_64-guard", ASM_PATH, ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"),
    ("asm-arm64-guard", ASM_PATH, ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf"),
    ("direct-pe-x86_64-guard", DIRECT_PATH, ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"),
    ("direct-pe-arm64-guard", DIRECT_PATH, ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe"),
    ("direct-i386-memcpy", DIRECT_PATH, ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"),
)


def _sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data else None


def _usage_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if isinstance(k, str)}
    return {"repr": type(value).__name__}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0,
                    help="only run the first N tasks (0 = all)")
    args = ap.parse_args()
    from app.services.assistant_llm import client_from_env

    client = client_from_env()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    if client is None:
        summary = {
            "schema_version": 1,
            "provider_available": False,
            "note": "no provider configured; experiment not run",
            "tasks": [],
        }
        (out / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False))
        return 2
    records = []
    tasks = TASKS[: args.limit] if args.limit > 0 else TASKS
    for name, path, fixture in tasks:
        data = fixture.read_bytes()
        baseline = repair_any(data)
        baseline_verified = baseline.verified
        try:
            outcome = ai_repair(data, path=path, client=client)
        except Exception as exc:  # noqa: BLE001
            records.append({
                "task": name, "path": path, "fixture": str(fixture.relative_to(ROOT)),
                "input_sha256": _sha(data), "exception": type(exc).__name__,
                "baseline_verified": baseline_verified,
            })
            continue
        ai = dict(outcome.ai)
        record = {
            "task": name,
            "path": path,
            "fixture": str(fixture.relative_to(ROOT)),
            "input_sha256": _sha(data),
            "ai": {
                "status": ai.get("status"),
                "called": ai.get("called"),
                "mode": ai.get("mode"),
                "provider": ai.get("provider"),
                "model": ai.get("model"),
                "latency_ms": ai.get("latency_ms"),
                "usage": _usage_dict(ai.get("usage")),
                "plan_sha256": ai.get("plan_sha256"),
                "error": ai.get("error"),
                "validation": ai.get("validation"),
            },
            "disposition": outcome.report.disposition,
            "verified": outcome.verified,
            "candidate_sha256": _sha(outcome.candidate),
            "report_error": outcome.report.error,
            "gate": ((outcome.report.verification or {}).get("gate") or {}),
            "runtime": (
                {"verdict": outcome.report.runtime.get("verdict"),
                 "tier": outcome.report.runtime.get("tier"),
                 "cases": outcome.report.runtime.get("cases")}
                if isinstance(outcome.report.runtime, dict) else None
            ),
            "baseline": {
                "disposition": baseline.report.disposition,
                "verified": baseline_verified,
                "candidate_sha256": _sha(baseline.candidate),
            },
            "increment": (
                "coverage_increment" if outcome.verified and not baseline_verified
                else "no_coverage_increment" if outcome.verified
                else "ai_failed_baseline_verified" if baseline_verified
                else "both_failed"
            ),
            "limitations": list(outcome.report.limitations),
        }
        records.append(record)
        print(json.dumps({
            "task": name, "path": path,
            "ai_status": record["ai"]["status"],
            "disposition": record["disposition"],
            "verified": record["verified"],
            "baseline_verified": baseline_verified,
            "increment": record["increment"],
        }, ensure_ascii=False), flush=True)
    summary = {
        "schema_version": 1,
        "provider_available": True,
        "provider": getattr(client, "base_url", ""),
        "model": getattr(client, "model", ""),
        "note": (
            "Exploratory real-provider run. No API key, raw prompt or raw model "
            "response is stored. All fixtures are also repairable by the "
            "deterministic baseline, so coverage increment on this set is expected "
            "to be zero; quality/candidate differences and AI failures are still "
            "recorded honestly."
        ),
        "records": records,
        "verified": sum(1 for row in records if row.get("verified")),
        "baseline_verified": sum(1 for row in records if (row.get("baseline") or {}).get("verified")),
        "coverage_increments": sum(1 for row in records if row.get("increment") == "coverage_increment"),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    sums = []
    for item in sorted(out.iterdir()):
        if item.is_file() and item.name != "SHA256SUMS":
            sums.append(f"{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(out), "verified": summary["verified"],
        "baseline_verified": summary["baseline_verified"],
        "coverage_increments": summary["coverage_increments"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
