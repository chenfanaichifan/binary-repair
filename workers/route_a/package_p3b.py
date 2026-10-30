#!/usr/bin/env python3
"""Package a Route B executor output as an INTERFACE v1 M3 -> M5 bundle.

Mechanical only: copies files, writes handoff.json, writes a slash-path
LC_ALL=C sorted SHA256SUMS, optionally zips. It never edits evidence bytes and
never invents a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(root: Path):
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
    ap.add_argument("--bundle-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--id", default="P3B")
    ap.add_argument("--created-at", required=True)
    ap.add_argument("--zip", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.bundle_dir)
    out = Path(args.out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for rel in collect(src):
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, dst)

    files = collect(out)
    handoff = {
        "id": args.id,
        "from": "M3",
        "to": "M5",
        "route": "route_b",
        "created_at": args.created_at,
        "files": files,
        "notes": "Route B runtime bundle; V3 status is whatever the evidence says",
    }
    (out / "handoff.json").write_text(
        json.dumps(handoff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [f"{sha256(out / rel)}  {rel}" for rel in files]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")

    if args.zip:
        zpath = out.with_suffix(".zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in files + ["handoff.json", "SHA256SUMS"]:
                z.write(out / rel, rel)
        print(f"zip {zpath} {zpath.stat().st_size} {sha256(zpath)}")
    print(f"package {out} files={len(files)} sha256sums={sha256(out / 'SHA256SUMS')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
