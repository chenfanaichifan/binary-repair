#!/usr/bin/env python3
"""Build the reproducible vulnerable binary fixtures used by the v4 pipeline.

The fixtures are tiny native programs whose only job is to place a 16-byte
stack buffer at the top of a callee frame and call an unbounded ``strcpy`` on
it.  That makes the repair engine's frame model exact:

    capacity = frame_top - destination = 0x10

Toolchains:
  * Mach-O arm64 / x86-64: system ``clang`` (ad-hoc signed by the linker);
  * PE x86-64 / arm64 and ELF AArch64: the Zig toolchain already vendored under
    ``.tmp/zigpkg/site/ziglang/zig`` (no network install).

Usage:
  python3 scripts/build_binary_fixtures.py --check
  python3 scripts/build_binary_fixtures.py --force
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "fixtures" / "src"
OUT = ROOT / "fixtures"
PROVENANCE = OUT / "PROVENANCE.json"
ZIG_DEFAULT = ROOT / ".tmp" / "zigpkg" / "site" / "ziglang" / "zig"
ZIG_CACHE = ROOT / ".tmp" / "zigcache"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    proc = subprocess.run(
        cmd, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{proc.stdout}\n{proc.stderr}"
        )


def _version(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=20)
        return (proc.stdout or "").strip().splitlines()[0]
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {type(exc).__name__}"


def _zig_spec(zig: Path) -> dict[str, object]:
    env = dict(os.environ)
    ZIG_CACHE.mkdir(parents=True, exist_ok=True)
    env["ZIG_GLOBAL_CACHE_DIR"] = str(ZIG_CACHE / "global")
    env["ZIG_LOCAL_CACHE_DIR"] = str(ZIG_CACHE / "local")
    return {
        "env": env,
        "base": [str(zig), "cc"],
        "version": _version([str(zig), "version"]),
    }


def _targets(zig: dict[str, object]) -> list[dict[str, object]]:
    clang = shutil.which("clang") or "/usr/bin/clang"
    common_c = ["-O0", "-g0", "-Wno-unused-command-line-argument"]
    return [
        {
            "name": "macho-arm64",
            "path": OUT / "macho" / "vuln-strcpy-arm64",
            "cmd": [
                clang, *common_c, "-o", "TMP",
                str(SRC / "main.c"), str(SRC / "vuln_copy_macho_aarch64.S"),
            ],
            "env": None,
            "tool": _version([clang, "--version"]),
            "expect": ("macho", "arm64"),
        },
        {
            "name": "macho-x86_64",
            "path": OUT / "macho" / "vuln-strcpy-x86_64",
            "cmd": [
                clang, *common_c, "-arch", "x86_64", "-o", "TMP",
                str(SRC / "main.c"), str(SRC / "vuln_copy_macho_x86_64.S"),
            ],
            "env": None,
            "tool": _version([clang, "--version"]),
            "expect": ("macho", "x86_64"),
        },
        {
            "name": "pe-x86_64",
            "path": OUT / "pe" / "vuln-strcpy-x64.exe",
            "cmd": [
                *zig["base"], "-target", "x86_64-windows-gnu", "-O0", "-g0",
                "-o", "TMP", str(SRC / "main.c"),
                str(SRC / "vuln_copy_win_x86_64.S"),
            ],
            "env": zig["env"],
            "tool": zig["version"],
            "expect": ("pe", "x86_64"),
        },
        {
            "name": "pe-arm64",
            "path": OUT / "pe" / "vuln-strcpy-arm64.exe",
            "cmd": [
                *zig["base"], "-target", "aarch64-windows-gnu", "-O0", "-g0",
                "-o", "TMP", str(SRC / "main.c"),
                str(SRC / "vuln_copy_win_aarch64.S"),
            ],
            "env": zig["env"],
            "tool": zig["version"],
            "expect": ("pe", "arm64"),
        },
        {
            "name": "elf-arm64",
            "path": OUT / "elf" / "vuln-strcpy-arm64.elf",
            "cmd": [
                *zig["base"], "-target", "aarch64-linux-musl", "-O0", "-g0",
                "-o", "TMP", str(SRC / "main.c"),
                str(SRC / "vuln_copy_win_aarch64.S"),
            ],
            "env": zig["env"],
            "tool": zig["version"],
            "expect": ("elf", "arm64"),
        },
        {
            "name": "pe-i386-control",
            "path": OUT / "pe" / "i386-control.exe",
            "cmd": [
                *zig["base"], "-target", "x86-windows-gnu", "-O0", "-g0",
                "-o", "TMP", str(SRC / "control_i386.c"),
            ],
            "env": zig["env"],
            "tool": zig["version"],
            "expect": ("pe", "i386"),
        },
    ]


def _record(target: dict[str, object]) -> dict[str, object]:
    path = Path(target["path"])
    # Commands are recorded relative to the repository so the provenance file
    # (and every handoff package built from it) carries no host paths.
    cmd = [
        str(part).replace(str(ROOT) + "/", "").replace(str(ROOT), ".")
        if str(part).startswith(str(ROOT)) else str(part)
        for part in target["cmd"]
    ]
    return {
        "name": target["name"],
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha(path),
        "size": path.stat().st_size,
        "command": ["<zig>" if str(part) == str(ZIG_DEFAULT) else part for part in cmd],
        "tool": target["tool"],
        "source_sha256": {
            str(item.relative_to(SRC)): _sha(item)
            for item in sorted(SRC.rglob("*")) if item.is_file()
        },
    }


def build(force: bool) -> dict[str, object]:
    zig = _zig_spec(Path(ZIG_DEFAULT))
    records = []
    for target in _targets(zig):
        path = Path(target["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and not force:
            records.append(_record(target))
            continue
        tmp = path.with_suffix(path.suffix + ".tmp")
        cmd = [str(tmp) if part == "TMP" else str(part) for part in target["cmd"]]
        _run(cmd, env=target["env"])
        tmp.replace(path)
        path.chmod(0o755)
        # The MinGW linker writes a large PDB next to the PE; it contains local
        # paths and is not needed for repair, so keep the fixture tree clean.
        for pdb in (path.with_suffix(path.suffix + ".pdb"),
                    path.with_suffix(".pdb")):
            pdb.unlink(missing_ok=True)
        records.append(_record(target))
    payload = {
        "schema_version": 1,
        "generated_by": "scripts/build_binary_fixtures.py",
        "sources": sorted(str(p.relative_to(ROOT)) for p in SRC.iterdir()),
        "fixtures": records,
    }
    PROVENANCE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def check() -> int:
    if not PROVENANCE.is_file():
        print("PROVENANCE.json missing; run without --check first", file=sys.stderr)
        return 1
    payload = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    errors = []
    for item in payload.get("fixtures", []):
        path = ROOT / item["path"]
        if not path.is_file():
            errors.append(f"missing {item['path']}")
        elif _sha(path) != item["sha256"]:
            errors.append(f"sha256 mismatch {item['path']}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"ok: {len(payload['fixtures'])} fixtures match PROVENANCE.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    payload = build(args.force)
    for item in payload["fixtures"]:
        print(f"{item['name']:18} {item['size']:>8}  {item['sha256'][:16]}  {item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
