"""Optional native trace plumbing.

Only observed data is emitted.  The current Linux guest has strace but no gdb;
register/stack modes therefore report not_run rather than synthesizing values.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NativeTrace:
    case_id: str
    mode: str
    available: bool
    status: str
    exit_code: int | None = None
    signal: int | None = None
    stdout: str = ""
    stderr: str = ""
    syscall_errors: list[str] = field(default_factory=list)
    registers: dict[str, str] = field(default_factory=dict)
    stack: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "case_id": self.case_id,
            "mode": self.mode,
            "available": self.available,
            "status": self.status,
            "exit_code": self.exit_code,
            "signal": self.signal,
            "stdout": self.stdout[:400],
            "stderr": self.stderr[:400],
            "syscall_errors": list(self.syscall_errors),
            "registers": dict(self.registers),
            "stack": list(self.stack),
            "limitations": list(self.limitations),
        }


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def from_case_result(case: Any, *, mode: str = "n1") -> NativeTrace:
    """Build N1/N2 trace from a case result; never invent registers/stack."""
    exit_code = getattr(case, "exit_code", None)
    stderr = str(getattr(case, "stderr", "") or "")
    signal = None
    for token in stderr.split():
        if token.isdigit() and "signal" in stderr:
            signal = int(token)
            break
    return NativeTrace(
        case_id=str(getattr(case, "case_id", "")),
        mode=mode,
        available=True,
        status="observed",
        exit_code=exit_code,
        signal=signal,
        stdout=str(getattr(case, "stdout", "") or ""),
        stderr=stderr,
        syscall_errors=list(getattr(case, "syscall_errors", []) or []),
        limitations=["register/stack/memory trace requires gdb; not run"]
        if not tool_available("gdb") else [],
    )


def unavailable(case_id: str, reason: str) -> NativeTrace:
    return NativeTrace(case_id=case_id, mode="n3+", available=False,
                       status="not_run", limitations=[reason])
