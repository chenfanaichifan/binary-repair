"""P2 acceptance: verify the real execution/verdict pipeline when it exists.

This is the next gate after ``tools/p0_acceptance.py``. It checks that a job that
reached ``finished`` carries honest, complete evidence: a run verdict, both route
outcomes, and the V0-V5 obligation set persisted by the worker. It never executes
a binary itself; execution belongs to the worker/executor in the disposable guest.

Two modes:

Pipeline mode (default) drives the whole journey through the live GUI + controller:
create a job, approve the current contract, start the run, optionally run the
worker once, then wait for ``finished`` and verify the evidence.

Verification-only mode (``--job-id``) skips the journey and verifies an existing
job. This is the mode inherited from ``main``.

Exit codes:
  0  PASS    real execution reached ``finished`` with honest obligations/verdict
  1  FAIL    the pipeline ran but produced an inconsistent/incomplete result
  2  BLOCKED the pipeline is not wired yet (no worker/result bundle; still queued)

Usage:
    python tools/p2_acceptance.py --timeout 180
    python tools/p2_acceptance.py --job-id <id> --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import pathlib
import shlex
import subprocess
import sys
import time
import urllib.request

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
FINAL_PHASES = {"finished"}
VALID_OUTCOMES = {
    "success_within_scope",
    "unsupported",
    "rejected",
    "inconclusive",
    "error",
    "cancelled",
}
# The V0-V5 obligation kinds the worker persists for one attempt.
EXPECTED_OBLIGATION_KINDS = {
    "identity",
    "structure",
    "interface",
    "behaviour",
    "symbolic",
    "reproducibility",
}
FORM = {
    "defect": "strcpy in stack_buf does not check length; overlong input writes out of bounds",
    "valid_tests": "valid: hello\nboundary: 8 bytes",
    "environment": "Ubuntu x86-64 VM (P2 acceptance)",
    "valid_domain": "Input length 0-64 bytes",
    "forbidden": "Out-of-bounds write to the target buffer",
    "invalid_outcome": "Return error code 1 without out-of-bounds access",
    "assumptions": "Single process\nStack protector disabled",
}
PAYLOAD = b"\x7fELF P2 acceptance sample"


def _csrf(token: str) -> str:
    return hmac.new(token.encode("utf-8"), b"gui-csrf", hashlib.sha256).hexdigest()


def _job_id(location: str) -> str:
    return location.rstrip("/").rsplit("/", 1)[-1]


def _session_token(explicit: str) -> str:
    token = explicit.strip()
    if token:
        return token
    token_file = ROOT / "var" / "session.token"
    if not token_file.exists():
        raise FileNotFoundError(str(token_file))
    return token_file.read_text(encoding="utf-8").strip()


def _entity(snapshot: dict, path: str) -> dict:
    """Read a nested JSON object from a snapshot, defaulting to an empty dict."""

    current = snapshot
    for part in path.split("."):
        current = (current or {}).get(part) if isinstance(current, dict) else None
    return current if isinstance(current, dict) else {}


def _wait_for_finished(controller: httpx.Client, job_id: str, timeout: float) -> dict:
    """Poll the controller until the job reports a terminal phase."""

    deadline = time.time() + timeout
    snapshot: dict = {}
    while time.time() < deadline:
        response = controller.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        snapshot = response.json()
        if snapshot.get("phase") in FINAL_PHASES:
            return snapshot
        time.sleep(2.0)
    return snapshot


def _verify_finished_snapshot(snapshot: dict, gui: httpx.Client | None, job_id: str) -> list[str]:
    """Return the list of acceptance failures for a ``finished`` snapshot."""

    errors: list[str] = []
    if snapshot.get("demo") is not False:
        errors.append("snapshot demo is not false")
    if not snapshot.get("verdict"):
        errors.append("snapshot verdict missing")

    for key in ("A", "B"):
        route = _entity(snapshot, f"routes.{key}")
        if route.get("outcome") not in VALID_OUTCOMES:
            errors.append(f"route {key} has no valid outcome: {route.get('outcome')!r}")
        if not route.get("verdict"):
            errors.append(f"route {key} verdict missing")
        obligations = route.get("obligations") or []
        kinds = {item.get("kind") for item in obligations}
        if len(obligations) != len(EXPECTED_OBLIGATION_KINDS):
            errors.append(f"route {key} obligations incomplete: {sorted(kinds)}")
        elif kinds != EXPECTED_OBLIGATION_KINDS:
            errors.append(f"route {key} obligation kinds are not V0-V5: {sorted(kinds)}")
        results = {item.get("result") for item in obligations}
        if not results:
            errors.append(f"route {key} has no obligation results")
        elif "not_run" in results and results == {"not_run"}:
            # All-not_run is an honest state, but it is not a verdict-bearing run:
            # only flag it when the run claims `success_within_scope`.
            if route.get("outcome") == "success_within_scope":
                errors.append(f"route {key} claims success but all obligations are not_run")

    if gui is not None:
        page = gui.get(f"/jobs/{job_id}")
        if "demo-banner" in page.text:
            errors.append("demo banner still visible for a real controller job")

    return errors


def _summary(snapshot: dict) -> dict:
    return {
        "phase": snapshot.get("phase"),
        "verdict": snapshot.get("verdict"),
        "routes": {
            key: {
                "outcome": _entity(snapshot, f"routes.{key}").get("outcome"),
                "obligations": len(_entity(snapshot, f"routes.{key}").get("obligations") or []),
            }
            for key in ("A", "B")
        },
    }


def _run_pipeline(args: argparse.Namespace, token: str) -> int:
    csrf = _csrf(token)
    with httpx.Client(base_url=args.gui, timeout=20.0, follow_redirects=True) as gui, httpx.Client(
        base_url=args.controller, timeout=20.0
    ) as controller:
        if gui.get("/?token=" + token).status_code != 200:
            print("FAIL  GUI session bootstrap failed")
            return 1
        health = controller.get("/healthz")
        if health.status_code != 200 or not health.json().get("ok"):
            print(f"FAIL  controller health check failed (HTTP {health.status_code})")
            return 1

        created = gui.post(
            "/jobs",
            data={**FORM, "csrf": csrf},
            files={"binary": ("p2-acceptance.bin", PAYLOAD, "application/octet-stream")},
            follow_redirects=False,
        )
        if created.status_code != 303:
            print(f"FAIL  create job HTTP {created.status_code}")
            return 1
        job_id = _job_id(created.headers["location"])
        print(f"job={job_id}")

        snapshot = controller.get(f"/api/jobs/{job_id}").json()
        approved = gui.post(
            f"/jobs/{job_id}/approve",
            data={
                "expected_sha256": _entity(snapshot, "contract").get("sha256", ""),
                "reviewer_label": "p2-acceptance",
                "csrf": csrf,
            },
            follow_redirects=False,
        )
        if approved.status_code != 303:
            print(f"FAIL  approval HTTP {approved.status_code}")
            return 1

        started = gui.post(f"/jobs/{job_id}/start", data={"csrf": csrf}, follow_redirects=False)
        if started.status_code != 303:
            print(f"FAIL  start HTTP {started.status_code}")
            return 1

        if args.worker_command:
            command = shlex.split(args.worker_command, posix=True)
            print(f"worker: {' '.join(command)}")
            completed = subprocess.run(
                command,
                cwd=args.worker_cwd or None,
                capture_output=True,
                text=True,
            )
            if completed.stdout.strip():
                print(completed.stdout.strip())
            if completed.stderr.strip():
                print(completed.stderr.strip())
            if completed.returncode != 0:
                print(f"FAIL  worker exited {completed.returncode}")
                return 1

        snapshot = _wait_for_finished(controller, job_id, args.timeout)
        if snapshot.get("phase") not in FINAL_PHASES:
            print(
                "BLOCKED  pipeline did not finish: "
                f"phase={snapshot.get('phase')!r}. The worker may be running, but it needs a "
                "result bundle per attempt (written by the external executor / "
                "BINARYREPAIR_ATTEMPT_CMD), and the controller still has to persist "
                "obligations/verdicts."
            )
            print(json.dumps(_summary(snapshot), indent=2))
            return 2

        errors = _verify_finished_snapshot(snapshot, gui, job_id)
        if errors:
            for error in errors:
                print(f"FAIL  {error}")
            print(json.dumps(_summary(snapshot), indent=2))
            return 1

        print(json.dumps(_summary(snapshot), indent=2))
        print(f"P2 ACCEPTANCE PASSED  phase={snapshot.get('phase')} job={job_id}")
        return 0


def _run_verification_only(args: argparse.Namespace) -> int:
    base_url = args.base_url or args.controller

    def _get(path: str) -> dict:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    deadline = time.monotonic() + args.timeout
    while True:
        snapshot = _get(f"/api/jobs/{args.job_id}")
        if snapshot.get("phase") in FINAL_PHASES:
            break
        if time.monotonic() >= deadline:
            print(f"p2_acceptance: job {args.job_id} did not finish", file=sys.stderr)
            print(json.dumps(_summary(snapshot), indent=2))
            return 1
        time.sleep(args.poll)

    errors = _verify_finished_snapshot(snapshot, None, args.job_id)
    print(json.dumps(_summary(snapshot), indent=2))
    if errors:
        for error in errors:
            print(f"p2_acceptance: {error}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P2 acceptance for the real pipeline")
    parser.add_argument("--gui", default="http://127.0.0.1:8123")
    parser.add_argument("--controller", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default="")
    parser.add_argument("--timeout", type=float, default=180.0, help="seconds to wait for finished")
    parser.add_argument("--poll", type=float, default=2.0, help="poll interval in seconds")
    parser.add_argument(
        "--worker-command",
        default="",
        help="optional one-shot worker command (for example: python -m app.services.worker --data-dir <dir> --once)",
    )
    parser.add_argument("--worker-cwd", default="", help="working directory for the worker command")
    parser.add_argument(
        "--job-id",
        default="",
        help="verify an existing job instead of driving a new pipeline run",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="controller base URL for verification-only mode (defaults to --controller)",
    )
    args = parser.parse_args(argv)

    if args.job_id:
        return _run_verification_only(args)

    try:
        token = _session_token(args.token)
    except FileNotFoundError as exc:
        print(f"BLOCKED  session token not found: {exc}")
        return 2
    return _run_pipeline(args, token)


if __name__ == "__main__":
    raise SystemExit(main())
