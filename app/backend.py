"""数据来源适配器：GUI 不直接依赖 demo.py，而是通过这一层取数据。

两种模式（环境变量 BINARYREPAIR_BACKEND 切换）：

- ``mock``（默认）：使用 ``app/demo.py`` 的合成数据，用于演示 / 离线开发；
  页面顶部会显示"演示数据"横幅，不执行真实二进制。
- ``http``：调用成员 1 的 controller API（真实数据）。真实 controller 没出来之前，
  可以用 ``tools/stub_backend.py`` 这个本地假服务联调。

约定（2026-10-18 团队决定）：
- GUI 只消费下面这组接口；页面模板与轮询逻辑不关心数据来自哪里。
- 传输的数据一律英文 ASCII；HTTP 模式会扫描响应，发现中日韩字符直接报错
  （语言规范由 tests/test_language_policy.py 与 tests/test_backend_contract.py 守护）。
- 契约（要与成员 1 对齐的最小集合）：
    POST /api/jobs                          multipart -> {"id": str, ...}
    GET  /api/jobs/{id}                     快照 -> snapshot JSON（见 get_snapshot）
    POST /api/jobs/{id}/start               启动
    POST /api/jobs/{id}/cancel              取消
    GET  /api/jobs/{id}/obligations         {"A": [...], "B": [...]}
    GET  /api/jobs/{id}/artifacts           {"A": [...], "B": [...]}
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Protocol

import httpx

from app import demo

BACKEND_ENV = "BINARYREPAIR_BACKEND"
API_BASE_ENV = "BINARYREPAIR_API_BASE"
API_TIMEOUT_ENV = "BINARYREPAIR_API_TIMEOUT"
DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 5.0

_CJK_PATTERN = re.compile(
    r"[\u2e80-\u2fff\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)


def _has_cjk(text: str) -> bool:
    return bool(_CJK_PATTERN.search(text))


def _has_cjk_in_payload(payload: Any) -> bool:
    """递归扫描 JSON，确认没有中日韩字符（语言规范）。"""
    if isinstance(payload, str):
        return _has_cjk(payload)
    if isinstance(payload, dict):
        return any(_has_cjk_in_payload(value) for value in payload.values()) or any(
            _has_cjk_in_payload(key) for key in payload
        )
    if isinstance(payload, (list, tuple)):
        return any(_has_cjk_in_payload(item) for item in payload)
    return False


class BackendError(RuntimeError):
    """数据来源出错：由 main.py 转成浏览器可见的英文错误。"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class Backend(Protocol):
    mode: str

    def create_job(self, *, binary_bytes: bytes, filename: str, defect: str, valid_tests: str,
                   environment: str, valid_domain: str, forbidden: str, invalid_outcome: str,
                   assumptions: str) -> str: ...

    def get_snapshot(self, job_id: str) -> dict[str, Any]: ...
    def start(self, job_id: str) -> None: ...
    def cancel(self, job_id: str) -> None: ...
    def get_obligations(self, job_id: str) -> dict[str, list[dict[str, Any]]]: ...
    def get_artifacts(self, job_id: str) -> dict[str, list[dict[str, Any]]]: ...
    def export_bundle(self, job_id: str) -> dict[str, Any]: ...


class MockBackend:
    """演示数据模式：包装 app/demo.py（合成数据，页面会明确标注）。"""

    mode = "mock"

    def create_job(self, *, binary_bytes: bytes, filename: str, defect: str, valid_tests: str,
                   environment: str, valid_domain: str, forbidden: str, invalid_outcome: str,
                   assumptions: str) -> str:
        job = demo.create_job(
            original_sha256=hashlib.sha256(binary_bytes).hexdigest(),
            filename=filename,
            defect=defect,
            valid_tests=valid_tests,
            environment=environment,
            valid_domain=valid_domain,
            forbidden=forbidden,
            invalid_outcome=invalid_outcome,
            assumptions=assumptions,
        )
        return job["id"]

    def _job(self, job_id: str) -> dict[str, Any]:
        job = demo.get_job(job_id)
        if job is None:
            raise BackendError(404, "Job not found.")
        return job

    def get_snapshot(self, job_id: str) -> dict[str, Any]:
        return demo.snapshot(self._job(job_id))

    def start(self, job_id: str) -> None:
        demo.start(self._job(job_id))

    def cancel(self, job_id: str) -> None:
        demo.cancel(self._job(job_id))

    def get_obligations(self, job_id: str) -> dict[str, list[dict[str, Any]]]:
        return demo.obligations(self._job(job_id))

    def get_artifacts(self, job_id: str) -> dict[str, list[dict[str, Any]]]:
        return demo.artifacts(self._job(job_id))

    def export_bundle(self, job_id: str) -> dict[str, Any]:
        snapshot = self.get_snapshot(job_id)
        return {
            "schema_version": 1,
            "demo": bool(snapshot.get("demo")),
            "content_language": "en",
            "note": (
                "GUI development mode: synthetic data; no real repair was executed. "
                "This export is not production approval."
            ),
            "job": snapshot,
            "obligations": self.get_obligations(job_id),
            "artifacts": self.get_artifacts(job_id),
        }


