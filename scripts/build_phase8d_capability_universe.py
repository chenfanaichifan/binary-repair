#!/usr/bin/env python3
"""Build the Phase-8D baseline record and capability-universe registry.

The builder is deterministic and offline. It reads the Phase-8C release
identity/gate/CI evidence, the declared 20-dimension/240-cell universe, the
Phase-8C public benchmark, the aggregate-only hidden benchmark evidence and the
read-only M2 analysis prototype. It writes two artifacts:

* ``artifacts/phase8d-baseline-2026-11-17/`` - D00 frozen baseline facts;
* ``artifacts/phase8d-capability-universe-2026-11-17/`` - D01 explicit
  capability units, legal denominators, state machine and unknown-space record.

Design rules: every unit is derived from a declared cell or a committed
evidence record; unknown outside the catalog is ``unmeasurable`` with a null
count; no generalized/promoted capability is asserted; no wall clock, network,
AI, hidden bytes or git mutation is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import capability_dimensions as dimensions  # noqa: E402

BASELINE_DIR = ROOT / "artifacts" / "phase8d-baseline-2026-11-17"
BASELINE_DIR_REL = "artifacts/phase8d-baseline-2026-11-17"
UNIVERSE_DIR = ROOT / "artifacts" / "phase8d-capability-universe-2026-11-17"
UNIVERSE_DIR_REL = "artifacts/phase8d-capability-universe-2026-11-17"
GENERATED_AT = "2026-11-17T00:00:00Z"
BUILDER_VERSION = 1
PHASE8C_RELEASE_SHA = "4a7b2355ffc5225d013a777bc7d588abac58f944"
PHASE8C_TREE_SHA = "4bf501314b6469328d0256031990bfc402ce6677"
PHASE8C_EVIDENCE_TIP = "ec503e4b1df53ad39fa836bd34d93a18564d78f9"
PHASE8C_RELEASE_TAG_OBJECT = "b03a0a461bb8cdacfa722c4cbd37e46b15b1ac9b"
PHASE8C_EVIDENCE_TAG_OBJECT = "08cc3719193d037335518d17bb3b5cb8b179475f"
PHASE8D_BASE_SHA = "f1bb1f41eba1e0be61be09cea56091e8a03a9896"
PHASE8C_GATE = "artifacts/release-gate-2026-11-16-phase8c/gate.json"
PHASE8C_FREEZE = "artifacts/release-gate-2026-11-16-phase8c/freeze.json"
PHASE8C_ADDENDUM = "docs/release-phase8c-final-evidence-2026-11-16.md"
PHASE8C_CLAIMS = "docs/status/claims.json"
PHASE8C_RELEASE_SUMMARY = "artifacts/phase8c-release-2026-11-16/summary.json"
PHASE8C_BASELINE_AUDIT = "artifacts/phase8c-baseline-2026-11-16/phase8c-baseline-audit.json"
MATRIX = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"
UNIVERSE_ARTIFACT = "artifacts/capability-universe-2026-11-16/dimension-registry.json"
PUBLIC_MANIFEST = "benchmark/phase8c/manifest.json"
PUBLIC_RESULTS = "benchmark/phase8c/results.json"
HIDDEN_AGGREGATE = "artifacts/phase8c-hidden-2026-11-16/aggregate.json"
HIDDEN_COMMITMENT = "benchmark/phase8c/hidden-commitment.json"
M2_DOC = "docs/operations/m2-analysis-api.md"
M2_ARTIFACTS = (
    "artifacts/m2-analysis-2026-11-16/crossfn-param.analysis.json",
    "artifacts/m2-analysis-2026-11-16/crossfn-global.analysis.json",
    "artifacts/m2-analysis-2026-11-16/cfg-elf-strcpy-x86_64.json",
)
FINAL_CI_RUN = 43748886046
FINAL_UBUNTU_RUN = 43748886289
GATED_CODE_CI_RUN = 43744573286
GATED_CODE_UBUNTU_RUN = 43744573230
PHASE8B_CANDIDATES = {
    "stack-strcpy-x86_64": "1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4",
    "heap-capacity-x86_64": "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2",
}
STATES = (
    "unknown", "discovered", "analysis_only", "candidate_generated",
    "independently_verified", "generalized", "promoted", "unsupported",
    "not_applicable", "not_run", "unmeasurable",
)
CELL_STATES = {
    "verified": "discovered",
    "supported": "discovered",
    "non_goal": "not_applicable",
    "unavailable": "unmeasurable",
    "unknown": "unknown",
}
DIMENSION_STATES = {
    "covered": "discovered",
    "partial": "discovered",
    "non_goal": "not_applicable",
    "unavailable": "unmeasurable",
    "not_started": "unknown",
}
LEGAL_TRANSITIONS = {
    "unknown": ["discovered", "analysis_only", "unsupported", "not_applicable", "not_run", "unmeasurable"],
    "discovered": ["analysis_only", "candidate_generated", "unsupported", "not_applicable", "not_run", "unmeasurable"],
    "analysis_only": ["candidate_generated", "unsupported", "not_run", "unmeasurable"],
    "candidate_generated": ["independently_verified", "unsupported", "not_run"],
    "independently_verified": ["generalized", "unsupported", "not_run"],
    "generalized": ["promoted", "not_run", "unmeasurable"],
    "promoted": [],
    "unsupported": ["discovered", "not_run", "unmeasurable"],
    "not_applicable": ["discovered", "not_run", "unmeasurable"],
    "not_run": ["discovered", "analysis_only", "unsupported", "not_applicable", "unmeasurable"],
    "unmeasurable": ["discovered", "not_run", "not_applicable"],
}
DIMENSION_DEPENDENCIES = {
    "D01": [],
    "D02": ["D01"],
    "D03": ["D02"],
    "D04": ["D01", "D02"],
    "D05": ["D01", "D02"],
    "D06": ["D05"],
    "D07": ["D05", "D06"],
    "D08": ["D05"],
    "D09": ["D06", "D08"],
    "D10": ["D08"],
    "D11": ["D09", "D10"],
    "D12": ["D01", "D02"],
    "D13": ["D02", "D03"],
    "D14": ["D05", "D06"],
    "D15": ["D13", "D14"],
    "D16": ["D15", "D11"],
    "D17": ["D16", "D03"],
    "D18": ["D09", "D10", "D11"],
    "D19": ["D03", "D04", "D15", "D16"],
    "D20": ["D09", "D11", "D19"],
}
WILDCARD = {"(all)", "(any)", ""}


class BuildError(RuntimeError):
    """A required source or consistency rule failed."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        raise BuildError(f"missing source file: {rel}")
    return _sha(path.read_bytes())


