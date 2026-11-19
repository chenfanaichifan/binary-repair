"""Host-side evidence validation for Route A result bundles (P0 trust boundary).

The host never executes the candidate, and P0 forbids running the producer's
patch tool on the host.  This module is the single place where a Route A guest
bundle is turned into gate results:

* V0 identity and V1 structure are recomputed from bytes on disk;
* V2 is recomputed by the product's own five-check static interface check;
* V3 is a guest observation and only gets structural validation here (the host
  cannot replay a binary);
* V4 must be a complete typed model-level marker with the independent-replay
  field, bound to this candidate, original and contract;
* V5 must be a complete reproducibility envelope; the patch replay itself stays
  a guest/replayer activity, and no host code executes the patch tool.

Every finding carries a reason prefix so a reviewer can tell the states apart:

``missing:``       required evidence is absent.
``invalid:``       evidence exists but cannot be trusted or does not bind this
                   candidate/original/contract.
``check_failed:``  a real check ran and failed (a definite failure).
``inconclusive:``  the host could not evaluate the check (tool/env gap).
``guest_observed:`` a guest-produced observation accepted after structural
                   validation only; it is never described as host-replayed.

A ``passed`` result is only ever produced by this module when the corresponding
rule below is satisfied.  Missing or invalid evidence stays ``not_run``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

GATES: tuple[str, ...] = ("V0", "V1", "V2", "V3", "V4", "V5")
INPUT_MODES = {"argv", "stdin", "none"}
RECORD_KIND = "route_a_verification"
RECORD_SCHEMA_VERSION = 1

#: Reason prefixes; a test asserts every detail starts with one of these.
REASON_PREFIXES = (
    "host_verified:",
    "missing:",
    "invalid:",
    "check_failed:",
    "inconclusive:",
    "guest_observed:",
)


class RouteAEvidenceError(ValueError):
    """The bundle itself is unusable (no candidate, unreadable directory)."""


@dataclass(frozen=True)
class GateFinding:
    gate: str
    status: str
    detail: str
    sources: tuple[dict[str, str], ...] = field(default_factory=tuple)
    checks: dict[str, Any] = field(default_factory=dict)
    generated: dict[str, Any] | None = None
    generated_name: str | None = None
    raw_source: str | None = None

    def as_record(
        self,
        *,
        source_artifacts: list[dict[str, str]],
        candidate_sha256: str,
        original_sha256: str,
        contract_canonical_sha256: str,
    ) -> dict[str, Any]:
        """The host-written record registered as this gate's evidence artifact."""
        return {
            "schema_version": RECORD_SCHEMA_VERSION,
            "record_kind": RECORD_KIND,
            "gate": self.gate,
            "status": self.status,
            "detail": self.detail,
            "candidate_sha256": candidate_sha256,
            "original_sha256": original_sha256,
            "contract_canonical_sha256": contract_canonical_sha256,
            "source_artifacts": source_artifacts,
            "checks": dict(self.checks),
            "validated_by": "host",
            "validator": "app.domain.route_a_evidence/v1",
        }


@dataclass(frozen=True)
class RouteAValidation:
    candidate_sha256: str
    candidate_size: int
    original_sha256: str
    contract_canonical_sha256: str
    contract_file_sha256: str | None
    findings: dict[str, GateFinding]
    bundle_claims: dict[str, str]

    @property
    def results(self) -> dict[str, str]:
        return {gate: self.findings[gate].status for gate in GATES}

    @property
    def details(self) -> dict[str, str]:
        return {gate: self.findings[gate].detail for gate in GATES}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _product_contract_hash(payload: Mapping[str, Any]) -> str:
    """The reviewed-contract hash rule, shared with the product.

    ``_canonical_hash`` is a plain JSON-dumps digest and is only correct for the
    manifest-set envelope. A reviewed contract is hashed with
    ``app.domain.contracts.contract_sha256`` (the same rule the guest worker and
    collector use), so the bundle contract check must use that rule too; the two
    digests differ for a contract that is not already normalised.
    """

    from app.domain.contracts import contract_sha256

    return contract_sha256(dict(payload))


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"file not found: {path.name}"
    except (OSError, ValueError) as exc:
        return None, f"cannot read {path.name}: {exc}"
    if not isinstance(data, dict):
        return None, f"{path.name} is not a JSON object"
    return data, None


