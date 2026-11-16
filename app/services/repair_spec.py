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
    "repair_strategy", "failure_behavior", "failure_behavior_contract",
    "permitted_calls", "expected_behavior", "verification_conditions",
    "confidence",
})
REQUIRED_STRINGS = (
    "vulnerability_type", "root_cause", "affected_function",
    "original_behavior", "required_invariant", "repair_strategy",
    "failure_behavior", "expected_behavior",
)
MAX_TEXT = 600
MAX_ITEMS = 64

#: Structured failure contract (v2 ``repair.failure_behavior`` / v1 optional
#: ``failure_behavior_contract``).  The deterministic native gate remains the
#: only acceptance authority; this structure only lets the repair plan *state*
#: the expected observable failure so the assembly stage can aim at it.
FAILURE_BEHAVIOR_FIELDS = frozenset({
    "exit_code", "stdout", "stderr", "stdout_hex",
})
MAX_FAILURE_EXIT_CODE = 255


@dataclass(frozen=True)
class FailureBehavior:
    """Typed expected observable behavior of the repaired program on failure.

    ``exit_code`` is the process exit status (0..255).  ``stdout``/``stderr``
    are exact text values; ``stdout_hex`` is the exact stdout byte sequence in
    hex.  ``stdout`` and ``stdout_hex`` are mutually exclusive.  At least one
    field must be non-null, otherwise the structure is empty and rejected.
    """

    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    stdout_hex: str | None = None

    @property
    def requested(self) -> bool:
        return any(value is not None for value in (
            self.exit_code, self.stdout, self.stderr, self.stdout_hex))

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_hex": self.stdout_hex,
        }


def parse_failure_behavior(value: Any) -> tuple[FailureBehavior | None, str]:
    """Validate one structured failure_behavior; fail closed with a typed error."""
    if not isinstance(value, Mapping):
        return None, "failure_behavior_not_object"
    extra = sorted(str(key) for key in value if key not in FAILURE_BEHAVIOR_FIELDS)
    if extra:
        return None, "failure_behavior_unexpected_fields:" + ",".join(extra)
    exit_code = value.get("exit_code")
    if exit_code is not None:
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            return None, "failure_behavior_invalid_exit_code"
        if not 0 <= exit_code <= MAX_FAILURE_EXIT_CODE:
            return None, "failure_behavior_exit_code_out_of_range"
    stdout = value.get("stdout")
    stderr = value.get("stderr")
    stdout_hex = value.get("stdout_hex")
    for name, item in (("stdout", stdout), ("stderr", stderr),
                       ("stdout_hex", stdout_hex)):
        if item is not None and not isinstance(item, str):
            return None, "failure_behavior_invalid_" + name
    if stdout is not None and stdout_hex is not None:
        return None, "failure_behavior_conflicting_stdout"
    if stdout_hex is not None:
        try:
            bytes.fromhex(stdout_hex)
        except ValueError:
            return None, "failure_behavior_invalid_stdout_hex"
    contract = FailureBehavior(
        exit_code=exit_code, stdout=stdout, stderr=stderr, stdout_hex=stdout_hex,
    )
    if not contract.requested:
        return None, "failure_behavior_empty"
    return contract, ""


def failure_behavior_of(spec: "RepairSpec | RepairSpecV2") -> FailureBehavior | None:
    """Return the structured failure contract of a validated/reserialized spec."""
    if isinstance(spec, RepairSpecV2):
        raw = spec.repair.get("failure_behavior")
        if not isinstance(raw, Mapping):
            return None
        known = {key: raw.get(key) for key in FAILURE_BEHAVIOR_FIELDS
                 if key in raw}
        contract, error = parse_failure_behavior(known)
        return contract if not error else None
    return spec.failure_behavior_contract


def _scope_expectation(target_scope: Mapping[str, Any] | None) -> str:
    if (isinstance(target_scope, Mapping)
            and isinstance(target_scope.get("va"), int)
            and isinstance(target_scope.get("end"), int)):
        return (f"every address inside target_scope "
                f"[{int(target_scope['va']):#x}, {int(target_scope['end']):#x})")
    return "every address inside target_scope"


