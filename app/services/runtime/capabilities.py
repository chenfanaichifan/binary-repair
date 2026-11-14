"""Measured runtime capability probe: what can this host actually execute?

The repair matrix *declares* runtime tiers; the benchmark/gate/audit need to know
which of them are **measurable on the current host** for a given
``(format, arch)`` pair.  This module is the single source of that measurement.

It never fabricates availability: a pair is ``available`` only when a concrete
execution path exists (native/qemu/Lima guest runner, native Mach-O execution, or
the function-level Unicorn emulator for PE).  ``poc_available`` is narrower: it
is true only when the *external PoC runner* can execute the target, i.e. a full
CLI process run.  Mach-O/PE function-level evidence therefore reports
``available=True`` with ``poc_available=False``.

Result schema (all keys always present)::

    {
      "format": "elf" | "pe" | "macho" | ...,
      "arch": "x86_64" | "arm64" | "i386" | ...,
      "available": bool,       # can produce execution evidence at all
      "tier": "native_run" | "emulated_run" | "unavailable",
      "engine": "native" | "qemu-<arch>" | "limactl" | "macho-native" |
                "unicorn-<arch>" | "none",
      "poc_available": bool,   # external PoC runner can execute this target
      "reason": str,           # human-readable, ASCII, deterministic
      "source": "guest_runner" | "macho_native" | "unicorn" | "none",
    }

``host`` may override the measured host for tests: ``{"platform": "darwin",
"machine": "arm64"}``.  Explicit-host probes are never cached, so they cannot
pollute the production cache; the default-host probe is cached by
``(format, arch, external_poc, platform, machine, macho_engine_ready)`` and can
be reset with :func:`clear_cache` (e.g. after monkeypatching in tests).
"""
from __future__ import annotations

import copy
import platform
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from app.services import guest_runner
from app.services.runtime import macho_native

TIERS = ("native_run", "emulated_run", "unavailable")

#: Architectures the Unicorn instruction-level path can emulate.  Mirrors the
#: documented support in ``app/services/runtime/emulated.py`` (x86_64 / arm64 /
#: i386) and PE's mapping strategy.  Kept as a declared set here because the
#: emulated module exposes no capability API.
UNICORN_EMULATED_ARCHES = frozenset({"x86_64", "arm64", "i386"})
#: Container formats the Unicorn path can map (``emulated._mappings``: ELF and
#: PE; Mach-O has no mapping strategy and is never claimed as emulated).
UNICORN_EMULATED_FORMATS = frozenset({"elf", "pe"})

_ARCH_ALIASES = {
    "x86_64": "x86_64",
    "x86-64": "x86_64",
    "amd64": "x86_64",
    "x64": "x86_64",
    "arm64": "arm64",
    "aarch64": "arm64",
    "i386": "i386",
    "i486": "i386",
    "i586": "i386",
    "i686": "i386",
    "x86": "i386",
    "ia32": "i386",
}

_FORMAT_ALIASES = {
    "mach-o": "macho",
    "mach_o": "macho",
    "macho": "macho",
    "macho-fat": "macho-fat",
    "machofat": "macho-fat",
    "elf64": "elf",
    "elf32": "elf",
    "elf": "elf",
    "pe": "pe",
    "pe32": "pe",
    "pe32+": "pe",
}


def _normalize_arch(arch: str) -> str:
    value = str(arch or "").strip().lower()
    return _ARCH_ALIASES.get(value, value)


def normalize_format(format_name: str) -> str:
    """Normalize a container format name used by the matrix/containers."""

    value = str(format_name or "").strip().lower()
    return _FORMAT_ALIASES.get(value, value)


def _normalize_platform(platform_name: str) -> str:
    value = str(platform_name or "").strip().lower()
    if value.startswith("darwin") or value in {"macos", "mac", "osx"}:
        return "darwin"
    if value.startswith("linux"):
        return "linux"
    if value.startswith("win"):
        return "win32"
    return value


def _macho_engine_ready() -> bool:
    """Whether the local native Mach-O execution engine can run at all."""

    try:
        return bool(macho_native.available())
    except Exception:  # noqa: BLE001 - a broken probe is "unavailable", not a crash
        return False