def _finding(
    gate: str,
    status: str,
    detail: str,
    *,
    sources: tuple[dict[str, str], ...] = (),
    checks: dict[str, Any] | None = None,
    generated: dict[str, Any] | None = None,
    generated_name: str | None = None,
    raw_source: str | None = None,
) -> GateFinding:
    if not status.startswith(("passed", "failed", "not_run")):
        raise ValueError(f"invalid gate status: {status!r}")
    if status == "passed" and not detail.startswith(("host_verified:", "guest_observed:")):
        detail = f"host_verified: {detail}"
    return GateFinding(
        gate=gate,
        status=status,
        detail=detail,
        sources=sources,
        checks=checks or {},
        generated=generated,
        generated_name=generated_name,
        raw_source=raw_source,
    )


def _missing(gate: str, what: str) -> GateFinding:
    return _finding(gate, "not_run", f"missing: {what}")


def _invalid(gate: str, why: str) -> GateFinding:
    return _finding(gate, "not_run", f"invalid: {why}")


def _inconclusive(gate: str, why: str) -> GateFinding:
    return _finding(gate, "not_run", f"inconclusive: {why}")


def _check_failed(gate: str, why: str, **kwargs: Any) -> GateFinding:
    return _finding(gate, "failed", f"check_failed: {why}", **kwargs)


def _source(bundle: Path, relative: str) -> dict[str, str] | None:
    path = bundle / relative
    if not path.is_file():
        return None
    return {"path": relative.replace("\\", "/"), "sha256": _sha256_file(path)}


def _manifest_set_sha256(tests_dir: Path, input_mode: str) -> tuple[str | None, str | None]:
    """Recompute the worker's manifest-set hash (file hashes, canonical JSON)."""

    valid_path = tests_dir / "valid.json"
    valid, error = _read_json(valid_path)
    if valid is None:
        return None, error
    manifests: list[dict[str, str]] = []
    if input_mode != "none":
        invalid_path = tests_dir / "invalid.json"
        invalid, error = _read_json(invalid_path)
        if invalid is None:
            return None, error
        if valid.get("case_id") != invalid.get("case_id"):
            return None, "valid/invalid manifests disagree on case_id"
        if valid.get("original_sha256") != invalid.get("original_sha256"):
            return None, "valid/invalid manifests disagree on original_sha256"
        manifests.append({"name": "invalid.json", "sha256": _sha256_file(invalid_path)})
    manifests.append({"name": "valid.json", "sha256": _sha256_file(valid_path)})
    payload = {
        "schema_version": 1,
        "case_id": valid.get("case_id"),
        "original_sha256": valid.get("original_sha256"),
        "manifests": manifests,
    }
    return _canonical_hash(payload), None


def _load_claims(bundle: Path) -> dict[str, str]:
    bundle_json, error = _read_json(bundle / "bundle.json")
    if error is not None or bundle_json is None:
        return {}
    gates = bundle_json.get("gates")
    if not isinstance(gates, dict):
        return {}
    claims: dict[str, str] = {}
    for gate in GATES:
        entry = gates.get(gate)
        if isinstance(entry, dict) and isinstance(entry.get("status"), str):
            claims[gate] = str(entry["status"]).lower()
    return claims


def _with_claims(finding: GateFinding, claims: Mapping[str, str]) -> GateFinding:
    claimed = claims.get(finding.gate)
    if claimed is None:
        return finding
    host = finding.status
    if claimed in {"passed", "failed", "not_run"} and claimed != host:
        return GateFinding(
            gate=finding.gate,
            status=finding.status,
            detail=f"{finding.detail}; bundle claimed {claimed}, host recomputed {host}",
            sources=finding.sources,
            checks=finding.checks,
            generated=finding.generated,
            generated_name=finding.generated_name,
            raw_source=finding.raw_source,
        )
    return finding


