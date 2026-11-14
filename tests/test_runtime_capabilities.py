"""Measured runtime capability probe tests (no VM or network required)."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import poc_runner
from app.services import repair_matrix
from app.services.guest_runner import GuestRunner
from app.services.repair_matrix import REPAIR_CELLS, matrix_payload
from app.services.runtime import capabilities, macho_native

_REQUIRED_KEYS = {
    "format", "arch", "available", "tier", "engine", "poc_available",
    "reason", "source",
}
_TIERS = {"native_run", "emulated_run", "unavailable"}
_MACHO_X86_64_ON_ARM64_REASON = "Rosetta"


@pytest.fixture(autouse=True)
def _isolate_capability_cache():
    capabilities.clear_cache()
    yield
    capabilities.clear_cache()


def _assert_schema(result: dict, *, format_name: str, arch: str) -> None:
    assert set(result) == _REQUIRED_KEYS
    assert result["format"] == format_name
    assert result["arch"] == arch
    assert isinstance(result["available"], bool)
    assert result["tier"] in _TIERS
    assert isinstance(result["engine"], str) and result["engine"]
    assert isinstance(result["poc_available"], bool)
    assert isinstance(result["reason"], str)
    assert isinstance(result["source"], str) and result["source"]
    assert str(result).isascii()


def _patch_host(monkeypatch, platform_name: str, machine: str) -> None:
    monkeypatch.setattr(capabilities.sys, "platform", platform_name)
    monkeypatch.setattr(capabilities.platform, "machine", lambda: machine)


def _patch_guest_runner(monkeypatch, runner):
    monkeypatch.setattr(capabilities.guest_runner, "find_guest_runner", lambda arch: runner)


def _patch_macho_engine(monkeypatch, ready: bool) -> None:
    monkeypatch.setattr(capabilities, "_macho_engine_ready", lambda: ready)


# --------------------------------------------------------------------------- ELF


def test_elf_native_on_matching_linux_host(monkeypatch):
    _patch_host(monkeypatch, "linux", "x86_64")
    _patch_guest_runner(monkeypatch, GuestRunner(kind="native", tool="", tier="native_run"))
    result = capabilities.probe("elf", "x86_64")
    _assert_schema(result, format_name="elf", arch="x86_64")
    assert result["available"] is True
    assert result["tier"] == "native_run"
    assert result["poc_available"] is True
    assert result["engine"] == "native"
    assert result["source"] == "guest_runner"
    assert "native" in result["reason"]


def test_elf_emulated_on_cross_arch_linux_host(monkeypatch):
    _patch_host(monkeypatch, "linux", "arm64")
    _patch_guest_runner(
        monkeypatch,
        GuestRunner(kind="qemu", tool="/usr/bin/qemu-x86_64", tier="emulated_run"),
    )
    result = capabilities.probe("elf", "x86_64")
    _assert_schema(result, format_name="elf", arch="x86_64")
    assert result["available"] is True
    assert result["tier"] == "emulated_run"
    assert result["poc_available"] is True
    assert result["engine"] == "qemu-x86_64"


def test_elf_lima_runner_is_emulated(monkeypatch):
    _patch_host(monkeypatch, "darwin", "arm64")
    _patch_guest_runner(
        monkeypatch,
        GuestRunner(kind="lima", tool="/opt/homebrew/bin/limactl",
                    tier="emulated_run", instance="binaryrepair"),
    )
    result = capabilities.probe("elf", "x86_64")
    _assert_schema(result, format_name="elf", arch="x86_64")
    assert result["available"] is True
    assert result["tier"] == "emulated_run"
    assert result["engine"] == "limactl"
    assert result["poc_available"] is True


def test_elf_unavailable_without_guest_runner(monkeypatch):
    _patch_host(monkeypatch, "darwin", "arm64")
    _patch_guest_runner(monkeypatch, None)
    result = capabilities.probe("elf", "x86_64")
    _assert_schema(result, format_name="elf", arch="x86_64")
    assert result["available"] is False
    assert result["tier"] == "unavailable"
    assert result["poc_available"] is False
    assert "no native/qemu/Lima" in result["reason"]


def test_elf_probe_never_raises_on_runner_error(monkeypatch):
    _patch_host(monkeypatch, "linux", "x86_64")

    def _boom(arch):  # noqa: ANN001
        raise RuntimeError("runner probe exploded")

    monkeypatch.setattr(capabilities.guest_runner, "find_guest_runner", _boom)
    result = capabilities.probe("elf", "x86_64")
    assert result["available"] is False and result["tier"] == "unavailable"
    assert "guest runner probe failed" in result["reason"]


# ------------------------------------------------------------------------- Mach-O


def test_macho_native_on_matching_macos_host(monkeypatch):
    _patch_macho_engine(monkeypatch, True)
    result = capabilities.probe(
        "macho", "x86_64", host={"platform": "darwin", "machine": "x86_64"},
    )
    _assert_schema(result, format_name="macho", arch="x86_64")
    assert result["available"] is True
    assert result["tier"] == "native_run"
    assert result["poc_available"] is True
    assert result["engine"] == "macho-native"
    assert result["source"] == "macho_native"


def test_macho_x86_64_on_arm64_host_is_emulated_and_no_external_poc(monkeypatch):
    _patch_macho_engine(monkeypatch, True)
    result = capabilities.probe(
        "macho", "x86_64", host={"platform": "darwin", "machine": "arm64"},
    )
    _assert_schema(result, format_name="macho", arch="x86_64")
    assert result["available"] is True
    assert result["tier"] == "emulated_run"
    assert result["poc_available"] is False
    assert _MACHO_X86_64_ON_ARM64_REASON in result["reason"]
    assert "unavailable" in result["reason"]


def test_macho_arm64_on_arm64_host_is_native(monkeypatch):
    _patch_macho_engine(monkeypatch, True)
    result = capabilities.probe(
        "macho", "arm64", host={"platform": "darwin", "machine": "arm64"},
    )
    assert result["tier"] == "native_run"
    assert result["poc_available"] is True


def test_macho_arm64_on_x86_64_host_unavailable(monkeypatch):
    _patch_macho_engine(monkeypatch, True)
    result = capabilities.probe(
        "macho", "arm64", host={"platform": "darwin", "machine": "x86_64"},
    )
    _assert_schema(result, format_name="macho", arch="arm64")
    assert result["available"] is False
    assert result["tier"] == "unavailable"
    assert result["poc_available"] is False
    assert "no native or cross-arch" in result["reason"]


def test_macho_on_non_macos_host_unavailable(monkeypatch):
    _patch_macho_engine(monkeypatch, False)
    result = capabilities.probe(
        "macho", "x86_64", host={"platform": "linux", "machine": "x86_64"},
    )
    assert result["available"] is False
    assert "macOS host" in result["reason"]


def test_macho_requires_codesign_engine(monkeypatch):
    _patch_macho_engine(monkeypatch, False)
    result = capabilities.probe(
        "macho", "x86_64", host={"platform": "darwin", "machine": "x86_64"},
    )
    assert result["available"] is False
    assert "codesign" in result["reason"]


def test_macho_32bit_is_not_claimed_as_emulated(monkeypatch):
    # Unicorn has no Mach-O mapping strategy, so a 32-bit Mach-O cannot be
    # reported as ``emulated_run`` without fabricating capability.
    _patch_macho_engine(monkeypatch, True)
    result = capabilities.probe(
        "macho", "i386", host={"platform": "darwin", "machine": "arm64"},
    )
    assert result["available"] is False
    assert result["tier"] == "unavailable"
    assert result["poc_available"] is False


# ----------------------------------------------------------------------------- PE


@pytest.mark.parametrize("arch", ["x86_64", "arm64", "i386"])
def test_pe_is_emulated_unicorn_without_external_poc(arch):
    result = capabilities.probe(
        "pe", arch, host={"platform": "linux", "machine": "x86_64"},
    )
    _assert_schema(result, format_name="pe", arch=arch)
    assert result["available"] is True
    assert result["tier"] == "emulated_run"
    assert result["poc_available"] is False
    assert result["engine"] == f"unicorn-{arch}"
    assert result["source"] == "unicorn"
    assert "external PoC runner unavailable" in result["reason"]


def test_pe_unsupported_arch_unavailable():
    result = capabilities.probe(
        "pe", "mips", host={"platform": "linux", "machine": "x86_64"},
    )
    assert result["available"] is False
    assert result["tier"] == "unavailable"
    assert "no Unicorn emulated path" in result["reason"]


def test_unknown_format_unavailable():
    result = capabilities.probe(
        "dos", "x86_64", host={"platform": "linux", "machine": "x86_64"},
    )
    assert result["available"] is False
    assert result["tier"] == "unavailable"
    assert result["engine"] == "none"
    assert result["source"] == "none"


def test_format_and_arch_aliases_normalized():
    result = capabilities.probe(
        "mach-o", "amd64", host={"platform": "darwin", "machine": "arm64"},
    )
    assert result["format"] == "macho"
    assert result["arch"] == "x86_64"


def test_probe_fails_closed_on_measurement_error(monkeypatch):
    def _boom(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("measurement exploded")

    monkeypatch.setattr(capabilities, "_probe_measured", _boom)
    result = capabilities.probe("elf", "x86_64")
    assert result["available"] is False
    assert result["tier"] == "unavailable"
    assert "capability probe failed" in result["reason"]


# -------------------------------------------------------------------- cache policy


def test_host_override_does_not_pollute_production_cache(monkeypatch):
    _patch_host(monkeypatch, "linux", "x86_64")
    _patch_guest_runner(monkeypatch, GuestRunner(kind="native", tool="", tier="native_run"))
    production = capabilities.probe("elf", "x86_64")
    assert production["tier"] == "native_run"

    overridden = capabilities.probe(
        "elf", "x86_64", host={"platform": "linux", "machine": "arm64"},
    )
    assert overridden["tier"] == "emulated_run"

    assert capabilities.probe("elf", "x86_64") == production
    assert capabilities.probe("elf", "x86_64") is not production


def test_default_probe_is_cached_and_resettable(monkeypatch):
    _patch_host(monkeypatch, "linux", "x86_64")
    _patch_guest_runner(monkeypatch, GuestRunner(kind="native", tool="", tier="native_run"))
    first = capabilities.probe("elf", "x86_64")
    second = capabilities.probe("elf", "x86_64")
    assert first == second
    info = capabilities._probe_cached.cache_info()
    assert info.hits >= 1
    first["tier"] = "mutated"  # returned dicts are copies of the cache entry
    assert capabilities.probe("elf", "x86_64")["tier"] == "native_run"
    capabilities.clear_cache()
    assert capabilities._probe_cached.cache_info().currsize == 0


# --------------------------------------------------- macho_native capability API


def test_macho_native_supports_arch():
    assert macho_native.supports_arch("x86_64", host_machine="arm64") is True
    assert macho_native.supports_arch("arm64", host_machine="arm64") is True
    assert macho_native.supports_arch("x86_64", host_machine="x86_64") is True
    assert macho_native.supports_arch("arm64", host_machine="x86_64") is False
    assert macho_native.supports_arch("i386", host_machine="arm64") is False
    assert macho_native.supports_arch("x86_64", host_machine="") is False


# ------------------------------------------------- poc_runner selector integration


def test_select_runner_macho_x86_64_on_arm64_host_is_none(monkeypatch):
    # The simulated macOS host needs the Mach-O engine available; on a Linux CI
    # runner the real engine probe is false and would otherwise return
    # unavailable before the Rosetta cross-arch branch.
    monkeypatch.setattr(capabilities, "_macho_engine_ready", lambda: True)
    capability = capabilities.probe(
        "macho", "x86_64", host={"platform": "darwin", "machine": "arm64"},
    )
    assert capability["tier"] == "emulated_run" and capability["poc_available"] is False
    monkeypatch.setattr(poc_runner.capabilities, "probe", lambda *a, **k: capability)
    assert poc_runner._select_runner("macho", "x86_64") is None


def test_select_runner_macho_native_returns_native_runner(monkeypatch):
    capability = {
        "format": "macho", "arch": "x86_64", "available": True,
        "tier": "native_run", "engine": "macho-native", "poc_available": True,
        "reason": "native", "source": "macho_native",
    }
    monkeypatch.setattr(poc_runner.capabilities, "probe", lambda *a, **k: capability)
    runner = poc_runner._select_runner("macho", "x86_64")
    assert runner == GuestRunner(kind="native", tool="", tier="native_run")


def test_select_runner_pe_is_none(monkeypatch):
    capability = {
        "format": "pe", "arch": "x86_64", "available": True,
        "tier": "emulated_run", "engine": "unicorn-x86_64",
        "poc_available": False, "reason": "unicorn only", "source": "unicorn",
    }
    monkeypatch.setattr(poc_runner.capabilities, "probe", lambda *a, **k: capability)
    assert poc_runner._select_runner("pe", "x86_64") is None


def test_select_runner_elf_uses_live_guest_runner(monkeypatch):
    live = GuestRunner(kind="native", tool="", tier="native_run")
    monkeypatch.setattr(poc_runner, "find_guest_runner", lambda arch: live)
    capability = {
        "format": "elf", "arch": "x86_64", "available": True,
        "tier": "native_run", "engine": "native", "poc_available": True,
        "reason": "native", "source": "guest_runner",
    }
    monkeypatch.setattr(poc_runner.capabilities, "probe", lambda *a, **k: capability)
    assert poc_runner._select_runner("elf", "x86_64") == live


def test_run_poc_macho_unavailable_surfaces_capability_reason(monkeypatch):
    reason = (
        "host arm64 cannot execute macho/x86_64 natively; only the Rosetta "
        "cross-arch path provides function-level evidence, and the external PoC "
        "runner is unavailable"
    )
    capability = {
        "format": "macho", "arch": "x86_64", "available": True,
        "tier": "emulated_run", "engine": "macho-native",
        "poc_available": False, "reason": reason, "source": "macho_native",
    }
    monkeypatch.setattr(poc_runner.capabilities, "probe", lambda *a, **k: capability)
    original = b"macho-bytes"
    manifest = {
        "schema_version": 1,
        "fixture_sha256": hashlib.sha256(original).hexdigest(),
        "format": "macho",
        "arch": "x86_64",
        "target": "fixture",
        "poc": [{"id": "poc", "argv": [], "original": {"crashed": True}}],
        "regression": [],
    }
    evidence = poc_runner.run_poc(original, original, manifest)
    assert evidence.status == "unavailable"
    assert evidence.runner == "" and evidence.tier == ""
    assert evidence.cases == [] and evidence.regression == []
    assert any("external PoC unavailable:" in item for item in evidence.limitations)
    assert any(reason in item for item in evidence.limitations)


# --------------------------------------------------------- repair-matrix payload


def test_matrix_payload_contains_measured_runtime_capabilities():
    payload = matrix_payload()
    assert str(payload).isascii()
    measured = payload["runtime_capabilities"]
    assert isinstance(measured, dict)
    assert set(measured) == {cell.key for cell in REPAIR_CELLS}
    required = {"cell_key", "format", "arch", "available", "tier",
                "engine", "poc_available", "reason", "source"}
    for cell in REPAIR_CELLS:
        entry = measured[cell.key]
        assert set(entry) == required
        assert entry["cell_key"] == cell.key
        assert entry["format"] == cell.container
        assert entry["arch"] == cell.arch
        assert isinstance(entry["available"], bool)
        assert entry["tier"] in _TIERS
        assert isinstance(entry["poc_available"], bool)
        assert isinstance(entry["reason"], str)
        assert isinstance(entry["engine"], str) and entry["engine"]
        assert isinstance(entry["source"], str) and entry["source"]
        # measured next to declared: the declarations stay untouched
        assert list(cell.runtime_tiers) <= list(payload["runtime_tiers"])


def test_matrix_measured_capability_matches_probe():
    payload = matrix_payload()
    for cell in REPAIR_CELLS:
        probe = capabilities.probe(cell.container, cell.arch)
        entry = payload["runtime_capabilities"][cell.key]
        for key in ("format", "arch", "available", "tier", "engine",
                    "poc_available", "reason", "source"):
            assert entry[key] == probe[key], (cell.key, key)


def test_matrix_payload_fail_safe_when_probe_raises(monkeypatch):
    def _boom(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(
        "app.services.runtime.capabilities.probe", _boom,
    )
    payload = matrix_payload()
    measured = payload["runtime_capabilities"]
    assert set(measured) == {cell.key for cell in REPAIR_CELLS}
    for entry in measured.values():
        assert entry["available"] is False
        assert entry["tier"] == "unavailable"
        assert entry["poc_available"] is False
        assert "capability probe failed" in entry["reason"]


def test_declared_tiers_unchanged():
    payload = matrix_payload()
    assert payload["runtime_tiers"] == dict(repair_matrix.RUNTIME_TIERS)


@pytest.mark.skipif(
    not (sys.platform == "darwin" and platform.machine().lower() in {"arm64", "aarch64"}),
    reason="the arm64 macOS host is the measured host",
)
def test_arm64_macos_measures_macho_x86_64_as_emulated_not_declared_native():
    payload = matrix_payload()
    measured = payload["runtime_capabilities"]["macho/x86_64/64/little"]
    assert measured["tier"] == "emulated_run"
    assert measured["poc_available"] is False
    # the declared cell still says native_run; the payload exposes both honestly
    declared = next(
        cell.runtime_tiers for cell in REPAIR_CELLS
        if cell.key == "macho/x86_64/64/little"
    )
    assert "native_run" in declared
    assert measured["tier"] not in declared


# --------------------------------------------------- unified capability contract


def test_contract_fields_are_the_documented_single_source():
    result = capabilities.contract("elf", "x86_64")
    assert set(result) == set(capabilities.CONTRACT_FIELDS)
    assert capabilities.CONTRACT_FIELDS == (
        "declared_tier", "measured_tier", "poc_available",
        "emulated_available", "available", "reason", "source",
    )
    assert result["declared_tier"] in _TIERS | {"unavailable"}
    assert result["measured_tier"] in _TIERS
    assert isinstance(result["available"], bool)
    assert isinstance(result["poc_available"], bool)
    assert isinstance(result["emulated_available"], bool)
    assert str(result["reason"]).strip()
    assert isinstance(result["source"], str) and result["source"]
    assert str(result).isascii()


def test_contract_derives_only_from_probe():
    for fmt, arch in (("elf", "x86_64"), ("pe", "x86_64"), ("macho", "x86_64"),
                      ("macho", "arm64"), ("macho", "i386")):
        probe = capabilities.probe(fmt, arch)
        contract = capabilities.contract(fmt, arch)
        assert contract["measured_tier"] == probe["tier"], (fmt, arch)
        assert contract["available"] == probe["available"], (fmt, arch)
        assert contract["poc_available"] == probe["poc_available"], (fmt, arch)
        assert contract["source"] == probe["source"], (fmt, arch)
        assert contract["emulated_available"] == (
            probe["available"] and probe["tier"] == "emulated_run"
        ), (fmt, arch)


def test_contract_declared_tier_comes_from_the_matrix_cell():
    # The ELF x86_64 cell declares both native_run (Linux x86_64 host) and
    # emulated_run (guest/Unicorn); declared_tier exposes the first declared
    # tier, while contract() reports the measured tier and any declared-vs-
    # measured gap with an explicit reason.
    assert capabilities.declared_tier("elf", "x86_64") in {"native_run", "emulated_run"}
    assert capabilities.declared_tier("pe", "x86_64") == "emulated_run"
    assert capabilities.declared_tier("macho", "x86_64") == "native_run"
    assert capabilities.declared_tier("macho", "arm64") == "native_run"
    # 32-bit Mach-O is outside the matrix: no declared tier may be invented
    assert capabilities.declared_tier("macho", "i386") == "unavailable"
    assert capabilities.declared_tier("dos", "x86_64") == "unavailable"


def test_contract_macho_x86_64_on_arm64_is_function_level_only(monkeypatch):
    _patch_macho_engine(monkeypatch, True)
    contract = capabilities.contract(
        "macho", "x86_64", host={"platform": "darwin", "machine": "arm64"},
    )
    assert contract["declared_tier"] == "native_run"
    assert contract["measured_tier"] == "emulated_run"
    assert contract["available"] is True
    assert contract["emulated_available"] is True
    assert contract["poc_available"] is False
    assert "function-level" in contract["reason"]
    assert "external PoC is unavailable" in contract["reason"]
    assert "declared native_run is unavailable" in contract["reason"]
    assert contract["source"] == "macho_native"


def test_contract_macho_native_on_matching_host(monkeypatch):
    _patch_macho_engine(monkeypatch, True)
    contract = capabilities.contract(
        "macho", "x86_64", host={"platform": "darwin", "machine": "x86_64"},
    )
    assert contract["declared_tier"] == "native_run"
    assert contract["measured_tier"] == "native_run"
    assert contract["poc_available"] is True
    assert contract["emulated_available"] is False


def test_contract_pe_emulated_but_external_poc_unavailable():
    contract = capabilities.contract(
        "pe", "x86_64", host={"platform": "linux", "machine": "x86_64"},
    )
    assert contract["declared_tier"] == "emulated_run"
    assert contract["measured_tier"] == "emulated_run"
    assert contract["available"] is True
    assert contract["emulated_available"] is True
    assert contract["poc_available"] is False
    assert "external PoC" in contract["reason"]


def test_contract_32bit_macho_stays_unavailable(monkeypatch):
    _patch_macho_engine(monkeypatch, True)
    for kwargs in ({}, {"host": {"platform": "darwin", "machine": "arm64"}}):
        contract = capabilities.contract("macho", "i386", **kwargs)
        assert contract["declared_tier"] == "unavailable"
        assert contract["measured_tier"] == "unavailable"
        assert contract["available"] is False
        assert contract["poc_available"] is False
        assert contract["emulated_available"] is False
        assert contract["reason"].strip()
    # No literal emulated_run claim without a Mach-O mapping implementation.
    assert "emulated_run" not in capabilities.contract("macho", "i386")["measured_tier"]


def test_contract_unknown_pair_and_probe_failure_are_unavailable(monkeypatch):
    unknown = capabilities.contract("dos", "x86_64")
    assert unknown["declared_tier"] == "unavailable"
    assert unknown["measured_tier"] == "unavailable"
    assert unknown["reason"].strip()

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("contract probe exploded")

    monkeypatch.setattr(capabilities, "probe", _boom)
    failed = capabilities.contract("elf", "x86_64")
    assert failed["measured_tier"] == "unavailable"
    assert failed["available"] is False
    assert "capability contract failed" in failed["reason"]


def test_contract_never_silently_ignores_a_declared_tier(monkeypatch):
    """Every cell: measured in declared tiers OR an explicit non-empty reason."""

    for cell in REPAIR_CELLS:
        contract = capabilities.contract(cell.container, cell.arch)
        if contract["measured_tier"] in cell.runtime_tiers:
            assert contract["declared_tier"] in cell.runtime_tiers
            continue
        assert contract["reason"].strip(), cell.key
        assert contract["declared_tier"] in contract["reason"], cell.key
        if contract["measured_tier"] == "unavailable":
            assert contract["available"] is False


def test_poc_selector_and_contract_agree(monkeypatch):
    monkeypatch.setattr(poc_runner, "find_guest_runner", lambda arch: None)
    native = {
        "declared_tier": "native_run", "measured_tier": "native_run",
        "poc_available": True, "emulated_available": False, "available": True,
        "reason": "native", "source": "macho_native",
    }
    emulated = {
        "declared_tier": "native_run", "measured_tier": "emulated_run",
        "poc_available": False, "emulated_available": True, "available": True,
        "reason": "rosetta", "source": "macho_native",
    }
    monkeypatch.setattr(poc_runner.capabilities, "contract", lambda *a, **k: native)
    assert poc_runner._select_runner("macho", "x86_64") == GuestRunner(
        kind="native", tool="", tier="native_run",
    )
    monkeypatch.setattr(poc_runner.capabilities, "contract", lambda *a, **k: emulated)
    assert poc_runner._select_runner("macho", "x86_64") is None


def test_probe_and_command_share_the_macho_execution_tier_helper(monkeypatch):
    _patch_macho_engine(monkeypatch, True)

    def tier_emulated(arch, **kwargs):  # noqa: ANN001
        return "emulated_run"

    monkeypatch.setattr(macho_native, "execution_tier", tier_emulated)
    probe = capabilities.probe(
        "macho", "x86_64", host={"platform": "darwin", "machine": "arm64"},
    )
    assert probe["tier"] == "emulated_run" and probe["poc_available"] is False
    assert macho_native._command(Path("/tmp/cand"), "x86_64")[-2:] == [
        "-x86_64", "/tmp/cand",
    ]

    monkeypatch.setattr(
        macho_native, "execution_tier",
        lambda arch, **kwargs: "native_run",
    )
    assert macho_native._command(Path("/tmp/cand"), "x86_64") == ["/tmp/cand"]


def test_native_macho_scheduler_reads_the_shared_execution_tier(monkeypatch):
    monkeypatch.setattr(macho_native, "available", lambda: True)
    monkeypatch.setattr(
        macho_native, "execution_tier",
        lambda arch, **kwargs: "unavailable",
    )
    evidence = macho_native.run(b"candidate", arch="arm64", capacity=16)
    assert evidence.tier == "unavailable"
    assert evidence.verdict == "unavailable"
    assert any("cannot execute" in item for item in evidence.limitations)

    monkeypatch.setattr(
        macho_native, "execution_tier",
        lambda arch, **kwargs: "emulated_run",
    )
    monkeypatch.setattr(macho_native, "_resign", lambda path: None)
    monkeypatch.setattr(
        macho_native.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    evidence = macho_native.run(b"candidate", arch="x86_64", capacity=16)
    assert any("function-level evidence only" in item for item in evidence.limitations)
    assert evidence.verdict == "pass"


# ------------------------------------------- platform-limit negatives (never faked)


def _platform_limit_manifest(fmt: str, arch: str, original: bytes) -> dict:
    return {
        "schema_version": 1,
        "fixture_sha256": hashlib.sha256(original).hexdigest(),
        "format": fmt,
        "arch": arch,
        "target": "fixture",
        "poc": [{"id": "poc", "argv": [], "original": {"crashed": True}}],
        "regression": [],
    }


@pytest.mark.parametrize(
    ("fmt", "arch"),
    [("pe", "x86_64"), ("pe", "arm64"), ("macho", "i386")],
)
def test_platform_limit_external_poc_is_unavailable_not_rejected(fmt, arch):
    """No external PoC on PE/32-bit Mach-O => unavailable, never pass/fail."""

    original = b"original-bytes"
    evidence = poc_runner.run_poc(
        original, original, _platform_limit_manifest(fmt, arch, original),
    )
    assert evidence.status == "unavailable"
    assert evidence.status not in {"pass", "fail"}  # never verified, never rejected
    assert evidence.cases == [] and evidence.regression == []
    assert evidence.runner == "" and evidence.tier == ""
    assert any("external PoC unavailable:" in item for item in evidence.limitations)
    assert any(item.strip() for item in evidence.limitations)


@pytest.mark.skipif(
    not (sys.platform == "darwin" and platform.machine().lower() in {"arm64", "aarch64"}),
    reason="the arm64 macOS host is the measured host",
)
def test_macho_x86_64_external_poc_unavailable_on_arm64_host_never_faked():
    contract = capabilities.contract("macho", "x86_64")
    assert contract["measured_tier"] == "emulated_run"
    assert contract["poc_available"] is False
    assert "function-level" in contract["reason"]

    original = b"original-macho-bytes"
    evidence = poc_runner.run_poc(
        original, original, _platform_limit_manifest("macho", "x86_64", original),
    )
    assert evidence.status == "unavailable"
    assert evidence.status not in {"pass", "fail"}
    assert evidence.cases == [] and evidence.regression == []
    assert any("external PoC unavailable:" in item for item in evidence.limitations)
    assert any("function-level" in item for item in evidence.limitations)
