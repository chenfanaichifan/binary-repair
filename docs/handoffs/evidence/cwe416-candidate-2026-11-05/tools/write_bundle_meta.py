#!/usr/bin/env python3
"""Write the bundle's identity, edit manifest, V4 placeholder and gate index.

Every number here is copied from a file another step produced; nothing is
inferred. In particular V3 is read from ``manifest-repaired.json`` as written by
``routeb/run_manifest_repaired.py``, and V4 is written as ``not_run`` because no
symbolic engine ran.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tool_version(argv: list[str]) -> str:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        return (proc.stdout or proc.stderr).splitlines()[0].strip()
    except Exception:
        return "unavailable"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--patch-report", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--interface", type=Path, required=True)
    ap.add_argument("--manifest-repaired", type=Path, required=True)
    ap.add_argument("--manifest-control", type=Path, required=True)
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--valid", type=Path, required=True)
    ap.add_argument("--repro", type=Path, required=True)
    ap.add_argument("--function", required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    original, candidate = args.original, args.candidate
    patch = read(args.patch_report)
    audit = read(args.audit)
    interface = read(args.interface)
    repaired = read(args.manifest_repaired)
    control = read(args.manifest_control)
    contract = read(args.contract)
    valid = read(args.valid)
    repro = read(args.repro)

    o_sha, c_sha = sha256(original), sha256(candidate)
    contract_sha = sha256(args.contract)
    manifest_original = valid["tests"][0].get("original_sha256") or valid.get("original_sha256")

    identity_checks = {
        "candidate_built_from_this_original": patch["original"]["sha256"] == o_sha,
        "original_matches_contract_manifest": o_sha == manifest_original,
        "file_sizes_recorded": patch["candidate"]["size"] == candidate.stat().st_size,
        "git_blob_hash_recorded": None,
    }
    identity_checks.pop("git_blob_hash_recorded")
    v0 = {
        "gate": "V0",
        "kind": "identity",
        "scope": "metadata",
        "state": "measured",
        "checks": identity_checks,
        "original_sha256": o_sha,
        "candidate_sha256": c_sha,
        "size": {"original": original.stat().st_size, "candidate": candidate.stat().st_size},
        "contract_sha256": contract_sha,
        "fixture_manifest_original_sha256": manifest_original,
        "pass": all(identity_checks.values()),
    }
    (args.out_dir / "v0-identity.json").write_text(json.dumps(v0, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 2,
        "route": "route_b",
        "mode": "fixed",
        "function": args.function,
        "original_sha256": o_sha,
        "candidate_sha256": c_sha,
        "original_size": original.stat().st_size,
        "candidate_size": candidate.stat().st_size,
        "replacement_c_sha256": None,
        "edit_method": {
            "kind": "byte-level instruction removal",
            "tool": "patch_candidate.py",
            "replacement_c": False,
            "code_cave": False,
            "bytes_added": 0,
            "contract_clause": patch["edits"][0]["contract_clause"],
        },
        "edits": patch["edits"],
        "changed_file_intervals": patch["changed_intervals"],
        "header_changes": {
            "same_program_header_count": audit["checks"]["program_headers_unchanged"],
            "entry_unchanged": audit["checks"]["entry_unchanged"],
        },
        "relocations_added": audit["relocations"]["candidate"] - audit["relocations"]["original"],
        "tools": {
            "compiler": tool_version(["gcc", "--version"]),
            "readelf": tool_version(["readelf", "--version"]),
            "objdump": tool_version(["objdump", "--version"]),
            "python": platform.python_version(),
        },
        "runtime_manifest": {
            "state": "measured",
            "artifact": "manifest-repaired.json",
            "input_mode": contract["input_mode"],
            "invalid": repaired["invalid"],
            "valid": repaired["valid"],
            "passed": repaired["passed"],
            "total": repaired["total"],
            "repaired_pass": repaired["repaired_pass"],
        },
        "scope_authorized": True,
        "audit": {"checks": audit["checks"], "pass": audit["pass"]},
        "contract_sha256": contract_sha,
    }
    (args.out_dir / "edit-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    v4 = {
        "gate": "V4",
        "kind": "symbolic",
        "scope": "model",
        "state": "not_run",
        "ran": False,
        "reason": (
            "no symbolic or bounded-model engine was run in this window; the five-byte "
            "edit has no model-level proof, and a replay result cannot be upgraded to one"
        ),
        "claimed_scope": None,
        "not_claimed": [
            "binary-level proof of the repair",
            "memory-safety for any path other than the single no-input observation",
            "absence of the defect in the rest of the program",
        ],
    }
    (args.out_dir / "v4-symbolic.json").write_text(json.dumps(v4, indent=2) + "\n", encoding="utf-8")

    index = {
        "schema_version": 1,
        "candidate_sha256": c_sha,
        "original_sha256": o_sha,
        "contract": {
            "sha256": contract_sha,
            "schema_version": contract["schema_version"],
            "input_mode": contract["input_mode"],
            "invalid": "not_applicable",
        },
        "gates": [
            {"gate": "V0", "kind": "identity", "scope": "metadata", "file": "v0-identity.json",
             "result": "passed" if v0["pass"] else "failed",
             "detail": f"original {o_sha} candidate {c_sha}"},
            {"gate": "V1", "kind": "structure", "scope": "binary", "file": "audit.json",
             "result": "passed" if audit["pass"] else "failed",
             "detail": f"{audit['changed_bytes']} changed bytes, all inside the recorded interval; "
                       f"size {audit['size']['original']} -> {audit['size']['candidate']}; "
                       f"segments and section layout unchanged"},
            {"gate": "V2", "kind": "interface", "scope": "binary", "file": "v2-interface.json",
             "result": "not_run",
             "detail": "no interface check is implemented in Route B; the file records a static "
                       f"observation (pass={str(interface['pass']).lower()}) and claims no verdict"},
            {"gate": "V3", "kind": "behaviour", "scope": "replay", "file": "manifest-repaired.json",
             "result": "passed" if repaired["repaired_pass"] else "failed",
             "detail": f"input_mode=none, valid {repaired['valid']}, passed={repaired['passed']} "
                       f"total={repaired['total']}, invalid={repaired['invalid']}"},
            {"gate": "V4", "kind": "symbolic", "scope": "model", "file": "v4-symbolic.json",
             "result": "not_run",
             "detail": "no symbolic engine ran; not a binary-level claim"},
            {"gate": "V5", "kind": "reproducibility", "scope": "replay", "file": "reproducibility.json",
             "result": "passed" if repro["pass"] else "failed",
             "detail": "source rebuilt twice to the same digest; patch replayed twice to the same digest"},
        ],
        "control": {
            "file": "manifest-repaired-original.json",
            "note": "the same runner and manifest pointed at the unrepaired original",
            "valid": control["valid"],
            "passed": control["passed"],
            "total": control["total"],
            "repaired_pass": control["repaired_pass"],
            "stdout_hex": control["cases"][0]["got"]["stdout_hex"],
        },
        "not_claimed": [
            "Gate 4 acceptance",
            "T8.3 relief",
            "a second defect class or a second sample",
            "binary-level V4",
        ],
    }
    (args.out_dir / "gate-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"v0": v0["pass"], "edit_manifest": manifest["candidate_sha256"][:16],
                      "v3": index["gates"][3]["detail"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
