#!/usr/bin/env python3
"""Repack the P3B runtime bundle with a successful jobwrap log and fixed C.

Mechanical only. Refuses unless the supplied jobwrap log is a success
(exit_code=0) for the exact fixed C hash and the isolation fields are present.
Does not alter candidate/edit-manifest/manifest-repaired bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload(root: Path):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if rel in ("handoff.json", "SHA256SUMS"):
                continue
            out.append(rel)
    return sorted(out, key=lambda s: s.encode())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--jobwrap-log", required=True)
    ap.add_argument("--fixed-c", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--created-at", required=True)
    ap.add_argument("--zip", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.package)
    out = Path(args.out)
    fixed = Path(args.fixed_c)
    log = json.loads(Path(args.jobwrap_log).read_text(encoding="utf-8"))
    fixed_hash = sha(fixed)
    if log.get("c_source_sha256") != fixed_hash:
        raise SystemExit("jobwrap c_source_sha256 does not match fixed C")
    if log.get("exit_code") != 0:
        raise SystemExit("jobwrap log is not a successful run (exit_code != 0)")
    for key, want in (("uid", 1003), ("cap_eff", "0"), ("no_new_privs", 1), ("netns", "empty")):
        if log.get(key) != want:
            raise SystemExit(f"jobwrap isolation field {key}={log.get(key)!r}, expected {want!r}")

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    (out / "fixed_badSink_existing_imports.c").write_bytes(fixed.read_bytes())
    (out / "jobwrap-routeb.json").write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")

    files = payload(out)
    handoff = {
        "id": "P3B",
        "from": "M3",
        "to": "M5",
        "route": "route_b",
        "created_at": args.created_at,
        "files": files,
        "notes": "Route B runtime, V3 6/6; jobwrap log is the successful run",
    }
    (out / "handoff.json").write_text(json.dumps(handoff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"{sha(out / rel)}  {rel}" for rel in files]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")

    if args.zip:
        zp = out.with_suffix(".zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in files + ["handoff.json", "SHA256SUMS"]:
                z.write(out / rel, rel)
        print(f"zip {zp} {zp.stat().st_size} {sha(zp)}")
    print(f"package {out} files={len(files)} sha256sums={sha(out / 'SHA256SUMS')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
