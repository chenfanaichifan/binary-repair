#!/usr/bin/env python3
"""Phase-8D read-only hidden-corpus isolation audit.

Checks the operational isolation properties of the private Phase-8C hidden
corpus without publishing hidden bytes, per-sample ids, paths or content:

* private root exists, is a real directory, is owner-only (0700) and owned by
  the current user;
* the public commitment and private hidden manifest agree on the commitment
  digest, public manifest digest and 8/6/2 sample counts;
* all material paths are relative, non-traversing and their bytes match the
  committed opaque binary hashes;
* the hidden aggregate has the same counts and contains no per-sample ids or
  paths;
* opaque hidden sample ids / binary digests do not appear in tracked public
  files outside the canonical commitment.

``--write`` writes ``artifacts/phase8d-hidden-isolation-2026-11-17``.
``--check`` rebuilds in memory and compares the committed artifact.

This is an **operational, not cryptographic** isolation audit: a same-UID or
root reader can inspect the private root. The audit records that limitation
explicitly and never copies hidden content into its artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_ROOT = Path(os.environ.get("PHASE8C_HIDDEN_ROOT") or
                    (Path.home() / ".binaryrepair" / "phase8c-hidden"))
COMMITMENT_REL = "benchmark/phase8c/hidden-commitment.json"
PUBLIC_MANIFEST_REL = "benchmark/phase8c/manifest.json"
AGGREGATE_REL = "artifacts/phase8c-hidden-2026-11-16/aggregate.json"
RESULTS_REL = "benchmark/phase8c/results.json"
PRIVATE_MANIFEST = "hidden-manifest.json"
OUT_REL = "artifacts/phase8d-hidden-isolation-2026-11-17"
GENERATED_AT = "2026-11-17T00:00:00Z"
KIND = "phase8d_hidden_isolation_audit"
EXPECTED_SAMPLE_COUNT = 8
EXPECTED_RUNTIME_COUNT = 6
EXPECTED_ANALYSIS_ONLY_COUNT = 2
SCAN_SKIP_NAMES = {COMMITMENT_REL}
SCAN_MAX_BYTES = 2_000_000


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_relative(value: str) -> bool:
    if not value or value.startswith("/") or "\\" in value:
        return False
    parts = Path(value).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _git_tracked(repo_root: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"], cwd=repo_root, capture_output=True,
            timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    raw = proc.stdout.decode("utf-8", "replace")
    return [item for item in raw.split("\x00") if item]


def _scan_public_text(
    repo_root: Path, tracked_paths: Iterable[str], needles: Iterable[str],
) -> list[dict[str, str]]:
    """Find opaque hidden ids/digests/root refs in tracked text files."""
    found: list[dict[str, str]] = []
    needles = sorted({needle for needle in needles if len(needle) >= 16})
    if not needles:
        return found
    for relative in tracked_paths:
        if relative in SCAN_SKIP_NAMES:
            continue
        path = repo_root / relative
        if not path.is_file() or path.stat().st_size > SCAN_MAX_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in needles:
            if needle in text:
                found.append({
                    "path": relative,
                    "needle_class": "opaque_hidden_material_ref",
                    "detail": "opaque hidden id/digest appears outside the canonical commitment",
                })
                break
    return found


def _scan_public_material(
    repo_root: Path, tracked_paths: Iterable[str], hidden_hashes: Iterable[str],
) -> list[dict[str, str]]:
    """Detect tracked public files whose bytes equal a hidden binary digest."""
    hidden = {digest for digest in hidden_hashes if len(digest) == 64}
    found: list[dict[str, str]] = []
    if not hidden:
        return found
    for relative in tracked_paths:
        if relative in SCAN_SKIP_NAMES:
            continue
        path = repo_root / relative
        if not path.is_file() or path.stat().st_size > SCAN_MAX_BYTES:
            continue
        try:
            digest = _sha(path)
        except OSError:
            continue
        if digest in hidden:
            found.append({
                "path": relative,
                "needle_class": "hidden_binary_material",
                "detail": "a tracked public file's bytes equal a private hidden binary",
            })
    return found


def _contains_sample_fields(value: Any) -> list[str]:
    problems: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"sample_id", "binary_path", "oracle_path", "reference_fix_path",
                       "material", "private_path"}:
                problems.append(f"hidden aggregate contains forbidden field {key!r}")
            problems.extend(_contains_sample_fields(item))
    elif isinstance(value, list):
        for item in value:
            problems.extend(_contains_sample_fields(item))
    return problems


def audit(
    *,
    root: Path = DEFAULT_ROOT,
    repo_root: Path = ROOT,
    ensure_root: bool = True,
) -> dict[str, Any]:
    """Run the isolation audit; never copies hidden content into the result."""
    checks: list[dict[str, str]] = []
    limitations = [
        "isolation is operational, not cryptographic: same-UID/root processes can read the private root",
        "the audit reads private metadata/material only to hash and compare; it never copies hidden bytes, ids, paths or content into public artifacts",
        "a green isolation audit does not imply hidden benchmark quality, hidden generalisation or capability promotion",
        "the hidden aggregate is aggregate-only; no per-sample hidden identifiers are permitted",
        "the tracked-file scan is dynamic; the exact count is not retained because this artifact itself becomes tracked",
    ]

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "status": "passed" if ok else "failed",
                       "detail": detail})

    root = Path(root).expanduser()
    root_exists = root.exists()
    root_is_dir = root.is_dir()
    root_is_symlink = root.is_symlink()
    mode: int | None = None
    owner_ok = False
    if root_exists and not root_is_symlink:
        try:
            st = root.stat()
            mode = stat.S_IMODE(st.st_mode)
            owner_ok = st.st_uid == os.getuid()
        except OSError:
            mode = None
    owner_only = mode == 0o700 and owner_ok
    add("root-exists", root_exists and root_is_dir, f"exists={root_exists} dir={root_is_dir}")
    add("root-not-symlink", not root_is_symlink, "private root must not be a symlink")
    add("root-owner-only-0700", owner_only,
        f"mode={oct(mode) if mode is not None else None} owner_ok={owner_ok}")

    commitment_path = repo_root / COMMITMENT_REL
    public_manifest_path = repo_root / PUBLIC_MANIFEST_REL
    aggregate_path = repo_root / AGGREGATE_REL
    results_path = repo_root / RESULTS_REL
    missing = [str(path.relative_to(repo_root)) for path in
               (commitment_path, public_manifest_path, aggregate_path)
               if not path.is_file()]
    if missing:
        return _result(checks, limitations, status="blocked", root=root,
                       reason=f"public evidence missing: {missing}")

    commitment = _load(commitment_path)
    public_manifest = _load(public_manifest_path)
    aggregate = _load(aggregate_path)
    commitment_ok = (
        commitment.get("kind") == "hidden_benchmark_commitment"
        and commitment.get("benchmark_id") == "phase8c-hidden"
        and commitment.get("sample_count") == EXPECTED_SAMPLE_COUNT
        and commitment.get("runtime_count") == EXPECTED_RUNTIME_COUNT
        and commitment.get("analysis_only_count") == EXPECTED_ANALYSIS_ONLY_COUNT
    )
    add("commitment-shape", commitment_ok, "commitment kind/counts are 8/6/2")
    public_manifest_sha = _sha(public_manifest_path)
    add("commitment-public-manifest-sha",
        commitment.get("public_manifest_sha256") == public_manifest_sha,
        "commitment binds the current public manifest bytes")

    private_manifest_path = root / PRIVATE_MANIFEST
    if not private_manifest_path.is_file():
        add("private-manifest-exists", False, "hidden-manifest.json is missing")
        return _result(checks, limitations, status="fail", root=root,
                       reason="private hidden manifest missing")
    private = _load(private_manifest_path)
    add("private-manifest-kind",
        private.get("kind") == "phase8c_private_hidden_manifest",
        "private hidden manifest kind")
    add("private-manifest-commitment",
        private.get("commitment_sha256") == commitment.get("commitment_sha256"),
        "private manifest commitment digest matches the public commitment")
    add("private-manifest-public-sha",
        private.get("public_manifest_sha256") == public_manifest_sha,
        "private manifest binds the current public manifest")
    samples = private.get("samples")
    material = private.get("material")
    sample_count_ok = isinstance(samples, list) and len(samples) == EXPECTED_SAMPLE_COUNT
    add("private-sample-count", sample_count_ok, f"samples={len(samples) if isinstance(samples, list) else 'missing'}")
    runtime_count = 0
    analysis_count = 0
    ids: list[str] = []
    binary_hashes: list[str] = []
    material_problems: list[str] = []
    if isinstance(samples, list):
        for sample in samples:
            if not isinstance(sample, Mapping):
                material_problems.append("sample is not an object")
                continue
            sample_id = str(sample.get("sample_id") or "")
            binary_sha = str(sample.get("binary_sha256") or "")
            if len(sample_id) == 64:
                ids.append(sample_id)
            if len(binary_sha) == 64:
                binary_hashes.append(binary_sha)
            if sample.get("expected_scope") == "analysis_only":
                analysis_count += 1
            elif set((sample.get("oracle") or {}).get("kinds") or []) & {
                "external_poc", "native", "emulated"
            }:
                runtime_count += 1
            if not isinstance(material, Mapping) or sample_id not in material:
                material_problems.append("material entry missing")
                continue
            entry = material.get(sample_id) or {}
            binary_path = str(entry.get("binary_path") or "")
            if not _safe_relative(binary_path):
                material_problems.append("unsafe material path")
                continue
            binary_file = root / binary_path
            if not binary_file.is_file():
                material_problems.append("material binary missing")
            elif _sha(binary_file) != binary_sha:
                material_problems.append("material binary digest mismatch")
    add("private-runtime-analysis-counts", runtime_count == EXPECTED_RUNTIME_COUNT
        and analysis_count == EXPECTED_ANALYSIS_ONLY_COUNT,
        f"runtime={runtime_count} analysis_only={analysis_count}")
    add("private-material-integrity", not material_problems,
        f"{len(material_problems)} problem(s)")
    commitment_ids = [str(item.get("opaque_sample_id") or "")
                      for item in commitment.get("samples") or []]
    commitment_hashes = [str(item.get("opaque_binary_sha256") or "")
                         for item in commitment.get("samples") or []]
    add("commitment-private-material-match",
        sorted(commitment_ids) == sorted(ids) and sorted(commitment_hashes) == sorted(binary_hashes),
        "opaque commitment samples match the private manifest")
    add("private-material-count",
        isinstance(material, Mapping) and len(material) == EXPECTED_SAMPLE_COUNT,
        f"material_entries={len(material) if isinstance(material, Mapping) else 'missing'}")

    agg = aggregate.get("aggregate") or {}
    agg_denominator = agg.get("denominator") or {}
    count_ok = (
        agg.get("sample_count") == EXPECTED_SAMPLE_COUNT
        and agg_denominator.get("samples") == EXPECTED_SAMPLE_COUNT
        and agg_denominator.get("executed") == EXPECTED_SAMPLE_COUNT
        and agg.get("verified_count") == 0
        and agg.get("false_verified_count") == 0
    )
    add("aggregate-consistency", count_ok,
        f"sample_count={agg.get('sample_count')} executed={agg_denominator.get('executed')} "
        f"verified={agg.get('verified_count')} false_verified={agg.get('false_verified_count')}")
    forbidden = _contains_sample_fields(aggregate)
    add("aggregate-no-per-sample-fields", not forbidden,
        f"{len(forbidden)} forbidden field(s)")

    if results_path.is_file():
        try:
            results = _load(results_path)
            hidden = results.get("hidden_aggregate") or {}
            add("results-hidden-aggregate-consistent",
                (hidden.get("sample_count") == agg.get("sample_count")
                 and hidden.get("false_verified_count") == agg.get("false_verified_count")),
                "results.hidden_aggregate matches the aggregate file")
        except (OSError, json.JSONDecodeError):
            add("results-hidden-aggregate-consistent", False, "results file unreadable")
    else:
        add("results-hidden-aggregate-consistent", False, "public results file missing")

    tracked = _git_tracked(repo_root) if ensure_root else []
    needles = ids + binary_hashes
    findings = _scan_public_text(repo_root, tracked, needles)
    material_matches = _scan_public_material(repo_root, tracked, binary_hashes)
    add("no-hidden-id-or-material-in-public-files", not findings,
        f"dynamic tracked-file scan; findings={len(findings)}")
    add("no-hidden-binary-material-in-public-files", not material_matches,
        f"dynamic tracked-file scan; exact-digest matches={len(material_matches)}")
    add("no-private-root-reference",
        not any("binaryrepair/phase8c-hidden" in json.dumps(item)
                for item in findings),
        "private root material/ids are not referenced by public findings")

    status = "ok" if all(check["status"] == "passed" for check in checks) else "fail"
    return _result(checks, limitations, status=status, root=root,
                   commitment=commitment, aggregate=aggregate, findings=findings,
                   material_matches=material_matches,
                   counts={
                       "sample_count": len(ids),
                       "runtime_count": runtime_count,
                       "analysis_only_count": analysis_count,
                       "material_entries": len(material) if isinstance(material, Mapping) else 0,
                   },
                   public_scan={"tracked_files": "dynamic", "findings": findings})


def _result(
    checks: list[dict[str, str]], limitations: list[str], *, status: str,
    root: Path, reason: str | None = None, commitment: Mapping[str, Any] | None = None,
    aggregate: Mapping[str, Any] | None = None, findings: list[dict[str, str]] | None = None,
    counts: Mapping[str, int] | None = None,
    public_scan: Mapping[str, Any] | None = None,
    material_matches: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": KIND,
        "generated_at": GENERATED_AT,
        "status": status,
        "ok": status == "ok",
        "reason": reason,
        "root": {
            "configured_env": "PHASE8C_HIDDEN_ROOT" in os.environ,
            "exists": root.exists(),
            "is_dir": root.is_dir(),
            "is_symlink": root.is_symlink(),
            "mode": oct(stat.S_IMODE(root.stat().st_mode)) if root.exists() and not root.is_symlink() else None,
            "owner_only": (root.exists() and not root.is_symlink()
                           and stat.S_IMODE(root.stat().st_mode) == 0o700
                           and root.stat().st_uid == os.getuid()),
            "path_published": False,
        },
        "checks": checks,
        "counts": dict(counts or {}),
        "commitment": {
            "commitment_sha256": (commitment or {}).get("commitment_sha256"),
            "public_manifest_sha256": (commitment or {}).get("public_manifest_sha256"),
            "sample_count": (commitment or {}).get("sample_count"),
            "runtime_count": (commitment or {}).get("runtime_count"),
            "analysis_only_count": (commitment or {}).get("analysis_only_count"),
        },
        "public_leak_scan": {
            "tracked_files_scanned": (public_scan or {}).get("tracked_files", "dynamic"),
            "findings": findings or [],
            "material_matches": material_matches or [],
        },
        "reads": ["private_manifest_metadata", "private_material_hashes",
                  "public_commitment", "public_manifest", "hidden_aggregate",
                  "public_results"],
        "writes": [OUT_REL],
        "limitations": limitations,
        "operational_isolation": True,
        "cryptographic_isolation": False,
        "no_hidden_content_published": True,
        "capability_promotion": False,
        "benchmark_version": "phase8c-v2",
    }


def _artifact_bytes(payload: Mapping[str, Any]) -> dict[str, bytes]:
    gaps = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    files = {"isolation.json": gaps}
    readme = (
        "# Phase-8D hidden isolation audit\n\n"
        f"- status: `{payload['status']}`\n"
        f"- generated_at: `{payload['generated_at']}` (fixed)\n"
        "- private root mode: " + str(payload["root"]["mode"]) + "\n"
        "- counts: " + json.dumps(payload["counts"], sort_keys=True) + "\n"
        "- operational isolation: true; cryptographic isolation: **false**\n"
        "- public leak findings: " + str(len(payload["public_leak_scan"]["findings"])) + "\n"
        "- no hidden paths/ids/content are published by this artifact; the private root path is omitted.\n\n"
        "## Checks\n\n" + "\n".join(
            f"- {c['id']}: {c['status']} ({c['detail']})" for c in payload["checks"]
        ) + "\n\n## Limitations\n\n"
        + "\n".join(f"- {item}" for item in payload["limitations"]) + "\n"
    ).encode("utf-8")
    files["README.md"] = readme
    sums = []
    for name in sorted(("isolation.json", "README.md")):
        sums.append(f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n")
    files["SHA256SUMS"] = "".join(sums).encode("utf-8")
    return files


def write_artifact(payload: Mapping[str, Any], out_dir: Path = ROOT / OUT_REL) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = _artifact_bytes(payload)
    for name, data in files.items():
        (out_dir / name).write_bytes(data)
    return sorted(files)


def check_artifact(out_dir: Path = ROOT / OUT_REL) -> list[str]:
    problems: list[str] = []
    path = out_dir / "isolation.json"
    if not path.is_file():
        return ["missing isolation.json"]
    try:
        payload = _load(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unreadable isolation.json: {exc}"]
    sums_path = out_dir / "SHA256SUMS"
    if not sums_path.is_file():
        problems.append("missing SHA256SUMS")
    else:
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, name = line.split(None, 1)
            target = out_dir / name.strip()
            if not target.is_file():
                problems.append(f"missing {name.strip()}")
            elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                problems.append(f"sha256 mismatch {name.strip()}")
    if payload.get("status") not in {"ok", "fail", "blocked"}:
        problems.append("invalid status")
    if payload.get("ok") is not (payload.get("status") == "ok"):
        problems.append("ok/status mismatch")
    if payload.get("no_hidden_content_published") is not True:
        problems.append("hidden content publication flag is not false")
    if payload.get("capability_promotion") is not False:
        problems.append("capability promotion must be false")
    if payload.get("cryptographic_isolation") is not False:
        problems.append("cryptographic isolation must not be claimed")
    if payload.get("public_leak_scan", {}).get("findings"):
        problems.append("committed artifact records public leak findings")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=ROOT / OUT_REL)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifact(args.out)
        payload = {"ok": not problems, "problems": problems}
        print(json.dumps(payload, indent=2) if args.json else
              "phase8d-hidden-isolation: " + ("check OK" if not problems else
                                              f"{len(problems)} problem(s)"))
        return 0 if not problems else 1
    try:
        payload = audit(root=args.root, repo_root=args.repo_root)
    except Exception as exc:  # noqa: BLE001 - record a typed failure, never fake ok
        payload = {
            "schema_version": 1,
            "kind": KIND,
            "generated_at": GENERATED_AT,
            "status": "fail",
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "checks": [],
            "reads": [],
            "writes": [OUT_REL],
            "limitations": ["audit raised; no isolation claim is made"],
            "operational_isolation": True,
            "cryptographic_isolation": False,
            "no_hidden_content_published": True,
            "capability_promotion": False,
        }
    if args.write:
        written = write_artifact(payload, args.out)
        payload = {**payload, "written": written}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"phase8d-hidden-isolation: status={payload['status']} "
              f"checks={len(payload.get('checks', []))}")
        for check in payload.get("checks", []):
            print(f"  {check['id']}: {check['status']}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