def _load(rel: str) -> Any:
    path = ROOT / rel
    if not path.is_file():
        raise BuildError(f"missing source artifact: {rel}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"unreadable source artifact {rel}: {exc}") from exc


def _source(rel: str) -> dict[str, str]:
    return {"path": rel, "sha256": _sha_file(rel)}


def _evidence(path: str, fragment: str) -> str:
    return f"{path}#{fragment}"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sums(files: Mapping[str, bytes], prefix: str) -> bytes:
    lines = []
    for name, data in sorted(files.items()):
        if name in {"SHA256SUMS", "README.md"}:
            continue
        lines.append(f"{_sha(data)}  {name}\n")
    return "".join(lines).encode("ascii")


def _readme_baseline(payload: Mapping[str, Any]) -> bytes:
    text = (
        "# Phase-8D D00 baseline (2026-11-17)\n\n"
        f"- Phase-8C release SHA: `{payload['phase8c']['release_sha']}`\n"
        f"- Phase-8C tree SHA: `{payload['phase8c']['tree_sha']}`\n"
        f"- evidence tip: `{payload['phase8c']['evidence_tip']}`\n"
        f"- frozen-tree nightly gate: {payload['gate']['passed']}/{payload['gate']['required']} passed\n"
        f"- final hosted CI: {payload['ci']['final_ci_run']} / {payload['ci']['final_ubuntu_run']}\n"
        f"- Phase-8B reproduction: {payload['phase8b']['verified']}/2 independently verified\n"
        "- consolidation base: `" + PHASE8D_BASE_SHA + "`\n\n"
        "The original Phase-8C tag/evidence refs were deleted/renamed by the\n"
        "consolidation; the target commit objects remain reachable and are\n"
        "recorded by SHA. No new capability is claimed by this baseline.\n"
    )
    return text.encode("utf-8")


def _readme_universe(payload: Mapping[str, Any]) -> bytes:
    counts = payload["counts"]["state_unit_counts"]
    text = (
        "# Phase-8D D01 capability universe (2026-11-17)\n\n"
        f"- units: {payload['counts']['unit_count']}\n"
        f"- dimensions: 20; declared cells: 240\n"
        f"- state counts: {json.dumps(counts, sort_keys=True)}\n"
        f"- generalized/promoted units: {payload['counts']['generalized']}/"
        f"{payload['counts']['promoted']} (no promotion evidence)\n"
        "- unknown outside catalog: explicit `unmeasurable`, count null\n\n"
        "States are bound to declared cells or committed evidence. A unit is not\n"
        "promoted automatically; `promoted` is reachable only from `generalized`\n"
        "through the external promotion gate.\n"
    )
    return text.encode("utf-8")


def build_baseline() -> dict[str, Any]:
    gate = _load(PHASE8C_GATE)
    claims = _load(PHASE8C_CLAIMS)
    release = _load(PHASE8C_RELEASE_SUMMARY)
    audit = _load(PHASE8C_BASELINE_AUDIT)
    addendum = (ROOT / PHASE8C_ADDENDUM).read_text(encoding="utf-8")
    for value in (str(FINAL_CI_RUN), str(FINAL_UBUNTU_RUN), PHASE8C_RELEASE_SHA):
        if value not in addendum:
            raise BuildError(f"final evidence addendum does not contain {value}")
    checks = gate.get("checks") or []
    status = gate.get("status_counts") or {}
    if gate.get("ok") is not True or status.get("passed") != 13:
        raise BuildError("Phase-8C gate is not the recorded 13/13 pass")
    if gate.get("frozen_sha") != PHASE8C_RELEASE_SHA:
        raise BuildError("gate frozen SHA does not match Phase-8C release")
    phase8b = audit.get("q3_reproduction") or {}
    samples = phase8b.get("samples") or []
    verified = [s for s in samples if s.get("independently_verified") is True]
    if len(verified) != 2:
        raise BuildError("Phase-8B reproduction is not 2/2 in the baseline audit")
    hid = release.get("hidden_benchmark") or {}
    pub = release.get("public_benchmark") or {}
    return {
        "schema_version": 1,
        "kind": "phase8d_baseline",
        "phase": "8D",
        "generated_at": GENERATED_AT,
        "base_sha": PHASE8D_BASE_SHA,
        "phase8c": {
            "release_sha": PHASE8C_RELEASE_SHA,
            "tree_sha": PHASE8C_TREE_SHA,
            "evidence_tip": PHASE8C_EVIDENCE_TIP,
            "release_tag": {
                "name": "release-2026-11-16-phase8c",
                "target_sha": PHASE8C_RELEASE_SHA,
                "tag_object_sha": PHASE8C_RELEASE_TAG_OBJECT,
                "status": "deleted_or_renamed_by_consolidation",
            },
            "evidence_tag": {
                "name": "release-2026-11-16-phase8c-evidence",
                "target_sha": PHASE8C_EVIDENCE_TIP,
                "tag_object_sha": PHASE8C_EVIDENCE_TAG_OBJECT,
                "status": "deleted_or_renamed_by_consolidation",
            },
            "evidence_branch": {
                "name": "release/2026-11-16-phase8c-evidence",
                "target_sha": PHASE8C_EVIDENCE_TIP,
                "status": "deleted_or_renamed_by_consolidation",
            },
        },
        "ancestry": {
            "phase8c_release_is_ancestor_of_base": True,
            "phase8c_evidence_tip_is_ancestor_of_base": True,
            "note": "Verified by tests with git merge-base; commit objects remain reachable after ref cleanup.",
        },
        "consolidation": {
            "head_sha": PHASE8D_BASE_SHA,
            "contains_phase8c_release": True,
            "contains_phase8c_evidence_tip": True,
            "refs_removed_or_renamed": True,
            "note": "The consolidation preserved commit and annotated-tag objects but not the original Phase-8C refs; tag object SHAs are recoverable with git fsck.",
        },
        "gate": {
            "path": PHASE8C_GATE,
            "sha256": _sha_file(PHASE8C_GATE),
            "mode": "nightly",
            "ok": True,
            "passed": status.get("passed"),
            "failed": status.get("failed"),
            "required": 13,
            "check_ids": [str(item.get("id")) for item in checks],
            "tree_sha": gate.get("tree_sha"),
            "release_sha": gate.get("release_sha"),
        },
        "ci": {
            "final_ci_run": FINAL_CI_RUN,
            "final_ubuntu_run": FINAL_UBUNTU_RUN,
            "final_ci_conclusion": "success",
            "final_ubuntu_conclusion": "success",
            "gated_code_ci_run": GATED_CODE_CI_RUN,
            "gated_code_ubuntu_run": GATED_CODE_UBUNTU_RUN,
            "gated_code_sha": "f1ba37eee5146b5bb5de97046a0f8b4b653538ff",
            "claims_latest_run": (claims.get("latest_verified_ci") or {}).get("run_id"),
            "source": PHASE8C_ADDENDUM,
            "note": "Final-SHA CI is recorded in the evidence addendum; claims cites the earlier gated-code CI.",
        },
        "phase8b": {
            "verified": 2,
            "samples": PHASE8B_CANDIDATES,
            "phase8b_artifact": "artifacts/phase8b-benchmark-2026-11-16/results.json",
            "reproduction_artifact": PHASE8C_BASELINE_AUDIT,
            "note": "2/2 independently verified in the C1 reproduction; candidates match Phase-8B.",
        },
        "phase8c_results": {
            "public_sample_count": pub.get("sample_count"),
            "public_runtime_oracle_samples": pub.get("runtime_oracle_samples"),
            "public_analysis_only_samples": pub.get("analysis_only_samples"),
            "public_verified": pub.get("verified"),
            "public_rejected": pub.get("rejected"),
            "public_false_verified": pub.get("false_verified"),
            "public_deterministic_claim_withdrawn": pub.get("deterministic_claim_withdrawn"),
            "hidden_sample_count": hid.get("sample_count"),
            "hidden_runtime_count": hid.get("runtime_count"),
            "hidden_analysis_only_count": hid.get("analysis_only_count"),
            "hidden_verified": hid.get("verified"),
            "hidden_false_verified": hid.get("false_verified"),
            "hidden_material_committed": hid.get("material_committed"),
            "no_capability_promotion": True,
            "no_hidden_generalization_claim": True,
        },
        "sources": [
            _source(PHASE8C_GATE),
            _source(PHASE8C_FREEZE),
            _source(PHASE8C_ADDENDUM),
            _source(PHASE8C_RELEASE_SUMMARY),
            _source(PHASE8C_BASELINE_AUDIT),
        ],
        "limitations": [
            "The Phase-8C tag/evidence refs were deleted or renamed by consolidation; target commits are recorded by SHA and ancestry is tested, but the original refs are not resolvable.",
            "The Phase-8C public result is 2 independently verified fixture repairs out of 24 eligible repair cases; it is not a general repair capability.",
            "The hidden benchmark has 0 independently verified repairs and aggregate-only evidence.",
            "Final-SHA hosted CI is recorded in the evidence addendum; claims.json cites the earlier gated-code CI run, not the final SHA CI run.",
            "No new vulnerability-repair capability or capability promotion is claimed.",
        ],
    }


def _cell_dimensions(cell: Mapping[str, Any]) -> list[str]:
    ids: set[str] = {"D19"}  # every declared cell carries a proof-scope field
    container = str(cell.get("container") or "")
    arch = str(cell.get("arch") or "")
    bits = str(cell.get("bits") or "")
    endian = str(cell.get("endian") or "")
    sink = str(cell.get("sink_class") or "")
    dest = str(cell.get("destination_kind") or "")
    runtime = str(cell.get("runtime_tier") or "")
    strategy = str(cell.get("strategy") or "")
    evidence = str(cell.get("evidence_profile") or "")
    provider = str(cell.get("provider") or "")
    if container not in WILDCARD:
        ids.add("D01")
    if arch not in WILDCARD:
        ids.add("D02")
    if bits not in WILDCARD or endian not in WILDCARD:
        ids.add("D12")
    if sink not in WILDCARD:
        ids.update(("D05", "D06"))
    if dest not in WILDCARD:
        ids.add("D06")
    if runtime not in WILDCARD:
        ids.add("D13")
    if strategy not in WILDCARD:
        ids.update(("D15", "D16"))
    if evidence not in WILDCARD:
        ids.update(("D16", "D17", "D19"))
    if provider not in WILDCARD:
        ids.add("D20")
    return sorted(ids)


def _public_state(sample: Mapping[str, Any], result: Mapping[str, Any]) -> tuple[str, str]:
    status = str(result.get("status") or "")
    verification = result.get("verification") or {}
    candidate = result.get("candidate") or {}
    if status == "unsupported":
        return "unsupported", "benchmark runner recorded unsupported"
    if status in {"not_run", "blocked"}:
        return status, f"benchmark runner recorded {status}"
    if str(sample.get("expected_scope")) == "analysis_only":
        return "analysis_only", "declared analysis-only sample; no repair expectation"
    if str(verification.get("decision")) == "verified":
        return "independently_verified", "independent verifier decision=verified"
    if candidate.get("produced") is True:
        return "candidate_generated", "candidate produced but independent verifier did not verify it"
    return "analysis_only", "executed with no candidate; analysis-only observation"


def _dimension_unit(item: Mapping[str, Any]) -> dict[str, Any]:
    state = DIMENSION_STATES[str(item["status"])]
    deps = [f"dimension:{dep}" for dep in DIMENSION_DEPENDENCIES[str(item["id"])]]
    refs = [
        _evidence(UNIVERSE_ARTIFACT, f"dimensions[id={item['id']}]"),
        _evidence("app/services/capability_dimensions.py", f"DIMENSIONS[{item['id']}]"),
    ]
    for ref in item.get("evidence_refs") or []:
        path = str((ref or {}).get("path") or "")
        frag = str((ref or {}).get("fragment") or "")
        if path:
            refs.append(_evidence(path, frag or "source"))
    return {
        "id": f"dimension:{item['id']}",
        "unit_kind": "dimension",
        "dimension_ids": [str(item["id"])],
        "state": state,
        "denominator_class": "dimension_summary",
        "represented_cases": 1,
        "dependencies": deps,
        "evidence_refs": refs,
        "reason": f"legacy dimension status={item['status']}; state is a conservative mapping, not a new verification claim",
    }


def _cell_unit(index: int, cell: Mapping[str, Any]) -> dict[str, Any]:
    state = CELL_STATES[str(cell.get("status"))]
    dims = _cell_dimensions(cell)
    return {
        "id": f"cell:{index:03d}",
        "unit_kind": "declared_cell",
        "dimension_ids": dims,
        "state": state,
        "denominator_class": "declared_cells",
        "represented_cases": 1,
        "dependencies": [f"dimension:{item}" for item in dims],
        "evidence_refs": [
            _evidence(MATRIX, f"universe.cells[{index}]"),
            _evidence(UNIVERSE_ARTIFACT, f"dimensions[id={dims[0]}]"),
        ],
        "reason": f"declared cell {cell.get('cell')!r} status={cell.get('status')}; no new capability inferred",
    }


def _public_unit(sample: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    state, reason = _public_state(sample, result)
    dims = ["D01", "D02", "D05"]
    text = str(sample.get("vulnerability_class") or "").upper()
    if any(token in text for token in ("CWE-121", "CWE-122", "CWE-125", "CWE-787", "CWE-416", "CWE-476")):
        dims.append("D06")
    if any(token in text for token in ("CWE-190", "CWE-134")):
        dims.append("D09")
    oracle = sample.get("oracle") or {}
    runtime = bool(set(oracle.get("kinds") or []) & {"external_poc", "native", "emulated"})
    denom = "public_runtime_oracle" if runtime else "public_analysis_only"
    return {
        "id": f"public:{sample['sample_id']}",
        "unit_kind": "public_benchmark_sample",
        "dimension_ids": sorted(set(dims)),
        "state": state,
        "denominator_class": denom,
        "represented_cases": 1,
        "dependencies": [f"dimension:{item}" for item in sorted(set(dims))],
        "evidence_refs": [
            _evidence(PUBLIC_MANIFEST, f"samples[id={sample['sample_id']}]"),
            _evidence(PUBLIC_RESULTS, f"samples[id={sample['sample_id']}]"),
            _evidence("artifacts/phase8c-benchmark-2026-11-16/results.json", f"samples[id={sample['sample_id']}]"),
        ],
        "reason": reason,
    }


def _hidden_units(
    aggregate: Mapping[str, Any], commitment: Mapping[str, Any]
) -> list[dict[str, Any]]:
    summary = aggregate.get("aggregate") or {}
    runtime = int(commitment.get("runtime_count") or 0)
    analysis = int(commitment.get("analysis_only_count") or 0)
    units = []
    if runtime:
        units.append({
            "id": "hidden:runtime-aggregate",
            "unit_kind": "hidden_benchmark_aggregate",
            "dimension_ids": ["D01", "D02", "D05", "D06", "D16", "D19"],
            "state": "analysis_only",
            "denominator_class": "hidden_runtime_oracle",
            "represented_cases": runtime,
            "dependencies": [f"dimension:{item}" for item in ("D01", "D02", "D05", "D06", "D16", "D19")],
            "evidence_refs": [
                _evidence(HIDDEN_AGGREGATE, "aggregate"),
                _evidence(HIDDEN_COMMITMENT, "commitment_sha256"),
            ],
            "reason": f"hidden aggregate: {summary.get('verified_count', 0)} verified among {runtime} runtime cases; opaque aggregate only",
        })
    if analysis:
        units.append({
            "id": "hidden:analysis-only-aggregate",
            "unit_kind": "hidden_benchmark_aggregate",
            "dimension_ids": ["D01", "D02", "D05", "D06", "D19"],
            "state": "analysis_only",
            "denominator_class": "hidden_analysis_only",
            "represented_cases": analysis,
            "dependencies": [f"dimension:{item}" for item in ("D01", "D02", "D05", "D06", "D19")],
            "evidence_refs": [
                _evidence(HIDDEN_AGGREGATE, "analysis_only"),
                _evidence(HIDDEN_COMMITMENT, "counts"),
            ],
            "reason": "hidden analysis-only aggregate; no sample identity or hidden content published",
        })
    return units


def _m2_units() -> list[dict[str, Any]]:
    specs = (
        ("analysis:m2-cfg", ("D10", "D11"), M2_ARTIFACTS[2], "cfg-callgraph"),
        ("analysis:m2-crossfn-param", ("D09", "D11"), M2_ARTIFACTS[0], "cross-function parameter dataflow"),
        ("analysis:m2-crossfn-global", ("D09", "D11"), M2_ARTIFACTS[1], "cross-function global capacity dataflow"),
    )
    return [
        {
            "id": uid,
            "unit_kind": "analysis_prototype",
            "dimension_ids": list(dims),
            "state": "analysis_only",
            "denominator_class": "analysis_prototypes",
            "represented_cases": 1,
            "dependencies": [f"dimension:{item}" for item in dims],
            "evidence_refs": [
                _evidence(M2_DOC, "read-only prototype; not gate-validated"),
                _evidence(artifact, "produced evidence"),
            ],
            "reason": f"{label} prototype is read-only and not gate-validated; no candidate or independent verification",
        }
        for uid, dims, artifact, label in specs
    ]


def _state_counts(units: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {state: 0 for state in STATES}
    for unit in units:
        state = str(unit.get("state"))
        if state not in counts:
            raise BuildError(f"unit {unit.get('id')} has invalid state {state!r}")
        counts[state] += 1
    return counts


def _denominator(units: Iterable[Mapping[str, Any]], denominator: int) -> dict[str, Any]:
    unit_list = list(units)
    unit_counts = _state_counts(unit_list)
    case_counts = {state: 0 for state in STATES}
    for unit in unit_list:
        case_counts[str(unit["state"])] += int(unit["represented_cases"])
    rates = {
        state: (case_counts[state] / denominator if denominator else None)
        for state in STATES
    }
    represented = sum(int(unit["represented_cases"]) for unit in unit_list)
    if represented != denominator:
        raise BuildError(
            f"denominator {denominator} represented_cases={represented} for units={len(unit_list)}"
        )
    return {
        "denominator": denominator,
        "unit_count": len(unit_list),
        "represented_cases": represented,
        "state_unit_counts": unit_counts,
        "state_case_counts": case_counts,
        "rates": rates,
        "note": "Rates are evidence counts divided by the declared legal denominator; a null rate is used only for a zero denominator. They are not promotion claims.",
    }


def build_universe(baseline: Mapping[str, Any]) -> dict[str, Any]:
    matrix = _load(MATRIX)
    universe = matrix.get("universe") or {}
    cells = universe.get("cells") or []
    if len(cells) != 240:
        raise BuildError(f"declared universe has {len(cells)} cells (expected 240)")
    if len(dimensions.DIMENSIONS) != 20:
        raise BuildError("capability_dimensions does not expose 20 dimensions")
    universe_artifact = _load(UNIVERSE_ARTIFACT)
    public_manifest = _load(PUBLIC_MANIFEST)
    public_results = _load(PUBLIC_RESULTS)
    hidden_aggregate = _load(HIDDEN_AGGREGATE)
    hidden_commitment = _load(HIDDEN_COMMITMENT)
    results_index = {str(item["sample_id"]): item for item in public_results.get("samples") or []}
    dimension_units = [_dimension_unit(item) for item in dimensions.DIMENSIONS]
    cell_units = [_cell_unit(index, cell) for index, cell in enumerate(cells)]
    public_units = [
        _public_unit(sample, results_index[str(sample["sample_id"])])
        for sample in public_manifest.get("samples") or []
    ]
    hidden_units = _hidden_units(hidden_aggregate, hidden_commitment)
    m2_units = _m2_units()
    units = dimension_units + cell_units + public_units + hidden_units + m2_units
    counts = _state_counts(units)
    if counts["generalized"] != 0 or counts["promoted"] != 0:
        raise BuildError("unexpected generalized/promoted evidence in baseline")
    if hidden_commitment.get("sample_count") != 8:
        raise BuildError("hidden commitment is not the recorded 8-sample commitment")
    by_class: dict[str, list[Mapping[str, Any]]] = {}
    for unit in units:
        by_class.setdefault(str(unit["denominator_class"]), []).append(unit)
    dimensions_by_class = {
        "declared_cells": 240,
        "dimension_summary": 20,
        "public_runtime_oracle": 24,
        "public_analysis_only": 8,
        "hidden_runtime_oracle": 6,
        "hidden_analysis_only": 2,
        "analysis_prototypes": 3,
    }
    denominators = {
        name: _denominator(by_class.get(name, []), denominator)
        for name, denominator in dimensions_by_class.items()
    }
    declared = denominators["declared_cells"]
    pub = denominators["public_runtime_oracle"]
    hidden = denominators["hidden_runtime_oracle"]
    analysis = denominators["public_analysis_only"]
    hidden_analysis = denominators["hidden_analysis_only"]
    baseline_sha = _sha(_canonical(baseline))
    source_paths = [
        (MATRIX, UNIVERSE_ARTIFACT, PHASE8C_CLAIMS, PUBLIC_MANIFEST,
         PUBLIC_RESULTS, HIDDEN_AGGREGATE, HIDDEN_COMMITMENT, M2_DOC,
         *M2_ARTIFACTS),
    ]
    sources = [_source(rel) for rel in source_paths[0]]
    sources.append({"path": f"{BASELINE_DIR_REL}/baseline.json", "sha256": baseline_sha})
    payload = {
        "schema_version": 1,
        "kind": "phase8d_capability_universe",
        "phase": "8D",
        "generated_at": GENERATED_AT,
        "baseline": {
            "artifact": f"{BASELINE_DIR_REL}/baseline.json",
            "sha256": baseline_sha,
            "phase8c_release_sha": PHASE8C_RELEASE_SHA,
            "phase8c_tree_sha": PHASE8C_TREE_SHA,
        },
        "state_machine": {
            "states": list(STATES),
            "initial_state": "unknown",
            "transitions": LEGAL_TRANSITIONS,
            "promotion_requires": {
                "from_state": "generalized",
                "gate": "external promotion governance; no automatic path",
                "evidence": ["hidden or multi-sample independent verification", "semantic/regression evidence", "acceptance/promotion review"],
            },
            "automatic_promotion_allowed": False,
            "rules": [
                "unknown is not a measured zero",
                "analysis_only may not transition directly to independently_verified",
                "candidate_generated may not transition directly to promoted",
                "independently_verified may not transition directly to promoted; generalized evidence is required first",
                "promoted is only reachable from generalized and only through the external promotion gate",
            ],
        },
        "dimensions": [
            {
                "id": str(item["id"]),
                "title": str(item["title"]),
                "legacy_status": str(item["status"]),
                "state": DIMENSION_STATES[str(item["status"])],
                "dependencies": list(DIMENSION_DEPENDENCIES[str(item["id"])]),
                "evidence_refs": [
                    _evidence(UNIVERSE_ARTIFACT, f"dimensions[id={item['id']}]"),
                    _evidence("app/services/capability_dimensions.py", f"DIMENSIONS[{item['id']}]"),
                ],
                "reason": "conservative dimension-level mapping; not a new verification claim",
            }
            for item in dimensions.DIMENSIONS
        ],
        "units": units,
        "denominators": denominators,
        "coverage": {
            "declared_universe": {
                "denominator": 240,
                "state_counts": declared["state_case_counts"],
                "legacy_status_counts": universe.get("counts"),
                "unknown_within_catalog": declared["state_case_counts"]["unknown"],
                "unknown_is_not_zero_outside_catalog": True,
            },
            "public_runtime_oracle": {
                "denominator": 24,
                "verified": pub["state_case_counts"]["independently_verified"],
                "candidate_generated": pub["state_case_counts"]["candidate_generated"],
                "analysis_only": pub["state_case_counts"]["analysis_only"],
                "unsupported": pub["state_case_counts"]["unsupported"],
                "false_verified": (public_results.get("aggregate") or {}).get("false_verified_count"),
                "verified_rate": pub["rates"]["independently_verified"],
                "candidate_rate": pub["rates"]["candidate_generated"],
            },
            "hidden_runtime_oracle": {
                "denominator": 6,
                "verified": hidden["state_case_counts"]["independently_verified"],
                "analysis_only": hidden["state_case_counts"]["analysis_only"],
                "verified_rate": hidden["rates"]["independently_verified"],
                "aggregate_only": True,
                "material_committed": False,
            },
            "analysis_only": {
                "public_denominator": analysis["denominator"],
                "hidden_denominator": hidden_analysis["denominator"],
                "public_state_counts": analysis["state_case_counts"],
                "hidden_state_counts": hidden_analysis["state_case_counts"],
            },
            "promotion": {
                "generalized_units": counts["generalized"],
                "promoted_units": counts["promoted"],
                "status": "not_observed",
                "reason": "no unit reached generalized evidence or the external promotion gate",
            },
        },
        "unknown_space": {
            "inside_catalog_unknown_units": counts["unknown"],
            "outside_catalog_state": "unmeasurable",
            "outside_catalog_count": None,
            "outside_catalog_measured_fraction": None,
            "reason": "There is no sampling frame for the unenumerated capability space; a null count is intentional and unknown must not be read as zero.",
        },
        "counts": {
            "unit_count": len(units),
            "state_unit_counts": counts,
            "generalized": counts["generalized"],
            "promoted": counts["promoted"],
            "dimension_count": 20,
            "declared_cell_count": 240,
        },
        "provenance": {
            "builder": "scripts/build_phase8d_capability_universe.py",
            "builder_version": BUILDER_VERSION,
            "sources": sources,
            "generated_at_policy": "fixed deterministic constant; no wall clock",
        },
        "limitations": [
            "Units derived from legacy cells are conservative mappings, not new independent verification.",
            "Only two public deterministic fixture repairs are independently verified; this is not a generalized repair capability.",
            "The hidden aggregate has zero independently verified repairs and is aggregate-only; no hidden sample identity is published.",
            "M2 analysis units are read-only prototypes and are not consumed by gates, planner or repair_any.",
            "Unknown outside the catalog is unmeasurable with a null count; it is never counted as zero coverage.",
            "No unit is generalized or promoted; no capability promotion is claimed.",
        ],
    }
    return payload


def build_artifacts() -> dict[str, bytes]:
    baseline = build_baseline()
    registry = build_universe(baseline)
    files: dict[str, bytes] = {
        f"{BASELINE_DIR_REL}/baseline.json": _canonical(baseline),
        f"{BASELINE_DIR_REL}/README.md": _readme_baseline(baseline),
        f"{UNIVERSE_DIR_REL}/registry.json": _canonical(registry),
        f"{UNIVERSE_DIR_REL}/README.md": _readme_universe(registry),
    }
    files[f"{BASELINE_DIR_REL}/SHA256SUMS"] = _sums(
        {name.split("/", 2)[-1]: data for name, data in files.items()
         if name.startswith(BASELINE_DIR_REL + "/")}, BASELINE_DIR_REL
    )
    files[f"{UNIVERSE_DIR_REL}/SHA256SUMS"] = _sums(
        {name.split("/", 2)[-1]: data for name, data in files.items()
         if name.startswith(UNIVERSE_DIR_REL + "/")}, UNIVERSE_DIR_REL
    )
    return files


def _schema_violations(registry: Mapping[str, Any]) -> list[str]:
    schema_path = ROOT / "contracts" / "phase8d-capability-universe.schema.json"
    try:
        import jsonschema  # type: ignore
    except Exception:
        return ["jsonschema unavailable; schema validation not_run"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(registry),
                    key=lambda error: list(error.path))
    return [f"{list(error.path)}: {error.message}" for error in errors]


def write_artifacts() -> list[str]:
    files = build_artifacts()
    registry = json.loads(files[f"{UNIVERSE_DIR_REL}/registry.json"])
    violations = _schema_violations(registry)
    if violations:
        raise BuildError("registry schema violations: " + "; ".join(violations[:5]))
    for relative, data in sorted(files.items()):
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return sorted(files)


def check_artifacts() -> list[str]:
    fresh = build_artifacts()
    registry = json.loads(fresh[f"{UNIVERSE_DIR_REL}/registry.json"])
    problems = _schema_violations(registry)
    for relative, data in sorted(fresh.items()):
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"missing committed artifact {relative}")
        elif path.read_bytes() != data:
            problems.append(f"fresh build differs from committed {relative}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        files = write_artifacts()
        if args.json:
            print(json.dumps({"ok": True, "written": files}, indent=2))
        else:
            print(f"phase8d: wrote {len(files)} files")
        return 0
    problems = check_artifacts()
    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
    else:
        print("phase8d: " + ("check OK" if not problems else f"{len(problems)} problem(s)"))
        for problem in problems:
            print(f"  - {problem}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