def _check_v0(
    bundle: Path,
    *,
    candidate_sha256: str,
    original_sha256: str,
    contract_canonical_sha256: str,
    contract_file_sha256: str | None,
    input_mode: str,
) -> GateFinding:
    """V0 identity: candidate bytes, original bytes and the contract are bound."""

    status_path = bundle / "route_a" / "status.json"
    status, error = _read_json(status_path)
    if status is None:
        return _missing("V0", f"route_a/status.json ({error})")

    checks: dict[str, Any] = {"candidate_sha256": candidate_sha256}
    failures: list[str] = []
    sources = [source for source in (_source(bundle, "route_a/candidate.elf"),
                                     _source(bundle, "route_a/status.json")) if source]

    bundle_json, bundle_error = _read_json(bundle / "bundle.json")
    if bundle_error is None and bundle_json is not None:
        identity = bundle_json.get("identity") or {}
        declared = identity.get("candidate_sha256") if isinstance(identity, dict) else None
        if isinstance(declared, str) and declared != candidate_sha256:
            failures.append(f"bundle identity candidate {declared} != candidate bytes {candidate_sha256}")

    bundle_original = _source(bundle, "original.elf")
    if bundle_original is not None:
        sources.append(bundle_original)
        if bundle_original["sha256"] != original_sha256:
            failures.append("bundle original.elf does not hash to the job original")
    bundle_contract = _source(bundle, "contract.json")
    if bundle_contract is not None:
        sources.append(bundle_contract)
        contract, error = _read_json(bundle / "contract.json")
        if contract is None:
            failures.append(f"bundle contract.json unusable: {error}")
        else:
            if _product_contract_hash(contract) != contract_canonical_sha256:
                failures.append("bundle contract.json canonical hash differs from the reviewed contract")
            if contract_file_sha256 is not None and bundle_contract["sha256"] != contract_file_sha256:
                failures.append("bundle contract.json bytes differ from the reviewed contract file")
    elif contract_file_sha256 is not None:
        failures.append("bundle has no contract.json")

    declared_candidate = (status.get("candidate") or {}).get("sha256") if isinstance(status.get("candidate"), dict) else None
    if declared_candidate != candidate_sha256:
        failures.append(f"status.candidate.sha256 {declared_candidate!r} != candidate bytes {candidate_sha256}")
    if status.get("contract_sha256") != contract_canonical_sha256:
        failures.append("status.contract_sha256 != reviewed contract canonical hash")
    if status.get("original_sha256") != original_sha256:
        failures.append("status.original_sha256 != job original hash")
    checks["status_contract_sha256"] = status.get("contract_sha256")

    set_hash, error = _manifest_set_sha256(bundle / "tests", input_mode)
    if set_hash is None:
        failures.append(f"cannot recompute manifest set: {error}")
    elif status.get("manifest_set_sha256") != set_hash:
        failures.append("status.manifest_set_sha256 != recomputed manifest set hash")
    else:
        checks["manifest_set_sha256"] = set_hash

    if failures:
        return _check_failed("V0", "; ".join(failures), sources=tuple(sources), checks=checks)
    detail = f"candidate {candidate_sha256} bound to job original {original_sha256}"
    return _finding("V0", "passed", detail, sources=tuple(sources), checks=checks,
                    raw_source="route_a/candidate.elf")


def _check_v1(bundle: Path) -> GateFinding:
    """V1 structure: required static artifacts exist and bind this candidate."""

    required = {
        "route_a/audit.json": True,
        "route_a/edit-manifest.json": True,
        "route_a/readelf-audit.txt": False,
        "evidence/v1/lief.json": False,
    }
    sources: list[dict[str, str]] = []
    missing: list[str] = []
    for relative, _ in required.items():
        source = _source(bundle, relative)
        if source is None:
            missing.append(relative)
        else:
            sources.append(source)
    if missing:
        return _missing("V1", "static structure artifacts: " + ", ".join(missing))

    audit, error = _read_json(bundle / "route_a" / "audit.json")
    if audit is None:
        return _invalid("V1", f"audit.json unusable: {error}")
    if audit.get("pass") is not True:
        return _check_failed("V1", "audit.json pass is not true", sources=tuple(sources))

    manifest, error = _read_json(bundle / "route_a" / "edit-manifest.json")
    if manifest is None:
        return _invalid("V1", f"edit-manifest.json unusable: {error}")
    checks = {
        "audit_pass": True,
        "edit_manifest_original": manifest.get("original_sha256"),
        "edit_manifest_candidate": manifest.get("candidate_sha256"),
        "readelf_present": True,
        "lief_present": True,
    }
    candidate = _source(bundle, "route_a/candidate.elf")
    original = _source(bundle, "original.elf")
    if candidate is None or original is None:
        return _invalid("V1", "candidate.elf or original.elf missing for the manifest binding")
    if manifest.get("candidate_sha256") != candidate["sha256"]:
        return _check_failed("V1", "edit-manifest.json candidate hash != candidate.elf", sources=tuple(sources))
    if manifest.get("original_sha256") != original["sha256"]:
        return _check_failed("V1", "edit-manifest.json original hash != original.elf", sources=tuple(sources))
    detail = "static audit passed; manifest binds candidate and original"
    return _finding("V1", "passed", detail, sources=tuple(sources), checks=checks)


