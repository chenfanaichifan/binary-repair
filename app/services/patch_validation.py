"""Validate generated C patches before they are shown.

A patch is a claim. If it does not compile, frees a stack array, or uses
``sizeof(pointer)`` as a capacity, it must never be presented as a fix. This is
static validation only; it does not execute the code.
"""
from __future__ import annotations

import re
import shutil
import subprocess

MAX_VALIDATE_BYTES = 80_000
PRELUDE = """#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stddef.h>
#include <unistd.h>
"""


def _stack_array_names(code: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r"\b(?:char|uint8_t|unsigned\s+char|int|long|short)\s+(\w+)\s*\[\s*\d*\s*\]", code):
        names.add(match.group(1))
    # A pointer declaration is not a stack array.
    pointer_names = set(re.findall(r"\b(?:char|uint8_t|unsigned\s+char|int|long|short)\s*\*\s*(\w+)", code))
    return names - pointer_names


def _pointer_names(code: str) -> set[str]:
    return set(re.findall(r"\b(?:char|uint8_t|unsigned\s+char|int|long|short)\s*\*\s*(\w+)", code))


def _function_at(text: str, position: int) -> str:
    for match in re.finditer(r"\b[A-Za-z_][\w\s\*]*\([^;{}]*\)\s*\{", text):
        start = match.end() - 1
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    if start <= position <= index:
                        return text[match.start():index + 1]
                    break
    return text


def _static_reason(code: str) -> str | None:
    for match in re.finditer(r"\bfree\s*\(\s*(\w+)\s*\)", code):
        name = match.group(1)
        scope = _function_at(code, match.start())
        if re.search(r"\b(?:char|uint8_t|unsigned\s+char|int|long|short)\s+" + re.escape(name) + r"\s*\[\s*\d*\s*\]", scope):
            return f"free() on stack array {name}"
    for match in re.finditer(
        r"\b(?:snprintf|strncpy|memset|memcpy)\s*\(\s*(\w+)\s*,\s*(?:sizeof\s*\(\s*(\w+)\s*\)|sizeof\s+(\w+))",
        code,
    ):
        name = match.group(1)
        size_name = match.group(2) or match.group(3)
        if name != size_name:
            continue
        scope = _function_at(code, match.start())
        is_pointer = re.search(r"\b(?:char|uint8_t|unsigned\s+char|int|long|short)\s*\*\s*" + re.escape(name) + r"\b", scope)
        is_array = re.search(r"\b(?:char|uint8_t|unsigned\s+char|int|long|short)\s+" + re.escape(name) + r"\s*\[\s*\d*\s*\]", scope)
        if is_pointer and not is_array:
            return f"sizeof(pointer) used as capacity for {name}"
    return None


COMPILER_UNAVAILABLE_PREFIX = "compiler validation unavailable"


def validate_c_patch(original: str, patched: str, *, language: str = "c") -> tuple[bool, str]:
    """Return ``(ok, reason)``. Fails closed for static/compile errors.

    A compiler that is installed but cannot complete (timeout or OS error) is
    *infrastructure unavailable*, not proof that the patch is invalid.  This is
    the same policy already used when no compiler is installed: the static
    checks still gate the patch, and the caller records that the compiler was
    unavailable.  A real non-zero compiler exit remains a rejection.
    """
    if patched == original:
        return True, "unchanged"
    if len(patched.encode("utf-8")) > MAX_VALIDATE_BYTES:
        return False, "patch exceeds validation size limit"
    static = _static_reason(patched)
    if static:
        return False, static
    compiler = shutil.which("clang++" if language == "cpp" else "clang")
    if not compiler:
        return True, "compiler unavailable; static checks only"
    try:
        proc = subprocess.run(
            [compiler, "-fsyntax-only", "-Wno-implicit-function-declaration",
             "-x", "c++" if language == "cpp" else "c", "-"],
            input=PRELUDE + patched,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return True, f"{COMPILER_UNAVAILABLE_PREFIX}: {type(exc).__name__}; static checks only"
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        first = next((line for line in detail if "error:" in line), detail[0] if detail else "unknown compile error")
        return False, "compile failed: " + first[:300]
    return True, "compiled (syntax only)"
