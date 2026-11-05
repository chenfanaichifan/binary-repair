"""Guest broker — narrow VM task protocol (host-safe part).

The host side of the broker only *plans and validates*. It never executes,
compiles, or symbolically analyses a binary, never builds a shell string, and
never accepts an arbitrary path. The six fixed operations and the typed task
request are the boundary the guest broker enforces.

See ``operations.py`` (the six operations) and ``task_request.py`` (the typed
request wrapper).
"""

from __future__ import annotations

from .operations import (
    AnalyzeOp,
    ApplyOp,
    AssembleOp,
    CompileOp,
    HOST_INVARIANTS,
    Operation,
    OpArtifact,
    ResourceLimits,
    TestOp,
    VerifyOp,
    validate_operation,
)
from .task_request import TaskRequest, build_task_request

__all__ = [
    "AnalyzeOp",
    "ApplyOp",
    "AssembleOp",
    "CompileOp",
    "HOST_INVARIANTS",
    "Operation",
    "OpArtifact",
    "ResourceLimits",
    "TaskRequest",
    "TestOp",
    "VerifyOp",
    "build_task_request",
    "validate_operation",
]