def _check_v2(
    bundle: Path,
    *,
    original_elf: Path,
    candidate_elf: Path,
    contract_body: Mapping[str, Any],
) -> GateFinding:
    """V2 interface: the host recomputes the five product checks itself."""

    target_entry = str(contract_body.get("target_entry") or "").strip()
    if not target_entry:
        return _invalid("V2", "contract has no target_entry")
    try:
        from app.domain.interface import check_interface
    except Exception as exc:  # noqa: BLE001 - absent tool is not a pass
        return _inconclusive("V2", f"interface checker unavailable: {exc}")
    try:
        report = check_interface(original_elf, candidate_elf, target_entry)
    except Exception as exc:  # noqa: BLE001 - fail closed, report why
        return _inconclusive("V2", f"interface check could not run: {exc}")
    checks = {
        "target_entry": target_entry,
        "checks": report.get("checks"),
        "score": report.get("score"),
    }
    if report.get("pass") is not True:
        failed = [name for name, value in (report.get("checks") or {}).items() if value is not True]
        return _check_failed(
            "V2",
            f"interface checks failed: {report.get('score')}; failed: {', '.join(failed) or 'unknown'}",
            checks=checks,
        )
    return _finding(
        "V2",
        "passed",
        "host recomputed 5/5 static interface checks",
        checks=checks,
        generated=report,
        generated_name="v2-interface-scored.json",
    )


def _check_v3(bundle: Path, *, candidate_sha256: str, input_mode: str) -> GateFinding:
    """V3 behaviour: guest observation, host structural validation only."""

    formal_rel = "evidence/v3/formal-run.json"
    repaired_rel = "evidence/v3/manifest-repaired.json"
    formal = _source(bundle, formal_rel)
    if formal is not None:
        payload, error = _read_json(bundle / formal_rel)
        if payload is None:
            return _invalid("V3", f"formal-run.json unusable: {error}")
        if payload.get("candidate_sha256_before") != candidate_sha256 or payload.get("candidate_sha256_after") != candidate_sha256:
            return _invalid("V3", "formal-run.json does not bind this candidate")
        if payload.get("reverted") is not True:
            return _invalid("V3", "formal-run.json is not a reverted-snapshot run")
        cases = payload.get("cases") or []
        if not isinstance(cases, list) or len(cases) != 6:
            return _invalid("V3", "formal-run.json does not contain six cases")
        if not all(isinstance(case, dict) and case.get("ok") is True for case in cases):
            return _check_failed("V3", "formal-run.json has a failed case", sources=(formal,))
        return _finding(
            "V3", "passed",
            "guest_observed: formal 6/6 run on a reverted snapshot; host did not replay",
            sources=(formal,),
            checks={"reverted": True, "cases": 6, "guest_observed": True},
            raw_source=formal_rel,
        )

    repaired = _source(bundle, repaired_rel)
    if repaired is None:
        return _missing("V3", f"{repaired_rel} or {formal_rel}")
    payload, error = _read_json(bundle / repaired_rel)
    if payload is None:
        return _invalid("V3", f"manifest-repaired.json unusable: {error}")
    if payload.get("candidate_sha256") != candidate_sha256:
        return _invalid("V3", "manifest-repaired.json does not bind this candidate")
    if payload.get("input_mode") != input_mode:
        return _invalid("V3", "manifest-repaired.json input_mode differs from the contract")
    total = payload.get("total")
    passed = payload.get("passed")
    cases = payload.get("cases") or []
    checks = {
        "repaired_pass": payload.get("repaired_pass"),
        "passed": passed,
        "total": total,
        "input_mode": payload.get("input_mode"),
        "guest_observed": True,
    }
    if not isinstance(total, int) or not isinstance(passed, int) or len(cases) != total:
        return _invalid("V3", "manifest-repaired.json has inconsistent passed/total/cases")
    if total < 1:
        return _invalid("V3", "manifest-repaired.json executes no case")
    if input_mode == "none" and total != 1:
        return _invalid("V3", "no-input behaviour must be a single case")
    if payload.get("repaired_pass") is not True or passed != total:
        return _check_failed("V3", f"guest observed {passed}/{total} behaviour cases", sources=(repaired,))
    if not all(isinstance(case, dict) and case.get("ok") is True for case in cases):
        return _invalid("V3", "manifest-repaired.json cases disagree with repaired_pass")
    return _finding(
        "V3", "passed",
        f"guest_observed: {passed}/{total} behaviour cases; host did not replay",
        sources=(repaired,),
        checks=checks,
        raw_source=repaired_rel,
    )


