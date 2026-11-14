"""Capability-universe first-level dimensions D01-D20 (Phase-7).

The user's authoritative Phase-7 roadmap defines **20 first-level capability
dimensions** (D01-D20, titles verbatim) for the capability universe.  The
existing universe registry (``artifacts/capability-gap-audit-2026-11-14``) only
models **11 technical dimensions** (:data:`OLD_11_DIMS`) and therefore cannot
express ABI/compiler/analysis/exploitability/... coverage at the first level.

This module is the single source of truth for the 20 dimensions and for the
explicit old-11 -> new-D mapping.  It is a *registry*, not a capability claim:
each dimension carries a status limited to::

    covered | partial | non_goal | unavailable | not_started

with ``owner``, ``review_by`` and ``evidence_refs``.  A status is never
``verified`` here - verification belongs to the evidence/gate layers.

Status rules (documented in the artifact ``assumptions`` block, never silently
inferred):

* ``covered``      - the complete subject of the dimension is represented by a
  mapped old dimension in the 240-cell universe registry.
* ``partial``      - a subset of the dimension is represented and/or evidence
  exists, but a material part of the dimension has no universe mapping.
* ``non_goal``     - the dimension's repair subject is explicitly declared a
  non-goal by ``docs/status/claims.json`` (the concrete non-goal ids are listed
  in ``related_non_goal_ids`` and become ``out_of_universe_candidates``).
* ``unavailable``  - the dimension has an implementation path but it is not
  measurable on this host/platform (reason required).
* ``not_started``  - no universe mapping and no implementation path in this
  tree yet (reason required).

No provider/HTTP/network access is used by this module; it imports only the
standard library.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
KIND = "capability_dimensions"
STATUSES: tuple[str, ...] = (
    "covered",
    "partial",
    "non_goal",
    "unavailable",
    "not_started",
)

#: The 11 dimensions of the existing universe registry. Exact ids are taken from
#: ``scripts/check_universe_methodology.py`` / ``coverage-matrix.json``.
OLD_11_DIMS: tuple[str, ...] = (
    "container",
    "arch",
    "bits",
    "endian",
    "sink_class",
    "strategy",
    "destination_kind",
    "evidence_profile",
    "runtime_tier",
    "provider",
    "proof_scope",
)

#: Old dimension -> new first-level dimension ids (authoritative mapping supplied
#: by the Lead from the user's Phase-7 roadmap).  A tuple means the old dimension
#: contributes direct evidence to each new dimension; an empty tuple means the
#: new dimension has no old-registry mapping at all.
OLD_TO_NEW: dict[str, tuple[str, ...]] = {
    "container": ("D01",),
    "arch": ("D02",),
    "bits": ("D01", "D02", "D12"),
    "endian": ("D01", "D02", "D12"),
    "sink_class": ("D05", "D06"),
    "strategy": ("D15", "D16"),
    "destination_kind": ("D06",),
    "evidence_profile": ("D16", "D17", "D19"),
    "runtime_tier": ("D13",),
    "provider": ("D20",),
    "proof_scope": ("D19",),
}

#: New dimension -> old dimensions that supply its universe evidence.  Derived
#: from :data:`OLD_TO_NEW` and kept in the module so tests can check consistency.
NEW_TO_OLD: dict[str, tuple[str, ...]] = {
    new_id: tuple(old for old, targets in OLD_TO_NEW.items() if new_id in targets)
    for new_id in (f"D{index:02d}" for index in range(1, 21))
}

_REVIEW_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DIMENSION_ID_RE = re.compile(r"^D\d{2}$")


def _evidence(path: str, fragment: str, kind: str) -> dict[str, str]:
    return {"path": path, "fragment": fragment, "kind": kind}


_CLAIMS = "docs/status/claims.json"
_MATRIX = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"
_UNIVERSE_DOC = "docs/acceptance/capability-universe-2026-11-15.md"
_LIMITATIONS = "docs/acceptance/LIMITATIONS.md"
_NON_GOALS = "docs/acceptance/non-goals-2026-11-14.md"
_NON_GOAL_ROADMAP = "docs/acceptance/non-goal-roadmap-2026-11-15.md"
_CONTRACT_DOC = "docs/acceptance/capability-contract-2026-11-14.md"
_GAP_AUDIT_DOC = "docs/acceptance/capability-gap-audit-2026-11-14.md"

#: The 20 first-level dimensions.  ``id``/``title`` are verbatim from the user's
#: Phase-7 list (the Lead relayed it as authoritative); descriptions/evidence are
#: analyst annotations, never capability claims.
DIMENSIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "D01",
        "title": "Binary formats",
        "description": (
            "Static container formats the repair pipeline can parse, analyze, "
            "rewrite and verify (ELF thin; Mach-O thin; PE). Fat/32-bit Mach-O "
            "and non-declared formats are explicit non-goals."
        ),
        "status": "covered",
        "owner": "universe",
        "review_by": "2027-05-14",
        "source_registries": [
            "REPAIR_CELLS.container",
            "REPAIR_CELLS.bits",
            "REPAIR_CELLS.endian",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["container", "bits", "endian"],
            "mapping_strength": "full",
        },
        "related_non_goal_ids": ["NG-non-goal-4"],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.container", "audit"),
            _evidence("app/services/repair_matrix.py", "REPAIR_CELLS", "code"),
            _evidence(_UNIVERSE_DOC, "section 2", "methodology"),
        ],
    },
    {
        "id": "D02",
        "title": "CPU architectures",
        "description": (
            "Machine architectures for which repair/verification is declared and "
            "measured: x86_64, i386, arm64 (little-endian). arm32/riscv/mips/"
            "powerpc and big-endian are explicit non-goals."
        ),
        "status": "covered",
        "owner": "universe",
        "review_by": "2027-05-14",
        "source_registries": [
            "REPAIR_CELLS.arch",
            "REPAIR_CELLS.bits",
            "REPAIR_CELLS.endian",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["arch", "bits", "endian"],
            "mapping_strength": "full",
        },
        "related_non_goal_ids": ["NG-non-goal-3"],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.arch", "audit"),
            _evidence("app/services/repair_matrix.py", "REPAIR_CELLS", "code"),
            _evidence(_NON_GOALS, "NG-non-goal-3", "acceptance"),
        ],
    },
    {
        "id": "D03",
        "title": "ABI and calling conventions",
        "description": (
            "ABI/calling-convention awareness needed to reason about arguments, "
            "return values, stack layout and register usage. The current universe "
            "has no ABI dimension; runtime/PoC code assumes the platform ABI "
            "implicitly but there is no measured ABI registry."
        ),
        "status": "not_started",
        "owner": "analysis",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions", "audit"),
            _evidence(_CLAIMS, "implicit ABI assumptions", "claims"),
            _evidence(_LIMITATIONS, "ABI/analysis limits", "acceptance"),
        ],
    },
    {
        "id": "D04",
        "title": "Compiler ecosystems",
        "description": (
            "Compiler/toolchain provenance (GCC/Clang/Rust/MSVC/...), optimization "
            "levels and instrumented code patterns that affect analysis and "
            "rewriting. No compiler-ecosystem registry or corpus exists here."
        ),
        "status": "not_started",
        "owner": "analysis",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(_MATRIX, "environment", "audit"),
            _evidence(_CLAIMS, "explicitly_unimplemented", "claims"),
        ],
    },
    {
        "id": "D05",
        "title": "Vulnerability classes",
        "description": (
            "Vulnerability classes the deterministic/repair pipeline models: "
            "unbounded copy, memcpy/syscall length, checked copy and capacity-"
            "check mismatch. Hard-case non-template classes stay AI/research "
            "evidence (EG-cases-target-not-analyzed)."
        ),
        "status": "covered",
        "owner": "engine",
        "review_by": "2027-05-14",
        "source_registries": [
            "REPAIR_CELLS.sink_classes",
            "SINK_CLASSES",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["sink_class"],
            "mapping_strength": "full",
        },
        "related_non_goal_ids": ["EG-cases-target-not-analyzed"],
        "evidence_refs": [
            _evidence("app/services/repair_matrix.py", "SINK_CLASSES", "code"),
            _evidence(_MATRIX, "universe.dimensions.sink_class", "audit"),
            _evidence(_GAP_AUDIT_DOC, "engine/sink-class rows", "acceptance"),
        ],
    },
    {
        "id": "D06",
        "title": "Memory safety",
        "description": (
            "Memory-safety analysis and repair: stack/heap/global destinations "
            "and copy-safety classes are mapped via sink_class + destination_kind. "
            "Unrecoverable destination capacity, UAF/lifetime and global "
            "destinations are explicit non-goals (NG-non-goal-1/2)."
        ),
        "status": "partial",
        "owner": "engine",
        "review_by": "2027-05-14",
        "source_registries": [
            "UNIVERSE_DESTINATION_KINDS",
            "REPAIR_CELLS.sink_classes",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["sink_class", "destination_kind"],
            "mapping_strength": "partial",
        },
        "related_non_goal_ids": ["NG-non-goal-1", "NG-non-goal-2"],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.destination_kind", "audit"),
            _evidence(_CLAIMS, "non_goals", "claims"),
            _evidence(_NON_GOALS, "destination capacity/UAF", "acceptance"),
        ],
    },
    {
        "id": "D07",
        "title": "Arithmetic safety",
        "description": (
            "Integer overflow/truncation/signedness and arithmetic-driven buffer "
            "defects. No arithmetic-safety universe dimension exists and the "
            "deterministic integer repair templates are an explicit non-goal "
            "(NG-non-goal-2)."
        ),
        "status": "non_goal",
        "owner": "engine",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": ["NG-non-goal-2"],
        "evidence_refs": [
            _evidence(_CLAIMS, "non_goals[NG-non-goal-2]", "claims"),
            _evidence(_NON_GOAL_ROADMAP, "integer/loop non-goals", "acceptance"),
            _evidence(_MATRIX, "universe.dimensions", "audit"),
        ],
    },
    {
        "id": "D08",
        "title": "Control-flow safety",
        "description": (
            "Loop bounds, branch/guard integrity and control-flow-hijack defects. "
            "No control-flow-safety universe dimension exists; deterministic "
            "array/loop templates are an explicit non-goal (NG-non-goal-2), while "
            "guard injection covers only the declared reviewed pattern."
        ),
        "status": "non_goal",
        "owner": "engine",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": ["NG-non-goal-2"],
        "evidence_refs": [
            _evidence(_CLAIMS, "non_goals[NG-non-goal-2]", "claims"),
            _evidence("app/services/repair_matrix.py", "STRATEGY_PROFILES", "code"),
            _evidence(_NON_GOAL_ROADMAP, "loop non-goal", "acceptance"),
        ],
    },
    {
        "id": "D09",
        "title": "Data-flow analysis",
        "description": (
            "Use/def, taint, length/capacity propagation and value-set reasoning. "
            "No first-class data-flow universe dimension; the deterministic "
            "analyzer models only the declared copy/length patterns."
        ),
        "status": "not_started",
        "owner": "analysis",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions", "audit"),
            _evidence("app/services/repair_matrix.py", "analyzer patterns", "code"),
            _evidence(_LIMITATIONS, "data-flow limits", "acceptance"),
        ],
    },
    {
        "id": "D10",
        "title": "Control-flow analysis",
        "description": (
            "CFG recovery, reachability, dominance and indirect-target "
            "resolution. The pipeline patches declared instruction sites; there "
            "is no first-class CFG/control-flow-insight universe dimension."
        ),
        "status": "not_started",
        "owner": "analysis",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions", "audit"),
            _evidence(_LIMITATIONS, "CFG limits", "acceptance"),
        ],
    },
    {
        "id": "D11",
        "title": "Interprocedural analysis",
        "description": (
            "Cross-function analysis, call graphs, cross-function capacity/"
            "lifetime reasoning. Analysis is function-scoped today; no "
            "interprocedural universe dimension exists (cross-function "
            "allocations stay non-goals)."
        ),
        "status": "not_started",
        "owner": "analysis",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": ["NG-non-goal-1"],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions", "audit"),
            _evidence(_CLAIMS, "non_goals[NG-non-goal-1]", "claims"),
            _evidence(_LIMITATIONS, "interprocedural limits", "acceptance"),
        ],
    },
    {
        "id": "D12",
        "title": "Binary structure",
        "description": (
            "Sections/segments, symbol/DWARF metadata, relocations, imports/"
            "exports, PIE/ASLR and instruction decoding. Only bits/endian provide "
            "partial universe evidence; there is no structural-metadata registry."
        ),
        "status": "partial",
        "owner": "universe",
        "review_by": "2027-05-14",
        "source_registries": ["REPAIR_CELLS.bits", "REPAIR_CELLS.endian"],
        "old_11dim_mapping": {
            "old_dimensions": ["bits", "endian"],
            "mapping_strength": "partial",
        },
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.bits", "audit"),
            _evidence(_UNIVERSE_DOC, "section 2", "methodology"),
        ],
    },
    {
        "id": "D13",
        "title": "Runtime environments",
        "description": (
            "Execution/evidence environments: native, qemu/Lima emulated, "
            "instruction-level Unicorn emulation, function-level native paths. "
            "The runtime_tier dimension maps fully; PE external PoC and native "
            "x86_64-on-arm64 are platform/non-goal limits."
        ),
        "status": "covered",
        "owner": "runtime",
        "review_by": "2027-05-14",
        "source_registries": ["REPAIR_CELLS.runtime_tiers", "runtime capabilities"],
        "old_11dim_mapping": {
            "old_dimensions": ["runtime_tier"],
            "mapping_strength": "full",
        },
        "related_non_goal_ids": [
            "NG-non-goal-5",
            "RG-external-poc::<doc>::pe/x86_64",
            "RG-external-poc::<doc>::pe/i386",
            "RG-external-poc::<doc>::pe/arm64",
            "RG-external-poc::<doc>::macho/x86_64",
        ],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.runtime_tier", "audit"),
            _evidence("app/services/runtime/capabilities.py", "probe/contract", "code"),
            _evidence(_CONTRACT_DOC, "runtime tiers", "acceptance"),
        ],
    },
    {
        "id": "D14",
        "title": "Exploitability assessment",
        "description": (
            "Whether a finding is practically exploitable (reachability, input "
            "control, mitigations, primitives). The pipeline repairs testcases/"
            "PoCs; it does not assess exploitability and has no universe mapping."
        ),
        "status": "not_started",
        "owner": "analysis",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.proof_scope", "audit"),
            _evidence(_CLAIMS, "scope", "claims"),
        ],
    },
    {
        "id": "D15",
        "title": "Repair strategies",
        "description": (
            "Deterministic repair strategies: strict-template, immediate, guard "
            "and capacity rewrite. The strategy dimension maps fully for the "
            "declared matrix strategies; non-template targets remain "
            "analysis_only (EG-cases-target-not-analyzed)."
        ),
        "status": "covered",
        "owner": "engine",
        "review_by": "2027-02-14",
        "source_registries": [
            "REPAIR_CELLS.strategies",
            "STRATEGY_PROFILES",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["strategy"],
            "mapping_strength": "full",
        },
        "related_non_goal_ids": ["EG-cases-target-not-analyzed"],
        "evidence_refs": [
            _evidence("app/services/repair_matrix.py", "STRATEGY_PROFILES", "code"),
            _evidence(_MATRIX, "universe.dimensions.strategy", "audit"),
            _evidence(_GAP_AUDIT_DOC, "strategy rows", "acceptance"),
        ],
    },
    {
        "id": "D16",
        "title": "Patch generation",
        "description": (
            "Generation of candidate patches/repairs: deterministic strategy "
            "writers and the AI assembly/binary leaf-only paths. Partially "
            "mapped via strategy + evidence_profile; AI generation is "
            "structurally validated but never owns acceptance."
        ),
        "status": "partial",
        "owner": "ai-path",
        "review_by": "2027-05-14",
        "source_registries": [
            "STRATEGY_PROFILES",
            "REPAIR_CELLS.evidence_profiles",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["strategy", "evidence_profile"],
            "mapping_strength": "partial",
        },
        "related_non_goal_ids": [
            "NG-ai-leaf-only::ai_assembly_repair",
            "NG-ai-leaf-only::ai_binary_repair",
        ],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.evidence_profile", "audit"),
            _evidence(_CLAIMS, "non_goals[NG-ai-leaf-only]", "claims"),
            _evidence(_LIMITATIONS, "AI path limits", "acceptance"),
        ],
    },
    {
        "id": "D17",
        "title": "Patch application",
        "description": (
            "In-place/section-aware application of generated patches with "
            "original-byte re-derivation and rollback semantics. Partially "
            "mapped via evidence_profile; native Mach-O application is "
            "supported, PE/32-bit application is not."
        ),
        "status": "partial",
        "owner": "pipeline",
        "review_by": "2027-05-14",
        "source_registries": ["REPAIR_CELLS.evidence_profiles", "rewrite actions"],
        "old_11dim_mapping": {
            "old_dimensions": ["evidence_profile"],
            "mapping_strength": "partial",
        },
        "related_non_goal_ids": ["NG-non-goal-4"],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.evidence_profile", "audit"),
            _evidence("app/services/repair_matrix.py", "rewrite", "code"),
            _evidence(_CLAIMS, "non_goals[NG-non-goal-4]", "claims"),
        ],
    },
    {
        "id": "D18",
        "title": "Semantic preservation",
        "description": (
            "Evidence that a repair preserves intended program semantics (proof/"
            "differential/invariant reasoning beyond PoC+regression behaviour). "
            "No semantic-preservation universe dimension exists; current gates "
            "check observed behaviour only."
        ),
        "status": "not_started",
        "owner": "verification",
        "review_by": "2027-05-14",
        "source_registries": [],
        "old_11dim_mapping": {"old_dimensions": [], "mapping_strength": "none"},
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(_CLAIMS, "scope", "claims"),
            _evidence(_LIMITATIONS, "semantic-preservation limits", "acceptance"),
        ],
    },
    {
        "id": "D19",
        "title": "Verification",
        "description": (
            "Acceptance/verification layers: unified gate evidence profiles, "
            "proof scopes, native/emulated PoC and regression, independence. "
            "Partially mapped via evidence_profile + proof_scope; whole-program/"
            "external-PoC scopes remain non-goals/platform limits."
        ),
        "status": "partial",
        "owner": "verification",
        "review_by": "2027-05-14",
        "source_registries": [
            "REPAIR_CELLS.evidence_profiles",
            "REPAIR_CELLS.proof_scopes",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["evidence_profile", "proof_scope"],
            "mapping_strength": "partial",
        },
        "related_non_goal_ids": [
            "RG-external-poc::<doc>::pe/x86_64",
            "RG-external-poc::<doc>::pe/i386",
            "RG-external-poc::<doc>::pe/arm64",
            "RG-external-poc::<doc>::macho/x86_64",
        ],
        "evidence_refs": [
            _evidence(_MATRIX, "universe.dimensions.proof_scope", "audit"),
            _evidence("app/services/unified_verification.py", "gate checks", "code"),
            _evidence(_CONTRACT_DOC, "verification/evidence", "acceptance"),
        ],
    },
    {
        "id": "D20",
        "title": "AI model intelligence",
        "description": (
            "AI/model capability dimension: provider/model configurations, "
            "strict model identity, measured AI target-mode repair increment and "
            "served-model attribution. Provider identity maps fully via the "
            "provider old dimension; model intelligence itself is only partially "
            "characterized (4 identity-verified models, loop-family only)."
        ),
        "status": "partial",
        "owner": "ai-path",
        "review_by": "2027-05-14",
        "source_registries": [
            "UNIVERSE_PROVIDERS",
            "provider coverage evidence",
        ],
        "old_11dim_mapping": {
            "old_dimensions": ["provider"],
            "mapping_strength": "partial",
        },
        "related_non_goal_ids": [],
        "evidence_refs": [
            _evidence(
                "artifacts/provider-coverage-2026-11-14/summary.json",
                "identity_policy/statistics",
                "acceptance",
            ),
            _evidence(
                "docs/acceptance/ai-capability-layering-2026-11-14.md",
                "AI target layering",
                "acceptance",
            ),
            _evidence(_MATRIX, "universe.dimensions.provider", "audit"),
        ],
    },
)

#: Verbatim titles supplied by the user via the Lead; used by validate() and the
#: artifact builder to guarantee id/title fidelity.
AUTHORITATIVE_TITLES: tuple[str, ...] = (
    "Binary formats",
    "CPU architectures",
    "ABI and calling conventions",
    "Compiler ecosystems",
    "Vulnerability classes",
    "Memory safety",
    "Arithmetic safety",
    "Control-flow safety",
    "Data-flow analysis",
    "Control-flow analysis",
    "Interprocedural analysis",
    "Binary structure",
    "Runtime environments",
    "Exploitability assessment",
    "Repair strategies",
    "Patch generation",
    "Patch application",
    "Semantic preservation",
    "Verification",
    "AI model intelligence",
)


def dimension_ids() -> tuple[str, ...]:
    return tuple(dimension["id"] for dimension in DIMENSIONS)


def get_dimension(dimension_id: str) -> dict[str, Any]:
    for dimension in DIMENSIONS:
        if dimension["id"] == dimension_id:
            return dimension
    raise KeyError(f"unknown capability dimension: {dimension_id}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def registry_payload() -> dict[str, Any]:
    """Deterministic, serializable registry payload (no file I/O)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "dimension_count": len(DIMENSIONS),
        "dimensions": [dict(dimension) for dimension in DIMENSIONS],
        "old_11_dimensions": list(OLD_11_DIMS),
        "old_to_new_mapping": {old: list(targets) for old, targets in OLD_TO_NEW.items()},
        "new_to_old_mapping": {new: list(olds) for new, olds in NEW_TO_OLD.items()},
    }


