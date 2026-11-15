"""Independent repair verifier (MVP).

This module is the *second* pair of eyes: it takes the raw original/candidate
bytes, declared target metadata, an independent oracle and generator metadata,
and re-derives every claim from bytes.  It never trusts a generator verdict and
never imports an AI provider or the repair generation pipeline.

Hard rules
----------

* the generator's claimed ``verified``/``decision`` value is never read and never
  contributes to the verifier decision; ``generator_evidence_excluded`` is always
  true and the verifier id is fixed (``independent-verifier/1``);
* ``generator_id`` must be declared and must differ from the verifier id;
* at least one independent oracle is required; generator/reference self-report
  alone is insufficient and is rejected;
* the decision is fail-closed: any failed required check -> ``rejected``; any
  required check that cannot run (oracle/ABI unavailable, missing scope) ->
  ``not_run``; only all-required-passed with a passing independent oracle can be
  ``verified``;
* ``report_sha256`` is the sha256 of the canonical report without that field, so
  identical inputs produce an identical report.

Checks (all required): ``identity``, ``container``, ``action-replay``,
``target-scope``, ``abi``, ``runtime-oracle``, ``evidence-completeness``,
``independence``.

The module is offline and deterministic: no network, no clock, no LLM.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable

SCHEMA_VERSION = 1
VERIFIER_ID = "independent-verifier/1"
CHECK_STATUSES = ("passed", "failed", "not_run")
DECISIONS = ("verified", "rejected", "inconclusive", "not_run")
CHECK_ORDER = (
    "identity",
    "container",
    "action-replay",
    "target-scope",
    "abi",
    "runtime-oracle",
    "evidence-completeness",
    "independence",
)
CHECK_TITLES = {
    "identity": "Original/candidate identity and candidate change",
    "container": "Container re-parse and metadata agreement",
    "action-replay": "Byte-level action replay from raw images",
    "target-scope": "Candidate modifications stay inside the declared target scope",
    "abi": "Candidate instruction-block ABI validation",
    "runtime-oracle": "Independent external PoC differential and regression",
    "evidence-completeness": "At least one independent oracle (no generator-only evidence)",
    "independence": "Generator/verifier independence and generator-evidence exclusion",
}
DEFAULT_TIMEOUT = 60.0
TARGET_FORMATS = ("elf", "macho", "pe")
TARGET_ARCHES = ("x86_64", "i386", "arm64")
TARGET_BITS = (32, 64)
TARGET_ENDIANS = ("little", "big")
TARGET_POLICIES = ("target_scoped", "whole_image", "analysis_only")
#: Sentinel id used only when the generator did not declare an identity; the
#: independence check still fails, so this can never produce a verified result.
UNDECLARED_GENERATOR = "undeclared-generator"


class UnsupportedVerificationTarget(ValueError):
    """Raised when the target cannot be represented by the verification schema."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _check(check_id: str, status: str, detail: str, *, required: bool = True,
           independent: bool = False) -> dict[str, Any]:
    if check_id not in CHECK_TITLES:
        raise ValueError(f"unknown check id: {check_id!r}")
    if status not in CHECK_STATUSES:
        raise ValueError(f"invalid check status: {status!r}")
    payload = {
        "id": check_id,
        "title": CHECK_TITLES[check_id],
        "status": status,
        "required": bool(required),
        "detail": detail,
    }
    if independent:
        payload["independent"] = True
    return payload


def _hex_at(data: bytes, offset: int, size: int) -> str | None:
    if offset < 0 or size <= 0 or offset + size > len(data):
        return None
    return data[offset:offset + size].hex()


def _normalize_target_fields(metadata: dict[str, Any], container: dict[str, Any]) -> dict[str, Any]:
    """Return the schema-required target fields, or raise (fail closed)."""
    problems: list[str] = []

    def pick(name: str) -> Any:
        value = metadata.get(name)
        if value is None and isinstance(container, dict):
            value = container.get(name)
        return value

    fmt = str(pick("format") or "")
    arch = str(pick("arch") or "")
    bits = pick("bits")
    endian = str(pick("endian") or "")
    if fmt not in TARGET_FORMATS:
        problems.append(f"format {fmt!r} is not one of {TARGET_FORMATS}")
    if arch not in TARGET_ARCHES:
        problems.append(f"arch {arch!r} is not one of {TARGET_ARCHES}")
    if isinstance(bits, bool) or bits not in TARGET_BITS:
        problems.append(f"bits {bits!r} is not one of {TARGET_BITS}")
    if endian not in TARGET_ENDIANS:
        problems.append(f"endian {endian!r} is not one of {TARGET_ENDIANS}")
    if problems:
        raise UnsupportedVerificationTarget("; ".join(problems))
    return {"format": fmt, "arch": arch, "bits": int(bits), "endian": endian}


