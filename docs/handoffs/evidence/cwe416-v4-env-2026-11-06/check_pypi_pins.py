#!/usr/bin/env python3
"""Check that each pinned version exists on PyPI and name the wheel a linux
x86-64 CPython 3.12 rebuild would fetch.

    python3 check_pypi_pins.py

Read-only: queries the JSON API, downloads nothing. This is not a substitute for
running provision_angr_venv.sh — it shows the pins are real artifacts, not that
they install and import on a particular machine.
"""

import json
import sys
import urllib.request

PACKAGES = [
    ("angr", "10.0.4.post1"),
    ("archinfo", "10.0.4"),
    ("cle", "10.0.4"),
    ("pyvex", "10.0.4"),
    ("z3-solver", "5.1.0.0"),
]


def wheel_for(files: list[dict]) -> dict | None:
    """Pick the wheel a manylinux x86-64 CPython 3.12 interpreter would install.

    Pure-Python distributions ship `py3-none-any` instead of a manylinux tag, so
    both shapes count as installable here.
    """
    candidates = [
        f
        for f in files
        if f["packagetype"] == "bdist_wheel"
        and (
            ("manylinux" in f["filename"] and "x86_64" in f["filename"]
             and ("cp312" in f["filename"] or "py3-none" in f["filename"]))
            or f["filename"].endswith("-py3-none-any.whl")
            or f["filename"].endswith("-py2.py3-none-any.whl")
        )
    ]
    return candidates[0] if candidates else None


def main() -> int:
    missing = []
    print(f"{'package':<11} {'version':<13} {'uploaded':<11} wheel")
    for name, version in PACKAGES:
        url = f"https://pypi.org/pypi/{name}/{version}/json"
        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.load(response)
        info = data["info"]
        files = data["urls"]
        uploaded = min(f["upload_time"] for f in files)[:10] if files else "?"
        wheel = wheel_for(files)
        if wheel is None:
            missing.append(f"{name}=={version} (no cp312 manylinux x86_64 wheel)")
            print(f"{name:<11} {version:<13} {uploaded:<11} none")
            continue
        print(f"{name:<11} {version:<13} {uploaded:<11} {wheel['filename']}")
        print(f"{'':<11} {'':<13} {'':<11} sha256 {wheel['digests']['sha256']}")
        if info.get("yanked"):
            print(f"{'':<11} WARNING: this release is yanked")
    print()
    if missing:
        print("not resolvable from PyPI:")
        for line in missing:
            print(f"  {line}")
        return 1
    print(f"all {len(PACKAGES)} pins exist on PyPI with a linux x86-64 CPython 3.12 wheel")
    return 0


if __name__ == "__main__":
    sys.exit(main())