def registry_digest(registry: Mapping[str, Any] | None = None) -> str:
    """SHA-256 of the canonical registry payload (stable across processes)."""
    payload = registry if registry is not None else registry_payload()
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _iter_refs(dimension: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    return dimension.get("evidence_refs") or []


def validate(registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate dimension registry integrity; returns ``{"ok", "violations"}``."""
    payload = dict(registry) if registry is not None else registry_payload()
    dimensions = payload.get("dimensions")
    violations: list[str] = []
    if not isinstance(dimensions, list) or len(dimensions) != 20:
        violations.append(
            f"dimension_count={len(dimensions) if isinstance(dimensions, list) else 'missing'} (expected 20)"
        )
        dimensions = dimensions if isinstance(dimensions, list) else []
    ids: list[str] = []
    titles: list[str] = []
    seen_old: set[str] = set()
    for dimension in dimensions:
        if not isinstance(dimension, Mapping):
            violations.append("dimension is not an object")
            continue
        dimension_id = str(dimension.get("id") or "")
        title = str(dimension.get("title") or "")
        ids.append(dimension_id)
        titles.append(title)
        if not _DIMENSION_ID_RE.match(dimension_id):
            violations.append(f"invalid dimension id: {dimension_id!r}")
        if not title:
            violations.append(f"{dimension_id}: empty title")
        status = dimension.get("status")
        if status not in STATUSES:
            violations.append(f"{dimension_id}: invalid status {status!r}")
        if not str(dimension.get("description") or "").strip():
            violations.append(f"{dimension_id}: empty description")
        if not str(dimension.get("owner") or "").strip():
            violations.append(f"{dimension_id}: empty owner")
        if not _REVIEW_DATE_RE.match(str(dimension.get("review_by") or "")):
            violations.append(f"{dimension_id}: invalid review_by")
        registries = dimension.get("source_registries")
        if not isinstance(registries, list):
            violations.append(f"{dimension_id}: source_registries must be a list")
        mapping = dimension.get("old_11dim_mapping")
        if not isinstance(mapping, Mapping):
            violations.append(f"{dimension_id}: old_11dim_mapping must be an object")
            mapping = {}
        old_dims = mapping.get("old_dimensions")
        if not isinstance(old_dims, list):
            violations.append(f"{dimension_id}: old_dimensions must be a list")
            old_dims = []
        for old in old_dims:
            if old not in OLD_11_DIMS:
                violations.append(f"{dimension_id}: unknown old dimension {old!r}")
            else:
                seen_old.add(old)
        strength = mapping.get("mapping_strength")
        if strength not in {"none", "partial", "full"}:
            violations.append(f"{dimension_id}: invalid mapping_strength {strength!r}")
        if strength == "none" and old_dims:
            violations.append(f"{dimension_id}: strength none but old_dims present")
        refs = list(_iter_refs(dimension))
        if not refs:
            violations.append(f"{dimension_id}: no evidence_refs")
        for ref in refs:
            if not isinstance(ref, Mapping):
                violations.append(f"{dimension_id}: evidence ref is not an object")
                continue
            for field in ("path", "fragment", "kind"):
                if not str(ref.get(field) or "").strip():
                    violations.append(f"{dimension_id}: evidence ref missing {field}")
        related = dimension.get("related_non_goal_ids")
        if not isinstance(related, list):
            violations.append(f"{dimension_id}: related_non_goal_ids must be a list")
        elif len(related) != len(set(related)):
            violations.append(f"{dimension_id}: duplicate related_non_goal_ids")
    expected_ids = tuple(f"D{index:02d}" for index in range(1, 21))
    if tuple(ids) != expected_ids:
        violations.append(f"dimension ids {ids} (expected D01..D20 in order)")
    if tuple(titles) != AUTHORITATIVE_TITLES:
        violations.append("dimension titles do not match the authoritative D01-D20 list")
    if len(ids) != len(set(ids)):
        violations.append("duplicate dimension ids")
    missing_old = [old for old in OLD_11_DIMS if old not in seen_old]
    if missing_old:
        violations.append(f"old dimensions not mapped by any new dimension: {missing_old}")
    new_to_old = payload.get("new_to_old_mapping")
    if not isinstance(new_to_old, Mapping):
        violations.append("new_to_old_mapping missing")
    else:
        for dimension_id, expected in NEW_TO_OLD.items():
            if tuple(new_to_old.get(dimension_id) or ()) != expected:
                violations.append(
                    f"new_to_old_mapping[{dimension_id}] inconsistent with OLD_TO_NEW"
                )
    old_to_new = payload.get("old_to_new_mapping")
    if not isinstance(old_to_new, Mapping) or set(old_to_new) != set(OLD_11_DIMS):
        violations.append("old_to_new_mapping must cover exactly the 11 old dimensions")
    return {
        "ok": not violations,
        "violations": violations,
        "dimension_count": len(dimensions),
        "registry_digest": registry_digest(payload),
    }
