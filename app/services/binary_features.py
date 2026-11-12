"""Static binary features without executing the artifact.

LIEF provides format/section/import metadata; ``strings`` provides a bounded
literal sample. Missing tools are reported, never installed at runtime.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

DANGEROUS = {
    "strcpy", "strcat", "sprintf", "gets", "memcpy", "memmove", "printf",
    "malloc", "calloc", "realloc", "free", "read", "recv", "system", "popen",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strings(path: Path, limit: int = 400) -> list[str]:
    exe = shutil.which("strings")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "-a", str(path)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return out.stdout.splitlines()[:limit]


def extract_features(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(str(target))
    result: dict[str, Any] = {
        "path": str(target), "size": target.stat().st_size, "sha256": _sha256(target),
        "format": None, "arch": None, "sections": [], "imports": [], "symbols": 0,
        "dangerous_imports": [], "strings_sample": [], "limitations": [],
    }
    try:
        import lief
    except Exception as exc:  # pragma: no cover - optional dependency
        result["limitations"].append(f"LIEF unavailable: {type(exc).__name__}")
        return result
    try:
        elf = lief.ELF.parse(str(target))
        if elf is not None:
            result["format"] = "elf"
            result["arch"] = str(getattr(elf.header, "machine_type", "unknown"))
            result["sections"] = [s.name for s in elf.sections][:80]
            result["imports"] = [s.name for s in elf.imported_symbols][:200]
            result["symbols"] = len(elf.symbols)
        else:
            macho = lief.MachO.parse(str(target))
            if macho is not None and len(macho):
                binary = macho.at(0)
                result["format"] = "macho"
                result["arch"] = str(binary.header.cpu_type)
                result["sections"] = [s.name for s in binary.sections][:80]
                result["imports"] = [s.name for s in binary.imported_symbols][:200]
                result["symbols"] = len(binary.exported_symbols)
    except Exception as exc:  # noqa: BLE001 - malformed artifacts are data, not a crash
        result["limitations"].append(f"parse failed: {type(exc).__name__}: {exc}")
    result["dangerous_imports"] = sorted(
        {name.lstrip("_") for name in result["imports"] if name.lstrip("_") in DANGEROUS}
    )
    result["strings_sample"] = _strings(target)
    return result
