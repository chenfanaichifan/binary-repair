"""No invalid patch may be presented as a fix."""
from app.services.code_repair import repair_code
from app.services.patch_validation import validate_c_patch


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
