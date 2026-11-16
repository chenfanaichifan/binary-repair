#!/usr/bin/env python3
"""Product demo pipeline: scan -> repair -> verify -> export evidence.

Product-facing demonstration entry point. It reuses the existing deterministic
engine and independent verifier instead of reimplementing them:

* scan      -> app.services.binary_pipeline.scan_binary
* repair    -> scripts/run_repair_benchmark.py execute_repair (which calls
               app.services.binary_pipeline.repair_any)
* verify    -> the in-tree independent verifier discovered by
               discover_verifier("auto"); the generator gate is never accepted
* export    -> scripts/product/export_report.py (customer report + evidence)

Security and reproducibility properties:

* deterministic path only: no AI provider, no API key, no outbound network;
* a fixture is reported VERIFIED_WITHIN_SCOPE only when the independent
  verifier returned "verified"; otherwise it stays NOT_VERIFIED/REFUSED/REJECTED
  with an explicit reason (fail closed);
* refused inputs produce no candidate bytes.

Usage::

    python scripts/product/demo_repair.py --list
    python scripts/product/demo_repair.py strcpy-stack-x86_64 --out artifacts/demo
    python scripts/product/demo_repair.py all --out artifacts/demo --json

Exit codes: 0 completed (any verdict, including REFUSED/NOT_VERIFIED), 1 an
internal fixture error or a false "verified" claim, 2 usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCHMARK_MANIFEST = "benchmark/phase8-v1/manifest.json"
NEGATIVE_FIXTURE = "tools/product/fixtures/unsupported-bigendian-elf64.bin"
ENGINE_EVIDENCE_DIR = "engine-evidence"
EVIDENCE_DIR = "evidence"
RUN_FILE = "demo-run.json"
DEFAULT_OUT = "artifacts/m3-product-2026-11-17/demo"

BOUNDARY = {
    "positioning": "bounded binary repair with auditable evidence; not universal repair",
    "public_benchmark": "2/24 verified (8.3%)",
    "hidden_benchmark": "0/8 verified",
    "detection_localization": "detection/root-cause/localization 3/24 (12.5%) each",
    "repair_scope": "one target function/sink per candidate; deterministic matrix only",
    "verification": (
        "deterministic unified gate + independent verifier; scope is the supplied "
        "PoC/regression cases and the one repaired function, not a whole-program proof"
    ),
    "not_claimed": [
        "arbitrary binary / arbitrary vulnerability / whole-program repair",
        "hidden generalisation or independently verified hidden repairs",
        "cross-compiler verification with a second toolchain",
        "new vulnerability-repair capability or automatic capability promotion",
        "that a repaired binary is safe for production use",
    ],
}

FIXTURES: dict[str, dict[str, Any]] = {
    "strcpy-stack-x86_64": {
        "label": "CWE-121 stack strcpy overflow (ELF x86-64)",
        "kind": "manifest_sample",
        "sample_id": "stack-strcpy-x86_64",
        "expected": "verified",
    },
    "marcx-capacity": {
        "label": "CWE-131/697/787 capacity-check confusion (ELF x86-64)",
        "kind": "manifest_sample",
        "sample_id": "heap-capacity-x86_64",
        "expected": "verified",
    },
    "unsupported-bigendian": {
        "label": "synthetic big-endian ELF64 header (fail-closed negative control)",
        "kind": "inline_sample",
        "expected": "refused",
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_module(relative: str, name: str) -> Any:
    path = ROOT / relative
    if not path.is_file():
        raise DemoError(f"required module is missing: {relative}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise DemoError(f"cannot load module: {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DemoError(RuntimeError):
    """The demo cannot run (missing engine module/fixture/manifest)."""


def load_engine() -> Any:
    """Load the committed deterministic repair benchmark driver as a library."""
    return _load_module("scripts/run_repair_benchmark.py", "product_demo_engine")


def load_scan() -> Any:
    from app.services.binary_pipeline import scan_binary

    return scan_binary


def _manifest_samples() -> tuple[dict[str, Any], dict[str, Any]]:
    path = ROOT / BENCHMARK_MANIFEST
    if not path.is_file():
        raise DemoError(f"missing benchmark manifest: {BENCHMARK_MANIFEST}")
    raw = path.read_bytes()
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DemoError(f"unreadable benchmark manifest: {exc}") from exc
    samples = {
        str(sample.get("sample_id")): sample
        for sample in manifest.get("samples") or []
        if isinstance(sample, dict) and sample.get("sample_id")
    }
    meta = {
        "manifest_path": BENCHMARK_MANIFEST,
        "manifest_sha256": _sha256(raw),
        "benchmark_id": manifest.get("benchmark_id"),
    }
    return samples, meta


def _negative_sample() -> tuple[dict[str, Any], dict[str, Any]]:
    path = ROOT / NEGATIVE_FIXTURE
    if not path.is_file():
        raise DemoError(f"missing negative-control fixture: {NEGATIVE_FIXTURE}")
    data = path.read_bytes()
    digest = _sha256(data)
    sample = {
        "sample_id": "unsupported-bigendian-negative-control",
        "split": "dev",
        "expected_scope": "function",
        "vulnerability_class": (
            "synthetic unsupported-container negative control (no vulnerability; "
            "fail-closed expectation)"
        ),
        "sha256": digest,
        "source_refs": [NEGATIVE_FIXTURE],
        "target": {"kind": "symbol", "symbol": "vuln_copy"},
        "oracle": {"kinds": [], "manifest_path": None},
        "format": "elf",
        "arch": "x86_64",
        "bits": 64,
        "endian": "big",
    }
    provenance = {
        "fixture": NEGATIVE_FIXTURE,
        "fixture_sha256": digest,
        "fixture_bytes": len(data),
        "kind": "synthetic_negative_control",
        "note": (
            "64-byte big-endian ELF64 header only; it is not a real vulnerability "
            "or a real program. It exists to prove the product refuses "
            "matrix-outside input without producing bytes."
        ),
    }
    return sample, provenance


def load_fixture(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve one registry fixture to a benchmark sample plus provenance."""
    spec = FIXTURES[name]
    if spec["kind"] == "manifest_sample":
        samples, meta = _manifest_samples()
        sample_id = str(spec["sample_id"])
        if sample_id not in samples:
            raise DemoError(
                f"sample {sample_id!r} is not in {BENCHMARK_MANIFEST}; the committed "
                "ground-truth manifest changed"
            )
        sample = json.loads(json.dumps(samples[sample_id]))
        refs = sample.get("source_refs") or []
        if not refs:
            raise DemoError(f"{sample_id}: empty source_refs")
        binary_path = str(refs[0])
        data = (ROOT / binary_path).read_bytes()
        digest = _sha256(data)
        declared = str(sample.get("sha256") or "")
        if declared and declared != digest:
            raise DemoError(
                f"{sample_id}: fixture sha256 mismatch (declared {declared}, "
                f"observed {digest}); refusing to demo a modified fixture"
            )
        provenance = {
            "fixture": binary_path,
            "fixture_sha256": digest,
            "fixture_bytes": len(data),
            "kind": "committed_benchmark_sample",
            "benchmark_manifest": meta["manifest_path"],
            "benchmark_manifest_sha256": meta["manifest_sha256"],
            "benchmark_id": meta["benchmark_id"],
            "poc_manifest": (sample.get("oracle") or {}).get("manifest_path"),
        }
        return sample, provenance
    sample, provenance = _negative_sample()
    return sample, provenance