def _check_v4(
    bundle: Path,
    *,
    candidate_sha256: str,
    original_sha256: str,
    contract_canonical_sha256: str,
    contract_file_sha256: str | None,
) -> GateFinding:
    """V4 symbolic: typed model-level marker validated by the product schema."""

    for relative in ("v4-symbolic.json", "evidence/v4/symbolic.json"):
        source = _source(bundle, relative)
        if source is None:
            continue
        payload, error = _read_json(bundle / relative)
        if payload is None:
            return _invalid("V4", f"{relative} unusable: {error}")
        try:
            from app.domain.v4 import V4EvidenceError, validate_v4_evidence
        except Exception as exc:  # noqa: BLE001 - absent validator is not a pass
            return _inconclusive("V4", f"V4 validator unavailable: {exc}")
        try:
            evidence = validate_v4_evidence(
                payload,
                candidate_sha256=candidate_sha256,
                original_sha256=original_sha256,
                require_independent=True,
            )
        except V4EvidenceError as exc:
            return _invalid("V4", f"typed V4 evidence rejected: {exc}")
        marker_contract = None
        source_section = payload.get("source")
        if isinstance(source_section, dict):
            marker_contract = source_section.get("contract_sha256")
        if marker_contract is None:
            marker_contract = payload.get("contract_sha256")
        accepted = {value for value in (contract_canonical_sha256, contract_file_sha256) if value}
        if not isinstance(marker_contract, str) or marker_contract not in accepted:
            return _invalid("V4", "V4 evidence does not bind the reviewed contract")
        checks = {
            "scope": "model",
            "replay_runs": evidence.replay.runs,
            "replay_identical": evidence.replay.identical,
            "verified_by": evidence.replay.verified_by,
            "contract_sha256": marker_contract,
        }
        return _finding(
            "V4", "passed",
            "typed model-level V4 marker bound to this candidate and contract; not a binary proof",
            sources=(source,),
            checks=checks,
            raw_source=relative,
        )
    return _missing("V4", "v4-symbolic.json or evidence/v4/symbolic.json")


