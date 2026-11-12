"""Structural features for C overflow families (source-level, no execution)."""
from __future__ import annotations

import re
from typing import Any

FEATURE_NAMES = [
    "strcpy", "strcat", "memcpy", "malloc", "printf", "sprintf", "snprintf",
    "strlen", "sizeof", "free", "array_decl", "global_array", "static_array",
    "member_access", "loop_le", "loop_lt", "malloc_const", "malloc_var",
    "index_by_var", "null_for_length", "zero_after_copy", "signed_int",
    "size_t_param", "add_len_check", "mul_len", "index_times_size",
    "format_identifier", "snprintf_then_printf", "free_after_copy",
    "count_loop", "stack_adjacent", "global_function_pointer", "heap_member_strcpy",
    "heap_poison", "format_direct", "format_via",
]


def _count(code: str, pattern: str) -> int:
    return len(re.findall(pattern, code, re.I | re.S))


def extract_features(code: str) -> dict[str, float]:
    low = code.lower()
    features = {name: 0.0 for name in FEATURE_NAMES}
    for name, pattern in {
        "strcpy": r"\bstrcpy\s*\(", "strcat": r"\bstrcat\s*\(",
        "memcpy": r"\b(?:memcpy|memmove)\s*\(", "malloc": r"\bmalloc\s*\(",
        "printf": r"\bprintf\s*\(", "sprintf": r"\bsprintf\s*\(",
        "snprintf": r"\bsnprintf\s*\(", "strlen": r"\bstrlen\s*\(",
        "sizeof": r"\bsizeof\b", "free": r"\bfree\s*\(",
    }.items():
        features[name] = float(_count(code, pattern))
    features["array_decl"] = float(_count(code, r"\b(?:char|uint8_t|unsigned\s+char)\s+\w+\s*\[\s*\d+\s*\]"))
    features["global_array"] = float(bool(re.search(r"(?m)^(?:char|uint8_t|unsigned\s+char)\s+\w+\s*\[\s*\d+\s*\]", code)))
    features["static_array"] = float(bool(re.search(r"\bstatic\s+(?:char|uint8_t|unsigned\s+char)\s+\w+\s*\[", code)))
    features["member_access"] = float(bool(re.search(r"\w+\s*(?:->|\.)\s*\w+", code)))
    features["loop_le"] = float(bool(re.search(r"for\s*\([^;]*;[^;]*<=\s*[^;]*;", code)))
    features["loop_lt"] = float(bool(re.search(r"for\s*\([^;]*;[^;]*<\s*[^;]*;", code)))
    features["malloc_const"] = float(bool(re.search(r"malloc\s*\(\s*(?:\d+|[A-Z_][A-Z0-9_]*)\s*\)", code)))
    features["malloc_var"] = float(bool(re.search(r"malloc\s*\(\s*[a-z_]\w*\s*\)", code)))
    features["index_by_var"] = float(bool(re.search(r"\w+\s*\[\s*(?:i|len|idx|index)\s*\]", code)))
    features["null_for_length"] = float(bool(re.search(r"\w+\s*\[\s*(?:len|length|n)\s*\]\s*=\s*(?:'\\0'|0)", code)))
    features["zero_after_copy"] = float(bool(re.search(r"(?:memcpy|strcpy)\s*\([^;]+\)\s*;[^{}]{0,80}\w+\s*\[\s*\w+\s*\]\s*=\s*(?:'\\0'|0)", code)))
    features["signed_int"] = float(bool(re.search(r"\bint\s+(?:len|length|n|size)\b", code)))
    features["size_t_param"] = float(bool(re.search(r"\bsize_t\s+(?:len|length|base_len|input_len)\b", code)))
    features["add_len_check"] = float(bool(re.search(r"if\s*\([^)]*\+\s*[^)]*>\s*\d+", code)))
    features["mul_len"] = float(bool(re.search(r"\b\w+\s*=\s*\w+\s*\*\s*\w+\s*;", code)))
    features["index_times_size"] = float(bool(re.search(r"\[\s*\w+\s*\*\s*\w+\s*\]", code)))
    features["format_identifier"] = float(bool(re.search(r"\bprintf\s*\(\s*[a-z_]\w*\s*\)\s*;", code)))
    features["snprintf_then_printf"] = float(bool(re.search(r"snprintf\s*\([^;]+\)\s*;[\s\S]{0,160}printf\s*\(\s*\w+\s*\)", code)))
    features["free_after_copy"] = float(bool(re.search(r"memcpy\s*\([^;]+\)\s*;[\s\S]{0,120}free\s*\(", code)))
    features["count_loop"] = float(bool(re.search(r"for\s*\([^;]*;\s*\w+\s*<\s*count\s*;", code)))
    features["stack_adjacent"] = float(bool(re.search(r"\bis_admin\b", code)))
    features["global_function_pointer"] = float(bool(re.search(r"\(\s*\*\s*\w+\s*\)\s*\(\s*void\s*\)", code)))
    features["heap_member_strcpy"] = float(bool(re.search(r"malloc\s*\([^;]+\).*?strcpy\s*\(\s*\w+\s*->", code, re.S)))
    features["heap_poison"] = float(bool(re.search(r"malloc\s*\(\s*\w+\s*\).*?\[\s*\w+\s*\]\s*=\s*(?:'\\0'|0)", code, re.S)))
    features["format_direct"] = float(bool(re.search(r"\bprintf\s*\(\s*[a-z_]\w*\s*\)\s*;", code)) and not re.search(r"snprintf", code))
    features["format_via"] = float(bool(re.search(r"snprintf\s*\([^;]+\s*\)\s*;[\s\S]{0,200}printf\s*\(\s*\w+\s*\)", code)))
    return features


def vector(code: str) -> list[float]:
    features = extract_features(code)
    return [features[name] for name in FEATURE_NAMES]
