"""Capture labelled screenshots of the agent console (Lead task T7.8).

Run from the project root:
    .venv/Scripts/python.exe tests/e2e/capture_agent_screens.py

Uses the same local Edge + DevTools setup as the e2e suite, against the demo
backend. Output: docs/screenshots/agent-*.png (fixture data, not real repairs).
"""

from __future__ import annotations

import base64
import socket
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cdp import find_edge, launch_browser, stop_browser  # noqa: E402
from conftest import start_gui, stop_gui  # noqa: E402
from config import SESSION_TOKEN  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "screenshots"

SHOTS = [
    ("agent-guided.png", "/agent/new?fixture=1", False),
    ("agent-pending.png", "/agent/new?fixture=1&scenario=pending", True),
    ("agent-failure.png", "/agent/new?fixture=1&scenario=failure", True),
    ("agent-success.png", "/agent/new?fixture=1&scenario=success", True),
]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    edge = find_edge()
    if edge is None:
        print("Microsoft Edge is not installed; cannot capture screenshots")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    process, base_url = start_gui(
        {"BINARYREPAIR_BACKEND": "mock", "BINARYREPAIR_SESSION_TOKEN": SESSION_TOKEN}
    )
    browser = None
    session = None
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
            browser, session = launch_browser(edge, _free_port(), Path(profile))
            session.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 1050, "deviceScaleFactor": 1, "mobile": False},
            )
            session.navigate(base_url + "/?token=" + SESSION_TOKEN)

            for name, path, result_tab in SHOTS:
                session.navigate(base_url + path)
                session.wait_js(
                    'document.querySelector(\'[data-testid="agent-stream"]\').textContent.length > 0'
                )
                if result_tab:
                    session.click('[data-testid="agent-tab-result"]')
                    session.wait_js(
                        '!document.querySelector(\'[data-testid="agent-view-result"]\').hidden'
                    )
                time.sleep(0.8)
                data = session.send("Page.captureScreenshot", {"format": "png"})["data"]
                (OUT / name).write_bytes(base64.b64decode(data))
                print(f"saved docs/screenshots/{name}")
    finally:
        if session is not None:
            stop_browser(browser, session)
        stop_gui(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
