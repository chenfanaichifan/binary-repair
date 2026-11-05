"""BinaryRepair MVP GUI (server-rendered FastAPI app).

Demo mode:
    .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
Real controller mode: set BINARYREPAIR_BACKEND=http and
BINARYREPAIR_API_BASE=http://127.0.0.1:8000 before starting uvicorn."""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlencode, urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import i18n, status
from app.backend import (
    BackendError,
    backend_description,
    backend_mode,
    get_backend,
)
from app.evidence_domains import evidence_domain, scope_display
from app.services.assistant_llm import ASSISTANT_MODE_ENV, assistant_status
from app.ui_config import load_ui_config, resolve_mode, resolve_workspace

BASE_DIR = Path(__file__).resolve().parent

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

def _load_session_token() -> str:
    """Return the persisted local session token (env override wins).

    The token is written to ``var/session.token`` once and reused across restarts,
    so the browser cookie stays valid and users do not have to re-login every time.
    """
    configured = os.environ.get("BINARYREPAIR_SESSION_TOKEN")
    if configured:
        return configured
    token_file = BASE_DIR.parent / "var" / "session.token"
    try:
        if token_file.exists():
            stored = token_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        token = secrets.token_urlsafe(32)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token, encoding="utf-8")
        return token
    except OSError:
        return secrets.token_urlsafe(32)


SESSION_TOKEN = _load_session_token()
CSRF_TOKEN = hmac.new(SESSION_TOKEN.encode("utf-8"), b"gui-csrf", hashlib.sha256).hexdigest()
SESSION_COOKIE = "br_session"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

app = FastAPI(title="BinaryRepair MVP - GUI slice")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

templates.env.globals.update(
    phase_labels_zh=i18n.PHASE_LABELS_ZH,
    stage_labels_zh=i18n.STAGE_LABELS_ZH,
    outcome_labels_zh=i18n.OUTCOME_LABELS_ZH,
    state_labels_zh=i18n.STATE_LABELS_ZH,
    value_labels_zh=i18n.VALUE_LABELS_ZH,
    route_names_zh=i18n.ROUTE_NAMES_ZH,
    csrf_token=CSRF_TOKEN,
    display_verdict=status.display_verdict,
    order_obligations=status.order_obligations,
)

BACKEND = get_backend()
BACKEND_MODE = backend_mode()


def _ascii_filename(name: str) -> str:
    """Sanitize an uploaded filename to an ASCII safe name."""
    base = Path(name or "").name
    if base and base.isascii() and _UNSAFE_FILENAME_CHARS.search(base) is None:
        return base
    stem, dot, suffix = base.rpartition(".")
    stem_clean = _UNSAFE_FILENAME_CHARS.sub("_", stem).strip("_-") if stem else ""
    suffix_clean = _UNSAFE_FILENAME_CHARS.sub("", suffix) if dot else ""
    if not stem_clean:
        stem_clean = "uploaded-sample"
    return f"{stem_clean}.{suffix_clean}" if suffix_clean else stem_clean


def _require_english(field: str, value: str) -> None:
    """Reject non-ASCII upload text with 422."""
    if value and any(ord(char) > 127 for char in value):
        raise HTTPException(
            status_code=422,
            detail=f"Field '{field}' must use English/ASCII characters only (no non-ASCII characters).",
        )


