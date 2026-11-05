#!/usr/bin/env python3
"""Guest-side V3 behaviour observer. GUEST ONLY. Stdlib only.

Runs one binary against the frozen test manifests and records what it did, as
raw bytes. It judges nothing: the host feeds the observations to
``tests/v3_oracle.py``, which is a pure function (AGENTS.md: the guest is an
untrusted data source; only the host decides a verdict).

Why a copy of the binary named after ``argv[0]``: the manifests are written as
``["./original", "<input>"]``. Reproducing that exactly (same basename, cwd =
scratch dir) is what makes the observation comparable to the frozen record.

Usage (inside the guest, as root):

    python3 guest_behaviour.py \
        --binary /var/lib/binrepair/jobs/demo/original.elf \
        --tests-dir /var/lib/binrepair/jobs/demo/tests \
        --work /var/tmp/behaviour/original \
        --out /var/tmp/behaviour/original-observations.json \
        --guest-ack

Exit codes: 0 observations written; 2 refusal; 3 bad input; 4 a case could not
be executed (the observation for that case is recorded as absent).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

CASE_TIMEOUT_SECONDS = 30
PER_CASE_OUTPUT_LIMIT = 1 << 20  # 1 MiB, matches tech_stack's concrete-test cap


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def refuse(reason: str) -> None:
    print(f"guest_behaviour: refusing: {reason}", file=sys.stderr)
    raise SystemExit(2)


def guard_guest(ack: bool) -> None:
    if not ack:
        refuse("pass --guest-ack; this runner executes a binary and is guest-only")
    sysname = platform.system()
    if sysname != "Linux":
        refuse(f"platform is {sysname!r}, not Linux; the host never executes binaries")
    if os.geteuid() != 0:
        refuse(f"euid={os.geteuid()}; run as root so the scratch dir can be reset")


def load_cases(tests_dir: Path) -> list[dict]:
    cases: list[dict] = []
    for name in ("valid.json", "invalid.json"):
        path = tests_dir / name
        if not path.is_file():
            raise SystemExit(f"guest_behaviour: manifest missing: {path}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("schema_version") != 1:
            raise SystemExit(f"guest_behaviour: unsupported schema in {name}")
        for case in doc.get("tests", []):
            case = dict(case)
            case["_manifest"] = name
            cases.append(case)
    if not cases:
        raise SystemExit("guest_behaviour: no cases in the manifests")
    return cases


def run_case(binary_dest: Path, work: Path, case: dict) -> dict:
    """Execute one case and return its raw observation."""
    argv = list(case.get("argv") or [])
    if not argv:
        return {"case_id": case["id"], "error": "manifest case has no argv"}
    # argv[0] is "./original"; the binary is placed under that exact name.
    recorded = {"case_id": case["id"], "kind": case.get("kind"),
                "argv": argv}

    try:
        proc = subprocess.run(
            argv, cwd=str(work), capture_output=True,
            timeout=CASE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {**recorded, "error": f"timed out after {CASE_TIMEOUT_SECONDS}s"}
    except Exception as exc:  # noqa: BLE001
        return {**recorded, "error": f"{type(exc).__name__}: {exc}"}

    # Normalise a signal death to the shell convention (128+N), which is how the
    # fixture provenance records the 100-byte crash (exit 139 = 128 + SIGSEGV).
    rc = proc.returncode
    signal_name = None
    if rc < 0:
        signal_name = f"SIG{-rc}"
        rc = 128 + (-rc)

    out, err = proc.stdout or b"", proc.stderr or b""
    return {
        **recorded,
        "return_code": rc,
        "signal": signal_name,
        "stdout_hex": out[:PER_CASE_OUTPUT_LIMIT].hex(),
        "stderr_hex": err[:PER_CASE_OUTPUT_LIMIT].hex(),
        "stdout_len": len(out),
        "stderr_len": len(err),
        "output_files": {},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Guest-side V3 behaviour observer")
    ap.add_argument("--binary", required=True, type=Path)
    ap.add_argument("--tests-dir", required=True, type=Path)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--guest-ack", action="store_true")
    args = ap.parse_args(argv)

    guard_guest(args.guest_ack)

    if not args.binary.is_file():
        print(f"guest_behaviour: binary not found: {args.binary}", file=sys.stderr)
        return 3
    if not args.tests_dir.is_dir():
        print(f"guest_behaviour: tests dir not found: {args.tests_dir}", file=sys.stderr)
        return 3

    cases = load_cases(args.tests_dir)

    # Fresh scratch dir per run: a stale artefact must never look like this run.
    shutil.rmtree(args.work, ignore_errors=True)
    args.work.mkdir(parents=True, exist_ok=True)

    # Place the binary under the basename the manifest expects ("./original").
    basename = os.path.basename(cases[0]["argv"][0])
    dest = args.work / basename
    shutil.copyfile(args.binary, dest)
    os.chmod(dest, 0o755)

    records = [run_case(dest, args.work, c) for c in cases]

    payload = {
        "schema_version": 1,
        "binary_sha256": sha256_file(args.binary),
        "binary_size": args.binary.stat().st_size,
        "binary_basename": basename,
        "tests_dir": str(args.tests_dir),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "cases": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    executed = sum(1 for r in records if "error" not in r)
    print(json.dumps({"out": str(args.out), "cases": len(records),
                      "executed": executed, "binary_sha256": payload["binary_sha256"]},
                     indent=2))
    for r in records:
        if "error" in r:
            print(f"  UNEXECUTED {r['case_id']}: {r['error']}", file=sys.stderr)
    return 0 if executed == len(records) else 4


if __name__ == "__main__":
    raise SystemExit(main())
