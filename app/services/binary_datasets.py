"""Read-only adapters for binary vulnerability datasets.

This module never executes a binary and never downloads data. It discovers
vulnerable/fixed pairs from a caller-selected local root, records architecture
and optimization level, and returns metadata-only inventories when binaries are
not present. Missing data is reported as unknown, never as zero vulnerabilities.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.I)
OPT_RE = re.compile(r"^opt([0-3])$", re.I)
MAX_FILES_DEFAULT = 5000


@dataclass(frozen=True)
class BinaryRecord:
    dataset: str
    cve: str
    variant: str
    optimization: str | None
    arch: str | None
    path: str
    size: int
    sha256: str
    pair_key: str
    cwes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)


def sha256_file(path: Path, limit: int = 256 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    remaining = limit
    with path.open("rb") as handle:
        while remaining > 0:
            block = handle.read(min(1024 * 1024, remaining))
            if not block:
                break
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def _is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def _arch_from_path(path: Path) -> str | None:
    text = "/".join(path.parts).lower()
    for arch in ("x86_64", "i386", "aarch64", "armv7", "arm", "mips", "riscv"):
        if arch in text:
            return arch
    return None


def _cve_dirs(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for base in (root, root / "binpool_artifact"):
        if not base.is_dir():
            continue
        candidates.extend(sorted(p for p in base.iterdir() if p.is_dir() and CVE_RE.match(p.name)))
    return candidates


def _iter_files(root: Path, limit: int) -> Iterable[Path]:
    seen = 0
    for path in sorted(root.rglob("*")):
        if seen >= limit:
            break
        if path.is_file() and _is_elf(path):
            seen += 1
            yield path


def inventory_bin_pool(root: str | Path, *, max_files: int = MAX_FILES_DEFAULT) -> dict[str, Any]:
    """Inventory BinPool's vulnerable/patch × opt0..3 layout."""
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        return {"available": False, "reason": "root_not_found", "root": str(base), "records": [], "pairs": []}
    metadata: dict[str, Any] = {}
    info_path = base / "binpool_info.json"
    if not info_path.is_file():
        info_path = base / "binpool_artifact" / "binpool_info.json"
    if info_path.is_file():
        try:
            metadata = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            metadata = {}
    records: list[BinaryRecord] = []
    pairs: dict[tuple[str, str, str], dict[str, str]] = {}
    truncated = False
    for cve_dir in _cve_dirs(base):
        cve = cve_dir.name.upper()
        info = metadata.get(cve, {}) if isinstance(metadata, dict) else {}
        cwes = [str(x) for x in (info.get("cwes") or [])]
        functions = sorted({str(v) for v in (info.get("file_func") or {}).values()})
        for variant in ("vulnerable", "patch"):
            variant_dir = cve_dir / variant
            if not variant_dir.is_dir():
                continue
            for opt_dir in sorted(variant_dir.iterdir()):
                m = OPT_RE.match(opt_dir.name)
                if not opt_dir.is_dir() or not m:
                    continue
                for path in _iter_files(opt_dir, max_files - len(records)):
                    if len(records) >= max_files:
                        truncated = True
                        break
                    rel = path.relative_to(opt_dir).as_posix()
                    key = (cve, "opt" + m.group(1), rel)
                    record = BinaryRecord(
                        dataset="binpool", cve=cve, variant=variant,
                        optimization="opt" + m.group(1), arch=_arch_from_path(path),
                        path=str(path), size=path.stat().st_size,
                        sha256=sha256_file(path), pair_key=rel,
                        cwes=cwes, functions=functions,
                    )
                    records.append(record)
                    pairs.setdefault(key, {})[variant] = record.sha256
                if truncated:
                    break
            if truncated:
                break
        if truncated:
            break
    pair_rows = [
        {"cve": key[0], "optimization": key[1], "pair_key": key[2],
         "vulnerable_sha256": value.get("vulnerable"), "patched_sha256": value.get("patch"),
         "paired": bool(value.get("vulnerable") and value.get("patch"))}
        for key, value in sorted(pairs.items())
    ]
    return {
        "available": True, "root": str(base), "records": [asdict(r) for r in records],
        "pairs": pair_rows, "truncated": truncated,
        "counts": {
            "binaries": len(records), "cves": len({r.cve for r in records}),
            "paired": sum(1 for row in pair_rows if row["paired"]),
            "optimizations": sorted({r.optimization for r in records if r.optimization}),
        },
        "limitations": ["ELF magic only; architecture labels are path-derived.", "No execution or decompilation."],
    }


def inventory_cvebinarysheet(root: str | Path, *, max_metadata: int = 5000) -> dict[str, Any]:
    """Inventory CveBinarySheet's cve-map JSON; binaries live in external datasets."""
    base = Path(root).expanduser().resolve()
    map_dir = base / "cve-map" if (base / "cve-map").is_dir() else base
    if not map_dir.is_dir():
        return {"available": False, "reason": "root_not_found", "root": str(base), "metadata": []}
    files = sorted(map_dir.glob("*.json"))
    rows = []
    for path in files[:max_metadata]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entries = []
        if isinstance(data, dict):
            for component, items in data.items():
                if isinstance(items, list):
                    for item in items:
                        entries.append({"component": component, **item})
        elif isinstance(data, list):
            entries = data
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rows.append({
                "cve": str(entry.get("cve_name") or path.stem),
                "component": entry.get("component") or entry.get("repository_url"),
                "function_names": entry.get("function_names") or [],
                "affected_version": entry.get("affected_version") or [],
                "patch_url": entry.get("patch_url"),
                "old_files": entry.get("old_files") or [],
                "new_files": entry.get("new_files") or [],
            })
    return {
        "available": True, "root": str(base), "metadata": rows,
        "counts": {"files": len(files), "entries": len(rows),
                   "cves": len({row["cve"] for row in rows}),
                   "components": len({str(row.get("component")) for row in rows if row.get("component")})},
        "limitations": ["Metadata only; pre-built binaries are distributed separately.",
                        "No binary hash is claimed without a local binary root."],
    }


def dataset_status() -> dict[str, Any]:
    """Env-configured inventory; unset roots are reported as not configured."""
    out: dict[str, Any] = {"datasets": {}, "notes": ["Read-only; no automatic download or execution."]}
    binpool = os.environ.get("BINARYREPAIR_BINPOOL_ROOT", "").strip()
    cvebs = os.environ.get("BINARYREPAIR_CVEBINARYSHEET_ROOT", "").strip()
    if binpool:
        out["datasets"]["binpool"] = inventory_bin_pool(binpool)
    else:
        out["datasets"]["binpool"] = {"available": False, "reason": "not_configured",
                                       "hint": "set BINARYREPAIR_BINPOOL_ROOT"}
    if cvebs:
        out["datasets"]["cvebinarysheet"] = inventory_cvebinarysheet(cvebs)
    else:
        out["datasets"]["cvebinarysheet"] = {"available": False, "reason": "not_configured",
                                              "hint": "set BINARYREPAIR_CVEBINARYSHEET_ROOT"}
    return out