@app.exception_handler(BackendError)
async def backend_error_handler(request: Request, exc: BackendError) -> JSONResponse:
    """Render backend failures as English JSON errors."""
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.middleware("http")
async def security_gate(request: Request, call_next):
    """Enforce the local-only session/CSRF security boundary."""
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if host not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "Local access only (host check failed)."}, status_code=403)

    path = request.url.path
    if path.startswith("/static/") or path in {"/healthz", "/favicon.ico"}:
        return await call_next(request)

    token = request.query_params.get("token")
    if token and secrets.compare_digest(token, SESSION_TOKEN):
        response = RedirectResponse(url=path or "/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            SESSION_TOKEN,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return response

    session = request.cookies.get(SESSION_COOKIE)
    if not session or not secrets.compare_digest(session, SESSION_TOKEN):
        if request.method == "GET" and "text/html" in (request.headers.get("accept") or ""):
            return HTMLResponse(_auth_required_page(), status_code=401)
        return JSONResponse(
            {
                "detail": (
                    "Authentication required. Open the launcher URL containing ?token=... "
                    "to start the local session."
                )
            },
            status_code=401,
        )

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme != "http" or (parsed.hostname or "") not in ALLOWED_HOSTS:
                return JSONResponse(
                    {"detail": "Cross-origin request rejected."}, status_code=403
                )

    return await call_next(request)


def _require_csrf(token: str) -> None:
    """Validate the CSRF token rendered into every POST form."""

    if not token or not secrets.compare_digest(str(token), CSRF_TOKEN):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid.")


def _auth_required_page() -> str:
    """Friendly 401 page for humans.

    It deliberately carries no session token. An unauthenticated response must
    never hand out the credential that unlocks the workspace; the trusted
    launcher prints the one-time login address to its own console instead.
    """

    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>需要本地会话 · BinaryRepair</title>
<style>
 body{margin:0;background:#f3ede1;color:#2c2925;font-family:"Trebuchet MS","Segoe UI","Microsoft YaHei",sans-serif;
      background-image:radial-gradient(900px 520px at 15% -5%,rgba(168,100,47,.08),transparent 60%);
      display:flex;align-items:center;justify-content:center;min-height:100vh}
 .card{max-width:600px;padding:30px 34px;background:#faf6ec;border:1.5px dashed #2c2925;border-radius:24px 18px 26px 16px;
       box-shadow:6px 7px 0 rgba(44,41,37,.12)}
 h1{font-family:Georgia,"Songti SC","SimSun",serif;font-size:24px;margin:0 0 10px;color:#2c2925}
 p{font-size:14px;line-height:1.75;color:#4a453d;margin:8px 0}
 code{font-family:"Cascadia Mono",Consolas,monospace;background:#eee6d6;color:#6b4a2c;padding:2px 6px;border-radius:4px}
 .steps{margin:16px 0 0;padding-left:18px;font-size:13px;color:#4a453d}
 .steps li{margin:6px 0}
 .hint{margin-top:14px;font-size:12px;color:#8a7f6e}
</style></head>
<body><div class="card">
<h1>需要本地会话</h1>
<p>这是本机工作台的访问保护。当前请求没有有效会话，<strong>所以这个页面不会显示登录令牌</strong>。</p>
<ol class="steps">
  <li>双击项目里的 <code>open.bat</code>，或运行 <code>start.ps1</code>；</li>
  <li>使用启动脚本控制台里打印的登录地址进入（令牌只在那一条地址里）；</li>
  <li>令牌保存在本机 <code>var/session.token</code>，只应复制到你自己的浏览器。</li>
</ol>
<p class="hint">不要把登录地址发到公开位置。服务只监听本机回环地址，重启服务不会改变令牌。</p>
</div></body></html>"""


@app.get("/", response_class=HTMLResponse, name="landing_page")
async def index(request: Request):
    """Render the landing page."""
    ui = load_ui_config()
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "backend_note": backend_description(BACKEND),
            "ui": ui,
            "default_workspace": resolve_workspace(ui, None),
            "default_mode": resolve_mode(ui, None),
        },
    )


@app.get("/api/ui-config", name="ui_config")
async def ui_config():
    """Expose the workspace/mode catalogue the landing page renders from.

    This is the GUI's own configuration. When a real backend owns it, only
    ``app.ui_config.load_ui_config`` changes; the response shape stays.
    """
    return JSONResponse(load_ui_config())


def _agent_context(
    *,
    job_id: str = "",
    fixture: int = 0,
    workspace: str = "",
    mode: str = "",
    job: dict[str, str] | None = None,
) -> dict:
    """Shared template context for the workbench routes.

    ``assistant`` is the GUI's view of the T8.2 seam. It is deliberately
    conservative: llm mode without a configured client reports
    ``available=false`` so the badge says "未接线" instead of implying a call
    happened.
    """
    ui = load_ui_config()
    selected_workspace = resolve_workspace(ui, workspace or None)
    selected_mode = resolve_mode(ui, mode or None)
    fixture_mode = bool(fixture) or selected_mode["id"] == "demo"
    return {
        "demo": BACKEND_MODE == "mock" or fixture_mode,
        "job": job,
        "job_id": job_id,
        "fixture": fixture_mode,
        "backend_note": backend_description(BACKEND),
        "workspace": selected_workspace,
        "mode": selected_mode,
        "assistant": assistant_status(
            mode=os.environ.get(ASSISTANT_MODE_ENV),
            client_configured=False,
        ),
    }


@app.get("/agent", response_class=HTMLResponse, name="agent_index")
async def agent_index(
    request: Request,
    job: str = "",
    fixture: int = 0,
    workspace: str = "",
    mode: str = "",
):
    """Workbench entry: the task list, with one action to start a new repair.

    Older links used ``/agent?job=<id>``; they keep working by redirecting to the
    per-task conversation route, so bookmarks and the landing CTA do not break.
    """
    if job:
        query: dict[str, str] = {}
        if fixture:
            query["fixture"] = str(fixture)
        if workspace:
            query["workspace"] = workspace
        if mode:
            query["mode"] = mode
        target = f"/agent/{job}"
        if query:
            target += "?" + urlencode(query)
        return RedirectResponse(url=target, status_code=307)

    return templates.TemplateResponse(
        request,
        "agent_index.html",
        _agent_context(fixture=fixture, workspace=workspace, mode=mode),
    )


@app.get("/agent/new", response_class=HTMLResponse, name="agent_new")
async def agent_new(
    request: Request,
    fixture: int = 0,
    workspace: str = "",
    mode: str = "",
):
    """Start a brand-new repair: the guided conversation with no job attached."""
    return templates.TemplateResponse(
        request,
        "agent.html",
        _agent_context(fixture=fixture, workspace=workspace, mode=mode),
    )


@app.get("/agent/{job_id}", response_class=HTMLResponse, name="agent_console")
async def agent_console(
    request: Request,
    job_id: str,
    fixture: int = 0,
    workspace: str = "",
    mode: str = "",
):
    """One repair task = one conversation, with its own local history.

    UI only: no planner, no model calls, no new write endpoints. Until M1's
    agent/execution fields and M5's assistant plan land, ?fixture=1 drives the
    shell with clearly labelled placeholder data, and the demo banner stays on.
    """
    return templates.TemplateResponse(
        request,
        "agent.html",
        _agent_context(
            job_id=job_id,
            fixture=fixture,
            workspace=workspace,
            mode=mode,
            job={"id": job_id},
        ),
    )


@app.get("/jobs/new", response_class=HTMLResponse, name="setup_page")
async def setup_page(request: Request):
    """Render setup/review (upload + contract)."""
    return templates.TemplateResponse(
        request,
        "setup.html",
        {"demo": BACKEND_MODE == "mock", "job": None, "backend_note": backend_description(BACKEND)},
    )


@app.post("/jobs")
async def create_job(
    binary: UploadFile = File(...),
    defect: str = Form(...),
    valid_tests: str = Form(""),
    environment: str = Form(""),
    valid_domain: str = Form(""),
    forbidden: str = Form(""),
    invalid_outcome: str = Form(""),
    assumptions: str = Form(""),
    csrf: str = Form(""),
):
    """Create a job from the upload form."""
    _require_csrf(csrf)
    raw = await binary.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 20 MiB limit.")
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    for field_name, field_value in (
        ("defect", defect),
        ("valid_tests", valid_tests),
        ("environment", environment),
        ("valid_domain", valid_domain),
        ("forbidden", forbidden),
        ("invalid_outcome", invalid_outcome),
        ("assumptions", assumptions),
    ):
        _require_english(field_name, field_value)

    job_id = BACKEND.create_job(
        binary_bytes=raw,
        filename=_ascii_filename(binary.filename or "sample.bin"),
        defect=defect,
        valid_tests=valid_tests,
        environment=environment,
        valid_domain=valid_domain,
        forbidden=forbidden,
        invalid_outcome=invalid_outcome,
        assumptions=assumptions,
    )
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


def _comparison_response(
    request: Request,
    job_id: str,
    *,
    error: str | None = None,
    status_code: int = 200,
):
    """Render the comparison screen (also used for explicit 409 conflict errors)."""
    snapshot = BACKEND.get_snapshot(job_id)
    try:
        code_visuals = BACKEND.get_visuals(job_id)
    except BackendError:
        code_visuals = {"available": False, "note": "Code view is unavailable from the controller."}
    return templates.TemplateResponse(
        request,
        "comparison.html",
        {
            "demo": bool(snapshot.get("demo")),
            "job": snapshot,
            "visuals": code_visuals,
            "can_start": BACKEND.supports_start,
            "backend_note": backend_description(BACKEND),
            "error": error,
        },
        status_code=status_code,
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def comparison_page(request: Request, job_id: str):
    """Render progress/comparison for both routes."""
    return _comparison_response(request, job_id)


@app.post("/jobs/{job_id}/contract")
async def update_contract(
    request: Request,
    job_id: str,
    expected_revision: str = Form(""),
    valid_domain: str = Form(""),
    forbidden: str = Form(""),
    invalid_outcome: str = Form(""),
    assumptions: str = Form(""),
    csrf: str = Form(""),
):
    """Create a new contract revision; a stale ``expected_revision`` returns 409."""

    _require_csrf(csrf)
    for field_name, field_value in (
        ("valid_domain", valid_domain),
        ("forbidden", forbidden),
        ("invalid_outcome", invalid_outcome),
        ("assumptions", assumptions),
    ):
        _require_english(field_name, field_value)
    try:
        BACKEND.update_contract(
            job_id,
            expected_revision=expected_revision,
            valid_domain=valid_domain,
            forbidden=forbidden,
            invalid_outcome=invalid_outcome,
            assumptions=assumptions,
        )
    except BackendError as exc:
        return _comparison_response(request, job_id, error=exc.detail, status_code=exc.status_code)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/approve")
async def approve_contract(
    request: Request,
    job_id: str,
    expected_sha256: str = Form(""),
    reviewer_label: str = Form(""),
    csrf: str = Form(""),
):
    """Approve the current contract revision; a stale hash returns 409."""

    _require_csrf(csrf)
    _require_english("reviewer_label", reviewer_label)
    try:
        BACKEND.approve_contract(
            job_id,
            expected_sha256=expected_sha256,
            reviewer_label=reviewer_label,
        )
    except BackendError as exc:
        return _comparison_response(request, job_id, error=exc.detail, status_code=exc.status_code)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/start")
async def start_run(request: Request, job_id: str, csrf: str = Form("")):
    """Start a run (demo advance or controller request)."""
    _require_csrf(csrf)
    try:
        BACKEND.start(job_id)
    except BackendError as exc:
        return _comparison_response(request, job_id, error=exc.detail, status_code=exc.status_code)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/cancel")
async def cancel_run(request: Request, job_id: str, csrf: str = Form("")):
    """Cancel the current run."""
    _require_csrf(csrf)
    try:
        BACKEND.cancel(job_id)
    except BackendError as exc:
        return _comparison_response(request, job_id, error=exc.detail, status_code=exc.status_code)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.get("/dryrun/route-a", response_class=HTMLResponse)
async def dryrun_route_a(request: Request):
    """Route A interface preview: render host dry-run artifacts only.

    The UI intentionally never derives an outcome here; it renders the raw
    V0-V5 statuses and, when present, the acceptance engine's decision.json.
    """
    base = BASE_DIR / "interfaces" / "route-a"
    bundle = json.loads((base / "result-bundle-DRYRUN.json").read_text(encoding="utf-8"))
    status = json.loads((base / "status-DRYRUN.json").read_text(encoding="utf-8"))
    decision_path = base / "decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8")) if decision_path.exists() else None
    return templates.TemplateResponse(
        request,
        "dryrun.html",
        {"demo": False, "backend_note": "host dry-run fixtures", "bundle": bundle, "status": status, "decision": decision},
    )


@app.get("/jobs/{job_id}/evidence", response_class=HTMLResponse)
async def evidence_page(request: Request, job_id: str):
    """Render evidence/export for both routes."""
    snapshot = BACKEND.get_snapshot(job_id)
    obligations: dict[str, list[dict]] = {}
    for key, route in (snapshot.get("routes") or {}).items():
        group = route.get("obligations")
        if group:
            obligations[key] = group
    if len(obligations) < len(snapshot.get("routes") or {}):
        for key, group in BACKEND.get_obligations(job_id).items():
            obligations.setdefault(key, group)
    getter = getattr(BACKEND, "get_attempts", None)
    if getter is None:
        attempts = {"available": False, "attempts": []}
    else:
        try:
            attempts = getter(job_id)
        except BackendError:
            attempts = None
        if attempts is None:
            attempts = {"available": False, "attempts": []}
    return templates.TemplateResponse(
        request,
        "evidence.html",
        {
            "demo": bool(snapshot.get("demo")),
            "job": snapshot,
            "obligations": obligations,
            "artifacts": BACKEND.get_artifacts(job_id),
            "attempts": attempts,
            "backend_note": backend_description(BACKEND),
            "evidence_domain": evidence_domain,
            "scope_display": scope_display,
        },
    )


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    """Return the polling status JSON."""
    return JSONResponse(BACKEND.get_snapshot(job_id))


@app.get("/api/jobs/{job_id}/attempts")
async def job_attempts(job_id: str):
    """Proxy M1's per-attempt history.

    ``available: false`` means the controller does not expose the endpoint yet;
    it is not the same as "this job has no attempts", and the UI says so.
    """
    getter = getattr(BACKEND, "get_attempts", None)
    payload = getter(job_id) if getter is not None else None
    if payload is None:
        return JSONResponse(
            {
                "attempts": [],
                "available": False,
                "note": "Controller does not expose GET /api/jobs/{id}/attempts yet.",
            }
        )
    payload = dict(payload)
    payload.setdefault("available", True)
    return JSONResponse(payload)


@app.post("/api/assistant/plan")
async def assistant_plan(request: Request) -> JSONResponse:
    """Proxy M1's job-less planning route.

    The GUI never invents a plan: when the controller has not shipped the route,
    this answers 503 and ``/agent/new`` shows "not connected" instead of falling
    back to fixture data.
    """
    _require_csrf(request.headers.get("x-csrf-token", ""))
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(
            {"plan": None, "error": "invalid_request", "detail": "JSON body required."},
            status_code=422,
        )
    if not isinstance(body, dict):
        return JSONResponse(
            {"plan": None, "error": "invalid_request", "detail": "JSON object required."},
            status_code=422,
        )
    description = body.get("description")
    if not isinstance(description, str) or not description.strip():
        return JSONResponse(
            {"plan": None, "error": "invalid_request", "detail": "'description' is required."},
            status_code=422,
        )
    context = body.get("context")
    if context is not None and not isinstance(context, dict):
        return JSONResponse(
            {"plan": None, "error": "invalid_request", "detail": "'context' must be an object."},
            status_code=422,
        )

    getter = getattr(BACKEND, "get_plan", None)
    if getter is None:
        return JSONResponse(
            {
                "plan": None,
                "error": "assistant_unavailable",
                "fallback_reason": "llm_client_not_configured",
            },
            status_code=503,
        )
    try:
        plan = getter(description.strip(), context)
    except BackendError as exc:
        return JSONResponse(
            {"plan": None, "error": "assistant_unavailable", "detail": exc.detail},
            status_code=503,
        )
    if plan is None:
        return JSONResponse(
            {
                "plan": None,
                "error": "assistant_unavailable",
                "fallback_reason": "assistant_endpoint_missing",
            },
            status_code=503,
        )
    return JSONResponse({"plan": plan})


@app.get("/api/jobs/{job_id}/export")
async def export_bundle(job_id: str):
    """Export JSON v2 evidence (English ASCII; not production approval)."""
    try:
        bundle = BACKEND.export_bundle(job_id)
    except BackendError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    job_id_for_file = str(bundle.get("job", {}).get("id") or job_id)
    body = json.dumps(bundle, ensure_ascii=True, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{job_id_for_file}-evidence.json"',
        },
    )


@app.get("/api/artifacts/{artifact_id}")
async def artifact_metadata(artifact_id: str):
    """Proxy artifact metadata so evidence pages work against the controller."""
    getter = getattr(BACKEND, "get_artifact_metadata", None)
    if getter is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact metadata is only available in controller (http) mode.",
        )
    return JSONResponse(getter(artifact_id))


@app.get("/api/artifacts/{artifact_id}/download")
async def artifact_download(artifact_id: str):
    """Proxy registered artifact bytes; a missing byte stream is a 404, not an empty file."""
    getter = getattr(BACKEND, "get_artifact_bytes", None)
    if getter is None:
        raise HTTPException(
            status_code=404,
            detail="Artifact downloads are only available in controller (http) mode.",
        )
    content, media_type, filename = getter(artifact_id)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or f"{artifact_id}.bin"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/jobs/{job_id}/report", response_class=HTMLResponse)
async def evidence_report(request: Request, job_id: str, download: int = 0):
    """Render the printable English evidence report (same data as JSON v2)."""
    try:
        bundle = BACKEND.export_bundle(job_id)
    except BackendError as exc:
        return HTMLResponse(
            f"<h1>Report unavailable</h1><p>{html.escape(exc.detail)}</p>",
            status_code=exc.status_code,
        )
    sha_lines = [f"{bundle['manifest_sha256']}  manifest.json"]
    for artifact in bundle.get("artifacts", []):
        if artifact.get("sha256"):
            sha_lines.append(f"{artifact['sha256']}  {artifact.get('name')}")
    headers = None
    if download:
        headers = {"Content-Disposition": f'attachment; filename="{job_id}-evidence.html"'}
    getter = getattr(BACKEND, "get_attempts", None)
    if getter is None:
        attempts = {"available": False, "attempts": []}
    else:
        try:
            attempts = getter(job_id)
        except BackendError:
            attempts = None
        if attempts is None:
            attempts = {"available": False, "attempts": []}
    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "bundle": bundle,
            "sha_lines": sha_lines,
            "evidence_domain": evidence_domain,
            "scope_display": scope_display,
            "attempts": attempts,
        },
        headers=headers,
    )


@app.get("/healthz")
async def healthz():
    # mock is synthetic; local is the real controller store; http trusts the
    # controller snapshot, so the demo flag is unknown until a job is fetched.
    demo = {"mock": True, "local": False}.get(BACKEND_MODE)
    return {
        "ok": True,
        "backend": BACKEND_MODE,
        "backend_detail": backend_description(BACKEND),
        "demo": demo,
    }