def scan_stage(data: bytes) -> dict[str, Any]:
    """Product scan view: container/matrix/findings, never a verdict."""
    scan = load_scan()(data)
    findings = []
    for finding in scan.get("findings") or []:
        findings.append({
            key: finding.get(key)
            for key in (
                "kind", "callee", "address", "strategy", "capacity",
                "before", "after", "patchable", "detail",
            )
        })
    matrix = scan.get("matrix") or {}
    coverage = scan.get("coverage") or {}
    return {
        "format": scan.get("format"),
        "arch": scan.get("arch"),
        "bits": scan.get("bits"),
        "endian": scan.get("endian"),
        "supported": bool(scan.get("supported")),
        "repair_supported": bool(scan.get("repair_supported")),
        "findings_count": len(findings),
        "findings": findings[:12],
        "matrix_cell": matrix.get("cell"),
        "matrix_strategies": list(matrix.get("strategies") or []),
        "runtime_tiers": list(matrix.get("runtime_tiers") or []),
        "container_limitations": list(scan.get("limitations") or []),
        "coverage_non_goals": list(coverage.get("non_goals") or []),
    }


def _product_status(result: dict[str, Any], disposition: str, verifier_decision: Any) -> str:
    if result.get("not_run"):
        return "ERROR"
    if verifier_decision == "verified" and disposition == "verified_patch":
        return "VERIFIED_WITHIN_SCOPE"
    if disposition == "rejected":
        return "REJECTED"
    if disposition in {"unsupported", "invalid", "analysis_only"}:
        return "REFUSED"
    return "NOT_VERIFIED"


