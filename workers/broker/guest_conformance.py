#!/usr/bin/env python3
"""Guest-side conformance runner (VMer task-15). GUEST ONLY. Stdlib only.

Deliberately dumb: it receives the case matrix as JSON, runs each fixed argv,
and records what happened. It judges nothing — the verdict is computed on the
host by ``workers.broker.conformance.evaluate``, because the guest is an
untrusted data source (AGENTS.md §4).

It refuses to run anywhere but the disposable Linux guest, because the host
must never execute a binary (AGENTS.md §3).

Usage (inside the guest, as root):

    python3 guest_conformance.py \
        --executor /var/tmp/conformance/jobwrap-gate5 \
        --matrix /var/tmp/conformance/matrix.json \
        --repo /srv/binrepair \
        --work /var/tmp/conformance/work \
        --routea-work /var/lib/binrepair/jobs/demo/route_a \
        --snapshot-uid 11 --snapshot-name gate4-harness \
        --out /var/tmp/conformance/evidence.json \
        --guest-ack

Exit codes: 0 evidence written; 2 refusal (wrong platform / not root / bad
args); 3 the executor or matrix is unreadable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

CASE_TIMEOUT_SECONDS = 300


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def refuse(reason: str) -> None:
    print(f"guest_conformance: refusing: {reason}", file=sys.stderr)
    raise SystemExit(2)


def guard_guest(ack: bool) -> None:
    if not ack:
        refuse("pass --guest-ack; this runner must only be used in the guest")
    sysname = platform.system()
    if sysname != "Linux":
        refuse(f"platform is {sysname!r}, not Linux; the host never executes binaries")
    if os.geteuid() != 0:
        refuse(f"euid={os.geteuid()}; the fixed-argv executor requires root")


def discover_modes(executor: Path) -> list[str]:
    """Probe the binary's own usage text for the modes it ships.

    A mode the binary does not have cannot be conformed; recording the real set
    lets the host mark those cases inconclusive instead of failed.
    """
    try:
        out = subprocess.run([str(executor)], capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    text = (out.stderr or "") + (out.stdout or "")
    return [t for t in ("probe", "routea", "gate3", "gate4", "gate5") if t in text]


def load_attestation(workdir: Path, case_id: str) -> dict | None:
    """Read an attestation the wrapper wrote. Never synthesise one."""
    for candidate in (workdir / f"{case_id}.attestation.json", workdir / "attestation.json"):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


def run_case(executor: Path, case: dict, repo: str, work: str,
             routea_work: str | None) -> dict:
    argv = [str(executor), *[t.replace("<repo>", repo).replace("<work>", work)
                             for t in case["argv"]]]
    record: dict = {"id": case["id"], "argv": argv}

    # A case that needs a prepared job is skipped when there is none, rather
    # than being run into a guaranteed refusal and reported as a failure.
    if case.get("requires_job"):
        target = Path(routea_work) if routea_work else None
        # The wrapper reads the candidate from <work-dir>/route_a/candidate.elf.
        if target is None or not (target / "route_a" / "candidate.elf").is_file():
            record.update({"rc": None, "stderr": "", "stdout": "", "attestation": None,
                           "skipped_reason": "no prepared candidate for the job"})
            return record

    # Some refusals are only observable as a non-root user.
    preexec = None
    run_uid = case.get("run_as_uid")
    if run_uid:
        def preexec() -> None:  # noqa: E306 - local, single use
            os.setgid(run_uid)
            os.setuid(run_uid)

    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=CASE_TIMEOUT_SECONDS, preexec_fn=preexec)
        record["rc"] = proc.returncode
        record["stderr"] = proc.stderr or ""
        record["stdout"] = proc.stdout or ""
    except subprocess.TimeoutExpired:
        record.update({"rc": None, "stderr": "", "stdout": "",
                       "skipped_reason": f"timed out after {CASE_TIMEOUT_SECONDS}s"})
        return record
    except Exception as exc:  # noqa: BLE001
        record.update({"rc": None, "stderr": "", "stdout": "",
                       "skipped_reason": f"{type(exc).__name__}: {exc}"})
        return record

    # A routea run writes its attestation into the job's configured work-dir,
    # not the runner's scratch dir, so look in the right place.
    if case.get("expect_isolation"):
        att_dir = routea_work if (case.get("requires_mode") == "routea" and routea_work) else work
        record["attestation"] = load_attestation(Path(att_dir), case["id"])
    else:
        record["attestation"] = None
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Guest-side conformance runner (stdlib only)")
    ap.add_argument("--executor", required=True, type=Path)
    ap.add_argument("--matrix", required=True, type=Path,
                    help="case matrix JSON, produced on the host by "
                         "python -m workers.broker.conformance --dump-matrix")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--routea-work", default=None,
                    help="work-dir the routea mode uses (from routea.conf)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--snapshot-uid", required=True, type=int)
    ap.add_argument("--snapshot-name", required=True)
    ap.add_argument("--original-jobwrap", type=Path)
    ap.add_argument("--guest-ack", action="store_true")
    args = ap.parse_args(argv)

    guard_guest(args.guest_ack)

    if not args.executor.is_file():
        print(f"guest_conformance: executor not found: {args.executor}", file=sys.stderr)
        return 3
    if not args.matrix.is_file():
        print(f"guest_conformance: matrix not found: {args.matrix}", file=sys.stderr)
        return 3

    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    if not isinstance(matrix, list) or not matrix:
        print("guest_conformance: matrix is empty or not a list", file=sys.stderr)
        return 3

    Path(args.work).mkdir(parents=True, exist_ok=True)

    started = now()
    records = [run_case(args.executor, c, args.repo, args.work, args.routea_work)
               for c in matrix]
    finished = now()

    window = {
        "snapshot_uid": args.snapshot_uid,
        "snapshot_name": args.snapshot_name,
        "started_at": started,
        "finished_at": finished,
        "executor_sha256": sha256_file(args.executor),
        "original_jobwrap_sha256": (
            sha256_file(args.original_jobwrap)
            if args.original_jobwrap and args.original_jobwrap.is_file() else None
        ),
        "available_modes": discover_modes(args.executor),
        "kernel": platform.release(),
        "python": platform.python_version(),
    }

    args.out.write_text(
        json.dumps({"schema_version": 1, "window": window, "cases": records},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"evidence": str(args.out), "cases": len(records),
                      "available_modes": window["available_modes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
