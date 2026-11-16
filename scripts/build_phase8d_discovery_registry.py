#!/usr/bin/env python3
"""Build/check the additive Phase-8D discovery-mechanism registry (D07).

The historical Phase-7 seven-mechanism artifact is retained untouched. This
registry records which mechanisms have real Phase-8D evidence, which remain
not_run, and which are still standalone adapters rather than integrated into
the historical discovery script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "phase8d-discovery-registry-2026-11-17"
GENERATED_AT = "2026-11-17T00:00:00Z"
KIND = "phase8d_discovery_mechanism_registry"


def _sha(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"missing evidence: {relative}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_registry() -> dict[str, Any]:
    old_registry = "artifacts/gap-registry-2026-11-16/gaps.json"
    metamorphic = "artifacts/phase8d-discovery-2026-11-17/discovery.json"
    external = "artifacts/phase8d-external-knowledge-2026-11-17/external-knowledge.json"
    records = [
        {
            "mechanism": "knowledge",
            "phase7_status": "run",
            "phase8d_status": "run",
            "evidence": old_registry,
            "evidence_sha256": _sha(old_registry),
            "support_claimed": False,
            "detail": "Historical knowledge adapter remains the only integrated catalog mapper; no new support claim.",
        },
        {
            "mechanism": "failure_driven",
            "phase7_status": "run",
            "phase8d_status": "run",
            "evidence": old_registry,
            "evidence_sha256": _sha(old_registry),
            "support_claimed": False,
            "detail": "Historical failure-driven adapter remains integrated; Phase-8D gap records reference it.",
        },
        {
            "mechanism": "differential",
            "phase7_status": "run",
            "phase8d_status": "run",
            "evidence": old_registry,
            "evidence_sha256": _sha(old_registry),
            "support_claimed": False,
            "detail": "Historical declared-vs-measured differential adapter remains integrated.",
        },
        {
            "mechanism": "mutation",
            "phase7_status": "not_run",
            "phase8d_status": "run_standalone",
            "evidence": metamorphic,
            "evidence_sha256": _sha(metamorphic),
            "support_claimed": False,
            "detail": "11 family-specific input mutations executed through the real guest oracle; adapter is standalone, not wired into scripts/discover_capability_gaps.py.",
        },
        {
            "mechanism": "metamorphic",
            "phase7_status": "not_run",
            "phase8d_status": "run_standalone",
            "evidence": metamorphic,
            "evidence_sha256": _sha(metamorphic),
            "support_claimed": False,
            "detail": "Four same-source compiler variants compared with actual deterministic-engine records; adapter is standalone.",
        },
        {
            "mechanism": "sample_based",
            "phase7_status": "not_run",
            "phase8d_status": "not_run",
            "evidence": None,
            "evidence_sha256": None,
            "support_claimed": False,
            "reason": "no external sample corpus was ingested into this Phase-8D tree; not_run instead of inventing samples",
        },
        {
            "mechanism": "knowledge_source_scan",
            "phase7_status": "not_run",
            "phase8d_status": "run_standalone",
            "evidence": external,
            "evidence_sha256": _sha(external),
            "support_claimed": False,
            "detail": "Versioned CWE 5.0 snapshot parsed into 232 candidates and drift facts; adapter is standalone and does not claim support.",
        },
    ]
    effective_run = [r for r in records if r["phase8d_status"].startswith("run")]
    standalone = [r for r in records if r["phase8d_status"] == "run_standalone"]
    not_run = [r for r in records if r["phase8d_status"] == "not_run"]
    return {
        "schema_version": 1,
        "kind": KIND,
        "generated_at": GENERATED_AT,
        "historical_registry": old_registry,
        "historical_registry_sha256": _sha(old_registry),
        "mechanism_count": len(records),
        "records": records,
        "summary": {
            "effective_run_count": len(effective_run),
            "integrated_run_count": len([r for r in records if r["phase8d_status"] == "run"]),
            "standalone_run_count": len(standalone),
            "not_run_count": len(not_run),
            "sample_based_status": "not_run",
            "capability_promotion": False,
            "support_claimed": False,
        },
        "limitations": [
            "This is an additive registry; the historical seven-mechanism artifact is not rewritten.",
            "Standalone mechanisms have real Phase-8D evidence but are not integrated into scripts/discover_capability_gaps.py.",
            "sample_based discovery remains not_run; no external sample corpus was ingested.",
            "Candidate counts are discovery inputs, not repaired or independently verified capabilities.",
        ],
    }


def _sums() -> str:
    files = ["registry.json", "README.md"]
    lines = []
    for name in files:
        path = OUT / name
        if path.is_file():
            lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}")
    return "\n".join(lines) + "\n"


def write() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build_registry()
    (OUT / "registry.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUT / "README.md").write_text(
        "# Phase-8D discovery mechanism registry\n\n"
        "Additive D07 record. The historical Phase-7 seven-mechanism artifact is unchanged.\n"
        "Statuses distinguish integrated, standalone-with-real-evidence, and not_run.\n\n"
        "- `registry.json` - mechanisms, evidence paths/digests, summary and limitations\n"
        "- `SHA256SUMS` - artifact integrity\n",
        encoding="utf-8",
    )
    (OUT / "SHA256SUMS").write_text(_sums(), encoding="utf-8")


def check() -> tuple[bool, list[str]]:
    problems: list[str] = []
    path = OUT / "registry.json"
    if not path.is_file():
        return False, ["missing registry.json"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"unreadable registry.json: {exc}"]
    if payload != build_registry():
        problems.append("registry.json differs from deterministic builder output")
    for record in payload.get("records") or []:
        if record.get("mechanism") == "sample_based" and record.get("phase8d_status") != "not_run":
            problems.append("sample_based must remain not_run without a real corpus")
        evidence = record.get("evidence")
        if record.get("phase8d_status", "").startswith("run"):
            if not evidence or not (ROOT / evidence).is_file():
                problems.append(f"{record.get('mechanism')}: missing evidence")
            elif hashlib.sha256((ROOT / evidence).read_bytes()).hexdigest() != record.get("evidence_sha256"):
                problems.append(f"{record.get('mechanism')}: evidence digest mismatch")
    if (payload.get("summary") or {}).get("capability_promotion") is not False:
        problems.append("capability_promotion must be false")
    return not problems, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        write()
        print("phase8d-discovery-registry: wrote", OUT)
        return 0
    ok, problems = check()
    if args.json:
        print(json.dumps({"ok": ok, "problems": problems}, indent=2))
    else:
        print("phase8d-discovery-registry: check OK" if ok else "phase8d-discovery-registry: FAILED")
        for problem in problems:
            print(" -", problem)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
