"""Real GUI end-to-end verification for the capacity-check quick-repair path.

Starts the real FastAPI app on a spare loopback port, drives headless Chrome over
the repo's CDP helpers, uploads the marcx fixture plus the PoC/regression
manifest through the /agent quick-repair card, and captures:

- ``repair-review-response.json``: direct API response for the same files.
- ``agent-quick-result.png``: the rendered result card (checks + chips + download).
- ``agent-review-card.png``: the review card with the optional manifest picker.

Run from the repo root:
    .venv/bin/python artifacts/marcx-capacity-gui-2026-11-14/verify_gui_capacity.py
"""

from __future__ import annotations

import base64
import json
import socket
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
E2E = ROOT / "tests" / "e2e"
sys.path.insert(0, str(E2E))

import httpx  # noqa: E402

from cdp import find_edge, launch_browser, stop_browser  # noqa: E402
from conftest import start_gui, stop_gui  # noqa: E402
from config import SESSION_TOKEN  # noqa: E402

MARCX = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"
MANIFEST = ROOT / "fixtures" / "poc" / "marcx-capacity.json"
DATA_DIR = HERE / "_var"
RESPONSE_PATH = HERE / "repair-review-response.json"
SCREENSHOT_RESULT = HERE / "agent-quick-result.png"
SCREENSHOT_REVIEW = HERE / "agent-review-card.png"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _shot(session, path: Path) -> None:
    # Capture the current viewport after scrollIntoView so the evidence shows
    # the card under test, not the top of the document.
    session.send(
        "Emulation.setDeviceMetricsOverride",
        {"width": 1440, "height": 1400, "deviceScaleFactor": 1, "mobile": False},
    )
    data = session.send("Page.captureScreenshot", {"format": "png"})["data"]
    path.write_bytes(base64.b64decode(data))


def _direct_api(base_url: str) -> dict:
    """POST the same files to /api/binary/repair-review and record the JSON."""
    with httpx.Client(base_url=base_url, follow_redirects=True, timeout=180.0) as client:
        client.get("/?token=" + SESSION_TOKEN)
        page = client.get("/agent/new?plan=fixture")
        csrf = page.headers.get("x-csrf-token", "")
        if not csrf:
            # Pages carry the token in the app root for JS; fall back to it.
            marker = 'data-csrf="'
            start = page.text.find(marker)
            end = page.text.find('"', start + len(marker))
            csrf = page.text[start + len(marker):end]
        response = client.post(
            "/api/binary/repair-review",
            files={
                "binary": (MARCX.name, MARCX.read_bytes(), "application/octet-stream"),
                "poc_manifest": (MANIFEST.name, MANIFEST.read_bytes(), "application/json"),
            },
            data={"csrf": csrf, "ai_review": "0"},
            timeout=180.0,
        )
        payload = response.json()
        RESPONSE_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"direct API HTTP {response.status_code} -> {RESPONSE_PATH}")
        return payload


def _summarize_api(payload: dict) -> str:
    decision = payload.get("decision") or {}
    verification = payload.get("verification") or {}
    scope = verification.get("scope") or {}
    checks = verification.get("checks") or []
    lines = [
        f"decision.success={decision.get('success')} outcome={decision.get('outcome')}",
        f"report.strategy={(payload.get('report') or {}).get('strategy')} "
        f"mode={(payload.get('report') or {}).get('mode')}",
        f"scope.runtime_tier={scope.get('runtime_tier')} "
        f"scope.runtime_verdict={scope.get('runtime_verdict')}",
        "checks: " + ", ".join(f"{c.get('id')}={c.get('status')}" for c in checks),
        f"download_allowed={payload.get('download_allowed')} "
        f"patched_base64_present={bool(payload.get('patched_base64'))}",
    ]
    return "\n".join(lines)


