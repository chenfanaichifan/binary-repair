"""Phase-8C C6: public benchmark runner v2 with layered metrics.

Runs the committed Phase-8C ground-truth manifest against the *deterministic*
repair engine (``app.services.binary_pipeline.repair_any``), then independently
verifies every produced candidate with ``app.services.independent_verifier``
(never with the generator's own gate), classifies the semantic regression
evidence and emits the C2 ``benchmark-results-v2`` document.

Design rules (Phase-8C contract):

* per-sample status is one of ``executed`` / ``not_run`` / ``blocked`` /
  ``unsupported`` / ``invalid`` -- a sample is never silently dropped;
* ``false_verified`` is a claim that the deterministic engine verified but an
  available independent verifier rejected.  It must be 0; the default
  ``withdraw`` claim policy withdraws such a claim (fail-closed publication),
  records the disagreement, and exits non-zero.  Nothing is hidden;
* ``verified_repair_rate`` denominator is the *eligible repair cases*: expected
  scope ``function``/``whole_program``, a real runtime oracle and judgeable
  expected behaviour.  Analysis-only samples are excluded from repair rates and
  reported separately; a zero denominator yields ``null`` (never a fake 0);
* the Lima guest is serialised through ``app.services.guest_coordinator``; a
  missing guest/lock yields ``blocked``/``not_run`` with an explicit reason, no
  fabricated pass;
* no wall clock, no network, no AI provider.  ``generated_at`` is inherited from
  the fixed manifest so repeated runs are byte-identical;
* the committed artifact is validated offline by ``check_artifact`` (and by the
  C2 contract checker integration) without executing any sample.

Hidden lane: a private hidden manifest (C4 shape) is executed only under the
Lead-owned root; the emitted hidden aggregate contains counts and layered
metrics only -- never per-sample ids, paths, bytes or case details.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # pragma: no cover - import side effect
    sys.path.insert(0, str(ROOT))

SCHEMA_VERSION = 2
KIND = "benchmark_results_v2"
MANIFEST_PATH = "benchmark/phase8c/manifest.json"
CANONICAL_RESULTS_PATH = "benchmark/phase8c/results.json"
PUBLIC_ARTIFACT_DIR = "artifacts/phase8c-benchmark-2026-11-16"
HIDDEN_AGGREGATE_PATH = "artifacts/phase8c-hidden-2026-11-16/aggregate.json"
HIDDEN_COMMITMENT_PATH = "benchmark/phase8c/hidden-commitment.json"

STATUSES = ("executed", "not_run", "blocked", "unsupported", "invalid")
VERIFICATION_DECISIONS = ("verified", "rejected", "inconclusive", "not_run")
RUNTIME_ORACLE_KINDS = frozenset({"external_poc", "native", "emulated"})
RUNTIME_TIERS = frozenset({"native_run", "emulated_run"})
CLAIM_POLICIES = ("withdraw", "fail_on_disagreement")
GENERATOR_ID = "deterministic-repair-any/app.services.binary_pipeline"
VERIFIER_ID = "independent-verifier/1"
HIDDEN_MANIFEST_KIND = "phase8c_private_hidden_manifest"
HIDDEN_AGGREGATE_KIND = "phase8c_hidden_aggregate"
SAFE_DEFAULT_MANIFEST_LIMITATION = (
    "public corpus only: hidden_available=false and hidden_commitment is null; "
    "the hidden lane must be run separately under the Lead-owned private root"
)
FLAKE_LIMITATION = (
    "single-run evidence is not an unconditional stability claim (C1 warning "
    "B-POST-REBASE-REPRODUCTION-FLAKY): repeated serialized runs and their "
    "attempt history must be recorded before claiming stability"
)


class BenchmarkError(RuntimeError):
    """The manifest/artifact/request is unusable (fail closed, exit 2)."""


class ManifestError(BenchmarkError):
    """The benchmark manifest violates the C2 v2 contract."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")


