"""Static code repair: deterministic patches, model fallback and the API guard.

Nothing in this module executes the submitted code; the tests assert the patch
text and the honest mode/confidence labels instead.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services.code_repair import detect_language, repair_code

PY_SAMPLE = '''import subprocess
from flask import Flask, request
app = Flask(__name__)

@app.route('/run')
def run():
    command = request.args.get('command', '')
    return subprocess.check_output(command, shell=True, text=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
'''

C_SAMPLE = '''#include <string.h>
void copy(char *input) {
    char buf[8];
    strcpy(buf, input);
}
'''

JS_SAMPLE = '''function render(value) {
  document.getElementById("out").innerHTML = value;
}
'''

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def test_detect_language_uses_hint_and_structure():
    assert detect_language("x = 1", "py") == "python"
    assert detect_language("x = 1", "python3") == "python"
    assert detect_language("#include <stdio.h>\nint main(void){}") == "c"
    assert detect_language(JS_SAMPLE) == "javascript"


def test_python_shell_and_debug_are_patched():
    result = repair_code(PY_SAMPLE, "python")
    assert result["mode"] == "rule"
    assert result["changed"] is True
    assert "import shlex" in result["patched_code"]
    assert "shlex.split(command)" in result["patched_code"]
    assert "shell=False" in result["patched_code"]
    assert "debug=False" in result["patched_code"]
    assert {finding["rule"] for finding in result["findings"]} == {"py.shell-true", "py.flask-debug"}
    assert result["diff"]
    shell = next(f for f in result["findings"] if f["rule"] == "py.shell-true")
    assert shell["cwe"] == "CWE-78"
    assert shell["impact"] and shell["explanation"] and shell["warning"]
    assert shell["references"][0]["url"].startswith("https://cwe.mitre.org/")
    assert result["cwe"] == "CWE-78"
    assert result["warning"] == shell["warning"]


def test_multiline_call_is_still_patched():
    code = """result = subprocess.check_output(command, shell=True,
    stderr=subprocess.STDOUT, text=True)
app.run(debug=True,
    port=5000)
"""
    result = repair_code(code, "python")
    assert "shlex.split(command)" in result["patched_code"]
    assert "shell=False" in result["patched_code"]
    assert "debug=False" in result["patched_code"]
    assert {finding["rule"] for finding in result["findings"]} == {"py.shell-true", "py.flask-debug"}


def test_c_strcpy_becomes_bounded_snprintf():
    result = repair_code(C_SAMPLE, "c")
    assert 'snprintf(buf, sizeof(buf), "%s", input);' in result["patched_code"]
    assert any(finding["rule"] == "c.strcpy" for finding in result["findings"])
    assert any("数组 sizeof" in note or "已声明的堆容量" in note for note in result["notes"])


def test_javascript_findings_do_not_claim_an_unreviewed_rewrite():
    result = repair_code(JS_SAMPLE, "javascript")
    assert result["patched_code"] == JS_SAMPLE
    assert result["changed"] is False
    assert result["confidence"] == "medium"
    assert [finding["rule"] for finding in result["findings"]] == ["js.innerhtml"]
    assert result["findings"][0]["cwe"] == "CWE-79"


def test_unknown_code_is_honest():
    result = repair_code("def add(a, b):\n    return a + b\n", "python")
    assert result["findings"] == []
    assert result["changed"] is False
    assert result["confidence"] == "low"
    assert "没有匹配到" in result["summary"]


def test_hardcoded_secret_evidence_is_masked():
    code = 'password = "super-secret-value"\n'
    result = repair_code(code, "python")
    finding = next(item for item in result["findings"] if item["rule"] == "generic.secret")
    assert "super-secret-value" not in finding["evidence"]


class _FakeClient:
    def __init__(self, content: str | None = None, *, fail: bool = False):
        self.content = content
        self.fail = fail
        self.model = "fake-model"

    def chat_json(self, messages, **kwargs):
        if self.fail:
            raise TimeoutError("nope")
        return type("Result", (), {"content": self.content, "model": self.model})()


def test_model_failure_falls_back_to_rules():
    result = repair_code(PY_SAMPLE, "python", client=_FakeClient(fail=True))
    assert result["mode"] == "rule"
    assert any("回退到规则修复" in note for note in result["notes"])


def test_model_answer_is_validated_and_labelled():
    answer = {
        "language": "python",
        "title": "命令注入",
        "summary": "改为参数列表并关闭调试。",
        "confidence": "high",
        "findings": [{
            "title": "shell=True", "severity": "high", "line": 7,
            "evidence": "shell=True", "advice": "改为 shell=False",
        }],
        "patched_code": "print('fixed')\n",
        "notes": ["仅静态建议"],
    }
    result = repair_code(PY_SAMPLE, "python", client=_FakeClient(__import__("json").dumps(answer)))
    assert result["mode"] == "llm"
    assert result["model"] == "fake-model"
    assert result["patched_code"] == "print('fixed')\n"
    assert result["findings"][0]["rule"] == "llm"


def test_api_requires_csrf_and_rejects_empty_code():
    assert client.post("/api/code/repair", json={"code": "x"}).status_code == 403
    response = client.post(
        "/api/code/repair",
        json={"code": ""},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 422


def test_api_returns_a_repair_without_executing_code():
    response = client.post(
        "/api/code/repair",
        json={"code": PY_SAMPLE, "language": "python"},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 200
    repair = response.json()["repair"]
    assert repair["mode"] in {"rule", "llm"}
    assert "shell=False" in repair["patched_code"]
    assert "subprocess.check_output" in repair["patched_code"]


def test_submitted_code_is_never_executed(tmp_path):
    marker = tmp_path / "pwned.txt"
    code = "open(%r, 'w').write('executed')\n" % str(marker)
    result = repair_code(code, "python")
    assert marker.exists() is False
    assert result["changed"] is False
