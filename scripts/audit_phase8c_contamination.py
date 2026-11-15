#!/usr/bin/env python3
"""Phase-8C C5: contamination audit for the public v2 corpus (and hidden mode).

Public-only mode is CI-capable and never reads hidden content. Hidden mode is
enabled only with an explicit ``--hidden-root`` and records ``not_run`` when the
root/manifest is unavailable. The audit detects exact binary/PoC/reference/
source SHA duplicates across dev/validation/hidden (same binary different target
is an explicit note) and near-duplicates (executable-section digest + capstone
opcode 4-gram Jaccard >= 0.90 for binaries; token/sequence similarity >= 0.90
for source/PoC/reference text). Declared variants/families are explicit notes.

Public reports contain no hidden ids/paths/hashes. Deterministic, offline, never
executes a corpus binary.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
KIND = "phase8c_contamination_audit"
PUBLIC_MANIFEST = "benchmark/phase8c/manifest.json"
PROVENANCE = "benchmark/phase8c/PROVENANCE.json"
ARTIFACT_DIR = ROOT / "artifacts" / "phase8c-contamination-2026-11-16"
NEAR_BINARY_THRESHOLD = 0.90
NEAR_TEXT_THRESHOLD = 0.90
OPCODE_NGRAM = 4
MAX_TOKENS = 50000
TEXT_MAX_TOKENS = 6000


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_ref(ref: Any) -> str:
    return str(ref or "").split("#", 1)[0]


def _target_key(sample: dict[str, Any]) -> str:
    return json.dumps(sample.get("target") or {}, sort_keys=True)


def _variant_families(provenance: dict[str, Any]) -> dict[str, str]:
    families: dict[str, str] = {}
    for entry in provenance.get("variants") or []:
        if isinstance(entry, dict) and entry.get("sample_id"):
            families[str(entry["sample_id"])] = str(
                entry.get("source_sample") or entry["sample_id"])
    return families


def _family(sample_id: str, families: dict[str, str]) -> str:
    current = sample_id
    seen: set[str] = set()
    while current in families and current not in seen:
        seen.add(current)
        current = families[current]
    return current


def _opcode_tokens(code: bytes, arch: str) -> list[str]:
    try:
        import capstone

        if arch in {"x86_64", "x86-64"}:
            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        elif arch in {"i386", "x86"}:
            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        elif arch in {"arm64", "aarch64"}:
            md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        else:
            return []
        tokens: list[str] = []
        for insn in md.disasm(code, 0):
            tokens.append(insn.mnemonic)
            if len(tokens) >= MAX_TOKENS:
                break
        return tokens
    except Exception:  # noqa: BLE001 - disassembly unavailable
        return []


def _binary_facts(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    facts: dict[str, Any] = {
        "sha256": _sha256_bytes(data),
        "size": len(data),
        "executable_sha256": None,
        "opcode_tokens": [],
    }
    try:
        from app.services.containers import detect_container

        info = detect_container(data)
        chunks: list[bytes] = []
        for section in info.sections:
            if not getattr(section, "executable", False):
                continue
            offset = int(getattr(section, "offset", 0) or 0)
            size = int(getattr(section, "size", 0) or 0)
            if size <= 0 or offset < 0 or offset + size > len(data):
                continue
            chunk = data[offset:offset + size].rstrip(b"\x00")
            if chunk:
                chunks.append(chunk)
        if chunks:
            executable = b"".join(chunks)
            facts["executable_sha256"] = _sha256_bytes(executable)
            facts["opcode_tokens"] = _opcode_tokens(executable,
                                                    str(info.arch))
    except Exception as exc:  # noqa: BLE001 - recorded as unsupported
        facts["executable_error"] = f"{type(exc).__name__}: {exc}"
    return facts


def _ngrams(tokens: list[str], size: int = OPCODE_NGRAM) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return set()
    return {tuple(tokens[index:index + size])
            for index in range(len(tokens) - size + 1)}


def _jaccard(left: set[Any], right: set[Any]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\sA-Za-z0-9_]")


def _text_tokens(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return _TOKEN_RE.findall(text.lower())[:TEXT_MAX_TOKENS]


def _text_similarity(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    return float(difflib.SequenceMatcher(None, left, right,
                                         autojunk=False).ratio())


def _sample_facts(sample: dict[str, Any], families: dict[str, str],
                  hidden: bool = False) -> dict[str, Any]:
    sample_id = str(sample.get("sample_id") or sample.get("opaque_sample_id"))
    split = str(sample.get("split") or "unknown")
    binary_sha = sample.get("binary_sha256")
    binary_path = sample.get("binary_path") or sample.get("binary")
    binary_facts: dict[str, Any] = {}
    if binary_path:
        path = _resolve(str(binary_path))
        if path.is_file():
            binary_facts = _binary_facts(path)
            binary_sha = binary_facts["sha256"]
    source_hashes: list[str] = []
    source_paths: list[str] = []
    for ref in sample.get("source_refs") or []:
        relative = _strip_ref(ref)
        if not relative:
            continue
        if hidden:
            continue
        path = _resolve(relative)
        if path.is_file() and path.suffix.lower() in {
                ".c", ".h", ".s", ".asm", ".cpp", ".cc"}:
            source_hashes.append(_sha256_file(path))
            source_paths.append(relative)
    oracle = sample.get("oracle") if isinstance(
        sample.get("oracle"), dict) else {}
    poc_sha = None
    oracle_path = oracle.get("manifest_path")
    if oracle_path:
        path = _resolve(str(oracle_path))
        if path.is_file():
            poc_sha = _sha256_file(path)
    reference = sample.get("reference_fix")
    reference_sha = None
    reference_path = None
    if isinstance(reference, dict):
        reference_path = reference.get("path")
        reference_sha = reference.get("sha256")
        if reference_path:
            path = _resolve(str(reference_path))
            if path.is_file():
                reference_sha = _sha256_file(path)
    return {
        "sample_id": sample_id,
        "split": split,
        "hidden": hidden,
        "family": "hidden" if hidden else _family(sample_id, families),
        "binary_sha256": binary_sha,
        "binary_opcode_tokens": binary_facts.get("opcode_tokens") or [],
        "target_key": _target_key(sample),
        "source_hashes": sorted(set(source_hashes)),
        "source_paths": source_paths,
        "poc_sha256": poc_sha,
        "reference_sha256": reference_sha,
        "reference_path": reference_path,
    }


def _apply_origin_families(samples: list[dict[str, Any]],
                           declared: dict[str, str]) -> None:
    """Union samples sharing declared variant or committed source/reference."""
    parent: dict[str, str] = {item["sample_id"]: item["sample_id"]
                              for item in samples}

    def find(value: str) -> str:
        root = value
        while parent.get(root, root) != root:
            root = parent[root]
        while parent.get(value, value) != value:
            parent[value], value = root, parent[value]
        return root

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for sample_id, source_sample in declared.items():
        if sample_id in parent and source_sample in parent:
            union(sample_id, source_sample)
    by_source: dict[str, list[str]] = defaultdict(list)
    by_reference: dict[str, list[str]] = defaultdict(list)
    for item in samples:
        for path in item["source_paths"]:
            by_source[path].append(item["sample_id"])
        if item["reference_path"]:
            by_reference[item["reference_path"]].append(item["sample_id"])
    for group in list(by_source.values()) + list(by_reference.values()):
        for other in group[1:]:
            union(group[0], other)
    for item in samples:
        item["family"] = find(item["sample_id"])


def _public_samples(manifest: dict[str, Any],
                    families: dict[str, str]) -> list[dict[str, Any]]:
    return [_sample_facts(sample, families)
            for sample in manifest.get("samples", [])
            if isinstance(sample, dict)]


def _hidden_samples(root: Path,
                    manifest_path: Path | None
                    ) -> tuple[list[dict[str, Any]], str]:
    path = manifest_path or (root / "manifest.json")
    if not path.is_file():
        return [], "hidden manifest missing"
    try:
        manifest = _load_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [], f"hidden manifest unreadable: {type(exc).__name__}"
    raw = manifest.get("samples") if isinstance(manifest, dict) else None
    if not isinstance(raw, list) or not raw:
        return [], "hidden manifest has no samples"
    facts: list[dict[str, Any]] = []
    for index, sample in enumerate(raw):
        if not isinstance(sample, dict):
            continue
        candidate = dict(sample)
        candidate.setdefault("sample_id", f"hidden_{index:03d}")
        if candidate.get("binary_path") or candidate.get("binary"):
            candidate["binary_path"] = str(
                root / str(candidate.get("binary_path") or candidate["binary"]))
        facts.append(_sample_facts(candidate, {}, hidden=True))
    return facts, "hidden mode enabled"


def _label(sample: dict[str, Any]) -> str:
    return "hidden" if sample["hidden"] else str(sample["sample_id"])


def _different_targets(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left["target_key"] != right["target_key"]


def _exact_duplicates(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for kind in ("binary", "poc", "reference"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            digest = sample.get(f"{kind}_sha256")
            if digest:
                groups[digest].append(sample)
        for digest, group in sorted(groups.items()):
            if len(group) < 2:
                continue
            hidden = any(item["hidden"] for item in group)
            families = {item["family"] for item in group if not item["hidden"]}
            same_family = len(families) <= 1 and not hidden
            distinct_targets = all(_different_targets(group[0], item)
                                   for item in group[1:])
            if kind == "binary":
                if hidden:
                    res, sev = "contaminated_public_hidden_overlap", "contaminated"
                elif distinct_targets:
                    res, sev = "same_binary_different_target_allowed", "note"
                else:
                    res, sev = "exact_binary_duplicate_same_target", "contaminated"
            else:
                if hidden:
                    res, sev = "contaminated_public_hidden_overlap", "contaminated"
                elif same_family:
                    res, sev = "shared_declared_family_allowed", "note"
                elif distinct_targets:
                    res, sev = ("shared_committed_fixture_distinct_target",
                                "note")
                else:
                    res, sev = "exact_duplicate_same_target", "contaminated"
            findings.append({
                "kind": kind,
                "digest_short": None if hidden else digest[:16],
                "samples": [_label(item) for item in group],
                "hidden_involved": hidden,
                "resolution": res,
                "severity": sev,
            })
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        for digest in sample["source_hashes"]:
            groups[digest].append(sample)
    for digest, group in sorted(groups.items()):
        unique = list({item["sample_id"]: item for item in group}.values())
        if len(unique) < 2:
            continue
        hidden = any(item["hidden"] for item in unique)
        families = {item["family"] for item in unique if not item["hidden"]}
        if hidden:
            res, sev = "contaminated_public_hidden_overlap", "contaminated"
        elif len(families) == 1:
            res, sev = "shared_declared_family_allowed", "note"
        elif all(_different_targets(unique[0], item) for item in unique[1:]):
            res, sev = "shared_committed_fixture_distinct_target", "note"
        else:
            res, sev = "shared_source_same_target", "suspicious"
        findings.append({
            "kind": "source",
            "digest_short": None if hidden else digest[:16],
            "samples": [_label(item) for item in unique],
            "hidden_involved": hidden,
            "resolution": res,
            "severity": sev,
        })
    return findings


def _near_duplicates(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for index, left in enumerate(samples):
        for right in samples[index + 1:]:
            if left["binary_sha256"] and left["binary_sha256"] == right[
                    "binary_sha256"]:
                continue
            hidden = left["hidden"] or right["hidden"]
            allowed = (not hidden and left["family"] == right["family"])
            similarity = _jaccard(_ngrams(left["binary_opcode_tokens"]),
                                  _ngrams(right["binary_opcode_tokens"]))
            if similarity >= NEAR_BINARY_THRESHOLD:
                findings.append({
                    "kind": "binary_executable",
                    "similarity": round(similarity, 6),
                    "threshold": NEAR_BINARY_THRESHOLD,
                    "samples": [_label(left), _label(right)],
                    "hidden_involved": hidden,
                    "resolution": ("declared_family_near_duplicate" if allowed
                                   else "undeclared_near_binary"),
                    "severity": ("note" if allowed else
                                 "contaminated" if hidden else "suspicious"),
                })
            for left_path in left["source_paths"]:
                for right_path in right["source_paths"]:
                    if left_path == right_path:
                        continue
                    text_similarity = _text_similarity(
                        _text_tokens(_resolve(left_path)),
                        _text_tokens(_resolve(right_path)))
                    if text_similarity >= NEAR_TEXT_THRESHOLD:
                        findings.append({
                            "kind": "source_text",
                            "similarity": round(text_similarity, 6),
                            "threshold": NEAR_TEXT_THRESHOLD,
                            "samples": [_label(left), _label(right)],
                            "hidden_involved": hidden,
                            "resolution": (
                                "declared_family_near_duplicate" if allowed
                                else "undeclared_near_source"),
                            "severity": ("note" if allowed else
                                         "contaminated" if hidden else
                                         "suspicious"),
                        })
    return findings


def _oracle_runtime(sample: dict[str, Any]) -> bool:
    oracle = sample.get("oracle") if isinstance(
        sample.get("oracle"), dict) else {}
    kinds = set(oracle.get("kinds") or [])
    if not kinds and oracle.get("kind"):
        kinds = {str(oracle["kind"])}
    return bool(kinds & {"external_poc", "native", "emulated"})


def audit(public_manifest_path: Path = ROOT / PUBLIC_MANIFEST,
          hidden_root: Path | None = None,
          hidden_manifest: Path | None = None) -> dict[str, Any]:
    try:
        manifest = _load_json(public_manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"schema_version": SCHEMA_VERSION, "kind": KIND,
                "status": "error",
                "error": f"public manifest unreadable: "
                         f"{type(exc).__name__}: {exc}"}
    try:
        provenance = _load_json(ROOT / PROVENANCE)
    except (OSError, UnicodeError, json.JSONDecodeError):
        provenance = {}
    families = _variant_families(provenance)
    public = _public_samples(manifest, families)
    _apply_origin_families(public, families)
    hidden: list[dict[str, Any]] = []
    hidden_status = "not_run"
    hidden_reason = None
    if hidden_root is not None:
        if not hidden_root.is_dir():
            hidden_reason = "hidden root is missing or not a directory"
        else:
            hidden, hidden_reason = _hidden_samples(hidden_root,
                                                    hidden_manifest)
            hidden_status = "audited" if hidden else "not_run"
    elif hidden_manifest is not None:
        hidden_reason = "hidden manifest supplied without --hidden-root"
    all_samples = public + hidden
    exact = _exact_duplicates(all_samples)
    near = _near_duplicates(all_samples)
    rank = {"note": 0, "suspicious": 1, "contaminated": 2}
    max_sev = max((rank.get(item["severity"], 1)
                   for item in exact + near), default=0)
    verdict = ("contaminated" if max_sev >= 2 else
               "suspicious" if max_sev == 1 else "clean")
    mode = "hidden" if hidden_root is not None else "public_only"
    status = "not_run" if mode == "hidden" and hidden_status == "not_run" \
        else "ok"
    oracle_by_id = {str(sample.get("sample_id")): _oracle_runtime(sample)
                    for sample in manifest.get("samples", [])}
    core = [item for item in public
            if not item["sample_id"].startswith("variant-")]
    counts = {
        "public_samples": len(public),
        "public_dev": sum(1 for item in public if item["split"] == "dev"),
        "public_validation": sum(1 for item in public
                                 if item["split"] == "validation"),
        "public_core": len(core),
        "public_runtime": sum(1 for item in core
                              if oracle_by_id.get(item["sample_id"])),
        "public_analysis_only": sum(1 for item in core
                                    if not oracle_by_id.get(item["sample_id"])),
        "hidden_samples": len(hidden),
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "mode": mode,
        "status": status,
        "public_manifest": {
            "path": str(public_manifest_path.relative_to(ROOT))
            if public_manifest_path.is_relative_to(ROOT) else
            str(public_manifest_path),
            "sha256": _sha256_file(public_manifest_path),
            "sample_count": manifest.get("sample_count"),
            "actual_sample_count": len(public),
            "hidden_available": manifest.get("hidden_available"),
        },
        "hidden": {
            "requested": hidden_root is not None,
            "status": hidden_status,
            "reason": hidden_reason,
            "content_included_in_report": False,
        },
        "counts": counts,
        "exact_duplicates": exact,
        "near_duplicates": near,
        "thresholds": {
            "binary_executable_ngram_jaccard": NEAR_BINARY_THRESHOLD,
            "source_text_similarity": NEAR_TEXT_THRESHOLD,
            "opcode_ngram": OPCODE_NGRAM,
        },
        "verdict": verdict,
        "resolutions": sorted({item["resolution"]
                               for item in exact + near}),
        "limitations": [
            "public-only mode never reads hidden content; hidden mode is "
            "explicit and reports aggregate/classes only",
            "opcode and text similarity are bounded heuristics, not proof of "
            "common origin; tokens are capped for deterministic runtime",
            "declared variants/source families are explicit notes, not silently "
            "exempted",
            "no corpus binary is executed; no network/AI is used",
        ],
        "capability_claims": [],
    }
    return report


def _readme(report: dict[str, Any]) -> str:
    lines = [
        "# Phase-8C contamination audit (2026-11-16)",
        "",
        f"Mode: `{report['mode']}`; status: `{report['status']}`; verdict: "
        f"**{report['verdict']}**",
        "",
        "| count | value |",
        "|---|---|",
    ]
    for key, value in report["counts"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend([
        "",
        "## Findings",
        "",
        "| kind | severity | resolution | samples | similarity |",
        "|---|---|---|---|---|",
    ])
    for item in report.get("exact_duplicates", []) + report.get(
            "near_duplicates", []):
        similarity = item.get("similarity")
        lines.append("| {} | {} | {} | {} | {} |".format(
            item.get("kind"), item.get("severity"),
            item.get("resolution"),
            ", ".join(item.get("samples") or []),
            f"{similarity:.3f}" if similarity is not None else "-"))
    lines.extend([
        "",
        "Hidden mode is explicit and never fakes availability: a missing "
        "hidden root/manifest is `not_run`, not `clean`.",
        "",
        "## Reproduce",
        "",
        "```",
        "python scripts/audit_phase8c_contamination.py --write",
        "python scripts/audit_phase8c_contamination.py --check",
        "python scripts/audit_phase8c_contamination.py --hidden-root PATH --write",
        "```",
        "",
    ])
    return "\n".join(lines)


def _verify_sums(target: Path) -> list[str]:
    sums = target / "SHA256SUMS"
    if not sums.is_file():
        return [f"missing SHA256SUMS: {sums}"]
    problems: list[str] = []
    try:
        lines = sums.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [f"SHA256SUMS unreadable: {exc}"]
    for line in lines:
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
        "contamination.json": _canonical(report),
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


def check_artifact(artifact_dir: Path = ARTIFACT_DIR) -> list[str]:
    target = Path(artifact_dir)
    problems = _verify_sums(target)
    try:
        committed = _load_json(target / "contamination.json")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return problems + [f"contamination.json unreadable: "
                           f"{type(exc).__name__}: {exc}"]
    if committed.get("kind") != KIND:
        problems.append("wrong contamination artifact kind")
    if committed.get("mode") != "public_only":
        problems.append("committed artifact must be public-only")
    fresh = audit()
    if committed != fresh:
        problems.append("contamination.json stale/tampered vs fresh audit")
    readme = target / "README.md"
    if not readme.is_file() or readme.read_text(
            encoding="utf-8") != _readme(fresh):
        problems.append("README.md stale/tampered")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--public-manifest", type=Path,
                        default=ROOT / PUBLIC_MANIFEST)
    parser.add_argument("--hidden-root", type=Path, default=None)
    parser.add_argument("--hidden-manifest", type=Path, default=None)
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifact(args.artifact_dir)
        if problems:
            for problem in problems:
                print(f"CONTAMINATION-VIOLATION: {problem}")
            return 1
        print("contamination-audit: check OK (public-only, deterministic, "
              "SHA256SUMS verified)")
        return 0
    report = audit(args.public_manifest, args.hidden_root,
                   args.hidden_manifest)
    if args.write:
        if report.get("status") == "not_run":
            print(json.dumps({"status": "not_run",
                              "reason": report["hidden"].get("reason")},
                             indent=2))
            return 0
        artifacts = write_artifacts(report, args.artifact_dir)
        print(f"contamination-audit: wrote {artifacts['artifact_dir']}")
        print(f"mode={report['mode']} status={report['status']} "
              f"verdict={report['verdict']}")
        for name in sorted(artifacts["sha256"]):
            print(f"{name}_sha256={artifacts['sha256'][name]}")
        return 0 if report["verdict"] != "contaminated" else 1
    print(json.dumps({
        "mode": report.get("mode"),
        "status": report.get("status"),
        "verdict": report.get("verdict"),
        "counts": report.get("counts"),
        "findings": len(report.get("exact_duplicates", []))
                    + len(report.get("near_duplicates", [])),
        "hidden": report.get("hidden"),
    }, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if report.get("verdict") != "contaminated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