def _normalize_target_scope(metadata: dict[str, Any]) -> dict[str, Any]:
    """Normalize the declared scope to {policy, name?, va?, end?} (schema-safe)."""
    raw = metadata.get("target_scope")
    if isinstance(raw, dict):
        policy = str(raw.get("policy") or "")
        kind = str(raw.get("kind") or "")
        if policy not in TARGET_POLICIES:
            if kind == "whole_program":
                policy = "whole_image" if metadata.get("allow_whole_image") is True else "analysis_only"
            elif kind in {"function", "vulnerability", "module"}:
                policy = "target_scoped"
            elif any(
                isinstance(raw.get(key), int) and not isinstance(raw.get(key), bool)
                for key in ("va", "start", "site_va", "file_offset", "offset")
            ):
                policy = "target_scoped"
            else:
                policy = "analysis_only"
        scope: dict[str, Any] = {"policy": policy}
        name = raw.get("name")
        if isinstance(name, str) and name:
            scope["name"] = name
        for key, target_key in (("va", "va"), ("start", "va"), ("site_va", "va"),
                                ("end", "end")):
            value = raw.get(key)
            if (target_key not in scope and isinstance(value, int)
                    and not isinstance(value, bool) and value >= 0):
                scope[target_key] = value
        return scope
    return {"policy": "analysis_only"}


def recompute_actions(original: bytes, candidate: bytes) -> list[dict[str, Any]]:
    """Derive contiguous byte-diff actions from the raw images (never trusted)."""
    if len(original) != len(candidate):
        return []
    actions: list[dict[str, Any]] = []
    index = 0
    length = len(original)
    while index < length:
        if original[index] == candidate[index]:
            index += 1
            continue
        start = index
        while index < length and original[index] != candidate[index]:
            index += 1
        size = index - start
        actions.append({
            "offset": start,
            "size": size,
            "before_hex": original[start:index].hex(),
            "after_hex": candidate[start:index].hex(),
        })
    return actions