def _result(
    format_name: str,
    arch: str,
    *,
    available: bool,
    tier: str,
    engine: str,
    poc_available: bool,
    reason: str,
    source: str,
) -> dict[str, Any]:
    if tier not in TIERS:  # pragma: no cover - internal invariant
        raise ValueError(f"invalid runtime tier {tier!r}")
    return {
        "format": format_name,
        "arch": arch,
        "available": bool(available),
        "tier": tier,
        "engine": engine,
        "poc_available": bool(poc_available),
        "reason": reason,
        "source": source,
    }


def _unavailable(
    format_name: str,
    arch: str,
    reason: str,
    *,
    source: str,
    engine: str = "none",
) -> dict[str, Any]:
    return _result(
        format_name,
        arch,
        available=False,
        tier="unavailable",
        engine=engine,
        poc_available=False,
        reason=reason,
        source=source,
    )


def _elf_native_possible(arch: str, platform_name: str, machine: str) -> bool:
    """Whether a Linux host of *machine* can execute ``elf/<arch>`` directly.

    Mirrors the native branch of ``guest_runner.find_guest_runner`` (x86_64 and
    arm64 only, matching host CPU).  Used for explicit ``host`` overrides so a
    simulated host reports the tier it would actually select; the default probe
    always measures the real guest runner.
    """

    return (
        platform_name == "linux"
        and arch in {"x86_64", "arm64"}
        and arch == machine
    )


def _probe_elf(
    arch: str,
    platform_name: str,
    machine: str,
    *,
    simulated_host: bool = False,
) -> dict[str, Any]:
    try:
        runner = guest_runner.find_guest_runner(arch)
    except Exception as exc:  # noqa: BLE001
        return _unavailable(
            "elf", arch,
            f"guest runner probe failed: {type(exc).__name__}: {exc}",
            source="guest_runner",
        )
    if simulated_host and _elf_native_possible(arch, platform_name, machine):
        # On a simulated Linux host with a matching CPU the native path needs no
        # external tool, so it is deterministically available.
        return _result(
            "elf", arch,
            available=True,
            tier="native_run",
            engine="native",
            poc_available=True,
            reason=f"native Linux host {platform_name}/{machine} executes "
                   f"elf/{arch} directly",
            source="guest_runner",
        )
    if runner is None:
        return _unavailable(
            "elf", arch,
            f"no native/qemu/Lima guest runner can execute elf/{arch} on "
            f"{platform_name}/{machine}",
            source="guest_runner",
        )
    tier = str(getattr(runner, "tier", "") or "")
    if tier not in {"native_run", "emulated_run"}:
        return _unavailable(
            "elf", arch,
            f"guest runner reported an unknown tier {tier!r} for elf/{arch}",
            source="guest_runner",
        )
    kind = str(getattr(runner, "kind", "") or "")
    tool = str(getattr(runner, "tool", "") or "")
    engine = "native" if kind == "native" else (Path(tool).name or kind or "guest")
    if simulated_host:
        # The simulated host is not the native-Linux match (handled above), so
        # the measured runner represents the emulated path on that host.
        tier = "emulated_run"
    return _result(
        "elf", arch,
        available=True,
        tier=tier,
        engine=engine,
        poc_available=True,
        reason=f"{kind or 'guest'} guest runner can execute elf/{arch} on "
               f"{platform_name}/{machine}",
        source="guest_runner",
    )


def _probe_macho(
    arch: str,
    platform_name: str,
    machine: str,
    engine_ready: bool,
) -> dict[str, Any]:
    if platform_name != "darwin":
        return _unavailable(
            "macho", arch,
            f"Mach-O execution requires a macOS host (measured host "
            f"{platform_name or 'unknown'}/{machine or 'unknown'})",
            source="macho_native",
        )
    if not engine_ready:
        return _unavailable(
            "macho", arch,
            "Mach-O execution requires a macOS host with codesign available",
            source="macho_native",
        )
    try:
        runnable = macho_native.supports_arch(arch, host_machine=machine)
    except Exception as exc:  # noqa: BLE001
        return _unavailable(
            "macho", arch,
            f"Mach-O architecture probe failed: {type(exc).__name__}: {exc}",
            source="macho_native",
        )
    if not runnable:
        return _unavailable(
            "macho", arch,
            f"host {machine or 'unknown'} has no native or cross-arch execution "
            f"path for macho/{arch}",
            source="macho_native",
        )
    if arch == machine:
        return _result(
            "macho", arch,
            available=True,
            tier="native_run",
            engine="macho-native",
            poc_available=True,
            reason=f"native Mach-O execution is available for macho/{arch} on "
                   f"{platform_name}/{machine}",
            source="macho_native",
        )
    # Cross-arch on macOS: only the x86_64-on-arm64 Rosetta path exists, and it
    # is function-level evidence (the engine runs the candidate itself); the
    # external CLI PoC runner is not selected for it.
    return _result(
        "macho", arch,
        available=True,
        tier="emulated_run",
        engine="macho-native",
        poc_available=False,
        reason=f"host {machine} cannot execute macho/{arch} natively; only the "
               f"Rosetta cross-arch path provides function-level evidence, and "
               f"the external PoC runner is unavailable",
        source="macho_native",
    )


