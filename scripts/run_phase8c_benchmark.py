#!/usr/bin/env python3
"""Phase-8C C6 public benchmark runner v2 (deterministic; no AI, no network).

Runs the committed ``benchmark/phase8c/manifest.json`` against the deterministic
repair engine, independently verifies candidates, classifies semantic regression
evidence, and emits:

* ``benchmark/phase8c/results.json`` -- the C2 ``benchmark-results-v2`` document
  validated by the contract checker integration;
* ``artifacts/phase8c-benchmark-2026-11-16/`` -- per-sample evidence, layered
  metrics, README and SHA256SUMS;
* optional hidden aggregate only at
  ``artifacts/phase8c-hidden-2026-11-16/aggregate.json`` (counts only).

Usage::

    python scripts/run_phase8c_benchmark.py                     # full public run
    python scripts/run_phase8c_benchmark.py --split dev --json  # print only
    python scripts/run_phase8c_benchmark.py --repeat 2          # flake history
    python scripts/run_phase8c_benchmark.py --check-artifact    # offline check
    python scripts/run_phase8c_benchmark.py --hidden-root "$PHASE8C_HIDDEN_ROOT"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import benchmark_runner  # noqa: E402


def _summary(run: dict, *, written: dict | None, hidden: dict | None) -> dict:
    results = run["results"]
    aggregate = results["aggregate"]
    metrics = run.get("metrics") or {}
    overall = (metrics.get("overall") or {})
    summary = {
        "ok": bool(run["ok"]),
        "exit_code": int(run["exit_code"]),
        "benchmark_id": results["benchmark_id"],
        "manifest_sha256": results["manifest_sha256"],
        "generated_at": results["generated_at"],
        "samples": aggregate["sample_count"],
        "status_counts": aggregate["status_counts"],
        "verified_count": aggregate["verified_count"],
        "rejected_count": aggregate["rejected_count"],
        "false_verified_count": aggregate["false_verified_count"],
        "false_verified_internal": run.get("false_verified_count", 0),
        "deterministic_claim_withdrawn": run.get("withdrawn_count", 0),
        "denominator": aggregate["denominator"],
        "eligible_repair_cases": overall.get("eligible_repair_cases"),
        "rates": {
            "detection": (overall.get("detection") or {}).get("rate"),
            "root_cause_match": (overall.get("root_cause_match") or {}).get("rate"),
            "localization": (overall.get("localization") or {}).get("rate"),
            "verified_repair": (overall.get("verified_repair") or {}).get("rate"),
        },
        "repeats": run.get("repeats"),
        "stable_across_repeats": run.get("stable_across_repeats"),
        "repeat_history": run.get("repeat_history"),
        "independent_verifier": run.get("verifier"),
        "limitations": results.get("limitations"),
        "written": written,
        "hidden": (
            None if hidden is None else {
                "ok": bool(hidden.get("ok")),
                "exit_code": hidden.get("exit_code"),
                "commitment_sha256": hidden.get("commitment_sha256"),
                "private_report_sha256": hidden.get("private_report_sha256"),
                "false_verified_internal": hidden.get("false_verified_count"),
                "limitations": hidden.get("limitations"),
            }
        ),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase-8C public benchmark runner v2 "
                    "(deterministic repair + independent verification)")
    parser.add_argument("--manifest", default=benchmark_runner.MANIFEST_PATH,
                        help="benchmark manifest (default: %(default)s)")
    parser.add_argument("--split", default="all", choices=("all", "dev", "validation"),
                        help="manifest split to execute (default: all)")
    parser.add_argument("--verifier", default="auto",
                        help="independent verifier: auto|none|<path> (default: auto)")
    parser.add_argument("--out", default=benchmark_runner.PUBLIC_ARTIFACT_DIR,
                        help="public evidence directory (default: %(default)s)")
    parser.add_argument("--hidden-root", default=None,
                        help="Lead-owned private hidden root (or hidden-manifest.json "
                             "path); emitted aggregate only")
    parser.add_argument("--hidden-aggregate-out",
                        default=benchmark_runner.HIDDEN_AGGREGATE_PATH,
                        help="hidden aggregate output path (default: %(default)s)")
    parser.add_argument("--json", action="store_true",
                        help="print the summary JSON only; write no artifacts")
    parser.add_argument("--check-artifact", action="store_true",
                        help="validate the committed artifacts offline (no execution)")
    parser.add_argument("--repeat", type=int, default=1,
                        help="serialized repeat count; every attempt is recorded "
                             "(C1 flake warning: no unconditional stability claim)")
    parser.add_argument("--claim-policy", default="withdraw",
                        choices=benchmark_runner.CLAIM_POLICIES,
                        help="independent-rejection handling (default: withdraw the "
                             "deterministic claim and exit non-zero)")
    args = parser.parse_args(argv)

    if args.check_artifact:
        try:
            report = benchmark_runner.check_artifact(root=ROOT)
        except Exception as exc:  # noqa: BLE001 - error is evidence
            print(json.dumps({"ok": False,
                              "error": f"{type(exc).__name__}: {exc}"}))
            return 2
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("ok") else 1

    try:
        run = benchmark_runner.run_repeated(
            args.repeat,
            root=ROOT,
            manifest_path=args.manifest,
            split=args.split,
            verifier_spec=args.verifier,
            claim_policy=args.claim_policy,
        )
        hidden_result = None
        if args.hidden_root:
            hidden_result = benchmark_runner.run_hidden_lane(
                args.hidden_root,
                root=ROOT,
                verifier_spec=args.verifier,
                claim_policy=args.claim_policy,
            )
            benchmark_runner.attach_hidden_aggregate(run, hidden_result)
        written = None
        if not args.json:
            written = benchmark_runner.write_public_artifacts(run, root=ROOT,
                                                              out_dir=args.out)
            if args.split == "all":
                canonical = benchmark_runner.write_canonical_results(run, root=ROOT)
                written["canonical_results"] = str(canonical)
            if hidden_result is not None:
                hidden_path = benchmark_runner.write_hidden_aggregate(
                    hidden_result, path=args.hidden_aggregate_out, root=ROOT)
                written["hidden_aggregate"] = (
                    str(hidden_path) if hidden_path is not None else None)
        summary = _summary(run, written=written, hidden=hidden_result)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        if hidden_result is not None and hidden_result.get("exit_code") == 2:
            return 2
        return int(run["exit_code"])
    except benchmark_runner.BenchmarkError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001 - never crash without a JSON record
        print(json.dumps({"ok": False,
                          "error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
