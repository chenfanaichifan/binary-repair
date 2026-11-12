"""Regression tests for the five C buffer-overflow shapes."""
from app.services.code_repair import repair_code

SAMPLES = {
    "off_by_one": '''#include <string.h>
void process_string(const char *input) {
    char buffer[32];
    size_t len = strlen(input);
    for (size_t i = 0; i <= len; i++) {
        buffer[i] = input[i];
    }
}
''',
    "safe_copy": '''#include <stdio.h>
void custom_safe_copy(char *dest, const char *src, size_t dest_size) {
    size_t i;
    for (i = 0; i < dest_size && src[i] != '\\0'; i++) {
        dest[i] = src[i];
    }
    dest[i] = '\\0';
}
''',
    "length_field": '''#include <stdlib.h>
#include <string.h>
#define MAX_PAYLOAD 128
typedef struct { unsigned short type; unsigned short payload_len; } PacketHeader;
void parse_packet(const unsigned char *raw_data) {
    PacketHeader *header = (PacketHeader *)raw_data;
    unsigned char *buffer = (unsigned char *)malloc(MAX_PAYLOAD);
    if (buffer == NULL) return;
    memcpy(buffer, raw_data, header->payload_len);
    free(buffer);
}
''',
    "sprintf": '''#include <stdio.h>
void log_message(const char *user_msg) {
    char log_buffer[128];
    sprintf(log_buffer, "[LOG] User says: %s", user_msg);
}
''',
    "signed_length": '''#include <string.h>
void copy_user_input(int len, const char *data) {
    char local_buf[1024];
    if (len < 1024) {
        memcpy(local_buf, data, len);
        local_buf[1023] = '\\0';
    }
}
''',
}


def test_five_c_buffer_overflow_shapes_are_detected_and_patched():
    expected = {
        "off_by_one": ("c.off-by-one-loop", "CWE-193"),
        "safe_copy": ("c.safe-copy-off-by-one", "CWE-193"),
        "length_field": ("c.length-field-heap", "CWE-190"),
        "sprintf": ("c.sprintf", "CWE-120"),
        "signed_length": ("c.signed-length", "CWE-195"),
    }
    for name, code in SAMPLES.items():
        result = repair_code(code, "c")
        rules = {item["rule"] for item in result["findings"]}
        assert expected[name][0] in rules, (name, rules)
        assert result["cwe"] == expected[name][1], (name, result["cwe"], rules)
        assert result["patched_code"] != code


def test_off_by_one_patch_reserves_terminator_and_capacity():
    result = repair_code(SAMPLES["off_by_one"], "c")
    patch = result["patched_code"]
    assert "len >= sizeof(buffer)" in patch
    assert "memcpy(buffer, input, len + 1)" in patch


def test_safe_copy_zero_capacity_and_nul_slot():
    patch = repair_code(SAMPLES["safe_copy"], "c")["patched_code"]
    assert "if (dest_size == 0) return;" in patch
    assert "i + 1 < dest_size" in patch
    assert "dest[i] = '\\0';" in patch


def test_length_field_guard_precedes_copy():
    patch = repair_code(SAMPLES["length_field"], "c")["patched_code"]
    assert "header->payload_len > MAX_PAYLOAD" in patch
    assert "free(buffer); return;" in patch
    assert patch.index("header->payload_len > MAX_PAYLOAD") < patch.index("memcpy(buffer")


def test_sprintf_patch_uses_snprintf():
    patch = repair_code(SAMPLES["sprintf"], "c")["patched_code"]
    assert "snprintf(log_buffer, sizeof(log_buffer)" in patch


def test_signed_length_patch_rejects_negative_and_casts():
    patch = repair_code(SAMPLES["signed_length"], "c")["patched_code"]
    assert "len >= 0" in patch
    assert "(size_t)len < sizeof(local_buf)" in patch
    assert "(size_t)len" in patch
