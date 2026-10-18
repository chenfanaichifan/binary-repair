"""最小冒烟测试：确保三屏和状态接口能打开、Host 校验生效。

运行（在项目根目录）：
    .\\.venv\\Scripts\\python.exe -m pytest -q
"""

from fastapi.testclient import TestClient

from app.main import app

# base_url 用 127.0.0.1，否则会被 local_only 中间件拦成 403
client = TestClient(app, base_url="http://127.0.0.1")

CONTRACT_FORM = {
    "defect": "strcpy 未检查长度，超长输入越界写",
    "valid_tests": "正常输入：hello\n边界输入：8 字节",
    "environment": "Ubuntu x86-64 VM（测试：未执行）",
    "valid_domain": "输入长度 0–64 字节",
    "forbidden": "越界写目标缓冲区",
    "invalid_outcome": "返回错误码 1，不越界",
    "assumptions": "单进程\n未开启栈保护",
}


def _create_job() -> str:
    response = client.post(
        "/jobs",
        data=CONTRACT_FORM,
        files={"binary": ("sample.bin", b"\x7fELF demo bytes", "application/octet-stream")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return response.headers["location"].rstrip("/").rsplit("/", 1)[-1]


def test_setup_page():
    response = client.get("/jobs/new")
    assert response.status_code == 200
    assert "新建任务与契约复核" in response.text
    assert 'data-testid="setup-form"' in response.text


def test_host_check_rejects_foreign_host():
    response = client.get("/jobs/new", headers={"host": "evil.example"})
    assert response.status_code == 403


def test_create_job_and_three_screens():
    job_id = _create_job()

    comparison = client.get(f"/jobs/{job_id}")
    assert comparison.status_code == 200
    assert "Route A" in comparison.text and "Route B" in comparison.text

    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    data = status.json()
    assert data["demo"] is True
    assert data["phase"] == "draft"
    assert len(data["original_sha256"]) == 64

    started = client.post(f"/jobs/{job_id}/start", follow_redirects=False)
    assert started.status_code == 303
    assert client.get(f"/api/jobs/{job_id}").json()["phase"] != "draft"

    evidence = client.get(f"/jobs/{job_id}/evidence")
    assert evidence.status_code == 200
    assert "V0" in evidence.text and "diagnostic candidate" in evidence.text.lower()

    export = client.get(f"/api/jobs/{job_id}/export")
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]
    assert '"demo": true' in export.text


def test_missing_job_returns_404():
    assert client.get("/jobs/does-not-exist").status_code == 404
    assert client.get("/api/jobs/does-not-exist").status_code == 404


def test_cancel_marks_cancelled():
    job_id = _create_job()
    client.post(f"/jobs/{job_id}/start", follow_redirects=False)
    client.post(f"/jobs/{job_id}/cancel", follow_redirects=False)
    data = client.get(f"/api/jobs/{job_id}").json()
    assert data["cancelled"] is True
    assert data["routes"]["A"]["outcome"] == "cancelled"
