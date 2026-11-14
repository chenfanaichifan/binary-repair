"""Structured repair specification for the assembly-repair AI path.

The planner must answer *what* invariant must hold before the assembly generator
answers *how*.  This module is deliberately strict: unknown fields, invented
symbols, out-of-scope addresses and empty verification conditions fail closed.
It does not execute or inject anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
ALLOWED_FIELDS = frozenset({
    "schema_version", "vulnerability_type", "root_cause",
    "affected_function", "affected_addresses", "affected_registers",
    "affected_memory", "original_behavior", "required_invariant",
    "repair_strategy", "failure_behavior", "permitted_calls",
    "expected_behavior", "verification_conditions", "confidence",
})
REQUIRED_STRINGS = (
    "vulnerability_type", "root_cause", "affected_function",
    "original_behavior", "required_invariant", "repair_strategy",
    "failure_behavior", "expected_behavior",
)
MAX_TEXT = 600
MAX_ITEMS = 64


@dataclass
class RepairSpec:
    schema_version: int
    vulnerability_type: str
    root_cause: str
    affected_function: str
    required_invariant: str
    repair_strategy: str
    failure_behavior: str
    expected_behavior: str
    original_behavior: str
    affected_addresses: list[str] = field(default_factory=list)
    affected_registers: list[str] = field(default_factory=list)
    affected_memory: list[str] = field(default_factory=list)
    permitted_calls: list[str] = field(default_factory=list)
    verification_conditions: list[str] = field(default_factory=list)
    confidence: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "vulnerability_type": self.vulnerability_type,
            "root_cause": self.root_cause,
            "affected_function": self.affected_function,
            "affected_addresses": list(self.affected_addresses),
            "affected_registers": list(self.affected_registers),
            "affected_memory": list(self.affected_memory),
            "original_behavior": self.original_behavior,
            "required_invariant": self.required_invariant,
            "repair_strategy": self.repair_strategy,
            "failure_behavior": self.failure_behavior,
            "permitted_calls": list(self.permitted_calls),
            "expected_behavior": self.expected_behavior,
            "verification_conditions": list(self.verification_conditions),
            "confidence": self.confidence,
        }


def validate_spec(parsed: Any, *, case: Mapping[str, Any],
                  allowed_calls: Iterable[str] = (),
                  target_scope: Mapping[str, Any] | None = None) -> tuple[RepairSpec | None, str]:
    """Validate one model plan; return (spec, '') or (None, typed_error)."""
    if not isinstance(parsed, Mapping):
        return None, "plan_not_object"
    extra = sorted(str(key) for key in parsed if key not in ALLOWED_FIELDS)
    if extra:
        return None, "unexpected_fields:" + ",".join(extra)
    if parsed.get("schema_version") != SCHEMA_VERSION:
        return None, "unsupported_schema_version"
    values: dict[str, str] = {}
    for key in REQUIRED_STRINGS:
        value = parsed.get(key)
        if not isinstance(value, str) or not value.strip():
            return None, f"missing_or_empty:{key}"
        if len(value) > MAX_TEXT:
            return None, f"too_long:{key}"
        values[key] = value.strip()
    if values["affected_function"] != str(case.get("target") or ""):
        return None, "affected_function_mismatch"
    raw_permitted = parsed.get("permitted_calls", [])
    if not isinstance(raw_permitted, list):
        return None, "invalid_permitted_calls"
    permitted: list[str] = []
    for item in raw_permitted:
        if isinstance(item, str):
            name = item
        elif isinstance(item, Mapping):
            name = item.get("name")
        else:
            return None, "invalid_permitted_calls"
        if not isinstance(name, str) or not name:
            return None, "invalid_permitted_calls"
        permitted.append(name)
    allowed = {str(x) for x in allowed_calls}
    if any(name not in allowed for name in permitted):
        return None, "permitted_call_not_allowed:" + ",".join(
            sorted(set(permitted) - allowed))
    addresses = parsed.get("affected_addresses", [])
    if not isinstance(addresses, list) or not all(isinstance(x, str) for x in addresses):
        return None, "invalid_affected_addresses"
    if len(addresses) > MAX_ITEMS:
        return None, "too_many_affected_addresses"
    start = end = None
    if isinstance(target_scope, Mapping):
        start, end = target_scope.get("va"), target_scope.get("end")
    for raw in addresses:
        try:
            va = int(raw, 16)
        except (TypeError, ValueError):
            return None, "invalid_affected_address"
        if not (isinstance(start, int) and isinstance(end, int) and start <= va < end):
            return None, "affected_address_out_of_scope"
    for key in ("affected_registers", "affected_memory", "verification_conditions"):
        value = parsed.get(key, [])
        if not isinstance(value, list) or len(value) > MAX_ITEMS:
            return None, f"invalid:{key}"
        if not all(isinstance(x, str) and x.strip() for x in value):
            return None, f"invalid:{key}"
    if not parsed.get("verification_conditions"):
        return None, "missing_verification_conditions"
    confidence = parsed.get("confidence", "medium")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        confidence = "high" if confidence >= 0.75 else "medium" if confidence >= 0.4 else "low"
    if confidence not in {"low", "medium", "high"}:
        return None, "invalid_confidence"
    spec = RepairSpec(
        schema_version=SCHEMA_VERSION,
        **values,
        affected_addresses=[str(x) for x in addresses],
        affected_registers=[str(x) for x in parsed.get("affected_registers", [])],
        affected_memory=[str(x) for x in parsed.get("affected_memory", [])],
        permitted_calls=[str(x) for x in permitted],
        verification_conditions=[str(x) for x in parsed.get("verification_conditions", [])],
        confidence=confidence,
    )
    return spec, ""
