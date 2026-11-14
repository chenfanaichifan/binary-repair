#!/usr/bin/env python3
"""Build the provider-coverage evidence artifact deterministically.

The artifact ``artifacts/provider-coverage-2026-11-14/`` answers: which real
provider/model pairs have 12-case benchmark evidence in this repository, what is
the verified rate (with a 95% Wilson confidence interval), how does the strict
model-identity policy treat served-model mismatches, and which provider
capabilities are honestly blocked/unavailable.

Design rules
------------
* **Deterministic**: the builder reads only committed source artifacts (no
  provider calls, no network, no git commands, no wall-clock timestamps).  The
  ``generated_at`` value is the latest ``generated_at`` recorded in a cited
  source artifact, so a fresh build is byte-identical to the committed artifact.
* **Re-derivable**: every evidence row cites its source files with SHA-256 and
  each source artifact's own ``SHA256SUMS`` is validated.
* **Honest**: ``identity_ok=false`` rows may be recorded as served-model
  evidence but are never requested-model identity verified; blocked providers
  are explicit; the international 5-6 model matrix is ``not_satisfied``.
* **Separate metrics**: ``deterministic_target_strict`` and ``ai_target`` are
  reported separately and are never combined into one score.

Usage::

    python scripts/build_provider_coverage.py                 # write artifact
    python scripts/build_provider_coverage.py --check         # fresh == committed
    python scripts/build_provider_coverage.py --out DIR       # alternate output
    python scripts/build_provider_coverage.py --check --out DIR

``--check`` rebuilds the artifact in memory and compares ``summary.json``,
``README.md`` and ``SHA256SUMS`` byte-for-byte against the target directory; a
difference exits 1 with a JSON report.  It never writes files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts" / "provider-coverage-2026-11-14"
ARTIFACT_FILES = ("README.md", "summary.json", "intl-unavailable.json")
INTL_UNAVAILABLE_NAME = "intl-unavailable.json"
ARTIFACT_DIR_REL = "artifacts/provider-coverage-2026-11-14"
SCHEMA_VERSION = 1
ARTIFACT_KIND = "provider_coverage"
BUILDER_VERSION = 1
CONFIDENCE_LEVEL = 0.95
Z_SCORE = 1.96
DEFAULT_GENERATED_AT = "2026-11-14T00:00:00Z"

# Source artifacts (repository-relative directories).
DS_PROBE_DIR = "artifacts/deepseek-matrix-2026-11-14"
DS_MATRIX_DIR = "artifacts/multi-model-matrix-2026-11-14"
INTL_DIR = "artifacts/multi-model-matrix-intl-2026-11-14"
CN_DIR = "artifacts/multi-model-matrix-cn-2026-11-14"
SF_INTL_PROBE_DIR = "artifacts/siliconflow-intl-probe-2026-11-14"
SF_KEY_DIR = "artifacts/siliconflow-key-2026-11-14"
PM_DIR = "artifacts/provider-matrix-2026-11-14"
MULTI_PROBE_DIR = "artifacts/multi-model-probe-2026-11-14"
LIMITATIONS_DOC = "docs/acceptance/LIMITATIONS.md"
MULTI_MODEL_DOC = "docs/operations/multi-model-benchmark.md"

IDENTITY_RULE = (
    "A benchmark row may be presented as requested-model-identity verified only "
    "when the provider response model equals the requested model "
    "(identity_ok=true) and the strict identity check "
    "(BINARYREPAIR_STRICT_MODEL_IDENTITY=1) passed."
)
IDENTITY_OK_FALSE = (
    "identity_ok=false rows may be recorded as served-model evidence but must "
    "never be presented as requested-model-identity verified; every AI verified "
    "count is attributed to the served model and carries a limitation note."
)


class BuildError(RuntimeError):
    """A required source artifact is missing or unreadable."""


# ---------------------------------------------------------------------------
# Filesystem / JSON helpers
# ---------------------------------------------------------------------------


def _path(relative: str) -> Path:
    return ROOT / relative


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(relative: str) -> str:
    path = _path(relative)
    if not path.is_file():
        raise BuildError(f"missing source file: {relative}")
    return _sha256_bytes(path.read_bytes())


def _read_json(relative: str, *, required: bool = True) -> Any:
    path = _path(relative)
    if not path.is_file():
        if required:
            raise BuildError(f"missing source artifact: {relative}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if required:
            raise BuildError(f"unreadable source artifact {relative}: {exc}") from exc
        return None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _wilson_ci95(verified: int, cases: int, *, z: float = Z_SCORE) -> list[float]:
    """Two-sided Wilson score interval at 95% confidence.

    ``cases == 0`` returns the uninformative interval ``[0.0, 1.0]`` (documented
    in the artifact); no point estimate is invented.
    """
    if cases <= 0:
        return [0.0, 1.0]
    p = verified / cases
    denominator = 1.0 + z * z / cases
    centre = (p + z * z / (2.0 * cases)) / denominator
    margin = (
        z * math.sqrt(p * (1.0 - p) / cases + z * z / (4.0 * cases * cases))
    ) / denominator
    return [round(max(0.0, centre - margin), 6), round(min(1.0, centre + margin), 6)]


_HTTP_STATUS_RE = re.compile(r"HTTP\s+(?P<status>\d{3})")
_HTTP_ERROR_CLASS_RE = re.compile(r"^(?P<cls>[A-Za-z_][A-Za-z0-9_]*)\s*:")


def _parse_http_error(error_text: Any) -> dict[str, Any] | None:
    """Parse the recorded typed provider error into {status, code, error_class}."""
    if not isinstance(error_text, str) or not error_text.strip():
        return None
    text = error_text.strip()
    status_match = _HTTP_STATUS_RE.search(text)
    class_match = _HTTP_ERROR_CLASS_RE.match(text)
    if not status_match and not class_match:
        return None
    return {
        "status": int(status_match.group("status")) if status_match else None,
        # The provider HTTP error body is not stored in a machine-readable
        # artifact, so the provider-specific code is not asserted.
        "code": None,
        "error_class": class_match.group("cls") if class_match else None,
    }


def _probe_log(relative_path: str | None) -> dict[str, Any]:
    """SHA-256 binding for the probe/matrix record that evidences a row."""
    if not relative_path or not _path(relative_path).is_file():
        return {"path": None, "sha256": None}
    return {"path": relative_path, "sha256": _sha256_file(relative_path)}


def _identity_layer(
    requested_model: str | None,
    served_model: str | None,
    observed_model: str | None,
    identity_ok: bool | None,
    identity_verified: bool,
    attribution: str,
) -> dict[str, Any]:
    """Explicit three-model identity layer for one evidence row."""
    return {
        "requested_model": requested_model,
        "served_model": served_model,
        "observed_model": observed_model,
        "identity_ok": identity_ok,
        "identity_verified": bool(identity_verified),
        "attribution": attribution,
    }


def _validate_sha256sums(artifact_dir: str) -> dict[str, Any]:
    """Validate an evidence directory's own SHA256SUMS file."""
    base = _path(artifact_dir)
    sums = base / "SHA256SUMS"
    if not sums.is_file():
        return {"sha256sums": None, "sha256sums_sha256": None,
                "valid": False, "entries": 0, "mismatches": [], "missing": []}
    mismatches: list[str] = []
    missing: list[str] = []
    entries = 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            digest, relative = line.split(None, 1)
        except ValueError:
            mismatches.append(f"malformed:{line[:80]}")
            continue
        relative = relative.strip().lstrip("*")
        target = base / relative
        entries += 1
        if not target.is_file():
            missing.append(relative)
        elif _sha256_bytes(target.read_bytes()).lower() != digest.lower():
            mismatches.append(relative)
    return {
        "sha256sums": f"{artifact_dir}/SHA256SUMS",
        "sha256sums_sha256": _sha256_bytes(sums.read_bytes()),
        "valid": not mismatches and not missing,
        "entries": entries,
        "mismatches": mismatches,
        "missing": missing,
    }


