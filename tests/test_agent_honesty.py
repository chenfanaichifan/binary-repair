"""Honesty guarantees for the M2 console and report.

Incremental to ``tests/test_agent_console.py``: that file pins the shell and the
M2 boundary; this file pins the claims the UI makes about evidence itself.

The rule under test: the console renders what the acceptance engine produced and
never upgrades it. An empty obligation table is not a pass, a pending receipt is
not ``not_run``, round-trip preservation is not repair evidence, and an
unreported outcome is not rewritten.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.evidence_domains import evidence_domain
from app.main import CSRF_TOKEN, SESSION_TOKEN, app

BASE_DIR = Path(__file__).resolve().parents[1]
AGENT_JS = (BASE_DIR / "app" / "static" / "js" / "agent.js").read_text(encoding="utf-8")
REPORT_HTML = (BASE_DIR / "app" / "templates" / "report.html").read_text(encoding="utf-8")
EVIDENCE_HTML = (BASE_DIR / "app" / "templates" / "evidence.html").read_text(encoding="utf-8")

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def _create_job() -> str:
    created = client.post(
        "/jobs",
        data={
            "defect": "strcpy in stack_buf does not check length; overlong input writes out of bounds",
            "valid_tests": "valid: hello\nboundary: 8 bytes",
            "environment": "Ubuntu x86-64 VM (test: execution disabled)",
            "valid_domain": "Input length 0-64 bytes",
            "forbidden": "Out-of-bounds write to the target buffer",
            "invalid_outcome": "Return error code 1 without out-of-bounds access",
            "assumptions": "Single process",
            "csrf": CSRF_TOKEN,
        },
        files={"binary": ("sample.bin", b"\x7fELF demo bytes", "application/octet-stream")},
        follow_redirects=False,
    )
    assert created.status_code == 303
    return created.headers["location"].rstrip("/").rsplit("/", 1)[-1]


def test_empty_obligation_table_is_not_a_pass():
    """No obligations means "the backend did not provide them", never "passed"."""
    empty_branch = AGENT_JS.split("if (!view.obligations.length)", 1)
    assert len(empty_branch) == 2, "the empty-table branch must exist"
    head, tail = empty_branch[0], empty_branch[1][:400]
    assert "后端未提供义务结果" in tail
    for banned in ("通过", "满足", "已修复"):
        assert banned not in tail, banned


def test_pending_receipt_never_renders_not_run():
    # The diagnostics table bails out while pending, and the failure card is
    # gated on a received result, so neither can invent a not_run row.
    assert "if (view.receiptPending) return;" in AGENT_JS
    assert "if (failed && !view.receiptPending)" in AGENT_JS
    assert "未回传：只显示占位，不渲染 not_run" in AGENT_JS
    # The placeholder is what the user sees, not an obligation result.
    assert 'show("agent-receipt-placeholder", view.receiptPending)' in AGENT_JS


def test_console_only_writes_through_the_create_job_form():
    """The console has no approve/start/verdict write path."""
    assert AGENT_JS.count('xhr.open("POST"') == 1
    assert 'xhr.open("POST", "/jobs")' in AGENT_JS
    for banned in ('"/approve"', '"/start"', '"/api/verdict', '"/attempts/retry"'):
        assert banned not in AGENT_JS, banned


def test_round_trip_is_not_repair_credit():
    round_trip = evidence_domain("round_trip")
    repaired = evidence_domain("repaired_behaviour")
    assert round_trip["repair_credit"] is False
    assert repaired["repair_credit"] is True
    # Both are binary-level execution, so the level alone must not imply credit.
    assert round_trip["level"] == repaired["level"] == "binary"


def test_round_trip_label_from_producer_resolves_to_the_same_domain():
    for label in ("Round-trip behaviour", "round trip behavior", "round_trip"):
        domain = evidence_domain(label)
        assert domain["label_en"] == "Round-trip behaviour", label
        assert domain["repair_credit"] is False, label


def test_unknown_kind_stays_unclassified():
    domain = evidence_domain("totally-new-check")
    assert domain["level"] == "unknown"
    assert domain["repair_credit"] is False
    assert domain["label_zh"] == "未分类证据"


def test_evidence_page_labels_every_row_with_its_level():
    job_id = _create_job()
    page = client.get(f"/jobs/{job_id}/evidence")
    assert page.status_code == 200
    assert "证据域" in page.text
    rows = [
        line for line in page.text.splitlines()
        if "data-evidence-level=" in line
    ]
    assert rows, "the evidence table must mark each row with its level"
    for line in rows:
        assert 'data-evidence-level="unknown"' not in line, line


def test_report_does_not_rewrite_missing_outcome():
    assert "none (not reported by the controller)" in REPORT_HTML
    assert 'or "not_run"' not in REPORT_HTML
    assert "an empty table is not a pass" in REPORT_HTML


def test_evidence_template_marks_unknown_separately():
    assert "data-evidence-level=\"{{ domain.level }}\"" in EVIDENCE_HTML
    assert "未分类证据" in EVIDENCE_HTML or "domain.label_zh" in EVIDENCE_HTML
