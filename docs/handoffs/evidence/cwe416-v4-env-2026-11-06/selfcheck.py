#!/usr/bin/env python3
"""Environment self-check for the guest interpreter that produced the V4 evidence.

Run it with the venv's own interpreter:

    /opt/angr-venv/bin/python selfcheck.py

Every check compares a measured value with a value recorded on 2026-11-06.
Nothing here asserts a gate result: it says whether this interpreter is the one
that produced docs/handoffs/evidence/cwe416-v4-2026-11-06/harness-output.json.

Exit status is 0 when every check passes, 1 otherwise, 2 when a path is missing.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

# ---------------------------------------------------------------- expectations
PYTHON = "3.12.3"
ANGR = "10.0.4.post1"
Z3_DIST = "5.1.0.0"       # distribution z3-solver
Z3_LIB = "5.1.0"          # what libz3 reports through z3.get_version_string()
VENV = Path("/opt/angr-venv")

HARNESS = Path("/home/lab/v4/v4_harness.py")
CANDIDATE = Path("/home/lab/cwe416-sync/candidate.elf")
FIXTURE = Path(
    "/home/lab/cwe416-sync/kit/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput"
)
ORIGINAL = FIXTURE / "original.elf"
CONTRACT = FIXTURE / "contract.json"

EXPECTED_SHA = {
    "harness": "986688bcc260abfe9da43e8534f056d11e5c8eae20f3a77763e6943bde6b863e",
    "candidate": "46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0",
    "original": "c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9",
    "contract": "8a2b408c9b1463ca8cb14692d11f1580f80816a74e81cc13310852f3700e3c3b",
}

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str) -> None:
    results.append((ok, name, detail))
    print(f"  [{'ok' if ok else 'FAIL'}] {name:<34} {detail}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print("# /opt/angr-venv environment self-check")
    print(f"# run at {platform.node()} on {platform.platform()}")
    print()

    # ---- interpreter -------------------------------------------------------
    print("interpreter")
    print(f"  executable        {sys.executable}")
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
    dists = sorted({d.metadata["Name"] for d in metadata.distributions()})
    print(f"  distributions     {len(dists)} installed")
    print(f"  pip               {metadata.version('pip')}")
    want = {
        "angr": ANGR,
        "archinfo": "10.0.4",
        "cle": "10.0.4",
        "pyvex": "10.0.4",
        "z3-solver": Z3_DIST,
    }
    for name, version in want.items():
        got = metadata.version(name)
        check(got == version, f"{name} pinned", f"{got} (expected {version})")

    import angr
    import z3

    claripy = angr.claripy
    check(angr.__version__ == ANGR, "angr.__version__", angr.__version__)
    check(z3.get_version_string() == Z3_LIB, "libz3 version",
          f"{z3.get_version_string()} (expected {Z3_LIB})")
    print(f"  claripy           {getattr(claripy, '__version__', 'bundled with angr')}")
    print(f"  z3 python module  {z3.__file__}")

    print()
    proc = subprocess.run([sys.executable, "-m", "pip", "check"],
                          capture_output=True, text=True)
    check(proc.returncode == 0, "pip check",
          (proc.stdout or proc.stderr).strip().splitlines()[0])

    # ---- solver smoke test -------------------------------------------------
    print()
    print("solver")
    x = z3.Int("x")
    s = z3.Solver()
    s.add(x > 1, x < 3)
    sat_answer = s.check()
    s2 = z3.Solver()
    s2.add(x > 2, x < 2)
    unsat_answer = s2.check()
    check(str(sat_answer) == "sat", "z3 returns sat", "x>1 and x<3")
    check(str(unsat_answer) == "unsat", "z3 returns unsat", "x>2 and x<2")

    # Timeout must surface as unknown rather than as a wrong verdict. Kept
    # informational: the answer is the solver's, not a claim about the binary.
    s3 = z3.Solver()
    s3.set(timeout=1)
    a, b = z3.Ints("a b")
    s3.add(a * a * a + b * b * b == 3)
    print(f"  timeout probe     {s3.check()} (1 ms budget; informational)")

    # ---- the binaries the harness reads ------------------------------------
    print()
    print("inputs")
    for label, path in (("harness", HARNESS), ("candidate", CANDIDATE),
                        ("original", ORIGINAL), ("contract", CONTRACT)):
        if not path.is_file():
            print(f"  [FAIL] {label:<17} missing: {path}")
            results.append((False, f"{label} present", str(path)))
            continue
        got = sha256(path)
        ok = got == EXPECTED_SHA[label]
        check(ok, f"{label} sha256", f"{got[:16]}… {path.stat().st_size} B")

    if not CONTRACT.is_file() or not CANDIDATE.is_file() or not ORIGINAL.is_file():
        print("\nverdict: cannot check angr loading — an input is missing")
        return 2

    # ---- angr loading the same two binaries --------------------------------
    print()
    print("angr")
    import json

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    entry_name = contract["target_entry"]
    print(f"  contract target   {entry_name}")
    print(f"  contract mode     schema {contract['schema_version']} / input_mode {contract['input_mode']}")
    addrs = {}
    for label, path in (("candidate", CANDIDATE), ("original", ORIGINAL)):
        project = angr.Project(str(path), auto_load_libs=False)
        symbol = project.loader.find_symbol(entry_name)
        addr = symbol.rebased_addr if symbol else None
        addrs[label] = addr
        print(f"  {label:<10} arch {project.arch.name:<6} entry {hex(project.entry)} "
              f"target {hex(addr) if addr else 'not found'}")
    check(addrs["candidate"] == addrs["original"] and addrs["candidate"] is not None,
          "target entry resolves", hex(addrs["candidate"]) if addrs["candidate"] else "?")

    # ---- summary -----------------------------------------------------------
    failed = [name for ok, name, _ in results if not ok]
    print()
    if failed:
        print(f"verdict: {len(results) - len(failed)}/{len(results)} checks passed")
        for name in failed:
            print(f"  failing: {name}")
        return 1
    print(f"verdict: {len(results)}/{len(results)} checks passed — this interpreter "
          f"matches the recipe recorded on 2026-11-06")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