def _check_v5(
    bundle: Path,
    *,
    candidate_sha256: str,
    original_sha256: str,
) -> GateFinding:
    """V5 reproducibility: structural validation of the replay envelope.

    The replay itself is a guest/replayer activity (P0 forbids running the patch
    tool on the host), so this function never executes anything.
    """

    relative = "evidence/v5/replay.json"
    source = _source(bundle, relative)
    if source is None:
        return _missing("V5", relative)
    payload, error = _read_json(bundle / relative)
    if payload is None:
        return _invalid("V5", f"replay.json unusable: {error}")
    if payload.get("candidate_sha256") != candidate_sha256:
        return _invalid("V5", "replay.json does not bind this candidate")
    required = ("independent_replay", "original_sha256", "patch_tool_sha256", "runs",
                "sha256", "byte_identical", "matches_candidate", "replayed_by", "method")
    missing = [name for name in required if name not in payload]
    if missing:
        return _invalid("V5", "replay.json is missing " + ", ".join(missing))
    if payload.get("independent_replay") is not True:
        return _invalid("V5", "replay.json does not assert an independent replay")
    if payload.get("original_sha256") != original_sha256:
        return _invalid("V5", "replay.json original hash != job original")
    patch_tool = payload.get("patch_tool_sha256")
    if not isinstance(patch_tool, str) or len(patch_tool) != 64:
        return _invalid("V5", "replay.json patch_tool_sha256 is not a 64-char digest")
    runs = payload.get("runs")
    shas = payload.get("sha256")
    if not isinstance(runs, int) or runs < 2:
        return _invalid("V5", "replay.json runs must be >= 2")
    if not isinstance(shas, list) or len(shas) != runs:
        return _invalid("V5", "replay.json sha256 list does not match runs")
    if payload.get("byte_identical") is not True:
        return _check_failed("V5", "independent replay did not reproduce identical bytes", sources=(source,))
    if any(not isinstance(value, str) or value != candidate_sha256 for value in shas):
        return _check_failed("V5", "independent replay reproduced a different candidate", sources=(source,))
    if payload.get("matches_candidate") is not True:
        return _check_failed("V5", "replay output does not match the candidate", sources=(source,))
    if not isinstance(payload.get("replayed_by"), str) or not payload["replayed_by"].strip():
        return _invalid("V5", "replay.json has no replayed_by identity")
    if not isinstance(payload.get("method"), str) or not payload["method"].strip():
        return _invalid("V5", "replay.json has no method")
    checks = {
        "independent_replay": True,
        "runs": runs,
        "byte_identical": True,
        "patch_tool_sha256": patch_tool,
        "replayed_by": payload["replayed_by"],
    }
    return _finding(
        "V5", "passed",
        "independent replay envelope bound to this candidate and patch tool; host did not re-run the tool",
        sources=(source,),
        checks=checks,
        raw_source=relative,
    )


def validate_route_a_bundle(
    bundle: Path,
    *,
    original_elf: Path,
    contract_body: Mapping[str, Any],
    contract_file: Path | None = None,
    interface_checker: Callable[..., dict[str, Any]] | None = None,
) -> RouteAValidation:
    """Validate one Route A guest bundle and return per-gate findings.

    Raising :class:`RouteAEvidenceError` means the bundle cannot be ingested at
    all (for example no candidate bytes); per-gate gaps are findings instead.
    """

    bundle = Path(bundle)
    if not bundle.is_dir():
        raise RouteAEvidenceError(f"route_a evidence directory is missing: {bundle}")
    candidate_elf = bundle / "route_a" / "candidate.elf"
    if not candidate_elf.is_file():
        raise RouteAEvidenceError(f"route_a evidence has no route_a/candidate.elf: {bundle}")
    original_elf = Path(original_elf)
    if not original_elf.is_file():
        raise RouteAEvidenceError(f"job original is missing: {original_elf}")

    from app.domain.contracts import contract_sha256

    original_sha256 = _sha256_file(original_elf)
    candidate_sha256 = _sha256_file(candidate_elf)
    contract_canonical = contract_sha256(dict(contract_body))
    contract_file_sha = _sha256_file(contract_file) if contract_file and Path(contract_file).is_file() else None
    input_mode = str(contract_body.get("input_mode") or "argv")
    if input_mode not in INPUT_MODES:
        raise RouteAEvidenceError(f"contract input_mode is unknown: {input_mode!r}")

    claims = _load_claims(bundle)
    findings = {
        "V0": _check_v0(
            bundle,
            candidate_sha256=candidate_sha256,
            original_sha256=original_sha256,
            contract_canonical_sha256=contract_canonical,
            contract_file_sha256=contract_file_sha,
            input_mode=input_mode,
        ),
        "V1": _check_v1(bundle),
        "V2": _check_v2(
            bundle,
            original_elf=original_elf,
            candidate_elf=candidate_elf,
            contract_body=contract_body,
        ),
        "V3": _check_v3(bundle, candidate_sha256=candidate_sha256, input_mode=input_mode),
        "V4": _check_v4(
            bundle,
            candidate_sha256=candidate_sha256,
            original_sha256=original_sha256,
            contract_canonical_sha256=contract_canonical,
            contract_file_sha256=contract_file_sha,
        ),
        "V5": _check_v5(bundle, candidate_sha256=candidate_sha256, original_sha256=original_sha256),
    }
    if interface_checker is not None:  # test seam; production uses the product check
        findings["V2"] = interface_checker(bundle)
    findings = {gate: _with_claims(finding, claims) for gate, finding in findings.items()}

    return RouteAValidation(
        candidate_sha256=candidate_sha256,
        candidate_size=candidate_elf.stat().st_size,
        original_sha256=original_sha256,
        contract_canonical_sha256=contract_canonical,
        contract_file_sha256=contract_file_sha,
        findings=findings,
        bundle_claims=claims,
    )