def diagnose_plan_error(
    error: str,
    *,
    case: Mapping[str, Any] | None = None,
    target_scope: Mapping[str, Any] | None = None,
    allowed_calls: Iterable[str] = (),
) -> dict[str, Any]:
    """Turn one typed plan-validation error into a field-level diagnostic.

    The repair plan already fails closed with typed error codes; this helper
    names the exact schema field and the expected value so a planner retry can
    be targeted. It never accepts a plan and never weakens validation.
    """
    reason = str(error or "")
    case = case or {}
    target = str(case.get("target") or "")
    architecture = str(case.get("arch") or "")
    capacity = case.get("capacity")
    allowed = sorted({str(item) for item in allowed_calls or ()})
    diagnostic: dict[str, Any] = {
        "schema_version": 1,
        "reason_code": reason,
        "field": None,
        "expected": None,
        "detail": None,
    }

    def set_fields(field: str | None, expected: str | None,
                   detail: str | None = None) -> dict[str, Any]:
        diagnostic["field"] = field
        diagnostic["expected"] = expected
        diagnostic["detail"] = detail
        return diagnostic

    if reason.startswith("missing_or_empty:"):
        return set_fields(reason.split(":", 1)[1], "a non-empty string")
    if reason.startswith("too_long:"):
        return set_fields(reason.split(":", 1)[1],
                          f"at most {MAX_TEXT} characters")
    if reason.startswith("unexpected_fields:"):
        return set_fields("(top level)",
                          "only fields from the supported schema",
                          "unexpected: " + reason.split(":", 1)[1])
    if reason.startswith("permitted_call_not_allowed"):
        offenders = reason.split(":", 1)[1] if ":" in reason else ""
        expected = ("a subset of the packet allowed_calls " + str(allowed)
                    if allowed else "a subset of the packet allowed_calls")
        return set_fields("program_context.allowed_calls", expected,
                          ("not allowed: " + offenders) if offenders else None)
    if reason.startswith("failure_behavior_"):
        return set_fields(
            "repair.failure_behavior",
            "{exit_code:int|null, stdout:str|null, stderr:str|null, "
            "stdout_hex:hex|null} with at least one non-null field")
    if reason == "invalid_allowed_calls":
        return set_fields("program_context.allowed_calls",
                          "a list of call names or {name} objects")
    if reason in {"invalid_affected_addresses", "invalid_affected_address",
                  "too_many_affected_addresses"}:
        return set_fields("program_context.addresses",
                          f"a list of at most {MAX_ITEMS} hex-string "
                          "addresses inside target_scope")
    if reason == "affected_address_out_of_scope":
        return set_fields(
            "program_context.addresses", _scope_expectation(target_scope),
            "do not list callee/import addresses; list only addresses inside "
            "target_scope (the planner packet now includes it)")
    if reason in {"invalid_capacity", "capacity_mismatch"}:
        expected = (f"the declared case capacity {capacity}" if capacity
                    else "a positive integer")
        return set_fields("program_context.capacity", expected)
    if reason in {"missing_security_invariants", "invalid_security_invariants"}:
        return set_fields("security_invariants",
                          "a non-empty list of non-empty strings")
    if reason in {"missing_security_conditions", "missing_regression_conditions",
                  "invalid_verification_conditions"}:
        return set_fields("verification.security_conditions / "
                          "verification.regression_conditions",
                          "non-empty lists of non-empty strings")
    if reason == "missing_verification_conditions":
        return set_fields("verification_conditions",
                          "a non-empty list of non-empty strings")
    if reason == "unsupported_repair_strategy":
        return set_fields("repair.strategy",
                          "one of " + str(sorted(V2_STRATEGIES)))
    if reason == "affected_function_mismatch":
        expected = (f"the target function name {target!r}" if target
                    else "the case target function name")
        return set_fields("program_context.function", expected)
    if reason == "abi_arch_mismatch":
        expected = (f"the case architecture {architecture!r}" if architecture
                    else "the case architecture")
        return set_fields("abi.architecture", expected)
    if reason == "abi_calling_convention_mismatch":
        expected = "the canonical convention for " + (architecture or "arch")
        return set_fields("abi.calling_convention", expected)
    if reason == "invalid_confidence":
        return set_fields("confidence",
                          "low|medium|high or a number in [0, 1]")
    if reason == "invalid_evidence_refs":
        return set_fields("evidence_refs",
                          "a list of real packet evidence ids")
    if reason == "v2_section_missing":
        return set_fields(
            "vulnerability/program_context/repair/abi/verification",
            "all five v2 sections present as objects")
    if reason in {"plan_not_object", "empty_plan"}:
        return set_fields(None, "one JSON RepairSpec object")
    if reason == "unsupported_schema_version":
        return set_fields("schema_version", "1 or 2")
    return diagnostic


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
    failure_behavior_contract: FailureBehavior | None = None

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
            **({"failure_behavior_contract":
                self.failure_behavior_contract.to_dict()}
               if self.failure_behavior_contract is not None else {}),
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
    contract = None
    if parsed.get("failure_behavior_contract") is not None:
        contract, error = parse_failure_behavior(
            parsed.get("failure_behavior_contract"))
        if error:
            return None, error
    spec = RepairSpec(
        schema_version=SCHEMA_VERSION,
        **values,
        affected_addresses=[str(x) for x in addresses],
        affected_registers=[str(x) for x in parsed.get("affected_registers", [])],
        affected_memory=[str(x) for x in parsed.get("affected_memory", [])],
        permitted_calls=[str(x) for x in permitted],
        verification_conditions=[str(x) for x in parsed.get("verification_conditions", [])],
        confidence=confidence,
        failure_behavior_contract=contract,
    )
    return spec, ""


# ---------------------------------------------------------------------------
# RepairSpec v2: nested vulnerability/context/security/repair/ABI/verification
# ---------------------------------------------------------------------------

