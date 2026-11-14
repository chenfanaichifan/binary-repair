"""Browser e2e for the M2 agent console (/agent).

Covers the parts that only exist in the browser:
- guided flow driven by a plan, ending in an explicit user-initiated job creation
  with a real upload (?plan=fixture keeps the plan as placeholder data while the
  POST /jobs and the polling are real);
- pending receipt renders a placeholder instead of obligations / not_run;
- failure renders the reason + advice cards and keeps not_run verbatim;
- success renders the mode badge, the fallback banner, model metadata and the diff.

Fixtures are development scaffolding only (M5's assistant seam is not wired yet).
"""

from __future__ import annotations

import time

from config import SESSION_TOKEN


def _open(page, base_url: str, path: str) -> None:
    page.navigate(base_url + "/?token=" + SESSION_TOKEN)
    page.navigate(base_url + path)


def _click_last(page, testid: str) -> None:
    page.eval_js(
        "(() => {"
        f"var nodes = document.querySelectorAll('[data-testid=\"{testid}\"]');"
        "if (!nodes.length) return false;"
        "nodes[nodes.length - 1].click();"
        "return true;})()"
    )


def test_guided_flow_creates_a_real_job(mock_server, page, tmp_path):
    sample = tmp_path / "sample.elf"
    sample.write_bytes(b"\x7fELF" + b"demo-bytes" * 32)

    _open(page, mock_server, "/agent/new?plan=fixture")
    page.wait_js('document.querySelector(\'[data-testid="agent-dropzone"]\') !== null')
    page.set_file_input('[data-testid="agent-file-input"]', str(sample))

    for index in (1, 2, 3):
        page.wait_js(
            "document.querySelectorAll('[data-testid=\"agent-question-card\"]').length >= "
            + str(index)
        )
        _click_last(page, "agent-question-default")
        _click_last(page, "agent-question-next")

    page.wait_js('document.querySelector(\'[data-testid="agent-review-card"]\') !== null')
    _click_last(page, "agent-create-job")

    page.wait_js('location.pathname.indexOf("/agent/") === 0 && location.pathname !== "/agent/new"', timeout=40)
    page.wait_js(
        'document.querySelector(\'[data-testid="agent-side-phase"]\').textContent !== "—"',
        timeout=30,
    )
    assert "未选择任务" not in page.text('[data-testid="agent-job-chip"]')


def test_pending_receipt_shows_placeholder_not_not_run(mock_server, page):
    _open(page, mock_server, "/agent/new?fixture=1&scenario=pending")
    page.click('[data-testid="agent-tab-result"]')
    page.wait_js('!document.querySelector(\'[data-testid="agent-receipt-placeholder"]\').hidden')
    assert page.eval_js('document.querySelector(\'[data-testid="agent-obligations"]\') === null')
    assert "not_run" not in page.text('[data-testid="agent-diagnostics"]')
    assert "awaiting_ingest" in page.text('[data-testid="agent-side-execution"]')


def test_failure_shows_reason_advice_and_verbatim_not_run(mock_server, page):
    _open(page, mock_server, "/agent/new?fixture=1&scenario=failure")
    page.click('[data-testid="agent-tab-result"]')
    page.wait_js('document.querySelector(\'[data-testid="agent-obligations"]\') !== null')
    assert "测试机缺少必需的环境变量" in page.text('[data-testid="agent-reason-card"]')
    assert "BINARYREPAIR_ORIGINAL" in page.text('[data-testid="agent-advice-card"]')
    assert page.text('[data-testid="agent-obligation-V1"]') == "not_run"
    assert "rejected" in page.text('[data-testid="agent-verdict"]')


def test_success_shows_mode_fallback_metadata_and_diff(mock_server, page):
    _open(page, mock_server, "/agent/new?fixture=1&scenario=success")
    assert "llm" in page.text('[data-testid="agent-mode-badge"]')
    page.wait_js('!document.querySelector(\'[data-testid="agent-fallback"]\').hidden')
    assert "fixture-model-name" in page.text('[data-testid="agent-model-meta"]')

    page.click('[data-testid="agent-tab-result"]')
    page.wait_js('document.querySelector(\'[data-testid="agent-before-after"] pre\') !== null')
    assert "memcpy" in page.text('[data-testid="agent-before-after"]')
    assert "success_within_scope" in page.text('[data-testid="agent-verdict"]')
    assert page.text('[data-testid="agent-obligation-V3"]') == "passed"


def test_live_mode_without_plan_says_so(mock_server, page):
    _open(page, mock_server, "/agent/new?new=1")
    page.wait_js(
        'document.querySelector(\'[data-testid="agent-stream"]\').textContent'
        '.indexOf("计划服务还没接通") >= 0'
    )
    assert "deterministic" in page.text('[data-testid="agent-mode-badge"]')


def test_quick_repair_panel_offers_optional_poc_manifest(mock_server, page, tmp_path):
    """Markup-only e2e: the review card exposes an optional PoC manifest picker.

    The manifest is optional, so the quick-repair button must be usable without
    choosing one; selecting a file only updates a local hint (the request itself
    is covered by the API tests).
    """
    sample = tmp_path / "sample.elf"
    sample.write_bytes(b"\x7fELF" + b"demo-bytes" * 32)

    _open(page, mock_server, "/agent/new?plan=fixture")
    page.wait_js('document.querySelector(\'[data-testid="agent-dropzone"]\') !== null')
    page.set_file_input('[data-testid="agent-file-input"]', str(sample))

    for index in (1, 2, 3):
        page.wait_js(
            "document.querySelectorAll('[data-testid=\"agent-question-card\"]').length >= "
            + str(index)
        )
        _click_last(page, "agent-question-default")
        _click_last(page, "agent-question-next")
    page.wait_js('document.querySelector(\'[data-testid="agent-review-card"]\') !== null')

    selector = '[data-testid="agent-poc-manifest"]'
    assert page.eval_js(
        f'document.querySelector(\'{selector}\').type'
    ) == "file"
    assert ".json" in page.eval_js(f'document.querySelector(\'{selector}\').accept')
    assert page.eval_js(f'document.querySelector(\'{selector}\').required') is False
    assert page.eval_js(
        f'document.querySelector(\'{selector}\').labels[0].textContent'
    ).find("回归用例清单") >= 0
    # The quick-repair action stays available without a manifest.
    assert page.eval_js(
        'document.querySelector(\'[data-testid="agent-quick-repair"]\').disabled'
    ) is False

    manifest = tmp_path / "marcx-capacity.json"
    manifest.write_text('{"schema_version": 1}', encoding="utf-8")
    page.set_file_input(selector, str(manifest))
    page.wait_js(
        'document.querySelector(\'[data-testid="agent-poc-manifest-wrap"]\').textContent'
        '.indexOf("已选择：marcx-capacity.json") >= 0'
    )