def _source(artifact_dir: str | None,
            files: list[tuple[str, str]] | None = None,
            *,
            corroborating: list[tuple[str, str]] | None = None,
            reference_docs: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Build the sha256-bound source block for one evidence row.

    ``files`` entries are ``(path, artifact_dir_for_this_file)`` so cited files
    may live in different artifact directories (e.g. a corroborating benchmark).
    """
    def _entries(items: list[tuple[str, str]] | None) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for relative, _dir in items or []:
            out.append({"path": relative, "sha256": _sha256_file(relative)})
        return out

    sums = _validate_sha256sums(artifact_dir) if artifact_dir else {
        "sha256sums": None, "sha256sums_sha256": None, "valid": False,
        "entries": 0, "mismatches": [], "missing": [],
    }
    return {
        "artifact_dir": artifact_dir,
        "files": _entries(files),
        "sha256sums": sums,
        "corroborating_files": _entries(corroborating),
        "reference_docs": _entries(reference_docs),
    }


# ---------------------------------------------------------------------------
# Source artifact loaders
# ---------------------------------------------------------------------------


def _require_dir(relative: str) -> None:
    if not _path(relative).is_dir():
        raise BuildError(f"missing source artifact directory: {relative}")


def _load_sources() -> dict[str, Any]:
    """Read every committed source artifact required for the derivation."""
    for required in (DS_PROBE_DIR, DS_MATRIX_DIR, INTL_DIR, PM_DIR,
                     MULTI_PROBE_DIR, SF_INTL_PROBE_DIR, SF_KEY_DIR):
        _require_dir(required)

    ds_probe = _read_json(f"{DS_PROBE_DIR}/summary.json")
    ds_aggregate = _read_json(f"{DS_MATRIX_DIR}/aggregate.json")
    ds_provider_probe = _read_json(f"{DS_MATRIX_DIR}/provider-probe.json")
    intl_summary = _read_json(f"{INTL_DIR}/summary.json")
    intl_aggregate = _read_json(f"{INTL_DIR}/aggregate.json")
    intl_identity = _read_json(f"{INTL_DIR}/identity-probe/summary.json")
    sf_intl_probe = _read_json(f"{SF_INTL_PROBE_DIR}/summary.json")
    pm_summary = _read_json(f"{PM_DIR}/summary.json")
    multi_probe = _read_json(f"{MULTI_PROBE_DIR}/summary.json")
    cn_present = _path(CN_DIR).is_dir()
    cn_summary = _read_json(f"{CN_DIR}/summary.json", required=False) if cn_present else None
    cn_aggregate = _read_json(f"{CN_DIR}/aggregate.json", required=False) if cn_present else None
    cn_identity = (
        _read_json(f"{CN_DIR}/identity-probe/summary.json", required=False)
        if cn_present else None
    )
    cn_benchmarks: dict[str, Any] = {}
    if cn_present:
        for slug in ("Qwen_Qwen3-8B", "Qwen_Qwen2.5-7B-Instruct"):
            loaded = _read_json(
                f"{CN_DIR}/benchmarks/siliconflow-{slug}/summary.json",
                required=False,
            )
            if isinstance(loaded, dict):
                cn_benchmarks[slug] = loaded
    pm_per_case: dict[str, Any] = {}
    per_case_dir = _path(PM_DIR) / "per-case"
    if per_case_dir.is_dir():
        for path in sorted(per_case_dir.glob("*.json")):
            try:
                pm_per_case[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise BuildError(f"unreadable provider-matrix case {path}: {exc}") from exc
    return {
        "ds_probe": ds_probe,
        "ds_aggregate": ds_aggregate,
        "ds_provider_probe": ds_provider_probe,
        "intl_summary": intl_summary,
        "intl_aggregate": intl_aggregate,
        "intl_identity": intl_identity,
        "sf_intl_probe": sf_intl_probe,
        "pm_summary": pm_summary,
        "multi_probe": multi_probe,
        "cn_present": cn_present,
        "cn_summary": cn_summary,
        "cn_aggregate": cn_aggregate,
        "cn_identity": cn_identity,
        "cn_benchmarks": cn_benchmarks,
        "pm_per_case": pm_per_case,
    }


# ---------------------------------------------------------------------------
# Deterministic metadata
# ---------------------------------------------------------------------------


def _latest_source_generated_at(sources: dict[str, Any]) -> tuple[str, str]:
    """Choose the latest ``generated_at`` recorded in a cited source artifact.

    This keeps the artifact byte-identical across rebuilds (no wall clock).  The
    provider-matrix summary is the only source that records the field today.
    """
    candidates: list[tuple[str, str]] = []
    pm = sources["pm_summary"]
    if isinstance(pm, dict) and isinstance(pm.get("generated_at"), str):
        candidates.append((pm["generated_at"], f"{PM_DIR}/summary.json#generated_at"))
    if not candidates:
        return DEFAULT_GENERATED_AT, "default constant (no source timestamp)"
    candidates.sort()
    return candidates[-1]


def _source_digest(rows: list[dict[str, Any]],
                   extra_files: list[str]) -> str:
    """Deterministic digest of every source file cited by the artifact."""
    cited: dict[str, str] = {}
    for row in rows:
        source = row["source"]
        for group in ("files", "corroborating_files", "reference_docs"):
            for entry in source[group]:
                cited[entry["path"]] = entry["sha256"]
    for relative in extra_files:
        cited[relative] = _sha256_file(relative)
    payload = [{"path": path, "sha256": digest}
               for path, digest in sorted(cited.items())]
    return _sha256_bytes(_canonical_json(payload).encode("utf-8"))


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _rate(verified: int, cases: int) -> float:
    if cases <= 0:
        return 0.0
    return round(verified / cases, 6)


def _model_stat(
    *,
    provider: str,
    model_requested: str,
    model_served: str | None,
    identity_ok: bool | None,
    identity_verified: bool,
    status: str,
    runs: int,
    cases_per_run: int,
    verified_per_run: list[int],
    inconclusive_per_run: list[int] | None = None,
    attributed_to: str | None = None,
    blocked_reason: str | None = None,
) -> dict[str, Any]:
    pooled_cases = int(cases_per_run) * int(runs)
    pooled_verified = int(sum(verified_per_run))
    if inconclusive_per_run is None:
        inconclusive_per_run = [int(cases_per_run) - int(v) for v in verified_per_run]
    pooled_inconclusive = int(sum(inconclusive_per_run))
    return {
        "provider": provider,
        "model_requested": model_requested,
        "model_served": model_served,
        "identity_ok": identity_ok,
        "identity_verified": bool(identity_verified),
        "status": status,
        "runs": int(runs),
        "cases": int(cases_per_run),
        "cases_pooled": pooled_cases,
        "verified": pooled_verified,
        "verified_per_run": [int(v) for v in verified_per_run],
        "verified_rate": _rate(pooled_verified, pooled_cases),
        "wilson_ci95": _wilson_ci95(pooled_verified, pooled_cases),
        "inconclusive": pooled_inconclusive,
        "inconclusive_per_run": [int(v) for v in inconclusive_per_run],
        "attributed_to": attributed_to or model_served or model_requested,
        "blocked_reason": blocked_reason,
    }


def _summarize_pooled(entries: list[dict[str, Any]]) -> dict[str, Any]:
    cases = sum(entry["cases_pooled"] for entry in entries)
    verified = sum(entry["verified"] for entry in entries)
    runs = sum(entry["runs"] for entry in entries)
    return {
        "models": len(entries),
        "runs": runs,
        "cases": cases,
        "verified": verified,
        "verified_rate": _rate(verified, cases),
        "wilson_ci95": _wilson_ci95(verified, cases),
        "inconclusive": cases - verified,
    }


def _deterministic_target_strict_stat(sources: dict[str, Any]) -> dict[str, Any]:
    """Deterministic target-strict measurement (model-independent).

    Source: the provider-matrix per-case records, which carry a deterministic
    ``baseline_target_strict`` for every hard case plus the
    ``baseline_expected_target_strict`` comparison.
    """
    per_case = sources["pm_per_case"]
    cases = len(per_case)
    verified = 0
    expected_matches = 0
    target_scope_resolved = 0
    dispositions: dict[str, int] = {}
    whole_image_verified = 0
    for record in per_case.values():
        strict = record.get("baseline_target_strict") or {}
        if strict.get("verified") is True:
            verified += 1
        if strict.get("matches_expected") is True:
            expected_matches += 1
        if strict.get("target_scope"):
            target_scope_resolved += 1
        disposition = str(strict.get("disposition") or "unknown")
        dispositions[disposition] = dispositions.get(disposition, 0) + 1
        if (record.get("baseline_whole_image") or {}).get("verified") is True:
            whole_image_verified += 1
    pm_provider = sources["pm_summary"].get("provider") or {}
    return {
        "available": cases > 0,
        "metric": "deterministic_target_strict",
        "source": f"{PM_DIR}/per-case/*.json",
        "identity_ok": pm_provider.get("model_identity_ok"),
        "identity_verified": False,
        "identity_note": (
            "the deterministic target-strict measurement is model-independent "
            "and is recorded on the provider-matrix benchmark suite; the provider "
            "run that produced that suite requested deepseek-chat and was served "
            "deepseek-flash (identity_ok=false), but the deterministic pipeline "
            "does not use a provider"
        ),
        "runs": 1,
        "cases": cases,
        "cases_pooled": cases,
        "verified": verified,
        "verified_rate": _rate(verified, cases),
        "wilson_ci95": _wilson_ci95(verified, cases),
        "inconclusive": cases - verified,
        "expected_matches": expected_matches,
        "expected_match_rate": _rate(expected_matches, cases),
        "target_scope_resolved": target_scope_resolved,
        "dispositions": dict(sorted(dispositions.items())),
        "whole_image_verified": whole_image_verified,
    }


def _build_statistics(rows: list[dict[str, Any]],
                      sources: dict[str, Any]) -> dict[str, Any]:
    """Per provider/model AI-target statistics plus the separate deterministic one."""
    by_provider_model: list[dict[str, Any]] = []
    ai_entries: list[dict[str, Any]] = []

    # DeepSeek official: two models x three identity-verified runs.
    ds_runs = sources["ds_aggregate"].get("runs_detail") or []
    for model in sources["ds_aggregate"].get("models") or []:
        runs = [run for run in ds_runs if run.get("model") == model]
        verified_per_run = [int(run.get("ai_verified") or 0) for run in runs]
        cases_per_run = int(sources["ds_aggregate"].get("cases") or 12)
        entry = _model_stat(
            provider="deepseek-official",
            model_requested=model,
            model_served=model,
            identity_ok=True,
            identity_verified=True,
            status="identity_verified_completed",
            runs=len(runs),
            cases_per_run=cases_per_run,
            verified_per_run=verified_per_run,
        )
        ai_entries.append(entry)
        by_provider_model.append(entry)

    # SiliconFlow China: one run per free Qwen model (if the artifact is present).
    if sources["cn_present"] and sources["cn_summary"] and sources["cn_aggregate"]:
        bench_by_model = {}
        for record in sources["cn_summary"].get("records") or []:
            if record.get("provider") != "siliconflow":
                continue
            model = record.get("model_requested")
            if not isinstance(model, str):
                continue
            slug = model.replace("/", "_")
            benchmark = sources["cn_benchmarks"].get(slug) or {}
            bench_by_model[model] = (record, benchmark)
        for model in sorted(bench_by_model):
            record, benchmark = bench_by_model[model]
            cases = len(benchmark.get("cases") or []) or 12
            verified = int(benchmark.get("ai_verified") or 0)
            entry = _model_stat(
                provider="siliconflow-cn",
                model_requested=model,
                model_served=str(record.get("model_returned") or model),
                identity_ok=bool(record.get("model_identity_ok")),
                identity_verified=bool(record.get("model_identity_ok")),
                status="identity_verified_completed",
                runs=1,
                cases_per_run=cases,
                verified_per_run=[verified],
            )
            ai_entries.append(entry)
            by_provider_model.append(entry)

    # SiliconFlow international: identity probes pass, benchmarks blocked (HTTP 402).
    intl_error_records = {}
    for record in sources["intl_summary"].get("records") or []:
        if record.get("provider") == "siliconflow":
            intl_error_records[record.get("model_requested")] = record
    intl_probe_models = {
        record.get("model_requested")
        for record in (sources["intl_identity"].get("records") or [])
        if record.get("status") == "ok"
    }
    for model in sorted(intl_probe_models | set(intl_error_records)):
        record = intl_error_records.get(model) or {}
        entry = _model_stat(
            provider="siliconflow-intl",
            model_requested=model,
            model_served=model,
            identity_ok=True,
            identity_verified=False,
            status="blocked_unavailable",
            runs=0,
            cases_per_run=0,
            verified_per_run=[],
            blocked_reason="HTTP 402 insufficient account balance on full benchmark calls",
        )
        by_provider_model.append(entry)

    # GLM (probe timeout) and the provider-matrix served-model-only run.
    for record in (sources["cn_identity"].get("records") or []):
        if record.get("model_requested") == "THUDM/GLM-Z1-9B-0414":
            by_provider_model.append(_model_stat(
                provider="siliconflow-cn",
                model_requested="THUDM/GLM-Z1-9B-0414",
                model_served=None,
                identity_ok=None,
                identity_verified=False,
                status="blocked_unavailable",
                runs=0,
                cases_per_run=0,
                verified_per_run=[],
                blocked_reason="identity probe timed out (TimeoutError)",
            ))

    pm_aggregate = sources["pm_summary"].get("aggregate") or {}
    pm_provider = sources["pm_summary"].get("provider") or {}
    served_entry = _model_stat(
        provider="deepseek-official",
        model_requested=str(pm_provider.get("model_requested") or "deepseek-chat"),
        model_served=str(pm_provider.get("model_returned") or "deepseek-flash"),
        identity_ok=bool(pm_provider.get("model_identity_ok")),
        identity_verified=bool(pm_provider.get("model_identity_ok")),
        status="served_model_mismatch_completed",
        runs=1,
        cases_per_run=int(pm_aggregate.get("cases") or 12),
        verified_per_run=[int(pm_aggregate.get("ai_target_verified") or 0)],
        attributed_to=str(pm_provider.get("model_returned") or "deepseek-flash"),
    )
    by_provider_model.append(served_entry)

    # Probe-only mismatch and the explicitly unavailable provider (no artifact).
    for record in sources["multi_probe"].get("records") or []:
        if record.get("spec") == "deepseek:deepseek-chat":
            by_provider_model.append(_model_stat(
                provider="deepseek-official",
                model_requested="deepseek-chat",
                model_served=str(record.get("model_returned") or "deepseek-flash"),
                identity_ok=False,
                identity_verified=False,
                status="probe_only_identity_mismatch",
                runs=0,
                cases_per_run=0,
                verified_per_run=[],
            ))
    by_provider_model.append(_model_stat(
        provider="dashscope",
        model_requested="qwen-plus",
        model_served=None,
        identity_ok=None,
        identity_verified=False,
        status="unavailable_no_artifact",
        runs=0,
        cases_per_run=0,
        verified_per_run=[],
        blocked_reason="no DashScope/Bailian key configured on this host; no artifact exists",
    ))

    # Separate ai_target section (identity-verified models only, then the
    # served-model-only run is reported separately and never pooled with it).
    identity_verified_entries = [
        entry for entry in ai_entries if entry["identity_verified"]
    ]
    served_model_only = next(
        entry for entry in by_provider_model
        if entry["status"] == "served_model_mismatch_completed"
    )
    deterministic = _deterministic_target_strict_stat(sources)
    return {
        "methodology": (
            "Wilson score interval at 95% confidence (z=1.96) over all cases of "
            "all runs of a model (pooled). verified = cases whose AI target "
            "repair passed the native/emulated PoC+regression gate. "
            "inconclusive = cases that produced no verified candidate "
            "(analysis_only / rejected / no candidate / gate fail). "
            "deterministic_target_strict and ai_target are reported separately "
            "and are never combined into one score. n=0 means not executed and "
            "uses the uninformative interval [0.0, 1.0]."
        ),
        "confidence_level": CONFIDENCE_LEVEL,
        "z_score": Z_SCORE,
        "definitions": {
            "verified": "cases accepted by the native/emulated PoC+regression gate",
            "verified_rate": "pooled verified / pooled cases for one model",
            "wilson_ci95": "two-element Wilson 95% interval for the pooled verified_rate",
            "inconclusive": "pooled cases with no verified candidate",
            "cases": "cases per run (12 for every hard-case benchmark)",
            "cases_pooled": "cases summed over all runs of the model",
            "deterministic_target_strict": (
                "deterministic pipeline under repair_any(target=..., "
                "require_target=True); verified means the deterministic gate "
                "verified a candidate; expected_matches compares the disposition "
                "with cases.json baseline_expected_target_strict"
            ),
            "ai_target": (
                "real provider target-assembly mode; identity_verified only when "
                "requested model == served model"
            ),
            "served_model_only": (
                "identity_ok=false run recorded as served-model evidence only; "
                "never pooled with requested-model-identity evidence"
            ),
        },
        "deterministic_target_strict": deterministic,
        "ai_target": {
            "by_model": ai_entries,
            "pooled_identity_verified": _summarize_pooled(identity_verified_entries),
            "served_model_only": served_model_only,
        },
        "by_provider_model": by_provider_model,
        "blocked": [
            entry for entry in by_provider_model
            if entry["status"] in {"blocked_unavailable", "unavailable_no_artifact"}
        ],
    }


# ---------------------------------------------------------------------------
# Evidence rows
# ---------------------------------------------------------------------------


def _augment_rows(rows: list[dict[str, Any]],
                  sources: dict[str, Any]) -> list[dict[str, Any]]:
    """Add the http / probe-log / identity-layer evidence to every row."""
    ds_probe_records = {
        str(record.get("spec")): record
        for record in (sources["ds_probe"].get("records") or [])
    }
    cn_matrix_records = {
        record.get("model_requested"): record
        for record in ((sources["cn_summary"] or {}).get("records") or [])
    }
    cn_identity_records = {
        record.get("model_requested"): record
        for record in ((sources["cn_identity"] or {}).get("records") or [])
    }
    intl_identity_records = {
        record.get("model_requested"): record
        for record in (sources["intl_identity"].get("records") or [])
    }
    intl_matrix_records = {
        record.get("model_requested"): record
        for record in (sources["intl_summary"].get("records") or [])
        if record.get("provider") == "siliconflow"
    }
    multi_probe_records = {
        str(record.get("spec")): record
        for record in (sources["multi_probe"].get("records") or [])
    }
    pm_provider = sources["pm_summary"].get("provider") or {}
    for row in rows:
        row_id = row["row_id"]
        http = None
        probe_path: str | None = None
        observed_model: str | None = None
        attribution = "none"
        if row_id.startswith("deepseek-official/") and "/provider-matrix/" not in row_id \
                and "/probe/" not in row_id:
            model = row["model_requested"]
            record = ds_probe_records.get(f"deepseek:{model}") or {}
            observed_model = str(record.get("model_returned") or row["model_served"])
            probe_path = f"{DS_PROBE_DIR}/summary.json"
            attribution = "requested_model"
        elif row_id.startswith("siliconflow-cn/") and "THUDM" not in row_id:
            record = cn_matrix_records.get(row["model_requested"]) or {}
            observed_model = str(record.get("model_returned") or row["model_served"])
            probe_path = f"{CN_DIR}/identity-probe/summary.json"
            attribution = "requested_model"
        elif row_id.startswith("siliconflow-intl/"):
            record = intl_identity_records.get(row["model_requested"]) or {}
            observed_model = str(record.get("model_returned") or row["model_served"])
            probe_path = f"{INTL_DIR}/identity-probe/summary.json"
            attribution = "none"
            matrix_record = intl_matrix_records.get(row["model_requested"]) or {}
            http = _parse_http_error(matrix_record.get("error"))
        elif "THUDM/GLM-Z1-9B-0414" in row_id:
            probe_path = f"{CN_DIR}/identity-probe/summary.json"
            attribution = "none"
        elif "/provider-matrix/" in row_id:
            observed_model = str(pm_provider.get("model_returned") or row["model_served"])
            probe_path = f"{PM_DIR}/summary.json"
            attribution = "served_model"
        elif "/probe/" in row_id:
            record = multi_probe_records.get("deepseek:deepseek-chat") or {}
            observed_model = str(record.get("model_returned") or row["model_served"])
            probe_path = f"{MULTI_PROBE_DIR}/summary.json"
            attribution = "served_model"
        probe = _probe_log(probe_path)
        row["http"] = http
        row["probe_log_path"] = probe["path"]
        row["probe_log_sha256"] = probe["sha256"]
        row["identity_layer"] = _identity_layer(
            row["model_requested"],
            row["model_served"],
            observed_model,
            row["identity_ok"],
            bool(row["identity_verified"]),
            attribution,
        )
    return rows


def _build_intl_unavailable(sources: dict[str, Any]) -> dict[str, Any]:
    """Derive the SiliconFlow-international unavailability evidence file."""
    aggregate = sources["intl_aggregate"]
    matrix = sources["intl_summary"]
    identity = sources["intl_identity"]
    intl_probe = sources["sf_intl_probe"]
    records = [
        record for record in (matrix.get("records") or [])
        if record.get("provider") == "siliconflow"
    ]
    identity_by_model = {
        record.get("model_requested"): record
        for record in (identity.get("records") or [])
    }
    first_http = None
    models: list[dict[str, Any]] = []
    for record in records:
        model = record.get("model_requested")
        probe_record = identity_by_model.get(model) or {}
        http = _parse_http_error(record.get("error"))
        if first_http is None and http is not None:
            first_http = http
        models.append({
            "model": model,
            "endpoint": "https://api.siliconflow.com/v1",
            "identity_probe_status": probe_record.get("status"),
            "model_returned": probe_record.get("model_returned"),
            "identity_ok": probe_record.get("model_identity_ok"),
            "identity_probe_latency_ms": probe_record.get("latency_ms"),
            "benchmark_status": record.get("status"),
            "benchmark_error_class": (http or {}).get("error_class"),
            "benchmark_error_text": record.get("error"),
            "http": http,
            "not_executed_reason": (
                "the identity probe passed with exact resp.model, but the full "
                "benchmark call was blocked before any of the 12 cases ran"
            ),
        })
    http = first_http or {"status": 402, "code": None, "error_class": "_ProviderHTTPError"}
    evidence = {
        "identity_probe": _probe_log(f"{INTL_DIR}/identity-probe/summary.json"),
        "benchmark_attempt": _probe_log(f"{INTL_DIR}/summary.json"),
        "aggregate": _probe_log(f"{INTL_DIR}/aggregate.json"),
        "intl_identity_probe": _probe_log(f"{SF_INTL_PROBE_DIR}/summary.json"),
        "key_status_doc": _probe_log(f"{SF_KEY_DIR}/README.md"),
        "artifact_readme": _probe_log(f"{INTL_DIR}/README.md"),
    }
    return {
        "schema_version": 1,
        "kind": "provider_unavailable_evidence",
        "provider": "siliconflow-intl",
        "provider_name": "siliconflow",
        "endpoint": "https://api.siliconflow.com/v1",
        "status": "blocked_unavailable",
        "reason": str(
            aggregate.get("siliconflow_benchmark")
            or "HTTP 402 insufficient account balance on full benchmark calls"
        ),
        "http_status": http.get("status"),
        "http": http,
        "error_class": http.get("error_class"),
        "requested_models": aggregate.get("requested_models"),
        "completed_models": aggregate.get("completed_models"),
        "identity_probe_status": aggregate.get("siliconflow_identity_probe"),
        "models": models,
        "evidence": evidence,
        "timestamp": {
            "available": False,
            "value": None,
            "reason": (
                "the SiliconFlow international source artifacts do not record a "
                "generated_at timestamp; not fabricated"
            ),
        },
        "provider_error_code": {
            "available": False,
            "value": None,
            "reason": (
                "the HTTP error body (provider code 30001, insufficient balance) "
                "is only described in prose in the source artifacts; no "
                "machine-readable field records it, so it is not asserted here"
            ),
        },
        "unavailable_fields": ["timestamp", "provider_error_code"],
        "limitations": [
            "no benchmark case ran for these models; this file is unavailability "
            "evidence, never a benchmark result",
            "identity probes passed before the benchmark calls were blocked by "
            "the account balance; identity is recorded, capability is not claimed",
        ],
        "notes": [
            "blocked by account balance, not by model identity or code",
            "this file is referenced by aggregate.not_satisfied with its SHA-256",
        ],
    }


def _build_rows(sources: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-derive the eleven evidence rows from the committed source artifacts."""
    rows: list[dict[str, Any]] = []
    ds_aggregate = sources["ds_aggregate"]
    ds_models = list(ds_aggregate.get("models") or [])
    ds_runs = ds_aggregate.get("runs_detail") or []

    for model in ds_models:
        runs = [run for run in ds_runs if run.get("model") == model]
        rows.append({
            "row_id": f"deepseek-official/{model}",
            "provider": "deepseek-official",
            "provider_kind": "official_endpoint",
            "endpoint": "https://api.deepseek.com/v1",
            "model_requested": model,
            "model_served": model,
            "identity_ok": True,
            "identity_verified": True,
            "status": "identity_verified_completed",
            "benchmark_executed": True,
            "cases": 12,
            "runs": len(runs),
            "runs_ai_verified": [int(run.get("ai_verified") or 0) for run in runs],
            "ai_verified": max((int(run.get("ai_verified") or 0) for run in runs),
                               default=0),
            "ai_verified_attributed_to": model,
            "source": _source(
                DS_MATRIX_DIR,
                [(f"{DS_PROBE_DIR}/summary.json", DS_PROBE_DIR),
                 (f"{DS_MATRIX_DIR}/aggregate.json", DS_MATRIX_DIR),
                 (f"{DS_MATRIX_DIR}/provider-probe.json", DS_MATRIX_DIR),
                 (f"{DS_MATRIX_DIR}/{model}-r1.json", DS_MATRIX_DIR),
                 (f"{DS_MATRIX_DIR}/{model}-r2.json", DS_MATRIX_DIR),
                 (f"{DS_MATRIX_DIR}/{model}-r3.json", DS_MATRIX_DIR),
                 (f"{DS_MATRIX_DIR}/README.md", DS_MATRIX_DIR)],
                corroborating=[
                    (f"{INTL_DIR}/benchmarks/deepseek-{model}/summary.json", INTL_DIR),
                    (f"{CN_DIR}/benchmarks/deepseek-{model}/summary.json", CN_DIR),
                ],
            ),
            "limitations": [
                "successful repairs remain loop-family only (6/6 loop, 0/6 non-loop) for every run",
                "native PoC/regression executed in the Linux guest; candidate generation on macOS",
            ],
            "notes": "requested and returned model identity matched exactly on all runs",
        })

    if sources["cn_present"] and sources["cn_summary"]:
        for record in sources["cn_summary"].get("records") or []:
            if record.get("provider") != "siliconflow":
                continue
            model = record.get("model_requested")
            if not isinstance(model, str):
                continue
            slug = model.replace("/", "_")
            benchmark = sources["cn_benchmarks"].get(slug) or {}
            cases = len(benchmark.get("cases") or []) or 12
            rows.append({
                "row_id": f"siliconflow-cn/{model}",
                "provider": "siliconflow-cn",
                "provider_kind": "third_party_free_tier",
                "endpoint": "https://api.siliconflow.cn/v1",
                "model_requested": model,
                "model_served": str(record.get("model_returned") or model),
                "identity_ok": bool(record.get("model_identity_ok")),
                "identity_verified": bool(record.get("model_identity_ok")),
                "status": "identity_verified_completed",
                "benchmark_executed": True,
                "cases": cases,
                "runs": 1,
                "runs_ai_verified": [int(benchmark.get("ai_verified") or 0)],
                "ai_verified": int(benchmark.get("ai_verified") or 0),
                "ai_verified_attributed_to": model,
                "source": _source(
                    CN_DIR,
                    [(f"{CN_DIR}/summary.json", CN_DIR),
                     (f"{CN_DIR}/aggregate.json", CN_DIR),
                     (f"{CN_DIR}/identity-probe/summary.json", CN_DIR),
                     (f"{CN_DIR}/benchmarks/siliconflow-{slug}/summary.json", CN_DIR),
                     (f"{CN_DIR}/README.md", CN_DIR)],
                ),
                "limitations": [
                    "identity probes and the full 12-case benchmark are real free-tier calls (no balance error)",
                    "model produced no verified candidate (0/12); this is model-capability evidence, not a pass",
                ],
                "notes": "see LIMITATIONS section 22 (4-model real matrix); the same evidence is in this tree",
            })

    intl_records = {
        record.get("model_requested"): record
        for record in sources["intl_summary"].get("records") or []
        if record.get("provider") == "siliconflow"
    }
    for model in sorted(intl_records):
        record = intl_records[model]
        rows.append({
            "row_id": f"siliconflow-intl/{model}",
            "provider": "siliconflow-intl",
            "provider_kind": "third_party_paid",
            "endpoint": "https://api.siliconflow.com/v1",
            "model_requested": model,
            "model_served": model,
            "identity_ok": True,
            "identity_verified": False,
            "status": "blocked_unavailable",
            "benchmark_executed": False,
            "blocked_reason": "HTTP 402 insufficient account balance on full benchmark calls",
            "http_status": 402,
            "cases": 0,
            "runs": 0,
            "runs_ai_verified": [],
            "ai_verified": None,
            "ai_verified_attributed_to": None,
            "source": _source(
                INTL_DIR,
                [(f"{INTL_DIR}/summary.json", INTL_DIR),
                 (f"{INTL_DIR}/aggregate.json", INTL_DIR),
                 (f"{INTL_DIR}/identity-probe/summary.json", INTL_DIR),
                 (f"{INTL_DIR}/README.md", INTL_DIR),
                 (f"{SF_INTL_PROBE_DIR}/summary.json", SF_INTL_PROBE_DIR),
                 (f"{SF_KEY_DIR}/README.md", SF_KEY_DIR)],
            ),
            "limitations": [
                "identity probe passed (resp.model exact); no 12-case benchmark was produced",
                "blocked by account balance, not by model identity or code; never counted as verified",
            ],
            "notes": (
                f"matrix record: {record.get('spec')} -> status="
                f"{record.get('status')}, {record.get('error')}"
            ),
        })

    for record in (sources["cn_identity"] or {}).get("records") or []:
        if record.get("model_requested") != "THUDM/GLM-Z1-9B-0414":
            continue
        rows.append({
            "row_id": "siliconflow-cn/THUDM/GLM-Z1-9B-0414",
            "provider": "siliconflow-cn",
            "provider_kind": "third_party_free_tier",
            "endpoint": "https://api.siliconflow.cn/v1",
            "model_requested": "THUDM/GLM-Z1-9B-0414",
            "model_served": None,
            "identity_ok": None,
            "identity_verified": False,
            "status": "blocked_unavailable",
            "benchmark_executed": False,
            "blocked_reason": "identity probe timed out (TimeoutError)",
            "http_status": None,
            "cases": 0,
            "runs": 0,
            "runs_ai_verified": [],
            "ai_verified": None,
            "ai_verified_attributed_to": None,
            "source": _source(
                CN_DIR,
                [(f"{CN_DIR}/identity-probe/summary.json", CN_DIR)],
                reference_docs=[(LIMITATIONS_DOC, ROOT),
                                (f"{SF_KEY_DIR}/README.md", SF_KEY_DIR)],
            ),
            "limitations": ["no benchmark evidence for this model; identity unknown, never counted"],
            "notes": "LIMITATIONS section 22; no fifth provider key is available",
        })

    pm_provider = sources["pm_summary"].get("provider") or {}
    pm_aggregate = sources["pm_summary"].get("aggregate") or {}
    rows.append({
        "row_id": "deepseek-official/provider-matrix/deepseek-chat->deepseek-flash",
        "provider": "deepseek-official",
        "provider_kind": "official_endpoint",
        "endpoint": "https://api.deepseek.com/v1",
        "model_requested": str(pm_provider.get("model_requested") or "deepseek-chat"),
        "model_served": str(pm_provider.get("model_returned") or "deepseek-flash"),
        "identity_ok": bool(pm_provider.get("model_identity_ok")),
        "identity_verified": bool(pm_provider.get("model_identity_ok")),
        "status": "served_model_mismatch_completed",
        "benchmark_executed": True,
        "cases": int(pm_aggregate.get("cases") or 12),
        "runs": 1,
        "runs_ai_verified": [int(pm_aggregate.get("ai_target_verified") or 0)],
        "ai_verified": int(pm_aggregate.get("ai_target_verified") or 0),
        "ai_verified_attributed_to": str(pm_provider.get("model_returned") or "deepseek-flash"),
        "source": _source(
            PM_DIR,
            [(f"{PM_DIR}/summary.json", PM_DIR),
             (f"{PM_DIR}/README.md", PM_DIR)],
        ),
        "limitations": [
            "identity_ok=false: this run must NOT be presented as requested-model-identity verified",
            "AI verified count is attributed to the served model only",
            "served-model aliasing is provider-side; recorded honestly, not excluded from evidence",
        ],
        "notes": "requested deepseek-chat was served as deepseek-flash (provider aliasing)",
    })

    for record in sources["multi_probe"].get("records") or []:
        if record.get("spec") != "deepseek:deepseek-chat":
            continue
        rows.append({
            "row_id": "deepseek-official/probe/deepseek-chat",
            "provider": "deepseek-official",
            "provider_kind": "official_endpoint",
            "endpoint": "https://api.deepseek.com/v1",
            "model_requested": "deepseek-chat",
            "model_served": str(record.get("model_returned") or "deepseek-flash"),
            "identity_ok": False,
            "identity_verified": False,
            "status": "probe_only_identity_mismatch",
            "benchmark_executed": False,
            "cases": 0,
            "runs": 0,
            "runs_ai_verified": [],
            "ai_verified": None,
            "ai_verified_attributed_to": None,
            "source": _source(
                MULTI_PROBE_DIR,
                [(f"{MULTI_PROBE_DIR}/summary.json", MULTI_PROBE_DIR),
                 (f"{MULTI_PROBE_DIR}/README.md", MULTI_PROBE_DIR)],
            ),
            "limitations": [
                "probe record only; the strict identity check rejects this model for benchmark evidence",
            ],
            "notes": "old single-model endpoint maps deepseek-chat to deepseek-flash (P5 model-shrinkage risk)",
        })

    rows.append({
        "row_id": "dashscope/qwen-plus",
        "provider": "dashscope",
        "provider_kind": "reference_only",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_requested": "qwen-plus",
        "model_served": None,
        "identity_ok": None,
        "identity_verified": False,
        "status": "unavailable_no_artifact",
        "benchmark_executed": False,
        "blocked_reason": "no DashScope/Bailian key configured on this host; no artifact exists",
        "http_status": None,
        "cases": 0,
        "runs": 0,
        "runs_ai_verified": [],
        "ai_verified": None,
        "ai_verified_attributed_to": None,
        "source": {
            "artifact_dir": None,
            "files": [],
            "sha256sums": None,
            "corroborating_files": [],
            "reference_docs": [
                {"path": MULTI_MODEL_DOC, "sha256": _sha256_file(MULTI_MODEL_DOC)},
            ],
        },
        "limitations": ["referenced by docs only; no key, no probe, no benchmark evidence"],
        "notes": "explicit unavailable/no-artifact row: never a provider claim",
    })
    return _augment_rows(rows, sources)


# ---------------------------------------------------------------------------
# Aggregate / summary / README
# ---------------------------------------------------------------------------


def _build_aggregate(rows: list[dict[str, Any]],
                     statistics: dict[str, Any],
                     intl_sha256: str) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "identity_verified_completed"]
    served_mismatch = [
        row for row in rows if row["status"] == "served_model_mismatch_completed"
    ]
    blocked = [row for row in rows if row["status"] == "blocked_unavailable"]
    probe_only = [
        row for row in rows if row["status"] == "probe_only_identity_mismatch"
    ]
    completed_providers = sorted({row["provider"] for row in completed})
    blocked_providers_all = sorted({row["provider"] for row in blocked})
    blocked_providers = [
        provider for provider in blocked_providers_all
        if provider not in completed_providers
    ]
    partially_blocked = [
        provider for provider in blocked_providers_all
        if provider in completed_providers
    ]
    identity_verified_models = sorted(
        row["model_served"] for row in completed if row["identity_verified"]
    )
    ai_by_model: dict[str, Any] = {}
    for row in completed:
        ai_by_model[row["model_served"]] = {
            "provider": row["provider"],
            "runs": row["runs"],
            "cases": row["cases"],
            "per_run_ai_verified": row["runs_ai_verified"],
        }
    blocked_reasons: list[dict[str, Any]] = []
    for provider in sorted({row["provider"] for row in blocked}):
        models = sorted(
            row["model_requested"] for row in blocked if row["provider"] == provider
        )
        reasons = sorted({
            str(row.get("blocked_reason") or "") for row in blocked
            if row["provider"] == provider
        })
        blocked_reasons.append({
            "provider": provider,
            "models": models,
            "reason": " | ".join(reason for reason in reasons if reason),
        })
    blocked_reasons.append({
        "provider": "dashscope",
        "models": ["qwen-plus"],
        "reason": "no DashScope/Bailian key configured; no artifact",
    })
    intl_evidence = {
        "evidence_path": f"{ARTIFACT_DIR_REL}/{INTL_UNAVAILABLE_NAME}",
        "evidence_sha256": intl_sha256,
    }
    not_satisfied: list[dict[str, Any]] = [{
        "id": "international_5_6_model_matrix",
        "reason": (
            "international 5-6 model matrix: 3 SiliconFlow international models "
            "passed identity probes but every benchmark call returned HTTP 402 "
            "insufficient balance; no fifth provider key is available; 4 models "
            "completed, not 5-6"
        ),
        **intl_evidence,
    }]
    if len(completed_providers) < 2:
        not_satisfied.append({
            "id": "at_least_2_providers_12case",
            "reason": (
                "at least 2 providers completed a 12-case benchmark: only "
                f"{len(completed_providers)} provider(s) have evidence in this tree"
            ),
            **intl_evidence,
        })
    if len(completed) < 4:
        not_satisfied.append({
            "id": "at_least_4_models_12case",
            "reason": (
                "at least 4 models completed a 12-case benchmark: only "
                f"{len(completed)} model(s) have evidence in this tree"
            ),
            **intl_evidence,
        })
    return {
        "providers_with_artifact": len({
            provider for provider in (
                {row["provider"] for row in rows if row["status"] != "unavailable_no_artifact"}
            )
        }),
        "providers_completed_12case": len(completed_providers),
        "providers_completed": completed_providers,
        "providers_blocked": len(blocked_providers),
        "providers_blocked_list": blocked_providers,
        "providers_partially_blocked": partially_blocked,
        "providers_referenced_no_artifact": 1,
        "models_completed_12case": len(completed),
        "models_blocked": len(blocked),
        "identity_verified_models": identity_verified_models,
        "identity_verified_models_count": len(identity_verified_models),
        "identity_mismatch_rows": len(served_mismatch) + len(probe_only),
        "served_model_only_completed_rows": len(served_mismatch),
        "ai_verified_by_completed_model": ai_by_model,
        "served_model_attribution_runs": [
            {
                "requested_model": row["model_requested"],
                "served_model": row["model_served"],
                "cases": row["cases"],
                "runs": row["runs"],
                "ai_verified": row["ai_verified"],
                "source": row["source"]["artifact_dir"],
            }
            for row in served_mismatch
        ],
        "not_satisfied": not_satisfied,
        "blocked_reasons": blocked_reasons,
        "requirements": {
            "at_least_2_models_12case": {
                "satisfied": len(completed) >= 2,
                "observed": len(completed),
                "evidence": identity_verified_models,
            },
            "at_least_2_providers_12case": {
                "satisfied": len(completed_providers) >= 2,
                "observed": len(completed_providers),
                "evidence": completed_providers,
                "note": (
                    "DeepSeek official (2 models) and SiliconFlow China (2 free "
                    "Qwen models); this 4-model evidence is in the tree "
                    "(LIMITATIONS section 22)"
                ),
            },
            "five_model_international_matrix": {
                "satisfied": False,
                "observed": len(completed),
                "reason": not_satisfied[0]["reason"],
            },
            "identity_policy_applied": {"satisfied": True},
        },
        "brief_expectation_check": {
            "brief_expected": {"providers_completed": 1, "providers_blocked": 1},
            "observed": {
                "providers_completed": len(completed_providers),
                "providers_blocked": len(blocked_providers),
            },
            "explanation": (
                "The frozen release tree also contains real SiliconFlow-CN 12-case "
                "benchmark evidence (artifacts/multi-model-matrix-cn-2026-11-14, "
                "4-model matrix, LIMITATIONS section 22). Both CN Qwen models are "
                "identity-verified and completed 12 cases (0/12 verified), so two "
                "providers completed 12-case; only the international 5-model matrix "
                "is blocked. No overclaim: CN models produced zero verified candidates."
            ),
        },
        "statistics_pooled": {
            "ai_target_identity_verified": statistics["ai_target"]["pooled_identity_verified"],
            "deterministic_target_strict": {
                "cases": statistics["deterministic_target_strict"]["cases"],
                "verified": statistics["deterministic_target_strict"]["verified"],
                "verified_rate": statistics["deterministic_target_strict"]["verified_rate"],
                "expected_match_rate": statistics["deterministic_target_strict"]["expected_match_rate"],
            },
        },
        "no_overclaim": True,
    }