def main() -> int:
    browser_path = find_edge()
    if browser_path is None:
        print("no Chrome/Chromium/Edge found")
        return 1
    for path in (MARCX, MANIFEST):
        if not path.exists():
            print(f"missing fixture: {path}")
            return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    process, base_url = start_gui(
        {
            "BINARYREPAIR_BACKEND": "mock",
            "BINARYREPAIR_SESSION_TOKEN": SESSION_TOKEN,
            "BINARYREPAIR_DATA_DIR": str(DATA_DIR),
        }
    )
    browser = None
    session = None
    try:
        payload = _direct_api(base_url)
        print(_summarize_api(payload))

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
            browser, session = launch_browser(browser_path, _free_port(), Path(profile))
            session.send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": 1440,
                    "height": 1200,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            session.navigate(base_url + "/?token=" + SESSION_TOKEN)
            session.navigate(base_url + "/agent/new?plan=fixture")
            session.wait_js(
                'document.querySelector(\'[data-testid="agent-dropzone"]\') !== null'
            )
            session.set_file_input('[data-testid="agent-file-input"]', str(MARCX))

            for index in (1, 2, 3):
                session.wait_js(
                    "document.querySelectorAll('[data-testid=\"agent-question-card\"]').length >= "
                    + str(index),
                    timeout=40,
                )
                session.eval_js(
                    "(() => {var n=document.querySelectorAll('[data-testid=\"agent-question-default\"]');"
                    "if(n.length) n[n.length-1].click(); return true;})()"
                )
                session.eval_js(
                    "(() => {var n=document.querySelectorAll('[data-testid=\"agent-question-next\"]');"
                    "if(n.length) n[n.length-1].click(); return true;})()"
                )

            session.wait_js(
                'document.querySelector(\'[data-testid="agent-review-card"]\') !== null',
                timeout=40,
            )
            session.wait_js(
                'document.querySelector(\'[data-testid="agent-poc-manifest"]\') !== null'
            )
            session.set_file_input(
                '[data-testid="agent-poc-manifest"]', str(MANIFEST)
            )
            session.wait_js(
                'document.querySelector(\'[data-testid="agent-poc-manifest-wrap"]\').textContent'
                '.indexOf("已选择：") >= 0'
            )
            session.eval_js(
                "document.querySelector('[data-testid=\"agent-review-card\"]')"
                ".scrollIntoView({block: 'start'}); true"
            )
            time.sleep(0.4)
            _shot(session, SCREENSHOT_REVIEW)
            print(f"saved {SCREENSHOT_REVIEW}")

            session.click('[data-testid="agent-quick-repair"]')
            session.wait_js(
                'document.querySelector(\'[data-testid="agent-quick-result"]\') !== null',
                timeout=240,
            )
            # Wait until the card carries its final title/check table.
            session.wait_js(
                "(() => {var c=document.querySelector('[data-testid=\"agent-quick-result\"]');"
                "if(!c) return false;"
                "return c.querySelectorAll('.repair-checks tbody tr').length > 0;})()",
                timeout=240,
            )
            result = {
                "card_text": session.eval_js(
                    "document.querySelector('[data-testid=\"agent-quick-result\"]').textContent"
                ),
                "check_ids": session.eval_js(
                    "(Array.from(document.querySelectorAll('[data-testid=\"agent-quick-result\"] .repair-checks tbody tr'))"
                    ".map(function(row){return row.dataset.checkId + '=' + (row.querySelector('.repair-check-status')||{}).textContent;}))"
                ),
                "strategy_chip": session.eval_js(
                    "(function(){var c=document.querySelector('[data-testid=\"agent-quick-result\"]');"
                    "var m=c && c.querySelector('.repair-meta'); return m ? m.textContent : '';})()"
                ),
                "download_href": session.eval_js(
                    "(function(){var a=document.querySelector('[data-testid=\"agent-quick-download\"]');"
                    "return a ? a.getAttribute('href').slice(0, 64) + '…' : null;})()"
                ),
            }
            session.eval_js(
                "document.querySelector('[data-testid=\"agent-quick-result\"]')"
                ".scrollIntoView({block: 'start'}); true"
            )
            time.sleep(0.4)
            _shot(session, SCREENSHOT_RESULT)
            print(f"saved {SCREENSHOT_RESULT}")
            print("GUI check ids:", result["check_ids"])
            print("GUI chips:", result["strategy_chip"])
            print("GUI download present:", result["download_href"] is not None)
            (HERE / "gui-assertions.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            success = (payload.get("decision") or {}).get("success") is True
            checks = {
                (c.get("id"), c.get("status"))
                for c in (payload.get("verification") or {}).get("checks") or []
            }
            required = {
                ("patch.capacity", "passed"),
                ("runtime.evidence", "passed"),
                ("runtime.tier", "passed"),
                ("runtime.contract", "passed"),
            }
            if not success or not required.issubset(checks):
                print("FAIL: gate did not succeed with the expected capacity checks")
                return 2
            if result["download_href"] is None:
                print("FAIL: success but no download link rendered")
                return 3
            print("PASS: decision.success=true, capacity checks passed, download rendered")
    finally:
        if session is not None:
            stop_browser(browser, session)
        stop_gui(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
