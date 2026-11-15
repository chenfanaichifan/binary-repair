"""Plan-to-assembly-to-native evidence links for one repair attempt."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def build_evidence_links(plan: Mapping[str, Any] | None, *,
                         assembly: str | None,
                         candidate: Mapping[str, Any] | None,
                         native_feedback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    plan = dict(plan or {})
    refs = list(plan.get("evidence_refs") or [])
    links: list[dict[str, Any]] = []
    if plan.get("schema_version") == 2:
        claims = (list(plan.get("security_invariants") or [])
                  + list((plan.get("verification") or {}).get("security_conditions") or []))
        for claim in claims:
            links.append({
                "claim": str(claim),
                "evidence": refs,
                "source": "provided" if refs else "model_inferred",
            })
    candidate = dict(candidate or {})
    native = dict(native_feedback or {})
    return {
        "schema_version": 1,
        "spec_version": int(plan.get("schema_version") or 1),
        "plan_sha256": _sha(plan),
        "assembly_sha256": (
            hashlib.sha256(assembly.encode()).hexdigest()
            if assembly is not None else None),
        "candidate_sha256": candidate.get("candidate_sha256"),
        "gate": candidate.get("gate"),
        "links": links,
        "native_feedback_class": native.get("failure_class"),
    }
