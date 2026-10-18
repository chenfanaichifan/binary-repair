"""BinaryRepair MVP —— 图形界面第一步（三屏骨架）。

怎么运行：
    cd "C:\\Users\\linyz\\Desktop\\项目文件的系统\\binaryrepair-mvp"
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8123
然后浏览器打开 http://127.0.0.1:8123

重要说明（先读这一段）：
- 这是 GUI-only 开发模式：阶段推进和结论都是演示数据（fixture），页面顶部有明确标注；
  它不是真实修复结果，不能当作“补丁已验证”的证据。
- 真实链路（VM 内筛查、Route A/B、angr 校验）由其他成员实现后再接入。这里的字段
  按 PRD F1/F4/F5 与 TechDesign §6/§7 设计，之后替换数据源，页面结构不用大改。
- 阶段（phase）与结论（outcome）是两条独立的轴，界面上必须分开显示。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import demo

BASE_DIR = Path(__file__).resolve().parent

# GUI-only 开发模式开关。接真实后端时把它关掉，并让 demo 数据来源换成真实的 job 存储。
DEMO = True

# 上传大小上限（对应技术设计里的 20 MiB 默认值）
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

app = FastAPI(title="BinaryRepair MVP — GUI slice")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.middleware("http")
async def local_only(request: Request, call_next):
    """只接受本机访问：Host 必须是 127.0.0.1 / localhost。

    这是技术设计 §11 的第一条安全要求（绑定 127.0.0.1）。它挡不住所有攻击，
    但能挡住“恶意网页把请求发到你的本地服务”这一类问题的一部分。
    后续还要加 session token、CSRF、Origin 校验。
    """
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if host not in {"127.0.0.1", "localhost"}:
        return JSONResponse({"detail": "只允许本机访问（Host 校验失败）"}, status_code=403)
    return await call_next(request)


def _job_or_404(job_id: str) -> dict:
    job = demo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
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
    """
    raw = await binary.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 20 MiB 上限")
    if not raw:
        raise HTTPException(status_code=422, detail="上传文件为空")

    original_sha256 = hashlib.sha256(raw).hexdigest()
    job = demo.create_job(
        original_sha256=original_sha256,
        filename=binary.filename or "sample.bin",
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
    """演示用“批准并启动”：真实版本应由成员 1 的 controller 提供。"""
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
    """③ Evidence / Export 屏：义务(V0–V5)、范围、哈希、导出（F4/F5）。"""
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
    """给页面轮询用的状态接口（每 2 秒一次，见 static/js/poll.js）。"""
    job = _job_or_404(job_id)
    return JSONResponse(demo.snapshot(job))


@app.get("/api/jobs/{job_id}/export")
async def export_bundle(job_id: str):
    """导出证据包（演示版：JSON）。

    真实版本要包含：原始/候选哈希、契约与测试清单、edit manifest、
    obligations、solver/exploration 记录、工具版本等；并且“导出不代表生产批准”。
    """
    job = _job_or_404(job_id)
    snapshot = demo.snapshot(job)
    bundle = {
        "schema_version": 1,
        "demo": True,
        "note": "GUI 开发模式的合成数据；未执行真实修复，导出不代表生产批准。",
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
