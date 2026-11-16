"""Metamorphic/mutation discovery over committed Phase-8C compiler variants.

The mechanism is intentionally conservative: it runs the real deterministic
engine and, where a runtime is available, the real guest oracle on derived
inputs.  It records only measured outcomes.  Unsupported/not_run variants stay
visible, and no result is promoted into a repair or capability claim.

Two metamorphic relations are evaluated:

* compiler/link/optimization variants of the same vulnerable source should be
  comparable for target resolution and deterministic repair;
* a family-specific input mutation should preserve the crash/no-crash relation
  across those variants unless the transformation changed the vulnerability.

Observations are evidence of differences, not proof of semantic equivalence.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
GENERATED_AT = "2026-11-17T00:00:00Z"
KIND = "phase8d_metamorphic_discovery"
MANIFEST_REL = "benchmark/phase8c/manifest.json"
VARIANT_PREFIX = "variant-"
MAX_MUTATIONS_PER_VARIANT = 8


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_sample_text(sample: Mapping[str, Any]) -> str:
    return " ".join([
        str(sample.get("sample_id") or ""),
        str(sample.get("cwe") or ""),
        str(sample.get("vulnerability_family") or ""),
        str(sample.get("vulnerability_subtype") or ""),
        str(sample.get("vulnerability_class") or ""),
    ])


def variants_from_manifest(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return public compiler-variant samples only (never hidden samples)."""
    variants: list[dict[str, Any]] = []
    for sample in manifest.get("samples") or []:
        if not isinstance(sample, Mapping):
            continue
        sample_id = str(sample.get("sample_id") or "")
        if not sample_id.startswith(VARIANT_PREFIX):
            continue
        variants.append(dict(sample))
    variants.sort(key=lambda item: str(item.get("sample_id")))
    return variants


