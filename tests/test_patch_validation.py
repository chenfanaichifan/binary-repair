"""No invalid patch may be presented as a fix."""
import subprocess
from types import SimpleNamespace

from app.services import patch_validation
from app.services.code_repair import repair_code
from app.services.patch_validation import validate_c_patch

OFF_BY_ONE = '''#include <string.h>
void process_string(const char *input) {
    char buffer[32];
    size_t len = strlen(input);
    for (size_t i = 0; i <= len; i++) {
        buffer[i] = input[i];
    }
}
'''


def test_rejects_free_on_stack_array():
    original = "void f(){char buf[8];buf[0]=0;}"
    bad = "void f(){char buf[8];if(1){free(buf);return;}buf[0]=0;}"
    ok, reason = validate_c_patch(original, bad)
    assert ok is False
    assert "free() on stack array" in reason


def test_rejects_undefined_identifiers_via_compiler():
    original = "void f(const char *p){char buf[8];strcpy(buf,p);}"
    bad = "void f(const char *p){char buf[8];if((size_t)1>n){free(buf);return;}strcpy(buf,p);}"
    ok, reason = validate_c_patch(original, bad)
    assert ok is False
    assert "compile failed" in reason or "free() on stack array" in reason


def test_rejects_sizeof_pointer_capacity():
    original = "void f(const char*p){char*buf=malloc(16);strcpy(buf,p);}"
    bad = "void f(const char*p){char*buf=malloc(16);snprintf(buf,sizeof(buf),\"%s\",p);}"
    ok, reason = validate_c_patch(original, bad)
    assert ok is False
    assert "sizeof(pointer)" in reason


def test_heap_strcpy_uses_malloc_capacity_not_pointer_size():
    code = "void f(const char*input){char *buf=(char*)malloc(16);if(!buf)return;strcpy(buf,input);free(buf);}"
    result = repair_code(code, "c")
    assert result.get("patch_rejected") is not True
    assert "snprintf(buf, 16," in result["patched_code"]
    assert "sizeof(buf)" not in result["patched_code"]


def test_stack_memcpy_guard_has_no_free_and_compiles():
    code = "void f(const char*src,size_t len){char buf[24];memcpy(buf,src,len);}"
    result = repair_code(code, "c")
    assert result.get("patch_rejected") is not True
    assert "free(buf)" not in result["patched_code"]
    assert "if (len > sizeof(buf)) return;" in result["patched_code"]


def test_changed_line_comment_is_updated_not_left_misleading():
    code = 'void f(const char*p){char buf[8];strcpy(buf,p); /* ❌ overflow */}'
    result = repair_code(code, "c")
    assert result.get("patch_rejected") is not True
    assert "✅ patched:" in result["patched_code"]
    assert "/* ❌ overflow */" not in result["patched_code"]


def test_realloc_capacity_is_updated_after_pointer_assignment():
    code = (
        "void f(const char*input){size_t cap=8;char*buf=malloc(cap);if(!buf)return;"
        "size_t need=strlen(input)+1;if(need>cap){char*nb=realloc(buf,need);if(!nb){free(buf);return;}buf=nb;}"
        "strcpy(buf,input);free(buf);}"
    )
    result = repair_code(code, "c")
    assert result.get("patch_rejected") is not True
    assert "cap = need;" in result["patched_code"]
    assert "snprintf(buf, need," in result["patched_code"]


def test_unconfigured_model_says_ai_was_not_called(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import CSRF_TOKEN, SESSION_TOKEN, app
    monkeypatch.delenv("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("app.services.assistant_key_store.load_key", lambda: "")
    client = TestClient(app, base_url="http://127.0.0.1")
    client.get("/?token=" + SESSION_TOKEN)
    response = client.post(
        "/api/code/repair",
        json={"code": "void f(char *p){sprintf(p, \"%s\", \"x\");}", "language": "c"},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 200
    notes = response.json()["repair"]["notes"]
    assert any("AI 没有被调用" in note for note in notes)


def test_ai_transport_failure_is_visible_and_falls_back_to_rule():
    from app.services.code_repair import repair_code

    class FailingClient:
        def chat_json(self, *args, **kwargs):
            raise TimeoutError("provider timeout")

    result = repair_code("void f(char *p){strcpy(p, \"x\");}", "c", client=FailingClient())
    assert result["repair_origin"] == "rule"
    assert result["ai_attempted"] is True
    assert result["ai_error"] == "TimeoutError"
    assert result["ai_fallback"] is True


def test_rule_only_path_is_not_labelled_as_ai():
    from app.services.code_repair import repair_code

    result = repair_code("void f(char *p){strcpy(p, \"x\");}", "c")
    assert result["repair_origin"] == "rule"
    assert result["ai_attempted"] is False


def test_compiler_timeout_is_not_a_patch_rejection(monkeypatch):
    """A transient compiler problem must not erase a statically valid rule patch.

    This is the regression for the Ubuntu #15 flake: an 8 s syntax-check timeout
    made ``_finalize_patch`` revert the off-by-one patch, so the test saw
    ``patched_code == original`` and reported a false functional failure.
    """
    monkeypatch.setattr(patch_validation.shutil, "which", lambda name: "/usr/bin/fake-clang")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("clang", 20)

    monkeypatch.setattr(patch_validation.subprocess, "run", timeout)
    ok, reason = validate_c_patch("void f(void){}", "void f(void){return;}")
    assert ok is True
    assert "compiler validation unavailable" in reason

    result = repair_code(OFF_BY_ONE, "c")
    assert result.get("patch_rejected") is not True
    assert result["patched_code"] != OFF_BY_ONE
    assert result.get("patch_validation") == "compiler_unavailable"
    assert any("编译器校验不可用" in note for note in result["notes"])


def test_actual_compiler_error_still_rejects(monkeypatch):
    monkeypatch.setattr(patch_validation.shutil, "which", lambda name: "/usr/bin/fake-clang")
    monkeypatch.setattr(
        patch_validation.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stderr="x.c:1:1: error: definitely not C\n",
        ),
    )
    ok, reason = validate_c_patch("void f(void){}", "void f(void){return;}")
    assert ok is False
    assert "compile failed" in reason

    result = repair_code(OFF_BY_ONE, "c")
    assert result.get("patch_rejected") is True
    assert result["patched_code"] == OFF_BY_ONE
