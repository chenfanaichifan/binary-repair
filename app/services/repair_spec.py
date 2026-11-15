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
    if parsed.get("schema_version") == 2:
        return validate_spec_v2(parsed, case=case, allowed_calls=allowed_calls,
                                target_scope=target_scope)
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


# ---------------------------------------------------------------------------
# RepairSpec v2: nested vulnerability/context/security/repair/ABI/verification
# ---------------------------------------------------------------------------

V2_FIELDS = frozenset({
    "schema_version", "vulnerability", "program_context",
    "security_invariants", "repair", "abi", "verification", "confidence",
})
V2_STRATEGIES = frozenset({
    "guard_input_length", "bounds_check", "lifetime", "format_string",
    "integer_range_check", "null_check", "reject_oversized_input",
})
V2_ABI = {"x86_64": "sysv_amd64", "i386": "cdecl", "arm64": "aapcs64"}


@dataclass
class RepairSpecV2:
    vulnerability: dict[str, str]
    program_context: dict[str, Any]
    security_invariants: list[str]
    repair: dict[str, str]
    abi: dict[str, str]
    verification: dict[str, list[str]]
    confidence: str = "medium"
    schema_version: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "vulnerability": dict(self.vulnerability),
            "program_context": dict(self.program_context),
            "security_invariants": list(self.security_invariants),
            "repair": dict(self.repair),
            "abi": dict(self.abi),
            "verification": {k: list(v) for k, v in self.verification.items()},
            "confidence": self.confidence,
        }


def _v2_text(value: Any, name: str) -> tuple[str | None, str]:
    if not isinstance(value, str) or not value.strip():
        return None, f"missing_or_empty:{name}"
    if len(value) > MAX_TEXT:
        return None, f"too_long:{name}"
    return value.strip(), ""


def validate_spec_v2(parsed: Mapping[str, Any], *, case: Mapping[str, Any],
                     allowed_calls: Iterable[str] = (),
                     target_scope: Mapping[str, Any] | None = None
                     ) -> tuple[RepairSpecV2 | None, str]:
    extra = sorted(str(k) for k in parsed if k not in V2_FIELDS)
    if extra:
        return None, "unexpected_fields:" + ",".join(extra)
    vulnerability = parsed.get("vulnerability")
    context = parsed.get("program_context")
    repair = parsed.get("repair")
    abi = parsed.get("abi")
    verification = parsed.get("verification")
    if not all(isinstance(x, Mapping) for x in (vulnerability, context, repair, abi, verification)):
        return None, "v2_section_missing"
    if not isinstance(parsed.get("security_invariants"), list) or not parsed["security_invariants"]:
        return None, "missing_security_invariants"
    invariants = parsed["security_invariants"]
    if not all(isinstance(x, str) and x.strip() for x in invariants):
        return None, "invalid_security_invariants"
    vuln_type, error = _v2_text(vulnerability.get("type"), "vulnerability.type")
    if error: return None, error
    root, error = _v2_text(vulnerability.get("root_cause"), "vulnerability.root_cause")
    if error: return None, error
    function, error = _v2_text(context.get("function"), "program_context.function")
    if error: return None, error
    if function != str(case.get("target") or ""):
        return None, "affected_function_mismatch"
    strategy, error = _v2_text(repair.get("strategy"), "repair.strategy")
    if error: return None, error
    if strategy not in V2_STRATEGIES:
        return None, "unsupported_repair_strategy"
    failure, error = _v2_text(repair.get("failure_behavior"), "repair.failure_behavior")
    if error: return None, error
    expected, error = _v2_text(repair.get("expected_behavior"), "repair.expected_behavior")
    if error: return None, error
    arch, error = _v2_text(abi.get("architecture"), "abi.architecture")
    if error: return None, error
    calling, error = _v2_text(abi.get("calling_convention"), "abi.calling_convention")
    if error: return None, error
    if str(case.get("arch") or "") and arch != str(case.get("arch")):
        return None, "abi_arch_mismatch"
    if V2_ABI.get(arch) and calling != V2_ABI[arch]:
        return None, "abi_calling_convention_mismatch"
    required_calls = context.get("allowed_calls", [])
    if not isinstance(required_calls, list) or not all(isinstance(x, str) for x in required_calls):
        return None, "invalid_allowed_calls"
    allowed = {str(x) for x in allowed_calls}
    if any(x not in allowed for x in required_calls):
        return None, "permitted_call_not_allowed:" + ",".join(sorted(set(required_calls) - allowed))
    addresses = context.get("addresses", [])
    if not isinstance(addresses, list) or not all(isinstance(x, str) for x in addresses):
        return None, "invalid_affected_addresses"
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
    if "capacity" in context:
        cap = context.get("capacity")
        if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
            return None, "invalid_capacity"
        if case.get("capacity") is not None and int(case["capacity"]) != cap:
            return None, "capacity_mismatch"
    security = verification.get("security_conditions", [])
    regression = verification.get("regression_conditions", [])
    if not isinstance(security, list) or not security:
        return None, "missing_security_conditions"
    if not isinstance(regression, list) or not regression:
        return None, "missing_regression_conditions"
    if not all(isinstance(x, str) and x.strip() for x in security + regression):
        return None, "invalid_verification_conditions"
    confidence = parsed.get("confidence", "medium")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        confidence = "high" if confidence >= 0.75 else "medium" if confidence >= 0.4 else "low"
    if confidence not in {"low", "medium", "high"}:
        return None, "invalid_confidence"
    return RepairSpecV2(
        vulnerability={"type": vuln_type, "root_cause": root,
                       **({"cwe": str(vulnerability["cwe"])} if vulnerability.get("cwe") else {})},
        program_context={
            "function": function, "addresses": list(addresses),
            "registers": list(context.get("registers", [])),
            "memory": list(context.get("memory", [])),
            "capacity": context.get("capacity"),
            "allowed_calls": list(required_calls),
        },
        security_invariants=[str(x) for x in invariants],
        repair={"strategy": strategy, "failure_behavior": failure,
                "expected_behavior": expected},
        abi={"architecture": arch, "calling_convention": calling},
        verification={"security_conditions": [str(x) for x in security],
                      "regression_conditions": [str(x) for x in regression],
                      "required_inputs": [str(x) for x in verification.get("required_inputs", [])]},
        confidence=confidence,
    ), ""


def spec_from_plan(plan: Mapping[str, Any]) -> RepairSpec | RepairSpecV2:
    if plan.get("schema_version") == 2:
        return RepairSpecV2(
            vulnerability=dict(plan.get("vulnerability") or {}),
            program_context=dict(plan.get("program_context") or {}),
            security_invariants=list(plan.get("security_invariants") or []),
            repair=dict(plan.get("repair") or {}),
            abi=dict(plan.get("abi") or {}),
            verification={k: list(v) for k, v in (plan.get("verification") or {}).items()},
            confidence=str(plan.get("confidence", "medium")),
        )
    return RepairSpec(**plan)
