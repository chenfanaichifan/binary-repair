#!/usr/bin/env python3
"""Validate the six Phase-7 JSON contracts and their fixtures.

The contracts directory is the machine-readable interface between the Phase-7
modules (acceptance intelligence, capability universe, gap registry, repair
state machine, evidence binding, reflection engine) and the audit/CI layers.  A
contract is only useful if it is strict and if valid samples pass while invalid
samples are rejected, so this checker:

* loads exactly the six schemas and validates their own structure (``$schema``,
  ``$id``, title/description, ``type=object``, non-empty ``required``,
  non-empty enums, compilable patterns, ASCII-only schema text);
* validates 6 committed valid fixtures against their schema (must pass) and 6
  invalid fixtures (must be rejected);
* enforces contract-specific cross-field semantics that JSON Schema alone
  cannot express (repair release gating, reflection 12-question/verified
  contract, acceptance registry completeness, evidence honesty);
* verifies ``SHA256SUMS`` deterministically with ``--check`` and can regenerate
  it with ``--write-sums``.

``jsonschema`` is used when importable. Otherwise a documented minimal
validator (``type``/``required``/``properties``/``additionalProperties``/
``enum``/``const``/``pattern``/``items``/``minItems``/``maxItems``/``minimum``/
``maximum``/``uniqueItems``) is used and the report says ``validator=fallback``.

``--json`` prints the report; exit code is 0 iff ok, 1 for contract/fixture/SUMS
violations, 2 for unusable inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAMES: tuple[str, ...] = (
    "capability",
    "gap",
    "acceptance",
    "repair",
    "evidence",
    "reflection",
    "benchmark-sample",
    "verification",
    "binary-target",
    "vulnerability-finding",
    "root-cause",
    "patch-candidate",
)
CONTRACTS_DIRNAME = "contracts"
FIXTURES_DIRNAME = "artifacts/contract-fixtures-2026-11-16"
FIXTURE_KINDS = ("valid", "invalid")
SUMS_FILENAME = "SHA256SUMS"

#: Committed module artifacts that must keep validating against their contract.
#: The third value is the collection key inside the JSON payload; ``None``
#: means "one record (or a list under verifications/reports)".
#: The last value marks the integration as required for this checkout.
ARTIFACT_INTEGRATIONS: tuple[tuple[str, str, str, str | None, bool], ...] = (
    ("capability-universe",
     "artifacts/capability-universe-2026-11-16/dimension-registry.json",
     "capability", "dimensions", True),
    ("gap-registry",
     "artifacts/gap-registry-2026-11-16/gaps.json",
     "gap", "records", True),
    ("autonomous-reflection",
     "artifacts/autonomous-reflection-2026-11-16/reflection.json",
     "reflection", "records", True),
    ("benchmark-manifest",
     "benchmark/phase8-v1/manifest.json",
     "benchmark-sample", "samples", False),
    ("verification-report",
     "artifacts/phase8-verification-2026-11-16/report.json",
     "verification", None, False),
)

SCHEMA_URL_PREFIX = "https://json-schema.org/"
JSON_TYPES = frozenset({
    "null", "boolean", "object", "array", "number", "string", "integer",
})
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ASCII = re.compile(r"^[\x00-\x7f]*$")

_FALLBACK_TYPES = {
    "null": lambda value: value is None,
    "boolean": lambda value: isinstance(value, bool),
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "number": lambda value: isinstance(value, (int, float))
    and not isinstance(value, bool),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int)
    and not isinstance(value, bool),
}


class _FallbackValidator:
    """Minimal JSON-Schema subset validator used when jsonschema is absent."""

    name = "fallback"

    def __init__(self) -> None:
        self.errors: list[str] = []

    def _error(self, path: str, message: str) -> None:
        self.errors.append(f"{path or '$'}: {message}")

    def validate(self, instance: Any, schema: Mapping[str, Any],
                 path: str = "") -> list[str]:
        self.errors = []
        self._validate(instance, schema, path)
        return list(self.errors)

    def _validate(self, value: Any, schema: Mapping[str, Any], path: str) -> None:
        if not isinstance(schema, Mapping):
            return
        if "const" in schema and value != schema["const"]:
            self._error(path, f"expected const {schema['const']!r}, got {value!r}")
        if "enum" in schema and value not in schema["enum"]:
            self._error(path, f"value {value!r} not in enum {schema['enum']!r}")
        if "type" in schema:
            expected = schema["type"]
            names = [expected] if isinstance(expected, str) else list(expected)
            checks = [_FALLBACK_TYPES[name] for name in names
                      if name in _FALLBACK_TYPES]
            if checks and not any(check(value) for check in checks):
                self._error(path, f"value {value!r} is not of type {names}")
                return
        if isinstance(value, str):
            pattern = schema.get("pattern")
            if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
                self._error(path, f"string {value!r} does not match {pattern!r}")
            if "minLength" in schema and len(value) < int(schema["minLength"]):
                self._error(path, f"string shorter than {schema['minLength']}")
            if "maxLength" in schema and len(value) > int(schema["maxLength"]):
                self._error(path, f"string longer than {schema['maxLength']}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                self._error(path, f"value {value!r} below minimum {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                self._error(path, f"value {value!r} above maximum {schema['maximum']}")
        if isinstance(value, list):
            if "minItems" in schema and len(value) < int(schema["minItems"]):
                self._error(path, f"array shorter than {schema['minItems']}")
            if "maxItems" in schema and len(value) > int(schema["maxItems"]):
                self._error(path, f"array longer than {schema['maxItems']}")
            if schema.get("uniqueItems"):
                try:
                    seen: list[Any] = []
                    for item in value:
                        if item in seen:
                            self._error(path, "array items are not unique")
                            break
                        seen.append(item)
                except TypeError:
                    pass
            item_schema = schema.get("items")
            if isinstance(item_schema, Mapping):
                for index, item in enumerate(value):
                    self._validate(item, item_schema, f"{path}[{index}]")
        if isinstance(value, dict):
            required = schema.get("required") or []
            for key in required:
                if key not in value:
                    self._error(path, f"missing required property {key!r}")
            properties = schema.get("properties") or {}
            for key, item in value.items():
                child = f"{path}.{key}" if path else key
                if isinstance(properties, Mapping) and key in properties:
                    self._validate(item, properties[key], child)
                else:
                    additional = schema.get("additionalProperties", True)
                    if additional is False:
                        self._error(path, f"unexpected property {key!r}")
                    elif isinstance(additional, Mapping):
                        self._validate(item, additional, child)


def _jsonschema_validator(schema: Mapping[str, Any]):
    """Return a jsonschema validator or ``None`` when the library is missing."""
    try:
        import jsonschema  # type: ignore
    except Exception:  # noqa: BLE001 - optional dependency
        return None, "jsonschema import failed"
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - reported to the caller
        return None, f"schema is not a valid JSON Schema: {exc}"
    return jsonschema.Draft202012Validator(schema), ""


def _load_json(path: Path) -> tuple[Any | None, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"


def _iter_schema_nodes(node: Any, path: str = "$"):
    if isinstance(node, Mapping):
        yield path, node
        for key, item in node.items():
            if key in {"properties"} and isinstance(item, Mapping):
                for name, child in item.items():
                    yield from _iter_schema_nodes(child, f"{path}.properties.{name}")
            elif key in {"items", "additionalProperties", "not"}:
                yield from _iter_schema_nodes(item, f"{path}.{key}")
            elif key in {"allOf", "anyOf", "oneOf"} and isinstance(item, list):
                for index, child in enumerate(item):
                    yield from _iter_schema_nodes(child, f"{path}.{key}[{index}]")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _iter_schema_nodes(item, f"{path}[{index}]")


def check_schema_document(name: str, schema: Any) -> list[str]:
    """Structural contract checks for one schema document."""
    violations: list[str] = []
    if not isinstance(schema, Mapping):
        return [f"{name}: schema is not a JSON object"]
    schema_url = schema.get("$schema")
    if not isinstance(schema_url, str) or not schema_url.startswith(
            SCHEMA_URL_PREFIX):
        violations.append(f"{name}: $schema must be a json-schema.org URL")
    if not isinstance(schema.get("$id"), str) or not schema["$id"]:
        violations.append(f"{name}: $id must be a non-empty string")
    if not isinstance(schema.get("title"), str) or not schema["title"]:
        violations.append(f"{name}: title must be a non-empty string")
    if not isinstance(schema.get("description"), str) or not schema["description"]:
        violations.append(f"{name}: description must be a non-empty string")
    if schema.get("type") != "object":
        violations.append(f"{name}: root type must be 'object'")
    if schema.get("additionalProperties") is not False:
        violations.append(f"{name}: root additionalProperties must be false")
    for node_path, node in _iter_schema_nodes(schema):
        required = node.get("required")
        if required is not None:
            if (not isinstance(required, list) or not required
                    or not all(isinstance(item, str) and item for item in required)):
                violations.append(
                    f"{name}: {node_path}.required must be a non-empty string list")
            elif len(set(required)) != len(required):
                violations.append(
                    f"{name}: {node_path}.required has duplicates")
        enum = node.get("enum")
        if enum is not None:
            if not isinstance(enum, list) or not enum:
                violations.append(f"{name}: {node_path}.enum must be non-empty")
            elif len({json.dumps(item, sort_keys=True) for item in enum}) != len(enum):
                violations.append(f"{name}: {node_path}.enum has duplicates")
        pattern = node.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str) or not pattern:
                violations.append(f"{name}: {node_path}.pattern must be a string")
            else:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    violations.append(
                        f"{name}: {node_path}.pattern is invalid: {exc}")
        node_type = node.get("type")
        if node_type is not None:
            names = [node_type] if isinstance(node_type, str) else node_type
            if (not isinstance(names, list) or not names
                    or not all(name in JSON_TYPES for name in names)):
                violations.append(
                    f"{name}: {node_path}.type is not a JSON type name")
    if not isinstance(schema.get("properties"), Mapping) or not schema["properties"]:
        violations.append(f"{name}: root properties must be a non-empty object")
    return violations


def _acceptance_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    dimensions = instance.get("dimensions")
    if isinstance(dimensions, list):
        ids = [str(item.get("id")) for item in dimensions
               if isinstance(item, Mapping)]
        expected = [f"A{index:02d}" for index in range(1, 9)]
        if ids != expected:
            violations.append(
                f"acceptance: dimension ids must be exactly {expected}, got {ids}")
    mismatches = instance.get("mismatch_classes")
    if isinstance(mismatches, list):
        ids = [str(item.get("id")) for item in mismatches
               if isinstance(item, Mapping)]
        expected = [f"AM{index:02d}" for index in range(1, 25)]
        if ids != expected:
            violations.append(
                "acceptance: mismatch class ids must be exactly AM01-AM24, "
                f"got {ids}")
    result = instance.get("match_result")
    if isinstance(result, Mapping):
        result_mismatches = result.get("mismatches")
        known = {
            str(item.get("id"))
            for item in (mismatches or [])
            if isinstance(item, Mapping)
        }
        for mismatch_id in result_mismatches or []:
            if known and mismatch_id not in known:
                violations.append(
                    f"acceptance: match_result mismatch {mismatch_id!r} "
                    "is not a declared mismatch class")
        if result.get("verified") is True:
            if result_mismatches:
                violations.append(
                    "acceptance: verified match result lists mismatches")
            if result.get("decision") != "verified":
                violations.append(
                    "acceptance: verified match result must use decision=verified")
    return violations


def _repair_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    state = instance.get("state")
    candidate = instance.get("candidate_sha256")
    if state in {"patch_candidate", "verified", "release_eligible"}:
        if not isinstance(candidate, str) or SHA256_PATTERN.fullmatch(candidate) is None:
            violations.append(
                f"repair: state {state!r} requires a candidate_sha256")
    if state == "verified" and instance.get("evidence_ok") is not True:
        violations.append("repair: verified state requires evidence_ok=true")
    if instance.get("release_eligible") is True:
        if state != "release_eligible":
            violations.append(
                "repair: release_eligible=true requires state=release_eligible")
        if instance.get("evidence_ok") is not True:
            violations.append(
                "repair: release_eligible=true requires evidence_ok=true")
        if instance.get("independence_ok") is not True:
            violations.append(
                "repair: release_eligible=true requires independence_ok=true")
    return violations


def _evidence_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    runner = instance.get("runner")
    guest = instance.get("guest")
    if isinstance(runner, Mapping) and isinstance(guest, Mapping):
        if runner.get("kind") == "none" and runner.get("available") is True:
            violations.append("evidence: a 'none' runner cannot be available")
        if guest.get("available") is True and guest.get("engine") == "none":
            violations.append("evidence: an available guest must have an engine")
        if guest.get("available") is False and not str(guest.get("reason") or "").strip():
            violations.append(
                "evidence: an unavailable guest must carry a reason")
    independence = instance.get("independence")
    if isinstance(independence, Mapping):
        if independence.get("ok") is True and independence.get("method") == "none":
            violations.append(
                "evidence: independence.ok=true needs a real method")
    return violations


def _reflection_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    questions = instance.get("12_questions")
    if isinstance(questions, list):
        ids = [str(item.get("q")) for item in questions
               if isinstance(item, Mapping)]
        expected = [f"Q{index:02d}" for index in range(1, 13)]
        if ids != expected:
            violations.append(
                f"reflection: 12_questions must be exactly Q01-Q12, got {ids}")
    if instance.get("verified") is not False:
        violations.append("reflection: verified must be exactly false")
    plan = instance.get("experiment_plan")
    decision = instance.get("capability_decision")
    if decision == "candidate" and isinstance(plan, Mapping):
        if plan.get("status") != "planned":
            violations.append(
                "reflection: candidate decision requires a planned experiment")
        if not plan.get("samples"):
            violations.append(
                "reflection: candidate decision requires concrete samples")
    return violations


def _gap_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    risk = instance.get("false_verified_risk")
    if risk in {"high", "critical"} and instance.get("verification_required") is not True:
        violations.append(
            "gap: high/critical false_verified_risk requires verification_required=true")
    if not SHA256_PATTERN.fullmatch("0" * 64):
        violations.append("gap: internal sha256 pattern is broken")
    return violations


def _verification_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    decision = instance.get("decision")
    independence = instance.get("independence")
    if not isinstance(independence, Mapping):
        return ["verification: independence must be an object"]
    checks = instance.get("checks")
    checks = checks if isinstance(checks, list) else []
    if decision == "verified":
        if independence.get("ok") is not True:
            violations.append(
                "verification: verified requires independence.ok=true")
        if independence.get("generator_evidence_excluded") is not True:
            violations.append(
                "verification: verified requires "
                "independence.generator_evidence_excluded=true")
        independent_passed = [
            check for check in checks
            if isinstance(check, Mapping)
            and check.get("status") == "passed"
            and check.get("independent") is True
        ]
        if not independent_passed:
            violations.append(
                "verification: verified requires at least one passed "
                "independent oracle check")
        required_failed = [
            check for check in checks
            if isinstance(check, Mapping)
            and check.get("required") is True
            and check.get("status") in {"failed", "not_run"}
        ]
        if required_failed:
            violations.append(
                "verification: verified forbids failed/not_run required checks")
    return violations


def _benchmark_sample_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    if instance.get("hidden_available") is not False:
        violations.append("benchmark-sample: hidden_available must be false")
    oracle = instance.get("oracle")
    kinds = oracle.get("kinds") if isinstance(oracle, Mapping) else None
    expected_scope = instance.get("expected_scope")
    independent_kinds = {"external_poc", "native", "emulated"}
    if isinstance(kinds, list):
        independent = sorted(set(kinds) & independent_kinds)
        if expected_scope == "analysis_only" and independent:
            violations.append(
                "benchmark-sample: analysis_only expectation must not claim "
                "an independent runtime oracle")
        if expected_scope in {"function", "whole_program"} and not independent:
            violations.append(
                "benchmark-sample: function/whole_program expectation requires "
                "at least one independent oracle kind")
    return violations


def _binary_target_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    scope = instance.get("target_scope")
    policy = scope.get("policy") if isinstance(scope, Mapping) else None
    if policy == "target_scoped":
        has_name = isinstance(scope, Mapping) and bool(str(scope.get("name") or ""))
        has_range = (
            isinstance(scope, Mapping)
            and isinstance(scope.get("va"), int)
            and isinstance(scope.get("end"), int)
            and scope.get("end") > scope.get("va")
        )
        if not (has_name or has_range):
            violations.append(
                "binary-target: target_scoped requires a name or a valid VA range")
    identity = instance.get("identity")
    if isinstance(identity, Mapping) and identity.get("kind") == "sha256":
        if identity.get("value") != instance.get("target_sha256"):
            violations.append(
                "binary-target: sha256 identity must equal target_sha256")
    compiler = instance.get("compiler")
    if isinstance(compiler, Mapping) and compiler.get("available") is False:
        if not str(compiler.get("reason") or "").strip():
            violations.append(
                "binary-target: unavailable compiler requires a reason")
    return violations


def _root_cause_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    data_flow = instance.get("data_flow_evidence") or []
    control_flow = instance.get("control_flow_evidence") or []
    if not data_flow and not control_flow:
        violations.append(
            "root-cause: at least one of data_flow_evidence/"
            "control_flow_evidence must be non-empty")
    return violations


def _patch_candidate_semantics(instance: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    status = instance.get("status")
    plan = instance.get("verification_plan")
    if status == "verified":
        if not isinstance(plan, Mapping) or plan.get("independent_oracle") is not True:
            violations.append(
                "patch-candidate: verified requires "
                "verification_plan.independent_oracle=true")
        model_identity = instance.get("model_identity")
        identity_status = (
            model_identity.get("status")
            if isinstance(model_identity, Mapping) else None
        )
        if identity_status in {"served-model-only", "unknown", "mismatch"}:
            violations.append(
                "patch-candidate: verified forbids untrusted model identity "
                f"status {identity_status!r}")
    range_info = instance.get("modification_range")
    if isinstance(range_info, Mapping):
        start = range_info.get("start")
        end = range_info.get("end")
        size = range_info.get("size")
        if isinstance(start, int) and isinstance(end, int) and isinstance(size, int):
            if end - start != size:
                violations.append(
                    "patch-candidate: modification_range size must equal end-start")
    for index, action in enumerate(instance.get("actions") or []):
        if not isinstance(action, Mapping):
            continue
        for key in ("before_hex", "after_hex"):
            value = action.get(key)
            if isinstance(value, str) and isinstance(action.get("size"), int):
                if len(value) != action["size"] * 2:
                    violations.append(
                        f"patch-candidate: actions[{index}].{key} length must "
                        f"equal size*2")
    return violations


CONTRACT_SEMANTICS = {
    "acceptance": _acceptance_semantics,
    "repair": _repair_semantics,
    "evidence": _evidence_semantics,
    "reflection": _reflection_semantics,
    "gap": _gap_semantics,
    "capability": lambda instance: [],
    "benchmark-sample": _benchmark_sample_semantics,
    "verification": _verification_semantics,
    "binary-target": _binary_target_semantics,
    "vulnerability-finding": lambda instance: [],
    "root-cause": _root_cause_semantics,
    "patch-candidate": _patch_candidate_semantics,
}


def _validate_instance(name: str, schema: Mapping[str, Any], instance: Any,
                       *, use_jsonschema: bool) -> tuple[list[str], str]:
    """Return ``(errors, validator_name)`` for one instance."""
    if use_jsonschema:
        validator, _error = _jsonschema_validator(schema)
        if validator is not None:
            errors = [
                f"$.{'.'.join(str(part) for part in item.absolute_path)}: "
                f"{item.message}"
                for item in validator.iter_errors(instance)
            ]
            return errors, "jsonschema"
    fallback = _FallbackValidator()
    return fallback.validate(instance, schema), "fallback"


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sums_entries(root: Path, contracts_dir: Path, fixtures_dir: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for name in SCHEMA_NAMES:
        path = contracts_dir / f"{name}.schema.json"
        entries[path.relative_to(root).as_posix()] = _hash_file(path)
    for name in SCHEMA_NAMES:
        for kind in FIXTURE_KINDS:
            path = fixtures_dir / f"{name}.{kind}.json"
            entries[path.relative_to(root).as_posix()] = _hash_file(path)
    return entries


def _write_sums(path: Path, entries: Mapping[str, str]) -> None:
    lines = [f"{digest}  {relative}\n" for relative, digest in sorted(entries.items())]
    path.write_text("".join(lines), encoding="utf-8")


def _parse_sums(path: Path) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}
    violations: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return {}, [f"SUMS unreadable: {type(exc).__name__}: {exc}"]
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (\S+)", line)
        if match is None:
            violations.append(f"SUMS line {line_number} is malformed: {line!r}")
            continue
        digest, relative = match.groups()
        if relative in entries:
            violations.append(f"SUMS line {line_number} duplicates {relative}")
            continue
        entries[relative] = digest
    return entries, violations


def check_sums(root: Path, sums_path: Path,
               entries: Mapping[str, str]) -> list[str]:
    if not sums_path.is_file():
        return [f"SUMS file missing: {sums_path}"]
    recorded, violations = _parse_sums(sums_path)
    expected = dict(entries)
    missing = sorted(set(expected) - set(recorded))
    extra = sorted(set(recorded) - set(expected))
    if missing:
        violations.append(f"SUMS missing entries: {missing}")
    if extra:
        violations.append(f"SUMS has unexpected entries: {extra}")
    for relative in sorted(set(expected) & set(recorded)):
        if recorded[relative] != expected[relative]:
            violations.append(f"SUMS digest mismatch for {relative}")
    return violations


def run_check(
    root: Path = ROOT,
    contracts_dir: Path | None = None,
    fixtures_dir: Path | None = None,
    *,
    check_sums: bool = False,
    write_sums: bool = False,
    use_jsonschema: bool = True,
) -> dict[str, Any]:
    """Run the full contract check; returns the report payload."""
    root = Path(root).resolve()
    contracts = Path(contracts_dir) if contracts_dir is not None else root / CONTRACTS_DIRNAME
    fixtures = Path(fixtures_dir) if fixtures_dir is not None else root / FIXTURES_DIRNAME
    sums_path = fixtures / SUMS_FILENAME
    report: dict[str, Any] = {
        "ok": False,
        "root": str(root),
        "contracts_dir": str(contracts),
        "fixtures_dir": str(fixtures),
        "validator": "jsonschema" if use_jsonschema else "fallback",
        "schema_count": 0,
        "fixtures": {"valid_passed": 0, "invalid_rejected": 0, "total": 0},
        "checks": [],
        "violations": [],
        "sums": {"checked": False, "written": False, "path": str(sums_path)},
    }
    violations: list[str] = report["violations"]
    stray = sorted(
        path.name for path in fixtures.glob("*.json")
        if path.name.rsplit(".", 2)[0] not in SCHEMA_NAMES
    ) if fixtures.is_dir() else []
    loaded_schemas: dict[str, Mapping[str, Any]] = {}
    for name in SCHEMA_NAMES:
        path = contracts / f"{name}.schema.json"
        schema, error = _load_json(path)
        if schema is None:
            violations.append(f"{name}: schema unavailable: {error}")
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:  # pragma: no cover - reported
            violations.append(f"{name}: unreadable schema: {exc}")
            continue
        if not _ASCII.match(raw):
            violations.append(f"{name}: schema file must be ASCII-only")
        violations.extend(check_schema_document(name, schema))
        loaded_schemas[name] = schema
    report["schema_count"] = len(loaded_schemas)
    if stray:
        violations.append(f"unexpected fixture files: {stray}")
    validator_names: set[str] = set()
    for name, schema in loaded_schemas.items():
        for kind in FIXTURE_KINDS:
            path = fixtures / f"{name}.{kind}.json"
            instance, error = _load_json(path)
            if instance is None:
                violations.append(f"{name}.{kind}: fixture unavailable: {error}")
                continue
            errors, validator_name = _validate_instance(
                name, schema, instance, use_jsonschema=use_jsonschema)
            validator_names.add(validator_name)
            if kind == "valid":
                if errors:
                    violations.append(
                        f"{name}.valid: valid fixture rejected: {errors[:3]}")
                else:
                    report["fixtures"]["valid_passed"] += 1
                    if isinstance(instance, Mapping):
                        violations.extend(CONTRACT_SEMANTICS[name](instance))
                    else:
                        violations.append(f"{name}.valid: fixture is not an object")
            else:
                if not errors:
                    violations.append(
                        f"{name}.invalid: invalid fixture was accepted")
                else:
                    report["fixtures"]["invalid_rejected"] += 1
    integrations: list[dict[str, Any]] = []
    for integration_id, relative, schema_name, collection, required in (
        ARTIFACT_INTEGRATIONS
    ):
        artifact_path = root / relative
        entry: dict[str, Any] = {
            "id": integration_id,
            "path": relative,
            "required": required,
            "status": "not_run",
            "record_count": 0,
            "detail": "",
        }
        schema = loaded_schemas.get(schema_name)
        if schema is None:
            entry["detail"] = "contract schema unavailable"
            if required:
                violations.append(
                    f"artifact {integration_id}: contract schema unavailable")
            integrations.append(entry)
            continue
        if not artifact_path.is_file():
            entry["detail"] = "artifact not committed in this checkout"
            if required:
                violations.append(
                    f"artifact {integration_id}: required committed artifact "
                    f"missing: {relative}")
            integrations.append(entry)
            continue
        payload, error = _load_json(artifact_path)
        if payload is None:
            entry["detail"] = f"unreadable artifact: {error}"
            violations.append(
                f"artifact {integration_id}: unreadable ({error})")
            integrations.append(entry)
            continue
        records: list[Any] = []
        if collection is not None:
            value = payload.get(collection) if isinstance(payload, Mapping) else None
            if isinstance(value, list):
                records = value
        else:
            if isinstance(payload, Mapping) and payload.get("decision"):
                records = [payload]
            elif isinstance(payload, Mapping) and isinstance(
                    payload.get("verifications"), list):
                records = list(payload["verifications"])
            elif isinstance(payload, Mapping) and isinstance(
                    payload.get("report"), Mapping):
                records = [payload["report"]]
        if not records:
            entry["detail"] = "no records found in the expected collection"
            integrations.append(entry)
            continue
        artifact_errors: list[str] = []
        for index, record in enumerate(records):
            errors, _validator_name = _validate_instance(
                schema_name, schema, record, use_jsonschema=use_jsonschema)
            if errors:
                artifact_errors.append(f"record[{index}]: {errors[:2]}")
            elif isinstance(record, Mapping):
                artifact_errors.extend(CONTRACT_SEMANTICS[schema_name](record))
        entry["record_count"] = len(records)
        if artifact_errors:
            entry["status"] = "failed"
            entry["detail"] = artifact_errors[0]
            violations.append(
                f"artifact {integration_id}: committed records violate the "
                f"contract: {artifact_errors[:2]}")
        else:
            entry["status"] = "validated"
        integrations.append(entry)
    report["integrations"] = integrations
    report["fixtures"]["total"] = 2 * len(SCHEMA_NAMES)
    if validator_names:
        report["validator"] = (
            "jsonschema" if "jsonschema" in validator_names else "fallback"
        )
    if write_sums:
        try:
            entries = _sums_entries(root, contracts, fixtures)
        except (OSError, ValueError) as exc:
            violations.append(f"cannot compute SUMS: {type(exc).__name__}: {exc}")
        else:
            try:
                _write_sums(sums_path, entries)
            except OSError as exc:
                violations.append(f"cannot write SUMS: {exc}")
            else:
                report["sums"]["written"] = True
    sums_violations: list[str] = []
    if check_sums:
        report["sums"]["checked"] = True
        try:
            entries = _sums_entries(root, contracts, fixtures)
        except (OSError, ValueError) as exc:
            sums_violations.append(
                f"cannot compute SUMS: {type(exc).__name__}: {exc}")
        else:
            sums_violations = check_sums_errors(root, sums_path, entries)
        violations.extend(sums_violations)
        report["sums"]["ok"] = not sums_violations
    else:
        report["sums"]["ok"] = True
    report["checks"] = [
        {"id": "schemas", "ok": report["schema_count"] == len(SCHEMA_NAMES)},
        {"id": "valid-fixtures",
         "ok": report["fixtures"]["valid_passed"] == len(SCHEMA_NAMES)},
        {"id": "invalid-fixtures",
         "ok": report["fixtures"]["invalid_rejected"] == len(SCHEMA_NAMES)},
        {"id": "artifacts",
         "ok": all(item["status"] != "failed"
                   for item in report.get("integrations", []))},
        {"id": "sums", "ok": bool(report["sums"]["ok"])},
    ]
    report["ok"] = not violations
    return report


def check_sums_errors(root: Path, sums_path: Path,
                      entries: Mapping[str, str]) -> list[str]:
    """Alias kept explicit for tests; delegates to :func:`check_sums`."""
    return check_sums(root, sums_path, entries)


def _format_text(report: Mapping[str, Any]) -> str:
    lines = [
        "contract-schemas: ok={ok} validator={validator} schemas={schemas} "
        "valid={valid}/{total} invalid={invalid}/{total} sums_checked={sums} "
        "violations={violations}".format(
            ok=report["ok"],
            validator=report["validator"],
            schemas=report["schema_count"],
            valid=report["fixtures"]["valid_passed"],
            invalid=report["fixtures"]["invalid_rejected"],
            total=report["fixtures"]["total"] // 2,
            artifacts=len(report.get("integrations", [])),
            sums=report["sums"]["checked"],
            violations=len(report["violations"]),
        )
    ]
    for violation in report["violations"]:
        lines.append(f"FAIL {violation}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="validate the six Phase-7 JSON contracts and fixtures")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root the SUMS paths are relative to")
    parser.add_argument("--contracts-dir", type=Path, default=None,
                        help="contracts directory (default: <root>/contracts)")
    parser.add_argument("--fixtures-dir", type=Path, default=None,
                        help="fixtures directory "
                             "(default: <root>/artifacts/contract-fixtures-2026-11-16)")
    parser.add_argument("--json", action="store_true", help="print JSON report")
    parser.add_argument("--check", action="store_true",
                        help="also verify the deterministic SHA256SUMS file")
    parser.add_argument("--write-sums", action="store_true",
                        help="write/regenerate the SHA256SUMS file")
    parser.add_argument("--no-jsonschema", action="store_true",
                        help="force the minimal fallback validator (test mode)")
    args = parser.parse_args(argv)
    report = run_check(
        args.root, args.contracts_dir, args.fixtures_dir,
        check_sums=args.check, write_sums=args.write_sums,
        use_jsonschema=not args.no_jsonschema,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(_format_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
