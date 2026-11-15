"""Structured diagnostics for policy and assembler failures."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_ASSEMBLER_LINE_RE = re.compile(
    r"(?P<path>[^:\n]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<kind>error|warning|fatal error):\s*(?P<message>.+)")


@dataclass
class AssemblyDiagnostic:
    error_class: str
    message: str
    line: int | None = None
    column: int | None = None
    token: str | None = None
    raw_stderr: str = ""
    retryable: bool = True

    def to_dict(self) -> dict:
        return {
            "error_class": self.error_class,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "token": self.token,
            "raw_stderr": self.raw_stderr[-1200:],
            "retryable": self.retryable,
        }


@dataclass
class AssemblyPreflightError(ValueError):
    error_class: str = "assembly_validation"
    token: str | None = None
    diagnostics: list[AssemblyDiagnostic] = field(default_factory=list)

    def __str__(self) -> str:
        return self.args[0] if self.args else self.error_class


def parse_assembler_stderr(stderr: str) -> list[AssemblyDiagnostic]:
    out: list[AssemblyDiagnostic] = []
    for line in (stderr or "").splitlines():
        match = _ASSEMBLER_LINE_RE.search(line)
        if not match:
            continue
        message = match.group("message").strip()
        lowered = message.lower()
        if "no such instruction" in lowered or "invalid instruction" in lowered:
            cls = "invalid_instruction"
        elif "invalid operand" in lowered or "unexpected token" in lowered:
            cls = "invalid_operand"
        else:
            cls = "assembler_syntax"
        token = None
        for candidate in (message.split(":", 1)[0].split(), message.split()):
            if candidate:
                token = candidate[-1].strip("'\"")
                break
        out.append(AssemblyDiagnostic(
            error_class=cls, message=message,
            line=int(match.group("line")), column=int(match.group("col")),
            token=token, raw_stderr=line,
        ))
    if not out and (stderr or "").strip():
        tail = (stderr or "").strip().splitlines()[-1]
        out.append(AssemblyDiagnostic(
            error_class="assembler_syntax", message=tail[:500], raw_stderr=tail,
        ))
    return out


def policy_error(diagnostics: list[dict]) -> AssemblyPreflightError:
    first = diagnostics[0] if diagnostics else {}
    raw_cls = str(first.get("error_class") or "assembly_validation")
    cls = {"forbidden_token": "assembly_forbidden"}.get(raw_cls, "assembly_validation")
    message = f"assembly policy violation: {raw_cls}: {first.get('message', '')}"
    err = AssemblyPreflightError(message)
    err.error_class = cls
    err.token = first.get("token")
    err.diagnostics = [
        AssemblyDiagnostic(
            error_class=str(item.get("error_class") or "assembly_validation"),
            message=str(item.get("message") or ""),
            line=item.get("line"), token=item.get("token"),
        )
        for item in diagnostics
    ]
    return err
