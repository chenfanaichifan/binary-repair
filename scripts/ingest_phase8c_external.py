#!/usr/bin/env python3
"""Phase-8C C7: local-only external corpus ingestion/quarantine.

Reads an explicitly supplied local ``--external-root`` only. Never touches the
network or AI providers, never merges candidates into the public or hidden
corpora, and records ``not_run`` when the root/manifest is absent. Every
candidate requires license, provenance and hash validation; rejected candidates
stay quarantined with explicit reasons.

Artifacts: artifacts/phase8c-external-2026-11-16/
    external-ingestion.json / README.md / SHA256SUMS
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
KIND = "phase8c_external_ingestion"
ARTIFACT_DIR = ROOT / "artifacts" / "phase8c-external-2026-11-16"
PUBLIC_MANIFEST = ROOT / "benchmark" / "phase8c" / "manifest.json"
ALLOWED_SPLITS = ("dev", "validation")
SAMPLE_ID_RE = None  # validated with a small deterministic character check


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_sample_id(value: str) -> bool:
    if not value or len(value) > 128:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyz"
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return all(character in allowed for character in value)


def _resolve(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _license_valid(value: Any) -> tuple[bool, str]:
    if isinstance(value, str):
        if value.strip():
            return True, value.strip()
        return False, "license string is empty"
    if isinstance(value, dict):
        name = str(value.get("name") or value.get("id") or "").strip()
        if name:
            return True, name
        return False, "license object needs name/id"
    return False, "license is required (string or object)"


def _provenance_valid(value: Any) -> tuple[bool, str]:
    if not isinstance(value, dict) or not value:
        return False, "provenance object is required"
    origin = str(value.get("origin") or value.get("source")
                 or value.get("source_url") or "").strip()
    if not origin:
        return False, "provenance needs origin/source"
    if not str(value.get("acquired_at") or value.get("collected_at")
               or "").strip():
        return False, "provenance needs acquired_at/collected_at"
    recorded = str(value.get("sha256") or "").strip()
    if recorded:
        normalized = _canonical({key: item for key, item in value.items()
                                 if key != "sha256"})
        actual = _sha256_bytes(normalized.encode("utf-8"))
        if recorded != actual:
            return False, "provenance sha256 does not match its content"
    return True, origin


def _validate_candidate(root: Path, raw: Any,
                        known_ids: set[str],
                        known_hashes: set[str]) -> dict[str, Any]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return {"sample_id": None, "verdict": "rejected",
                "reasons": ["candidate is not an object"]}
    sample_id = str(raw.get("sample_id") or "")
    if not _valid_sample_id(sample_id):
        reasons.append("invalid/missing sample_id")
    if sample_id in known_ids:
        reasons.append("sample_id collides with the public corpus")
    binary_path = _resolve(root, raw.get("binary_path") or raw.get("binary"))
    binary_sha = str(raw.get("binary_sha256") or "")
    if binary_path is None or not binary_path.is_file():
        reasons.append("binary_path is missing")
    elif not binary_sha:
        reasons.append("binary_sha256 is required")
    elif _sha256_file(binary_path) != binary_sha:
        reasons.append("binary sha256 mismatch")
    elif binary_sha in known_hashes:
        reasons.append("binary duplicates the public corpus")
    split = str(raw.get("split") or "")
    if split not in ALLOWED_SPLITS:
        reasons.append("split must be dev or validation")
    if not isinstance(raw.get("target"), dict) or not raw["target"]:
        reasons.append("target is required")
    oracle = raw.get("oracle")
    if not isinstance(oracle, dict) or not oracle:
        reasons.append("oracle is required")
    elif not _resolve(root, oracle.get("manifest_path")):
        reasons.append("oracle.manifest_path is required")
    else:
        oracle_path = _resolve(root, oracle.get("manifest_path"))
        if not oracle_path.is_file():
            reasons.append("oracle manifest file is missing")
        elif oracle.get("sha256") and _sha256_file(
                oracle_path) != str(oracle["sha256"]):
            reasons.append("oracle manifest sha256 mismatch")
    sources = raw.get("source_refs")
    if not isinstance(sources, list) or not sources:
        reasons.append("source_refs are required")
    else:
        for ref in sources:
            ref_path = _resolve(root, ref.split("#", 1)[0])
            if ref_path is None or not ref_path.is_file():
                reasons.append("source ref is missing")
                break
    reference = raw.get("reference_fix")
    if reference is not None:
        if not isinstance(reference, dict):
            reasons.append("reference_fix must be an object")
        else:
            ref_path = _resolve(root, reference.get("path"))
            if ref_path is None or not ref_path.is_file():
                reasons.append("reference_fix file is missing")
            elif reference.get("sha256") and _sha256_file(
                    ref_path) != str(reference["sha256"]):
                reasons.append("reference_fix sha256 mismatch")
    license_ok, license_note = _license_valid(raw.get("license"))
    if not license_ok:
        reasons.append(license_note)
    provenance_ok, provenance_note = _provenance_valid(raw.get("provenance"))
    if not provenance_ok:
        reasons.append(provenance_note)
    if not isinstance(raw.get("evidence_refs"), list) or not raw.get(
            "evidence_refs"):
        reasons.append("evidence_refs are required")
    return {
        "sample_id": sample_id,
        "split": split,
        "binary_sha256": binary_sha if len(binary_sha) == 64 else None,
        "license": license_note,
        "provenance": provenance_note,
        "verdict": "accepted_quarantined" if not reasons else "rejected",
        "merge_allowed": False,
        "reasons": reasons,
    }


def ingest(external_root: Path | None,
           manifest_override: Path | None = None) -> dict[str, Any]:
    if external_root is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": KIND,
            "status": "not_run",
            "mode": "external_local",
            "reason": "no --external-root supplied; external ingestion not run",
            "external_root": None,
            "candidates": [],
            "accepted": 0,
            "rejected": 0,
            "merge": {"public_merge_performed": False,
                      "hidden_merge_performed": False,
                      "auto_merge_allowed": False},
            "network_used": False,
            "ai_invoked": False,
            "limitations": ["local-only ingestion; no network/AI"],
        }
    if not external_root.is_dir():
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": KIND,
            "status": "not_run",
            "mode": "external_local",
            "reason": "external root is missing or not a directory",
            "external_root": str(external_root),
            "candidates": [],
            "accepted": 0,
            "rejected": 0,
            "merge": {"public_merge_performed": False,
                      "hidden_merge_performed": False,
                      "auto_merge_allowed": False},
            "network_used": False,
            "ai_invoked": False,
            "limitations": ["local-only ingestion; no network/AI"],
        }
    manifest_path = manifest_override or (external_root / "manifest.json")
    if not manifest_path.is_file():
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": KIND,
            "status": "not_run",
            "mode": "external_local",
            "reason": "external manifest is missing",
            "external_root": str(external_root),
            "candidates": [],
            "accepted": 0,
            "rejected": 0,
            "merge": {"public_merge_performed": False,
                      "hidden_merge_performed": False,
                      "auto_merge_allowed": False},
            "network_used": False,
            "ai_invoked": False,
            "limitations": ["local-only ingestion; no network/AI"],
        }
    try:
        payload = _load_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"schema_version": SCHEMA_VERSION, "kind": KIND,
                "status": "error",
                "reason": f"external manifest unreadable: "
                          f"{type(exc).__name__}: {exc}"}
    raw_samples = payload if isinstance(payload, list) else (
        payload.get("samples") if isinstance(payload, dict) else None)
    if not isinstance(raw_samples, list):
        return {"schema_version": SCHEMA_VERSION, "kind": KIND,
                "status": "error", "reason": "external manifest has no samples"}
    known_ids: set[str] = set()
    known_hashes: set[str] = set()
    if PUBLIC_MANIFEST.is_file():
        try:
            public = _load_json(PUBLIC_MANIFEST)
            known_ids = {str(sample.get("sample_id"))
                         for sample in public.get("samples", [])}
            known_hashes = {str(sample.get("binary_sha256"))
                            for sample in public.get("samples", [])
                            if sample.get("binary_sha256")}
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    candidates = [_validate_candidate(external_root, sample, known_ids,
                                      known_hashes) for sample in raw_samples]
    accepted = sum(1 for item in candidates
                   if item["verdict"] == "accepted_quarantined")
    rejected = len(candidates) - accepted
    seen: set[str] = set()
    for candidate in candidates:
        sample_id = candidate.get("sample_id")
        if sample_id and sample_id in seen:
            candidate["verdict"] = "rejected"
            candidate["reasons"].append("duplicate sample_id inside external root")
        if sample_id:
            seen.add(sample_id)
    accepted = sum(1 for item in candidates
                   if item["verdict"] == "accepted_quarantined")
    rejected = len(candidates) - accepted
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "status": "ok",
        "mode": "external_local",
        "reason": None,
        "external_root": str(external_root),
        "manifest_sha256": _sha256_file(manifest_path),
        "candidate_count": len(candidates),
        "accepted": accepted,
        "rejected": rejected,
        "candidates": candidates,
        "merge": {"public_merge_performed": False,
                  "hidden_merge_performed": False,
                  "auto_merge_allowed": False,
                  "quarantine_only": True},
        "network_used": False,
        "ai_invoked": False,
        "licenses_recorded": sorted({str(item.get("license"))
                                     for item in candidates
                                     if item.get("license")}),
        "limitations": [
            "local-only: the external root is caller-supplied; no network/AI",
            "accepted candidates stay quarantined; nothing is merged into the "
            "public or hidden corpus automatically",
            "license/provenance/hash validation is necessary but not a legal "
            "review",
        ],
    }


def _readme(report: dict[str, Any]) -> str:
    lines = [
        "# Phase-8C external ingestion/quarantine (2026-11-16)",
        "",
        f"Status: `{report['status']}`; mode: `{report.get('mode')}`",
        "",
    ]
    if report["status"] == "not_run":
        lines.append(f"Not run: {report.get('reason')}")
    else:
        lines.extend([
            f"- candidate_count: {report['candidate_count']}",
            f"- accepted_quarantined: {report['accepted']}",
            f"- rejected: {report['rejected']}",
            "- public_merge_performed: false",
            "- hidden_merge_performed: false",
            "",
            "| sample_id | verdict | reasons |",
            "|---|---|---|",
        ])
        for candidate in report["candidates"]:
            lines.append("| {} | {} | {} |".format(
                candidate.get("sample_id"), candidate.get("verdict"),
                "; ".join(candidate.get("reasons") or []) or "-"))
    lines.extend([
        "",
        "No candidate is merged automatically. Root/manifest absence is "
        "recorded as `not_run`, never faked as accepted.",
        "",
    ])
    return "\n".join(lines)


def _verify_sums(target: Path) -> list[str]:
    sums = target / "SHA256SUMS"
    if not sums.is_file():
        return [f"missing SHA256SUMS: {sums}"]
    problems: list[str] = []
    for line in sums.read_text(encoding="utf-8").splitlines():
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


def write_artifacts(report: dict[str, Any],
                    artifact_dir: Path = ARTIFACT_DIR) -> dict[str, Any]:
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "external-ingestion.json": _canonical(report),
        "README.md": _readme(report),
    }
    sums: dict[str, str] = {}
    for name, content in files.items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        sums[name] = _sha256_file(path)
    sums_path = target / "SHA256SUMS"
    sums_path.write_text("\n".join(
        f"{digest}  {name}" for name, digest in sorted(sums.items())),
        encoding="utf-8")
    return {"artifact_dir": str(target), "sha256": sums,
            "sums_sha256": _sha256_file(sums_path)}


def check_artifact(artifact_dir: Path = ARTIFACT_DIR,
                   external_root: Path | None = None,
                   manifest: Path | None = None) -> list[str]:
    target = Path(artifact_dir)
    problems = _verify_sums(target)
    try:
        committed = _load_json(target / "external-ingestion.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return problems + [f"external-ingestion.json unreadable: {exc}"]
    if committed.get("kind") != KIND:
        problems.append("wrong external ingestion artifact kind")
    if committed.get("status") not in {"not_run", "ok"}:
        problems.append("invalid external ingestion status")
    fresh = ingest(external_root, manifest)
    if committed != fresh:
        problems.append("external-ingestion.json stale/tampered vs fresh run")
    readme = target / "README.md"
    if not readme.is_file() or readme.read_text(
            encoding="utf-8") != _readme(fresh):
        problems.append("README.md stale/tampered")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-root", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifact(args.artifact_dir, args.external_root,
                                  args.manifest)
        if problems:
            for problem in problems:
                print(f"EXTERNAL-VIOLATION: {problem}")
            return 1
        print("external-ingestion: check OK (deterministic, SHA256SUMS "
              "verified)")
        return 0
    report = ingest(args.external_root, args.manifest)
    if args.write:
        artifacts = write_artifacts(report, args.artifact_dir)
        print(f"external-ingestion: wrote {artifacts['artifact_dir']}")
        print(f"status={report.get('status')} "
              f"accepted={report.get('accepted')} "
              f"rejected={report.get('rejected')}")
        for name in sorted(artifacts["sha256"]):
            print(f"{name}_sha256={artifacts['sha256'][name]}")
        return 0
    print(json.dumps({
        "status": report.get("status"),
        "mode": report.get("mode"),
        "reason": report.get("reason"),
        "candidate_count": report.get("candidate_count"),
        "accepted": report.get("accepted"),
        "rejected": report.get("rejected"),
        "merge": report.get("merge"),
    }, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
