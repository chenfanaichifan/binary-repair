#!/usr/bin/env python3
"""Apply the independent verifier to every candidate in benchmark run dirs.

The generator's gate/verdict is never used for the verifier decision.  Real
PoC execution is the independent oracle; missing candidates are not_run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import independent_verifier as verifier  # noqa: E402
from app.services import verification_semantics as semantics  # noqa: E402
from app.services.containers import detect_container  # noqa: E402
from app.services.binary_pipeline import build_patch_plan  # noqa: E402
from app.services.poc_runner import run_poc  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _container_meta(data: bytes) -> dict:
    c = detect_container(data)
    return {"format": c.format, "arch": c.arch, "bits": c.bits,
            "endian": getattr(c, "endian", "little")}


def _diff_operations(original: bytes, candidate: bytes, *,
                     header_boundary: int = 4096) -> list[dict]:
    n = min(len(original), len(candidate))
    ops = []
    index = 0
    while index < n:
        if original[index] == candidate[index]:
            index += 1
            continue
        start = index
        while index < n and original[index] != candidate[index]:
            index += 1
        before = original[start:index]
        after = candidate[start:index]
        if before == after:
            continue
        ops.append({
            "kind": "write",
            "reason": "header_update" if start < header_boundary else "reviewed_site",
            "original_offset": start, "size": index - start,
            "before_hex": before.hex(), "after_hex": after.hex(),
        })
    return ops


def _patch_plan(case: dict, original: bytes, candidate: bytes,
                record: dict) -> dict | None:
    injection = record.get("injection") or {}
    if not injection.get("code_bytes") or not injection.get("cave_va"):
        return None
    try:
        target_va = int(str(injection.get("target_va") or "0"), 16)
        cave_va = int(str(injection.get("cave_va") or "0"), 16)
        code_size = int(injection.get("code_bytes") or 0)
    except (TypeError, ValueError):
        return None
    operations = _diff_operations(original, candidate)
    if len(candidate) > len(original):
        operations.append({
            "kind": "insert", "reason": "guard_cave",
            "original_offset": len(original), "size": len(candidate) - len(original),
            "before_hex": "", "after_hex": candidate[len(original):].hex(),
        })
    poc = record.get("candidate", {}).get("poc") or {}
    return {
        "schema_version": 1,
        "candidate_id": "cand-" + str(
            record.get("candidate", {}).get("candidate_sha256") or "unknown")[:16],
        "target_sha256": hashlib.sha256(original).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "strategy": "asm-target-guard",
        "scope_policy": "target_scoped_associated",
        "target_scope": {"policy": "target_scoped_associated",
                         "name": case.get("target"), "va": target_va,
                         "end": target_va + 0x400},
        "operations": operations,
        "cave": {"va": cave_va, "size": max(code_size, 1),
                 "executable": True,
                 "method": str(injection.get("method") or "new-pt-load")},
        "relocations": [],
        "abi_blocks": [{"va": cave_va, "size": max(code_size, 1),
                        "arch": "x86_64"}],
        "oracle": {
            "manifest_sha256": hashlib.sha256(
                (ROOT / case["poc"]).read_bytes()).hexdigest(),
            "runner": poc.get("runner") or "limactl",
            "tier": poc.get("tier") or "emulated_run",
            "status": "executed",
        },
        "limitations": ["automated plan derived from recorded injection metadata"],
    }


def verify_case(run_dir: Path, record: dict, case: dict) -> dict:
    candidate_meta = record.get("candidate") or {}
    artifact = candidate_meta.get("candidate_artifact")
    original_path = ROOT / case["binary"] if not Path(case["binary"]).is_absolute() else Path(case["binary"])
    if not artifact:
        return {"case_id": case["id"], "decision": "not_run",
                "reason": "no candidate artifact"}
    candidate_path = Path(artifact)
    if not candidate_path.is_absolute():
        candidate_path = run_dir / candidate_path
    if not candidate_path.is_file() or not original_path.is_file():
        return {"case_id": case["id"], "decision": "not_run",
                "reason": "artifact missing"}
    original = original_path.read_bytes()
    candidate = candidate_path.read_bytes()
    meta = _container_meta(original)
    meta.update({
        "original_sha256": _sha(original), "candidate_sha256": _sha(candidate),
        "target_scope": {"policy": "whole_image", "name": case.get("target") or "image"},
        "allow_whole_image": True, "allow_resize": True,
        "generator": {"generator_id": "ai-repair-benchmark/1",
                      "agent": "repair-pipeline", "model": record.get("model"),
                      "run_id": case["id"]},
    })
    injection = record.get("injection") or {}
    code_bytes = injection.get("code_bytes")
    code_hex = injection.get("code_hex")
    if code_hex and code_bytes:
        try:
            raw = bytes.fromhex(str(code_hex))
            prefix = raw[:24]
            offset = candidate.rfind(prefix)
            if offset >= 0 and offset + int(code_bytes) <= len(candidate):
                meta["abi_block"] = {"offset": offset, "size": int(code_bytes)}
        except Exception:  # noqa: BLE001
            pass
    manifest = ROOT / case["poc"] if not Path(case["poc"]).is_absolute() else Path(case["poc"])
    injection = record.get("injection") or {}
    actions = []
    try:
        actions.append({
            "kind": "guard",
            "site_va": int(str(injection.get("target_va") or "0"), 16),
            "cave_va": str(injection.get("cave_va") or ""),
            "method": str(injection.get("method") or "new-pt-load"),
        })
    except (TypeError, ValueError):
        actions = []
    poc_manifest = json.loads((ROOT / case["poc"]).read_text())
    target_va_int = actions[0]["site_va"] if actions else 0
    plan = build_patch_plan(
        original, candidate, detect_container(original), actions,
        None, record.get("candidate", {}).get("poc"), poc_manifest,
        {"va": target_va_int, "end": target_va_int + 0x400,
         "name": case.get("target")},
        "target_scoped_associated",
    )
    if isinstance(plan, dict):
        # The builder's ABI blocks describe the primary target; the candidate
        # code actually lives in the declared cave.  Add the cave block using
        # the same mapping/provenance the plan already declared.
        cave_va = actions[0].get("cave_va") if actions else ""
        try:
            plan["abi_blocks"] = [{"va": int(str(cave_va), 16),
                                   "size": int(injection.get("code_bytes") or 0),
                                   "arch": "x86_64"}]
        except (TypeError, ValueError):
            pass
        oracle = plan.setdefault("oracle", {})
        oracle["manifest_sha256"] = hashlib.sha256(
            (ROOT / case["poc"]).read_bytes()).hexdigest()
        oracle["runner"] = (record.get("candidate", {}).get("poc") or {}).get("runner") or "limactl"
        oracle["tier"] = (record.get("candidate", {}).get("poc") or {}).get("tier") or "emulated_run"
        oracle["status"] = "executed"
    report = verifier.verify_repair(
        original=original, candidate=candidate, metadata=meta,
        oracle={"manifest": str(manifest)}, generator=meta["generator"],
        patch_plan=plan, run_poc=run_poc,
    )
    validation = verifier.validate_verification_report(report)
    return {"case_id": case["id"], "decision": report["decision"],
            "report": report, "validation": validation,
            "generator_gate": (record.get("candidate") or {}).get("gate")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, required=True)
    ap.add_argument("--runs", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    manifest = json.loads(args.cases.read_text())
    by_id = {str(c["id"]): c for c in manifest["cases"]}
    records = []
    for run_dir in args.runs:
        summary = json.loads((run_dir / "summary.json").read_text())
        for record in summary.get("cases") or []:
            cid = (record.get("case") or {}).get("id")
            if cid not in by_id:
                continue
            records.append(verify_case(run_dir, record, by_id[cid]))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "verification.json").write_text(json.dumps({"schema_version": 1,
        "kind": "independent_benchmark_verification", "cases": records}, indent=2) + "\n")
    counts = {}
    for item in records:
        counts[item["decision"]] = counts.get(item["decision"], 0) + 1
    lines = ["# Independent benchmark verification", "",
             f"- cases: {len(records)}", f"- decisions: `{json.dumps(counts)}`", ""]
    (args.out / "README.md").write_text("\n".join(lines) + "\n")
    sums = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
            for p in sorted(args.out.iterdir()) if p.is_file() and p.name != "SHA256SUMS"]
    (args.out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(json.dumps({"out": str(args.out), "cases": len(records), "decisions": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
