"""BinaryRepair MVP —— 图形界面第一步（三屏骨架）。

怎么运行（演示数据模式，默认）：
    cd "C:\\Users\\linyz\\Desktop\\项目文件的系统\\binaryrepair-mvp"
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
然后浏览器打开 http://127.0.0.1:8123

怎么运行（真实数据模式，接成员 1 的 controller）：
    $env:BINARYREPAIR_BACKEND = "http"
    $env:BINARYREPAIR_API_BASE = "http://127.0.0.1:8000"
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
（controller 还没出来时，可以用 tools/stub_backend.py 这个本地假服务先联调。）

怎么运行（本地 controller 模式，接成员 1 的真实任务存储）：
    $env:BINARYREPAIR_BACKEND = "local"
    $env:BINARYREPAIR_DATA_DIR = "var"
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
（任务身份、输入哈希、原始字节会真实写入 SQLite + 文件；Route A/B 执行尚未实现。）

数据来源：
- mock 模式：app/demo.py 的合成数据，页面顶部有"演示数据"横幅，不执行真实二进制；
- http 模式：通过 app/backend.py 调用 controller；页面模板与轮询逻辑完全不变；
- local 模式：直接调用仓库里的 app/services/jobs.py（成员 1 的 SQLite job store），
  任务登记是真实的，修复执行未实现，页面会如实显示 not started / not_run。

语言规范（2026-10-18，团队决定）：
- 界面（UI）可以中文：模板里的标题、按钮、状态徽章、说明都是中文；
- 但**上传 / API / 导出数据一律英文 ASCII**：任务字段、契约、obligations、
  结论原因、变更区域、产物角色、导出 JSON 全部英文。
  服务端会校验表单内容必须是 ASCII，非 ASCII 返回 422；
  上传文件名会转成 ASCII 安全名（避免中文名进入导出数据）。

重要说明（先读这一段）：
- 演示数据模式不是真实修复结果，不能当作"补丁已验证"的证据。
- 阶段（phase）与结论（outcome）是两条独立的轴，界面上必须分开显示。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import i18n
from app.backend import (
    BackendError,
    backend_description,
    backend_mode,
    get_backend,
)

BASE_DIR = Path(__file__).resolve().parent

# 上传大小上限（对应技术设计里的 20 MiB 默认值）
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# 本机会话：launcher 用 ?token=... 引导一次，之后靠 HttpOnly cookie。
# CSRF token 由会话 token 派生，服务端渲染进表单，POST 必须回传。
SESSION_TOKEN = os.environ.get("BINARYREPAIR_SESSION_TOKEN") or secrets.token_urlsafe(32)
CSRF_TOKEN = hmac.new(SESSION_TOKEN.encode("utf-8"), b"gui-csrf", hashlib.sha256).hexdigest()
SESSION_COOKIE = "br_session"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}

# 上传文件名只保留 ASCII 安全字符，避免中文名进入 API/导出数据
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

app = FastAPI(title="BinaryRepair MVP - GUI slice")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# 中文显示标签只给模板用，不会进入 API/导出
templates.env.globals.update(
    phase_labels_zh=i18n.PHASE_LABELS_ZH,
    stage_labels_zh=i18n.STAGE_LABELS_ZH,
    outcome_labels_zh=i18n.OUTCOME_LABELS_ZH,
    state_labels_zh=i18n.STATE_LABELS_ZH,
    value_labels_zh=i18n.VALUE_LABELS_ZH,
    route_names_zh=i18n.ROUTE_NAMES_ZH,
    csrf_token=CSRF_TOKEN,
)

# 数据来源（测试里默认 mock；接真实 controller 时只需换环境变量）
BACKEND = get_backend()
BACKEND_MODE = backend_mode()


def _ascii_filename(name: str) -> str:
    """把上传文件名转成 ASCII 安全名（保留扩展名，去掉路径与中文）。"""
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
    """上传的数据必须是英文 ASCII；发现非 ASCII 直接 422。"""
    if value and any(ord(char) > 127 for char in value):
        raise HTTPException(
            status_code=422,
            detail=f"Field '{field}' must use English/ASCII characters only (no non-ASCII characters).",
        )


@app.exception_handler(BackendError)
async def backend_error_handler(request: Request, exc: BackendError) -> JSONResponse:
    """让 controller 的错误以英文 JSON 返回给浏览器，而不是 500 traceback。"""
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.middleware("http")
async def security_gate(request: Request, call_next):
    """本地安全边界（Technical Design section 11）。

    - Host 必须是 127.0.0.1 / localhost；
    - 首次访问用 ?token=<一次性 token> 引导，换成 HttpOnly + SameSite=Strict cookie，
      并把 token 从地址栏去掉；
    - 之后所有非静态请求都要求有效会话；
    - POST 还要通过同源 Origin 检查（CSRF token 由路由校验）。
    """
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


@app.get("/", response_class=HTMLResponse)
async def index():
    return RedirectResponse(url="/jobs/new", status_code=303)


@app.get("/jobs/new", response_class=HTMLResponse, name="setup_page")
async def setup_page(request: Request):
    """① Setup / Review 屏：上传样本 + 填写契约（F1）。"""
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
    """接收上传并登记输入哈希（F1：输入身份用哈希记录）。

    演示模式只保存哈希和元数据；http 模式把文件转给 controller。
    所有文本字段必须是英文 ASCII（语言规范）。
    """
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
    """② Progress / Comparison 屏：双路线阶段 + 结论（F5）。"""
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
    """批准并启动：mock 模式是演示推进，http 模式转给 controller。

    Unapproved contracts are rejected with an explicit 409 page instead of an
    opaque JSON error.
    """
    _require_csrf(csrf)
    try:
        BACKEND.start(job_id)
    except BackendError as exc:
        return _comparison_response(request, job_id, error=exc.detail, status_code=exc.status_code)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/cancel")
async def cancel_run(request: Request, job_id: str, csrf: str = Form("")):
    """取消：真实版本要等进程树确认终止后才能记录 cancelled。"""
    _require_csrf(csrf)
    try:
        BACKEND.cancel(job_id)
    except BackendError as exc:
        return _comparison_response(request, job_id, error=exc.detail, status_code=exc.status_code)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.get("/jobs/{job_id}/evidence", response_class=HTMLResponse)
async def evidence_page(request: Request, job_id: str):
    """③ Evidence / Export 屏：义务(V0-V5)、范围、哈希、导出（F4/F5）。"""
    snapshot = BACKEND.get_snapshot(job_id)
    return templates.TemplateResponse(
        request,
        "evidence.html",
        {
            "demo": bool(snapshot.get("demo")),
            "job": snapshot,
            "obligations": BACKEND.get_obligations(job_id),
            "artifacts": BACKEND.get_artifacts(job_id),
            "backend_note": backend_description(BACKEND),
        },
    )


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    """给页面轮询用的状态接口（每 2 秒一次，见 static/js/poll.js）。

    返回内容全部英文 ASCII（语言规范）；中文显示标签由前端 JS 映射。
    """
    return JSONResponse(BACKEND.get_snapshot(job_id))


@app.get("/api/jobs/{job_id}/export")
async def export_bundle(job_id: str):
    """导出证据包（英文 JSON）。

    真实版本要包含：原始/候选哈希、契约与测试清单、edit manifest、
    obligations、solver/exploration 记录、工具版本等；并且"导出不代表生产批准"。
    """
    bundle = BACKEND.export_bundle(job_id)
    job_id_for_file = str(bundle.get("job", {}).get("id") or job_id)
    body = json.dumps(bundle, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{job_id_for_file}-evidence.json"',
        },
    )


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "backend": BACKEND_MODE,
        "backend_detail": backend_description(BACKEND),
        "demo": BACKEND_MODE == "mock",
    }
