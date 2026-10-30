#!/usr/bin/env python3
"""V2 interface / compatibility check for one candidate against the original.

Reads real ELF bytes with readelf and actually executes both binaries, then
reports invariant checks. It never invents a pass: a check that cannot be
evaluated is reported as null and fails the gate.

Usage: v2_interface.py <original> <candidate> <label>
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

READELF = "/usr/bin/readelf"


def sh(*args: str) -> str:
    out = subprocess.run(args, capture_output=True, text=True)
    return out.stdout


def header(path: Path) -> dict:
    text = sh(READELF, "-hW", str(path))
    out = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key in ("Class", "Data", "Type", "Machine", "Entry point address", "OS/ABI", "ABI Version"):
            out[key] = value
    return out


def loads(path: Path) -> list[dict]:
    text = sh(READELF, "-lW", str(path))
    rows: list[dict] = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("LOAD"):
            parts = stripped.split()
            rows.append({
                "type": "LOAD",
                "offset": parts[1],
                "vaddr": parts[2],
                "filesz": parts[4],
                "memsz": parts[5],
                "flags": parts[6],
                "align": parts[7],
            })
        elif stripped in ("INTERP", "GNU_STACK", "GNU_RELRO", "GNU_PROPERTY", "PHDR", "DYNAMIC", "NOTE"):
            current = stripped
            rows.append({"type": current})
    return rows


def segment_types(path: Path) -> list[str]:
    text = sh(READELF, "-lW", str(path))
    types = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("LOAD", "INTERP", "GNU_STACK", "GNU_RELRO", "PHDR", "DYNAMIC", "NOTE", "TLS", "GNU_PROPERTY")):
            types.append(stripped.split()[0])
    return types


def interp(path: Path) -> str:
    text = sh(READELF, "-lW", str(path))
    for line in text.splitlines():
        if "Requesting program interpreter" in line:
            return line.split(":", 1)[1].strip().rstrip("]")
    return ""


def needed(path: Path) -> list[str]:
    text = sh(READELF, "-dW", str(path))
    return sorted(
        line.split("[", 1)[1].rstrip("]")
        for line in text.splitlines()
        if "(NEEDED)" in line
    )


def dyn_flags(path: Path) -> str:
    text = sh(READELF, "-dW", str(path))
    for line in text.splitlines():
        if "FLAGS" in line or "FLAGS_1" in line:
            return line.split(":", 1)[1].strip() if ":" in line else line.strip()
    return ""


def exported_symbols(path: Path) -> list[str]:
    text = sh(READELF, "--dyn-syms", "-W", str(path))
    names = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[0].endswith(":"):
            # readelf dyn-syms row: Num: Value Size Type Bind Vis Ndx Name
            name = parts[7]
            if name and name != "UND" and parts[4] in ("GLOBAL", "WEAK"):
                names.append(name)
    return sorted(set(names))


def stack_flags(path: Path) -> str:
    text = sh(READELF, "-lW", str(path))
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("GNU_STACK"):
            return line.strip()
    return ""


def reloc_summary(path: Path) -> dict:
    text = sh(READELF, "-rW", str(path))
    counts: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2].startswith("R_X86_64"):
            counts[parts[2]] = counts.get(parts[2], 0) + 1
    return {"total": sum(counts.values()), "by_type": dict(sorted(counts.items()))}


def run_probe(path: Path) -> dict:
    """Load and run the binary with an empty argv[1]; capture rc and streams."""
    proc = subprocess.run(
        [str(path), ""],
        capture_output=True,
        cwd=str(path.parent),
        timeout=30,
    )
    return {
        "returncode": proc.returncode,
        "stdout_hex": proc.stdout.hex(),
        "stderr_hex": proc.stderr.hex(),
    }


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    original = Path(sys.argv[1]).resolve()
    candidate = Path(sys.argv[2]).resolve()
    label = sys.argv[3]

    o_head, c_head = header(original), header(candidate)
    o_interp, c_interp = interp(original), interp(candidate)
    o_needed, c_needed = needed(original), needed(candidate)
    o_syms, c_syms = exported_symbols(original), exported_symbols(candidate)
    o_types, c_types = segment_types(original), segment_types(candidate)

    def flag_ok(text: str) -> bool:
        return "RWE" not in text and "WE" not in text

    o_loads = [row for row in loads(original) if row["type"] == "LOAD"]
    c_loads = [row for row in loads(candidate) if row["type"] == "LOAD"]

    def base_shape(rows: list[dict]) -> list[dict]:
        return [
            {k: row[k] for k in ("offset", "vaddr", "flags", "align")} for row in rows
        ]

    o_shape = base_shape(o_loads)
    c_shape = base_shape(c_loads)
    preserved = c_shape[: len(o_shape)] == o_shape
    extra = c_shape[len(o_shape):] if len(c_shape) > len(o_shape) else []

    # contract.json authorizes at most ONE new R-X PT_LOAD, and only as the
    # fallback when the existing R-X tail extension is rejected.
    ALLOWED_EXTRA_LOADS = 1
    extra_within_contract = len(extra) <= ALLOWED_EXTRA_LOADS
    extra_all_read_only = all(
        "W" not in row["flags"] and "R" in row["flags"] for row in extra
    )

    checks: dict[str, bool | None] = {}
    failures: list[str] = []
    informational: dict[str, object] = {}

    checks["same_elf_class"] = o_head.get("Class") == c_head.get("Class")
    checks["same_machine"] = o_head.get("Machine") == c_head.get("Machine")
    checks["same_elf_type"] = o_head.get("Type") == c_head.get("Type")
    checks["same_os_abi"] = o_head.get("OS/ABI") == c_head.get("OS/ABI")
    checks["entry_unchanged"] = o_head.get("Entry point address") == c_head.get("Entry point address")
    checks["interp_unchanged"] = o_interp == c_interp
    checks["needed_set_unchanged"] = o_needed == c_needed
    checks["exported_symbols_unchanged"] = o_syms == c_syms
    checks["original_load_segments_preserved"] = preserved
    checks["extra_load_segments_within_contract"] = extra_within_contract
    checks["extra_load_segments_not_writable"] = extra_all_read_only
    checks["no_writable_executable_segment"] = all(flag_ok(row["flags"]) for row in c_loads)
    checks["stack_nx_preserved"] = stack_flags(original) == stack_flags(candidate)
    checks["relocation_types_subset"] = set(reloc_summary(candidate)["by_type"]) <= set(
        reloc_summary(original)["by_type"]
    )

    # A real load: both binaries must execute in this environment.
    o_run = run_probe(original)
    c_run = run_probe(candidate)
    checks["candidate_loads_and_runs"] = c_run["returncode"] == 0
    checks["valid_path_stdout_matches_original"] = c_run["stdout_hex"] == o_run["stdout_hex"]

    for name, value in checks.items():
        if value is not True:
            failures.append(name)

    informational["program_header_order_changed"] = o_types != c_types
    informational["original_segment_types"] = o_types
    informational["candidate_segment_types"] = c_types
    informational["extra_load_segment_count"] = len(extra)
    informational["extra_load_segments"] = extra
    informational["allowed_extra_load_segments"] = ALLOWED_EXTRA_LOADS
    informational["size_change"] = {
        "original": original.stat().st_size,
        "candidate": candidate.stat().st_size,
    }

    payload = {
        "gate": "V2",
        "obligation": "interface",
        "mode": "invoked by name",
        "invoked_as": "v2_interface.py ./original.elf ./candidate.elf <label>",
        "label": label,
        "environment": {
            "kernel": subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip(),
            "arch": subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip(),
            "readelf": subprocess.run([READELF, "--version"], capture_output=True, text=True).stdout.splitlines()[0],
            "hostname": subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip(),
            "uid": subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip(),
        },
        "hashes": {"original_sha256": digest(original), "candidate_sha256": digest(candidate)},
        "original": {
            "header": o_head,
            "interp": o_interp,
            "needed": o_needed,
            "exported_symbols": o_syms,
            "load_segments": o_loads,
            "segment_types": o_types,
            "stack": stack_flags(original),
            "relocations": reloc_summary(original),
            "probe_run": o_run,
        },
        "candidate": {
            "header": c_head,
            "interp": c_interp,
            "needed": c_needed,
            "exported_symbols": c_syms,
            "load_segments": c_loads,
            "segment_types": c_types,
            "stack": stack_flags(candidate),
            "relocations": reloc_summary(candidate),
            "probe_run": c_run,
        },
        "checks": checks,
        "informational": informational,
        "contract_reference": (
            "authorized_edits[2]: allow no new segment ... only if the tail extension "
            "is rejected, allow one new R-X PT_LOAD with recorded headers"
        ),
        "failures": failures,
        "result": "passed" if not failures else "failed",
    }

    out = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(f"v2-{label}.json")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"label": label, "result": payload["result"], "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
