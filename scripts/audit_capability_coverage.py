#!/usr/bin/env python3
"""Run the capability-gap self-discovery audit and write the evidence artifacts.

Usage::

    .venv/bin/python scripts/audit_capability_coverage.py
    .venv/bin/python scripts/audit_capability_coverage.py --static-only
    .venv/bin/python scripts/audit_capability_coverage.py --output-dir /tmp/audit

The audit imports and probes the real product modules, writes
``coverage-matrix.json``, ``gap-report.md`` and ``SHA256SUMS`` into
``artifacts/capability-gap-audit-2026-11-14/`` by default, prints a short
summary and exits 0. Missing/mid-flight modules are recorded as
``module_not_ready`` evidence instead of aborting the run.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.coverage_audit import (  # noqa: E402
    ARTIFACT_DIR,
    DEFAULT_BUDGET_SECONDS,
    build_audit,
    write_artifacts,
)


def _print_summary(audit: dict) -> None:
    summary = audit.get("summary", {})
    print(
        "audit: gaps={gap_count} open={open_count} mitigated={mitigated_count} "
        "closed={closed_count} non_goal={non_goal_count} "
        "high_open={high_severity_open}".format(**summary)
    )
    probes = summary.get("probes", {})
    print(
        "probes: fixtures={fixtures} analysis={analysis} strategies={strategies} "
        "capacity={capacity} skipped_budget={skipped_budget}".format(**probes)
    )
    open_ids = summary.get("open_gap_ids", [])
    if open_ids:
        print("open gap ids:")
        for gap_id in open_ids:
            print(f"  - {gap_id}")
    if audit.get("mode") == "static":
        print("mode=static: no fixture/strategy probes were run")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="capability-gap self-discovery audit for the binary repair product"
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / ARTIFACT_DIR),
        help=f"artifact directory (default: {ARTIFACT_DIR})",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="run the static census only (no fixture/strategy probes)",
    )
    parser.add_argument(
        "--max-fixture-probes",
        type=int,
        default=None,
        help="bound the number of fixture probes (tests/debugging)",
    )
    parser.add_argument(
        "--budget-seconds",
        type=float,
        default=DEFAULT_BUDGET_SECONDS,
        help=f"wall-clock safety budget for probes (default {DEFAULT_BUDGET_SECONDS:.0f}s)",
    )
    parser.add_argument(
        "--no-legacy-artifact",
        action="store_true",
        help="do not include the legacy artifacts/vuln-elf/vuln.elf input",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the full audit JSON to stdout instead of only a summary",
    )
    args = parser.parse_args(argv)
    try:
        audit = build_audit(
            include_probes=not args.static_only,
            include_legacy_artifact=not args.no_legacy_artifact,
            max_fixture_probes=args.max_fixture_probes,
            budget_seconds=args.budget_seconds,
        )
    except Exception:  # noqa: BLE001 - a self-discovery audit must not crash a CI job
        traceback.print_exc()
        audit = {
            "schema_version": 1,
            "audit_date": "2026-11-14",
            "generated_by": "app/services/coverage_audit.py",
            "mode": "failed",
            "gaps": [],
            "summary": {"gap_count": 0, "open_count": 0, "open_gap_ids": [],
                        "probes": {}},
        }
    try:
        written = write_artifacts(audit, args.output_dir)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 0
    if args.json:
        import json

        print(json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_summary(audit)
    print("wrote:")
    for name, path in written["files"].items():
        print(f"  {name}: {path} ({written['sha256'][name]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
