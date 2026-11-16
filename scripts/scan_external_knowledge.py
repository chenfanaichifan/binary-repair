#!/usr/bin/env python3
"""Scan the committed CWE 5.0 external snapshot into capability candidates.

Offline by default. ``--live`` fetches official catalog/schema bytes for a
source/hash comparison only; tests never use it. External entries are
candidates, never support claims.
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

from app.services import external_knowledge as knowledge  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "phase8d-external-knowledge-2026-11-17"
ARTIFACT_FILES = ("external-knowledge.json", "README.md", "SHA256SUMS")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(rel: str) -> str:
    return _sha((ROOT / rel).read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def build_artifact(*, live: bool = False) -> dict[str, Any]:
    payload = knowledge.scan(root=ROOT, live=live)
    payload["provenance"]["scanner"] = "scripts/scan_external_knowledge.py"
    payload["provenance"]["snapshot_file_sha256"] = _sha_file(
        f"{knowledge.SNAPSHOT_REL}/snapshot.json"
    )
    payload["provenance"]["schema_drift_file_sha256"] = _sha_file(
        f"{knowledge.SNAPSHOT_REL}/schema-drift.json"
    )
    payload["provenance"]["provenance_file_sha256"] = _sha_file(
        f"{knowledge.SNAPSHOT_REL}/provenance.json"
    )
    payload["provenance"]["manifest_sha256"] = _sha_file("benchmark/phase8c/manifest.json")
    results = ROOT / "benchmark/phase8c/results.json"
    payload["provenance"]["results_sha256"] = (
        _sha(results.read_bytes()) if results.is_file() else None
    )
    candidates = payload["mapping"]["candidates"]
    if any(item.get("support_claimed") is not False for item in candidates):
        raise ValueError("external candidates must never claim support")
    if payload["summary"]["capability_promotion"] is not False:
        raise ValueError("external scan must not promote capability")
    return payload


def render_readme(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    drift = payload["version_drift"]
    lines = [
        "# Phase-8D external CWE 5.0 knowledge scan (2026-11-17)",
        "",
        "Generated deterministically from the committed normalized",
        "`data/external/cwe-5.0/` snapshot. External entries are capability",
        "*candidates*, not evidence of local support.",
        "",
        f"- catalog: CWE {payload['snapshot']['catalog_version']} "
        f"({payload['snapshot']['catalog_date']}), schema namespace "
        f"`{payload['snapshot']['schema_namespace']}`",
        f"- external weaknesses: {summary['external_entries']}",
        f"- mapped binary-relevant candidates: {summary['mapped_candidates']}",
        f"- unmapped entries: {summary['unmapped']}",
        f"- version drift status: `{drift['status']}`; new ids "
        f"{drift['new_count']}, removed {drift['removed_count']}",
        f"- support_claimed: `{summary['support_claimed']}`",
        f"- capability_promotion: `{summary['capability_promotion']}`",
        "",
        "## Candidate groups",
        "",
        "| group | candidates |",
        "|---|---|",
    ]
    for group, count in summary["mapped_by_group"].items():
        lines.append(f"| {group} | {count} |")
    lines += [
        "",
        "Every candidate carries a deterministic `GAP-KSRC-...` id, a proposed",
        "experiment, `support_claimed=false`, and public-corpus exposure counts.",
        "None is promoted to verified/resolved/open.",
        "",
        "## Schema drift",
        "",
        f"- prior: CWE {page(payload['schema_drift'])}",
        "- 4.19 -> 5.0 changed the XML namespace to `cwe-8`, removed Categories",
        "  from the weakness catalog layout, added 431 Groupings, and added 15 new",
        "  weakness ids. The briefing's approximate 16 is not asserted.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["limitations"])
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python scripts/scan_external_knowledge.py --write",
        "python scripts/scan_external_knowledge.py --check",
        "python -m pytest -q tests/test_phase8d_external_knowledge.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def page(schema_drift: dict[str, Any]) -> str:
    return str(schema_drift.get("prior_version") or "")


def build_files(payload: dict[str, Any]) -> dict[str, bytes]:
    files = {
        "external-knowledge.json": _canonical(payload).encode("utf-8"),
        "README.md": render_readme(payload).encode("utf-8"),
    }
    files["SHA256SUMS"] = "".join(
        f"{_sha(files[name])}  {name}\n"
        for name in sorted(files)
    ).encode("utf-8")
    return files


def write_artifact(payload: dict[str, Any], out: Path = ARTIFACT_DIR) -> list[str]:
    files = build_files(payload)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    return sorted(files)


def check_artifact(out: Path = ARTIFACT_DIR) -> list[str]:
    problems: list[str] = []
    expected = build_files(build_artifact(live=False))
    for name in ARTIFACT_FILES:
        target = out / name
        if not target.is_file():
            problems.append(f"missing {name}")
        elif target.read_bytes() != expected[name]:
            problems.append(f"artifact differs from offline rebuild: {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--live", action="store_true",
                        help="fetch official metadata for a source/hash comparison; no artifact write")
    parser.add_argument("--out", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args(argv)
    if args.live:
        meta = knowledge.fetch_live_metadata()
        snapshot = knowledge.load_snapshot(ROOT)
        same = meta["catalog_sha256"] == (snapshot.get("source") or {}).get("catalog_sha256")
        print(json.dumps({
            "ok": True,
            "live": meta,
            "snapshot_catalog_sha256": (snapshot.get("source") or {}).get("catalog_sha256"),
            "catalog_hash_matches_committed_snapshot": same,
            "note": "live fetch is metadata-only; the committed snapshot remains the scan source",
        }, indent=2, ensure_ascii=True))
        return 0
    payload = build_artifact(live=False)
    if args.check:
        problems = check_artifact(args.out)
        if args.json:
            print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
        else:
            print("external-knowledge: " + ("check OK" if not problems else
                                             f"{len(problems)} problem(s)"))
            for item in problems:
                print(f"  - {item}")
        return 0 if not problems else 1
    if args.write:
        written = write_artifact(payload, args.out)
        print(f"external-knowledge: wrote {args.out} files={len(written)}")
        return 0
    if args.json:
        print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    else:
        print(f"external-knowledge: candidates={payload['summary']['mapped_candidates']} "
              f"unmapped={payload['summary']['unmapped']} "
              f"drift={payload['version_drift']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