def canonical_json(payload: Any) -> bytes:
    """Deterministic pretty JSON bytes for committed artifacts."""

    return (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("ascii")


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise BenchmarkError(f"missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"unreadable JSON {path}: {type(exc).__name__}") from exc


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _escape(value: Any) -> str:
    return str(value)


# ---------------------------------------------------------------------------
# Manifest loading / validation (C2 v2 contract)
# ---------------------------------------------------------------------------


def load_manifest(
    path: str | Path = MANIFEST_PATH,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Load and structurally validate a benchmark-manifest-v2 document."""

    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = Path(root) / resolved
    try:
        payload = _load_json(resolved)
    except BenchmarkError as exc:
        raise ManifestError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise ManifestError("benchmark manifest is not an object")
    violations = validate_manifest_payload(payload)
    if violations:
        raise ManifestError("; ".join(violations[:5]))
    return payload


def validate_manifest_payload(manifest: Mapping[str, Any]) -> list[str]:
    """Fail-closed structural checks for the C2 manifest v2 document.

    This mirrors the schema's required fields and the handful of semantics the
    runner depends on; the authoritative JSON-schema validation is the C2
    checker's job (see :func:`check_artifact`).
    """

    violations: list[str] = []
    if manifest.get("schema_version") != 2:
        violations.append("manifest schema_version must be 2")
    if manifest.get("kind") != "ground_truth_benchmark_v2":
        violations.append(
            f"manifest kind must be ground_truth_benchmark_v2, got "
            f"{manifest.get('kind')!r}"
        )
    if not isinstance(manifest.get("benchmark_id"), str) or not manifest.get("benchmark_id"):
        violations.append("manifest benchmark_id is required")
    if not isinstance(manifest.get("generated_at"), str) or not manifest.get("generated_at"):
        violations.append("manifest generated_at is required")
    if not isinstance(manifest.get("hidden_available"), bool):
        violations.append("manifest hidden_available must be boolean")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        violations.append("manifest samples must be a non-empty array")
        return violations
    seen: set[str] = set()
    for index, sample in enumerate(samples):
        where = f"samples[{index}]"
        if not isinstance(sample, Mapping):
            violations.append(f"{where}: not an object")
            continue
        sample_id = sample.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            violations.append(f"{where}: sample_id is required")
        elif sample_id in seen:
            violations.append(f"{where}: duplicate sample_id {sample_id!r}")
        else:
            seen.add(sample_id)
        if sample.get("sample_version") != 2:
            violations.append(f"{where}: sample_version must be 2")
        if not _is_sha256(sample.get("binary_sha256")):
            violations.append(f"{where}: binary_sha256 must be a sha256")
        for key in ("format", "arch", "expected_scope", "vulnerability_family"):
            if not isinstance(sample.get(key), str) or not sample.get(key):
                violations.append(f"{where}: {key} is required")
        if sample.get("format") not in {"elf", "macho", "pe"}:
            violations.append(f"{where}: unsupported format {sample.get('format')!r}")
        if sample.get("arch") not in {"x86_64", "i386", "arm64"}:
            violations.append(f"{where}: unsupported arch {sample.get('arch')!r}")
        if sample.get("expected_scope") not in {"function", "whole_program", "analysis_only"}:
            violations.append(
                f"{where}: unsupported expected_scope {sample.get('expected_scope')!r}")
        if sample.get("split") not in {"dev", "validation"}:
            violations.append(f"{where}: split must be dev|validation")
        target = sample.get("target")
        if not isinstance(target, Mapping) or target.get("kind") not in {
            "function", "symbol", "va_range", "whole_image", "analysis_only",
        }:
            violations.append(f"{where}: target.kind is invalid")
        oracle = sample.get("oracle")
        if not isinstance(oracle, Mapping):
            violations.append(f"{where}: oracle is required")
        elif oracle.get("kind") not in {
            "external_poc", "native", "emulated", "static", "analysis_only",
        }:
            violations.append(f"{where}: oracle.kind is invalid")
        elif not isinstance(oracle.get("regression_case_ids"), list):
            violations.append(f"{where}: oracle.regression_case_ids must be an array")
    if manifest.get("sample_count") != len(samples):
        violations.append("manifest sample_count must equal len(samples)")
    split_counts = manifest.get("split_counts")
    actual = {"dev": 0, "validation": 0}
    for sample in samples:
        if isinstance(sample, Mapping) and sample.get("split") in actual:
            actual[str(sample["split"])] += 1
    if isinstance(split_counts, Mapping):
        for split in actual:
            if split_counts.get(split) != actual[split]:
                violations.append(
                    f"manifest split_counts.{split} must equal the sample count")
    else:
        violations.append("manifest split_counts is required")
    hidden_commitment = manifest.get("hidden_commitment")
    if manifest.get("hidden_available") is True and not isinstance(
        hidden_commitment, Mapping
    ):
        violations.append(
            "hidden_available=true requires a hidden commitment record")
    return violations


def sample_binary_path(sample: Mapping[str, Any], *, root: Path = ROOT) -> Path:
    """Resolve the public sample binary by content hash (lossless, no guessing).

    The v2 contract has no dedicated binary path; committed ``source_refs`` /
    ``evidence_refs`` are the documented path convention.  Exactly one existing
    referenced file must hash to ``binary_sha256``; anything else is an explicit
    error (never a silent fallback to a similarly named file).
    """

    expected = str(sample.get("binary_sha256") or "")
    sample_id = str(sample.get("sample_id") or "?")
    refs: list[str] = []
    for key in ("source_refs", "evidence_refs"):
        value = sample.get(key)
        if isinstance(value, list):
            refs.extend(str(item) for item in value if isinstance(item, str))
    if not refs:
        raise ManifestError(f"{sample_id}: no source_refs/evidence_refs to resolve the binary")
    matches: list[Path] = []
    for ref in refs:
        relative = ref.split("#", 1)[0].strip()
        if not relative:
            continue
        candidate = Path(relative)
        if not candidate.is_absolute():
            candidate = Path(root) / candidate
        if not candidate.is_file():
            continue
        if _sha256_file(candidate) == expected:
            matches.append(candidate)
    unique = sorted({str(path) for path in matches})
    if len(unique) != 1:
        detail = "no referenced file matches" if not unique else f"ambiguous: {unique[:3]}"
        raise ManifestError(
            f"{sample_id}: binary_sha256 {expected[:12]}... could not be "
            f"resolved to exactly one committed file ({detail})")
    return Path(unique[0])


def resolve_target_argument(sample: Mapping[str, Any]) -> Any:
    """Translate the manifest target to ``repair_any``'s selector/argument."""

    target = sample.get("target") or {}
    kind = target.get("kind")
    if kind in {"function", "symbol"}:
        value = target.get("symbol") or target.get("function")
        if not isinstance(value, str) or not value:
            raise ManifestError(
                f"{sample.get('sample_id')}: target kind {kind} has no symbol")
        return value
    if kind == "va_range":
        va, end = target.get("va"), target.get("end")
        if not _is_int(va) or not _is_int(end) or end <= va:
            raise ManifestError(
                f"{sample.get('sample_id')}: invalid va_range target")
        return {"va": va, "end": end}
    return None


def is_runtime_oracle_sample(sample: Mapping[str, Any]) -> bool:
    oracle = sample.get("oracle") or {}
    kinds = set(oracle.get("kinds") or []) | {oracle.get("kind")}
    return bool(kinds & RUNTIME_ORACLE_KINDS)


def is_analysis_only_sample(sample: Mapping[str, Any]) -> bool:
    target = sample.get("target") or {}
    return (
        sample.get("expected_scope") == "analysis_only"
        or target.get("kind") == "analysis_only"
        or (sample.get("oracle") or {}).get("kind") in {"static", "analysis_only"}
    )


def is_judgeable_expected_behavior(sample: Mapping[str, Any]) -> bool:
    """Whether the manifest declares an expected behavior a verifier can judge."""

    oracle = sample.get("oracle") or {}
    if is_analysis_only_sample(sample):
        return False
    if oracle.get("expected_original") is None or oracle.get("expected_candidate") is None:
        expected_original = sample.get("expected_original_behavior")
        expected_fixed = sample.get("expected_fixed_behavior")
        semantic = sample.get("semantic_regression") or {}
        if not (isinstance(expected_original, str) and expected_original
                and isinstance(expected_fixed, str) and expected_fixed):
            if not (isinstance(semantic, Mapping) and semantic.get("required") is True):
                return False
    if isinstance(oracle.get("manifest_path"), str) and oracle.get("manifest_path"):
        return True
    return isinstance(oracle.get("expected_original"), (str, bool)) or isinstance(
        oracle.get("expected_candidate"), (str, bool)
    )


def is_eligible_repair_case(sample: Mapping[str, Any]) -> bool:
    """Eligibility for repair-rate denominators (Phase-8C C6 contract)."""

    if sample.get("expected_scope") not in {"function", "whole_program"}:
        return False
    if not is_runtime_oracle_sample(sample):
        return False
    return bool(is_judgeable_expected_behavior(sample))


def load_oracle_manifest(
    sample: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any] | None:
    path = (sample.get("oracle") or {}).get("manifest_path")
    if not isinstance(path, str) or not path:
        return None
    from app.services.poc_runner import load_manifest as load_poc_manifest

    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = Path(root) / resolved
    return load_poc_manifest(resolved)


# ---------------------------------------------------------------------------
# Guest/oracle runtime coordination (C11)
# ---------------------------------------------------------------------------


class GuestRuntime:
    """Guest availability probe + Lima lease around one sample execution.

    The Lima tier is the only shared guest; the lease comes from the C11
    ``guest_coordinator`` and is reentrant, so the PoC/verifier executions that
    happen inside the lease reuse it instead of deadlocking.
    """

    def __init__(self, coordinator: Any = None) -> None:
        self._coordinator = coordinator
        self.attempts: list[dict[str, Any]] = []

    def _coordinator_module(self) -> Any:
        if self._coordinator is not None:
            return self._coordinator
        from app.services import guest_coordinator

        return guest_coordinator

    def runtime_for(self, arch: str) -> Any:
        try:
            from app.services.guest_runner import find_guest_runner

            return find_guest_runner(arch)
        except Exception:  # noqa: BLE001 - a probe failure means unavailable
            return None

    def availability(self, format_name: str, arch: str) -> dict[str, Any]:
        """Return ``{available, poc_available, runner, tier, kind, reason}``."""

        runtime = self.runtime_for(arch)
        poc_available = False
        tier = "unavailable"
        reason = ""
        try:
            from app.services.runtime import capabilities

            contract = capabilities.contract(format_name, arch)
            poc_available = bool(contract.get("poc_available"))
            tier = str(contract.get("measured_tier") or "unavailable")
            reason = str(contract.get("reason") or "")
        except Exception as exc:  # noqa: BLE001 - capability probe is evidence
            reason = f"capability probe failed: {type(exc).__name__}: {exc}"
        if runtime is None and not poc_available:
            return {
                "available": False, "poc_available": False, "runner": None,
                "tier": "unavailable", "kind": "none",
                "reason": reason or "no external PoC/guest runner for this format/arch",
            }
        runner_name = None
        kind = "none"
        if runtime is not None:
            runner_name = getattr(runtime, "tool", None) or getattr(runtime, "kind", None)
            kind = str(getattr(runtime, "kind", "") or "none")
            tier = str(getattr(runtime, "tier", "") or tier)
        if not poc_available and kind != "lima":
            return {
                "available": False, "poc_available": False,
                "runner": runner_name, "tier": tier, "kind": kind,
                "reason": reason or "external PoC runner unavailable",
            }
        return {
            "available": True,
            "poc_available": bool(poc_available or kind == "lima"),
            "runner": runner_name, "tier": tier, "kind": kind,
            "reason": reason,
        }

    def lease(self, arch: str, *, purpose: str, run_id: str) -> Any:
        """Acquire the C11 Lima lease (or a no-op for native/qemu tiers)."""

        runtime = self.runtime_for(arch)
        kind = str(getattr(runtime, "kind", "") or "")
        if runtime is None or kind != "lima":
            return _NullLease()
        coordinator = self._coordinator_module()
        instance = str(getattr(runtime, "instance", "") or "")
        lease = coordinator.acquire_lima_guest_lock(
            purpose=purpose,
            instance=instance or None,
            limactl=getattr(runtime, "tool", None),
            run_id=run_id,
        )
        return lease


class _NullLease:
    """No-op lease context for native/qemu tiers."""

    run_id = ""
    attempts: list[dict[str, Any]] = []  # type: ignore[assignment]

    def release(self) -> None:
        return None

    def __enter__(self) -> "_NullLease":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.release()

    def __getattr__(self, _name: str) -> Any:  # pragma: no cover - defensive
        return None


class _GuestLockBlocked(RuntimeError):
    """The C11 guest lock could not be acquired (blocked, nothing executed)."""

    def __init__(self, message: str, attempts: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.attempts = list(attempts or [])


# ---------------------------------------------------------------------------
# Independent verifier adapter
# ---------------------------------------------------------------------------


def _load_module_from_path(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"phase8c_verifier_{abs(hash(str(path))) & 0xFFFFFFFF}", path,
    )
    if spec is None or spec.loader is None:
        raise BenchmarkError(f"cannot import verifier module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_verifier(
    spec: str | Path | Any | None,
    *,
    root: Path = ROOT,
) -> tuple[Any | None, dict[str, Any]]:
    """Resolve ``auto|none|<path>`` to a verifier module and a status record."""

    status: dict[str, Any] = {
        "requested": _escape(spec) if not isinstance(spec, (str, Path)) else str(spec),
        "available": False,
        "id": None,
        "detail": "",
    }
    if isinstance(spec, str):
        requested = spec.strip() or "auto"
    elif isinstance(spec, Path):
        requested = str(spec)
    elif spec is None:
        requested = "none"
    else:
        return spec, {
            "requested": "injected", "available": True,
            "id": str(getattr(spec, "VERIFIER_ID", VERIFIER_ID)),
            "detail": "injected verifier",
        }
    status["requested"] = requested
    if requested == "none":
        status["detail"] = "independent verification disabled by --verifier none"
        return None, status
    try:
        if requested == "auto":
            import app.services.independent_verifier as module

            status["id"] = str(getattr(module, "VERIFIER_ID", VERIFIER_ID))
        else:
            path = Path(requested)
            if not path.is_absolute():
                path = Path(root) / path
            if not path.is_file():
                raise BenchmarkError(f"verifier module not found: {path}")
            module = _load_module_from_path(path)
            status["id"] = str(
                getattr(module, "VERIFIER_ID", "external-verifier")
            )
        if not callable(getattr(module, "verify_repair", None)):
            raise BenchmarkError(
                f"verifier module {requested!r} has no verify_repair function")
        status["available"] = True
        status["detail"] = f"loaded verifier {status['id']}"
        return module, status
    except BenchmarkError:
        raise
    except Exception as exc:  # noqa: BLE001 - recorded as unavailable, not a pass
        status["detail"] = f"verifier unavailable: {type(exc).__name__}: {exc}"
        return None, status


def _target_scope_for_verifier(sample: Mapping[str, Any]) -> dict[str, Any]:
    target = sample.get("target") or {}
    kind = target.get("kind")
    if kind in {"function", "symbol"}:
        name = target.get("symbol") or target.get("function")
        return {"policy": "target_scoped", "name": name}
    if kind == "va_range":
        return {
            "policy": "target_scoped", "kind": "va_range",
            "va": target.get("va"), "end": target.get("end"),
        }
    return {"policy": "analysis_only"}


def _verification_metadata(
    sample: Mapping[str, Any],
    classified: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "format": sample.get("format"),
        "arch": sample.get("arch"),
        "bits": sample.get("bits"),
        "endian": sample.get("endian"),
        "target_sha256": sample.get("binary_sha256"),
        "target_scope": _target_scope_for_verifier(sample),
        "allow_whole_image": (sample.get("target") or {}).get("kind") == "whole_image",
        "generator": {"generator_id": GENERATOR_ID},
    }
    if not isinstance(classified, Mapping):
        return metadata
    report = classified.get("report")
    resolved = {}
    if isinstance(report, Mapping):
        universal = report.get("universal")
        if isinstance(universal, Mapping) and isinstance(
            universal.get("target_scope"), Mapping
        ):
            resolved = dict(universal["target_scope"])
    if not resolved:
        scope_info = _report_field(report, "universal", {}) or {}
        if isinstance(scope_info, Mapping) and isinstance(
            scope_info.get("target_scope"), Mapping
        ):
            resolved = dict(scope_info["target_scope"])
    if resolved:
        scope: dict[str, Any] = {"policy": "target_scoped"}
        if isinstance(resolved.get("name"), str) and resolved["name"]:
            scope["name"] = resolved["name"]
        if _is_int(resolved.get("va")):
            scope["va"] = int(resolved["va"])
        if _is_int(resolved.get("end")):
            scope["end"] = int(resolved["end"])
        if resolved.get("source") == "explicit":
            scope["kind"] = "va_range"
        metadata["target_scope"] = scope
    plan = classified.get("patch_plan")
    if isinstance(plan, Mapping):
        exchange_plan = json.loads(json.dumps(plan))
        oracle = exchange_plan.get("oracle")
        manifest_path = (sample.get("oracle") or {}).get("manifest_path")
        if isinstance(oracle, dict) and isinstance(manifest_path, str) and manifest_path:
            try:
                oracle["manifest_sha256"] = _sha256_file(
                    Path(manifest_path) if Path(manifest_path).is_absolute()
                    else ROOT / manifest_path
                )
            except OSError:
                pass
            oracle.pop("evidence_sha256", None)
        metadata["patch_plan"] = exchange_plan
    if classified.get("actions"):
        metadata["actions"] = list(classified["actions"])
    if classified.get("message_actions"):
        metadata["message_actions"] = list(classified["message_actions"])
    return metadata


def run_independent_verification(
    sample: Mapping[str, Any],
    original: bytes,
    candidate: bytes | None,
    *,
    verifier: Any | None,
    oracle_manifest_path: str | None,
    root: Path = ROOT,
    run_poc: Callable[..., Any] | None = None,
    classified: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the independent verifier; never the generator's own gate."""

    if verifier is None:
        return {
            "decision": "not_run",
            "evidence_sha256": None,
            "reason": "no independent verifier was loaded",
            "report": {},
        }
    if candidate is None:
        return {
            "decision": "not_run",
            "evidence_sha256": None,
            "reason": "no candidate bytes exist to independently verify",
            "report": {},
        }
    oracle: Any = None
    if oracle_manifest_path:
        resolved = Path(oracle_manifest_path)
        if not resolved.is_absolute():
            resolved = Path(root) / resolved
        oracle = str(resolved)
    if run_poc is None:
        try:
            from app.services.poc_runner import run_poc as run_poc_impl

            run_poc = run_poc_impl
        except Exception:  # noqa: BLE001 - verifier records oracle unavailable
            run_poc = None
    metadata = _verification_metadata(sample, classified)
    try:
        import inspect as _inspect

        parameters = set(_inspect.signature(verifier.verify_repair).parameters)
        call_kwargs: dict[str, Any] = {
            "original": original,
            "candidate": candidate,
            "metadata": metadata,
            "oracle": oracle,
            "generator": metadata["generator"],
            "run_poc": run_poc,
        }
        for extra in ("patch_plan", "claimed_actions", "abi_block"):
            if extra in parameters and metadata.get(extra) is not None:
                call_kwargs[extra] = metadata[extra]
        report = verifier.verify_repair(**call_kwargs)
    except Exception as exc:  # noqa: BLE001 - recorded, never hidden
        return {
            "decision": "not_run",
            "evidence_sha256": None,
            "reason": f"independent verifier failed: {type(exc).__name__}: {exc}",
            "report": {},
        }
    if not isinstance(report, Mapping) or "decision" not in report:
        return {
            "decision": "not_run",
            "evidence_sha256": None,
            "reason": "independent verifier returned no decision",
            "report": dict(report) if isinstance(report, Mapping) else {},
        }
    decision = str(report.get("decision"))
    if decision not in VERIFICATION_DECISIONS:
        decision = "not_run"
    evidence_sha = report.get("report_sha256")
    if not _is_sha256(evidence_sha):
        evidence_sha = _sha256_bytes(_canonical(dict(report)))
    reason = "; ".join(
        str(item) for item in (report.get("limitations") or []) if str(item)
    )[:500] or None
    return {
        "decision": decision,
        "evidence_sha256": evidence_sha,
        "reason": reason,
        "report": dict(report),
    }


# ---------------------------------------------------------------------------
# Sample execution
# ---------------------------------------------------------------------------


def _default_repair(original: bytes, sample: Mapping[str, Any], *,
                    root: Path) -> Any:
    from app.services.binary_pipeline import repair_any

    oracle_path = (sample.get("oracle") or {}).get("manifest_path")
    poc_manifest = load_oracle_manifest(sample, root=root)
    target = resolve_target_argument(sample)
    target_kind = (sample.get("target") or {}).get("kind")
    if is_analysis_only_sample(sample):
        return repair_any(original)
    allow_whole_image = target_kind == "whole_image"
    return repair_any(
        original,
        poc_manifest=poc_manifest,
        target=None if allow_whole_image else target,
        require_target=not allow_whole_image,
        allow_whole_image=allow_whole_image,
    )


def _report_field(report: Any, name: str, default: Any = None) -> Any:
    if isinstance(report, Mapping):
        return report.get(name, default)
    return getattr(report, name, default)


def _finding_address(finding: Mapping[str, Any]) -> int | None:
    value = finding.get("site_va")
    if _is_int(value):
        return int(value)
    address = finding.get("address")
    if isinstance(address, str):
        try:
            return int(address, 16)
        except ValueError:
            return None
    if _is_int(address):
        return int(address)
    return None


def _expected_scope_range(sample: Mapping[str, Any],
                          report: Any) -> tuple[int, int] | None:
    scope = _report_field(report, "universal", {}) or {}
    if not isinstance(scope, Mapping):
        return None
    target_scope = scope.get("target_scope")
    if isinstance(target_scope, Mapping):
        va, end = target_scope.get("va"), target_scope.get("end")
        if _is_int(va) and _is_int(end) and end > va:
            return int(va), int(end)
    target = sample.get("target") or {}
    if target.get("kind") == "va_range":
        va, end = target.get("va"), target.get("end")
        if _is_int(va) and _is_int(end) and end > va:
            return int(va), int(end)
    return None


def _finding_matches_target(sample: Mapping[str, Any], report: Any,
                            finding: Mapping[str, Any],
                            scope: tuple[int, int] | None) -> bool:
    address = _finding_address(finding)
    if scope is not None and address is not None:
        if scope[0] <= address < scope[1]:
            return True
    expected_name = (
        (sample.get("target") or {}).get("symbol")
        or (sample.get("target") or {}).get("function")
        or sample.get("affected_function")
    )
    if isinstance(expected_name, str) and expected_name:
        detail = " ".join(
            str(value) for value in finding.values() if isinstance(value, str)
        )
        if expected_name in detail:
            return True
        actions = _report_field(report, "actions", []) or []
        container_symbols = _report_field(report, "container", {}) or {}
        symbols = container_symbols.get("symbols") if isinstance(container_symbols, Mapping) else None
        for action in actions if isinstance(actions, list) else []:
            if not isinstance(action, Mapping):
                continue
            function_va = action.get("function_va")
            if isinstance(symbols, Mapping) and _is_int(function_va):
                name = symbols.get(str(function_va)) or symbols.get(function_va)
                if isinstance(name, str) and name == expected_name:
                    return True
    return False


def classify_repair_outcome(
    sample: Mapping[str, Any],
    original: bytes,
    outcome: Any,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Extract the layered v2 fields from one ``repair_any`` outcome."""

    report = getattr(outcome, "report", None)
    candidate = getattr(outcome, "candidate", None)
    disposition = str(_report_field(report, "disposition", "") or "")
    findings = _report_field(report, "findings", []) or []
    actions = _report_field(report, "actions", []) or []
    scope = _expected_scope_range(sample, report)
    analysis_only = is_analysis_only_sample(sample)
    oracle = sample.get("oracle") or {}

    detection: bool | None
    root_cause: bool | None
    localization: bool | None
    if analysis_only:
        detection = bool(findings)
        root_cause = None
        localization = None
    else:
        detection = bool(findings) or candidate is not None
        causes = [
            finding for finding in findings
            if isinstance(finding, Mapping)
            and _finding_matches_target(sample, report, finding, scope)
        ]
        if causes:
            root_cause = True
        elif candidate is not None and scope is not None:
            # A produced candidate whose actions stay inside the declared target
            # is acceptable root-cause evidence too (the engine patched the
            # declared vulnerable function).
            root_cause = bool(actions) and all(
                isinstance(action, Mapping)
                and _is_int(action.get("site_va"))
                and scope[0] <= int(action["site_va"]) < scope[1]
                for action in actions
            )
        else:
            root_cause = False
        if candidate is None:
            localization = False
        elif scope is not None and actions:
            localization = all(
                isinstance(action, Mapping)
                and _is_int(action.get("site_va"))
                and scope[0] <= int(action["site_va"]) < scope[1]
                for action in actions
            )
        else:
            localization = bool(actions)

    poc = _report_field(report, "poc", {}) or {}
    tier = "static_only"
    runner = None
    oracle_status = "not_run"
    if isinstance(poc, Mapping) and poc:
        poc_tier = str(poc.get("tier") or "")
        if poc_tier in RUNTIME_TIERS:
            tier = poc_tier
        runner = poc.get("runner") or None
        if poc.get("status") in {"pass", "fail"}:
            oracle_status = "executed"
        elif poc.get("status") == "unavailable":
            oracle_status = "unavailable"
    elif not analysis_only and not oracle.get("manifest_path"):
        tier = "unavailable"

    environment = {
        "tier": tier,
        "runner": runner,
        "oracle_status": oracle_status,
    }
    packet = {}
    verification = _report_field(report, "verification", {}) or {}
    if isinstance(verification, Mapping):
        packet = verification.get("packet") if isinstance(
            verification.get("packet"), Mapping) else {}
    capacity = packet.get("capacity") if isinstance(
        packet.get("capacity"), Mapping) else {}
    message_actions = capacity.get("message_actions") if isinstance(
        capacity.get("message_actions"), list) else []
    plan = _report_field(report, "patch_plan")
    return {
        "disposition": disposition,
        "status_supported": disposition not in {"invalid", "unsupported"},
        "patch_plan": plan if isinstance(plan, Mapping) else None,
        "actions": [dict(action) for action in actions
                    if isinstance(action, Mapping)],
        "message_actions": [dict(action) for action in message_actions
                            if isinstance(action, Mapping)],
        "detection": detection,
        "root_cause": root_cause,
        "localization": localization,
        "strategy": _report_field(report, "strategy") or None,
        "candidate": candidate,
        "environment": environment,
        "regression": None,
        "poc_evidence": dict(poc) if isinstance(poc, Mapping) else {},
        "report": report,
        "analysis_only": analysis_only,
        "oracle_manifest_path": oracle.get("manifest_path"),
    }


def _blocked_execution(
    sample: Mapping[str, Any],
    reason: str,
    *,
    status: str = "blocked",
    detection: bool | None = None,
) -> dict[str, Any]:
    return {
        "sample": dict(sample),
        "result": None,
        "status": status,
        "detection": detection,
        "root_cause": None,
        "localization": None,
        "strategy": None,
        "candidate": None,
        "verification": {
            "decision": "not_run", "evidence_sha256": None,
            "reason": reason, "report": {},
        },
        "regression": None,
        "environment": {
            "tier": "unavailable", "runner": None, "oracle_status": "not_run",
        },
        "false_verified": False,
        "false_verified_internal": False,
        "not_run_reason": reason,
        "semantic_regression": {
            "status": "unavailable", "decision": "not_run",
            "regression": None, "reason": reason,
        },
        "limitations": [reason],
    }


def execute_sample(
    sample: Mapping[str, Any],
    *,
    root: Path = ROOT,
    repair_fn: Callable[..., Any] | None = None,
    verifier: Any | None = None,
    guest: GuestRuntime | None = None,
    oracle_runner: Callable[..., Any] | None = None,
    binary_path: Path | None = None,
    oracle_manifest_path: str | None = None,
    run_id: str = "phase8c",
) -> dict[str, Any]:
    """Execute one sample and return the classified v2 sample record."""

    sample_id = str(sample.get("sample_id") or "?")
    guest = guest or GuestRuntime()
    analysis_only = is_analysis_only_sample(sample)
    try:
        resolved_binary = binary_path or sample_binary_path(sample, root=root)
        original = resolved_binary.read_bytes()
    except (ManifestError, OSError) as exc:
        return _blocked_execution(sample, f"{sample_id}: binary resolution failed: {exc}",
                                  status="invalid")
    if _sha256_bytes(original) != str(sample.get("binary_sha256")):
        return _blocked_execution(
            sample,
            f"{sample_id}: committed binary sha256 does not match the manifest",
            status="invalid",
        )
    material = {"sample_id": sample_id, "binary_path": str(resolved_binary)}
    execution: dict[str, Any] = {
        "sample": sample, "material": material, "original_sha256": _sha256_bytes(original),
        "host": {"platform": sys.platform, "machine": platform.machine(),
                 "python": platform.python_version()},
    }
    if analysis_only:
        # Static analysis path only; no candidate and no runtime oracle.
        try:
            outcome = _run_repair(original, sample, root=root, repair_fn=repair_fn)
        except Exception as exc:  # noqa: BLE001 - recorded as not_run
            return _blocked_execution(
                sample, f"{sample_id}: deterministic analysis raised "
                        f"{type(exc).__name__}: {exc}", status="not_run")
        classified = classify_repair_outcome(sample, original, outcome, root=root)
        environment = classified["environment"]
        environment["tier"] = "static_only"
        environment["runner"] = None
        environment["oracle_status"] = "not_run"
        result = {
            "status": "executed",
            "detection": classified["detection"],
            "root_cause": None,
            "localization": None,
            "strategy": classified["strategy"],
            "candidate": None,
            "verification": {
                "decision": "not_run", "evidence_sha256": None,
                "reason": "analysis-only sample: no candidate is produced",
                "report": {},
            },
            "regression": None,
            "environment": environment,
            "false_verified": False,
            "false_verified_internal": False,
            "not_run_reason": None,
            "semantic_regression": {
                "status": "not_run", "decision": "not_run",
                "regression": None,
                "reason": "analysis-only sample: no candidate regression check",
            },
            "limitations": [],
            "repair": classified,
        }
        execution["result"] = result
        return execution

    availability = guest.availability(str(sample.get("format")), str(sample.get("arch")))
    if not availability.get("available"):
        return _blocked_execution(
            sample,
            f"{sample_id}: guest/oracle unavailable: "
            f"{availability.get('reason') or 'no runtime oracle'}",
            status="blocked",
        )
    lease = None
    try:
        try:
            lease = guest.lease(
                str(sample.get("arch")),
                purpose=f"phase8c_benchmark.{sample_id}",
                run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001 - C11 typed lock failure
            reason = (
                f"{sample_id}: Lima guest lock unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
            execution["guest_lock_attempts"] = list(
                getattr(exc, "attempts", []) or []
            )
            return _blocked_execution(sample, reason, status="blocked")
        try:
            outcome = _run_repair(
                original, sample, root=root, repair_fn=repair_fn,
            )
        except Exception as exc:  # noqa: BLE001 - recorded as not_run
            return _blocked_execution(
                sample,
                f"{sample_id}: deterministic repair raised "
                f"{type(exc).__name__}: {exc}",
                status="not_run",
            )
        classified = classify_repair_outcome(sample, original, outcome, root=root)
        candidate = classified["candidate"]
        candidate_bytes = bytes(candidate) if candidate is not None else None
        disposition = classified["disposition"]
        if disposition in {"invalid", "unsupported"}:
            return _blocked_execution(
                sample,
                f"{sample_id}: deterministic engine disposition {disposition}: "
                f"{_report_field(classified['report'], 'error') or 'no candidate'}",
                status=disposition,
            )
        poc_evidence = classified["poc_evidence"]
        if (
            isinstance(poc_evidence, Mapping)
            and (poc_evidence.get("lock_blocked") is True
                 or poc_evidence.get("status") == "unavailable")
        ):
            reason = "; ".join(
                str(item) for item in (poc_evidence.get("limitations") or [])
                if str(item)
            ) or "external PoC/guest unavailable"
            return _blocked_execution(
                sample,
                f"{sample_id}: oracle blocked: {reason}",
                status="blocked",
            )
        verification = run_independent_verification(
            sample, original, candidate_bytes,
            verifier=verifier,
            oracle_manifest_path=oracle_manifest_path
            or classified.get("oracle_manifest_path"),
            root=root, run_poc=oracle_runner, classified=classified,
        )
    finally:
        if lease is not None:
            try:
                lease.release()
            except Exception:  # noqa: BLE001 - release must never mask evidence
                pass
            attempts = list(getattr(lease, "attempts", []) or [])
            if attempts:
                execution["guest_lock_attempts"] = (
                    list(execution.get("guest_lock_attempts") or []) + attempts
                )
    guest_attempts = [
        {key: value for key, value in record.items() if key != "lock_path"}
        for record in (execution.get("guest_lock_attempts") or [])
        if isinstance(record, Mapping)
    ]
    from app.services import semantic_regression

    regression = semantic_regression.evaluate_evidence(
        poc_evidence,
        expected_regression_ids=(sample.get("oracle") or {}).get("regression_case_ids"),
    )
    if regression.decision == "rejected":
        verification = dict(verification)
        verification["decision"] = "rejected"
        verification["reason"] = (
            "semantic regression rejected the candidate: "
            + (regression.reason or "declared regression case mismatch")
        )
    engine_limitations = [
        str(item) for item in (_report_field(classified["report"], "limitations", []) or [])
        if str(item)
    ]
    deterministic_verified = bool(getattr(outcome, "verified", False))
    false_verified_internal = (
        deterministic_verified and verification.get("decision") == "rejected"
    )
    result = {
        "status": "executed",
        "detection": classified["detection"],
        "root_cause": classified["root_cause"],
        "localization": classified["localization"],
        "strategy": classified["strategy"],
        "candidate": candidate_bytes,
        "verification": verification,
        "regression": regression.regression,
        "environment": classified["environment"],
        "false_verified": bool(false_verified_internal),
        "false_verified_internal": bool(false_verified_internal),
        "not_run_reason": None,
        "semantic_regression": regression.to_dict(),
        "limitations": list(regression.limitations) + engine_limitations,
        "repair": classified,
        "guest_lock_attempts": guest_attempts,
    }
    execution["result"] = result
    return execution


def _run_repair(
    original: bytes,
    sample: Mapping[str, Any],
    *,
    root: Path,
    repair_fn: Callable[..., Any] | None,
) -> Any:
    if repair_fn is None:
        return _default_repair(original, sample, root=root)
    try:
        return repair_fn(original, sample, root=root)
    except TypeError:
        return repair_fn(original, sample)


# ---------------------------------------------------------------------------
# Aggregation / metrics
# ---------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _sample_view(execution: Mapping[str, Any]) -> dict[str, Any]:
    result = execution.get("result") or execution
    sample = execution.get("sample") or {}
    return {"sample": sample, "result": result}


def _aggregate_counts(views: list[Mapping[str, Any]]) -> dict[str, Any]:
    status_counts = {status: 0 for status in STATUSES}
    verified = rejected = false_verified = 0
    executed = verification_attempted = 0
    for view in views:
        result = view["result"]
        status = str(result.get("status") or "invalid")
        if status not in status_counts:
            status = "invalid"
        status_counts[status] += 1
        if status == "executed":
            executed += 1
        decision = str((result.get("verification") or {}).get("decision") or "not_run")
        if decision == "verified":
            verified += 1
        elif decision == "rejected":
            rejected += 1
        if status == "executed" and decision != "not_run":
            verification_attempted += 1
        if result.get("false_verified") is True:
            false_verified += 1
    return {
        "sample_count": len(views),
        "status_counts": status_counts,
        "verified_count": verified,
        "rejected_count": rejected,
        "false_verified_count": false_verified,
        "denominator": {
            "samples": len(views),
            "executed": executed,
            "verification_attempted": verification_attempted,
        },
    }


def _layer_metrics(views: list[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [
        view for view in views
        if is_eligible_repair_case(view["sample"]) and not is_analysis_only_sample(view["sample"])
    ]
    analysis_only = [
        view for view in views if is_analysis_only_sample(view["sample"])
    ]

    def metric(views_in: list[Mapping[str, Any]], key: str) -> dict[str, Any]:
        denominator = len(views_in)
        count = sum(
            1 for view in views_in if view["result"].get(key) is True
        )
        return {
            "count": count,
            "denominator": denominator,
            "rate": _rate(count, denominator),
        }

    counts = _aggregate_counts(views)
    layer = {
        "sample_count": len(views),
        "eligible_repair_cases": len(eligible),
        "status_counts": counts["status_counts"],
        "verification": {
            "verified": counts["verified_count"],
            "rejected": counts["rejected_count"],
            "attempted": counts["denominator"]["verification_attempted"],
        },
        "detection": metric(eligible, "detection"),
        "root_cause_match": metric(eligible, "root_cause"),
        "localization": metric(eligible, "localization"),
        "verified_repair": {
            "count": counts["verified_count"],
            "denominator": len(eligible),
            "rate": (
                None if counts["denominator"]["verification_attempted"] == 0
                else _rate(counts["verified_count"], len(eligible))
            ),
        },
        "false_verified_internal": sum(
            1 for view in views
            if view["result"].get("false_verified_internal") is True
        ),
        "analysis_only": {
            "sample_count": len(analysis_only),
            "detection": metric(analysis_only, "detection"),
        },
    }
    return layer


def _group_metrics(
    views: list[Mapping[str, Any]],
    key: str,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for view in views:
        value = str(view["sample"].get(key) or "unknown")
        groups.setdefault(value, []).append(view)
    return {name: _layer_metrics(items) for name, items in sorted(groups.items())}


def build_metrics(views: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Layered public metrics: overall + by format/arch/family.

    ``null`` rates mean the denominator is zero (not a measured 0 failure).
    """

    views = list(views)
    overall = _layer_metrics(views)
    return {
        "schema_version": 1,
        "kind": "phase8c_layered_metrics",
        "denominator_policy": (
            "verified_repair_rate = independently verified / eligible repair "
            "cases; eligible = expected_scope function|whole_program AND real "
            "runtime oracle AND judgeable expected behaviour.  analysis_only "
            "samples are excluded from repair rates and reported separately; "
            "a zero denominator yields null, never a fabricated 0."
        ),
        "overall": overall,
        "by_format": _group_metrics(views, "format"),
        "by_arch": _group_metrics(views, "arch"),
        "by_family": _group_metrics(views, "vulnerability_family"),
    }


def contract_sample(execution: Mapping[str, Any]) -> dict[str, Any]:
    """Project one execution into the C2 benchmark-results-v2 sample shape."""

    sample = execution.get("sample") or {}
    result = execution.get("result") or {}
    candidate = result.get("candidate")
    candidate_sha = _sha256_bytes(candidate) if candidate is not None else None
    verification = result.get("verification") or {}
    decision = str(verification.get("decision") or "not_run")
    if decision not in VERIFICATION_DECISIONS:
        decision = "not_run"
    evidence_sha = verification.get("evidence_sha256")
    if not _is_sha256(evidence_sha):
        evidence_sha = None
    environment = result.get("environment") or {}
    tier = str(environment.get("tier") or "unavailable")
    if tier not in {"native_run", "emulated_run", "static_only", "unavailable"}:
        tier = "unavailable"
    oracle_status = str(environment.get("oracle_status") or "not_run")
    if oracle_status not in {"executed", "not_run", "unavailable"}:
        oracle_status = "not_run"
    status = str(result.get("status") or "invalid")
    if status not in STATUSES:
        status = "invalid"
    detection = result.get("detection")
    root_cause = result.get("root_cause")
    localization = result.get("localization")
    regression = result.get("regression")
    strategy = result.get("strategy")
    return {
        "sample_id": str(sample.get("sample_id") or "?"),
        "status": status,
        "detection": detection if isinstance(detection, bool) else None,
        "root_cause": root_cause if isinstance(root_cause, bool) else None,
        "localization": localization if isinstance(localization, bool) else None,
        "strategy": str(strategy) if isinstance(strategy, str) and strategy else None,
        "candidate": {
            "produced": candidate_sha is not None,
            "sha256": candidate_sha,
        },
        "verification": {
            "decision": decision,
            "evidence_sha256": evidence_sha,
        },
        "regression": regression if isinstance(regression, bool) else None,
        "environment": {
            "tier": tier,
            "runner": environment.get("runner") if isinstance(
                environment.get("runner"), str) and environment.get("runner") else None,
            "oracle_status": oracle_status,
        },
        "false_verified": bool(result.get("false_verified")),
        "not_run_reason": (
            result.get("not_run_reason")
            if status in {"not_run", "blocked", "unsupported", "invalid"}
            else None
        ),
    }


def _withdraw_false_verified(views: list[Mapping[str, Any]]) -> int:
    """Withdraw every independently rejected deterministic claim (fail-closed).

    The published C2 contract must not retain a verified claim that the
    independent verifier rejected; the disagreement is recorded in the
    evidence layer and the run exits non-zero.
    """

    withdrawn = 0
    for view in views:
        result = view["result"]
        if result.get("false_verified_internal") is not True:
            continue
        result["false_verified"] = False
        result["deterministic_claim_withdrawn"] = True
        withdrawn += 1
    return withdrawn


def run_benchmark(
    *,
    root: Path = ROOT,
    manifest_path: str | Path = MANIFEST_PATH,
    split: str = "all",
    verifier_spec: str | Path | Any | None = "auto",
    repair_fn: Callable[..., Any] | None = None,
    guest: GuestRuntime | None = None,
    oracle_runner: Callable[..., Any] | None = None,
    claim_policy: str = "withdraw",
    run_id: str = "phase8c-public",
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the manifest and return the C2 results document + evidence.

    The return value is a private run bundle:
    ``{"ok", "exit_code", "results", "metrics", "evidence", "views",
       "false_verified_count", "withdrawn_count", "limitations", "manifest"}``.
    """

    if claim_policy not in CLAIM_POLICIES:
        raise BenchmarkError(f"unknown claim policy {claim_policy!r}")
    if split not in {"all", "dev", "validation"}:
        raise BenchmarkError(f"unknown split {split!r}")
    root = Path(root)
    if manifest is None:
        manifest = load_manifest(manifest_path, root=root)
    violations = validate_manifest_payload(manifest)
    if violations:
        raise ManifestError("; ".join(violations[:5]))
    manifest_path_resolved = Path(manifest_path)
    if not manifest_path_resolved.is_absolute():
        manifest_path_resolved = root / manifest_path_resolved
    manifest_sha = _sha256_file(manifest_path_resolved)
    verifier, verifier_status = load_verifier(verifier_spec, root=root)
    guest = guest or GuestRuntime()
    selected = [
        sample for sample in manifest["samples"]
        if split == "all" or sample.get("split") == split
    ]
    if not selected:
        raise BenchmarkError(f"split {split!r} selects no manifest samples")
    views: list[Mapping[str, Any]] = []
    for index, sample in enumerate(selected):
        execution = execute_sample(
            sample, root=root, repair_fn=repair_fn, verifier=verifier,
            guest=guest, oracle_runner=oracle_runner,
            run_id=f"{run_id}.{index}",
        )
        views.append(_sample_view(execution))
    false_verified_count = sum(
        1 for view in views
        if view["result"].get("false_verified_internal") is True
    )
    withdrawn = 0
    if claim_policy == "withdraw":
        withdrawn = _withdraw_false_verified(views)
    contract_samples = [contract_sample(view) for view in views]
    aggregate = _aggregate_counts(views)
    aggregate["false_verified_count"] = sum(
        1 for sample in contract_samples if sample["false_verified"] is True
    )
    limitations = [
        "deterministic repair evidence only: no AI provider and no network is "
        "used by this runner.",
        "verified_count counts independent-verifier decisions only; the "
        "deterministic engine's own gate is never accepted as verification.",
        FLAKE_LIMITATION,
    ]
    if not verifier_status.get("available"):
        limitations.append(
            "independent verifier unavailable: "
            + str(verifier_status.get("detail") or "not loaded")
        )
    if false_verified_count:
        limitations.append(
            f"{false_verified_count} deterministic verified claim(s) were "
            "rejected by the independent verifier"
            + (" and withdrawn from the published claim" if withdrawn else "")
        )
    results = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "benchmark_id": str(manifest.get("benchmark_id")),
        "manifest_sha256": manifest_sha,
        "generated_at": str(manifest.get("generated_at")),
        "samples": contract_samples,
        "aggregate": aggregate,
        "hidden_aggregate": None,
        "limitations": limitations,
    }
    metrics = build_metrics(views)
    metrics["independent_verifier"] = verifier_status
    metrics["claim_policy"] = claim_policy
    metrics["false_verified_internal"] = false_verified_count
    metrics["deterministic_claim_withdrawn"] = withdrawn
    evidence = {
        "schema_version": 1,
        "kind": "phase8c_run_evidence",
        "benchmark_id": str(manifest.get("benchmark_id")),
        "manifest_path": str(manifest_path_resolved.relative_to(root))
        if _is_relative_to(manifest_path_resolved, root) else str(manifest_path_resolved),
        "manifest_sha256": manifest_sha,
        "generated_at": str(manifest.get("generated_at")),
        "split": split,
        "verifier": verifier_status,
        "samples": [_public_sample_evidence(view) for view in views],
        "disagreements": [
            _disagreement(view) for view in views
            if view["result"].get("false_verified_internal") is True
        ],
        "limitations": list(limitations),
    }
    exit_code = 1 if false_verified_count else 0
    return {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "results": results,
        "metrics": metrics,
        "evidence": evidence,
        "views": views,
        "false_verified_count": false_verified_count,
        "withdrawn_count": withdrawn,
        "verifier": verifier_status,
        "manifest": dict(manifest),
        "manifest_sha256": manifest_sha,
        "limitations": limitations,
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _disagreement(view: Mapping[str, Any]) -> dict[str, Any]:
    sample = view["sample"]
    result = view["result"]
    return {
        "sample_id": str(sample.get("sample_id")),
        "deterministic_verified": True,
        "independent_decision": str(
            (result.get("verification") or {}).get("decision") or "not_run"
        ),
        "independent_reason": (result.get("verification") or {}).get("reason"),
        "claim_withdrawn": bool(result.get("deterministic_claim_withdrawn")),
    }


def _sanitize_public(value: Any, root: Path = ROOT) -> Any:
    """Strip absolute checkout/home prefixes from published evidence strings."""

    replacements = [(str(Path(root).resolve()), "<repo>"),
                    (str(Path.home()), "<home>")]
    if isinstance(value, str):
        for prefix, label in replacements:
            if prefix and prefix in value:
                value = value.replace(prefix, label)
        return value
    if isinstance(value, Mapping):
        return {str(key): _sanitize_public(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_public(item, root) for item in value]
    return value


def _public_sample_evidence(view: Mapping[str, Any]) -> dict[str, Any]:
    """Per-sample private evidence for the *public* artifact directory.

    Public samples are committed inputs, but the evidence record stays metadata
    only (no binary bytes); verifier reports are included when available.
    """

    sample = view["sample"]
    result = view["result"]
    repair = result.get("repair") or {}
    report = repair.get("report")
    verifier_report = (result.get("verification") or {}).get("report")
    evidence = {
        "sample_id": str(sample.get("sample_id")),
        "binary_sha256": str(sample.get("binary_sha256")),
        "status": result.get("status"),
        "disposition": repair.get("disposition"),
        "detection": result.get("detection"),
        "root_cause": result.get("root_cause"),
        "localization": result.get("localization"),
        "strategy": result.get("strategy"),
        "candidate_sha256": (
            _sha256_bytes(result["candidate"])
            if result.get("candidate") is not None else None
        ),
        "verification": {
            "decision": (result.get("verification") or {}).get("decision"),
            "evidence_sha256": (result.get("verification") or {}).get(
                "evidence_sha256"),
            "reason": (result.get("verification") or {}).get("reason"),
        },
        "regression": result.get("regression"),
        "semantic_regression": (
            (result.get("semantic_regression") or {}).get("decision")
        ),
        "environment": dict(result.get("environment") or {}),
        "false_verified": bool(result.get("false_verified")),
        "deterministic_claim_withdrawn": bool(
            result.get("deterministic_claim_withdrawn")),
        "not_run_reason": result.get("not_run_reason"),
        "guest_lock_attempts": list(result.get("guest_lock_attempts") or []),
        "limitations": list(result.get("limitations") or []),
    }
    if isinstance(verifier_report, Mapping) and verifier_report:
        evidence["verifier_report"] = dict(verifier_report)
    if isinstance(report, Mapping):
        evidence["report"] = {
            "disposition": report.get("disposition"),
            "status": report.get("status"),
            "strategy": report.get("strategy"),
            "error": report.get("error"),
            "universal": report.get("universal"),
        }
    return _sanitize_public(evidence)


# ---------------------------------------------------------------------------
# Public artifact writing
# ---------------------------------------------------------------------------


def public_artifact_files(run: Mapping[str, Any]) -> dict[str, bytes]:
    """Build the deterministic public artifact file map (relative path -> bytes)."""

    results_bytes = canonical_json(run["results"])
    files: dict[str, bytes] = {
        "results.json": results_bytes,
        "metrics.json": canonical_json(run["metrics"]),
        "README.md": _public_readme(run).encode("utf-8"),
    }
    for evidence in run["evidence"]["samples"]:
        sample_id = str(evidence["sample_id"])
        files[f"samples/{sample_id}/outcome.json"] = canonical_json(evidence)
        verifier_report = evidence.get("verifier_report")
        if isinstance(verifier_report, Mapping) and verifier_report:
            files[f"samples/{sample_id}/verifier-report.json"] = canonical_json(
                _sanitize_public(dict(verifier_report)))
        candidate_sha = evidence.get("candidate_sha256")
        if isinstance(candidate_sha, str) and candidate_sha:
            files[f"samples/{sample_id}/candidate.sha256"] = (
                candidate_sha + "\n").encode("ascii")
    if run["evidence"]["disagreements"]:
        files["disagreements.json"] = canonical_json(
            run["evidence"]["disagreements"])
    return files


def _public_readme(run: Mapping[str, Any]) -> str:
    results = run["results"]
    aggregate = results["aggregate"]
    metrics = run["metrics"]
    overall = metrics["overall"]
    lines = [
        "# Phase-8C public benchmark evidence (2026-11-16)",
        "",
        f"- benchmark_id: `{results['benchmark_id']}`",
        f"- manifest_sha256: `{results['manifest_sha256']}`",
        f"- generated_at: `{results['generated_at']}` (inherited from the fixed manifest)",
        f"- samples: {aggregate['sample_count']}",
        f"- status counts: `{json.dumps(aggregate['status_counts'], sort_keys=True)}`",
        f"- independently verified: {aggregate['verified_count']}",
        f"- independent rejected: {aggregate['rejected_count']}",
        f"- false_verified (published): {aggregate['false_verified_count']}",
        f"- false_verified (internal disagreements): "
        f"{run['false_verified_count']}",
        f"- deterministic claims withdrawn: {run['withdrawn_count']}",
        f"- repeats: {run.get('repeats')} (stable across repeats: "
        f"{run.get('stable_across_repeats')}; C1 flake policy records every "
        f"attempt, it never claims unconditional stability)",
        "",
        "## Layered metrics",
        "",
        "| layer | eligible repair cases | detection rate | root-cause rate | "
        "localization rate | verified repair rate |",
        "|---|---|---|---|---|---|",
    ]
    for label, layer in (
        ("overall", overall),
        *[(f"format:{name}", value) for name, value in metrics["by_format"].items()],
        *[(f"arch:{name}", value) for name, value in metrics["by_arch"].items()],
    ):
        def _fmt(metric: Mapping[str, Any]) -> str:
            rate = metric.get("rate")
            return "null" if rate is None else f"{rate:.4f}"

        lines.append(
            f"| {label} | {layer['eligible_repair_cases']} | "
            f"{_fmt(layer['detection'])} | {_fmt(layer['root_cause_match'])} | "
            f"{_fmt(layer['localization'])} | {_fmt(layer['verified_repair'])} |"
        )
    lines.extend([
        "",
        "## Reproduce",
        "",
        "```bash",
        "python scripts/run_phase8c_benchmark.py",
        "python scripts/run_phase8c_benchmark.py --check-artifact",
        "```",
        "",
        "## Limitations",
        "",
    ])
    lines.extend(f"- {item}" for item in results.get("limitations") or [])
    lines.extend([
        f"- {FLAKE_LIMITATION}",
        "- public artifacts contribute metadata evidence only: raw binary bytes "
        "are not duplicated here; the binary sha256 and committed fixture paths "
        "bind every sample.",
        "",
    ])
    return "\n".join(lines)


def write_public_artifacts(
    run: Mapping[str, Any],
    *,
    root: Path = ROOT,
    out_dir: str | Path = PUBLIC_ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write the deterministic public evidence directory (+ SUMS)."""

    root = Path(root)
    out = Path(out_dir)
    if not out.is_absolute():
        out = root / out
    files = public_artifact_files(run)
    sums_lines = []
    written: list[str] = []
    for relative, data in sorted(files.items()):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(relative)
        sums_lines.append(f"{_sha256_bytes(data)}  {relative}")
    sums_payload = ("\n".join(sums_lines) + "\n").encode("ascii")
    (out / "SHA256SUMS").write_bytes(sums_payload)
    written.append("SHA256SUMS")
    return {
        "out_dir": str(out),
        "files": written,
        "sha256sums": _sha256_bytes(sums_payload),
        "results_sha256": _sha256_bytes(files["results.json"]),
        "metrics_sha256": _sha256_bytes(files["metrics.json"]),
    }


def write_canonical_results(
    run: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> Path:
    """Write the committed C2 results document (full-split runs only)."""

    if run.get("results", {}).get("samples") is None:
        raise BenchmarkError("run has no results document")
    path = Path(root) / CANONICAL_RESULTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(run["results"]))
    return path


# ---------------------------------------------------------------------------
# Offline artifact check
# ---------------------------------------------------------------------------


def _check_contract_integration(root: Path) -> tuple[bool, str]:
    """Validate the committed results through the C2 contract checker (offline)."""

    try:
        from scripts.check_contract_schemas import run_check
    except Exception as exc:  # noqa: BLE001 - checker is optional in unit tests
        return False, f"C2 checker unavailable: {type(exc).__name__}: {exc}"
    try:
        report = run_check(root, check_sums=False)
    except Exception as exc:  # noqa: BLE001 - checker failure is a violation
        return False, f"C2 checker raised: {type(exc).__name__}: {exc}"
    for integration in report.get("integrations") or []:
        if integration.get("id") == "phase8c-results":
            status = integration.get("status")
            if status == "validated":
                return True, "phase8c-results validated by the C2 checker"
            return False, f"phase8c-results integration status={status!r}: " \
                          f"{integration.get('detail') or ''}"
    return False, "C2 checker did not report the phase8c-results integration"


def check_artifact(
    *,
    root: Path = ROOT,
    results_path: str | Path = CANONICAL_RESULTS_PATH,
    out_dir: str | Path = PUBLIC_ARTIFACT_DIR,
    hidden_aggregate_path: str | Path = HIDDEN_AGGREGATE_PATH,
    use_contract_check: bool = True,
) -> dict[str, Any]:
    """Validate the committed public/hidden artifacts offline (no execution)."""

    root = Path(root)
    results_file = Path(results_path)
    if not results_file.is_absolute():
        results_file = root / results_file
    artifact_dir = Path(out_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir
    checks: list[dict[str, Any]] = []
    violations: list[str] = []

    def record(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "ok": bool(ok), "detail": detail})
        if not ok:
            violations.append(f"{check_id}: {detail}")

    try:
        payload = _load_json(results_file)
    except BenchmarkError as exc:
        record("results.readable", False, str(exc))
        return {"ok": False, "violations": violations, "checks": checks}
    record("results.readable", isinstance(payload, Mapping),
           f"{results_file}")
    if not isinstance(payload, Mapping):
        return {"ok": False, "violations": violations, "checks": checks}
    results_sha = _sha256_file(results_file)
    checks.append({"id": "results.sha256", "ok": True, "detail": results_sha})

    # 1. Structural contract checks (mirrors the C2 results-v2 semantics).
    semantic_violations = _results_contract_violations(payload)
    record("results.contract", not semantic_violations,
           "; ".join(semantic_violations[:4]) or "contract shape and counts agree")
    if use_contract_check:
        ok, detail = _check_contract_integration(root)
        record("results.c2_checker", ok, detail)

    # 2. Manifest binding and sample coverage.
    try:
        manifest = load_manifest(MANIFEST_PATH, root=root)
    except BenchmarkError as exc:
        record("manifest.readable", False, str(exc))
        manifest = None
    if manifest is not None:
        manifest_sha = _sha256_file(root / MANIFEST_PATH)
        record("manifest.sha256", payload.get("manifest_sha256") == manifest_sha,
               f"results={payload.get('manifest_sha256')} committed={manifest_sha}")
        record("manifest.benchmark_id",
               payload.get("benchmark_id") == manifest.get("benchmark_id"),
               f"results={payload.get('benchmark_id')!r}")
        expected_ids = [str(sample.get("sample_id")) for sample in manifest["samples"]]
        actual_ids = [
            str(sample.get("sample_id")) for sample in payload.get("samples") or []
            if isinstance(sample, Mapping)
        ]
        record("results.sample_ids", sorted(actual_ids) == sorted(expected_ids),
               f"{len(actual_ids)} results vs {len(expected_ids)} manifest samples")
        record("results.generated_at",
               payload.get("generated_at") == manifest.get("generated_at"),
               "generated_at inherited from the fixed manifest")

    # 3. Aggregate consistency.
    aggregate = payload.get("aggregate") or {}
    samples = [sample for sample in payload.get("samples") or []
               if isinstance(sample, Mapping)]
    status_counts = {status: 0 for status in STATUSES}
    for sample in samples:
        status = str(sample.get("status"))
        if status in status_counts:
            status_counts[status] += 1
    record("aggregate.status_counts",
           aggregate.get("status_counts") == status_counts,
           json.dumps(status_counts, sort_keys=True))
    record("aggregate.sample_count", aggregate.get("sample_count") == len(samples),
           str(len(samples)))
    verified = sum(1 for sample in samples
                   if (sample.get("verification") or {}).get("decision") == "verified")
    rejected = sum(1 for sample in samples
                   if (sample.get("verification") or {}).get("decision") == "rejected")
    record("aggregate.verified_count", aggregate.get("verified_count") == verified,
           str(verified))
    record("aggregate.rejected_count", aggregate.get("rejected_count") == rejected,
           str(rejected))
    false_verified = sum(1 for sample in samples if sample.get("false_verified") is True)
    record("aggregate.false_verified_count",
           aggregate.get("false_verified_count") == false_verified,
           str(false_verified))
    record("aggregate.false_verified.published_zero", false_verified == 0,
           f"published false_verified={false_verified} (must be 0)")
    not_run_missing = [
        sample.get("sample_id") for sample in samples
        if sample.get("status") in {"not_run", "blocked", "unsupported", "invalid"}
        and not sample.get("not_run_reason")
    ]
    record("results.not_run_reason", not not_run_missing,
           f"samples without explicit reason: {not_run_missing[:3]}")

    # 4. Evidence directory consistency and SUMS.
    evidence_results = artifact_dir / "results.json"
    record("evidence.results_present", evidence_results.is_file(),
           str(evidence_results))
    if evidence_results.is_file():
        record("evidence.results_matches_canonical",
               _sha256_file(evidence_results) == results_sha,
               "artifact results.json must equal the committed results document")
    for name in ("metrics.json", "README.md", "SHA256SUMS"):
        record(f"evidence.{name}", (artifact_dir / name).is_file(),
               str(artifact_dir / name))
    sums_ok, sums_detail = _verify_sums(artifact_dir)
    record("evidence.SHA256SUMS", sums_ok, sums_detail)

    # 5. Hidden aggregate privacy + consistency.
    hidden_file = Path(hidden_aggregate_path)
    if not hidden_file.is_absolute():
        hidden_file = root / hidden_file
    hidden_aggregate = payload.get("hidden_aggregate")
    if hidden_file.is_file():
        ok, detail, hidden_counts, hidden_commitment = _check_hidden_aggregate(
            hidden_file, public_sample_ids={
                str(sample.get("sample_id")) for sample in samples
            },
        )
        record("hidden.aggregate", ok, detail)
        if ok:
            record("hidden.results_consistency",
                   hidden_aggregate == hidden_counts,
                   "results.hidden_aggregate must match the hidden aggregate file")
            manifest_commitment = (manifest or {}).get("hidden_commitment")
            if isinstance(manifest_commitment, Mapping):
                expected = manifest_commitment.get("commitment_sha256")
                record("hidden.commitment",
                       hidden_commitment == expected,
                       "hidden commitment digest must match the public manifest")
    else:
        record("hidden.results_consistency", hidden_aggregate is None,
               "no hidden aggregate file; results.hidden_aggregate must be null")

    return {
        "ok": not violations,
        "written": None,
        "results_sha256": results_sha,
        "artifact_dir": str(artifact_dir),
        "violations": violations,
        "checks": checks,
    }


def _results_contract_violations(payload: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    if payload.get("schema_version") != 2:
        violations.append("schema_version must be 2")
    if payload.get("kind") != KIND:
        violations.append(f"kind must be {KIND}")
    if not _is_sha256(payload.get("manifest_sha256")):
        violations.append("manifest_sha256 must be a sha256")
    if not isinstance(payload.get("generated_at"), str) or not payload.get("generated_at"):
        violations.append("generated_at is required")
    if not isinstance(payload.get("limitations"), list):
        violations.append("limitations must be an array")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        violations.append("samples must be a non-empty array")
        return violations
    required_sample = {
        "sample_id", "status", "detection", "root_cause", "localization",
        "strategy", "candidate", "verification", "regression", "environment",
        "false_verified", "not_run_reason",
    }
    for sample in samples:
        if not isinstance(sample, Mapping):
            violations.append("sample is not an object")
            continue
        missing = sorted(required_sample - set(sample))
        if missing:
            violations.append(f"{sample.get('sample_id')}: missing {missing}")
            continue
        if sample.get("status") not in STATUSES:
            violations.append(f"{sample.get('sample_id')}: bad status")
        decision = (sample.get("verification") or {}).get("decision")
        if decision not in VERIFICATION_DECISIONS:
            violations.append(f"{sample.get('sample_id')}: bad verification decision")
        if sample.get("status") in {"not_run", "blocked", "unsupported", "invalid"} \
                and not sample.get("not_run_reason"):
            violations.append(f"{sample.get('sample_id')}: missing not_run_reason")
        if sample.get("false_verified") is True and decision != "verified":
            violations.append(
                f"{sample.get('sample_id')}: false_verified requires a verified "
                "diagnosis (withdrawn claims are published as false_verified=false)")
    aggregate = payload.get("aggregate")
    if not isinstance(aggregate, Mapping):
        violations.append("aggregate is required")
    else:
        for key in (
            "sample_count", "status_counts", "verified_count", "rejected_count",
            "false_verified_count", "denominator",
        ):
            if key not in aggregate:
                violations.append(f"aggregate.{key} is required")
        if aggregate.get("sample_count") != len(samples):
            violations.append("aggregate.sample_count mismatch")
        denominator = aggregate.get("denominator") or {}
        if denominator.get("samples") != len(samples):
            violations.append("aggregate.denominator.samples mismatch")
        executed = sum(1 for sample in samples if sample.get("status") == "executed")
        if denominator.get("executed") != executed:
            violations.append("aggregate.denominator.executed mismatch")
        attempted = sum(
            1 for sample in samples
            if sample.get("status") == "executed"
            and (sample.get("verification") or {}).get("decision") != "not_run"
        )
        if denominator.get("verification_attempted") != attempted:
            violations.append("aggregate.denominator.verification_attempted mismatch")
    return violations


def _verify_sums(directory: Path) -> tuple[bool, str]:
    sums_path = directory / "SHA256SUMS"
    if not sums_path.is_file():
        return False, "SHA256SUMS missing"
    problems: list[str] = []
    listed: set[str] = set()
    for line in sums_path.read_text(encoding="ascii", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not _is_sha256(parts[0]):
            problems.append(f"malformed line: {line[:60]}")
            continue
        digest, relative = parts
        if relative in listed:
            problems.append(f"duplicate entry: {relative}")
            continue
        listed.add(relative)
        target = directory / relative
        if not target.is_file():
            problems.append(f"missing file: {relative}")
            continue
        if _sha256_file(target) != digest:
            problems.append(f"digest mismatch: {relative}")
    on_disk = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    missing = sorted(on_disk - listed)
    if missing:
        problems.append(f"unlisted files: {missing[:3]}")
    return (not problems), "; ".join(problems[:4]) or "all digests match"


# ---------------------------------------------------------------------------
# Hidden lane (aggregate only)
# ---------------------------------------------------------------------------


def load_hidden_manifest(hidden_root: str | Path) -> tuple[dict[str, Any], Path]:
    """Load the C4 private hidden manifest and validate path containment."""

    root = Path(hidden_root).expanduser()
    if root.is_dir():
        manifest_path = root / "hidden-manifest.json"
    else:
        manifest_path = root
        root = manifest_path.parent
    payload = _load_json(manifest_path)
    if not isinstance(payload, dict):
        raise ManifestError("hidden manifest is not an object")
    violations = _hidden_manifest_violations(payload, root)
    if violations:
        raise ManifestError("; ".join(violations[:5]))
    return payload, root


def _hidden_manifest_violations(payload: Mapping[str, Any], root: Path) -> list[str]:
    violations: list[str] = []
    if payload.get("kind") != HIDDEN_MANIFEST_KIND:
        violations.append(f"hidden manifest kind must be {HIDDEN_MANIFEST_KIND}")
    if payload.get("schema_version") != 1:
        violations.append("hidden manifest schema_version must be 1")
    if not _is_sha256(payload.get("public_manifest_sha256")):
        violations.append("hidden manifest public_manifest_sha256 is required")
    if not _is_sha256(payload.get("commitment_sha256")):
        violations.append("hidden manifest commitment_sha256 is required")
    samples = payload.get("samples")
    material = payload.get("material")
    if not isinstance(samples, list) or not samples:
        violations.append("hidden manifest samples must be a non-empty array")
        return violations
    if not isinstance(material, Mapping):
        violations.append("hidden manifest material must be an object")
        return violations
    seen: set[str] = set()
    for index, sample in enumerate(samples):
        where = f"hidden samples[{index}]"
        if not isinstance(sample, Mapping):
            violations.append(f"{where}: not an object")
            continue
        sample_id = sample.get("sample_id")
        if not _is_sha256(sample_id):
            violations.append(f"{where}: opaque sample_id must be a sha256")
            continue
        if sample_id in seen:
            violations.append(f"{where}: duplicate opaque sample_id")
        seen.add(sample_id)
        record = material.get(sample_id)
        if not isinstance(record, Mapping):
            violations.append(f"{where}: material entry missing")
            continue
        binary_path = record.get("binary_path")
        if not isinstance(binary_path, str) or not binary_path:
            violations.append(f"{where}: material.binary_path is required")
            continue
        resolved = (root / binary_path).resolve()
        if not _is_relative_to(resolved, root.resolve()):
            violations.append(f"{where}: binary path escapes the private root")
        if not resolved.is_file():
            violations.append(f"{where}: private binary is missing")
        oracle_path = record.get("oracle_path")
        if oracle_path is not None:
            if not isinstance(oracle_path, str) or not oracle_path:
                violations.append(f"{where}: material.oracle_path is invalid")
            else:
                oracle_resolved = (root / oracle_path).resolve()
                if not _is_relative_to(oracle_resolved, root.resolve()):
                    violations.append(f"{where}: oracle path escapes the private root")
        if not is_sha256_format(sample.get("binary_sha256")):
            violations.append(f"{where}: binary_sha256 is required")
    return violations


def is_sha256_format(value: Any) -> bool:
    return _is_sha256(value)


def run_hidden_lane(
    hidden_root: str | Path,
    *,
    root: Path = ROOT,
    public_manifest: Mapping[str, Any] | None = None,
    verifier_spec: str | Path | Any | None = "auto",
    repair_fn: Callable[..., Any] | None = None,
    guest: GuestRuntime | None = None,
    oracle_runner: Callable[..., Any] | None = None,
    claim_policy: str = "withdraw",
    run_id: str = "phase8c-hidden",
    collect_stage_attribution: bool = False,
) -> dict[str, Any]:
    """Execute the private hidden corpus and return only aggregate evidence.

    When ``collect_stage_attribution`` is true, a private per-sample stage
    diagnostic is added to the private report and a counts-only distribution is
    added to the public hidden aggregate.  Hidden ids/paths/bytes never enter
    the public file.
    """

    try:
        hidden_manifest, hidden_dir = load_hidden_manifest(hidden_root)
    except BenchmarkError as exc:
        return {
            "ok": False,
            "hidden_aggregate": None,
            "hidden_aggregate_file": None,
            "private_report_sha256": None,
            "limitations": [f"hidden lane not run: {exc}"],
            "exit_code": 2,
        }
    if public_manifest is None:
        public_manifest = load_manifest(MANIFEST_PATH, root=root)
    public_sha = _sha256_file(Path(root) / MANIFEST_PATH)
    if hidden_manifest.get("public_manifest_sha256") != public_sha:
        return {
            "ok": False,
            "hidden_aggregate": None,
            "hidden_aggregate_file": None,
            "private_report_sha256": None,
            "limitations": [
                "hidden lane not run: hidden manifest public_manifest_sha256 "
                "does not match the committed public manifest"
            ],
            "exit_code": 2,
        }
    commitment_path = Path(root) / HIDDEN_COMMITMENT_PATH
    commitment_sha = hidden_manifest.get("commitment_sha256")
    if not commitment_path.is_file():
        return {
            "ok": False,
            "hidden_aggregate": None,
            "hidden_aggregate_file": None,
            "private_report_sha256": None,
            "limitations": [
                "hidden lane not run: hidden commitment is missing "
                f"({HIDDEN_COMMITMENT_PATH}); no representative commitment, no "
                "aggregate is claimed"
            ],
            "exit_code": 2,
        }
    try:
        commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False, "hidden_aggregate": None, "hidden_aggregate_file": None,
            "private_report_sha256": None,
            "limitations": [f"hidden commitment unreadable: {type(exc).__name__}: {exc}"],
            "exit_code": 2,
        }
    if isinstance(commitment, Mapping) and commitment.get("commitment_sha256") != commitment_sha:
        return {
            "ok": False, "hidden_aggregate": None, "hidden_aggregate_file": None,
            "private_report_sha256": None,
            "limitations": [
                "hidden lane not run: commitment digest does not match the "
                "private hidden manifest"
            ],
            "exit_code": 2,
        }
    verifier, verifier_status = load_verifier(verifier_spec, root=root)
    guest = guest or GuestRuntime()
    material = hidden_manifest.get("material") or {}
    views: list[Mapping[str, Any]] = []
    executions: list[Mapping[str, Any]] = []
    for index, sample in enumerate(hidden_manifest["samples"]):
        record = material[sample["sample_id"]]
        binary = (hidden_dir / str(record["binary_path"])).resolve()
        oracle_path = record.get("oracle_path")
        sample_view = {**sample, "split": sample.get("split") or "validation"}
        execution = execute_sample(
            sample_view, root=hidden_dir, repair_fn=repair_fn, verifier=verifier,
            guest=guest, oracle_runner=oracle_runner,
            binary_path=binary,
            oracle_manifest_path=(
                str((hidden_dir / str(oracle_path)).resolve())
                if oracle_path else None
            ),
            run_id=f"{run_id}.{index}",
        )
        executions.append(execution)
        views.append(_sample_view(execution))
    stage_diagnostics: list[Mapping[str, Any]] = []
    stage_summary: Mapping[str, Any] | None = None
    if collect_stage_attribution:
        from app.services import hidden_stage_attribution

        stage_diagnostics = [
            hidden_stage_attribution.attribute_hidden_execution(
                sample, execution,
            )
            for sample, execution in zip(hidden_manifest["samples"], executions)
        ]
        stage_summary = hidden_stage_attribution.aggregate_stage_attribution(
            stage_diagnostics,
            sample_count=len(stage_diagnostics),
            runtime_count=sum(
                1 for item in stage_diagnostics
                if item.get("no_candidate_expected") is not True),
            analysis_only_count=sum(
                1 for item in stage_diagnostics
                if item.get("no_candidate_expected") is True),
        )
    false_verified_count = sum(
        1 for view in views
        if view["result"].get("false_verified_internal") is True
    )
    withdrawn = 0
    if claim_policy == "withdraw":
        withdrawn = _withdraw_false_verified(views)
    counts = _aggregate_counts(views)
    counts["false_verified_count"] = sum(
        1 for view in views if view["result"].get("false_verified") is True
    )
    aggregate = dict(counts)
    private_report = {
        "schema_version": 1,
        "kind": "phase8c_private_hidden_report",
        "benchmark_id": str(hidden_manifest.get("benchmark_id")),
        "commitment_sha256": commitment_sha,
        "public_manifest_sha256": public_sha,
        "samples": [
            {
                "opaque_sample_id": str(view["sample"].get("sample_id")),
                "status": view["result"].get("status"),
                "verification": {
                    "decision": (view["result"].get("verification") or {}).get(
                        "decision"),
                    "evidence_sha256": (view["result"].get("verification") or {}).get(
                        "evidence_sha256"),
                },
                "detection": view["result"].get("detection"),
                "root_cause": view["result"].get("root_cause"),
                "localization": view["result"].get("localization"),
                "false_verified_internal": bool(
                    view["result"].get("false_verified_internal")),
            }
            for view in views
        ],
        "limitations": [],
    }
    if stage_diagnostics:
        private_report["stage_attribution"] = [
            dict(item) for item in stage_diagnostics
        ]
        private_report["stage_attribution_summary"] = dict(stage_summary or {})
    private_report_sha = _sha256_bytes(_canonical(private_report))
    hidden_file = {
        "schema_version": 1,
        "kind": HIDDEN_AGGREGATE_KIND,
        "benchmark_id": hidden_manifest.get("benchmark_id"),
        "hidden_version": hidden_manifest.get("hidden_version"),
        "commitment_sha256": commitment_sha,
        "public_manifest_sha256": public_sha,
        "hidden_manifest_sha256": _sha256_bytes(_canonical(dict(hidden_manifest))),
        "private_report_sha256": private_report_sha,
        "generated_at": str(hidden_manifest.get("generated_at") or "hidden"),
        "sample_count": counts["sample_count"],
        "status_counts": counts["status_counts"],
        "verified_count": counts["verified_count"],
        "rejected_count": counts["rejected_count"],
        "false_verified_count": counts["false_verified_count"],
        "denominator": counts["denominator"],
        "aggregate": aggregate,
        "analysis_only": _layer_metrics(
            [view for view in views
             if is_analysis_only_sample(view["sample"])])["analysis_only"],
        "by_format": _group_metrics(views, "format"),
        "by_arch": _group_metrics(views, "arch"),
        "by_family": _group_metrics(views, "vulnerability_family"),
        "deterministic_claim_withdrawn": withdrawn,
        "false_verified_internal": false_verified_count,
        "limitations": [
            "hidden aggregate contains counts only: no per-sample ids, paths, "
            "bytes, candidate hashes or case details are published.",
            FLAKE_LIMITATION,
        ],
    }
    if stage_summary is not None:
        hidden_file["stage_attribution"] = dict(stage_summary)
        hidden_file["limitations"].append(
            "stage attribution is counts-only evidence; private per-sample "
            "diagnostics are retained under the private attribution artifact")
    return {
        "ok": false_verified_count == 0,
        "hidden_aggregate": aggregate,
        "hidden_aggregate_file": hidden_file,
        "private_report_sha256": private_report_sha,
        "hidden_manifest_sha256": hidden_file["hidden_manifest_sha256"],
        "commitment_sha256": commitment_sha,
        "false_verified_count": false_verified_count,
        "withdrawn_count": withdrawn,
        "verifier": verifier_status,
        "private_report": private_report,
        "stage_attribution": (
            dict(stage_summary) if stage_summary is not None else None),
        "limitations": list(hidden_file["limitations"]),
        "exit_code": 0 if false_verified_count == 0 else 1,
    }


def run_repeated(
    repeats: int,
    *,
    root: Path = ROOT,
    manifest_path: str | Path = MANIFEST_PATH,
    split: str = "all",
    verifier_spec: str | Path | Any | None = "auto",
    repair_fn: Callable[..., Any] | None = None,
    guest: GuestRuntime | None = None,
    oracle_runner: Callable[..., Any] | None = None,
    claim_policy: str = "withdraw",
    run_id: str = "phase8c-public",
) -> dict[str, Any]:
    """Run the benchmark ``repeats`` times and record the stability history.

    C1 warning ``B-POST-REBASE-REPRODUCTION-FLAKY`` forbids claiming
    unconditional stability from one run; the caller must publish every
    attempt.  The first attempt is canonical; any difference in the per-sample
    outcome digest marks the run as unstable (exit code 1) and records the
    history rather than hiding it.
    """

    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 1:
        raise BenchmarkError("repeats must be a positive integer")
    attempts: list[dict[str, Any]] = []
    canonical: dict[str, Any] | None = None
    for index in range(repeats):
        attempt = run_benchmark(
            root=root, manifest_path=manifest_path, split=split,
            verifier_spec=verifier_spec, repair_fn=repair_fn, guest=guest,
            oracle_runner=oracle_runner, claim_policy=claim_policy,
            run_id=f"{run_id}.r{index + 1}",
        )
        attempt_sha = _sha256_bytes(_canonical(attempt["results"]))
        attempts.append({
            "attempt": index + 1,
            "run_id": f"{run_id}.r{index + 1}",
            "results_sha256": attempt_sha,
            "exit_code": attempt["exit_code"],
            "status_counts": attempt["results"]["aggregate"]["status_counts"],
            "verified_count": attempt["results"]["aggregate"]["verified_count"],
            "false_verified_internal": attempt["false_verified_count"],
            "dispatch_order": [sample.get("sample_id")
                               for sample in attempt["results"]["samples"]],
        })
        if canonical is None:
            canonical = attempt
            canonical["results_sha256"] = attempt_sha
    assert canonical is not None
    stable = len({record["results_sha256"] for record in attempts}) == 1
    canonical["repeat_history"] = attempts
    canonical["stable_across_repeats"] = stable and repeats > 1
    canonical["repeats"] = repeats
    if not stable:
        canonical["limitations"].append(
            "repeat history differs across attempts: stability is NOT claimed "
            "(C1 B-POST-REBASE-REPRODUCTION-FLAKY); inspect repeat_history"
        )
        canonical["exit_code"] = 1
        canonical["ok"] = False
    canonical["evidence"]["repeat_history"] = attempts
    canonical["evidence"]["stable_across_repeats"] = bool(
        stable and repeats > 1)
    canonical["evidence"]["repeats"] = repeats
    canonical["metrics"]["repeat_history"] = attempts
    canonical["metrics"]["stable_across_repeats"] = bool(
        stable and repeats > 1)
    canonical["metrics"]["repeats"] = repeats
    return canonical


def attach_hidden_aggregate(
    run: Mapping[str, Any],
    hidden_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach a hidden-lane result to the public results document (counts only)."""

    counts = hidden_result.get("hidden_aggregate")
    results = run["results"]
    results["hidden_aggregate"] = counts if isinstance(counts, Mapping) else None
    limitations = results.setdefault("limitations", [])
    if isinstance(counts, Mapping):
        limitations.append(
            "hidden aggregate present: counts only, committed under the "
            "hidden aggregate path; no per-sample hidden ids/paths/content are "
            "published"
        )
    else:
        limitations.append(
            "hidden lane not run: " + "; ".join(
                str(item) for item in (hidden_result.get("limitations") or [])
            )
        )
    return run


def write_hidden_aggregate(
    hidden_result: Mapping[str, Any],
    *,
    path: str | Path = HIDDEN_AGGREGATE_PATH,
    root: Path = ROOT,
) -> Path | None:
    payload = hidden_result.get("hidden_aggregate_file")
    if not isinstance(payload, Mapping):
        return None
    target = Path(path)
    if not target.is_absolute():
        target = Path(root) / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json(payload))
    return target


def _check_hidden_aggregate(
    path: Path,
    *,
    public_sample_ids: set[str],
) -> tuple[bool, str, dict[str, Any] | None, Any]:
    try:
        payload = _load_json(path)
    except BenchmarkError as exc:
        return False, str(exc), None, None
    if not isinstance(payload, Mapping):
        return False, "hidden aggregate is not an object", None, None
    problems: list[str] = []
    if payload.get("kind") != HIDDEN_AGGREGATE_KIND:
        problems.append(f"kind must be {HIDDEN_AGGREGATE_KIND}")
    for key in (
        "sample_count", "status_counts", "verified_count", "rejected_count",
        "false_verified_count", "denominator", "commitment_sha256",
        "public_manifest_sha256", "private_report_sha256",
    ):
        if key not in payload:
            problems.append(f"missing {key}")
    aggregate = payload.get("aggregate")
    if isinstance(aggregate, Mapping):
        counts = {
            "sample_count": aggregate.get("sample_count"),
            "status_counts": aggregate.get("status_counts"),
            "verified_count": aggregate.get("verified_count"),
            "rejected_count": aggregate.get("rejected_count"),
            "false_verified_count": aggregate.get("false_verified_count"),
            "denominator": aggregate.get("denominator"),
        }
        for key, value in counts.items():
            if payload.get(key) != value:
                problems.append(f"{key} disagrees with aggregate")
    else:
        counts = None
    forbidden_keys = {"sample_id", "binary_path", "oracle_path",
                      "reference_fix_path", "case_id", "candidate_sha256"}
    if isinstance(payload.get("samples"), list):
        leaked_top_level = True
    else:
        leaked_top_level = False
    leaked_paths: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            if "/" in value or "\\" in value:
                leaked_paths.append(value)
            if value in public_sample_ids:
                leaked_paths.append(value)
        elif isinstance(value, Mapping):
            for key, item in value.items():
                if str(key) in forbidden_keys:
                    leaked_paths.append(str(key))
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    if leaked_top_level:
        leaked_paths.append("samples[]")
    if leaked_paths:
        problems.append(f"hidden aggregate leaks ids/paths/content: {leaked_paths[:3]}")
    return (not problems), "; ".join(problems[:4]) or "privacy and counts ok", \
        counts if isinstance(counts, Mapping) else None, payload.get("commitment_sha256")


__all__ = [
    "BenchmarkError",
    "attach_hidden_aggregate",
    "CANONICAL_RESULTS_PATH",
    "FLAKE_LIMITATION",
    "GuestRuntime",
    "HIDDEN_AGGREGATE_PATH",
    "HIDDEN_COMMITMENT_PATH",
    "KIND",
    "MANIFEST_PATH",
    "ManifestError",
    "PUBLIC_ARTIFACT_DIR",
    "SCHEMA_VERSION",
    "build_metrics",
    "canonical_json",
    "check_artifact",
    "classify_repair_outcome",
    "contract_sample",
    "execute_sample",
    "is_analysis_only_sample",
    "is_eligible_repair_case",
    "is_judgeable_expected_behavior",
    "is_runtime_oracle_sample",
    "load_hidden_manifest",
    "load_manifest",
    "load_oracle_manifest",
    "load_verifier",
    "public_artifact_files",
    "resolve_target_argument",
    "run_benchmark",
    "run_hidden_lane",
    "run_independent_verification",
    "run_repeated",
    "sample_binary_path",
    "validate_manifest_payload",
    "write_canonical_results",
    "write_hidden_aggregate",
    "write_public_artifacts",
]
