"""BinaryRepair MVP —— 图形界面第一步（三屏骨架）。

怎么运行：
    cd "C:\\Users\\linyz\\Desktop\\项目文件的系统\\binaryrepair-mvp"
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
然后浏览器打开 http://127.0.0.1:8123

语言规范（2026-10-18，团队决定）：
- 界面（UI）可以中文：模板里的标题、按钮、状态徽章、说明都是中文；
- 但**上传 / API / 导出数据一律英文 ASCII**：任务字段、契约、obligations、
  结论原因、变更区域、产物角色、导出 JSON 全部英文。
  服务端会校验表单内容必须是 ASCII，非 ASCII 返回 422；
  上传文件名会转成 ASCII 安全名（避免中文名进入导出数据）。

重要说明（先读这一段）：
- 这是 GUI-only 开发模式：阶段推进和结论都是演示数据（fixture），页面顶部有明确标注；
  它不是真实修复结果，不能当作"补丁已验证"的证据。
- 真实链路（VM 内筛查、Route A/B、angr 校验）由其他成员实现后再接入。这里的字段
  按 PRD F1/F4/F5 与 TechDesign §6/§7 设计，之后替换数据源，页面结构不用大改。
- 阶段（phase）与结论（outcome）是两条独立的轴，界面上必须分开显示。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import demo, i18n

BASE_DIR = Path(__file__).resolve().parent

# GUI-only 开发模式开关。接真实后端时把它关掉，并让 demo 数据来源换成真实的 job 存储。
DEMO = True

# 上传大小上限（对应技术设计里的 20 MiB 默认值）
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

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
)


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


@app.middleware("http")
async def local_only(request: Request, call_next):
    """只接受本机访问：Host 必须是 127.0.0.1 / localhost。

    这是技术设计 §11 的第一条安全要求（绑定 127.0.0.1）。它挡不住所有攻击，
    但能挡住"恶意网页把请求发到你的本地服务"这一类问题的一部分。
    后续还要加 session token、CSRF、Origin 校验。
    """
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if host not in {"127.0.0.1", "localhost"}:
        return JSONResponse({"detail": "Local access only (host check failed)."}, status_code=403)
    return await call_next(request)


def _job_or_404(job_id: str) -> dict:
    job = demo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/", response_class=HTMLResponse)
async def index():
    return RedirectResponse(url="/jobs/new", status_code=303)


@app.get("/jobs/new", response_class=HTMLResponse, name="setup_page")
async def setup_page(request: Request):
    """① Setup / Review 屏：上传样本 + 填写契约（F1）。"""
    return templates.TemplateResponse(
        request,
        "setup.html",
        {"demo": DEMO, "job": None},
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
):
    """接收上传并登记输入哈希（F1：输入身份用哈希记录）。

    演示模式：只保存哈希和元数据，不解析 ELF、不执行任何二进制。
    所有文本字段必须是英文 ASCII（语言规范）。
    """
    raw = await binary.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 20 MiB limit.")
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    # 上传的数据必须英文 ASCII（界面可以中文，但数据不行）
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

    original_sha256 = hashlib.sha256(raw).hexdigest()
    job = demo.create_job(
        original_sha256=original_sha256,
        filename=_ascii_filename(binary.filename or "sample.bin"),
        defect=defect,
        valid_tests=valid_tests,
        environment=environment,
        valid_domain=valid_domain,
        forbidden=forbidden,
        invalid_outcome=invalid_outcome,
        assumptions=assumptions,
    )
    return RedirectResponse(url=f"/jobs/{job['id']}", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def comparison_page(request: Request, job_id: str):
    """② Progress / Comparison 屏：双路线阶段 + 结论（F5）。"""
    job = _job_or_404(job_id)
    snapshot = demo.snapshot(job)
    return templates.TemplateResponse(
        request,
        "comparison.html",
        {"demo": DEMO, "job": snapshot},
    )


@app.post("/jobs/{job_id}/start")
async def start_run(job_id: str):
    """演示用"批准并启动"：真实版本应由成员 1 的 controller 提供。"""
    job = _job_or_404(job_id)
    demo.start(job)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/cancel")
async def cancel_run(job_id: str):
    """取消：真实版本要等进程树确认终止后才能记录 cancelled。"""
    job = _job_or_404(job_id)
    demo.cancel(job)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.get("/jobs/{job_id}/evidence", response_class=HTMLResponse)
async def evidence_page(request: Request, job_id: str):
    """③ Evidence / Export 屏：义务(V0-V5)、范围、哈希、导出（F4/F5）。"""
    job = _job_or_404(job_id)
    snapshot = demo.snapshot(job)
    return templates.TemplateResponse(
        request,
        "evidence.html",
        {
            "demo": DEMO,
            "job": snapshot,
            "obligations": demo.obligations(job),
            "artifacts": demo.artifacts(job),
        },
    )


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    """给页面轮询用的状态接口（每 2 秒一次，见 static/js/poll.js）。

    返回内容全部英文 ASCII（语言规范）；中文显示标签由前端 JS 映射。
    """
    job = _job_or_404(job_id)
    return JSONResponse(demo.snapshot(job))


@app.get("/api/jobs/{job_id}/export")
async def export_bundle(job_id: str):
    """导出证据包（演示版：英文 JSON）。

    真实版本要包含：原始/候选哈希、契约与测试清单、edit manifest、
    obligations、solver/exploration 记录、工具版本等；并且"导出不代表生产批准"。
    """
    job = _job_or_404(job_id)
    snapshot = demo.snapshot(job)
    bundle = {
        "schema_version": 1,
        "demo": True,
        "content_language": "en",
        "note": (
            "GUI development mode: synthetic data; no real repair was executed. "
            "This export is not production approval."
        ),
        "job": snapshot,
        "obligations": demo.obligations(job),
        "artifacts": demo.artifacts(job),
    }
    body = json.dumps(bundle, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{job["id"]}-evidence.json"',
        },
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True, "demo": DEMO}
