"""Scorable no-input V2 static interface check.

This check is binary-level and reads the original and candidate ELF directly.
A measured observation file that merely says ``pass: true`` is not a verdict;
only the five checks below, all true, may turn V2 from ``not_run`` into
``passed``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

CHECK_NAMES = (
    "target_entry_symbol_unchanged",
    "dynamic_symbols_unchanged",
    "needed_flags_unchanged",
    "entry_unchanged",
    "no_new_dynamic_import",
)


class InterfaceCheckError(ValueError):
    """The static interface check could not be evaluated."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _symbol_row(symbol: Any) -> tuple:
    info = symbol["st_info"]
    return (
        str(symbol.name),
        int(symbol["st_value"]),
        int(symbol["st_size"]),
        str(info["type"]),
        str(info["bind"]),
        str(symbol["st_other"]["visibility"]),
        str(symbol["st_shndx"]),
    )


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise InterfaceCheckError(f"missing ELF: {path}")
    with path.open("rb") as handle:
        elf = ELFFile(handle)
        symtab = elf.get_section_by_name(".symtab")
        dynsym = elf.get_section_by_name(".dynsym")
        dynamic = elf.get_section_by_name(".dynamic")
        symbols = {}
        if symtab is not None:
            for symbol in symtab.iter_symbols():
                if symbol.name and symbol.name not in symbols:
                    symbols[str(symbol.name)] = _symbol_row(symbol)
        dynamic_rows = []
        undefined = set()
        if dynsym is not None:
            for symbol in dynsym.iter_symbols():
                if not symbol.name:
                    continue
                row = _symbol_row(symbol)
                dynamic_rows.append(row)
                if row[-1] in ("SHN_UNDEF", "0"):
                    undefined.add(row[0])
        needed = []
        flags = []
        if dynamic is not None:
            for tag in dynamic.iter_tags():
                name = str(tag.entry.d_tag)
                if name == "DT_NEEDED":
                    needed.append(str(getattr(tag, "needed", "")))
                elif name in ("DT_FLAGS", "DT_FLAGS_1"):
                    flags.append((name, int(tag.entry.d_val)))
        return {
            "entry": int(elf["e_entry"]),
            "symbols": symbols,
            "dynamic_rows": sorted(dynamic_rows),
            "undefined": undefined,
            "needed": sorted(needed),
            "flags": sorted(flags),
        }


def check_interface(
    original_path: str | Path,
    candidate_path: str | Path,
    target_entry: str,
) -> dict[str, Any]:
    """Evaluate the five V2 checks. Any failure leaves state ``not_run``."""

    original_path = Path(original_path)
    candidate_path = Path(candidate_path)
    target = str(target_entry or "").strip()
    checks = {name: False for name in CHECK_NAMES}
    details: dict[str, Any] = {}
    try:
        original = _load(original_path)
        candidate = _load(candidate_path)
        original_symbol = original["symbols"].get(target)
        candidate_symbol = candidate["symbols"].get(target)
        checks["target_entry_symbol_unchanged"] = (
            target != "" and original_symbol is not None and original_symbol == candidate_symbol
        )
        checks["dynamic_symbols_unchanged"] = (
            original["dynamic_rows"] == candidate["dynamic_rows"]
        )
        checks["needed_flags_unchanged"] = (
            original["needed"] == candidate["needed"]
            and original["flags"] == candidate["flags"]
        )
        checks["entry_unchanged"] = original["entry"] == candidate["entry"]
        new_imports = sorted(candidate["undefined"] - original["undefined"])
        checks["no_new_dynamic_import"] = not new_imports

        details = {
            "target_entry": target,
            "original_entry": hex(original["entry"]),
            "candidate_entry": hex(candidate["entry"]),
            "original_needed": original["needed"],
            "candidate_needed": candidate["needed"],
            "original_flags": original["flags"],
            "candidate_flags": candidate["flags"],
            "new_dynamic_imports": new_imports,
            "target_symbol_original": list(original_symbol) if original_symbol else None,
            "target_symbol_candidate": list(candidate_symbol) if candidate_symbol else None,
        }
    except Exception as exc:  # noqa: BLE001 - fail closed, report why
        details = {"error": f"{type(exc).__name__}: {exc}", "target_entry": target}

    passed = all(checks.values())
    return {
        "schema_version": 1,
        "gate": "V2",
        "kind": "interface",
        "scope": "binary",
        "state": "passed" if passed else "not_run",
        "pass": passed,
        "target_entry": target,
        "original_sha256": _sha256(original_path) if original_path.is_file() else "",
        "candidate_sha256": _sha256(candidate_path) if candidate_path.is_file() else "",
        "checks": checks,
        "score": {"passed": sum(1 for value in checks.values() if value), "total": len(CHECK_NAMES)},
        "details": details,
    }


def validate_interface_report(
    data: object,
    *,
    candidate_sha256: str | None = None,
    original_sha256: str | None = None,
    target_entry: str | None = None,
) -> dict[str, Any]:
    """Validate a scored V2 report; a measured observation does not qualify."""

    if not isinstance(data, dict):
        raise InterfaceCheckError("V2 report must be an object")
    if data.get("schema_version") != 1 or data.get("gate") != "V2":
        raise InterfaceCheckError("V2 report is not a schema-1 V2 report")
    checks = data.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(CHECK_NAMES):
        raise InterfaceCheckError("V2 report does not contain exactly the five checks")
    if any(checks[name] is not True for name in CHECK_NAMES):
        raise InterfaceCheckError("V2 report has a failed or missing check")
    if data.get("pass") is not True or data.get("state") != "passed":
        raise InterfaceCheckError("V2 report is not a passed verdict")
    if data.get("score") != {"passed": len(CHECK_NAMES), "total": len(CHECK_NAMES)}:
        raise InterfaceCheckError("V2 report score is not 5/5")
    if candidate_sha256 is not None and data.get("candidate_sha256") != candidate_sha256:
        raise InterfaceCheckError("V2 report candidate hash mismatch")
    if original_sha256 is not None and data.get("original_sha256") != original_sha256:
        raise InterfaceCheckError("V2 report original hash mismatch")
    if target_entry is not None and data.get("target_entry") != target_entry:
        raise InterfaceCheckError("V2 report target entry mismatch")
    return data


__all__ = ["CHECK_NAMES", "InterfaceCheckError", "check_interface", "validate_interface_report"]
