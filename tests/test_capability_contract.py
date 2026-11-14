"""Tests for the capability-contract checker."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import check_capability_contract as checker  # noqa: E402
from app.services.repair_matrix import REPAIR_CELLS  # noqa: E402
from app.services.runtime import capabilities  # noqa: E402


def _fake_contract(**overrides: object) -> dict:
    contract = {
        "declared_tier": "emulated_run",
        "measured_tier": "emulated_run",
        "poc_available": False,
        "emulated_available": True,
        "available": True,
        "reason": "test contract reason",
        "source": "test",
    }
    contract.update(overrides)
    return contract


def test_cli_json_contract_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_capability_contract.py"),
         "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["violations"] == []
    assert payload["cell_count"] == len(REPAIR_CELLS) == len(payload["cells"])
    covered = {f"{cell.container}/{cell.arch}" for cell in REPAIR_CELLS}
    assert {row["cell"] for row in payload["cells"]} == covered
    for row in payload["cells"]:
        assert row["ok"] is True, row
        contract = checker._call_contract(
            capabilities.contract, row["cell"].split("/")[0],
            row["cell"].split("/")[1], None)
        if contract["measured_tier"] not in row["declared_tiers"]:
            assert str(contract["reason"]).strip(), row
        if contract["available"] is False:
            assert str(contract["reason"]).strip(), row


def test_human_cli_exit_code_and_summary_line() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_capability_contract.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "capability-contract: ok=True" in result.stdout


def test_negative_platform_checks() -> None:
    report = checker.evaluate_contract()
    checks = {check["id"]: check for check in report["negative_checks"]}
    for check_id in (
        "pe/i386-external-poc-unavailable",
        "pe/x86_64-external-poc-unavailable",
        "pe/arm64-external-poc-unavailable",
        "macho/i386-unavailable",
        "macho/x86_64-platform-semantics",
    ):
        assert check_id in checks, check_id
        assert checks[check_id]["ok"] is True, checks[check_id]
    host = checker.current_host()
    macho_x86_64 = capabilities.contract("macho", "x86_64")
    if host["platform"] == "darwin" and host["machine"] == "arm64":
        assert macho_x86_64["measured_tier"] == "emulated_run"
        assert macho_x86_64["emulated_available"] is True
        assert macho_x86_64["poc_available"] is False
        assert "function-level" in macho_x86_64["reason"]
    macho_i386 = capabilities.contract("macho", "i386")
    assert macho_i386["declared_tier"] == "unavailable"
    assert macho_i386["available"] is False
    assert str(macho_i386["reason"]).strip()
    for arch in ("i386", "x86_64", "arm64"):
        pe = capabilities.contract("pe", arch)
        assert pe["poc_available"] is False
        assert str(pe["reason"]).strip()


def test_unavailable_contract_without_reason_is_a_violation() -> None:
    def fake_contract(format_name: str, arch: str, **_: object) -> dict:
        return _fake_contract(
            declared_tier="native_run", measured_tier="unavailable",
            poc_available=False, emulated_available=False, available=False,
            reason="", source="none")

    report = checker.evaluate_contract(contract_fn=fake_contract)
    assert report["ok"] is False
    assert any("not_run semantics" in item for item in report["violations"])


def test_measured_tier_mismatch_without_reason_is_a_violation() -> None:
    def fake_contract(format_name: str, arch: str, **_: object) -> dict:
        return _fake_contract(declared_tier="native_run",
                              measured_tier="emulated_run", reason="")

    report = checker.evaluate_contract(contract_fn=fake_contract)
    assert report["ok"] is False
    assert any("not a declared runtime tier" in item
               for item in report["violations"])


def test_missing_contract_fields_and_raised_errors_fail_closed() -> None:
    def missing_fields(format_name: str, arch: str, **_: object) -> dict:
        return {"declared_tier": "native_run"}

    report = checker.evaluate_contract(contract_fn=missing_fields)
    assert report["ok"] is False
    assert any("contract missing fields" in item
               for item in report["violations"])

    def raising(format_name: str, arch: str, **_: object) -> dict:
        raise RuntimeError("probe exploded")

    report = checker.evaluate_contract(contract_fn=raising)
    assert report["ok"] is False
    assert any("contract raised" in item for item in report["violations"])


def test_simulated_linux_host_keeps_macho_unavailable_semantics() -> None:
    report = checker.evaluate_contract(
        host={"platform": "linux", "machine": "x86_64"})
    assert report["ok"] is True, report["violations"]
    assert report["host"] == {"platform": "linux", "machine": "x86_64"}
    by_cell = {row["cell"]: row for row in report["cells"]}
    macho = by_cell["macho/x86_64"]
    assert macho["available"] is False
    assert str(macho["reason"]).strip()
    negative = {check["id"]: check for check in report["negative_checks"]}
    assert negative["macho/x86_64-platform-semantics"]["ok"] is True


def test_monkeypatched_capabilities_contract_is_used(monkeypatch) -> None:
    def fake_contract(format_name: str, arch: str, **_: object) -> dict:
        return _fake_contract(declared_tier="native_run",
                              measured_tier="emulated_run", reason="")

    monkeypatch.setattr(capabilities, "contract", fake_contract)
    report = checker.evaluate_contract()
    assert report["ok"] is False
    assert any("not a declared runtime tier" in item
               for item in report["violations"])


def test_current_host_is_measured() -> None:
    host = checker.current_host()
    assert isinstance(host.get("platform"), str) and host["platform"]
    assert isinstance(host.get("machine"), str)