def _checks(evidence: dict[str, Any], verifier_reason: str | None) -> list[dict[str, Any]]:
    report = evidence.get("verifier_report")
    checks = report.get("checks") if isinstance(report, dict) else None
    rows = []
    for check in checks or []:
        if not isinstance(check, dict):
            continue
        rows.append({
            "id": check.get("id"),
            "title": check.get("title"),
            "status": check.get("status"),
            "required": check.get("required"),
            "detail": check.get("detail"),
        })
    if not rows:
        rows.append({
            "id": "independent_verification",
            "title": "independent verifier report",
            "status": "not_run",
            "required": True,
            "detail": verifier_reason or "independent verification did not run",
        })
    return rows


def _limitations(
    evidence: dict[str, Any], scan: dict[str, Any], spec: dict[str, Any]
) -> list[str]:
    report = evidence.get("verifier_report")
    rows = list(report.get("limitations") or []) if isinstance(report, dict) else []
    rows.extend(scan.get("container_limitations") or [])
    if spec["expected"] == "refused":
        rows.append(
            "negative control: the input is a synthetic header-only container, not "
            "a real program or vulnerability"
        )
    return rows


def _not_run(
    result: dict[str, Any], verifier_decision: Any, verifier_reason: str | None,
    oracle_status: Any, candidate_produced: bool,
) -> list[str]:
    rows = []
    if result.get("not_run"):
        rows.append(f"repair not run: {result.get('not_run_reason')}")
    if verifier_decision in {"not_run", "error", "inconclusive"}:
        rows.append(f"independent verification {verifier_decision}: {verifier_reason}")
    if oracle_status != "pass":
        rows.append(f"runtime oracle status={oracle_status}; no runtime evidence")
    if not candidate_produced:
        rows.append(
            f"no candidate produced (disposition={result.get('disposition')}); "
            "nothing is downloadable"
        )
    return rows