class HttpBackend:
    """真实数据模式：调用成员 1 的 controller API。

    ``transport`` 参数只给测试用（httpx.MockTransport），生产运行不要传。
    """

    mode = "http"

    def __init__(self, base_url: str | None = None, timeout: float | None = None,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = (base_url or os.environ.get(API_BASE_ENV, DEFAULT_API_BASE)).rstrip("/")
        if timeout is None:
            try:
                timeout = float(os.environ.get(API_TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS))
            except ValueError:
                timeout = DEFAULT_TIMEOUT_SECONDS
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    # ---------- 内部工具 ----------

    def _decode(self, response: httpx.Response, where: str) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise BackendError(502, f"Backend returned invalid JSON for {where}.") from exc
        if _has_cjk_in_payload(payload):
            raise BackendError(
                502,
                f"Backend returned non-English data for {where} (language policy violation).",
            )
        return payload

    def _request(self, method: str, path: str, *, where: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendError(
                502, f"Backend unavailable at {self.base_url}: {exc.__class__.__name__}."
            ) from exc

        if response.status_code >= 400:
            detail = f"Backend request failed for {where}."
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
                detail = payload["detail"]
            status = response.status_code if response.status_code in (400, 404, 409, 422) else 502
            raise BackendError(status, detail)

        if response.status_code == 204 or not response.content:
            return None
        return self._decode(response, where)

    # ---------- Backend 接口 ----------

    def create_job(self, *, binary_bytes: bytes, filename: str, defect: str, valid_tests: str,
                   environment: str, valid_domain: str, forbidden: str, invalid_outcome: str,
                   assumptions: str) -> str:
        payload = self._request(
            "POST",
            "/api/jobs",
            where="create_job",
            files={"binary": (filename, binary_bytes, "application/octet-stream")},
            data={
                "defect": defect,
                "valid_tests": valid_tests,
                "environment": environment,
                "valid_domain": valid_domain,
                "forbidden": forbidden,
                "invalid_outcome": invalid_outcome,
                "assumptions": assumptions,
            },
        )
        job_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(job_id, str) or not job_id:
            raise BackendError(502, "Backend create_job response is missing a string 'id'.")
        return job_id

    def get_snapshot(self, job_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/jobs/{job_id}", where="get_snapshot")
        if not isinstance(payload, dict) or "phase" not in payload or "routes" not in payload:
            raise BackendError(502, "Backend snapshot is missing required fields (phase, routes).")
        return payload

    def start(self, job_id: str) -> None:
        self._request("POST", f"/api/jobs/{job_id}/start", where="start")

    def cancel(self, job_id: str) -> None:
        self._request("POST", f"/api/jobs/{job_id}/cancel", where="cancel")

    def get_obligations(self, job_id: str) -> dict[str, list[dict[str, Any]]]:
        payload = self._request("GET", f"/api/jobs/{job_id}/obligations", where="get_obligations")
        if not isinstance(payload, dict):
            raise BackendError(502, "Backend obligations response must be an object.")
        return payload

    def get_artifacts(self, job_id: str) -> dict[str, list[dict[str, Any]]]:
        payload = self._request("GET", f"/api/jobs/{job_id}/artifacts", where="get_artifacts")
        if not isinstance(payload, dict):
            raise BackendError(502, "Backend artifacts response must be an object.")
        return payload

    def export_bundle(self, job_id: str) -> dict[str, Any]:
        """控制器暂时没有导出端点，先在 GUI 侧组装英文证据包。

        等成员 1 提供 POST /api/runs/{id}/exports 之后，改成调用它即可。
        """
        snapshot = self.get_snapshot(job_id)
        return {
            "schema_version": 1,
            "demo": bool(snapshot.get("demo")),
            "content_language": "en",
            "note": "Export assembled by the GUI from controller data. This export is not production approval.",
            "job": snapshot,
            "obligations": self.get_obligations(job_id),
            "artifacts": self.get_artifacts(job_id),
        }


def backend_mode() -> str:
    mode = os.environ.get(BACKEND_ENV, "mock").strip().lower() or "mock"
    if mode not in {"mock", "http"}:
        raise ValueError(f"{BACKEND_ENV} must be 'mock' or 'http', got {mode!r}.")
    return mode


def get_backend() -> Backend:
    """按环境变量创建数据来源。main.py 在启动时调用一次。"""
    if backend_mode() == "http":
        return HttpBackend()
    return MockBackend()


def backend_description(backend: Backend) -> str:
    """给页面/健康检查显示的数据来源说明（英文，可进入 API）。"""
    if backend.mode == "http":
        return f"controller API at {backend.base_url}"  # type: ignore[attr-defined]
    return "synthetic demo data (no execution)"


__all__ = [
    "Backend",
    "BackendError",
    "HttpBackend",
    "MockBackend",
    "backend_description",
    "backend_mode",
    "get_backend",
]
