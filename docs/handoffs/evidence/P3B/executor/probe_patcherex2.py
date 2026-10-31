#!/usr/bin/env python3
"""Probe Patcherex2's ModifyFunctionPatch against our fixture.

Three experiments, in increasing order of evidence:

  --demo        reproduce the documented add()/multiply example. Proves the tool
                and its compiler backend work on this machine. Touches nothing of ours.
  --roundtrip   replace copy_name() with the *unchanged* recovered C and compare the
                patched ELF against the original on all oracle cases.
  --fixed       replace copy_name() with the model's edited C and run the fixed oracle.

Patcherex2 is a candidate backend, not an approved dependency. Record the version and
whether it worked; do not silently fall back to a hand-written engine.

Install (separate venv recommended, it pulls angr/LIEF):
    python3 -m venv .venv-patcherex
    .venv-patcherex/bin/pip install patcherex2
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from elftools.elf.elffile import ELFFile
from elftools.elf.constants import P_FLAGS

HERE = Path(__file__).resolve().parent
VERIFY = HERE / "verify.py"


def _find_rx_tail(binary: Path):
    """Return (vaddr, filesz, new_filesz) for the unique R-X PT_LOAD tail."""
    with binary.open("rb") as fh:
        elf = ELFFile(fh)
        rx = [
            seg for seg in elf.iter_segments()
            if seg["p_type"] == "PT_LOAD"
            and (seg["p_flags"] & P_FLAGS.PF_X)
            and not (seg["p_flags"] & P_FLAGS.PF_W)
        ]
    if len(rx) != 1:
        raise SystemExit(f"expected exactly one R-X PT_LOAD, found {len(rx)}")
    seg = rx[0]
    vaddr = seg["p_vaddr"]
    filesz = seg["p_filesz"]
    align = seg["p_align"]
    new_filesz = (filesz + align - 1) // align * align
    return vaddr, filesz, new_filesz


def patch_function(binary: Path, func: str, c_source: str, out: Path) -> None:
    try:
        import lief
        from patcherex2 import ModifyFunctionPatch, Patcherex
    except ImportError as e:
        raise SystemExit(f"missing dependency for Route B patch: {e}")

    # Route B must NOT add PT_LOAD segments (contract authorized_edits[2]
    # allows at most one R-X fallback segment, and only when the tail extension
    # is rejected). Reuse the verified-unused tail of the existing R-X PT_LOAD:
    #   1. extend its p_filesz/p_memsz to the next page boundary
    #      (authorized_edits[1] - the tail ending at the page boundary),
    #   2. register that tail as RX free space,
    #   3. let ModifyFunctionPatch place the recompiled body + data there.
    rx_vaddr, rx_filesz, new_filesz = _find_rx_tail(binary)
    free_start = rx_vaddr + rx_filesz
    free_size = new_filesz - rx_filesz

    with tempfile.NamedTemporaryFile(prefix="routeb-pre-", suffix=".elf", delete=False) as tf:
        pre = Path(tf.name)
    b = lief.parse(str(binary))
    for seg in b.segments:
        if seg.type == lief.ELF.Segment.TYPE.LOAD and seg.virtual_address == rx_vaddr:
            seg.physical_size = new_filesz
            seg.virtual_size = new_filesz
            break
    else:
        raise SystemExit(f"R-X PT_LOAD at {hex(rx_vaddr)} not found in LIEF view")
    b.write(str(pre))

    p = Patcherex(str(pre))
    p.allocation_manager.add_free_space(free_start, free_size, "RX")
    p.patches.append(ModifyFunctionPatch(func, c_source))
    p.apply_patches()
    p.save_binary(str(out))
    pre.unlink(missing_ok=True)


def demo() -> int:
    src = "int add(int a, int b) { return a + b; }\nint main(void) { return 0; }\n"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        c_file = td_path / "add.c"
        c_file.write_text(
            "#include <stdio.h>\n"
            "int add(int a, int b) { return a + b; }\n"
            "int main(void) { printf(\"%d\\n\", add(2, 3)); return 0; }\n"
        )
        binary = td_path / "add"
        subprocess.run(["cc", "-O0", "-o", str(binary), str(c_file)], check=True)

        patched = td_path / "add_patched"
        patch_function(binary, "add", "int add(int a, int b) { return a * b; }", patched)

        before = subprocess.run([str(binary)], capture_output=True, text=True).stdout.strip()
        after = subprocess.run([str(patched)], capture_output=True, text=True).stdout.strip()
        print(f"original: {before}")
        print(f"patched : {after}")
        ok = before == "5" and after == "6"
        print("DEMO", "OK" if ok else "FAILED")
        return 0 if ok else 1


def replace(binary: Path, c_file: Path, out: Path, mode: str, func: str, skip_verify: bool) -> int:
    c_source = c_file.read_text()
    patch_function(binary, func, c_source, out)
    print(f"wrote {out} ({out.stat().st_size} bytes)")

    if skip_verify:
        print("skipped the fixture oracle; run the team's test manifest on this binary")
        return 0

    if mode == "roundtrip":
        cmd = [
            sys.executable, str(VERIFY),
            "--binary", str(out), "--mode", "roundtrip", "--reference", str(binary),
        ]
    else:
        cmd = [sys.executable, str(VERIFY), "--binary", str(out), "--mode", "fixed"]
    return subprocess.run(cmd).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--mode", choices=["roundtrip", "fixed"])
    ap.add_argument("--binary", type=Path, default=HERE / "fixture" / "vuln")
    ap.add_argument("--func", default="copy_name", help="function to replace")
    ap.add_argument("--skip-verify", action="store_true", help="do not run the fixture oracle")
    ap.add_argument("--c-source", type=Path)
    ap.add_argument("--out", type=Path, default=HERE / "out" / "vuln_patched")
    args = ap.parse_args()

    if args.demo:
        return demo()

    if not args.mode or not args.c_source:
        ap.error("use --demo, or --mode roundtrip|fixed with --c-source")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    return replace(
        args.binary, args.c_source, args.out, args.mode, args.func, args.skip_verify
    )


if __name__ == "__main__":
    raise SystemExit(main())
