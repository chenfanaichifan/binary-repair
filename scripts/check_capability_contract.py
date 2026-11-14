#!/usr/bin/env python3
"""Capability-contract checker.

Every declared repair cell must have a runtime capability contract consistent
with what this host can actually measure:

* the contract carries the full field set (declared/measured tier, PoC and
  emulated availability, reason, source);
* ``measured_tier`` is one of the cell's declared runtime tiers, or the
  contract states a non-empty reason for the mismatch (a declaration is never
  silently turned into an availability claim);
* an unavailable capability keeps explicit ``not_run`` semantics: it reports
  ``available=False``, no PoC/emulated evidence, a measured tier of
  ``unavailable`` and a non-empty reason;
* negative platform checks (PE external PoC, 32-bit Mach-O, and Mach-O/x86_64
  on an arm64 macOS host = function-level Rosetta only).

``--json`` prints ``{ok, cells, violations, ...}``; exit code is 0 iff ok.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT_FIELDS = (
    "declared_tier",
    "measured_tier",
    "poc_available",
    "emulated_available",
    "available",
    "reason",
    "source",
)
RUNNABLE_TIERS = ("native_run", "emulated_run")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def current_host() -> dict[str, str]:
    """Real host identity (never simulated by the checker itself)."""
    return {"platform": sys.platform, "machine": platform.machine()}


def _call_contract(contract_fn: Callable[..., dict[str, Any]],
                   container: str, arch: str,
                   host: Mapping[str, Any] | None) -> dict[str, Any]:
    try:
        if host is not None:
            return _as_dict(contract_fn(container, arch, host=host))
        return _as_dict(contract_fn(container, arch))
    except TypeError:
        # Test doubles may not accept the host keyword; any other exception is
        # the caller's to report as a fail-closed observation.
        return _as_dict(contract_fn(container, arch))


def _safe_contract(contract_fn: Callable[..., dict[str, Any]],
                   container: str, arch: str,
                   host: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
    try:
        return _call_contract(contract_fn, container, arch, host), ""
    except Exception as exc:  # noqa: BLE001 - reported as a failed check
        return {}, f"{type(exc).__name__}: {exc}"


def _cell_check(cell: Any, contract: dict[str, Any]) -> list[str]:
    key = f"{cell.container}/{cell.arch}"
    violations: list[str] = []
    missing = [field for field in CONTRACT_FIELDS if field not in contract]
    if missing:
        violations.append(f"{key}: contract missing fields {missing}")
        return violations
    declared_tiers = tuple(str(item) for item in _as_list(cell.runtime_tiers))
    declared = str(contract.get("declared_tier", ""))
    measured = str(contract.get("measured_tier", ""))
    reason = str(contract.get("reason", "") or "").strip()
    available = bool(contract.get("available"))
    poc_available = bool(contract.get("poc_available"))
    emulated_available = bool(contract.get("emulated_available"))
    if declared != "unavailable" and declared not in declared_tiers:
        violations.append(
            f"{key}: contract declares {declared!r} but the repair matrix "
            f"declares {declared_tiers}")
    if measured not in declared_tiers:
        if not reason:
            violations.append(
                f"{key}: measured_tier {measured!r} is not a declared runtime "
                f"tier {declared_tiers} and the contract has no reason")
    elif measured != declared and not reason:
        violations.append(
            f"{key}: measured_tier {measured!r} differs from declared "
            f"{declared!r} without an explicit reason")
    if not available:
        not_run_ok = (
            measured == "unavailable"
            and not poc_available
            and not emulated_available
            and reason
        )
        if not not_run_ok:
            violations.append(
                f"{key}: unavailable capability does not keep not_run "
                f"semantics (measured={measured!r} poc={poc_available} "
                f"emulated={emulated_available} reason={reason!r})")
    else:
        if measured not in RUNNABLE_TIERS:
            violations.append(
                f"{key}: capability is available but measured tier {measured!r} "
                "is not runnable evidence")
        if not str(contract.get("source", "") or "").strip():
            violations.append(
                f"{key}: available capability has no measurement source")
    return violations


def _negative_checks(contract_fn: Callable[..., dict[str, Any]],
                     host: Mapping[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    platform_name = str(host.get("platform", ""))
    machine = str(host.get("machine", ""))

    def _record(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "ok": ok, "detail": detail})

    def _contract_or_fail(container: str, arch: str,
                          check_id: str) -> dict[str, Any]:
        contract, error = _safe_contract(contract_fn, container, arch, host)
        if error:
            _record(check_id, False, f"contract raised {error}")
        return contract

    # 1. PE external PoC must never be available (emulated only).
    for arch in ("i386", "x86_64", "arm64"):
        check_id = f"pe/{arch}-external-poc-unavailable"
        contract = _contract_or_fail("pe", arch, check_id)
        if not contract:
            continue
        poc = bool(contract.get("poc_available"))
        reason = str(contract.get("reason", "") or "").strip()
        _record(
            check_id, not poc and bool(reason),
            f"poc_available={poc} reason={'yes' if reason else 'missing'}",
        )

    # 2. 32-bit Mach-O has no runtime evidence at all.
    contract = _contract_or_fail("macho", "i386", "macho/i386-unavailable")
    if not contract:
        contract = {}
    reason = str(contract.get("reason", "") or "").strip()
    ok = (
        str(contract.get("declared_tier", "")) == "unavailable"
        and bool(contract.get("available")) is False
        and bool(contract.get("poc_available")) is False
        and bool(reason)
    )
    if contract:
        _record("macho/i386-unavailable",
                ok,
                f"declared={contract.get('declared_tier')!r} "
                f"available={contract.get('available')} reason="
                f"{'yes' if reason else 'missing'}")

    # 3. Mach-O/x86_64 on an arm64 macOS host: function-level Rosetta only.
    contract = _contract_or_fail(
        "macho", "x86_64", "macho/x86_64-platform-semantics")
    reason = str(contract.get("reason", "") or "").strip()
    if platform_name == "darwin" and machine == "arm64":
        ok = (
            str(contract.get("measured_tier", "")) == "emulated_run"
            and bool(contract.get("emulated_available")) is True
            and bool(contract.get("poc_available")) is False
            and bool(contract.get("available")) is True
            and bool(reason)
        )
        detail = (
            "arm64 macOS host must report function-level emulated_run only: "
            f"measured={contract.get('measured_tier')!r} "
            f"emulated={contract.get('emulated_available')} "
            f"poc={contract.get('poc_available')}")
    else:
        # On other hosts native Mach-O/x86_64 must be honestly unavailable (or
        # at most emulated) with an explicit reason and no PoC claim.
        measured = str(contract.get("measured_tier", ""))
        ok = (
            not bool(contract.get("poc_available"))
            and bool(reason)
            and (measured == "unavailable"
                 or (measured == "emulated_run"
                     and bool(contract.get("available"))))
        )
        detail = (
            f"non-arm64 host: measured={measured!r} "
            f"available={contract.get('available')} poc="
            f"{contract.get('poc_available')} reason="
            f"{'yes' if reason else 'missing'}")
    if contract:
        _record("macho/x86_64-platform-semantics", ok, detail)
    return checks


def evaluate_contract(
        contract_fn: Callable[..., dict[str, Any]] | None = None,
        host: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate every REPAIR_CELL against the runtime capability contract."""
    from app.services.repair_matrix import REPAIR_CELLS
    from app.services.runtime import capabilities

    fn = contract_fn or capabilities.contract
    host_info = dict(host) if host is not None else current_host()
    violations: list[str] = []
    cells_out: list[dict[str, Any]] = []
    for cell in REPAIR_CELLS:
        key = f"{cell.container}/{cell.arch}"
        try:
            contract = _call_contract(fn, cell.container, cell.arch, host)
        except Exception as exc:  # noqa: BLE001 - fail closed, never crash
            violations.append(
                f"{key}: capability contract raised "
                f"{type(exc).__name__}: {exc}")
            cells_out.append({
                "cell": key,
                "declared_tiers": [str(item) for item in cell.runtime_tiers],
                "ok": False,
                "violations": [f"contract raised {type(exc).__name__}"],
            })
            continue
        cell_violations = _cell_check(cell, contract)
        violations.extend(cell_violations)
        cells_out.append({
            "cell": key,
            "declared_tiers": [str(item) for item in cell.runtime_tiers],
            "declared_tier": contract.get("declared_tier"),
            "measured_tier": contract.get("measured_tier"),
            "available": contract.get("available"),
            "poc_available": contract.get("poc_available"),
            "emulated_available": contract.get("emulated_available"),
            "reason": contract.get("reason"),
            "source": contract.get("source"),
            "ok": not cell_violations,
            "violations": cell_violations,
        })
    negative_checks = _negative_checks(fn, host_info)
    violations.extend(
        f"negative check {check['id']}: {check['detail']}"
        for check in negative_checks if not check["ok"])
    return {
        "ok": not violations,
        "host": host_info,
        "cells": cells_out,
        "cell_count": len(cells_out),
        "negative_checks": negative_checks,
        "violations": violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="validate every repair-cell runtime capability contract")
    parser.add_argument("--json", action="store_true",
                        help="print the full JSON report")
    args = parser.parse_args(argv)
    report = evaluate_contract()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "capability-contract: ok={ok} host={platform}/{machine} "
            "cells={cells} negative_checks={negative} violations={violations}"
            .format(
                ok=report["ok"],
                platform=report["host"].get("platform"),
                machine=report["host"].get("machine"),
                cells=report["cell_count"],
                negative=len(report["negative_checks"]),
                violations=len(report["violations"]),
            )
        )
        for violation in report["violations"]:
            print(f"CONTRACT-VIOLATION: {violation}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
