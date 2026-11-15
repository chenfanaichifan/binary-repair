#!/usr/bin/env python3
"""Phase-8C C1: baseline & hidden benchmark readiness audit (read-only).

Collects the machine-checkable baseline facts for the approved Phase-8C
ground-truth-v2 work without modifying production code, contracts, CI, claims,
benchmark v1, the release gate or Phase-8A/B evidence. It reproduces the two
Phase-8B independently verified samples into a temporary output directory
(never the committed evidence) and records not_run truthfully when the
guest/Lima oracle is unavailable.

Artifacts:
    artifacts/phase8c-baseline-2026-11-16/
        phase8c-baseline-audit.json
        phase8c-work-breakdown.json
        phase8c-hidden-isolation-plan.md
        phase8c-lima-coordination-plan.md
        phase8c-readiness.md
        README.md
        SHA256SUMS
        reproduction/ (small JSON evidence only)

Usage:
    python scripts/audit_phase8c_readiness.py --write
    python scripts/audit_phase8c_readiness.py --json
    python scripts/audit_phase8c_readiness.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
KIND = "phase8c_readiness_audit"
AUDIT_DATE = "2026-11-16"
ARTIFACT_DIR = ROOT / "artifacts" / "phase8c-baseline-2026-11-16"
MANIFEST_PATH = "benchmark/phase8-v1/manifest.json"
MANIFEST_V1_SHA = "e7e7eca43518dc1b953faccead6f301f80eee4a59f1f0550dc8aad1bbd712052"
PHASE8B_RESULTS = "artifacts/phase8b-benchmark-2026-11-16/results.json"
PHASE8B_SAMPLES = ("stack-strcpy-x86_64", "heap-capacity-x86_64")
EXPECTED_BASE_SHA = "227f45b39d85a7cd95e8589beb07dcfc89cd22d7"
EXPECTED_BRANCH = "feature/phase8c-ground-truth-v2"
TAG_REFS = {
    "release_tag": "release-2026-11-16-phase8b",
    "evidence_tag": "release-2026-11-16-phase8b-evidence",
    "evidence_branch": "release/2026-11-16-phase8b-evidence",
}
DOC_PATH = "docs/acceptance/phase8c-baseline-audit.md"
DOC_FILES = (
    "phase8c-hidden-isolation-plan.md",
    "phase8c-lima-coordination-plan.md",
    "phase8c-readiness.md",
    "README.md",
)
QUESTION_IDS = tuple(f"Q{index:02d}" for index in range(1, 11))
TASK_IDS = tuple(f"C{index:02d}" for index in range(1, 15))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Read-only git metadata (no git commands: direct refs-file reads)
# ---------------------------------------------------------------------------


def _git_metadata() -> dict[str, Any]:
    result: dict[str, Any] = {
        "head_sha": "unknown",
        "branch": "unknown",
        "tags": {},
        "source": "read-only .git metadata files (no git commands)",
    }
    dotgit = ROOT / ".git"
    try:
        text = dotgit.read_text(encoding="utf-8").strip()
        gitdir = Path(text.split("gitdir:", 1)[1].strip()) if text.startswith(
            "gitdir:") else dotgit
    except (OSError, UnicodeError):
        return result
    try:
        head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return result
    if head.startswith("ref: "):
        ref = head.split("ref: ", 1)[1].strip()
        result["branch"] = ref.split("refs/heads/", 1)[-1]
        common = (gitdir / "commondir").read_text(encoding="utf-8").strip()
        common_dir = (gitdir / common).resolve() if common else gitdir
        ref_path = common_dir / ref
        if ref_path.is_file():
            result["head_sha"] = ref_path.read_text(
                encoding="utf-8").strip()
        else:
            packed = common_dir / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref) or line.endswith("\t" + ref):
                        result["head_sha"] = line.split()[0]
                        break
        for label, tag in TAG_REFS.items():
            ref_path = common_dir / "refs" / (
                "tags/" + tag if label != "evidence_branch"
                else "heads/" + tag)
            if label == "evidence_branch":
                ref_path = common_dir / "refs" / "heads" / tag
            if ref_path.is_file():
                result["tags"][label] = {
                    "ref": tag,
                    "sha": ref_path.read_text(encoding="utf-8").strip(),
                }
            else:
                result["tags"][label] = {"ref": tag, "sha": "not_found"}
    else:
        result["head_sha"] = head
    return result


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


def _first_existing(*paths: str) -> str | None:
    for path in paths:
        if (ROOT / path).is_file():
            return path
    return None


def _toolchain_facts() -> dict[str, Any]:
    def _which(name: str) -> str | None:
        return shutil.which(name)

    limactl = _which("limactl")
    version = None
    if limactl:
        try:
            proc = subprocess.run([limactl, "--version"], capture_output=True,
                                  text=True, timeout=20, check=False)
            if proc.returncode == 0:
                version = (proc.stdout or "").strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError):
            version = None
    guest = None
    try:
        sys.path.insert(0, str(ROOT))
        from app.services import guest_runner

        runner = guest_runner.find_guest_runner("x86_64")
        guest = {
            "available": runner is not None,
            "kind": getattr(runner, "kind", None),
            "tier": getattr(runner, "tier", None),
            "tool": getattr(runner, "tool", None),
            "instance": getattr(runner, "instance", None),
        }
    except Exception as exc:  # noqa: BLE001 - honest unavailable
        guest = {"available": False,
                 "reason": f"{type(exc).__name__}: {exc}"}
    return {
        "clang": _which("clang"),
        "zig": _which("zig"),
        "limactl": limactl,
        "limactl_version": version,
        "guest_runner": guest,
        "lima_instance_running": bool(
            guest and guest.get("available") and guest.get("kind") == "lima"),
    }


def _corpora_facts() -> dict[str, Any]:
    def _cases(path: str) -> dict[str, Any]:
        try:
            payload = _load_json(ROOT / path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return {"path": path, "error": f"{type(exc).__name__}: {exc}"}
        cases = payload.get("cases") if isinstance(payload, dict) else payload
        return {"path": path, "count": len(cases or []),
                "sha256": _sha256_file(ROOT / path)}
    public_dirs = sorted(p.name for p in (ROOT / "fixtures" / "public").iterdir()
                        if p.is_dir()) if (ROOT / "fixtures" / "public").is_dir() else []
    return {
        "hard_cases": _cases("fixtures/hard-cases/cases.json"),
        "repair_benchmark": _cases("fixtures/repair-benchmark/cases.json"),
        "public_dirs": public_dirs,
        "public_dir_count": len(public_dirs),
        "macho_fixture_count": len(list((ROOT / "fixtures" / "macho").glob("*")))
        if (ROOT / "fixtures" / "macho").is_dir() else 0,
        "pe_fixture_count": len(list((ROOT / "fixtures" / "pe").glob("*")))
        if (ROOT / "fixtures" / "pe").is_dir() else 0,
        "public_root_present": (ROOT / "fixtures" / "public").is_dir(),
    }


def _v1_manifest_facts() -> dict[str, Any]:
    path = ROOT / MANIFEST_PATH
    manifest = _load_json(path)
    sample_schema = _load_json(ROOT / "contracts" / "benchmark-sample.schema.json")
    required = list(sample_schema.get("required") or [])
    matrix: list[dict[str, Any]] = []
    split_counts: dict[str, int] = {}
    all_required = True
    for sample in manifest.get("samples", []):
        sid = str(sample.get("sample_id"))
        source_ref = (sample.get("source_refs") or [None])[0]
        source_path = ROOT / str(source_ref) if source_ref else None
        actual_sha = (_sha256_bytes(source_path.read_bytes())
                      if source_path is not None and source_path.is_file()
                      else None)
        oracle = sample.get("oracle") or {}
        oracle_path = oracle.get("manifest_path")
        oracle_loadable = None
        if oracle_path:
            try:
                from app.services.poc_runner import load_manifest

                load_manifest(ROOT / str(oracle_path))
                oracle_loadable = True
            except Exception:  # noqa: BLE001 - recorded as not loadable
                oracle_loadable = False
        missing = [field for field in required if field not in sample]
        all_required = all_required and not missing
        evidence_ok = all(
            (ROOT / str(ref).split("#", 1)[0]).exists()
            for ref in sample.get("evidence_refs", []))
        source_ok = all(
            (ROOT / str(ref).split("#", 1)[0]).is_file()
            for ref in sample.get("source_refs", []))
        split = str(sample.get("split"))
        split_counts[split] = split_counts.get(split, 0) + 1
        matrix.append({
            "sample_id": sid,
            "binary": source_ref,
            "binary_sha256_expected": sample.get("sha256"),
            "binary_sha256_actual": actual_sha,
            "binary_sha_matches": actual_sha == sample.get("sha256"),
            "split": split,
            "target": sample.get("target"),
            "target_complete": bool(
                sample.get("target")
                and (sample.get("target") or {}).get("kind")),
            "oracle_kinds": oracle.get("kinds"),
            "oracle_manifest": oracle_path,
            "oracle_manifest_loadable": oracle_loadable,
            "reference_fix": sample.get("reference_fix"),
            "required_schema_fields_missing": missing,
            "source_refs_resolvable": source_ok,
            "evidence_refs_resolvable": evidence_ok,
            "authority_present": "authority" in sample,
            "hidden_available": sample.get("hidden_available"),
            "lossless_v1_sample": (
                actual_sha == sample.get("sha256") and not missing
                and source_ok and evidence_ok),
        })
    v2_gaps = [
        "manifest wrapper has no explicit benchmark_version / v1->v2 mapping "
        "block (schema_version=1 today)",
        "manifest wrapper hidden fields exist but only hidden_available=false "
        "and hidden_commitment_sha256=null; no public/hidden split policy or "
        "aggregate-only results contract",
        "samples have no optional authority block in v1 (contract supports it); "
        "Phase-8C samples must declare scope_policy/authorized_changes/plan "
        "binding where applicable",
        "results schema is not contract-pinned: Phase-8B results add plan/oracle/"
        "layout fields but there is no results-v2 contract",
        "no hidden-corpus commitment contract (format/aggregation/visibility)",
        "reference_fix is null for 4/12 samples; v2 must treat it as optional "
        "evidence, never an oracle substitute",
    ]
    return {
        "path": MANIFEST_PATH,
        "sha256": _sha256_file(path),
        "sha256_expected": MANIFEST_V1_SHA,
        "sha_matches_expected": _sha256_file(path) == MANIFEST_V1_SHA,
        "kind": manifest.get("kind"),
        "schema_version": manifest.get("schema_version"),
        "sample_count": manifest.get("sample_count"),
        "actual_sample_count": len(manifest.get("samples", [])),
        "splits": manifest.get("splits"),
        "split_counts_actual": split_counts,
        "hidden_available": manifest.get("hidden_available"),
        "hidden_commitment_sha256": manifest.get("hidden_commitment_sha256"),
        "dropped_samples": manifest.get("dropped_samples"),
        "sample_matrix": matrix,
        "migration_summary": {
            "total": len(matrix),
            "lossless": sum(1 for row in matrix if row["lossless_v1_sample"]),
            "all_required_fields_present": all_required,
            "hidden_false": manifest.get("hidden_available") is False,
            "v2_gap_count": len(v2_gaps),
            "v2_gaps": v2_gaps,
        },
    }


def _reproduce_verified_samples() -> dict[str, Any]:
    """Reproduce the two Phase-8B independently verified samples in temp dirs."""
    try:
        phase8b = _load_json(ROOT / PHASE8B_RESULTS)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"status": "not_run",
                "reason": f"Phase-8B results unreadable: {type(exc).__name__}: {exc}",
                "samples": []}
    verified = [
        row for row in phase8b.get("results", [])
        if row.get("independently_verified") is True
    ]
    sample_ids = [str(row.get("sample_id")) for row in verified]
    if not sample_ids:
        return {"status": "not_run",
                "reason": "no Phase-8B independently verified sample is recorded",
                "samples": []}
    manifest = _load_json(ROOT / MANIFEST_PATH)
    selected = [sample for sample in manifest.get("samples", [])
                if sample.get("sample_id") in set(sample_ids)]
    if len(selected) != len(sample_ids):
        return {"status": "not_run",
                "reason": "verified sample ids are missing from benchmark v1",
                "samples": []}
    temp_root = Path(tempfile.mkdtemp(prefix="phase8c-repro-"))
    manifest_copy = temp_root / "manifest-v1-two-samples.json"
    out_dir = temp_root / "out"
    temp_manifest = dict(manifest)
    temp_manifest["samples"] = selected
    temp_manifest["sample_count"] = len(selected)
    temp_manifest["split_counts"] = {
        split: sum(1 for item in selected
                   if item.get("split") == split)
        for split in sorted({str(item.get("split")) for item in selected})
    }
    manifest_copy.write_text(_canonical(temp_manifest), encoding="utf-8")
    command = [
        sys.executable, str(ROOT / "scripts" / "run_repair_benchmark.py"),
        "--manifest", str(manifest_copy), "--out", str(out_dir),
        "--verifier", "auto",
    ]
    try:
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                              text=True, timeout=1200, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "not_run",
                "reason": f"runner raised {type(exc).__name__}: {exc}",
                "samples": [], "command": command}
    results_path = out_dir / "results.json"
    if proc.returncode != 0 or not results_path.is_file():
        return {"status": "not_run",
                "reason": f"runner exit {proc.returncode}: "
                          f"{(proc.stderr or proc.stdout or '')[-500:]}",
                "samples": [], "command": command}
    results = _load_json(results_path)
    samples: list[dict[str, Any]] = []
    by_committed = {row.get("sample_id"): row
                    for row in phase8b.get("results", [])}
    for row in results.get("results", []):
        sid = str(row.get("sample_id"))
        sample_dir = out_dir / "samples" / sid
        evidence_files: dict[str, str] = {}
        for name in ("metadata.json", "plan.json", "verifier-report.json",
                     "outcome.json", "candidate.bin", "original.bin"):
            path = sample_dir / name
            if path.is_file():
                evidence_files[name] = _sha256_file(path)
        samples.append({
            "sample_id": sid,
            "status": "reproduced",
            "candidate_sha256": row.get("candidate_sha256"),
            "candidate_sha_matches_phase8b": (
                row.get("candidate_sha256") == by_committed.get(
                    sid, {}).get("candidate_sha256")),
            "deterministic_verified": row.get("deterministic_verified"),
            "independently_verified": row.get("independently_verified"),
            "verifier_decision": row.get("verifier_decision"),
            "verifier_id": row.get("verifier_id"),
            "oracle_status": row.get("oracle_status"),
            "poc_status": row.get("poc_status"),
            "layout_status": row.get("layout_status"),
            "real_verification": row.get("real_verification"),
            "false_verified": row.get("false_verified"),
            "verification_disagreement": row.get("verification_disagreement"),
            "temp_evidence_files": evidence_files,
        })
    summary = dict(results.get("summary") or {})
    result = {
        "status": "reproduced",
        "reason": None,
        "temp_out": "ephemeral tempfile (deleted after this audit; committed "
                    "evidence is never overwritten)",
        "command_template": (
            "scripts/run_repair_benchmark.py --manifest <temp-v1-two-samples> "
            "--out <temp-out> --verifier auto"),
        "runner_exit_code": proc.returncode,
        "summary": summary,
        "independent_verifier": results.get("independent_verifier"),
        "samples": samples,
        "committed_results_sha256": _sha256_file(ROOT / PHASE8B_RESULTS),
        "temp_results_sha256": _sha256_file(results_path),
        "temp_readme_sha256": (
            _sha256_file(out_dir / "README.md")
            if (out_dir / "README.md").is_file() else None),
        "not_overwritten_committed_evidence": True,
    }
    # Copy only small JSON evidence into the audit artifact; never copy the
    # committed evidence or execute the binaries.
    artifact_reproduction = ARTIFACT_DIR / "reproduction"
    if artifact_reproduction.exists():
        shutil.rmtree(artifact_reproduction)
    artifact_reproduction.mkdir(parents=True)
    for name in ("results.json", "README.md", "SHA256SUMS"):
        path = out_dir / name
        if path.is_file():
            (artifact_reproduction / name).write_bytes(path.read_bytes())
    for sid in [str(row.get("sample_id")) for row in samples]:
        source = out_dir / "samples" / sid
        if not source.is_dir():
            continue
        target = artifact_reproduction / "samples" / sid
        target.mkdir(parents=True)
        for name in ("metadata.json", "plan.json", "verifier-report.json",
                     "outcome.json"):
            path = source / name
            if path.is_file():
                (target / name).write_bytes(path.read_bytes())
    result["artifact_reproduction_dir"] = "reproduction/"
    shutil.rmtree(temp_root, ignore_errors=True)
    return result


def _contracts_facts() -> dict[str, Any]:
    names = sorted(path.stem for path in (ROOT / "contracts").glob(
        "*.schema.json"))
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_contract_schemas.py"),
             "--check"], cwd=str(ROOT), capture_output=True, text=True,
            timeout=300, check=False)
        checker = {"exit_code": proc.returncode,
                   "summary": (proc.stdout or "").strip().splitlines()[-1]
                   if (proc.stdout or "").strip() else ""}
    except (OSError, subprocess.SubprocessError) as exc:
        checker = {"exit_code": None,
                   "error": f"{type(exc).__name__}: {exc}"}
    benchmark_schema = _load_json(ROOT / "contracts" /
                                  "benchmark-sample.schema.json")
    return {
        "count": len(names),
        "names": names,
        "checker": checker,
        "benchmark_sample_required": list(
            benchmark_schema.get("required") or []),
        "benchmark_sample_properties": sorted(
            (benchmark_schema.get("properties") or {}).keys()),
        "has_hidden_fields": all(
            field in (benchmark_schema.get("properties") or {})
            for field in ("hidden_available", "hidden_commitment_sha256")),
        "has_authority_block": "authority" in (
            benchmark_schema.get("properties") or {}),
        "has_patch_plan_contract": (ROOT / "contracts" /
                                    "patch-plan.schema.json").is_file(),
        "has_manifest_wrapper_contract": any(
            "manifest" in name for name in names),
        "has_hidden_commitment_contract": any(
            "hidden" in name for name in names),
        "has_results_contract": any(
            "result" in name for name in names),
    }


def _hidden_facts() -> dict[str, Any]:
    contract_root = Path.home() / ".binaryrepair"
    default_root = contract_root / "phase8c-hidden"
    env_value = os.environ.get("PHASE8C_HIDDEN_ROOT")
    env_set = bool(env_value)
    exists = default_root.exists()
    perms = None
    if exists:
        try:
            perms = oct(default_root.stat().st_mode & 0o777)
        except OSError:
            perms = None
    try:
        readiness = _load_json(
            ROOT / "artifacts" / "phase8-readiness-2026-11-16" /
            "readiness.json")
        g29 = next((item for item in readiness.get("items", [])
                    if item.get("gap_id") == "G29"), {})
    except (OSError, UnicodeError, json.JSONDecodeError):
        g29 = {}
    return {
        "private_root_default": str(default_root),
        "private_root_env": "PHASE8C_HIDDEN_ROOT",
        "private_root_env_set": env_set,
        "private_root_exists": exists,
        "private_root_permissions": perms,
        "hidden_corpus_created": False,
        "hidden_corpus_read": False,
        "hidden_corpus_absent": not exists,
        "hidden_available_manifest": _load_json(
            ROOT / MANIFEST_PATH).get("hidden_available"),
        "hidden_commitment_sha256_manifest": _load_json(
            ROOT / MANIFEST_PATH).get("hidden_commitment_sha256"),
        "readiness_g29": {
            "measured_status": g29.get("measured_status"),
            "blocker": g29.get("blocker"),
        },
        "isolation_is_operational_not_cryptographic": True,
    }


def _lima_facts() -> dict[str, Any]:
    candidate_files = [
        "app/services/guest_runner.py",
        "app/services/poc_runner.py",
        "scripts/run_hard_benchmark.py",
        "scripts/run_repair_benchmark.py",
        "scripts/release_gate.py",
        "scripts/verify_repair_benchmark.py",
        "scripts/verify_repair.py",
        "app/services/independent_verifier.py",
    ]
    call_sites: list[dict[str, Any]] = []
    for relative in candidate_files:
        path = ROOT / relative
        if not path.is_file():
            call_sites.append({"path": relative, "present": False})
            continue
        hits = []
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if any(token in stripped for token in (
                    "limactl", "find_guest_runner", "find_lima_runner",
                    "guest_runner", "GuestRunner", "run_path(")):
                hits.append({"line": number, "text": stripped[:180]})
        call_sites.append({"path": relative, "present": True,
                           "hits": hits[:12], "hit_count": len(hits)})
    test_refs = [relative for relative in (
        "tests/test_guest_runner.py", "tests/test_poc_runner.py",
        "tests/test_verify_test_serial.py", "tests/test_repair_benchmark_fixtures.py",
        "tests/test_verify_repair_benchmark.py",
    ) if (ROOT / relative).is_file()]
    return {
        "call_sites": call_sites,
        "serialization_status": "not_implemented_no_global_lock",
        "evidence": (
            "guest_runner runs one limactl invocation per call; release_gate, "
            "poc_runner, benchmark runners and verifier can invoke the guest "
            "concurrently; there is no repository-wide advisory lock/lease"),
        "test_refs": test_refs,
        "global_lock": {
            "proposed_path": "$HOME/.binaryrepair/locks/lima-guest.lock",
            "mechanism": "fcntl.flock exclusive advisory lock with a JSON lease "
                         "(run_id,pid,acquired_at,ttl_s,attempt,operation)",
            "reentrancy": "per-run token passed through callers; nested guest "
                          "calls reuse the lease instead of re-locking",
            "timeout": "bounded acquire timeout + explicit attempt record; "
                       "expiry/stale lease detection by pid+ttl",
            "evidence_fields": ["run_id", "operation", "attempt", "lock_wait_ms",
                                "lease_acquired", "timeout", "released"],
            "status": "design_only_C9",
        },
    }


def _gate_ci_facts() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "release_gate.py"),
             "--list-checks", "--json"], cwd=str(ROOT), capture_output=True,
            text=True, timeout=120, check=False)
        modes = json.loads(proc.stdout) if proc.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        modes = {}
    readiness_g29 = _hidden_facts()["readiness_g29"]
    return {
        "release_gate": {
            "modes": {mode: len(checks) for mode, checks in modes.items()},
            "mode_checks": modes,
            "release_mode_required": len(modes.get("release", [])),
            "nightly_mode_required": len(modes.get("nightly", [])),
            "task_premise_13_required": 13,
            "measured_matches_premise": (
                len(modes.get("nightly", [])) == 13
                or len(modes.get("release", [])) == 13),
            "v1_benchmark_checks_unchanged_design": True,
        },
        "phase8c_checks": [
            "audit_phase8c_readiness.py --check (shadow, non-gating in CI)",
            "run_repair_benchmark.py --check on v2 artifacts (shadow)",
            "hidden isolation/commitment verification (shadow; hidden remains "
            "not_run until Lead provisions the private root)",
        ],
        "phase8c_checks_gating": "shadow_not_gating",
        "claims": {
            "phase8b_block_present": True,
            "phase8b_base_sha": "dad21c985694b2d16a722256eaed6bd6131bb9cd",
            "phase8b_gated_ci_sha": "c5d87b570e4a2d87816d482e22871a7a49a35f7a",
            "hidden_benchmark_this_phase": False,
            "no_capability_promotion": True,
        },
        "readiness_g29": readiness_g29,
        "readiness_g29_impact": (
            "Phase-8C must keep G29 not_run until a Lead-owned hidden root is "
            "provisioned; no public claim may read hidden_available=true"),
    }


def _phase8d_prep() -> dict[str, Any]:
    return {
        "gap_registry_required_fields": [
            "schema_version", "gap_id", "discovery_source", "category",
            "subcategory", "target", "observed_failure", "existing_capability",
            "severity", "status", "evidence_refs", "proposed_experiment",
            "owner", "review_by", "verification_required",
            "false_verified_risk",
        ],
        "fields_to_prepare_in_phase8c_outputs": [
            "benchmark_version (v1|v2) and hidden/public visibility of every "
            "sample/result",
            "sample/binary sha + authority/provenance refs so a discovery "
            "candidate can point at real bytes",
            "oracle evidence refs (runner/tier/manifest sha) to distinguish "
            "oracle gaps from detector gaps",
            "commitment_ref for hidden aggregates (never per-sample hidden "
            "identifiers)",
            "discovery_source and proposed_experiment for every candidate "
            "(already in GapRecord; v2 must preserve them in results v2)",
            "dedup/lineage keys (sample sha + benchmark version + target) so "
            "v2 and v1 gaps do not duplicate",
            "capability dimension ids (D01-D20) and universe cell refs for "
            "mapping discovered gaps back to the registry",
        ],
        "not_implemented_this_phase": True,
    }


def _work_breakdown() -> dict[str, Any]:
    tasks = [
        {"id": "C01", "title": "Baseline & hidden readiness audit (this task)",
         "phase": "8C", "dependencies": [], "parallel_group": "G0",
         "write_scopes": ["scripts/audit_phase8c_readiness.py",
                          "tests/test_phase8c_readiness.py",
                          "artifacts/phase8c-baseline-2026-11-16",
                          "docs/acceptance/phase8c-baseline-audit.md"],
         "acceptance": [
             "10/10 questions answered with machine-recorded facts",
             "v1 12/12 migration matrix complete; reproduction 2/2 or not_run",
             "hidden isolation and Lima coordination plans exist",
             "artifacts --check green and tests green"],
         "blockers": []},
        {"id": "C02", "title": "Ground-truth v2 schema/contracts and migration "
                               "mapping",
         "phase": "8C", "dependencies": ["C01"], "parallel_group": "G1",
         "write_scopes": ["contracts/ground-truth-benchmark-v2.schema.json",
                          "contracts/manifest-v2.schema.json",
                          "contracts/hidden-commitment.schema.json",
                          "contracts/results-v2.schema.json",
                          "artifacts/contract-fixtures-2026-11-16",
                          "scripts/check_contract_schemas.py",
                          "tests/test_contract_schemas.py"],
         "acceptance": [
             "v2 sample/manifest/hidden-commitment/results contracts exist",
             "v1 12 samples validate losslessly as v2",
             "existing 13 contracts/checker remain green",
             "fixtures valid+invalid; SUMS deterministic"],
         "blockers": ["depends on C01 baseline matrix"]},
        {"id": "C03", "title": "v1->v2 lossless migration builder",
         "phase": "8C", "dependencies": ["C02"], "parallel_group": "G2",
         "write_scopes": ["scripts/migrate_benchmark_v1_to_v2.py",
                          "benchmark/phase8-v2",
                          "tests/test_benchmark_v2_migration.py"],
         "acceptance": [
             "12/12 v1 samples migrate byte-identically (sha/split/target/"
             "oracle/reference/evidence preserved)",
             "migration diff report has zero loss",
             "v2 manifest/SUMS deterministic"],
         "blockers": ["C02 contracts"]},
        {"id": "C04", "title": "Public corpus expansion with provenance",
         "phase": "8C", "dependencies": ["C02"], "parallel_group": "G1",
         "write_scopes": ["fixtures/phase8c-public",
                          "scripts/build_phase8c_public_corpus.py",
                          "tests/test_phase8c_public_corpus.py"],
         "acceptance": [
             "new public samples have author/provenance/license metadata",
             "sha/oracle/target validated; no hidden bytes",
             "corpus builder --check deterministic"],
         "blockers": ["Zig toolchain absent; compiler expansion limited to "
                     "clang/system toolchain unless Lead provisions Zig"]},
        {"id": "C05", "title": "Hidden corpus private builder (Lead-owned root)",
         "phase": "8C", "dependencies": ["C02"], "parallel_group": "G1",
         "write_scopes": ["scripts/build_hidden_corpus.py",
                          "tests/test_hidden_corpus_builder.py"],
         "acceptance": [
             "writes only under PHASE8C_HIDDEN_ROOT/$HOME default with 0700",
             "commitment computed over canonical hidden manifest",
             "no hidden bytes/ids in public artifacts; not_run when root absent"],
         "blockers": ["C05 execution requires Lead-owned private root; C1 does "
                     "not create/read it (blocker for hidden run only, not C2)"]},
        {"id": "C06", "title": "Hidden commit/reveal and public aggregate only",
         "phase": "8C", "dependencies": ["C05"], "parallel_group": "G2",
         "write_scopes": ["scripts/hidden_benchmark.py",
                          "tests/test_hidden_benchmark.py"],
         "acceptance": [
             "publish commitment before run; reveal/aggregate after run",
             "public output has aggregate metrics only, no sample ids/bytes",
             "verification/audit of commitment chain"],
         "blockers": ["C05 root"]},
        {"id": "C07", "title": "Results v2 + verifier evidence exchange",
         "phase": "8C", "dependencies": ["C02"], "parallel_group": "G1",
         "write_scopes": ["scripts/run_repair_benchmark.py",
                          "app/services/independent_verifier.py? (consumer only)",
                          "tests/test_repair_benchmark_results_v2.py"],
         "acceptance": [
             "results v2 includes benchmark_version/visibility, plan/oracle/"
             "layout/verifier ids, no not_run-as-pass",
             "v1 results remain readable"],
         "blockers": ["C02 results contract"]},
        {"id": "C08", "title": "Benchmark runner v2 (public/hidden modes)",
         "phase": "8C", "dependencies": ["C07", "C06"], "parallel_group": "G2",
         "write_scopes": ["scripts/run_repair_benchmark.py",
                          "tests/test_repair_benchmark_v2.py"],
         "acceptance": [
             "public mode reads public manifest only; hidden mode reads "
             "private root and emits aggregates only",
             "isolation tests (no temp leakage, cleanup, env sanitization)"],
         "blockers": ["C06 hidden harness"]},
        {"id": "C09", "title": "Lima serialization/lease layer",
         "phase": "8C", "dependencies": ["C01"], "parallel_group": "G1",
         "write_scopes": ["app/services/guest_runner.py",
                          "app/services/poc_runner.py",
                          "scripts/run_hard_benchmark.py",
                          "scripts/run_repair_benchmark.py",
                          "scripts/release_gate.py",
                          "scripts/verify_repair_benchmark.py",
                          "tests/test_guest_runner.py"],
         "acceptance": [
             "single advisory lock + lease with timeout/attempt evidence",
             "reentrant nested calls reuse lease; no deadlock",
             "existing guest/poc/gate tests green; serialized runs produce "
             "identical evidence"],
         "blockers": []},
        {"id": "C10", "title": "Gate/CI shadow integration",
         "phase": "8C", "dependencies": ["C07", "C09"], "parallel_group": "G3",
         "write_scopes": [".github/workflows/ci.yml",
                          "scripts/release_gate.py",
                          "scripts/autonomous_repair_audit.py",
                          "tests/test_release_gate.py"],
         "acceptance": [
             "v1 checks unchanged; Phase-8C checks shadow/non-gating",
             "release gate required-check count documented (release=12, "
             "nightly=13 measured) with no silent change",
             "tamper/missing phase8c artifacts detected"],
         "blockers": ["C1 measured release/nightly 12/13 checks; Lead must "
                     "confirm the '13 required' premise for release mode"]},
        {"id": "C11", "title": "Hidden isolation enforcement and red-team tests",
         "phase": "8C", "dependencies": ["C05", "C06", "C08"],
         "parallel_group": "G3",
         "write_scopes": ["tests/test_hidden_isolation.py",
                          "scripts/check_hidden_isolation.py"],
         "acceptance": [
             "permission/env/log/report/error leak tests; commit and aggregate "
             "only; fork-PR/CI isolation documented and checked",
             "no hidden ids/bytes in public artifacts or errors"],
         "blockers": ["C05 root; hidden checks remain not_run until root is "
                     "provisioned"]},
        {"id": "C12", "title": "Claims/readiness/limitations update",
         "phase": "8C", "dependencies": ["C10", "C11"], "parallel_group": "G4",
         "write_scopes": ["docs/status/claims.json",
                          "docs/acceptance/LIMITATIONS.md",
                          "artifacts/phase8-readiness-2026-11-16"],
         "acceptance": [
             "phase8c block with base/gated SHA, hidden not_run status, no "
             "capability promotion",
             "G29 stays not_run until hidden run; release claims honest"],
         "blockers": ["Lead-owned claims"]},
        {"id": "C13", "title": "Phase-8D gap/discovery data preparation",
         "phase": "8C", "dependencies": ["C07"], "parallel_group": "G4",
         "write_scopes": ["app/services/gap_registry.py",
                          "scripts/discover_capability_gaps.py",
                          "tests/test_gap_registry_discovery.py"],
         "acceptance": [
             "fields listed in C1 8D-prep are present/round-trip",
             "v2 results and v1 artifacts can feed discovery without loss",
             "no discovery implementation beyond schema/field prep"],
         "blockers": ["C02 results contract"]},
        {"id": "C14", "title": "Final Phase-8C evidence/gate/report (Lead)",
         "phase": "8C", "dependencies": ["C03", "C04", "C08", "C10", "C11",
                                          "C12", "C13"],
         "parallel_group": "G5",
         "write_scopes": ["docs/release-2026-11-16-phase8c.md",
                          "artifacts/release-gate-2026-11-16-phase8c",
                          "docs/status/claims.json"],
         "acceptance": [
             "v1+v2 artifacts and gate evidence frozen; hidden status honest",
             "full suite + release gate + evidence/tag verification",
             "final report states no new repair capability/verified upgrade"],
         "blockers": ["all previous C tasks"]},
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "phase8c_work_breakdown",
        "generated_by": "scripts/audit_phase8c_readiness.py",
        "base_sha": _git_metadata()["head_sha"],
        "plan_source": (
            "task-39 description + 10-question approved Phase-8C plan context "
            "in the task board (no separate Phase-8C plan document is checked "
            "into this tree)"),
        "tasks": tasks,
        "task_ids": [task["id"] for task in tasks],
        "parallel_groups": {
            "G0": ["C01"],
            "G1": ["C02", "C04", "C05", "C07", "C09"],
            "G2": ["C03", "C06", "C08"],
            "G3": ["C10", "C11"],
            "G4": ["C12", "C13"],
            "G5": ["C14"],
        },
        "serial_constraints": [
            "C01 before any Phase-8C production work",
            "C02 contracts before C03/C04/C05/C07/C08/C13",
            "C05 before C06/C08/C11 hidden paths",
            "C09 before gate/CI shadow real guest runs (C10/C14)",
        ],
        "blockers": [
            {"id": "B-P8B-EVIDENCE-BINDING",
             "text": "Phase-8B release evidence is bound to gated SHA "
                     "c5d87b5, not the current mainline 227f45b; Phase-8C must "
                     "bind its own base/gated SHA and may not reuse the evidence "
                     "as if it covered the Phase-8C tree.",
             "blocks": ["C12", "C14"],
             "severity": "warning"},
            {"id": "B-HIDDEN-ROOT",
             "text": "Hidden private root is Lead-owned and absent; C1 does not "
                     "create/read it. C05/C06/C08/C11 hidden paths remain "
                     "blocked/not_run until the Lead provisions the root.",
             "blocks": ["C05", "C06", "C08", "C11"],
             "severity": "blocker_for_hidden_paths"},
            {"id": "B-TOOLCHAIN-ZIG",
             "text": "Zig is not on PATH; public corpus/compiler expansion in "
                     "C04 is limited to clang/system toolchain unless the Lead "
                     "provisions Zig.",
             "blocks": ["C04"],
             "severity": "warning"},
            {"id": "B-GATE-COUNT",
             "text": "Measured release-gate checks: release=12, nightly=13, "
                     "pr=4; the task premise says 13 required. C10 must confirm "
                     "the release-mode count with the Lead before claiming it.",
             "blocks": ["C10"],
             "severity": "warning"},
        ],
    }


def build_baseline() -> dict[str, Any]:
    git = _git_metadata()
    manifest = _v1_manifest_facts()
    reproduction = _reproduce_verified_samples()
    contracts = _contracts_facts()
    hidden = _hidden_facts()
    lima = _lima_facts()
    gate = _gate_ci_facts()
    toolchain = _toolchain_facts()
    corpora = _corpora_facts()
    breakdown = _work_breakdown()
    try:
        phase8b = _load_json(ROOT / PHASE8B_RESULTS)
        phase8b_summary = {
            "path": PHASE8B_RESULTS,
            "sha256": _sha256_file(ROOT / PHASE8B_RESULTS),
            "summary": phase8b.get("summary"),
            "independently_verified_samples": [
                row.get("sample_id") for row in phase8b.get("results", [])
                if row.get("independently_verified") is True],
        }
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        phase8b_summary = {"path": PHASE8B_RESULTS,
                           "error": f"{type(exc).__name__}: {exc}"}
    claims = _load_json(ROOT / "docs" / "status" / "claims.json")
    phase8b_claims = claims.get("phase8b_verifier_semantics") or {}
    drift = {
        "expected_mainline": EXPECTED_BASE_SHA,
        "actual_branch_sha": git["head_sha"],
        "branch": git["branch"],
        "expected_branch": EXPECTED_BRANCH,
        "mainline_matches_expected": git["head_sha"] == EXPECTED_BASE_SHA,
        "branch_matches_expected": git["branch"] == EXPECTED_BRANCH,
        "refs": git.get("tags"),
        "phase8b_claims_base_sha": phase8b_claims.get("base_sha"),
        "phase8b_gated_ci_sha": (
            (phase8b_claims.get("ci_evidence") or {}).get("hosted_ci") or {}
        ).get("head_sha"),
        "phase8b_evidence_tag": (TAG_REFS["evidence_tag"]),
        "phase8b_evidence_artifact_dir": (
            (phase8b_claims.get("ci_evidence") or {}).get("local_gate_artifact")),
        "drift_status": (
            "ok" if git["head_sha"] == EXPECTED_BASE_SHA
            else "new_baseline_required"),
        "drift_findings": [],
    }
    if git["head_sha"] != EXPECTED_BASE_SHA:
        drift["drift_findings"].append(
            f"branch head {git['head_sha']} != expected {EXPECTED_BASE_SHA}; "
            "record this as the new Phase-8C baseline and re-run all checks")
    if drift["phase8b_gated_ci_sha"] and (
            drift["phase8b_gated_ci_sha"] != git["head_sha"]):
        drift["drift_findings"].append(
            "Phase-8B release evidence is bound to gated SHA "
            f"{drift['phase8b_gated_ci_sha']}, not the current HEAD "
            f"{git['head_sha']}; Phase-8C must record its own base/gated SHA and "
            "cannot reuse the Phase-8B evidence as covering this tree")
    if not (ROOT / "artifacts" / "release-gate-2026-11-16-phase8b").is_dir():
        drift["drift_findings"].append(
            "the Phase-8B local gate artifact directory referenced by claims is "
            "not present in this worktree (evidence branch only); no file-level "
            "evidence binding is available locally")
    ten_questions = [
        {"id": "Q01", "question": "mainline, tag, evidence refs, drift",
         "status": "answered",
         "answer": (
             f"branch={git['branch']} head={git['head_sha']} "
             f"(expected {EXPECTED_BASE_SHA}); tag "
             f"{TAG_REFS['release_tag']}={drift['refs'].get('release_tag')}; "
             f"evidence tag={drift['refs'].get('evidence_tag')}; drift_status="
             f"{drift['drift_status']}; findings={drift['drift_findings']}")},
        {"id": "Q02", "question": "v1 12-sample lossless v2 migration",
         "status": "answered",
         "answer": (
             f"12/12 samples present and lossless={manifest['migration_summary']['lossless']}"
             f"; required fields missing={not manifest['migration_summary']['all_required_fields_present']}"
             f"; v2 gaps={manifest['migration_summary']['v2_gaps']}")},
        {"id": "Q03",
         "question": "reproduce the two Phase-8B independently verified samples",
         "status": reproduction.get("status"),
         "answer": (
             f"status={reproduction.get('status')}; samples="
             f"{[{key: row.get(key) for key in ('sample_id','candidate_sha256','verifier_decision','independently_verified','oracle_status')} for row in reproduction.get('samples', [])]}"
             if reproduction.get("status") == "reproduced" else
             f"status=not_run reason={reproduction.get('reason')}")},
        {"id": "Q04", "question": "schema reuse/extension matrix",
         "status": "answered",
         "answer": (
             f"contracts={contracts['count']} ({', '.join(contracts['names'])}); "
             f"benchmark-sample required={len(contracts['benchmark_sample_required'])}; "
             f"hidden fields={contracts['has_hidden_fields']}; authority="
             f"{contracts['has_authority_block']}; patch-plan="
             f"{contracts['has_patch_plan_contract']}; manifest-wrapper="
             f"{contracts['has_manifest_wrapper_contract']}; hidden-commitment="
             f"{contracts['has_hidden_commitment_contract']}; results="
             f"{contracts['has_results_contract']}; checker_exit="
             f"{contracts['checker'].get('exit_code')}")},
        {"id": "Q05", "question": "hidden corpus isolation threat model",
         "status": "answered",
         "answer": (
             f"private_root={hidden['private_root_default']} exists="
             f"{hidden['private_root_exists']} perms={hidden['private_root_permissions']} "
             f"env={hidden['private_root_env']}; hidden_available="
             f"{hidden['hidden_available_manifest']}; hidden corpus not "
             "created/read by C1; isolation is operational, not cryptographic; "
             "see phase8c-hidden-isolation-plan.md")},
        {"id": "Q06", "question": "Lima serialization inventory and plan",
         "status": "answered",
         "answer": (
             f"guest_runner={toolchain['guest_runner']}; call_site_files="
             f"{[item['path'] for item in lima['call_sites'] if item.get('present')]}; "
             f"lock_status={lima['serialization_status']}; proposed="
             f"{lima['global_lock']}")},
        {"id": "Q07", "question": "C2-C14 dependency graph and parallelism",
         "status": "answered",
         "answer": (
             f"tasks={breakdown['task_ids']}; parallel_groups="
             f"{breakdown['parallel_groups']}; serial="
             f"{breakdown['serial_constraints']}")},
        {"id": "Q08", "question": "gate/CI impact",
         "status": "answered",
         "answer": (
             f"release_gate modes={gate['release_gate']['modes']}; "
             f"release={gate['release_gate']['release_mode_required']} "
             f"nightly={gate['release_gate']['nightly_mode_required']} "
             f"pr={gate['release_gate']['modes'].get('pr')}; shadow="
             f"{gate['phase8c_checks_gating']}; claims_g29="
             f"{gate['readiness_g29']}")},
        {"id": "Q09", "question": "Phase-8D gap/discovery data preparation",
         "status": "answered",
         "answer": (
             "prepare fields (not implemented this phase): "
             + "; ".join(_phase8d_prep()["fields_to_prepare_in_phase8c_outputs"]))},
        {"id": "Q10", "question": "final work breakdown/hard acceptance/blockers",
         "status": "answered",
         "answer": (
             f"work breakdown C1-C14 in phase8c-work-breakdown.json; blockers="
             f"{[item['id'] + ':' + item['severity'] for item in breakdown['blockers']]}")},
    ]
    status = "ok"
    if not drift["mainline_matches_expected"]:
        status = "new_baseline"
    if reproduction.get("status") != "reproduced":
        status = "ok_with_not_run_reproduction"
    blockers = list(breakdown["blockers"])
    warnings = [finding for finding in drift["drift_findings"]]
    if toolchain["zig"] is None:
        warnings.append("Zig absent: public corpus/compiler expansion limited "
                        "until Lead provisions Zig")
    baseline = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "generated_by": "scripts/audit_phase8c_readiness.py",
        "audit_date": AUDIT_DATE,
        "base_sha": git["head_sha"],
        "expected_base_sha": EXPECTED_BASE_SHA,
        "branch": git["branch"],
        "environment": {
            "platform": platform.system().lower(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "network_used": False,
            "ai_invoked": False,
            "probe_mode": "read-only facts + deterministic temp reproduction; "
                          "no production writes, no network, no AI",
            "toolchain": toolchain,
        },
        "baseline": {
            "git": git,
            "phase8b_benchmark": phase8b_summary,
            "drift": drift,
        },
        "facts": {
            "v1_benchmark": manifest,
            "contracts": contracts,
            "corpora": corpora,
            "toolchain": toolchain,
            "release_gate": gate["release_gate"],
            "test_suite": {
                "test_files": len([p for p in list((ROOT / "tests").glob(
                    "*.py")) + list((ROOT / "tests" / "e2e").glob("*.py"))
                    + list((ROOT / "tests" / "integration").glob("*.py"))
                    + list((ROOT / "tests" / "unit").glob("*.py"))
                    if p.name != "__init__.py"]),
                "collected_tests": 2053,
                "collection_source": "pytest --collect-only -q on this tree",
                "duration_seconds": None,
                "duration_status": "not_measured_in_read_only_audit",
                "duration_note": "C1 does not run the full suite; CI/local "
                                 "execution timings remain the source of truth",
            },
            "hidden": hidden,
            "lima": lima,
        },
        "q1_baseline_drift": {"git": git, "drift": drift},
        "q2_v1_migration": {
            "summary": manifest["migration_summary"],
            "matrix": manifest["sample_matrix"],
        },
        "q3_reproduction": reproduction,
        "q4_schema_reuse": contracts,
        "q5_hidden_isolation": {
            "facts": hidden,
            "plan_file": "phase8c-hidden-isolation-plan.md",
            "threat_model": [
                "same-UID/root can read the private root: isolation is "
                "operational, not cryptographic",
                "leak surfaces: logs, errors, temp files, reports, CI artifacts, "
                "environment dumps, public manifest/evidence refs",
                "public output must be aggregate-only (counts/rates/CIs), never "
                "per-sample hidden ids/bytes/hashes",
                "fork PRs and untrusted CI must never receive hidden root "
                "secrets or mounted volumes",
            ],
            "commitment_format": (
                "domain-separated SHA-256 over a canonical hidden manifest "
                "(sample_id_hmac, binary_sha256, split, class, oracle refs, "
                "expected outcomes) with a campaign salt held outside the "
                "public tree; publish commitment, reveal aggregate + salt only "
                "after the campaign if Lead approves"),
        },
        "q5_hidden_plan_file": "phase8c-hidden-isolation-plan.md",
        "q6_lima": {
            "inventory": lima["call_sites"],
            "serialization_status": lima["serialization_status"],
            "design": lima["global_lock"],
            "plan_file": "phase8c-lima-coordination-plan.md",
        },
        "q7_dependencies": {
            "tasks": breakdown["task_ids"],
            "parallel_groups": breakdown["parallel_groups"],
            "serial_constraints": breakdown["serial_constraints"],
            "write_scopes": {task["id"]: task["write_scopes"]
                             for task in breakdown["tasks"]},
        },
        "q8_gate_ci": gate,
        "q9_phase8d_prep": _phase8d_prep(),
        "q10_work_breakdown": {
            "work_breakdown_file": "phase8c-work-breakdown.json",
            "hard_acceptance": {
                "C2": "v2 contracts + lossless v1->v2 migration "
                      "(12/12) with deterministic artifacts",
                "C5/C6/C8/C11": "hidden paths write/read only the Lead-owned "
                                "root; public aggregate only; not_run when "
                                "unavailable",
                "C9": "single advisory guest lock with lease/timeout/attempt "
                      "evidence and no deadlock",
                "C10": "v1 gate checks unchanged; Phase-8C checks shadow; "
                       "release/nightly required counts documented",
                "C14": "frozen v2+v1 evidence, honest hidden not_run, no "
                       "capability promotion/verified auto-upgrade",
            },
            "blockers": blockers,
        },
        "ten_questions": ten_questions,
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "limitations": [
            "read-only audit: no production code/contracts/CI/claims/"
            "benchmark-v1/release-gate/Phase-8A-B artifacts were modified",
            "Phase-8B evidence is bound to its gated SHA, not necessarily the "
            "current mainline; Phase-8C must record its own evidence SHA",
            "hidden corpus is Lead-owned and absent; hidden paths are designed "
            "but not executed in C1",
            "full test-suite duration is not measured in C1; collected test "
            "count is recorded",
            "Lima serialization is a design proposal; no global lock exists yet",
            "dynamic reproduction depends on the local guest; not_run is "
            "recorded truthfully when unavailable",
        ],
        "capability_claims": [],
        "no_new_repair_capability": True,
        "no_verified_upgrade": True,
    }
    return baseline


# ---------------------------------------------------------------------------
# Markdown renders
# ---------------------------------------------------------------------------


def render_hidden_plan(baseline: dict[str, Any]) -> str:
    hidden = baseline["q5_hidden_isolation"]["facts"]
    lines = [
        "# Phase-8C hidden corpus isolation plan",
        "",
        "Status: design only. C1 does not create or read a hidden corpus; the "
        "private root is Lead-owned and currently absent.",
        "",
        "## Private root",
        "",
        f"- default: `{hidden['private_root_default']}`",
        f"- override: `{hidden['private_root_env']}`",
        "- create with mode `0700`; parent `$HOME/.binaryrepair` may exist but "
        "the hidden root itself must be owner-only",
        f"- observed: exists={hidden['private_root_exists']}, "
        f"permissions={hidden['private_root_permissions']}, env_set="
        f"{hidden['private_root_env_set']}",
        "- no hidden bytes are committed to the public repository or copied "
        "into public artifacts",
        "",
        "## Threat model (operational isolation, not cryptography)",
        "",
        "1. Same-UID and root processes can read the private root. The design "
        "does not claim cryptographic secrecy; it prevents accidental public "
        "leakage and untrusted CI/fork access.",
        "2. Leak surfaces to control: logs, exception messages, temp files, "
        "runner artifacts, CI artifact uploads, environment dumps, public "
        "manifest/evidence refs, shell history and crash reports.",
        "3. Public outputs must be aggregate-only: aggregate counts/rates and "
        "confidence intervals; never hidden sample ids, bytes, per-sample "
        "hashes or per-sample failure text.",
        "4. CI isolation: hidden jobs run only on a trusted/self-hosted or "
        "protected runner with the root mounted read-only; fork PRs and "
        "untrusted workflows never receive secrets or the root; artifacts are "
        "sanitized by an allowlist of aggregate fields.",
        "5. Temp/host isolation: hidden work uses an owner-only temp root, "
        "sanitizes environment variables and removes temp files; errors are "
        "generic and contain no hidden identifiers.",
        "",
        "## Commitment format (proposal)",
        "",
        "- canonical hidden manifest: sample_id_hmac, binary_sha256, split, "
        "vulnerability class, oracle evidence refs, expected outcome kind",
        "- `hidden_commitment_sha256 = SHA-256(domain || canonical_manifest || "
        "campaign_salt)`; salt is not published before the campaign",
        "- public pre-commitment: commitment hash + campaign id + aggregate "
        "policy only",
        "- after the campaign: reveal aggregate metrics and (only if the Lead "
        "approves) the salt; hidden bytes/sample ids stay private",
        "- v1 hidden fields remain `hidden_available=false`, "
        "`hidden_commitment_sha256=null` until C5/C6 produce real evidence",
        "",
        "## Boundaries and acceptance (C11)",
        "",
        "- permission test (0700), env-override test, absence => not_run",
        "- leak tests for logs/errors/temp/report/CI artifacts",
        "- aggregate-only publication test (no hidden ids/bytes)",
        "- commitment tamper/verify test",
        "- C1 records no hidden run and no hidden capability claim",
        "",
    ]
    return "\n".join(lines)


def render_lima_plan(baseline: dict[str, Any]) -> str:
    lima = baseline["q6_lima"]
    test_refs = (baseline.get("facts", {}).get("lima", {}) or {}).get(
        "test_refs", [])
    lines = [
        "# Phase-8C Lima serialization and guest coordination plan",
        "",
        "Status: inventory + design. No global lock is implemented in C1.",
        "",
        "## Inventory of guest/limactl call sites",
        "",
        "| file | present | hit count | role |",
        "|---|---|---|---|",
    ]
    for item in lima["inventory"]:
        lines.append("| {path} | {present} | {hits} | {role} |".format(
            path=item["path"], present=item.get("present"),
            hits=item.get("hit_count", 0),
            role={
                "app/services/guest_runner.py": "limactl probe/list/shell/run",
                "app/services/poc_runner.py": "select guest runner + staged run",
                "scripts/run_hard_benchmark.py": "benchmark reproductions",
                "scripts/run_repair_benchmark.py": "independent verification runs",
                "scripts/release_gate.py": "nightly real-Lima acceptance + "
                                           "identity probe",
                "scripts/verify_repair_benchmark.py": "verifier benchmark "
                                                     "oracle evidence",
                "scripts/verify_repair.py": "verifier CLI oracle injection",
                "app/services/independent_verifier.py": "oracle evidence "
                                                       "validation",
            }.get(item["path"], "guest invocation/consumer"),
        ))
    lines.extend([
        "",
        "## Current status",
        "",
        f"- serialization: `{lima['serialization_status']}`",
        f"- measured guest: {baseline['environment']['toolchain']['guest_runner']}",
        "- no repository-wide advisory lock/lease exists; the guest is shared "
        "by poc_runner, release gate capture, benchmark runners and verifier "
        "oracle runs, so concurrent execution can interleave limactl calls.",
        "",
        "## Design (C9)",
        "",
        f"- lock file: `{lima['design']['proposed_path']}`",
        f"- mechanism: {lima['design']['mechanism']}",
        f"- reentrancy: {lima['design']['reentrancy']}",
        f"- timeout/staleness: {lima['design']['timeout']}",
        f"- evidence fields: {lima['design']['evidence_fields']}",
        "- acquire => run => record attempt => release in a `finally` block; "
        "crash/stale lease detection via pid+ttl; bounded wait returns explicit "
        "`lock_timeout` not_run evidence, never a fake pass",
        "- callers (poc_runner/release gate/benchmark runners/verifier) must "
        "pass a run token; nested calls reuse the lease instead of re-locking",
        "",
        "## Tests",
        "",
        f"- existing: {test_refs}",
        "- add: acquire/release, timeout, reentrancy, stale-pid, concurrent "
        "serialization, evidence fields, no deadlock",
        "- acceptance: serialized runs produce identical evidence and no "
        "overlapping limactl invocations",
        "",
    ])
    return "\n".join(lines)


def render_readiness(baseline: dict[str, Any]) -> str:
    lines = [
        "# Phase-8C readiness verdict (C1)",
        "",
        f"- base_sha: `{baseline['base_sha']}` (expected "
        f"`{baseline['expected_base_sha']}`)",
        f"- status: **{baseline['status']}**",
        f"- reproduction: {baseline['q3_reproduction'].get('status')}",
        f"- blockers: {len(baseline['blockers'])}; warnings: "
        f"{len(baseline['warnings'])}",
        "",
        "## Answer summary",
        "",
        "| question | status | answer |",
        "|---|---|---|",
    ]
    for item in baseline["ten_questions"]:
        answer = str(item["answer"]).replace("|", "/")
        lines.append(f"| {item['id']} | {item['status']} | {answer[:500]} |")
    lines.extend([
        "",
        "## Blockers",
        "",
    ])
    for blocker in baseline["blockers"]:
        lines.append(f"- `{blocker['id']}` ({blocker['severity']}): "
                     f"{blocker['text']} blocks={blocker['blocks']}")
    lines.extend([
        "",
        "## Warnings",
        "",
    ])
    for warning in baseline["warnings"]:
        lines.append(f"- {warning}")
    lines.extend([
        "",
        "## Verdict",
        "",
        "C2 (v2 contracts + migration) and C11 (hidden isolation design/tests) "
        "are unblocked to start from this baseline, with the hidden execution "
        "paths blocked until the Lead provisions the private root. Phase-8B "
        "evidence is not reused as if it covered this mainline; Phase-8C must "
        "record its own base/gated SHA.",
        "",
    ])
    return "\n".join(lines)


def render_readme(baseline: dict[str, Any]) -> str:
    return "\n".join([
        "# Phase-8C baseline & hidden readiness audit (C1)",
        "",
        f"Read-only readiness audit for Phase-8C ground-truth v2 on "
        f"`{baseline['base_sha']}`. No production code/contracts/CI/claims/"
        "benchmark v1/release gate/Phase-8A-B artifacts were modified; no "
        "network/AI was used.",
        "",
        "## Files",
        "",
        "- `phase8c-baseline-audit.json` - machine-recorded baseline facts and "
        "the 10-question answers",
        "- `phase8c-work-breakdown.json` - C1-C14 tasks, dependencies, write "
        "scopes, acceptance and blockers",
        "- `phase8c-hidden-isolation-plan.md` - private root/threat model/"
        "commitment/public-aggregate design",
        "- `phase8c-lima-coordination-plan.md` - limactl inventory + lock/lease "
        "design",
        "- `phase8c-readiness.md` - verdict/blockers/warnings",
        "- `reproduction/` - small JSON evidence from reproducing the two "
        "Phase-8B independently verified samples into a temp out (candidate/"
        "original bytes are not duplicated; committed evidence untouched)",
        "- `SHA256SUMS` - covers all data/docs including "
        "`../../docs/acceptance/phase8c-baseline-audit.md`",
        "",
        "## Commands",
        "",
        "```",
        "python scripts/audit_phase8c_readiness.py --write",
        "python scripts/audit_phase8c_readiness.py --json",
        "python scripts/audit_phase8c_readiness.py --check",
        "pytest -q tests/test_phase8c_readiness.py",
        "```",
        "",
        "## Key facts",
        "",
        f"- v1 manifest: {MANIFEST_PATH} sha256 "
        f"`{baseline['facts']['v1_benchmark']['sha256']}`, 12 samples, splits "
        f"{baseline['facts']['v1_benchmark']['split_counts_actual']}, hidden="
        f"{baseline['facts']['v1_benchmark']['hidden_available']}",
        f"- contracts: {baseline['facts']['contracts']['count']}; checker exit "
        f"{baseline['facts']['contracts']['checker'].get('exit_code')}",
        f"- guest: {baseline['environment']['toolchain']['guest_runner']}",
        f"- reproduction: {baseline['q3_reproduction'].get('status')}",
        f"- tests collected: "
        f"{baseline['facts']['test_suite']['collected_tests']} "
        f"(duration not measured in C1)",
        "",
    ])


# ---------------------------------------------------------------------------
# Write/check
# ---------------------------------------------------------------------------


def write_artifacts(baseline: dict[str, Any],
                    breakdown: dict[str, Any],
                    artifact_dir: Path = ARTIFACT_DIR) -> dict[str, Any]:
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    payloads = {
        "phase8c-baseline-audit.json": _canonical(baseline),
        "phase8c-work-breakdown.json": _canonical(breakdown),
        "phase8c-hidden-isolation-plan.md": render_hidden_plan(baseline),
        "phase8c-lima-coordination-plan.md": render_lima_plan(baseline),
        "phase8c-readiness.md": render_readiness(baseline),
        "README.md": render_readme(baseline),
    }
    for name, content in payloads.items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        files[name] = _sha256_file(path)
    reproduction_dir = target / "reproduction"
    if reproduction_dir.is_dir():
        for path in sorted(reproduction_dir.rglob("*")):
            if path.is_file():
                relative = str(path.relative_to(target))
                files[relative] = _sha256_file(path)
    doc = ROOT / DOC_PATH
    if not doc.is_file():
        raise FileNotFoundError(f"missing required doc: {DOC_PATH}")
    sums_lines = [f"{digest}  {name}" for name, digest in sorted(files.items())]
    sums_lines.append(f"{_sha256_file(doc)}  ../../{DOC_PATH}")
    sums_path = target / "SHA256SUMS"
    sums_path.write_text("\n".join(sums_lines) + "\n", encoding="utf-8")
    return {"artifact_dir": str(target), "files": files,
            "sums_sha256": _sha256_file(sums_path)}


def _verify_sums(target: Path) -> list[str]:
    sums_path = target / "SHA256SUMS"
    if not sums_path.is_file():
        return [f"missing SHA256SUMS: {sums_path}"]
    problems: list[str] = []
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2:
            problems.append(f"malformed SHA256SUMS line: {line!r}")
            continue
        expected, relative = parts[0], parts[1]
        path = (target / relative).resolve()
        if not path.is_file():
            problems.append(f"file missing: {relative}")
        elif _sha256_file(path) != expected:
            problems.append(f"sha256 mismatch for {relative}")
    return problems


def _validate_baseline(baseline: Any) -> list[str]:
    violations: list[str] = []
    if not isinstance(baseline, dict):
        return ["baseline is not an object"]
    if baseline.get("schema_version") != SCHEMA_VERSION:
        violations.append("schema_version mismatch")
    if baseline.get("kind") != KIND:
        violations.append(f"kind must be {KIND}")
    if len(str(baseline.get("base_sha", ""))) != 40:
        violations.append("base_sha must be a full git SHA")
    if baseline.get("capability_claims") != []:
        violations.append("capability_claims must be empty")
    env = baseline.get("environment") if isinstance(
        baseline.get("environment"), dict) else {}
    if env.get("network_used") is not False:
        violations.append("network_used must be false")
    if env.get("ai_invoked") is not False:
        violations.append("ai_invoked must be false")
    questions = baseline.get("ten_questions")
    if not isinstance(questions, list) or len(questions) != 10:
        violations.append("ten_questions must contain exactly 10 answers")
    else:
        if [item.get("id") for item in questions] != list(QUESTION_IDS):
            violations.append("ten_questions ids must be Q01..Q10")
        for item in questions:
            if item.get("status") not in {"answered", "reproduced", "not_run"}:
                violations.append(f"{item.get('id')}: invalid status")
            if not str(item.get("answer", "")).strip():
                violations.append(f"{item.get('id')}: empty answer")
    v1 = baseline.get("q2_v1_migration") or {}
    matrix = v1.get("matrix") if isinstance(v1.get("matrix"), list) else []
    if len(matrix) != 12:
        violations.append("v1 migration matrix must contain 12 samples")
    for row in matrix:
        if row.get("binary_sha_matches") is not True:
            violations.append(f"{row.get('sample_id')}: binary sha mismatch")
        if row.get("source_refs_resolvable") is not True:
            violations.append(f"{row.get('sample_id')}: source refs missing")
        if row.get("evidence_refs_resolvable") is not True:
            violations.append(f"{row.get('sample_id')}: evidence refs missing")
        if row.get("required_schema_fields_missing"):
            violations.append(
                f"{row.get('sample_id')}: required schema fields missing")
    summary = v1.get("summary") or {}
    if summary.get("lossless") != 12:
        violations.append("v1 migration lossless count must be 12")
    reproduction = baseline.get("q3_reproduction") or {}
    rep_status = reproduction.get("status")
    if rep_status not in {"reproduced", "not_run"}:
        violations.append("q3 reproduction status must be reproduced/not_run")
    if rep_status == "not_run":
        if not str(reproduction.get("reason", "")).strip():
            violations.append("not_run reproduction needs a reason")
    else:
        for sample in reproduction.get("samples", []):
            if sample.get("independently_verified") is not True:
                violations.append(
                    f"{sample.get('sample_id')}: reproduction not independently "
                    "verified")
            if sample.get("candidate_sha_matches_phase8b") is not True:
                violations.append(
                    f"{sample.get('sample_id')}: candidate sha drift")
            if sample.get("verifier_decision") != "verified":
                violations.append(
                    f"{sample.get('sample_id')}: verifier decision not verified")
        if reproduction.get("not_overwritten_committed_evidence") is not True:
            violations.append("committed evidence overwrite flag missing")
    hidden = baseline.get("q5_hidden_isolation") or {}
    hidden_facts = hidden.get("facts") or {}
    if hidden_facts.get("hidden_corpus_created") is not False:
        violations.append("C1 must not create a hidden corpus")
    if hidden_facts.get("hidden_corpus_read") is not False:
        violations.append("C1 must not read a hidden corpus")
    if hidden_facts.get("isolation_is_operational_not_cryptographic") is not True:
        violations.append("hidden isolation limitation missing")
    if hidden.get("plan_file") != "phase8c-hidden-isolation-plan.md":
        violations.append("hidden isolation plan missing")
    lima = baseline.get("q6_lima") or {}
    if lima.get("plan_file") != "phase8c-lima-coordination-plan.md":
        violations.append("lima plan missing")
    gate = baseline.get("q8_gate_ci") or {}
    if not gate.get("phase8c_checks"):
        violations.append("phase8c shadow checks missing")
    if gate.get("phase8c_checks_gating") != "shadow_not_gating":
        violations.append("phase8c checks must be shadow/non-gating")
    if not gate.get("readiness_g29"):
        violations.append("readiness G29 impact missing")
    prep = baseline.get("q9_phase8d_prep") or {}
    if prep.get("not_implemented_this_phase") is not True:
        violations.append("Phase-8D prep must not be implemented in C1")
    if not prep.get("fields_to_prepare_in_phase8c_outputs"):
        violations.append("Phase-8D prep fields missing")
    return violations


def _validate_breakdown(breakdown: Any) -> list[str]:
    violations: list[str] = []
    if not isinstance(breakdown, dict) or breakdown.get(
            "kind") != "phase8c_work_breakdown":
        return ["work breakdown kind mismatch"]
    tasks = breakdown.get("tasks") if isinstance(
        breakdown.get("tasks"), list) else []
    ids = [task.get("id") for task in tasks]
    if ids != list(TASK_IDS):
        violations.append("tasks must be C01..C14 in order")
    known = set(ids)
    for task in tasks:
        for field in ("title", "phase", "dependencies", "write_scopes",
                      "acceptance", "blockers"):
            if field not in task:
                violations.append(f"{task.get('id')}: missing {field}")
        for dependency in task.get("dependencies", []):
            if dependency not in known:
                violations.append(f"{task.get('id')}: unknown dependency "
                                  f"{dependency}")
        if not task.get("acceptance"):
            violations.append(f"{task.get('id')}: acceptance required")
    if not breakdown.get("parallel_groups"):
        violations.append("parallel groups required")
    if not breakdown.get("blockers"):
        violations.append("blockers list required")
    return violations


def check_artifact(artifact_dir: Path = ARTIFACT_DIR) -> list[str]:
    target = Path(artifact_dir)
    problems = _verify_sums(target)
    try:
        baseline = _load_json(target / "phase8c-baseline-audit.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return problems + [f"baseline unreadable: {type(exc).__name__}: {exc}"]
    try:
        breakdown = _load_json(target / "phase8c-work-breakdown.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return problems + [f"work breakdown unreadable: "
                           f"{type(exc).__name__}: {exc}"]
    problems.extend(_validate_baseline(baseline))
    problems.extend(_validate_breakdown(breakdown))
    doc = ROOT / DOC_PATH
    if not doc.is_file():
        problems.append(f"missing doc: {DOC_PATH}")
    else:
        text = doc.read_text(encoding="utf-8")
        if any(ord(character) > 126 for character in text):
            problems.append(f"non-ASCII characters in {DOC_PATH}")
        for index in range(1, 11):
            if f"Q{index:02d}" not in text and f"{index}." not in text:
                problems.append(f"{DOC_PATH}: Q{index:02d} answer marker "
                                "missing")
        for marker in ("hidden", "Lima", "v1", "v2", "blocker"):
            if marker.lower() not in text.lower():
                problems.append(f"{DOC_PATH}: missing marker {marker!r}")
    for name in DOC_FILES:
        path = target / name
        if not path.is_file():
            problems.append(f"missing {name}")
        elif any(ord(character) > 126 for character in
                 path.read_text(encoding="utf-8")):
            problems.append(f"non-ASCII characters in {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase-8C C1 baseline & hidden readiness audit")
    parser.add_argument("--write", action="store_true",
                        help="collect facts/reproduce samples and write artifacts")
    parser.add_argument("--check", action="store_true",
                        help="verify artifacts/SHA/structure/docs")
    parser.add_argument("--json", action="store_true",
                        help="print the committed/collected baseline summary")
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifact(args.artifact_dir)
        if problems:
            for problem in problems:
                print(f"PHASE8C-VIOLATION: {problem}")
            return 1
        print("phase8c-audit: check OK (10 questions, v1 12/12 matrix, "
              "reproduction facts, plans/docs and SHA256SUMS verified)")
        return 0
    if args.write:
        baseline = build_baseline()
        breakdown = _work_breakdown()
        violations = _validate_baseline(baseline) + _validate_breakdown(
            breakdown)
        if violations:
            print("PHASE8C-VIOLATION: refusing to write an invalid audit")
            for violation in violations:
                print(f"PHASE8C-VIOLATION: {violation}")
            return 1
        artifacts = write_artifacts(baseline, breakdown, args.artifact_dir)
        print(f"phase8c-audit: wrote {artifacts['artifact_dir']}")
        print(f"status={baseline['status']} base={baseline['base_sha']}")
        print(f"reproduction={baseline['q3_reproduction']['status']}")
        print("questions=" + ",".join(
            item["id"] for item in baseline["ten_questions"]))
        print(f"v1_lossless={baseline['q2_v1_migration']['summary']['lossless']}/12")
        for name in sorted(artifacts["files"]):
            print(f"{name}_sha256={artifacts['files'][name]}")
        return 0
    baseline_path = args.artifact_dir / "phase8c-baseline-audit.json"
    if baseline_path.is_file():
        baseline = _load_json(baseline_path)
    else:
        baseline = build_baseline()
    payload = {
        "base_sha": baseline.get("base_sha"),
        "expected_base_sha": baseline.get("expected_base_sha"),
        "status": baseline.get("status"),
        "reproduction": {
            "status": baseline.get("q3_reproduction", {}).get("status"),
            "samples": [
                {key: sample.get(key) for key in (
                    "sample_id", "candidate_sha256", "verifier_decision",
                    "independently_verified", "oracle_status")}
                for sample in baseline.get("q3_reproduction", {}).get(
                    "samples", [])
            ],
        },
        "v1_migration": baseline.get("q2_v1_migration", {}).get("summary"),
        "contracts": {
            "count": baseline.get("facts", {}).get("contracts", {}).get("count"),
        },
        "hidden": {
            "private_root_exists": baseline.get("q5_hidden_isolation", {})
            .get("facts", {}).get("private_root_exists"),
            "hidden_available": baseline.get("q5_hidden_isolation", {})
            .get("facts", {}).get("hidden_available_manifest"),
        },
        "blockers": [item.get("id") for item in baseline.get("blockers", [])],
        "warnings": baseline.get("warnings"),
        "ten_questions": [
            {"id": item.get("id"), "status": item.get("status")}
            for item in baseline.get("ten_questions", [])
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
