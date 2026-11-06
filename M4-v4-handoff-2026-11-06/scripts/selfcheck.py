#!/usr/bin/env python3
"""Check that this machine is the one that produced the V4 evidence.

    /opt/angr-venv/bin/python scripts/selfcheck.py
    /opt/angr-venv/bin/python scripts/selfcheck.py --json out.json

Every check compares a measured value with a value recorded on 2026-11-06. The
script says whether the interpreter in front of it is the interpreter behind
`expected/harness-output.expected.json`. It asserts nothing about whether that
evidence passes a gate — that is the verifier's call, not the producer's.

Exit status: 0 every check passed, 1 a check failed, 2 an input is missing.

Paths are resolved from this file's location, so the handoff can be extracted
anywhere and run from any working directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "inputs"

PYTHON = "3.12.3"
ANGR = "10.0.4.post1"
Z3_DIST = "5.1.0.0"          # distribution z3-solver
Z3_LIB = "5.1.0"             # what libz3 reports through z3.get_version_string()
VENV = Path("/opt/angr-venv")

HARNESS = INPUTS / "v4_harness.py"
CANDIDATE = INPUTS / "candidate.elf"
ORIGINAL = INPUTS / "original.elf"
CONTRACT = INPUTS / "contract.json"

EXPECTED_SHA = {
    "harness": "986688bcc260abfe9da43e8534f056d11e5c8eae20f3a77763e6943bde6b863e",
    "candidate": "46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0",
    "original": "c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9",
    "contract": "8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b",
}

checks: list[dict] = []


def check(ok: bool, name: str, detail: str) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'ok' if ok else 'FAIL'}] {name:<34} {detail}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, help="write the normalised result here")
    args = ap.parse_args(argv)

    print("# environment self-check")
    print(f"# handoff   {ROOT}")
    print(f"# machine   {platform.node()} / {platform.platform()}")
    print(f"# python    {sys.executable}")
    print()

    # ---- interpreter -------------------------------------------------------
    print("interpreter")
    print(f"  version           {sys.version.splitlines()[0]}")
    print(f"  prefix            {sys.prefix}")
    print(f"  base_prefix       {sys.base_prefix}")
    cfg = VENV / "pyvenv.cfg"
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            print(f"  pyvenv.cfg        {line}")
    libc_name, libc_ver = platform.libc_ver()
    print(f"  libc              {libc_name} {libc_ver}")
    print()

    check(sys.version.split()[0] == PYTHON, "python version",
          f"{sys.version.split()[0]} (expected {PYTHON})")
    check(Path(sys.prefix) == VENV, "interpreter is the venv", str(sys.prefix))
    check(Path(sys.base_prefix) == Path("/usr"), "base interpreter", str(sys.base_prefix))

    # ---- packages ----------------------------------------------------------
    print()
    print("packages")
    distributions = len(list(metadata.distributions()))
    print(f"  distributions     {distributions} (pip itself included)")
    print(f"  pip               {metadata.version('pip')}")
    for name, version in (("angr", ANGR), ("archinfo", "10.0.4"),
                          ("cle", "10.0.4"), ("pyvex", "10.0.4"),
                          ("z3-solver", Z3_DIST)):
        got = metadata.version(name)
        check(got == version, f"{name} pinned", f"{got} (expected {version})")

    import angr
    import z3

    claripy = angr.claripy
    print(f"  claripy           {getattr(claripy, '__version__', 'bundled with angr')}"
          "   (not importable as `claripy` in angr 10; use `angr.claripy`)")
    print(f"  z3 module         {z3.__file__}")
    check(angr.__version__ == ANGR, "angr.__version__", angr.__version__)
    check(z3.get_version_string() == Z3_LIB, "libz3 version",
          f"{z3.get_version_string()} (expected {Z3_LIB})")

    print()
    proc = subprocess.run([sys.executable, "-m", "pip", "check"],
                          capture_output=True, text=True)
    check(proc.returncode == 0, "pip check",
          (proc.stdout or proc.stderr).strip().splitlines()[0])

    # ---- solver smoke test -------------------------------------------------
    print()
    print("solver")
    x = z3.Int("x")
    s1 = z3.Solver()
    s1.add(x > 1, x < 3)
    s2 = z3.Solver()
    s2.add(x > 2, x < 2)
    check(str(s1.check()) == "sat", "z3 returns sat", "x>1 and x<3")
    check(str(s2.check()) == "unsat", "z3 returns unsat", "x>2 and x<2")

    # ---- the inputs --------------------------------------------------------
    print()
    print("inputs")
    missing = False
    for label, path in (("harness", HARNESS), ("candidate", CANDIDATE),
                        ("original", ORIGINAL), ("contract", CONTRACT)):
        if not path.is_file():
            check(False, f"{label} present", f"missing: {path}")
            missing = True
            continue
        got = sha256(path)
        check(got == EXPECTED_SHA[label], f"{label} sha256",
              f"{got[:16]}… {path.stat().st_size} B")

    if missing or not CONTRACT.is_file() or not CANDIDATE.is_file() \
            or not ORIGINAL.is_file():
        print("\nverdict: cannot continue — an input is missing")
        return 2

    # ---- angr loading the same two binaries --------------------------------
    print()
    print("angr")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    entry_name = contract["target_entry"]
    print(f"  contract          schema {contract['schema_version']} / "
          f"input_mode {contract['input_mode']} / target_entry {entry_name}")
    addrs = {}
    for label, path in (("candidate", CANDIDATE), ("original", ORIGINAL)):
        project = angr.Project(str(path), auto_load_libs=False)
        symbol = project.loader.find_symbol(entry_name)
        addr = symbol.rebased_addr if symbol is not None else None
        addrs[label] = addr
        print(f"  {label:<10} arch {project.arch.name:<6} entry {hex(project.entry)} "
              f"target {hex(addr) if addr is not None else 'not found'}")
    check(addrs["candidate"] is not None and addrs["candidate"] == addrs["original"],
          "target entry resolves",
          hex(addrs["candidate"]) if addrs["candidate"] is not None else "?")

    # ---- verdict -----------------------------------------------------------
    failed = [c["name"] for c in checks if not c["ok"]]
    passed = len(checks) - len(failed)
    print()
    if failed:
        print(f"verdict: {passed}/{len(checks)} checks passed")
        for name in failed:
            print(f"  failing: {name}")
        status = 1
    else:
        print(f"verdict: {passed}/{len(checks)} checks passed — this interpreter "
              "matches the recipe recorded on 2026-11-06")
        status = 0

    if args.json:
        payload = {
            "checks": checks,
            "passed": passed,
            "total": len(checks),
            "ok": status == 0,
            "engine": {
                "python": sys.version.split()[0],
                "angr": angr.__version__,
                "z3_solver": metadata.version("z3-solver"),
                "z3_lib": z3.get_version_string(),
                "pip": metadata.version("pip"),
                "distributions": distributions,
            },
        }
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8", newline="\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