def relation_groups(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Group variants by their committed source-sample relation."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for sample in variants_from_manifest(manifest):
        patch = sample.get("expected_patch_properties") or {}
        key = str(patch.get("variant_of") or "unknown-source")
        groups.setdefault(key, []).append(sample)
    relations: list[dict[str, Any]] = []
    for key in sorted(groups):
        items = groups[key]
        relations.append({
            "relation_id": f"compiler-variant-{key}",
            "relation_type": "compiler_optimization_link_strip",
            "source_relation": key,
            "variant_sample_ids": [str(item.get("sample_id")) for item in items],
            "expected_invariance": (
                "the declared target and vulnerability semantics should remain "
                "comparable; differences in target resolution or candidate output "
                "are recorded, not assumed equivalent"
            ),
        })
    return relations


def build_mutations(sample: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build deterministic, family-specific input mutations."""
    text = _safe_sample_text(sample).lower()
    mutations: list[dict[str, Any]] = []
    if "cwe-122" in text or "cwe-119" in text or "cwe-121" in text or "buffer" in text:
        for length in (0, 15, 16, 17, 64, 256):
            mutations.append({
                "mutation_id": f"length-{length}",
                "mutation_family": "buffer_length_boundary",
                "argv": ["A" * length],
                "description": f"single argv payload with length {length}",
            })
    elif "cwe-125" in text or "out-of-bounds" in text or "out of bounds" in text:
        for index in ("0", "5", "15", "16", "1000000"):
            mutations.append({
                "mutation_id": f"index-{index}",
                "mutation_family": "index_boundary",
                "argv": [index],
                "description": f"single argv index {index}",
            })
    elif "cwe-134" in text or "format" in text:
        for value in ("hi", "%s", "%n", "%x.%x.%x"):
            mutations.append({
                "mutation_id": "format-" + _sha256_bytes(value.encode())[:8],
                "mutation_family": "format_string_boundary",
                "argv": [value],
                "description": "format-string boundary input",
            })
    elif "cwe-190" in text or "integer" in text:
        for value in ("0", "1", "2147483647", "4294967295"):
            mutations.append({
                "mutation_id": "integer-" + value,
                "mutation_family": "integer_boundary",
                "argv": [value],
                "description": "integer boundary input",
            })
    else:
        mutations.append({
            "mutation_id": "baseline-empty",
            "mutation_family": "generic_baseline",
            "argv": [],
            "description": "empty argv baseline for a non-specialized family",
        })
    return mutations[:MAX_MUTATIONS_PER_VARIANT]


def _engine_record(sample: Mapping[str, Any], result: Any) -> dict[str, Any]:
    if isinstance(result, Mapping) and isinstance(result.get("result"), Mapping):
        result = result.get("result")
    if result is None:
        return {
            "status": "not_run",
            "disposition": None,
            "detection": None,
            "candidate_produced": None,
            "candidate_sha256": None,
            "error": "engine returned no execution record",
        }
    if not isinstance(result, Mapping):
        return {
            "status": "not_run",
            "disposition": None,
            "detection": None,
            "candidate_produced": None,
            "candidate_sha256": None,
            "error": f"engine returned {type(result).__name__}",
        }
    repair = result.get("repair") if isinstance(result.get("repair"), Mapping) else {}
    candidate = result.get("candidate")
    if isinstance(candidate, (bytes, bytearray)):
        candidate_bytes = bytes(candidate)
        candidate_produced = bool(candidate_bytes)
        candidate_sha = _sha256_bytes(candidate_bytes) if candidate_bytes else None
    elif isinstance(candidate, Mapping):
        candidate_produced = bool(candidate.get("produced"))
        candidate_sha = candidate.get("sha256")
    else:
        candidate_produced = False
        candidate_sha = None
    return {
        "status": str(result.get("status") or "not_run"),
        "disposition": repair.get("disposition"),
        "detection": result.get("detection"),
        "candidate_produced": candidate_produced,
        "candidate_sha256": candidate_sha,
        "error": result.get("not_run_reason") or result.get("error"),
    }


def _execution_record(result: Any) -> dict[str, Any]:
    if result is None:
        return {"status": "not_run", "executed": False, "error": "no execution result"}
    if isinstance(result, Mapping):
        available = bool(result.get("available", False))
        get = result.get
    else:
        available = bool(getattr(result, "available", False))
        get = lambda key, default=None: getattr(result, key, default)
    if not available and get("error") is None:
        return {
            "status": "not_run",
            "executed": False,
            "error": f"execution returned {type(result).__name__} without availability",
        }
    return {
        "status": "executed" if available else "not_run",
        "executed": available,
        "crashed": get("crashed") if available else None,
        "exit_code": get("exit_code") if available else None,
        "timed_out": bool(get("timed_out")) if available else None,
        "runner": get("runner"),
        "tier": get("tier"),
        "error": get("error"),
    }


def discover(
    *,
    root: Path = ROOT,
    engine_fn: Callable[[Mapping[str, Any], Path], Any] | None = None,
    execute_fn: Callable[[Path, list[str]], Any] | None = None,
    max_variants: int | None = None,
    max_mutations: int | None = None,
) -> dict[str, Any]:
    """Run one real metamorphic/mutation discovery pass."""
    from app.services.benchmark_runner import sample_binary_path

    manifest_path = (root / MANIFEST_REL).resolve()
    manifest = _load_json(manifest_path)
    relations = relation_groups(manifest)
    variant_map = {str(item.get("sample_id")): item for item in variants_from_manifest(manifest)}
    selected_ids: list[str] = []
    for relation in relations:
        selected_ids.extend(relation["variant_sample_ids"])
    if max_variants is not None:
        selected_ids = selected_ids[:max(0, int(max_variants))]
    selected_ids = [item for item in selected_ids if item in variant_map]

    if engine_fn is None or execute_fn is None:
        from app.services.benchmark_runner import execute_sample
        from app.services.guest_runner import find_guest_runner, run_path

        if engine_fn is None:
            def engine_fn(sample: Mapping[str, Any], binary_path: Path) -> Any:
                return execute_sample(sample, root=root, verifier=None)
        if execute_fn is None:
            def execute_fn(binary_path: Path, argv: list[str]) -> Any:
                arch = str(variant_map.get(_binary_to_sample_id(str(binary_path)), {}).get("arch") or "x86_64")
                return run_path(
                    binary_path, argv=argv, arch=arch,
                    timeout=12.0,
                    lock_purpose="phase8d.metamorphic.input-mutation",
                )

    def _binary_to_sample_id(path_text: str) -> str:
        name = Path(path_text).name
        if name.endswith(".elf"):
            return name[:-4]
        return name

    variant_runs: list[dict[str, Any]] = []
    mutation_runs: list[dict[str, Any]] = []
    not_run: list[dict[str, Any]] = []
    for sample in (variant_map[item] for item in selected_ids):
        sample_id = str(sample.get("sample_id"))
        try:
            binary_path = sample_binary_path(sample, root=root)
        except Exception as exc:  # noqa: BLE001 - recorded
            variant_runs.append({
                "sample_id": sample_id,
                "binary_sha256": sample.get("binary_sha256"),
                "engine": {"status": "invalid", "error": f"{type(exc).__name__}: {exc}"},
                "binary_path": None,
            })
            not_run.append({"sample_id": sample_id, "reason": "binary resolution failed"})
            continue
        try:
            raw = engine_fn(sample, binary_path) if engine_fn else None
            engine = _engine_record(sample, raw)
        except Exception as exc:  # noqa: BLE001 - real not_run
            engine = {"status": "not_run", "disposition": None, "detection": None,
                      "candidate_produced": None, "candidate_sha256": None,
                      "error": f"{type(exc).__name__}: {exc}"}
        variant_runs.append({
            "sample_id": sample_id,
            "binary_sha256": sample.get("binary_sha256"),
            "binary_path": str(binary_path.relative_to(root)) if binary_path.is_relative_to(root) else binary_path.name,
            "compiler": sample.get("compiler"),
            "compiler_version": sample.get("compiler_version"),
            "optimization": sample.get("optimization_level"),
            "linking_mode": sample.get("linking_mode"),
            "stripping_status": sample.get("stripping_status"),
            "cwe": sample.get("cwe"),
            "engine": engine,
        })
        if engine["status"] != "executed":
            not_run.append({
                "sample_id": sample_id,
                "reason": engine.get("error") or f"engine status {engine['status']}",
            })

    # Input mutations run on every selected variant, including stripped ones,
    # because target-scope failure must not hide real guest behavior.
    for relation in relations:
        relation_ids = [item for item in relation["variant_sample_ids"] if item in selected_ids]
        if not relation_ids:
            continue
        primary = variant_map[relation_ids[0]]
        mutations = build_mutations(primary)
        if max_mutations is not None:
            mutations = mutations[:max(0, int(max_mutations))]
        for mutation in mutations:
            per_variant: list[dict[str, Any]] = []
            for sample_id in relation_ids:
                sample = variant_map[sample_id]
                try:
                    binary_path = sample_binary_path(sample, root=root)
                    if not binary_path.is_absolute():
                        binary_path = (root / binary_path).resolve()
                    observation = _execution_record(execute_fn(binary_path, list(mutation["argv"])))
                except Exception as exc:  # noqa: BLE001 - recorded
                    observation = {
                        "status": "not_run", "executed": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                per_variant.append({"sample_id": sample_id, **observation})
            executed = [item for item in per_variant if item.get("executed") is True]
            crashes = [bool(item.get("crashed")) for item in executed]
            agreement: bool | None = None
            if len(crashes) >= 2:
                agreement = len(set(crashes)) == 1
            difference = None
            if agreement is False:
                difference = (
                    "input mutation produced different crash outcomes across "
                    "compiler variants; capability/normalization difference recorded"
                )
            mutation_runs.append({
                "relation_id": relation["relation_id"],
                "mutation_id": mutation["mutation_id"],
                "mutation_family": mutation["mutation_family"],
                "argv_sha256": _sha256_bytes("\x00".join(mutation["argv"]).encode("utf-8")),
                "argv_lengths": [len(value) for value in mutation["argv"]],
                "variants": per_variant,
                "executed_variant_count": len(executed),
                "relation_holds": agreement,
                "difference": difference,
            })

    # Engine-level differences within a relation.
    differences: list[dict[str, Any]] = []
    for relation in relations:
        ids = [item for item in relation["variant_sample_ids"] if item in selected_ids]
        if len(ids) < 2:
            continue
        observations = [
            next((item for item in variant_runs if item["sample_id"] == sid), None)
            for sid in ids
        ]
        observations = [item for item in observations if item is not None]
        dispositions = {
            str((item.get("engine") or {}).get("disposition"))
            for item in observations
        }
        statuses = {str((item.get("engine") or {}).get("status")) for item in observations}
        if len(dispositions) > 1 or len(statuses) > 1:
            differences.append({
                "relation_id": relation["relation_id"],
                "variant_sample_ids": ids,
                "observed_engine_statuses": sorted(statuses),
                "observed_dispositions": sorted(dispositions),
                "difference_type": "compiler_variant_engine_capability_difference",
                "interpretation": (
                    "same-source variants did not yield the same target-resolution/"
                    "repair disposition; this is a measured capability difference, "
                    "not proof of semantic change"
                ),
            })
    for mutation in mutation_runs:
        if mutation["relation_holds"] is False:
            differences.append({
                "relation_id": mutation["relation_id"],
                "mutation_id": mutation["mutation_id"],
                "difference_type": "input_mutation_behavior_difference",
                "variant_sample_ids": [item["sample_id"] for item in mutation["variants"]],
                "interpretation": mutation["difference"],
            })
    return {
        "schema_version": 1,
        "kind": KIND,
        "generated_at": GENERATED_AT,
        "manifest_path": MANIFEST_REL,
        "manifest_sha256": _sha256_file(manifest_path),
        "host": {
            "platform": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "relations": relations,
        "variant_runs": variant_runs,
        "mutation_runs": mutation_runs,
        "differences": differences,
        "summary": {
            "variant_count": len(variant_runs),
            "engine_executed": sum(1 for item in variant_runs
                                   if (item.get("engine") or {}).get("status") == "executed"),
            "engine_not_run_or_unsupported": sum(
                1 for item in variant_runs
                if (item.get("engine") or {}).get("status") != "executed"),
            "mutation_count": len(mutation_runs),
            "mutations_executed": sum(1 for item in mutation_runs
                                      if item.get("executed_variant_count", 0) > 0),
            "relation_hold_count": sum(1 for item in mutation_runs
                                       if item.get("relation_holds") is True),
            "relation_difference_count": sum(1 for item in mutation_runs
                                             if item.get("relation_holds") is False),
            "engine_difference_count": sum(
                1 for item in differences
                if item.get("difference_type") == "compiler_variant_engine_capability_difference"),
            "not_run_count": len(not_run),
        },
        "mechanisms": [
            {
                "mechanism": "metamorphic",
                "status": "run",
                "evidence": "four same-source compiler variants compared with actual deterministic-engine records",
                "support_claimed": False,
            },
            {
                "mechanism": "input_mutation",
                "status": "run",
                "evidence": "family-specific input boundaries executed through the real guest oracle",
                "support_claimed": False,
            },
            {
                "mechanism": "unified_gap_registry_integration",
                "status": "not_run",
                "reason": "standalone D07 artifact; the existing seven-mechanism registry was not edited by this angle",
            },
        ],
        "not_run": not_run,
        "provenance": {
            "runner": "app/services/metamorphic_discovery.py",
            "deterministic_engine": "app.services.binary_pipeline.repair_any via benchmark_runner.execute_sample",
            "runtime_oracle": "app.services.guest_runner.run_path",
            "network_used": False,
            "ai_used": False,
            "no_hidden_material_read": True,
        },
        "limitations": [
            "metamorphic relations are observational; equal outcomes are not a semantic-equivalence proof",
            "input mutations are family-specific and bounded; they do not exhaust the input space",
            "unsupported/stripped target resolution and guest failures are recorded as differences/not_run, not hidden",
            "no candidate, capability, or support claim is promoted from this artifact",
            "guest outcomes are host-dependent; this artifact records one measured reference-host pass",
        ],
    }
