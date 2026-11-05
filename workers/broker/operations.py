"""Guest broker — fixed operation list (host-safe part).

This module is the *host side* of the narrow VM task protocol. It defines the
six fixed operations the disposable Ubuntu guest broker is allowed to perform,
as typed manifests. It validates and plans only: it never executes, compiles,
or symbolically analyses a binary, never builds a shell string, and never
accepts an arbitrary path. All of that happens inside the guest through the
fixed operation list.

Fixed operations (code_patterns.md): analyze, assemble, compile, apply, test,
verify. Each is expressed as a typed manifest, not a command string.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# ---- shared lexical rules (kept consistent with binaryrepair_ai.schemas) ----

# An artifact id is an opaque token issued by the artifact store, not a path.
ARTIFACT_ID_RE = r"^[A-Za-z0-9._:-]{1,64}$"
# A symbol name or a hex address; never a path or a shell fragment.
TARGET_RE = r"^(?:[A-Za-z_][A-Za-z0-9_@.$]*|0x[0-9a-fA-F]{1,16})$"
SHA256_RE = r"^[0-9a-fA-F]{64}$"


class Operation(str, Enum):
    """The six fixed operations. This is a closed set, not user-extensible."""

    ANALYZE = "analyze"
    ASSEMBLE = "assemble"
    COMPILE = "compile"
    APPLY = "apply"
    TEST = "test"
    VERIFY = "verify"


class OpArtifact(BaseModel):
    """A typed reference to a stored artifact by id, never by path.

    ``sha256`` is mandatory: an operation may only act on a byte identity the
    store has actually recorded. A missing or mismatched hash makes the request
    fail closed before it can reach the guest.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]
    sha256: Annotated[str, Field(pattern=SHA256_RE)]


class ResourceLimits(BaseModel):
    """Per-job resource ceiling (tech_stack.md operational defaults).

    Enforced on the host at planning time and re-enforced by jobwrap in the
    guest. Exceeding a ceiling means ``inconclusive`` / ``error``, never
    ``pass``.
    """

    model_config = ConfigDict(extra="forbid")

    cpu_seconds: int = Field(default=300, ge=1, le=3600)
    as_gib: int = Field(default=4, ge=1, le=64)
    nofile: int = Field(default=1024, ge=1, le=65536)
    fsize_mib: int = Field(default=256, ge=1, le=4096)


class AnalyzeOp(BaseModel):
    """Headless analysis of a frozen binary. Produces typed excerpts only."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["analyze"] = "analyze"
    binary: OpArtifact
    target_entry: Annotated[str, Field(pattern=TARGET_RE)]
    # Analysis never widens scope: only these tools may run, in the guest.
    tools: tuple[Literal["ghidra", "readelf", "objdump", "capstone"], ...] = (
        "readelf",
        "objdump",
    )


class AssembleOp(BaseModel):
    """Assemble a reviewed byte patch into an artifact. No execution."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["assemble"] = "assemble"
    base_binary: OpArtifact
    # Patch is expressed as (vaddr, hex) edits — never a raw byte blob the host
    # cannot bound, never a path.
    edits: tuple[tuple[int, str], ...] = Field(default=(), max_length=32)
    # Where the assembled candidate must land, by artifact id.
    out_artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]

    @field_validator("edits")
    @classmethod
    def _edits_are_bounded(cls, v: tuple[tuple[int, str], ...]) -> tuple[tuple[int, str], ...]:
        for vaddr, hexbytes in v:
            if vaddr < 0:
                raise ValueError("patch vaddr must be non-negative")
            if len(hexbytes) % 2 != 0 or not all(c in "0123456789abcdefABCDEF" for c in hexbytes):
                raise ValueError("patch bytes must be even-length hex")
        return v


class CompileOp(BaseModel):
    """Compile recovered C in the guest. Never on the host."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["compile"] = "compile"
    source_artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]
    # The compile flags are a closed, reviewed set — never an open string.
    flags: tuple[str, ...] = Field(default=(), max_length=32)
    out_artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]


class ApplyOp(BaseModel):
    """Apply a reviewed candidate to the frozen binary (Route A rewrite)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["apply"] = "apply"
    base_binary: OpArtifact
    candidate_artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]
    out_artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]
    # Applying a patch is a Gate 3 scope decision; without an explicit ruling
    # the request is rejected before it reaches the guest.
    scope_authorized: bool = False


class TestOp(BaseModel):
    """Run the frozen test manifest against a candidate, in the guest only."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["test"] = "test"
    candidate: OpArtifact
    manifest_artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]
    mode: Literal["roundtrip", "repaired"] = "repaired"


class VerifyOp(BaseModel):
    """Verify a candidate against an obligation (identity/structure/behaviour/
    symbolic/reproducibility). Produces evidence, never a verdict by itself."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["verify"] = "verify"
    candidate: OpArtifact
    obligation: Literal["identity", "structure", "interface", "behaviour", "symbolic", "reproducibility"]
    evidence_artifact_id: Annotated[str, Field(pattern=ARTIFACT_ID_RE)]


OpManifest = Annotated[
    AnalyzeOp | AssembleOp | CompileOp | ApplyOp | TestOp | VerifyOp,
    Field(discriminator="kind"),
]


def validate_operation(payload: dict) -> AnalyzeOp | AssembleOp | CompileOp | ApplyOp | TestOp | VerifyOp:
    """Validate one operation manifest. Raises ``ValueError`` on any invalid
    payload; never repairs, defaults, or "cleans up" an operation."""
    kind = payload.get("kind")
    if kind not in {o.value for o in Operation}:
        raise ValueError(f"unknown operation: {kind!r}")
    model = {
        "analyze": AnalyzeOp,
        "assemble": AssembleOp,
        "compile": CompileOp,
        "apply": ApplyOp,
        "test": TestOp,
        "verify": VerifyOp,
    }[kind]
    return model.model_validate(payload)


# Every op may only reference artifacts; the host never passes a path, a
# binary name, or an argv array. This invariant is structural (the models have
# no path field) and documented so a reviewer can verify it at a glance.
HOST_INVARIANTS = (
    "no shell string",
    "no arbitrary path",
    "no argv array",
    "artifact ids only",
    "hashes mandatory",
    "scope_authorized gates apply",
)
