"""P2 acceptance: verify the real execution/verdict pipeline when it exists.

This is the next gate after `tools/p0_acceptance.py`. It creates a job, approves
it, starts it, and then waits for the controller to advance beyond `queued` and
persist real obligations/verdicts.

Exit codes:
  0  PASS   real execution reached `finished` with honest obligations/outcome
  1  FAIL   the pipeline ran but produced an inconsistent/honest failure
  2  BLOCKED the pipeline is not wired yet (no worker entry / still queued)

Usage:
    .\.venv\Scripts\python.exe tools\p2_acceptance.py --timeout 180
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import pathlib
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]

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
FINAL_PHASES = {"finished"}
VALID_OUTCOMES = {
    "success_within_scope",
    "unsupported",
    "rejected",
    "inconclusive",
    "error",
    "cancelled",
}


def _csrf(token: str) -> str:
    return hmac.new(token.encode("utf-8"), b"gui-csrf", hashlib.sha256).hexdigest()


def _job_id(location: str) -> str:
    return location.rstrip("/").rsplit("/", 1)[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="P2 acceptance for the real pipeline")
    parser.add_argument("--gui", default="http://127.0.0.1:8123")
    parser.add_argument("--controller", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default="")
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait for finished")
    args = parser.parse_args()

    token = args.token.strip()
    if not token:
        token_file = ROOT / "var" / "session.token"
        if not token_file.exists():
            print(f"BLOCKED  session token not found: {token_file}")
            return 2
        token = token_file.read_text(encoding="utf-8").strip()
    csrf = _csrf(token)

    with httpx.Client(base_url=args.gui, timeout=20.0, follow_redirects=True) as gui, httpx.Client(
        base_url=args.controller, timeout=20.0
    ) as controller:
        if gui.get("/?token=" + token).status_code != 200:
            print("FAIL  GUI session bootstrap failed")
            return 1
        if controller.get("/healthz").status_code != 200:
            print("FAIL  controller health check failed")
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
                "expected_sha256": snapshot["contract"]["sha256"],
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

        deadline = time.time() + args.timeout
        last_phase = None
        while time.time() < deadline:
            snapshot = controller.get(f"/api/jobs/{job_id}").json()
            last_phase = snapshot.get("phase")
            if last_phase in FINAL_PHASES:
                break
            time.sleep(2.0)

        if last_phase not in FINAL_PHASES:
            print(
                "BLOCKED  pipeline did not finish: "
                f"phase={last_phase!r}. Member 1 integration gaps: "
                "no worker entry (orchestration is a library), controller API not wired to "
                "evaluate_attempt/evaluate_run, no obligations write path."
            )
            return 2

        obligations = controller.get(f"/api/jobs/{job_id}/obligations")
        if obligations.status_code != 200:
            print(f"FAIL  obligations HTTP {obligations.status_code}")
            return 1
        data = obligations.json()
        results = [item.get("result") for route in ("A", "B") for item in data.get(route, [])]
        if not results:
            print("FAIL  obligations are empty after finished")
            return 1
        if all(result == "not_run" for result in results):
            print("FAIL  finished job still has only not_run obligations (verdict not persisted)")
            return 1

        outcomes = [route.get("outcome") for route in snapshot.get("routes", {}).values()]
        if not all(outcome in VALID_OUTCOMES for outcome in outcomes):
            print(f"FAIL  missing/invalid route outcomes: {outcomes}")
            return 1

        page = gui.get(f"/jobs/{job_id}")
        if "demo-banner" in page.text:
            print("FAIL  demo banner still visible for a real controller job")
            return 1

        print(f"P2 ACCEPTANCE PASSED  phase={last_phase} outcomes={outcomes}")
        print(f"job={job_id}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
