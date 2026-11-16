#!/usr/bin/env python3
"""Run real metamorphic/input-mutation discovery over Phase-8C variants."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import metamorphic_discovery as mechanism  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "phase8d-discovery-2026-11-17"
FILES = ("discovery.json", "README.md", "SHA256SUMS")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def build_files(payload: dict[str, Any]) -> dict[str, bytes]:
    files = {"discovery.json": _canonical(payload).encode("utf-8")}
    s = payload["summary"]
    lines = [
        "# Phase-8D metamorphic and input-mutation discovery (2026-11-17)",
        "",
        "Real deterministic-engine and guest-oracle runs over the committed",
        "Phase-8C compiler variants. No candidates or capabilities are invented.",
        "",
        f"- manifest: `{payload['manifest_path']}` sha `{payload['manifest_sha256']}`",
        f"- variants run: {s['variant_count']}",
        f"- engine executed: {s['engine_executed']}; not_run/unsupported: {s['engine_not_run_or_unsupported']}",
        f"- input mutations: {s['mutation_count']}; executed: {s['mutations_executed']}",
        f"- relations held: {s['relation_hold_count']}; differences: {s['relation_difference_count']}",
        f"- engine-level differences: {s['engine_difference_count']}",
        "",
        "## Relations",
        "",
        "| relation | variants |",
        "|---|---|",
    ]
    for relation in payload.get("relations") or []:
        lines.append(f"| {relation['relation_id']} | {', '.join(relation['variant_sample_ids'])} |")
    lines += ["", "## Measured differences", ""]
    if payload.get("differences"):
        for item in payload["differences"]:
            lines.append(f"- `{item['difference_type']}` / `{item.get('relation_id')}`: "
                         f"{item.get('interpretation')}")
    else:
        lines.append("- none measured")
    lines += ["", "## Not run", ""]
    if payload.get("not_run"):
        for item in payload["not_run"]:
            lines.append(f"- `{item.get('sample_id')}`: {item.get('reason')}")
    else:
        lines.append("- none")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in payload.get("limitations") or [])
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python scripts/run_metamorphic_discovery.py --write",
        "python scripts/run_metamorphic_discovery.py --check",
        "python -m pytest -q tests/test_phase8d_metamorphic_discovery.py",
        "```",
        "",
    ]
    files["README.md"] = "\n".join(lines).encode("utf-8")
    files["SHA256SUMS"] = "".join(
        f"{_sha(files[name])}  {name}\n" for name in sorted(files)
    ).encode("utf-8")
    return files


def write_artifact(payload: dict[str, Any], out: Path = ARTIFACT_DIR) -> list[str]:
    files = build_files(payload)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    return sorted(files)


def check_artifact(out: Path = ARTIFACT_DIR) -> list[str]:
    problems: list[str] = []
    if not (out / "discovery.json").is_file():
        return ["missing discovery.json"]
    try:
        payload = json.loads((out / "discovery.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"discovery.json unreadable: {exc}"]
    if payload.get("kind") != mechanism.KIND:
        problems.append("kind mismatch")
    if payload.get("provenance", {}).get("no_hidden_material_read") is not True:
        problems.append("hidden-material provenance flag missing")
    summary = payload.get("summary") or {}
    for key in ("variant_count", "engine_executed", "mutation_count",
                "relation_hold_count", "relation_difference_count"):
        if not isinstance(summary.get(key), int):
            problems.append(f"summary.{key} must be an integer")
    if summary.get("variant_count", 0) <= 0:
        problems.append("no variant was measured")
    for item in payload.get("differences") or []:
        if str(item.get("difference_type") or "") not in {
            "compiler_variant_engine_capability_difference",
            "input_mutation_behavior_difference",
        }:
            problems.append("unknown difference type")
    if payload.get("provenance", {}).get("network_used") is not False:
        problems.append("network_used must be false")
    if payload.get("provenance", {}).get("ai_used") is not False:
        problems.append("ai_used must be false")
    sums = out / "SHA256SUMS"
    if not sums.is_file():
        problems.append("missing SHA256SUMS")
    else:
        listed = {}
        for line in sums.read_text(encoding="utf-8").splitlines():
            if line.strip():
                digest, name = line.split(None, 1)
                listed[name.strip()] = digest
        expected = {"discovery.json", "README.md"}
        if set(listed) != expected:
            problems.append(f"SHA256SUMS entries {sorted(listed)} != {sorted(expected)}")
        for name, digest in listed.items():
            target = out / name
            if not target.is_file():
                problems.append(f"missing {name}")
            elif _sha(target.read_bytes()) != digest:
                problems.append(f"sha mismatch {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-variants", type=int, default=None)
    parser.add_argument("--max-mutations", type=int, default=None)
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifact()
        if args.json:
            print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
        else:
            print("metamorphic: " + ("check OK" if not problems else
                                      f"{len(problems)} problem(s)"))
            for item in problems:
                print(f"  - {item}")
        return 0 if not problems else 1
    payload = mechanism.discover(
        root=ROOT, max_variants=args.max_variants, max_mutations=args.max_mutations,
    )
    if args.write:
        files = write_artifact(payload)
        print(f"metamorphic: wrote {ARTIFACT_DIR} files={len(files)}")
        return 0
    if args.json:
        print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
