"""Deterministic assembly preflight policy for the assembly-repair path.

The policy never rewrites model text.  It classifies concrete violations so the
model can be asked for a corrected block; the assembler and native gate remain
authoritative.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

_LABEL_RE = re.compile(r"^[A-Za-z_.][A-Za-z0-9_.$]*:\s*$")
_ABS_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_BRANCH_RE = re.compile(
    r"^(j[a-z]+|loop[a-z]*)\s+(.+)$", re.IGNORECASE)
_CALL_RE = re.compile(r"^(call|bl)\s+(.+)$", re.IGNORECASE)
_DIRECTIVE_OK = re.compile(
    r"^\s*\.(text|globl|global|intel_syntax)\b[^\n]*$", re.IGNORECASE)
_DENIED_SUBSTR = (
    "syscall", "sysenter", "int ", "int3", "hlt", "cli", "sti", "in ",
    "out ", "wrmsr", "rdmsr", "iret", "ud2", "swapgs", "svc", "hvc",
    "smc", "brk", "eret", "msr", "mrs", "blr", "br ",
)


@dataclass
class PolicyDiagnostic:
    error_class: str
    message: str
    line: int | None = None
    token: str | None = None
    retryable: bool = True

    def to_dict(self) -> dict:
        return {
            "error_class": self.error_class,
            "message": self.message,
            "line": self.line,
            "token": self.token,
            "retryable": self.retryable,
        }


@dataclass
class PolicyResult:
    diagnostics: list[PolicyDiagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics

    def to_dict(self) -> dict:
        return {"ok": self.ok,
                "diagnostics": [item.to_dict() for item in self.diagnostics]}


def _strip_comments(text: str, arch: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw
        if arch == "i386" and "#" in line:
            line = line.split("#", 1)[0]
        if "//" in line:
            line = line.split("//", 1)[0]
        rows.append((number, line.strip()))
    return rows


def check_assembly_policy(text: str, arch: str,
                          allowed_calls: Iterable[object] = ()) -> PolicyResult:
    """Reject absolute branch targets, directives and forbidden instructions.

    Calls are not rejected here: the existing call-whitelist validator owns that
    check and accepted calls may use either a local name or an exact allowed VA.
    """
    allowed_names = set()
    for item in allowed_calls or ():
        name = getattr(item, "name", None)
        if name is None and isinstance(item, dict):
            name = item.get("name")
        if name:
            allowed_names.add(str(name))
    result = PolicyResult()
    if not isinstance(text, str) or not text.strip():
        result.diagnostics.append(PolicyDiagnostic("empty_assembly", "empty assembly"))
        return result
    instruction_lines = 0
    for number, line in _strip_comments(text, arch):
        if not line:
            continue
        if _LABEL_RE.match(line):
            continue
        if line.startswith("."):
            if not _DIRECTIVE_OK.match(line):
                result.diagnostics.append(PolicyDiagnostic(
                    "directive", f"assembly directive not allowed: {line[:60]}",
                    number, line.split()[0]))
            continue
        low = line.lower()
        if any(token in low for token in _DENIED_SUBSTR):
            token = next(token for token in _DENIED_SUBSTR if token in low)
            result.diagnostics.append(PolicyDiagnostic(
                "forbidden_token", f"forbidden assembly construct: {line[:60]}",
                number, token.strip()))
            continue
        branch = _BRANCH_RE.match(line)
        if branch:
            operand = branch.group(2).strip()
            if _ABS_HEX_RE.search(operand):
                result.diagnostics.append(PolicyDiagnostic(
                    "absolute_branch_target",
                    "branch target is an absolute address; use a local label "
                    "inside the replacement block",
                    number, operand.split()[0]))
            continue
        call = _CALL_RE.match(line)
        if call:
            instruction_lines += 1
            continue
        instruction_lines += 1
    if instruction_lines == 0:
        result.diagnostics.append(PolicyDiagnostic("empty_assembly", "assembly contains no instructions"))
    return result
