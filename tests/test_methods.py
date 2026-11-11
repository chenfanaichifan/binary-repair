"""The methods page: a research-backed map, not a claim of verification."""

from fastapi.testclient import TestClient

from app.main import SESSION_TOKEN, app

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def test_methods_page_covers_the_toolchain_and_the_boundary():
    page = client.get("/methods")
    assert page.status_code == 200
    for text in ("修复链", "Ghidra", "angr", "Frida", "Diaphora", "AFL++",
                 "验证要回答的四个问题", "不构成"):
        assert text in page.text, text
    assert 'data-testid="methods-page"' in page.text
    assert "https://angr.io/" in page.text
    assert "https://cwe.mitre.org/" in page.text


def test_methods_is_reachable_from_the_shell_and_workbench():
    shell = client.get("/agent/new")
    assert 'href="/methods"' in shell.text
    assert 'data-testid="sidebar-methods"' in shell.text
    workbench = client.get("/agent")
    assert 'href="/methods"' in workbench.text
    assert "查看方法库" in workbench.text
