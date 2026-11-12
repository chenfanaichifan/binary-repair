"""Agent console (/agent) — M2 GUI owner, Lead record 86 / tasks T7.4-T7.8.

These tests pin the M2 boundary rather than backend behaviour:
- the shell renders and stays behind the local session + host gate;
- the console never declares a repair verdict by itself;
- obligations are rendered verbatim and "not_run" is not shown while the
  execution result has not been received (placeholder instead);
- model calls only through the backend; the browser holds no key and never executes code;
- no new job-writing endpoints, no SSE/WebSocket, no frameworks;
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
        "agent-history-sync",
        "agent-side-artifacts",
        "agent-timeline",
        "agent-before-after",
        "agent-diagnostics",
        "agent-downloads",
        "agent-receipt-placeholder",
        "agent-scorecard",
        "agent-evidence-matrix",
        "agent-obligation-table",
        "agent-artifact-table",
        "agent-raw-json",
        "agent-attempt-table",
        "agent-result-refresh",
    ):
        assert f'data-testid="{testid}"' in response.text, testid
    assert "新建修复内容" in response.text
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


def test_timeline_uses_timeline_status_and_marks_unknown_exit_code():
    assert 'ok: "成功", failed: "失败", timeout: "超时", cancelled: "已取消", unknown: "未知"' in AGENT_JS
    assert '"尝试记录不可用"' in AGENT_JS
    assert '"尚无尝试记录"' in AGENT_JS
    assert '"未知退出码"' in AGENT_JS
    assert '"/attempts"' in AGENT_JS


def test_scope_and_bounded_never_turn_missing_into_pass():
    assert 'var scopeText = "unknown";' in AGENT_JS
    assert 'var boundedText = "unknown";' in AGENT_JS
    # Review 12: missing scope/bounded must still render as unknown, never be hidden.
    assert 'if (!view.scope && !view.bounded) return;' not in AGENT_JS
    assert 'if (!view.jobId && !view.phase) return;' in AGENT_JS
    assert 'wrap.dataset.testid = "agent-scope-bounded"' in AGENT_JS


def test_snapshot_id_is_accepted_as_job_id():
    # P1 snapshot uses "id"; the console must not show an empty job chip for it.
    assert 'jobId: data.job_id || data.id || state.jobId || ""' in AGENT_JS


def test_comparison_is_only_shown_when_the_api_says_available():
    # 179 contract: status is the only source of truth; not_provided is never a pass.
    assert 'comparisonCache.status === "available"' in AGENT_JS
    assert 'text = "未提供（not_provided）"' in AGENT_JS
    assert 'text = "不可用（"' in AGENT_JS
    assert '"comparison：" + text' in AGENT_JS
    assert "comparison：通过" not in AGENT_JS
    assert '"超出边界"' in AGENT_JS


def test_comparison_cases_are_rendered_without_becoming_a_verdict():
    # M5 schema: an available comparison is behaviour evidence. same / different /
    # not_run describe what was observed; none of them is an acceptance verdict.
    assert "function appendComparisonCases" in AGENT_JS
    assert 'if (comparisonCache.status === "available") appendComparisonCases(wrap);' in AGENT_JS
    assert "CASE_KIND_LABELS" in AGENT_JS
    assert "CASE_VERDICT_LABELS" in AGENT_JS
    assert "不构成验收结论" in AGENT_JS
    assert "data.not_claimed" in AGENT_JS
    assert "未执行" in AGENT_JS
    # Neutral vocabulary only: the comparison card never grows a pass label.
    assert 'text = "通过"' not in AGENT_JS
    assert "comparison：通过" not in AGENT_JS
    # M5 (197): unknown kind/verdict is rejected by the route, so the
    # comparison verdict table carries no unknown label. The execution-status
    # map keeps its own "unknown" entry and is out of scope here.
    verdict_block = AGENT_JS.split("var CASE_VERDICT_LABELS = {")[1].split("};")[0]
    assert "unknown" not in verdict_block


def test_top_level_obligations_are_accepted_when_routes_omit_them():
    """M5 may return obligations at the top level; the view must not drop them."""
    assert "!obligations.length && Array.isArray(data.obligations)" in AGENT_JS


def test_missing_region_field_renders_a_dash_not_a_blank_cell():
    """A missing before/after byte shows —, never a blank cell."""
    assert 'value === undefined || value === null || value === "" ? "—" : value' in AGENT_JS


def test_artifact_without_id_is_not_linked():
    """A bad artifact row must not yield /api/artifacts/undefined/download."""
    assert 'if (!artifact || typeof artifact.id !== "string" || !artifact.id || seen[artifact.id]) return;' in AGENT_JS


def test_route_without_evidence_says_unavailable():
    """Missing evidence is announced, not silently omitted."""
    assert "证据不可用（该路线未回传 attempt）" in AGENT_JS
    assert "证据不可用（attempt 未回传或端点未开通）" in AGENT_JS


def test_pasted_code_has_a_reviewable_repair_path():
    assert "extractCode" in AGENT_JS
    assert "agent-repair-card" in AGENT_JS
    assert "chat-code" in AGENT_JS
    assert "复制补丁" in AGENT_JS
    assert "粘贴代码" in AGENT_TEMPLATE
    assert 'id="agent-code-repair"' in AGENT_TEMPLATE
    # Advice only: the card must not look like an acceptance verdict.
    assert "也不构成验收结论" in AGENT_JS


def test_no_model_calls_or_new_transport():
    # Actual usage is banned (mentioning the rule in comments is fine).
    for banned in ("api.openai.com", "new WebSocket", "new EventSource", "Bearer ",
                   'setRequestHeader("Authorization'):
        assert banned not in AGENT_JS, banned
    # Same-origin paths: snapshot, attempts, plan, evidence, comparison, the
    # operator key status/save/test/clear endpoints, static code repair and
    # history get/put/delete.
    assert AGENT_JS.count("fetch(") == 16
    assert "/artifacts" in AGENT_JS
    assert "/deliverables" in AGENT_JS
    assert 'fetch("/api/jobs/" + encodeURIComponent(state.jobId)' in AGENT_JS
    assert 'fetch("/api/jobs/" + encodeURIComponent(jobId) + "/attempts"' in AGENT_JS
    assert 'fetch("/api/jobs/" + encodeURIComponent(jobId) + "/comparison"' in AGENT_JS
    assert 'fetch("/api/assistant/plan"' in AGENT_JS
    assert 'fetch("/api/assistant/key"' in AGENT_JS
    assert 'fetch("/api/assistant/key/test"' in AGENT_JS
    assert 'fetch("/api/code/repair"' in AGENT_JS
    assert 'fetch(serverHistoryUrl(scope)' in AGENT_JS
    assert '"/api/history/" + encodeURIComponent(scope)' in AGENT_JS
    assert 'fetch("/api/attempts/" + encodeURIComponent(attemptId) + "/evidence"' in AGENT_JS
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


def test_landing_offers_one_intake_and_no_form_path():
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-testid="landing-agent-cta"' in response.text
    assert 'href="/agent/new?' in response.text
    assert 'data-primary="1"' in response.text
    # The form intake is retired: no form CTA or form link may remain.
    assert 'landing-cta' not in response.text
    assert 'href="/jobs/new"' not in response.text
    assert "表单建单" not in response.text
    assert "使用表单上传" not in response.text


def test_retired_setup_page_redirects_and_job_creation_still_works():
    setup = client.get("/jobs/new", follow_redirects=False)
    assert setup.status_code == 303
    assert setup.headers["location"] == "/agent/new?new=1"

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
        assert 'href="/agent/new' in page.text
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
    assert 'data-testid="agent-open-comparison"' not in fresh.text


def test_legacy_agent_query_redirects_to_the_task_route():
    response = client.get("/agent?job=abc123", follow_redirects=False)
    assert response.status_code in (307, 302)
    assert response.headers["location"].startswith("/agent/abc123")


def test_legacy_agent_query_never_redirects_a_non_job_id():
    # ``/agent/../x`` would be normalised by the browser into another site
    # path, so a legacy link may only redirect for an id-shaped job.
    for bad in ("../secret", "a/b", "abc?x=1", "x" * 65, "%2e%2e"):
        response = client.get(f"/agent?job={bad}", follow_redirects=False)
        assert response.status_code == 404, bad
        assert "location" not in response.headers, bad


def test_conversation_history_is_stored_per_job():
    assert "br.msg.v1." in AGENT_JS
    assert "HISTORY_LIMIT" in AGENT_JS
    assert "state.entries" in AGENT_JS
    assert "writeHistoryFor(match[1], state.entries)" in AGENT_JS
    assert "hydrateHistory" in AGENT_JS
    assert "scheduleServerSave" in AGENT_JS
    assert "historyGeneration" in AGENT_JS
    assert "FRESH_SESSION" in AGENT_JS
    assert "clearServerHistory" in AGENT_JS
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


def test_plan_route_serves_the_real_planner_in_mock_mode(monkeypatch):
    # Mock mode plans through the same seam as local mode: the steps are
    # computed by the planner, not read from a fixture, and the page labels a
    # deterministic answer as "no model call". Pin the no-key branch so the
    # test never reaches the network.
    import app.services.assistant_llm as assistant_llm

    monkeypatch.setattr(assistant_llm, "client_from_env", lambda: None)
    response = client.post(
        "/api/assistant/plan",
        json={"description": "fix it"},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["mode"] == "deterministic"
    assert plan["fallback"] is False
    assert plan["steps"] and plan["steps"][-1]["kind"] == "review"


def test_plan_route_says_unavailable_when_the_backend_has_no_plan_route(monkeypatch):
    # A controller that has not shipped the route still answers 503 instead of
    # borrowing a plan from somewhere else.
    import app.main as main_module

    class _NoPlanBackend:
        mode = "http"
        base_url = ""

        def get_plan(self, description, context=None):
            return None

    monkeypatch.setattr(main_module, "BACKEND", _NoPlanBackend())
    response = client.post(
        "/api/assistant/plan",
        json={"description": "fix it"},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["plan"] is None
    assert body["error"] == "assistant_unavailable"
    assert body["fallback_reason"] == "assistant_endpoint_missing"


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


def test_plan_mode_badge_shows_scripted_v1_and_keeps_raw_mode():
    # T8.4: the badge must read "脚本 v1" for deterministic plans, while the
    # raw mode stays visible and is also exposed as a data attribute.
    assert 'deterministic: "脚本 v1"' in AGENT_JS
    assert 'llm: "LLM"' in AGENT_JS
    assert '"（" + agent.mode + "）"' in AGENT_JS
    assert '"data-plan-mode", activeMode' in AGENT_JS


def test_empty_test_suite_renders_as_na():
    # 0/0 is not a result. An empty suite must render N/A and must not be
    # folded into another suite's ratio.
    assert 'var total = typeof tests.total === "number"' in AGENT_JS
    assert '? "N/A" : (passed + "/" + total)' in AGENT_JS


def test_gates_render_in_endpoint_order():
    # The endpoint returns V0..V5 as an ordered array; the GUI renders that
    # order and never sorts or invents a gate row.
    assert "Array.isArray(evidence.gates)" in AGENT_JS
    assert "evidence.gates.forEach(function (gate)" in AGENT_JS
    assert 'gateList.dataset.testid = "agent-gates-" + key' in AGENT_JS
    assert "evidence.gates.sort" not in AGENT_JS


def test_invalid_is_na_when_input_mode_is_none():
    # Lead 定稿：input_mode="none" 时 invalid 是 {passed:0,total:0}，显示 N/A，
    # 不显示 0/0 passed。invalid_applicable 只作旧响应的兼容。
    assert 'v3.input_mode === "none"' in AGENT_JS
    assert 'var invalidText = "N/A";' in AGENT_JS
    assert "v3.invalid.total > 0" in AGENT_JS
    assert '" · invalid " + invalidText' in AGENT_JS


def test_valid_ratio_comes_from_the_v3_summary():
    assert '" · valid " + v3.valid.passed + "/" + v3.valid.total' in AGENT_JS


def test_result_screen_exposes_coverage_and_raw_evidence():
    assert "/api/jobs/" in AGENT_JS and "/evaluation" in AGENT_JS
    assert "buildLocalEvaluation" in AGENT_JS
    assert "not_verdict: true" in AGENT_JS  # explicit coverage-only marker
    assert "observability_index" in AGENT_JS
    assert "agent-result-table" in AGENT_JS


def test_result_screen_does_not_hardcode_the_evidence_sample():
    # The controller sample (124: V4 not_run, inconclusive) is evidence, not a
    # fixture; the screen renders whatever the API returns.
    assert "required_check_not_run" not in AGENT_JS
    assert "V4 not_run" not in AGENT_JS
    assert '["V0", "V1"' not in AGENT_JS


def test_evidence_proxy_reports_unavailable_in_fixture_mode():
    response = client.get("/api/attempts/att-1/evidence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False


def test_http_backend_treats_a_missing_evidence_route_as_not_available():
    import httpx

    from app.backend import HttpBackend

    def handler(request):
        assert request.url.path == "/api/attempts/att-1/evidence"
        return httpx.Response(404, json={"detail": "Attempt not found."})

    backend = HttpBackend(base_url="http://test", transport=httpx.MockTransport(handler))
    assert backend.get_attempt_evidence("att-1") is None


def test_http_backend_passes_gates_and_v3_through():
    import httpx

    from app.backend import HttpBackend

    payload = {
        "gates": [{"gate": "V3", "kind": "behaviour", "result": "passed"}],
        "v3": {
            "gate": "V3",
            "valid": {"passed": 1, "total": 1},
            "invalid": {"passed": 0, "total": 0},
            "invalid_applicable": False,
        },
    }

    def handler(request):
        assert request.url.path == "/api/attempts/att-1/evidence"
        return httpx.Response(200, json=payload)

    backend = HttpBackend(base_url="http://test", transport=httpx.MockTransport(handler))
    assert backend.get_attempt_evidence("att-1") == payload


def test_evidence_proxy_passes_gates_and_v3_unchanged(monkeypatch):
    import app.main as main_module

    payload = {
        "gates": [
            {"gate": "V0", "kind": "identity", "result": "passed"},
            {"gate": "V3", "kind": "behaviour", "result": "passed"},
        ],
        "v3": {
            "gate": "V3",
            "valid": {"passed": 1, "total": 1},
            "invalid": {"passed": 0, "total": 0},
            "invalid_applicable": False,
        },
    }

    class _EvidenceBackend:
        def get_attempt_evidence(self, attempt_id):
            assert attempt_id == "att-1"
            return payload

    monkeypatch.setattr(main_module, "BACKEND", _EvidenceBackend())
    response = client.get("/api/attempts/att-1/evidence")
    assert response.status_code == 200
    body = response.json()
    assert [row["gate"] for row in body["gates"]] == ["V0", "V3"]
    assert body["v3"]["valid"] == {"passed": 1, "total": 1}
    assert body["v3"]["invalid_applicable"] is False


def test_deliverable_upload_controls_exist():
    """The operator-facing repaired ELF upload must be present and same-origin."""
    assert 'id="agent-deliverable-input"' in AGENT_TEMPLATE
    assert 'id="agent-deliverable-upload"' in AGENT_TEMPLATE
    assert 'data-testid="agent-deliverable-input"' in AGENT_TEMPLATE
    assert "uploadDeliverable" in AGENT_JS
    assert '"/deliverables"' in AGENT_JS
    assert "/artifacts" in AGENT_JS


def test_deliverable_upload_is_hidden_off_http_and_rejects_oversized_files():
    """The upload control must not be offered without an HTTP origin, and a file
    above the server limit must be refused before any request leaves the page."""
    assert 'window.location.protocol === "http:"' in AGENT_JS
    assert 'window.location.protocol === "https:"' in AGENT_JS
    assert "if (!UPLOAD_AVAILABLE)" in AGENT_JS
    assert "uploadButton.hidden = true" in AGENT_JS
    assert "uploadInput.hidden = true" in AGENT_JS
    assert "DELIVERABLE_MAX_BYTES = 64 * 1024 * 1024" in AGENT_JS
    assert "if (file.size > DELIVERABLE_MAX_BYTES)" in AGENT_JS
    assert "64 MiB" in AGENT_JS


def test_console_panels_are_resizable_and_the_sidebar_collapses():
    assert 'id="agent-side-resizer"' in AGENT_TEMPLATE
    assert 'aria-orientation="vertical"' in AGENT_TEMPLATE
    assert "agent-side-resizer" in AGENT_JS
    assert "br.agent.side.width" in AGENT_JS
    assert 'id="agent-focus-toggle"' in AGENT_TEMPLATE
    assert 'id="agent-focus-exit"' in AGENT_TEMPLATE
    assert "br.agent.focus" in AGENT_JS
    page = client.get("/agent/new")
    assert "ds-sidebar-toggle" in page.text
    assert "ds-sidebar-expand" in page.text
    assert "/static/js/shell.js" in page.text


def test_workbench_is_a_dashboard_not_an_empty_list():
    page = client.get("/agent")
    assert page.status_code == 200
    assert "修复工作台" in page.text
    assert "方法与工具" in page.text
    assert "服务端会话" in page.text
    assert "粘贴代码" in page.text
    assert "wb-method" in page.text
    assert "Ghidra" in page.text
    assert "angr" in page.text