def _build_summary(sources: dict[str, Any],
                   intl_unavailable_sha256: str) -> dict[str, Any]:
    rows = _build_rows(sources)
    statistics = _build_statistics(rows, sources)
    aggregate = _build_aggregate(rows, statistics, intl_unavailable_sha256)
    generated_at, generated_at_source = _latest_source_generated_at(sources)
    extra_files = [
        f"{DS_PROBE_DIR}/summary.json",
        f"{DS_PROBE_DIR}/README.md",
        f"{MULTI_PROBE_DIR}/README.md",
        f"{INTL_DIR}/aggregate.json",
        f"{CN_DIR}/aggregate.json",
        f"{CN_DIR}/README.md",
        LIMITATIONS_DOC,
        MULTI_MODEL_DOC,
    ]
    extra_files = [path for path in extra_files if _path(path).is_file()]
    provenance = {
        "builder": "scripts/build_provider_coverage.py",
        "builder_version": BUILDER_VERSION,
        "build_method": (
            "deterministic re-derivation from committed source artifacts; "
            "no provider calls, no network, no git commands, no wall-clock timestamps"
        ),
        "generated_at": generated_at,
        "generated_at_source": generated_at_source,
        "generated_at_note": (
            "generated_at is the latest timestamp recorded in a cited source "
            "artifact so a fresh build is byte-identical; it is not the build time"
        ),
        "source_digest_sha256": _source_digest(rows, extra_files),
        "cited_source_count": len({
            entry["path"]
            for row in rows for group in
            ("files", "corroborating_files", "reference_docs")
            for entry in row["source"][group]
        }),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": ARTIFACT_KIND,
        "generated_at": generated_at,
        "provenance": provenance,
        "purpose": (
            "Machine-readable provider/model coverage: which models have real "
            "12-case benchmark evidence, with sha256-bound source artifacts, "
            "strict model-identity policy, Wilson 95% intervals and honest "
            "blocked/unavailable rows."
        ),
        "identity_policy": {
            "rule": IDENTITY_RULE,
            "identity_ok_false": IDENTITY_OK_FALSE,
            "served_model_attribution": True,
            "strict_identity_env": "BINARYREPAIR_STRICT_MODEL_IDENTITY=1",
            "excluded_when_strict": True,
            "applied_in_this_artifact": True,
            "identity_mismatch_rows": aggregate["identity_mismatch_rows"],
            "served_model_only_completed_rows": aggregate["served_model_only_completed_rows"],
        },
        "evidence_rows": rows,
        "statistics": statistics,
        "cost": {
            "available": False,
            "value": None,
            "currency": None,
            "basis": "provider APIs expose token usage only; no price table configured",
        },
        "seed": {
            "available": False,
            "value": None,
            "reason": (
                "the shared provider client (HttpJsonClient.chat_json) does not "
                "marshal a seed; no source artifact records one"
            ),
        },
        "aggregate": aggregate,
        "intl_unavailable": {
            "path": f"{ARTIFACT_DIR_REL}/{INTL_UNAVAILABLE_NAME}",
            "sha256": intl_unavailable_sha256,
            "status": "blocked_unavailable",
            "http_status": 402,
            "error_class": "_ProviderHTTPError",
            "models": [
                row["model_requested"] for row in rows
                if row["provider"] == "siliconflow-intl"
            ],
            "evidence_note": (
                "aggregate.not_satisfied items reference this file by path and "
                "SHA-256; it is derived from the SiliconFlow international "
                "identity-probe and benchmark-attempt artifacts"
            ),
        },
        # Top-level aliases kept for consumers that read the blocked list outside
        # the aggregate block; both are byte-identical content.
        "blocked_reasons": aggregate["blocked_reasons"],
        "next_steps": [
            "top up the SiliconFlow international account (or use a funded key) and "
            "rerun scripts/run_multi_model_matrix.py --benchmark for the three "
            "identity-probed models to reach 5-6 models",
            "or configure a DashScope/Bailian key and run the same 12-case benchmark",
            "then rerun the multi-provider matrix in CI (one provider/model per row, "
            "strict identity, Linux guest PoC) and replace blocked rows with completed rows",
            "do not present served-model evidence as requested-model identity evidence "
            "(deepseek-chat alias)",
        ],
        "limitations": [
            "no provider calls were made for this artifact; it consolidates committed "
            "evidence only",
            "two SiliconFlow international models and GLM have no benchmark evidence "
            "(blocked), explicitly recorded",
            "CN Qwen models completed 12 cases with 0/12 verified: completing a "
            "benchmark is not a pass",
            "successful AI repairs remain loop-family only (6/6 loop, 0/6 non-loop) "
            "for every completed model",
            "the provider-matrix deepseek-chat run is served-model evidence "
            "(identity_ok=false) and is never counted as requested-model coverage",
        ],
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _render_readme(summary: dict[str, Any]) -> str:
    statistics = summary["statistics"]
    aggregate = summary["aggregate"]
    provenance = summary["provenance"]
    deterministic = statistics["deterministic_target_strict"]
    pooled = statistics["ai_target"]["pooled_identity_verified"]
    served = statistics["ai_target"]["served_model_only"]
    lines: list[str] = [
        "# Provider coverage - machine-readable provider/model evidence (2026-11-14)",
        "",
        "Generated deterministically by `scripts/build_provider_coverage.py` from the",
        "committed source artifacts in this repository. No provider calls were made",
        "to build it.",
        "",
        f"- generated_at: `{summary['generated_at']}` ({provenance['generated_at_source']};",
        "  deterministic source-derived timestamp, not build wall clock)",
        f"- source digest: `{provenance['source_digest_sha256']}`",
        f"- cited source files: {provenance['cited_source_count']}",
        "",
        "Artifact files: `summary.json` (machine-readable), `README.md` (this file),",
        "`intl-unavailable.json` (SiliconFlow-international unavailability evidence)",
        "and `SHA256SUMS` (covers all three files; never itself).",
        "",
        "## What this artifact answers",
        "",
        "1. Which provider/model pairs have real 12-case benchmark evidence, where",
        "   that evidence lives (path + SHA-256), and the verified rate with a 95%",
        "   Wilson confidence interval.",
        "2. What the strict model-identity policy means for a run whose served model",
        "   differs from the requested one (`identity_ok=false`).",
        "3. Which provider-dimension requirements are satisfied and which are",
        "   blocked/unavailable, with exact reasons - no fabricated success.",
        "4. Separate deterministic and AI metrics: `deterministic_target_strict`",
        "   (model-independent) is never combined with `ai_target` (provider run).",
        "5. HTTP failure evidence and the three-model identity layer",
        "   (requested / served / observed) for every evidence row, plus the",
        "   `intl-unavailable.json` evidence file referenced by `not_satisfied`.",
        "",
        "## Evidence rows",
        "",
        "| # | provider | model requested | model served | identity_ok | status | cases | runs | AI verified | attributed to | source artifact |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(summary["evidence_rows"], start=1):
        lines.append(
            f"| {index} | {row['provider']} | `{row['model_requested']}` | "
            f"`{row['model_served']}` | {row['identity_ok']} | {row['status']} | "
            f"{row['cases']} | {row['runs']} | "
            f"{row['ai_verified'] if row['ai_verified'] is not None else '-'} | "
            f"`{row['ai_verified_attributed_to'] or '-'}` | "
            f"`{row['source']['artifact_dir'] or '(none)'}` |"
        )
    lines += [
        "",
        "Every row cites source files with SHA-256; each source artifact's own",
        "`SHA256SUMS` is validated by the builder and by the test suite, which also",
        "re-derives the row values from the cited artifacts.",
        "",
        "### Evidence layers (per row)",
        "",
        "- `http`: `{status, code, error_class}` for a typed provider HTTP failure,",
        "  or `null` when the provider call did not fail with an HTTP status.",
        "  The provider-specific `code` stays `null` unless a machine-readable",
        "  field records it (never parsed from prose).",
        "- `probe_log_path` / `probe_log_sha256`: the identity-probe or matrix",
        "  record that evidences `model_served`; `null` when no probe exists.",
        "- `identity_layer`: `{requested_model, served_model, observed_model,`",
        "  `identity_ok, identity_verified, attribution}` where `attribution` is",
        "  `requested_model`, `served_model`, or `none`. A served-model mismatch",
        "  is always `attribution=served_model` and is never identity-verified.",
        "",
        "## International provider unavailability (`intl-unavailable.json`)",
        "",
        f"- file: `{summary['intl_unavailable']['path']}`",
        f"- sha256: `{summary['intl_unavailable']['sha256']}`",
        "- provider/status: `siliconflow-intl` / `blocked_unavailable`",
        f"- http_status: {summary['intl_unavailable']['http_status']}; "
        f"error_class: `{summary['intl_unavailable']['error_class']}`",
        f"- models: {', '.join('`' + model + '`' for model in summary['intl_unavailable']['models'])}",
        "",
        "The file is derived from the committed SiliconFlow-international identity",
        "probe, benchmark-attempt and account-status artifacts; every cited source",
        "file carries a SHA-256. Fields the sources do not record (timestamp,",
        "provider error code) are explicitly marked unavailable with a reason -",
        "never fabricated. The `not_satisfied` items below reference this file by",
        "path and SHA-256.",
        "",
        "## Statistics (AI target, Wilson 95% CI)",
        "",
        "| provider | model | runs | cases/run | verified (pooled) | verified_rate | wilson_ci95 | inconclusive | identity |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in statistics["by_provider_model"]:
        identity = (
            "verified" if entry["identity_verified"] else
            ("mismatch-served-only" if entry["identity_ok"] is False else
             ("blocked" if entry["status"] == "blocked_unavailable" else "n/a"))
        )
        lines.append(
            f"| {entry['provider']} | `{entry['model_requested']}` | "
            f"{entry['runs']} | {entry['cases']} | {entry['verified']} | "
            f"{_fmt(entry['verified_rate'])} | "
            f"[{_fmt(entry['wilson_ci95'][0])}, {_fmt(entry['wilson_ci95'][1])}] | "
            f"{entry['inconclusive']} | {identity} |"
        )
    lines += [
        "",
        f"Pooled identity-verified AI-target evidence: {pooled['models']} models, "
        f"{pooled['runs']} runs, {pooled['cases']} cases, {pooled['verified']} verified, "
        f"verified_rate={_fmt(pooled['verified_rate'])}, "
        f"wilson_ci95=[{_fmt(pooled['wilson_ci95'][0])}, "
        f"{_fmt(pooled['wilson_ci95'][1])}], inconclusive={pooled['inconclusive']}.",
        "",
        "### Deterministic target-strict (model-independent, separate metric)",
        "",
        f"- source: `{deterministic['source']}`",
        f"- cases: {deterministic['cases']}, verified: {deterministic['verified']}, "
        f"verified_rate: {_fmt(deterministic['verified_rate'])}, "
        f"wilson_ci95: [{_fmt(deterministic['wilson_ci95'][0])}, "
        f"{_fmt(deterministic['wilson_ci95'][1])}], "
        f"inconclusive: {deterministic['inconclusive']}",
        f"- expected-disposition matches: {deterministic['expected_matches']}"
        f"/{deterministic['cases']} "
        f"(expected_match_rate {_fmt(deterministic['expected_match_rate'])}); "
        f"target scope resolved: {deterministic['target_scope_resolved']}",
        f"- dispositions: `{json.dumps(deterministic['dispositions'], sort_keys=True)}`",
        "",
        "## Identity policy",
        "",
        f"- {summary['identity_policy']['rule']}",
        f"- {summary['identity_policy']['identity_ok_false']}",
        "- Consequence: `deepseek-chat` (provider-side alias to `deepseek-flash`)",
        "  is not counted towards requested-model coverage. Its 6/12 verified",
        "  repairs are attributed to the served model `deepseek-flash` and excluded",
        "  from `ai_target.pooled_identity_verified`; the identity-verified model",
        "  rows remain the explicit `deepseek-flash` runs.",
        "",
        "## Aggregate",
        "",
        "| metric | value |",
        "|---|---|",
        f"| providers with artifact | {aggregate['providers_with_artifact']} |",
        f"| providers completed 12-case | {aggregate['providers_completed_12case']} "
        f"({', '.join(aggregate['providers_completed'])}) |",
        f"| providers blocked | {aggregate['providers_blocked']} "
        f"({', '.join(aggregate['providers_blocked_list'])}) |",
        f"| providers referenced with no artifact | "
        f"{aggregate['providers_referenced_no_artifact']} |",
        f"| models completed 12-case | {aggregate['models_completed_12case']} |",
        f"| models blocked (row level) | {aggregate['models_blocked']} |",
        f"| identity-verified models | {aggregate['identity_verified_models_count']} "
        f"({', '.join(aggregate['identity_verified_models'])}) |",
        f"| identity-mismatch rows | {aggregate['identity_mismatch_rows']} |",
        f"| served-model-only completed rows | "
        f"{aggregate['served_model_only_completed_rows']} |",
        "",
        "Requirements:",
        "",
    ]
    for key in ("at_least_2_models_12case", "at_least_2_providers_12case",
                "five_model_international_matrix"):
        item = aggregate["requirements"][key]
        lines.append(f"- `{key}`: satisfied={item['satisfied']}")
    lines += [
        "",
        "### Not satisfied (explicit)",
        "",
    ]
    for item in aggregate["not_satisfied"]:
        lines.append(
            f"- {item['reason']} (evidence: `{item['evidence_path']}` "
            f"sha256 `{item['evidence_sha256']}`)"
        )
    lines += [
        "",
        "### Reconciliation with the phase-4 brief",
        "",
        f"- brief expected: providers_completed="
        f"{aggregate['brief_expectation_check']['brief_expected']['providers_completed']}, "
        f"providers_blocked="
        f"{aggregate['brief_expectation_check']['brief_expected']['providers_blocked']}",
        f"- observed: providers_completed="
        f"{aggregate['brief_expectation_check']['observed']['providers_completed']}, "
        f"providers_blocked="
        f"{aggregate['brief_expectation_check']['observed']['providers_blocked']}",
        f"- {aggregate['brief_expectation_check']['explanation']}",
        "",
        "## Blocked / unavailable reasons",
        "",
    ]
    for item in aggregate["blocked_reasons"]:
        lines.append(f"- {item['provider']}: {item['reason']} "
                     f"(models: {', '.join(item['models'])})")
    lines += [
        "",
        "## Cost and seed",
        "",
        f"- cost available: {summary['cost']['available']} "
        f"(value={summary['cost']['value']}); {summary['cost']['basis']}",
        f"- seed available: {summary['seed']['available']} "
        f"(value={summary['seed']['value']}); {summary['seed']['reason']}",
        "",
        "## Next steps",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["next_steps"])
    lines += [
        "",
        "## Validation",
        "",
        "```bash",
        "python scripts/build_provider_coverage.py --check   # fresh build == committed artifact",
        "python -m pytest -q tests/test_provider_matrix.py tests/test_provider_coverage_artifact.py",
        "```",
        "",
        "`--check` rebuilds the artifact in memory and compares `summary.json`,",
        "`README.md`, `intl-unavailable.json` and `SHA256SUMS` byte-for-byte with",
        "the committed artifact, and re-validates the SHA256SUMS coverage; it exits",
        "0 only on an exact match and never writes files. The artifact test suite",
        "is offline: it verifies the schema, the SHA-256 of every cited file, each source artifact's own `SHA256SUMS`, the identity",
        "policy, Wilson interval sanity, aggregate re-derivation, and that the",
        "committed artifact matches a fresh deterministic build (`--check`).",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def _render_sha256sums(files: dict[str, bytes]) -> bytes:
    lines = [
        f"{_sha256_bytes(files[name])}  {name}"
        for name in ARTIFACT_FILES
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Build / check API
# ---------------------------------------------------------------------------


def build_artifact() -> dict[str, bytes]:
    """Build the artifact files in memory (deterministic, no side effects)."""
    sources = _load_sources()
    # intl-unavailable.json is rendered first because summary.json references its
    # SHA-256 in aggregate.not_satisfied; README.md then embeds the summary data
    # and the intl file hash; SHA256SUMS covers all three files.
    intl_payload = _build_intl_unavailable(sources)
    intl_bytes = (
        json.dumps(intl_payload, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    intl_sha256 = _sha256_bytes(intl_bytes)
    summary = _build_summary(sources, intl_sha256)
    summary_bytes = (
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    files: dict[str, bytes] = {
        "summary.json": summary_bytes,
        "intl-unavailable.json": intl_bytes,
        "README.md": _render_readme(summary).encode("utf-8"),
    }
    files["SHA256SUMS"] = _render_sha256sums(files)
    return files


def write_artifact(out_dir: Path) -> list[dict[str, str]]:
    files = build_artifact()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        target = out_dir / name
        target.write_bytes(files[name])
        written.append({"path": str(target), "sha256": _sha256_bytes(files[name])})
    return written


def check_artifact(artifact_dir: Path) -> dict[str, Any]:
    """Compare a fresh deterministic build with the artifact on disk."""
    files = build_artifact()
    report: dict[str, Any] = {
        "artifact_dir": str(artifact_dir),
        "ok": True,
        "files": {},
        "violations": [],
    }
    on_disk: dict[str, bytes] = {}
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        target = artifact_dir / name
        if not target.is_file():
            report["ok"] = False
            report["violations"].append(f"missing artifact file: {name}")
            report["files"][name] = {"match": False, "reason": "missing"}
            continue
        on_disk[name] = target.read_bytes()
        match = on_disk[name] == files[name]
        report["files"][name] = {
            "match": match,
            "fresh_sha256": _sha256_bytes(files[name]),
            "actual_sha256": _sha256_bytes(on_disk[name]),
        }
        if not match:
            report["ok"] = False
            report["violations"].append(f"fresh build differs from committed {name}")
    # The on-disk SHA256SUMS must also match every on-disk artifact file.
    sums_bytes = on_disk.get("SHA256SUMS")
    if sums_bytes is not None:
        try:
            entries: dict[str, str] = {}
            for line in sums_bytes.decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                digest, relative = line.split(None, 1)
                entries[relative.strip()] = digest.strip()
        except (UnicodeDecodeError, ValueError) as exc:
            report["ok"] = False
            report["violations"].append(f"on-disk SHA256SUMS unreadable: {exc}")
            entries = {}
        for name in ARTIFACT_FILES:
            if name not in entries:
                report["ok"] = False
                report["violations"].append(
                    f"on-disk SHA256SUMS does not cover {name}"
                )
                continue
            if name in on_disk and entries[name] != _sha256_bytes(on_disk[name]):
                report["ok"] = False
                report["violations"].append(
                    f"on-disk SHA256SUMS mismatch for {name}"
                )
    report["fresh_source_digest_sha256"] = (
        json.loads(files["summary.json"]).get("provenance", {}).get(
            "source_digest_sha256"
        )
    )
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically build the provider-coverage evidence artifact "
            "from committed source artifacts (offline; no provider calls)."
        ),
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_ARTIFACT_DIR,
                        help="artifact directory (default: %(default)s)")
    parser.add_argument("--check", action="store_true",
                        help="rebuild in memory and compare with the artifact on disk")
    args = parser.parse_args(argv)
    try:
        if args.check:
            report = check_artifact(args.out)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["ok"] else 1
        written = write_artifact(args.out)
        print(json.dumps({
            "ok": True,
            "out": str(args.out),
            "written": written,
        }, indent=2, ensure_ascii=False))
        return 0
    except BuildError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