def _probe_pe(arch: str) -> dict[str, Any]:
    if arch not in UNICORN_EMULATED_ARCHES:
        return _unavailable(
            "pe", arch,
            f"no Unicorn emulated path for pe/{arch}; external PoC runner "
            f"unavailable",
            source="unicorn",
        )
    return _result(
        "pe", arch,
        available=True,
        tier="emulated_run",
        engine=f"unicorn-{arch}",
        poc_available=False,
        reason=f"pe/{arch} has Unicorn instruction-level execution evidence; "
               f"external PoC runner unavailable",
        source="unicorn",
    )


def _probe_measured(
    format_name: str,
    arch: str,
    external_poc: bool,
    platform_name: str,
    machine: str,
    macho_engine_ready: bool,
    *,
    simulated_host: bool = False,
) -> dict[str, Any]:
    del external_poc  # reported through ``poc_available``; kept for the probe API
    fmt = normalize_format(format_name)
    arch = _normalize_arch(arch)
    platform_name = _normalize_platform(platform_name)
    machine = _normalize_arch(machine)

    if fmt == "elf":
        return _probe_elf(
            arch, platform_name, machine, simulated_host=simulated_host,
        )
    if fmt == "macho":
        return _probe_macho(arch, platform_name, machine, macho_engine_ready)
    if fmt == "macho-fat":
        return _unavailable(
            "macho-fat", arch,
            "fat Mach-O is outside the repair matrix and the external PoC "
            "runner does not select it",
            source="macho_native",
        )
    if fmt in UNICORN_EMULATED_FORMATS:
        return _probe_pe(arch)
    return _unavailable(
        fmt, arch,
        f"no measured runtime capability for format {fmt or 'unknown'!r}",
        source="none",
    )


@lru_cache(maxsize=256)
def _probe_cached(
    format_name: str,
    arch: str,
    external_poc: bool,
    platform_name: str,
    machine: str,
    macho_engine_ready: bool,
) -> dict[str, Any]:
    # Default-host measurements are never simulated: platform/machine above are
    # the real ones read at call time and form the cache key.
    return _probe_measured(
        format_name, arch, external_poc, platform_name, machine,
        macho_engine_ready, simulated_host=False,
    )


def clear_cache() -> None:
    """Drop the default-host probe cache (use after monkeypatching in tests)."""

    _probe_cached.cache_clear()


def probe(
    format_name: str,
    arch: str,
    *,
    external_poc: bool = False,
    host: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure the runtime capability for ``(format, arch)`` on this host.

    ``host`` overrides the measured host for tests and is never cached; the
    default-host measurement is cached (see :func:`clear_cache`).  This function
    never raises for a probe failure: an exception is reported as an
    ``unavailable`` capability with the error in ``reason``.
    """

    fmt = normalize_format(format_name)
    normalized_arch = _normalize_arch(arch)
    try:
        if host is not None:
            platform_name = _normalize_platform(host.get("platform", ""))
            machine = _normalize_arch(host.get("machine", ""))
            return _probe_measured(
                fmt, normalized_arch, bool(external_poc),
                platform_name, machine, _macho_engine_ready(),
                simulated_host=True,
            )
        platform_name = _normalize_platform(sys.platform)
        machine = _normalize_arch(platform.machine())
        engine_ready = (
            _macho_engine_ready() if fmt in {"macho", "macho-fat"} else False
        )
        return copy.deepcopy(
            _probe_cached(
                fmt, normalized_arch, bool(external_poc),
                platform_name, machine, engine_ready,
            )
        )
    except Exception as exc:  # noqa: BLE001 - fail closed, never fabricate
        return _unavailable(
            fmt, normalized_arch,
            f"capability probe failed: {type(exc).__name__}: {exc}",
            source="none",
        )