V2_FIELDS = frozenset({
    "schema_version", "vulnerability", "program_context",
    "security_invariants", "repair", "abi", "verification", "confidence",
    "evidence_refs",
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
    repair: dict[str, Any]
    abi: dict[str, str]
    verification: dict[str, list[str]]
    confidence: str = "medium"
    evidence_refs: list[str] = field(default_factory=list)
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
            "evidence_refs": list(self.evidence_refs),
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
        low = strategy.lower()
        aliases = (
            ("format", "format_string"),
            ("lifetime", "lifetime"),
            ("use-after-free", "lifetime"),
            ("double-free", "lifetime"),
            ("null", "null_check"),
            ("integer", "integer_range_check"),
            ("length", "guard_input_length"),
            ("size", "guard_input_length"),
            ("copy", "guard_input_length"),
            ("bound", "bounds_check"),
            ("index", "bounds_check"),
            ("range", "bounds_check"),
        )
        strategy = next((canon for token, canon in aliases if token in low), "")
    if strategy not in V2_STRATEGIES:
        return None, "unsupported_repair_strategy"
    raw_failure = repair.get("failure_behavior")
    if isinstance(raw_failure, Mapping):
        contract, error = parse_failure_behavior(raw_failure)
        if error: return None, error
        failure = contract.to_dict()
    else:
        failure, error = _v2_text(raw_failure, "repair.failure_behavior")
        if error: return None, error
    expected, error = _v2_text(repair.get("expected_behavior"), "repair.expected_behavior")
    if error: return None, error
    arch, error = _v2_text(abi.get("architecture"), "abi.architecture")
    if error: return None, error
    calling, error = _v2_text(abi.get("calling_convention"), "abi.calling_convention")
    if error: return None, error
    arch_norm = arch.lower().replace("-", "_")
    case_arch = str(case.get("arch") or "").lower().replace("-", "_")
    if case_arch and arch_norm != case_arch:
        return None, "abi_arch_mismatch"
    calling_norm = " ".join(calling.lower().replace("_", " ").split())
    canonical_calling = {
        "sysv amd64": "sysv_amd64",
        "systemv amd64": "sysv_amd64",
        "system v amd64": "sysv_amd64",
        "sysv": "sysv_amd64",
        "systemv": "sysv_amd64",
        "cdecl": "cdecl",
        "aapcs64": "aapcs64",
    }.get(calling_norm)
    if canonical_calling is None:
        canonical_calling = calling_norm.replace(" ", "_")
    if V2_ABI.get(arch_norm) and canonical_calling != V2_ABI[arch_norm]:
        return None, "abi_calling_convention_mismatch"
    raw_calls = context.get("allowed_calls", [])
    if not isinstance(raw_calls, list):
        return None, "invalid_allowed_calls"
    required_calls: list[str] = []
    for item in raw_calls:
        if isinstance(item, str):
            name = item
        elif isinstance(item, Mapping):
            name = item.get("name")
        else:
            return None, "invalid_allowed_calls"
        if not isinstance(name, str) or not name:
            return None, "invalid_allowed_calls"
        required_calls.append(name)
    allowed = {str(x) for x in allowed_calls}
    if any(x not in allowed for x in required_calls):
        return None, "permitted_call_not_allowed:" + ",".join(sorted(set(required_calls) - allowed))
    addresses = context.get("addresses", [])
    if isinstance(addresses, Mapping):
        addresses = [str(value) for value in addresses.values()]
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
    refs = parsed.get("evidence_refs", [])
    if not isinstance(refs, list) or not all(isinstance(x, str) and x.strip() for x in refs):
        return None, "invalid_evidence_refs"
    return RepairSpecV2(
        vulnerability={"type": vuln_type, "root_cause": root,
                       **({"cwe": str(vulnerability["cwe"])} if vulnerability.get("cwe") else {})},
        program_context={
            "function": function, "addresses": list(addresses),
            "registers": list(context.get("registers", [])),
            "memory": (
                [f"{key}={value}" for key, value in context["memory"].items()]
                if isinstance(context.get("memory"), Mapping)
                else list(context.get("memory", []))
            ),
            "capacity": context.get("capacity"),
            "allowed_calls": list(required_calls),
        },
        security_invariants=[str(x) for x in invariants],
        repair={"strategy": strategy, "failure_behavior": failure,
                "expected_behavior": expected},
        abi={"architecture": arch_norm, "calling_convention": canonical_calling},
        verification={"security_conditions": [str(x) for x in security],
                      "regression_conditions": [str(x) for x in regression],
                      "required_inputs": [str(x) for x in verification.get("required_inputs", [])]},
        confidence=confidence,
        evidence_refs=[str(x) for x in refs],
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
            evidence_refs=list(plan.get("evidence_refs") or []),
        )
    values = dict(plan)
    raw_contract = values.pop("failure_behavior_contract", None)
    contract = None
    if isinstance(raw_contract, Mapping):
        contract, _error = parse_failure_behavior(raw_contract)
    values["failure_behavior_contract"] = contract
    return RepairSpec(**values)