def run_fixture(
    name: str,
    outdir: Path,
    engine: Any,
    verifier: Any,
    verifier_status: dict[str, Any],
) -> dict[str, Any]:
    """Run scan -> repair -> verify for one fixture and persist its evidence."""
    spec = FIXTURES[name]
    sample, provenance = load_fixture(name)
    binary_path = str((sample.get("source_refs") or [""])[0])
    data = (ROOT / binary_path).read_bytes()
    scan = scan_stage(data)
    fixture_dir = outdir / EVIDENCE_DIR / name
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "scan.json").write_text(
        json.dumps(scan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = {
        "kind": "ground_truth_benchmark",
        "benchmark_id": f"product-demo/{name}",
        "generated_at": _utc_now(),
        "hidden_available": False,
        "samples": [sample],
    }
    error = None
    results = None
    try:
        results = engine.run_benchmark(
            manifest,
            verifier=verifier,
            verifier_status=verifier_status,
            claim_policy="withdraw",
        )
        engine.write_results(results, fixture_dir / ENGINE_EVIDENCE_DIR)
    except Exception as exc:  # noqa: BLE001 - recorded as an explicit error, never hidden
        error = f"{type(exc).__name__}: {exc}"

    if error is not None:
        record = {
            "fixture": name,
            "label": spec["label"],
            "expected": spec["expected"],
            "status": "ERROR",
            "reason": error,
            "input": {"path": binary_path, "sha256": provenance["fixture_sha256"]},
            "provenance": provenance,
            "scan": scan,
            "repair": {},
            "verification": {"independent_decision": None, "reason": error},
            "checks": _checks({}, error),
            "limitations": _limitations({}, scan, spec),
            "not_run": ["pipeline error; no repair or verification evidence"],
            "evidence_root": f"{EVIDENCE_DIR}/{name}",
        }
        return record

    result = results["results"][0]
    summary = results["summary"]
    evidence = result.get("_evidence") or {}
    disposition = str(result.get("disposition") or "")
    verifier_decision = result.get("verifier_decision")
    verifier_reason = result.get("verifier_reason")
    candidate_produced = bool(result.get("candidate_produced"))
    oracle_status = result.get("oracle_status")
    status = _product_status(result, disposition, verifier_decision)
    reason = (
        (evidence.get("outcome") or {}).get("error")
        or verifier_reason
        or (result.get("not_run_reason"))
    )
    repair = {
        "disposition": disposition,
        "strategy": result.get("strategy"),
        "candidate_produced": candidate_produced,
        "candidate_sha256": result.get("candidate_sha256"),
        "patched_sha256": result.get("patched_sha256"),
        "integrity": result.get("integrity"),
        "gate_outcome": result.get("gate_outcome"),
        "poc_status": result.get("poc_status"),
        "runtime_tier": result.get("runtime_tier"),
        "patch_plan_sha256": result.get("patch_plan_sha256"),
        "abi_blocks": result.get("abi_blocks") or [],
        "layout_status": result.get("layout_status"),
        "false_verified": bool(result.get("false_verified")),
        "deterministic_claim_withdrawn": bool(
            result.get("deterministic_claim_withdrawn")
        ),
        "deterministic_verified": bool(result.get("deterministic_verified")),
    }
    verification = {
        "independent_decision": verifier_decision,
        "verifier_id": result.get("verifier_id"),
        "reason": verifier_reason,
        "oracle_status": oracle_status,
        "layout_status": result.get("layout_status"),
        "real_verification": bool(result.get("real_verification")),
        "evidence_files_expected": True,
    }
    return {
        "fixture": name,
        "label": spec["label"],
        "expected": spec["expected"],
        "status": status,
        "reason": reason,
        "input": {"path": binary_path, "sha256": provenance["fixture_sha256"]},
        "provenance": provenance,
        "sample_id": result.get("sample_id"),
        "scan": scan,
        "repair": repair,
        "verification": verification,
        "checks": _checks(evidence, verifier_reason),
        "limitations": _limitations(evidence, scan, spec),
        "not_run": _not_run(
            result, verifier_decision, verifier_reason, oracle_status, candidate_produced
        ),
        "engine_summary": {
            key: summary.get(key)
            for key in (
                "samples", "executed", "not_run", "detected", "candidate_produced",
                "deterministic_verified", "independently_verified", "false_verified",
                "verification_disagreements", "deterministic_claim_withdrawn",
                "vuln_eliminated", "regression_ok",
            )
        },
        "evidence_root": f"{EVIDENCE_DIR}/{name}",
    }


def _evidence_index(outdir: Path) -> list[dict[str, Any]]:
    rows = []
    skip = {"SHA256SUMS", "EVIDENCE-INDEX.json"}
    for path in sorted(outdir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(outdir).as_posix()
        if relative in skip:
            continue
        data = path.read_bytes()
        rows.append({"path": relative, "sha256": _sha256(data), "bytes": len(data)})
    return rows


def _write_sha256sums(outdir: Path) -> Path:
    rows = []
    for path in sorted(outdir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(outdir).as_posix()
        if relative == "SHA256SUMS":
            continue
        rows.append(f"{_sha256(path.read_bytes())}  {relative}")
    target = outdir / "SHA256SUMS"
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return target


def run_demo(
    fixtures: list[str],
    outdir: Path,
    title: str,
    langs: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full product demo for the requested fixtures."""
    started = time.time()
    outdir.mkdir(parents=True, exist_ok=True)
    engine = load_engine()
    verifier, verifier_status = engine.discover_verifier("auto")
    records = []
    for name in fixtures:
        records.append(run_fixture(name, outdir, engine, verifier, verifier_status))
    run = {
        "schema_version": 1,
        "kind": "product_demo_run",
        "title": title,
        "generated_at": _utc_now(),
        "elapsed_seconds": round(time.time() - started, 2),
        "host": {
            "platform": sys.platform,
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "execution": {
            "deterministic_only": True,
            "ai_used": False,
            "api_key_required": False,
            "network_used": False,
            "engine": "app.services.binary_pipeline.repair_any",
            "repair_driver": "scripts/run_repair_benchmark.py (execute_repair)",
            "independent_verifier": verifier_status,
            "report_langs": list(langs or ["en", "zh"]),
        },
        "fixtures": records,
        "boundary": BOUNDARY,
    }
    (outdir / RUN_FILE).write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    run["evidence_index"] = _evidence_index(outdir)
    exporter = _load_module("scripts/product/export_report.py", "product_export_report")
    reports = {}
    for lang in langs or ["en", "zh"]:
        reports[lang] = exporter.export_report(outdir, title=title, lang=lang)
    run["reports"] = reports
    run["report"] = reports.get("en") or next(iter(reports.values()))
    return run


def _format_line(index: int, total: int, record: dict[str, Any]) -> str:
    repair = record.get("repair") or {}
    verification = record.get("verification") or {}
    details = [
        f"disposition={repair.get('disposition')}",
        f"verifier={verification.get('independent_decision')}",
        f"oracle={verification.get('oracle_status')}",
        f"tier={repair.get('runtime_tier')}",
    ]
    line = (
        f"[{index}/{total}] {record['fixture']}: {record['status']} "
        f"({', '.join(details)})"
    )
    reason = record.get("reason")
    if reason and record["status"] != "VERIFIED_WITHIN_SCOPE":
        line += f"\n      reason: {reason}"
    for item in record.get("not_run") or []:
        line += f"\n      not_run: {item}"
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Product demo: scan -> repair -> independent verify -> export report "
            "(deterministic path, no AI provider, no API key, no network)."
        )
    )
    parser.add_argument(
        "fixture",
        nargs="?",
        help="fixture id, or 'all'; see --list",
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--title", default="BinaryRepair product demo",
                        help="report title")
    parser.add_argument(
        "--lang",
        choices=("en", "zh", "both"),
        default="both",
        help="report language: en (ASCII, default-safe), zh, or both",
    )
    parser.add_argument("--list", action="store_true", help="list fixtures and exit")
    parser.add_argument("--json", action="store_true", help="print only JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when an expected-verified fixture is not VERIFIED_WITHIN_SCOPE",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name, spec in FIXTURES.items():
            print(f"{name}\texpected={spec['expected']}\t{spec['label']}")
        return 0
    if not args.fixture:
        parser.error("a fixture id or 'all' is required (see --list)")
    names = list(FIXTURES) if args.fixture == "all" else [args.fixture]
    unknown = [name for name in names if name not in FIXTURES]
    if unknown:
        print(json.dumps({"ok": False, "error": f"unknown fixture(s): {unknown}"}))
        return 2
    outdir = Path(args.out)
    if not outdir.is_absolute():
        outdir = Path.cwd() / outdir
    langs = ["en", "zh"] if args.lang == "both" else [args.lang]
    try:
        run = run_demo(names, outdir, args.title, langs)
    except DemoError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    records = run["fixtures"]
    false_verified = [
        record["fixture"] for record in records
        if (record.get("repair") or {}).get("false_verified")
        or (record.get("repair") or {}).get("deterministic_claim_withdrawn")
    ]
    internal_errors = [r["fixture"] for r in records if r["status"] == "ERROR"]
    strict_failures = [
        r["fixture"] for r in records
        if args.strict and r["expected"] == "verified" and r["status"] != "VERIFIED_WITHIN_SCOPE"
    ]
    report = run.get("report") or {}
    summary = {
        "ok": not internal_errors and not false_verified,
        "outdir": str(outdir),
        "elapsed_seconds": run["elapsed_seconds"],
        "fixtures": [
            {
                "fixture": record["fixture"],
                "expected": record["expected"],
                "status": record["status"],
                "disposition": (record.get("repair") or {}).get("disposition"),
                "independent_decision": (
                    record.get("verification") or {}
                ).get("independent_decision"),
                "oracle_status": (record.get("verification") or {}).get("oracle_status"),
                "runtime_tier": (record.get("repair") or {}).get("runtime_tier"),
                "reason": record.get("reason"),
                "not_run": record.get("not_run"),
            }
            for record in records
        ],
        "report": report.get("report_md"),
        "report_zh": (run.get("reports") or {}).get("zh", {}).get("report_md"),
        "evidence_index": report.get("evidence_index"),
        "fail_closed_ok": report.get("fail_closed", {}).get("ok"),
        "false_verified": false_verified,
        "boundary": {
            "public_benchmark": BOUNDARY["public_benchmark"],
            "hidden_benchmark": BOUNDARY["hidden_benchmark"],
        },
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("== BinaryRepair product demo (deterministic, no key, no network) ==")
        print(f"outdir: {outdir}")
        for index, record in enumerate(records, 1):
            print(_format_line(index, len(records), record))
        print(f"report (en): {report.get('report_md')}")
        zh_report = (run.get("reports") or {}).get("zh", {}).get("report_md")
        if zh_report:
            print(f"report (zh): {zh_report}")
        print(f"evidence index: {report.get('evidence_index')}")
        print(
            "boundary: public benchmark 2/24 verified (8.3%) | hidden 0/8 | "
            "one target function/sink per candidate"
        )
        if not summary["fail_closed_ok"]:
            print("FAIL-CLOSED CHECK FAILED: see REPORT.md fail-closed section")
        if false_verified:
            print(f"FALSE VERIFIED CLAIM DETECTED: {false_verified}")
    if internal_errors or false_verified:
        return 1
    if strict_failures:
        print(
            "strict mode: expected-verified fixtures that are not verified: "
            + ", ".join(strict_failures),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
