"""Agent console (/agent) — M2 GUI owner, Lead record 86 / tasks T7.4-T7.8.

These tests pin the M2 boundary rather than backend behaviour:
- the shell renders and stays behind the local session + host gate;
- the console never declares a repair verdict by itself;
- obligations are rendered verbatim and "not_run" is not shown while the
  execution result has not been received (placeholder instead);
- no model calls, no new write endpoints, no SSE/WebSocket, no frameworks;
- UI copy is Chinese while every fixture value bound for submission is ASCII;
- the pre-existing pages and the original landing CTA keep working.
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app

BASE_DIR = Path(__file__).resolve().parents[1]
AGENT_JS = (BASE_DIR / "app" / "static" / "js" / "agent.js").read_text(encoding="utf-8")
AGENT_FIXTURES = (BASE_DIR / "app" / "static" / "js" / "agent.fixtures.js").read_text(encoding="utf-8")
AGENT_TEMPLATE = (BASE_DIR / "app" / "templates" / "agent.html").read_text(encoding="utf-8")

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def test_agent_shell_renders():
    response = client.get("/agent/new?fixture=1")
    assert response.status_code == 200
    for testid in (
        "agent-root",
        "agent-stream",
        "agent-composer",
        "agent-input",
        "agent-mode-badge",
        "agent-fallback",
        "agent-model-meta",
        "agent-side-execution",
        "agent-side-artifacts",
        "agent-timeline",
        "agent-before-after",
        "agent-diagnostics",
        "agent-downloads",
        "agent-receipt-placeholder",
        "agent-switch-form",
    ):
        assert f'data-testid="{testid}"' in response.text, testid
    assert "修复任务" in response.text
    assert 'data-fixture="1"' in response.text


def test_agent_fixture_mode_keeps_demo_banner():
    response = client.get("/agent/new?fixture=1")
    assert "演示数据" in response.text
    assert "未执行真实修复" in response.text


def test_agent_live_mode_is_not_marked_as_fixture():
    response = client.get("/agent/new")
    assert response.status_code == 200
    assert 'data-fixture="0"' in response.text


def test_agent_shell_requires_session():
    anonymous = TestClient(app, base_url="http://127.0.0.1")
    response = anonymous.get("/agent", headers={"accept": "text/html"})
    assert response.status_code == 401


def test_agent_shell_enforces_host_check():
    response = client.get("/agent", headers={"host": "evil.example"})
    assert response.status_code == 403


def test_agent_static_assets_are_served():
    for path in (
        "/static/css/agent.css",
        "/static/js/agent.js",
        "/static/js/agent.fixtures.js",
    ):
        assert client.get(path).status_code == 200, path


def test_console_never_declares_success_by_itself():
    """No copy in which the assistant or the UI claims a repair succeeded."""
    for source in (AGENT_TEMPLATE, AGENT_JS):
        for banned in ("AI 判定修复成功", "修复成功！", "我已修复", "补丁已验证通过"):
            assert banned not in source
    # The verdict line is sourced from the backend verdict only.
    assert "view.verdict && view.verdict.outcome" in AGENT_JS
    assert "结论：尚无 verdict（等待验收引擎）" in AGENT_JS


def test_obligations_are_rendered_verbatim():
    """not_run stays not_run: no label mapping on obligation results."""
    assert 'el("span", "agent-result-value", item.result)' in AGENT_JS
    assert '"not_run"' in AGENT_FIXTURES


def test_pending_receipt_shows_placeholder_instead_of_not_run():
    assert "等待执行结果回传" in AGENT_TEMPLATE
    assert "if (view.receiptPending) return;" in AGENT_JS
    assert 'show("agent-receipt-placeholder", view.receiptPending);' in AGENT_JS


def test_no_model_calls_or_new_transport():
    # Actual usage is banned (mentioning the rule in comments is fine).
    for banned in ("api.openai.com", "new WebSocket", "new EventSource", "Bearer ",
                   'setRequestHeader("Authorization'):
        assert banned not in AGENT_JS, banned
    # Read paths: the snapshot and the job-less plan route (same-origin only).
    assert AGENT_JS.count("fetch(") == 2
    assert 'fetch("/api/jobs/" + encodeURIComponent(state.jobId)' in AGENT_JS
    assert 'fetch("/api/assistant/plan"' in AGENT_JS
    # Write path: the existing create-job form endpoint only, with CSRF.
    assert 'xhr.open("POST", "/jobs")' in AGENT_JS
    assert 'form.append("csrf", CSRF)' in AGENT_JS
    assert "assistant_plans" not in AGENT_JS


def test_job_creation_is_an_explicit_user_action():
    """The assistant must not auto-submit: creation is bound to a button click."""
    assert 'create.addEventListener("click", function () { createJob(' in AGENT_JS
    assert "创建任务（由你确认）" in AGENT_JS


def test_fixture_defaults_bound_for_submission_are_ascii():
    """UI copy is Chinese; values that enter the payload must stay ASCII."""
    defaults = re.findall(r'default:\s*"((?:[^"\\]|\\.)*)"', AGENT_FIXTURES)
    assert defaults, "expected fixture default answers"
    for value in defaults:
        assert value.isascii(), value


def test_fixture_file_is_labelled_as_placeholder():
    assert "FIXTURE ONLY" in AGENT_FIXTURES
    assert "fixture_only: true" in AGENT_FIXTURES
    assert "execution-bridge-v1" in AGENT_FIXTURES


def test_unknown_reason_code_is_not_guessed():
    assert "未登记，请把 status.json 发给 M1/M4" in AGENT_JS


def test_landing_offers_console_without_breaking_original_cta():
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-testid="landing-cta"' in response.text
    assert 'href="/jobs/new"' in response.text
    assert 'data-testid="landing-agent-cta"' in response.text
    assert 'href="/agent?' in response.text
    # T7.8: the console is the primary entry; the form is the fallback.
    assert 'data-primary="1"' in response.text
    assert response.text.index('data-testid="landing-agent-cta"') < response.text.index(
        'data-testid="landing-cta"'
    )


def test_existing_setup_and_job_pages_still_work():
    setup = client.get("/jobs/new")
    assert setup.status_code == 200
    assert 'data-testid="setup-form"' in setup.text

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
    job_id = created.headers["location"].rstrip("/").rsplit("/", 1)[-1]

    assert client.get(f"/jobs/{job_id}").status_code == 200
    assert client.get(f"/jobs/{job_id}/evidence").status_code == 200
    # The console also opens an existing job by URL (resume by URL).
    resumed = client.get(f"/agent?job={job_id}")
    assert resumed.status_code == 200
    assert f'data-job-id="{job_id}"' in resumed.text

def test_state_panel_can_collapse_into_a_single_column():
    """The side panel folds away so the conversation gets the full width."""
    page = client.get("/agent/new")
    assert page.status_code == 200
    assert 'data-testid="agent-side-toggle"' in page.text
    assert 'aria-controls="agent-side"' in page.text
    assert 'aria-expanded="true"' in page.text
    assert "收起状态面板" in page.text
    assert 'id="agent-side"' in page.text
    # The toggle sits in the row, outside the tablist, so it is not a tab.
    assert AGENT_TEMPLATE.index('class="agent-tabs-row"') < AGENT_TEMPLATE.index(
        'id="agent-side-toggle"'
    )
    assert AGENT_TEMPLATE.index('class="agent-tabs"') < AGENT_TEMPLATE.index(
        'id="agent-side-toggle"'
    )

    assert "br.agent.side.collapsed" in AGENT_JS
    assert "is-side-collapsed" in AGENT_JS
    assert "aria-expanded" in AGENT_JS

    css = (BASE_DIR / "app" / "static" / "css" / "agent.css").read_text(encoding="utf-8")
    collapsed = css.split(".agent-body.is-side-collapsed", 1)[1]
    # Collapsed leaves a thin rail instead of removing the panel outright.
    assert "width: 16px" in collapsed[:600]
    assert "position: absolute" in collapsed[:400]
    assert ":hover" in collapsed[:2600]
    assert "max-width: 820px" in collapsed

def test_workspace_nav_does_not_repeat_the_landing_entry():
    """Inside the workbench the sidebar must not offer a second way back."""
    for path in ("/agent", "/jobs/new"):
        page = client.get(path)
        assert page.status_code == 200
        assert ">起始页<" not in page.text
        # The brand stays the one way back, so the entry is still reachable.
        assert 'class="ds-brand" href="/"' in page.text
        assert 'aria-label="返回起始页"' in page.text
        # Core entries remain: one new-task action, and the form as a secondary route.
        assert 'href="/agent/new"' in page.text
        assert 'data-testid="ds-job-list"' in page.text


def test_agent_index_is_the_task_list_and_one_new_task_action():
    """The workbench entry lists repairs and offers exactly one new-task entry."""
    page = client.get("/agent")
    assert page.status_code == 200
    assert "修复任务" in page.text
    assert 'data-testid="agent-start-new"' in page.text
    assert 'data-testid="agent-job-cards"' in page.text
    assert 'data-testid="ds-job-list"' in page.text
    # The old duplicate nav entries are gone from the sidebar.
    assert "修复控制台" not in page.text
    assert "新建任务（表单）" not in page.text


def test_single_task_route_is_its_own_conversation():
    job_id = "abc123def456"
    page = client.get(f"/agent/{job_id}")
    assert page.status_code == 200
    assert f'data-job-id="{job_id}"' in page.text
    assert 'data-testid="agent-back"' in page.text
    assert 'data-testid="agent-history-note"' in page.text
    assert 'data-testid="agent-open-comparison"' in page.text
    assert 'data-testid="agent-open-evidence"' in page.text
    assert "该任务的独立会话" in page.text
    # A new task does not show the per-task links.
    fresh = client.get("/agent/new")
    assert 'data-testid="agent-switch-form"' in fresh.text
    assert 'data-testid="agent-open-comparison"' not in fresh.text


def test_legacy_agent_query_redirects_to_the_task_route():
    response = client.get("/agent?job=abc123", follow_redirects=False)
    assert response.status_code in (307, 302)
    assert response.headers["location"].startswith("/agent/abc123")


def test_conversation_history_is_stored_per_job():
    assert "br.msg.v1." in AGENT_JS
    assert "HISTORY_LIMIT" in AGENT_JS
    assert "state.entries" in AGENT_JS
    assert "writeHistoryFor(match[1], state.entries)" in AGENT_JS
    # History replay must not re-record what it replays.
    assert "{ replay: true }" in AGENT_JS


# --- job-less plan route (M1's POST /api/assistant/plan) -------------------

def test_plan_route_requires_csrf():
    response = client.post("/api/assistant/plan", json={"description": "fix it"})
    assert response.status_code == 403


def test_plan_route_rejects_an_empty_description():
    response = client.post(
        "/api/assistant/plan",
        json={"description": "   "},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_plan_route_says_unavailable_instead_of_inventing_a_plan():
    response = client.post(
        "/api/assistant/plan",
        json={"description": "fix it"},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["plan"] is None
    assert body["error"] == "assistant_unavailable"


def test_plan_route_forwards_the_backend_plan(monkeypatch):
    import app.main as main_module

    class _PlanBackend:
        mode = "mock"
        base_url = ""

        def get_plan(self, description, context=None):
            assert description == "fix it"
            assert context == {"filename": "s.elf"}
            return {
                "plan_id": "p1",
                "mode": "llm",
                "fallback": False,
                "steps": [{"id": "r", "kind": "review", "title": "复核", "prompt": "复核"}],
            }

    monkeypatch.setattr(main_module, "BACKEND", _PlanBackend())
    response = client.post(
        "/api/assistant/plan",
        json={"description": "fix it", "context": {"filename": "s.elf"}},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 200
    assert response.json()["plan"]["plan_id"] == "p1"


def test_http_backend_treats_a_missing_plan_route_as_not_available():
    import httpx

    from app.backend import HttpBackend

    def handler(request):
        assert request.url.path == "/api/assistant/plan"
        return httpx.Response(404, json={"detail": "Not Found"})

    backend = HttpBackend(base_url="http://test", transport=httpx.MockTransport(handler))
    assert backend.get_plan("fix it") is None


def test_http_backend_keeps_chinese_plan_copy():
    import httpx

    from app.backend import HttpBackend

    plan = {
        "plan_id": "p1",
        "mode": "llm",
        "fallback": False,
        "steps": [{"id": "r", "kind": "review", "title": "复核", "prompt": "复核"}],
    }

    def handler(request):
        return httpx.Response(200, json={"plan": plan})

    backend = HttpBackend(base_url="http://test", transport=httpx.MockTransport(handler))
    assert backend.get_plan("fix it") == plan


def test_plan_response_must_carry_steps():
    import httpx

    from app.backend import BackendError, HttpBackend

    def handler(request):
        return httpx.Response(200, json={"plan": {"plan_id": "p1"}})

    backend = HttpBackend(base_url="http://test", transport=httpx.MockTransport(handler))
    try:
        backend.get_plan("fix it")
    except BackendError:
        pass
    else:  # pragma: no cover
        raise AssertionError("a plan without steps must not be accepted")


def test_plan_rendering_is_not_class_specific():
    # T8.3 needs a second defect class; the GUI must not assume the first one's
    # step count, question keys or wording.
    assert "steps.length - 2" not in AGENT_JS
    assert 'nextStep.kind === "review"' in AGENT_JS
    assert "question.label || labels[question.key]" in AGENT_JS
    assert "样本 → 缺陷 → 用例 → 契约 → 复核" not in AGENT_JS


def test_agent_js_marks_a_deterministic_plan():
    # mode=deterministic is a real answer, not a model answer; the page has to
    # say so even when fallback is false.
    assert 'plan.mode === "deterministic"' in AGENT_JS
    assert "确定性计划（未调用模型）" in AGENT_JS


def test_plan_503_keeps_the_fallback_reason():
    import httpx

    from app.backend import BackendError, HttpBackend

    def handler(request):
        return httpx.Response(503, json={
            "plan": None,
            "error": "assistant_unavailable",
            "fallback_reason": "no LLM client is configured on this host",
        }, request=request)

    backend = HttpBackend(base_url="http://test", transport=httpx.MockTransport(handler))
    try:
        backend.get_plan("fix it")
    except BackendError as exc:
        assert exc.status_code == 503
        assert "no LLM client" in exc.detail
    else:  # pragma: no cover
        raise AssertionError("503 must surface as BackendError")


def test_usage_null_is_not_rendered_as_zero():
    # aggregate_job_usage returns None when any token count is missing; the
    # page must keep that as 未提供 instead of defaulting to 0.
    assert 'typeof usage.input_tokens === "number"' in AGENT_JS
    assert 'input === undefined ? "未提供"' in AGENT_JS
    assert "input_tokens || 0" not in AGENT_JS
    assert 'setText("agent-model-meta", "未提供")' in AGENT_JS


def test_partial_usage_is_labelled():
    # partial=true means the sum is real but incomplete; it must never be
    # presented as the full number.
    assert "partial: usage.partial === true" in AGENT_JS
    assert "（部分真实用量）" in AGENT_JS
    assert "tokens：未提供" in AGENT_JS


def test_empty_test_suite_renders_as_na():
    # 0/0 is not a result. An empty suite must render N/A and must not be
    # folded into another suite's ratio.
    assert 'var total = typeof tests.total === "number"' in AGENT_JS
    assert '? "N/A" : (passed + "/" + total)' in AGENT_JS
