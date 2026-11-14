"""Measured runtime capability probe tests (no VM or network required)."""
from __future__ import annotations

import hashlib
import json
import platform
import sys

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