# ---------------------------------------------------------------------------
# Re-validation of host-written verification records (used by obligations).
# ---------------------------------------------------------------------------


def validate_route_a_record(
    payload: object,
    *,
    gate: str,
    candidate_sha256: str,
    original_sha256: str,
    contract_canonical_sha256: str | None = None,
) -> None:
    """Validate one host-written Route A verification record.

    Raises :class:`RouteAEvidenceError`; callers must downgrade the claim, never
    treat an invalid record as a pass.
    """

    if not isinstance(payload, dict):
        raise RouteAEvidenceError("record is not an object")
    if payload.get("record_kind") != RECORD_KIND:
        raise RouteAEvidenceError("not a route_a verification record")
    if payload.get("schema_version") != RECORD_SCHEMA_VERSION:
        raise RouteAEvidenceError("unsupported record schema")
    if payload.get("gate") != gate:
        raise RouteAEvidenceError(f"record gate {payload.get('gate')!r} != {gate!r}")
    if payload.get("status") != "passed":
        raise RouteAEvidenceError(f"record status is {payload.get('status')!r}")
    if payload.get("candidate_sha256") != candidate_sha256:
        raise RouteAEvidenceError("record does not bind this candidate")
    if payload.get("original_sha256") != original_sha256:
        raise RouteAEvidenceError("record does not bind the job original")
    if contract_canonical_sha256 is not None and payload.get("contract_canonical_sha256") != contract_canonical_sha256:
        raise RouteAEvidenceError("record does not bind the reviewed contract")
    sources = payload.get("source_artifacts")
    if not isinstance(sources, list) or not sources:
        raise RouteAEvidenceError("record has no source artifacts")
    for source in sources:
        if not isinstance(source, dict):
            raise RouteAEvidenceError("record source artifact is not an object")
        if not isinstance(source.get("artifact_id"), str) or not source["artifact_id"]:
            raise RouteAEvidenceError("record source artifact has no artifact id")
        digest = source.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise RouteAEvidenceError("record source artifact has no sha256")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise RouteAEvidenceError("record has no checks object")

    required_true = {
        "V1": ("audit_pass", "edit_manifest_bound", "readelf_present", "lief_present"),
        "V3": ("repaired_pass", "cases_ok"),
        "V5": ("independent_replay", "sha256_all_candidate", "byte_identical"),
    }
    for name in required_true.get(gate, ()):
        if checks.get(name) is not True:
            raise RouteAEvidenceError(f"record check {name} is not true")
    if gate == "V3":
        passed, total = checks.get("passed"), checks.get("total")
        if not isinstance(passed, int) or not isinstance(total, int) or passed != total or total < 1:
            raise RouteAEvidenceError("record V3 counts are inconsistent")
    if gate == "V5":
        runs = checks.get("runs")
        if not isinstance(runs, int) or runs < 2:
            raise RouteAEvidenceError("record V5 runs < 2")
        tool = checks.get("patch_tool_sha256")
        if not isinstance(tool, str) or len(tool) != 64:
            raise RouteAEvidenceError("record V5 patch tool hash is not pinned")
        if not isinstance(checks.get("replayed_by"), str) or not checks["replayed_by"].strip():
            raise RouteAEvidenceError("record V5 has no replayer identity")


__all__ = [
    "GATES",
    "REASON_PREFIXES",
    "RECORD_KIND",
    "GateFinding",
    "RouteAEvidenceError",
    "RouteAValidation",
    "validate_route_a_bundle",
    "validate_route_a_record",
]
