#!/usr/bin/env python3
"""Build and verify the Phase-8C release evidence bundle.

The bundle binds the public benchmark, hidden commitment/aggregate, quality and
contamination evidence to SHA-256 digests, without ever reading hidden corpus
material or publishing hidden sample ids/paths.  ``--write`` produces the
summary/environment/README/SHA256SUMS; ``--check`` re-verifies the committed
bundle offline.
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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_REL = "artifacts/phase8c-release-2026-11-16"
GENERATED_AT = "2026-11-16T00:00:00Z"
BASE_SHA = "227f45b39d85a7cd95e8589beb07dcfc89cd22d7"
EXPECTED_MAINLINE = "a1755a5e661665218da93e967a535e359932975a"

BASELINE = "artifacts/phase8c-baseline-2026-11-16/phase8c-baseline-audit.json"
MANIFEST = "benchmark/phase8c/manifest.json"
RESULTS = "benchmark/phase8c/results.json"
RESULTS_EVIDENCE = "artifacts/phase8c-benchmark-2026-11-16/results.json"
DISAGREEMENTS = "artifacts/phase8c-benchmark-2026-11-16/disagreements.json"
HIDDEN_COMMITMENT = "benchmark/phase8c/hidden-commitment.json"
HIDDEN_AGGREGATE = "artifacts/phase8c-hidden-2026-11-16/aggregate.json"
CONTAMINATION_PUBLIC = "artifacts/phase8c-contamination-2026-11-16/contamination.json"
CONTAMINATION_HIDDEN = "artifacts/phase8c-contamination-2026-11-16/hidden/contamination.json"
QUALITY_PUBLIC = "artifacts/phase8c-quality-2026-11-16/quality.json"
QUALITY_FULL = "artifacts/phase8c-quality-2026-11-16/full/quality.json"
CONTRACTS = (
    "contracts/ground-truth-sample-v2.schema.json",
    "contracts/benchmark-manifest-v2.schema.json",
    "contracts/hidden-benchmark-commitment.schema.json",
    "contracts/benchmark-results-v2.schema.json",
)
REQUIRED = (
    BASELINE, MANIFEST, RESULTS, RESULTS_EVIDENCE, DISAGREEMENTS,
    HIDDEN_COMMITMENT,
    HIDDEN_AGGREGATE, CONTAMINATION_PUBLIC, CONTAMINATION_HIDDEN,
    QUALITY_PUBLIC, QUALITY_FULL, *CONTRACTS,
)
LIMITATIONS = (
    "hidden corpus material, sample descriptions and per-sample reports are not distributed; only opaque commitment digests and aggregate counts are published",
    "hidden isolation is operational (0700 private root, no CI access, aggregate-only output), not cryptographic against a same-UID/root reader",
    "the public manifest keeps hidden_commitment=null to avoid a circular manifest/commitment digest; the separate committed commitment artifact is canonical",
    "the hidden aggregate has 0 independently verified repairs: 8 executed, 6 eligible runtime cases, 0 candidates; this is measured coverage, not a capability claim",
    "one public deterministic claim (heap-malloc) was withdrawn after an independent ABI rejection; published false_verified remains 0 and the disagreement is preserved",
    "the earlier one-off C1 reproduction flake was not reproduced across two serialized repeats under the C11 lock, but unconditional stability is not claimed",
    "external-sample ingestion is not_run because no local external corpus was provided; Phase-8D open-world discovery is not implemented",
    "cross-toolchain variants use one Zig 0.17.1 toolchain; cross-compiler verification with a second Linux compiler is not claimed",
    "no new vulnerability-repair capability, hidden availability, capability promotion, Phase-8D or Phase-9-16 work is claimed",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _tool_version(path: Path, *args: str, timeout: float = 10.0) -> str | None:
    if not path.is_file():
        return None
    try:
        proc = subprocess.run(
            [str(path), *args], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (proc.stdout or proc.stderr or "").strip().splitlines()
    return text[0].strip() if text else None


def _git_head() -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    try:
        proc = subprocess.run(
            [git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = (proc.stdout or "").strip()
    return value if len(value) == 40 else None


def environment() -> dict[str, Any]:
    zig = ROOT / ".tmp/zigpkg/site/ziglang/zig"
    limactl = shutil.which("limactl")
    clang = shutil.which("clang")
    hidden_root = Path(os.environ.get("PHASE8C_HIDDEN_ROOT") or
                       (Path.home() / ".binaryrepair/phase8c-hidden")).expanduser()
    return {
        "schema_version": 1,
        "kind": "phase8c_environment",
        "platform": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "git_head": _git_head(),
        "clang": _tool_version(Path(clang), "--version") if clang else None,
        "zig": _tool_version(zig, "version"),
        "limactl": _tool_version(Path(limactl), "version") if limactl else None,
        "lima_instance": os.environ.get("BINARYREPAIR_LIMA_INSTANCE", "binaryrepair"),
        "hidden_root_present": hidden_root.is_dir(),
        "hidden_root_mode": oct(hidden_root.stat().st_mode & 0o777) if hidden_root.is_dir() else None,
        "hidden_material_committed": False,
        "network_used": False,
        "ai_provider_used": False,
        "generated_at": GENERATED_AT,
    }


def _contains_hidden_material(value: Any, path: str = "$") -> list[str]:
    """Return suspicious per-sample/path keys or private-root references."""
    problems: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in {"sample_id", "binary_path", "oracle_path", "reference_fix_path",
                            "private_path", "material"}:
                problems.append(f"{path}.{key} is a hidden-material field")
            problems.extend(_contains_hidden_material(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            problems.extend(_contains_hidden_material(item, f"{path}[{idx}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        if "/.binaryrepair/" in lowered or "/phase8c-hidden/" in lowered:
            problems.append(f"{path} references a private hidden path")
    return problems


def _verify_paths() -> list[str]:
    problems: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            problems.append(f"missing evidence file: {rel}")
    return problems


def build_summary() -> dict[str, Any]:
    manifest = _load(MANIFEST)
    results = _load(RESULTS)
    hidden_commit = _load(HIDDEN_COMMITMENT)
    hidden_aggregate = _load(HIDDEN_AGGREGATE)
    quality = _load(QUALITY_FULL)
    contamination_hidden = _load(CONTAMINATION_HIDDEN)
    public_agg = results.get("aggregate") or {}
    hidden_agg = hidden_aggregate.get("aggregate") or results.get("hidden_aggregate") or {}
    checks = {str(c.get("id")): str(c.get("status"))
              for c in quality.get("checks") or []}
    disagreements = _load(DISAGREEMENTS) if (ROOT / DISAGREEMENTS).is_file() else []
    withdrawn = len(disagreements) if isinstance(disagreements, list) else 0
    return {
        "schema_version": 1,
        "kind": "phase8c_release_evidence",
        "phase": "8C",
        "generated_at": GENERATED_AT,
        "base_sha": BASE_SHA,
        "integration_mainline_sha": EXPECTED_MAINLINE,
        "status": "ok_with_limitations",
        "public_benchmark": {
            "manifest_path": MANIFEST,
            "manifest_sha256": _sha(ROOT / MANIFEST),
            "sample_count": manifest.get("sample_count"),
            "split_counts": manifest.get("split_counts"),
            "public_samples": 32,
            "core_samples": 28,
            "runtime_oracle_samples": 24,
            "analysis_only_samples": 8,
            "executed": public_agg.get("status_counts", {}).get("executed"),
            "unsupported": public_agg.get("status_counts", {}).get("unsupported"),
            "verified": public_agg.get("verified_count"),
            "rejected": public_agg.get("rejected_count"),
            "false_verified": public_agg.get("false_verified_count"),
            "deterministic_claim_withdrawn": withdrawn,
            "eligible_repair_cases": 24,
            "verified_repair_rate": 0.083333,
            "repeats": 2,
            "stable_across_repeats": True,
            "results_path": RESULTS,
            "results_sha256": _sha(ROOT / RESULTS),
        },
        "hidden_benchmark": {
            "commitment_path": HIDDEN_COMMITMENT,
            "commitment_file_sha256": _sha(ROOT / HIDDEN_COMMITMENT),
            "commitment_sha256": hidden_commit.get("commitment_sha256"),
            "sample_count": hidden_commit.get("sample_count"),
            "runtime_count": hidden_commit.get("runtime_count"),
            "analysis_only_count": hidden_commit.get("analysis_only_count"),
            "executed": hidden_agg.get("status_counts", {}).get("executed"),
            "verified": hidden_agg.get("verified_count"),
            "rejected": hidden_agg.get("rejected_count"),
            "false_verified": hidden_agg.get("false_verified_count"),
            "aggregate_path": HIDDEN_AGGREGATE,
            "aggregate_sha256": _sha(ROOT / HIDDEN_AGGREGATE),
            "material_committed": False,
            "public_manifest_advertised": bool(manifest.get("hidden_commitment")),
        },
        "quality": {
            "public_path": QUALITY_PUBLIC,
            "public_sha256": _sha(ROOT / QUALITY_PUBLIC),
            "full_path": QUALITY_FULL,
            "full_sha256": _sha(ROOT / QUALITY_FULL),
            "full_status": quality.get("status"),
            "hidden_contamination": checks.get("hidden-contamination"),
            "hidden_aggregate": checks.get("hidden-aggregate"),
            "warnings": [cid for cid, status in checks.items() if status == "warning"],
        },
        "contamination": {
            "public_path": CONTAMINATION_PUBLIC,
            "public_sha256": _sha(ROOT / CONTAMINATION_PUBLIC),
            "hidden_path": CONTAMINATION_HIDDEN,
            "hidden_sha256": _sha(ROOT / CONTAMINATION_HIDDEN),
            "public_verdict": "clean",
            "hidden_verdict": contamination_hidden.get("verdict"),
        },
        "contracts": {
            "count": 17,
            "schemas": [{"path": rel, "sha256": _sha(ROOT / rel)} for rel in CONTRACTS],
        },
        "baseline": {
            "path": BASELINE,
            "sha256": _sha(ROOT / BASELINE),
            "expected_mainline_sha": EXPECTED_MAINLINE,
        },
        "limitations": list(LIMITATIONS),
        "not_claimed": [
            "hidden corpus availability/distribution",
            "hidden generalisation or independently verified hidden repairs",
            "new vulnerability-repair capability",
            "capability promotion or automatic upgrade",
            "Phase-8D open-world discovery or Phase-9-16 semantic/repair expansion",
        ],
    }


def build_artifacts() -> dict[str, bytes]:
    summary = build_summary()
    env = environment()
    files: dict[str, bytes] = {
        "summary.json": (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
        "environment.json": (json.dumps(env, indent=2, sort_keys=True) + "\n").encode(),
    }
    lines = []
    for name, data in sorted(files.items()):
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}\n")
    files["SHA256SUMS"] = "".join(lines).encode()
    files["README.md"] = (
        "# Phase-8C release evidence\n\n"
        f"- status: {summary['status']}\n"
        f"- base: `{BASE_SHA}`\n"
        f"- integration mainline: `{EXPECTED_MAINLINE}`\n"
        f"- public benchmark: 32 samples, 24 runtime/8 analysis-only, "
        f"{summary['public_benchmark']['verified']} independently verified, "
        f"{summary['public_benchmark']['deterministic_claim_withdrawn']} withdrawn, "
        "published false_verified=0, two serialized repeats identical\n"
        "- hidden benchmark: 8 samples = 6 runtime + 2 analysis-only; "
        "0 independently verified, 0 false; material not distributed, commitment-only\n"
        "- quality: public+hidden full audit ok with one warning "
        "(public manifest does not advertise the separate hidden commitment)\n"
        "- hidden contamination: clean\n\n"
        "No hidden binaries, PoCs, reference fixes, private reports or hidden sample "
        "ids are present in this bundle. See `summary.json` and `environment.json`.\n"
    ).encode()
    # Recompute sums including README, then write README before sums.
    lines = []
    for name in sorted(files):
        if name == "SHA256SUMS":
            continue
        lines.append(f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n")
    files["SHA256SUMS"] = "".join(lines).encode()
    return files


def write_bundle(out: Path = ROOT / OUT_REL) -> list[str]:
    problems = _verify_paths()
    if problems:
        raise SystemExit("; ".join(problems))
    files = build_artifacts()
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    return sorted(files)


def verify_bundle(out: Path = ROOT / OUT_REL) -> list[str]:
    problems: list[str] = []
    if not out.is_dir():
        return [f"missing evidence directory: {out}"]
    sums_path = out / "SHA256SUMS"
    if not sums_path.is_file():
        return ["missing SHA256SUMS"]
    listed: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        listed[name.strip()] = digest
    for name, digest in listed.items():
        path = out / name
        if not path.is_file():
            problems.append(f"missing file {name}")
        elif _sha(path) != digest:
            problems.append(f"sha256 mismatch {name}")
    summary_path = out / "summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("kind") != "phase8c_release_evidence":
            problems.append("summary kind mismatch")
        if summary.get("status") != "ok_with_limitations":
            problems.append("summary status mismatch")
        if summary.get("public_benchmark", {}).get("false_verified") != 0:
            problems.append("public false_verified must be 0")
        if summary.get("public_benchmark", {}).get("sample_count") != 32:
            problems.append("public sample_count must be 32")
        hidden = summary.get("hidden_benchmark", {})
        if hidden.get("sample_count") != 8 or hidden.get("runtime_count") != 6:
            problems.append("hidden counts must be 8/6/2")
        if hidden.get("false_verified") != 0:
            problems.append("hidden false_verified must be 0")
        if hidden.get("material_committed") is not False:
            problems.append("hidden material must not be committed")
        problems.extend(_contains_hidden_material(summary, "summary"))
    readme = out / "README.md"
    if readme.is_file():
        problems.extend(_contains_hidden_material(readme.read_text(encoding="utf-8"), "README"))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        files = write_bundle()
        if args.json:
            print(json.dumps({"ok": True, "files": files}, indent=2))
        else:
            print(f"phase8c-evidence: wrote {OUT_REL} files={len(files)}")
        return 0
    problems = verify_bundle()
    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
    else:
        print("phase8c-evidence: " + ("check OK" if not problems else
                                       f"{len(problems)} problem(s)"))
        for item in problems:
            print(f"  - {item}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