def _normalize_claimed_actions(claimed: Iterable[Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate and normalize a claimed action list (offset/size/before/after)."""
    normalized: list[dict[str, Any]] = []
    problems: list[str] = []
    for index, action in enumerate(claimed):
        if not isinstance(action, dict):
            problems.append(f"claimed_actions[{index}] is not an object")
            continue
        offset = action.get("offset")
        size = action.get("size")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            problems.append(f"claimed_actions[{index}] has an invalid offset")
            continue
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            problems.append(f"claimed_actions[{index}] has an invalid size")
            continue
        before_hex = str(action.get("before_hex") or "").strip().lower()
        after_hex = str(action.get("after_hex") or "").strip().lower()
        try:
            bytes.fromhex(before_hex)
            bytes.fromhex(after_hex)
        except ValueError:
            problems.append(f"claimed_actions[{index}] has invalid before_hex/after_hex")
            continue
        if len(before_hex) != size * 2 or len(after_hex) != size * 2:
            problems.append(f"claimed_actions[{index}] hex length does not match size")
            continue
        normalized.append({
            "offset": offset,
            "size": size,
            "before_hex": before_hex,
            "after_hex": after_hex,
        })
    return normalized, problems


def _actions_equal(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    def key(action: dict[str, Any]) -> tuple[Any, ...]:
        return (int(action["offset"]), int(action["size"]),
                str(action["before_hex"]), str(action["after_hex"]))
    return sorted(left, key=key) == sorted(right, key=key)


def _default_detect(data: bytes) -> dict[str, Any]:
    """Read-only container probe; imports the parser lazily (never the gate)."""
    try:
        from app.services.binary_pipeline import detect_format
        from app.services.containers import detect_container
    except Exception as exc:  # pragma: no cover - import failure is environment
        return {"error": f"container parser unavailable: {type(exc).__name__}: {exc}"}
    try:
        fmt, arch, bits = detect_format(data)
        container = detect_container(data)
    except Exception as exc:  # noqa: BLE001 - parser failure is evidence
        return {"error": f"container parse failed: {type(exc).__name__}: {exc}"}
    sections = []
    try:
        for section in getattr(container, "sections", []) or []:
            sections.append({
                "name": str(getattr(section, "name", "")),
                "va": int(getattr(section, "va", 0) or 0),
                "size": int(getattr(section, "size", 0) or 0),
                "offset": int(getattr(section, "offset", 0) or 0),
                "executable": bool(getattr(section, "executable", False)),
            })
    except (TypeError, ValueError):
        sections = []
    return {
        "format": fmt,
        "arch": arch,
        "bits": bits,
        "endian": str(getattr(container, "endian", "little") or "little"),
        "sections": sections,
    }


def _default_abi_check(code: bytes, arch: str) -> dict[str, Any]:
    try:
        from app.services.repair.abi import check_block
    except Exception as exc:  # pragma: no cover - import failure is environment
        return {"ok": False, "unavailable": f"ABI checker unavailable: {type(exc).__name__}: {exc}",
                "fatal": 0, "findings": []}
    try:
        report = check_block(code, arch)
    except Exception as exc:  # noqa: BLE001 - checker failure is evidence
        return {"ok": False, "unavailable": f"ABI check failed: {type(exc).__name__}: {exc}",
                "fatal": 0, "findings": []}
    findings = []
    try:
        findings = [finding.to_dict() for finding in getattr(report, "findings", [])]
    except (AttributeError, TypeError):
        findings = []
    return {
        "ok": bool(getattr(report, "ok", False)),
        "fatal": len(getattr(report, "fatal", []) or []),
        "findings": findings,
    }


def _normalize_oracle_evidence(oracle: Any, *, original: bytes, candidate: bytes,
                               run_poc: Callable[..., Any] | None) -> tuple[dict[str, Any] | None, str, str]:
    """Return ``(evidence_dict, source, error)``; never invents an oracle result."""
    if oracle is None:
        return None, "none", "no independent oracle was supplied"
    if isinstance(oracle, (str, Path)):
        manifest: Any = str(oracle)
        source = "external-poc-manifest"
    elif isinstance(oracle, dict) and set(oracle) == {"manifest"}:
        manifest = oracle["manifest"]
        source = "external-poc-manifest"
    elif isinstance(oracle, dict) and ("status" in oracle or "poc" in oracle
                                       or "cases" in oracle or "regression" in oracle):
        return dict(oracle), "external-oracle-evidence", ""
    elif isinstance(oracle, dict):
        manifest = oracle
        source = "external-poc-manifest"
    else:
        return None, "invalid", f"unsupported oracle input type: {type(oracle).__name__}"
    if run_poc is None:
        return None, source, "no oracle runner is available"
    try:
        result = run_poc(original, candidate, manifest)
    except Exception as exc:  # noqa: BLE001 - runner failure is evidence
        return None, source, f"oracle runner failed: {type(exc).__name__}: {exc}"
    if hasattr(result, "to_dict"):
        evidence = result.to_dict()
    elif isinstance(result, dict):
        evidence = dict(result)
    else:
        return None, source, f"oracle runner returned unsupported type: {type(result).__name__}"
    return evidence, source, ""


def _check_container(checks: list[dict[str, Any]], metadata: dict[str, Any],
                     original: bytes, candidate: bytes,
                     detect: Callable[[bytes], dict[str, Any]]) -> dict[str, Any]:
    info_original = detect(original)
    info_candidate = detect(candidate)
    problems: list[str] = []
    for label, info in (("original", info_original), ("candidate", info_candidate)):
        if not isinstance(info, dict) or info.get("error"):
            problems.append(f"{label}: {info.get('error') if isinstance(info, dict) else 'no container info'}")
            continue
        fmt = str(info.get("format") or "unknown")
        arch = str(info.get("arch") or "unknown")
        if fmt == "unknown" or arch == "unknown":
            problems.append(f"{label}: container format/arch is unknown")
        for field in ("format", "arch", "bits", "endian"):
            expected = metadata.get(field)
            if expected is None:
                continue
            actual = info.get(field)
            if actual is None:
                problems.append(f"{label}: parser did not report {field} (expected {expected!r})")
            elif str(actual).lower() != str(expected).lower():
                problems.append(
                    f"{label}: parser {field}={actual!r} != metadata {expected!r}"
                )
    if isinstance(info_original, dict) and isinstance(info_candidate, dict):
        if not info_original.get("error") and not info_candidate.get("error"):
            for field in ("format", "arch", "bits", "endian"):
                if str(info_original.get(field)) != str(info_candidate.get(field)):
                    problems.append(
                        f"original/candidate container {field} differs "
                        f"({info_original.get(field)!r} != {info_candidate.get(field)!r})"
                    )
    evidence = {"original": info_original, "candidate": info_candidate}
    if problems:
        checks.append(_check("container", "failed", "; ".join(problems[:5])))
    else:
        checks.append(_check(
            "container", "passed",
            f"format={info_original.get('format')} arch={info_original.get('arch')} "
            f"bits={info_original.get('bits')} endian={info_original.get('endian')}",
        ))
    return evidence


def _offset_to_va(container: dict[str, Any], offset: int) -> int | None:
    for section in container.get("sections") or []:
        try:
            start = int(section.get("offset", 0))
            size = int(section.get("size", 0))
            va = int(section.get("va", 0))
        except (TypeError, ValueError):
            continue
        if start <= offset < start + max(size, 1):
            return va + (offset - start)
    return None


def _scope_range(scope: Any, metadata: dict[str, Any],
                 container: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Normalize a target scope to a file-offset or VA range; fail closed."""
    if not isinstance(scope, dict):
        return None, "no target_scope was declared; whole-image/verified claims are not allowed"
    kind = str(scope.get("kind") or scope.get("policy") or "unknown")
    if kind in {"whole_program", "whole_image"}:
        allowed = metadata.get("allow_whole_image") is True
        if not allowed:
            return None, ("whole_program scope requires the explicit allow_whole_image "
                          "opt-in; a whole-image claim is not allowed here")
        return {"kind": kind, "file_range": None, "va_range": None,
                "whole_program": True, "detail": "explicit whole-image opt-in"}, ""
    start = scope.get("va", scope.get("start", scope.get("site_va")))
    end = scope.get("end")
    size = scope.get("size")
    file_offset = scope.get("file_offset", scope.get("offset"))
    file_size = scope.get("byte_size", size)
    if isinstance(file_offset, int) and not isinstance(file_offset, bool) and file_offset >= 0:
        if isinstance(file_size, int) and not isinstance(file_size, bool) and file_size > 0:
            return {"kind": kind, "file_range": [file_offset, file_offset + file_size],
                    "va_range": None, "whole_program": False,
                    "detail": f"file offset range [{file_offset}, {file_offset + file_size})"}, ""
        return None, "file_offset scope requires a positive byte size"
    if isinstance(start, int) and not isinstance(start, bool) and start >= 0:
        if isinstance(end, int) and not isinstance(end, bool) and end > start:
            return {"kind": kind, "file_range": None, "va_range": [start, end],
                    "whole_program": False, "detail": f"VA range [{start:#x}, {end:#x})"}, ""
        if isinstance(size, int) and not isinstance(size, bool) and size > 0:
            return {"kind": kind, "file_range": None, "va_range": [start, start + size],
                    "whole_program": False,
                    "detail": f"VA range [{start:#x}, {start + size:#x})"}, ""
        if scope.get("site_va") is not None:
            return {"kind": kind, "file_range": None, "va_range": [start, start + 1],
                    "whole_program": False, "detail": f"VA site {start:#x}"}, ""
    return None, "target_scope has no usable range (va/end, va/size, file_offset/size)"


def _check_target_scope(checks: list[dict[str, Any]], metadata: dict[str, Any],
                        actions: list[dict[str, Any]], container: dict[str, Any],
                        claimed: list[dict[str, Any]]) -> dict[str, Any]:
    scope = metadata.get("target_scope")
    scope_range, error = _scope_range(scope, metadata, container)
    if error:
        checks.append(_check("target-scope", "not_run", error))
        return {"declared": scope, "range": None, "error": error}
    escaping: list[str] = []
    if scope_range is not None and not scope_range["whole_program"]:
        for action in actions:
            offset = int(action["offset"])
            size = int(action["size"])
            if scope_range.get("file_range"):
                start, end = scope_range["file_range"]
                if offset < start or offset + size > end:
                    escaping.append(f"action at file offset {offset} size {size} escapes [{start}, {end})")
                continue
            va_start, va_end = scope_range["va_range"]
            first_va = _offset_to_va(container, offset)
            last_va = _offset_to_va(container, offset + size - 1)
            if first_va is None or last_va is None:
                escaping.append(f"action at file offset {offset} cannot be mapped to a VA")
                continue
            if first_va < va_start or last_va >= va_end:
                escaping.append(
                    f"action at VA {first_va:#x}..{last_va:#x} escapes "
                    f"[{va_start:#x}, {va_end:#x})"
                )
        for index, action in enumerate(claimed):
            site_va = action.get("site_va")
            if isinstance(site_va, int) and not isinstance(site_va, bool) and scope_range.get("va_range"):
                va_start, va_end = scope_range["va_range"]
                if not (va_start <= site_va < va_end):
                    escaping.append(f"claimed_actions[{index}] site_va {site_va:#x} escapes scope")
    if escaping:
        checks.append(_check("target-scope", "failed", "; ".join(escaping[:5])))
    else:
        checks.append(_check("target-scope", "passed", str(scope_range.get("detail") or "scope holds")))
    return {"declared": scope, "range": scope_range}


def _check_abi(checks: list[dict[str, Any]], metadata: dict[str, Any],
               candidate: bytes, abi_check: Callable[[bytes, str], dict[str, Any]]) -> dict[str, Any]:
    block_spec = metadata.get("abi_block")
    if not isinstance(block_spec, dict):
        checks.append(_check("abi", "not_run", "no abi_block was declared; ABI is unverifiable"))
        return {}
    arch = str(metadata.get("arch") or "")
    offset = block_spec.get("offset", block_spec.get("file_offset"))
    size = block_spec.get("size", block_spec.get("byte_size"))
    if (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0
            or isinstance(size, bool) or not isinstance(size, int) or size <= 0):
        checks.append(_check("abi", "failed", "abi_block requires non-negative offset and positive size"))
        return {}
    block = _hex_at(candidate, offset, size)
    if block is None:
        checks.append(_check("abi", "failed", "abi_block is outside the candidate bytes"))
        return {}
    report = abi_check(bytes.fromhex(block), arch)
    if not isinstance(report, dict):
        checks.append(_check("abi", "not_run", "ABI checker returned no report"))
        return {}
    if report.get("unavailable"):
        checks.append(_check("abi", "not_run", str(report["unavailable"])))
        return report
    codes = {str(item.get("code") or "") for item in report.get("findings") or []}
    if codes & {"unsupported_arch", "abi_check_not_implemented"}:
        checks.append(_check(
            "abi", "not_run",
            f"ABI checks are not implemented for arch {arch!r}; explicit limitation recorded",
        ))
        return report
    if not report.get("ok") or int(report.get("fatal") or 0) > 0:
        detail = f"ABI report not ok (fatal={report.get('fatal')}); findings={sorted(codes)[:5]}"
        checks.append(_check("abi", "failed", detail))
        return report
    checks.append(_check("abi", "passed", f"block {offset}+{size} arch={arch!r} ABI ok"))
    return report


def _check_identity(checks: list[dict[str, Any]], metadata: dict[str, Any],
                    original: bytes, candidate: bytes) -> dict[str, Any]:
    original_sha = _sha256(original)
    candidate_sha = _sha256(candidate)
    problems: list[str] = []
    declared_original = metadata.get("original_sha256") or metadata.get("target_sha256")
    declared_target = metadata.get("target")
    if isinstance(declared_target, dict):
        declared_original = declared_original or declared_target.get("target_sha256")
    declared_candidate = metadata.get("candidate_sha256")
    if declared_original is not None and str(declared_original).lower() != original_sha:
        problems.append("metadata original/target sha256 does not match the original bytes")
    if declared_candidate is not None and str(declared_candidate).lower() != candidate_sha:
        problems.append("metadata candidate sha256 does not match the candidate bytes")
    if not original:
        problems.append("original bytes are empty")
    if not candidate:
        problems.append("candidate bytes are empty")
    if candidate == original:
        problems.append("candidate is byte-identical to the original (no repair applied)")
    if problems:
        checks.append(_check("identity", "failed", "; ".join(problems)))
    else:
        checks.append(_check("identity", "passed",
                             f"original={original_sha} candidate={candidate_sha}"))
    return {"original_sha256": original_sha, "candidate_sha256": candidate_sha}


def _check_action_replay(checks: list[dict[str, Any]], metadata: dict[str, Any],
                         original: bytes, candidate: bytes,
                         claimed_actions: Iterable[Any] | None) -> dict[str, Any]:
    if len(original) != len(candidate):
        checks.append(_check(
            "action-replay", "failed",
            f"length changed ({len(original)} -> {len(candidate)}); byte-replay verification "
            "covers rewrites only and cannot accept a resized candidate",
        ))
        return {"actions": [], "claimed_actions": []}
    recomputed = recompute_actions(original, candidate)
    claimed_raw = claimed_actions if claimed_actions is not None else metadata.get("claimed_actions")
    claimed: list[dict[str, Any]] = []
    problems: list[str] = []
    if claimed_raw is not None:
        if not isinstance(claimed_raw, list):
            problems.append("claimed_actions must be a list when present")
        else:
            claimed, normalize_problems = _normalize_claimed_actions(claimed_raw)
            problems.extend(normalize_problems)
            if not normalize_problems and not _actions_equal(claimed, recomputed):
                problems.append(
                    "claimed actions do not match the byte diffs recomputed from the raw images"
                )
    if not recomputed:
        problems.append("no byte difference was found between original and candidate")
    if problems:
        checks.append(_check("action-replay", "failed", "; ".join(problems[:5])))
    else:
        checks.append(_check(
            "action-replay", "passed",
            f"actions={len(recomputed)} offsets="
            + ",".join(hex(int(action["offset"])) for action in recomputed[:8]),
        ))
    return {"actions": recomputed, "claimed_actions": claimed}


def _check_oracle(checks: list[dict[str, Any]], evidence: dict[str, Any] | None,
                  source: str, error: str, metadata: dict[str, Any],
                  original_sha: str, candidate_sha: str) -> dict[str, Any]:
    if evidence is None:
        checks.append(_check("runtime-oracle", "not_run", error or "no independent oracle result"))
        return {"source": source, "error": error}
    status = str(evidence.get("status") or "not_run")
    problems: list[str] = []
    declared_original = evidence.get("original_sha256")
    declared_candidate = evidence.get("candidate_sha256")
    if declared_original and str(declared_original) != original_sha:
        problems.append("oracle evidence original sha256 does not match the original bytes")
    if declared_candidate and str(declared_candidate) != candidate_sha:
        problems.append("oracle evidence candidate sha256 does not match the candidate bytes")
    expected_signature = metadata.get("expected_stdout_signature")
    signature = str(evidence.get("stdout_signature") or "")
    if expected_signature is not None and signature and signature != str(expected_signature):
        problems.append(f"oracle stdout_signature={signature!r} != expected {expected_signature!r}")
    if signature == "mismatch":
        problems.append("oracle reported a regression stdout mismatch")
    summary = {
        "source": source,
        "status": status,
        "runner": evidence.get("runner"),
        "tier": evidence.get("tier"),
        "stdout_signature": evidence.get("stdout_signature"),
        "errno_signature": evidence.get("errno_signature"),
        "no_input": evidence.get("no_input"),
        "case_count": len(evidence.get("poc") or evidence.get("cases") or []),
        "regression_count": len(evidence.get("regression") or []),
        "limitations": list(evidence.get("limitations") or []),
    }
    if problems:
        checks.append(_check("runtime-oracle", "failed", "; ".join(problems[:5]),
                             independent=True))
    elif status == "pass":
        checks.append(_check(
            "runtime-oracle", "passed", independent=True,
            detail=f"independent oracle passed (runner={summary['runner'] or 'unknown'} "
            f"tier={summary['tier'] or 'unknown'} cases={summary['case_count']})",
        ))
    elif status in {"unavailable", "not_run"}:
        checks.append(_check(
            "runtime-oracle", "not_run", independent=True,
            detail=f"oracle status={status}; not executed: "
            + "; ".join(summary["limitations"][:2] or ["no reason reported"]),
        ))
    elif status == "inconclusive":
        checks.append(_check(
            "runtime-oracle", "not_run", independent=True,
            detail="oracle evidence is inconclusive: " + "; ".join(summary["limitations"][:2] or []),
        ))
    else:
        checks.append(_check(
            "runtime-oracle", "failed", independent=True,
            detail=f"oracle status={status}: " + "; ".join(summary["limitations"][:2] or ["no reason reported"]),
        ))
    return summary


def _sanitize_generator(raw: Any) -> tuple[dict[str, Any], list[str]]:
    """Return only identity fields; generator verdicts are never read."""
    problems: list[str] = []
    if raw is None:
        return ({"generator_id": UNDECLARED_GENERATOR},
                ["generator metadata is not declared; independence cannot be established"])
    if not isinstance(raw, dict):
        return ({"generator_id": UNDECLARED_GENERATOR},
                ["generator metadata must be an object"])
    generator_id = str(raw.get("generator_id") or raw.get("agent") or "").strip()
    if not generator_id:
        generator_id = UNDECLARED_GENERATOR
        problems.append("generator_id is missing; independence cannot be established")
    sanitized = {"generator_id": generator_id}
    for key in ("agent", "model", "run_id"):
        value = raw.get(key)
        if value is None or isinstance(value, str):
            sanitized[key] = value
    return sanitized, problems


def _check_independence(checks: list[dict[str, Any]], generator: dict[str, Any],
                        generator_problems: list[str], oracle_present: bool,
                        raw_generator_verdict_present: bool) -> dict[str, Any]:
    problems = list(generator_problems)
    if generator.get("generator_id") and generator["generator_id"] == VERIFIER_ID:
        problems.append(f"generator_id equals the verifier id {VERIFIER_ID!r}")
    if not oracle_present:
        problems.append("no independent oracle evidence: generator/reference self-report alone is insufficient")
    detail = ("; ".join(problems) if problems else
              "generator identity is distinct and its evidence is excluded from the decision")
    result = {"ok": not problems, "generator_evidence_excluded": True}
    if raw_generator_verdict_present:
        detail += "; generator verdict keys were present and ignored"
    if problems:
        checks.append(_check("independence", "failed", detail))
    else:
        checks.append(_check("independence", "passed", detail))
    return result


def _check_evidence(checks: list[dict[str, Any]], oracle: Any,
                    oracle_summary: dict[str, Any], runtime_status: str,
                    generator_only: bool) -> dict[str, Any]:
    problems: list[str] = []
    if oracle is None:
        problems.append("no independent oracle was supplied; generator/reference evidence only")
    if generator_only and oracle is None:
        problems.append("the only evidence is generator self-report/reference fix")
    if runtime_status == "passed":
        detail = "one independent external oracle passed"
        checks.append(_check("evidence-completeness", "passed", detail, independent=True))
        return {"ok": True, "detail": detail, "sources": [oracle_summary.get("source")]}
    if runtime_status == "not_run" and oracle is not None:
        detail = "independent oracle declared but not executed (unavailable/inconclusive); evidence incomplete"
        checks.append(_check("evidence-completeness", "not_run", detail, independent=True))
        return {"ok": False, "detail": detail, "sources": [oracle_summary.get("source")]}
    if problems:
        checks.append(_check("evidence-completeness", "failed", "; ".join(problems),
                             independent=True))
    else:
        checks.append(_check("evidence-completeness", "failed",
                             "the independent oracle did not produce passing evidence",
                             independent=True))
    return {"ok": False, "detail": "; ".join(problems) or "no passing independent evidence",
            "sources": [oracle_summary.get("source")] if oracle_summary else []}


def verify_repair(
    *,
    original: bytes,
    candidate: bytes,
    metadata: dict[str, Any],
    oracle: Any = None,
    generator: dict[str, Any] | None = None,
    claimed_actions: Iterable[Any] | None = None,
    detect: Callable[[bytes], dict[str, Any]] | None = None,
    abi_check: Callable[[bytes, str], dict[str, Any]] | None = None,
    run_poc: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Independently verify one repair candidate; never trusts a generator verdict."""
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(original, (bytes, bytearray)) or not isinstance(candidate, (bytes, bytearray)):
        raise TypeError("original and candidate must be bytes")
    original_bytes = bytes(original)
    candidate_bytes = bytes(candidate)
    detect_fn = detect or _default_detect
    abi_fn = abi_check or _default_abi_check

    checks: list[dict[str, Any]] = []
    identity = _check_identity(checks, metadata, original_bytes, candidate_bytes)
    container = _check_container(checks, metadata, original_bytes, candidate_bytes, detect_fn)
    replay = _check_action_replay(checks, metadata, original_bytes, candidate_bytes, claimed_actions)
    scope = _check_target_scope(checks, metadata, replay["actions"],
                                container.get("candidate") or {}, replay["claimed_actions"])
    abi = _check_abi(checks, metadata, candidate_bytes, abi_fn)

    raw_generator = generator if generator is not None else metadata.get("generator")
    sanitized_generator, generator_problems = _sanitize_generator(raw_generator)
    verdict_keys = {"verified", "decision", "verdict", "state", "result"}
    raw_generator_verdict_present = bool(
        isinstance(raw_generator, dict) and (set(raw_generator) & verdict_keys)
    )
    oracle_evidence, oracle_source, oracle_error = _normalize_oracle_evidence(
        oracle, original=original_bytes, candidate=candidate_bytes, run_poc=run_poc,
    )
    oracle_summary = _check_oracle(
        checks, oracle_evidence, oracle_source, oracle_error, metadata,
        identity["original_sha256"], identity["candidate_sha256"],
    )
    runtime_status = next(
        check["status"] for check in checks if check["id"] == "runtime-oracle"
    )
    evidence = _check_evidence(
        checks, oracle, oracle_summary, runtime_status,
        generator_only=bool(raw_generator and oracle is None),
    )
    independence = _check_independence(
        checks, sanitized_generator, generator_problems,
        oracle_present=oracle is not None,
        raw_generator_verdict_present=raw_generator_verdict_present,
    )

    failed = [check for check in checks if check["required"] and check["status"] == "failed"]
    not_run = [check for check in checks if check["required"] and check["status"] == "not_run"]
    decision = "rejected" if failed else ("not_run" if not_run else "verified")
    if oracle_summary.get("status") == "inconclusive" and not failed:
        decision = "inconclusive"

    independent_passed = [
        check for check in checks if check.get("independent") is True and check["status"] == "passed"
    ]
    if decision == "verified" and not (independence["ok"] and independent_passed):
        decision = "rejected"

    limitations: list[str] = []
    if decision != "verified":
        limitations.append(
            "fail-closed: only an all-required-passed result with a passing independent "
            "oracle can be verified"
        )
    limitations.extend(str(item) for item in oracle_summary.get("limitations") or [])
    for check in checks:
        if check["status"] == "not_run":
            limitations.append(f"{check['id']}: {check['detail']}")
    if decision == "rejected" and not failed and not independence["ok"]:
        limitations.append("independence requirement was not satisfied")
    limitations = sorted({item for item in limitations if isinstance(item, str) and item})

    container_candidate = container.get("candidate") if isinstance(container, dict) else {}
    target_fields = _normalize_target_fields(metadata, container_candidate or {})
    target = {
        **target_fields,
        "target_sha256": identity["original_sha256"],
        "target_scope": _normalize_target_scope(metadata),
    }
    evidence_list: list[Any] = [
        {"kind": "candidate", "original_sha256": identity["original_sha256"],
         "candidate_sha256": identity["candidate_sha256"]},
        {"kind": "container", "original": container.get("original"),
         "candidate": container.get("candidate")},
        {"kind": "actions", "actions": replay["actions"],
         "claimed_actions": replay["claimed_actions"]},
        {"kind": "target-scope", "declared": scope.get("declared"),
         "range": scope.get("range")},
        {"kind": "abi", "report": abi},
        {"kind": "oracle", **oracle_summary},
        {"kind": "evidence-completeness", **evidence},
    ]
    if isinstance(oracle, (str, Path)):
        evidence_list.append(str(oracle))

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "target": target,
        "generator": sanitized_generator,
        "verifier": {"verifier_id": VERIFIER_ID, "version": str(SCHEMA_VERSION)},
        "independence": independence,
        "checks": checks,
        "decision": decision,
        "evidence": evidence_list,
        "limitations": limitations,
    }
    report["report_sha256"] = _sha256(_canonical(report).encode("ascii"))
    return report


VERIFICATION_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "verification.schema.json"


def validate_verification_report(report: dict[str, Any]) -> dict[str, Any]:
    """Validate a report against contracts/verification.schema.json.

    Uses jsonschema when installed and a small fail-closed fallback otherwise.
    Also re-computes report_sha256 so a tampered report is detected.
    """
    violations: list[str] = []
    method = "fallback"
    payload = dict(report)
    declared_sha = payload.pop("report_sha256", None)
    recomputed = _sha256(_canonical(payload).encode("ascii"))
    if declared_sha != recomputed:
        violations.append("report_sha256 does not match the canonical report content")
    try:
        import jsonschema
    except ImportError:
        jsonschema = None  # type: ignore[assignment]
    if jsonschema is not None:
        try:
            schema = json.loads(VERIFICATION_SCHEMA_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"verification schema unavailable: {type(exc).__name__}: {exc}")
        else:
            method = "jsonschema"
            validator = jsonschema.Draft202012Validator(schema)
            for error in sorted(validator.iter_errors(report), key=lambda item: list(item.path)):
                violations.append(f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}")
    else:
        required = ("schema_version", "target", "generator", "verifier",
                    "independence", "checks", "decision", "evidence",
                    "limitations", "report_sha256")
        for key in required:
            if key not in report:
                violations.append(f"missing required field {key!r}")
        if report.get("schema_version") != 1:
            violations.append("schema_version must be 1")
        if report.get("decision") not in DECISIONS:
            violations.append("decision is not in the allowed enum")
        if not isinstance(report.get("evidence"), list):
            violations.append("evidence must be an array")
        checks = report.get("checks")
        if not isinstance(checks, list) or not checks:
            violations.append("checks must be a non-empty array")
        else:
            for item in checks:
                if not isinstance(item, dict) or not {"id", "title", "status", "required", "detail"} <= set(item):
                    violations.append("a check is missing schema-required fields")
                    break
                if item.get("status") not in CHECK_STATUSES:
                    violations.append(f"check {item.get('id')!r} has an invalid status")
                    break
    if report.get("decision") == "verified":
        independence = report.get("independence") or {}
        if independence.get("ok") is not True:
            violations.append("verified requires independence.ok=true")
        if independence.get("generator_evidence_excluded") is not True:
            violations.append("verified requires generator_evidence_excluded=true")
        independent_passed = [
            item for item in report.get("checks") or []
            if isinstance(item, dict) and item.get("independent") is True
            and item.get("status") == "passed"
        ]
        if not independent_passed:
            violations.append("verified requires at least one passed independent check")
        for item in report.get("checks") or []:
            if (isinstance(item, dict) and item.get("required") is True
                    and item.get("status") != "passed"):
                violations.append("verified requires every required check to pass")
                break
    return {"ok": not violations, "method": method, "violations": violations}


__all__ = [
    "SCHEMA_VERSION",
    "VERIFIER_ID",
    "CHECK_ORDER",
    "DECISIONS",
    "recompute_actions",
    "verify_repair",
    "validate_verification_report",
    "UnsupportedVerificationTarget",
]
