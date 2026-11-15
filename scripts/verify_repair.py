#!/usr/bin/env python3
"""CLI for the independent repair verifier.

Usage::

    python scripts/verify_repair.py --original PATH --candidate PATH \
        --metadata PATH [--poc PATH] [--json]
    python scripts/verify_repair.py --selftest [--json]

The verifier re-derives everything from raw bytes and an independent oracle; it
never reads a generator verdict.  Exit codes:

* ``0`` verified (or a passing self-test);
* ``1`` rejected/inconclusive, or a tamper/self-test failure;
* ``2`` usage/unsupported target/unavailable (no verification report emitted).

The self-test is hermetic: it uses synthetic bytes and injected container/ABI/
oracle stubs, executes no real binary, and also validates every generated report
against ``contracts/verification.schema.json`` (jsonschema when installed, a
fail-closed fallback otherwise).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import independent_verifier as verifier  # noqa: E402


def _exit_for_decision(decision: str) -> int:
    if decision == "verified":
        return 0
    if decision == "not_run":
        return 2
    return 1


def _selftest_fixtures() -> dict[str, Any]:
    original = bytes(range(256)) * 4
    candidate = bytearray(original)
    candidate[32:40] = b"\x90" * 8
    candidate = bytes(candidate)
    actions = [{
        "offset": 32,
        "size": 8,
        "before_hex": original[32:40].hex(),
        "after_hex": candidate[32:40].hex(),
    }]
    return {"original": original, "candidate": candidate, "actions": actions}


def _selftest_stubs(oracle_status: str = "pass", abi_ok: bool = True) -> dict[str, Any]:
    import hashlib

    def detect(data: bytes) -> dict[str, Any]:
        return {
            "format": "elf",
            "arch": "x86_64",
            "bits": 64,
            "endian": "little",
            "sections": [{"name": ".text", "va": 0x401000, "size": 256,
                          "offset": 0, "executable": True}],
        }

    def abi_check(code: bytes, arch: str) -> dict[str, Any]:
        return {"ok": abi_ok, "fatal": 0 if abi_ok else 1,
                "findings": [] if abi_ok else [{"code": "stack_unbalanced",
                                                "severity": "fatal"}]}

    def run_poc(original: bytes, candidate: bytes, manifest: Any) -> dict[str, Any]:
        return {
            "status": oracle_status,
            "runner": "native",
            "tier": "native_run",
            "stdout_signature": "matched" if oracle_status == "pass" else "not_run",
            "errno_signature": "not_run",
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
            "poc": [{"case_id": "poc", "kind": "poc"}],
            "regression": [{"case_id": "reg", "kind": "regression"}],
            "limitations": [] if oracle_status == "pass" else [f"oracle status={oracle_status}"],
        }

    return {"detect": detect, "abi_check": abi_check, "run_poc": run_poc}


def _selftest_metadata(original: bytes, candidate: bytes, *,
                       scope_va: int = 0x401000, scope_end: int = 0x401100,
                       abi_block: dict[str, Any] | None = None,
                       generator: dict[str, Any] | None = None) -> dict[str, Any]:
    import hashlib

    metadata: dict[str, Any] = {
        "format": "elf",
        "arch": "x86_64",
        "bits": 64,
        "endian": "little",
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "target_scope": {"policy": "target_scoped", "name": "vuln_fn",
                         "va": scope_va, "end": scope_end},
        "abi_block": abi_block if abi_block is not None else {"offset": 32, "size": 8},
        "generator": generator if generator is not None else {
            "generator_id": "repair-generator/1",
            "agent": "deterministic",
            "model": None,
            "run_id": "selftest-run",
        },
    }
    return metadata


def run_selftest() -> dict[str, Any]:
    """Hermetic fail-closed self-test; returns a structured report."""
    fixtures = _selftest_fixtures()
    original = fixtures["original"]
    candidate = fixtures["candidate"]
    actions = fixtures["actions"]
    schema_method = "fallback"
    cases: list[dict[str, Any]] = []

    def run_case(case_id: str, expected_decision: str, expected_exit: int,
                 metadata: dict[str, Any], *,
                 oracle: Any = {"manifest": {"format": "elf", "arch": "x86_64"}},
                 claimed_actions: Any = None, stubs: dict[str, Any] | None = None,
                 generator: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal schema_method
        active = stubs or _selftest_stubs()
        try:
            report = verifier.verify_repair(
                original=original,
                candidate=candidate,
                metadata=metadata,
                oracle=oracle,
                generator=generator,
                claimed_actions=claimed_actions if claimed_actions is not None else actions,
                detect=active["detect"],
                abi_check=active["abi_check"],
                run_poc=active["run_poc"],
            )
        except verifier.UnsupportedVerificationTarget as exc:
            cases.append({"id": case_id, "expected_decision": expected_decision,
                          "actual_decision": "usage-error", "exit_code": 2,
                          "schema_ok": True, "ok": expected_exit == 2,
                          "detail": str(exc)})
            return cases[-1]
        validation = verifier.validate_verification_report(report)
        schema_method = validation["method"]
        actual_exit = _exit_for_decision(report["decision"])
        case = {
            "id": case_id,
            "expected_decision": expected_decision,
            "actual_decision": report["decision"],
            "exit_code": actual_exit,
            "schema_ok": validation["ok"],
            "ok": report["decision"] == expected_decision
                  and actual_exit == expected_exit
                  and validation["ok"],
            "report_sha256": report["report_sha256"],
        }
        cases.append(case)
        return case

    # 1. valid independent verification -> verified / exit 0
    base_metadata = _selftest_metadata(original, candidate)
    run_case("valid-independent", "verified", 0, base_metadata)

    # 2. identity tamper: metadata sha does not match the bytes -> rejected
    tampered = _selftest_metadata(original, candidate)
    tampered["original_sha256"] = "0" * 64
    run_case("identity-tamper", "rejected", 1, tampered)

    # 3. unchanged candidate -> rejected
    unchanged_metadata = _selftest_metadata(original, original)
    run_case("unchanged-candidate", "rejected", 1, unchanged_metadata,
             claimed_actions=[])

    # 4. claimed action mismatch -> rejected
    bad_claim = [{"offset": 0, "size": 8, "before_hex": "00" * 8, "after_hex": "11" * 8}]
    run_case("claimed-action-mismatch", "rejected", 1, base_metadata,
             claimed_actions=bad_claim)

    # 5. scope escape -> rejected
    escaping = _selftest_metadata(original, candidate, scope_va=0x500000, scope_end=0x500100)
    run_case("scope-escape", "rejected", 1, escaping)

    # 6. generator-only evidence (no oracle) -> rejected
    run_case("generator-only-evidence", "rejected", 1, base_metadata, oracle=None)

    # 7. generator verdict present but ignored; still rejected without oracle
    verdict_generator = {"generator_id": "repair-generator/1", "verified": True,
                         "decision": "verified", "agent": "deterministic"}
    run_case("generator-verdict-ignored", "rejected", 1, base_metadata,
             oracle=None, generator=verdict_generator)

    # 8. oracle unavailable -> not_run
    run_case("oracle-unavailable", "not_run", 2, base_metadata,
             stubs=_selftest_stubs(oracle_status="unavailable"))

    # 9. ABI failure -> rejected
    run_case("abi-failure", "rejected", 1, base_metadata,
             stubs=_selftest_stubs(abi_ok=False))

    # 10. oracle differential failure -> rejected
    run_case("oracle-failure", "rejected", 1, base_metadata,
             stubs=_selftest_stubs(oracle_status="fail"))

    # 11. determinism: same input -> identical report sha (and schema valid)
    first = verifier.verify_repair(
        original=original, candidate=candidate, metadata=_selftest_metadata(original, candidate),
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}}, claimed_actions=actions,
        detect=_selftest_stubs()["detect"], abi_check=_selftest_stubs()["abi_check"],
        run_poc=_selftest_stubs()["run_poc"],
    )
    second = verifier.verify_repair(
        original=original, candidate=candidate, metadata=_selftest_metadata(original, candidate),
        oracle={"manifest": {"format": "elf", "arch": "x86_64"}}, claimed_actions=actions,
        detect=_selftest_stubs()["detect"], abi_check=_selftest_stubs()["abi_check"],
        run_poc=_selftest_stubs()["run_poc"],
    )
    validation = verifier.validate_verification_report(first)
    schema_method = validation["method"]
    cases.append({
        "id": "deterministic-report-sha",
        "expected_decision": "verified",
        "actual_decision": first["decision"],
        "exit_code": _exit_for_decision(first["decision"]),
        "schema_ok": validation["ok"],
        "ok": first["report_sha256"] == second["report_sha256"]
              and first["decision"] == "verified" and validation["ok"],
        "report_sha256": first["report_sha256"],
    })

    ok = all(case["ok"] for case in cases)
    return {
        "schema_version": 1,
        "kind": "independent_verifier_selftest",
        "verifier_id": verifier.VERIFIER_ID,
        "schema_validation_method": schema_method,
        "ok": ok,
        "case_count": len(cases),
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently verify one repair candidate (never trusts the generator).",
    )
    parser.add_argument("--original", type=Path, help="original binary path")
    parser.add_argument("--candidate", type=Path, help="candidate binary path")
    parser.add_argument("--metadata", type=Path, help="target/generator metadata JSON path")
    parser.add_argument("--poc", type=Path, default=None,
                        help="external PoC manifest path (independent oracle)")
    parser.add_argument("--selftest", action="store_true",
                        help="run the hermetic fail-closed self-test and exit")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    if args.selftest:
        payload = run_selftest()
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
        else:
            print("verify-repair selftest: {result} cases={cases} schema={method}".format(
                result="PASS" if payload["ok"] else "FAIL",
                cases=payload["case_count"],
                method=payload["schema_validation_method"],
            ))
            for case in payload["cases"]:
                status = "ok" if case["ok"] else "FAIL"
                print(f"  {status:<4} {case['id']}: expected={case['expected_decision']} "
                      f"actual={case['actual_decision']} exit={case['exit_code']} "
                      f"schema_ok={case['schema_ok']}")
        return 0 if payload["ok"] else 1

    missing = [
        flag for flag, value in (("--original", args.original),
                                 ("--candidate", args.candidate),
                                 ("--metadata", args.metadata))
        if value is None
    ]
    if missing:
        if args.json:
            print(json.dumps({"ok": False, "error": f"missing required option(s): {missing}"}))
        else:
            print(f"verify-repair: usage error: missing required option(s): {missing}", file=sys.stderr)
        return 2
    try:
        original = args.original.read_bytes()
        candidate = args.candidate.read_bytes()
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        if args.json:
            print(json.dumps({"ok": False, "error": message}))
        else:
            print(f"verify-repair: cannot read inputs: {message}", file=sys.stderr)
        return 2
    if not isinstance(metadata, dict):
        if args.json:
            print(json.dumps({"ok": False, "error": "metadata must be a JSON object"}))
        else:
            print("verify-repair: metadata must be a JSON object", file=sys.stderr)
        return 2

    oracle: Any = args.poc if args.poc is not None else None
    try:
        report = verifier.verify_repair(
            original=original, candidate=candidate, metadata=metadata, oracle=oracle,
        )
    except verifier.UnsupportedVerificationTarget as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"verify-repair: unsupported target: {exc}", file=sys.stderr)
        return 2
    validation = verifier.validate_verification_report(report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(
            "verify-repair: decision={decision} verifier={verifier} "
            "independence_ok={independence} checks={checks} schema={schema}".format(
                decision=report["decision"],
                verifier=report["verifier"]["verifier_id"],
                independence=report["independence"]["ok"],
                checks=len(report["checks"]),
                schema="ok" if validation["ok"] else "INVALID",
            )
        )
        for check in report["checks"]:
            print(f"  {check['status'].upper():<7} {check['id']}: {check['detail']}")
        for limitation in report["limitations"]:
            print(f"  LIMIT   {limitation}")
    if not validation["ok"]:
        print("verify-repair: report failed schema validation: " + "; ".join(validation["violations"]),
              file=sys.stderr)
        return 1
    return _exit_for_decision(report["decision"])


if __name__ == "__main__":
    sys.exit(main())
