#!/usr/bin/env python3
"""Generate the committed M2 analysis evidence for 2026-11-16 (deterministic).

Read-only: this generator only reads fixtures and runs the read-only analysis
prototype (plus one read-only current-engine probe in memory).  It never writes
a patch, never persists candidate bytes, never calls a model/provider and is
not wired into any gate.

Run from anywhere:
  .venv/bin/python artifacts/m2-analysis-2026-11-16/generate_evidence.py

Outputs (all in this directory):
  envelope.json
  cfg-elf-strcpy-x86_64.json
  crossfn-param.analysis.json
  crossfn-global.analysis.json
  heap-canary.analysis.json
  capacity-param.crosscheck.json
  engine-probe.json
  comparison.json
  SHA256SUMS
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.analysis import analyze_crossfn  # noqa: E402
from app.services.analysis.callgraph import build_call_graph  # noqa: E402
from app.services.analysis.cfg import build_cfg  # noqa: E402
from app.services.binary_pipeline import repair_any  # noqa: E402
from app.services.containers import detect_container  # noqa: E402

FIXTURES = {
    "elf_strcpy_x86_64": ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf",
    "crossfn_param": ROOT / "fixtures" / "crossfn" / "crossfn_param.elf",
    "crossfn_global": ROOT / "fixtures" / "crossfn" / "crossfn_global.elf",
    "heap_canary": ROOT / "fixtures" / "hard-cases" / "vuln-heap-canary-x86_64.elf",
    "capacity_param": ROOT / "fixtures" / "hard-cases" / "vuln-capacity-param-x86_64.elf",
}
CROSSFN = ROOT / "fixtures" / "crossfn"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _input(path: Path) -> dict:
    return {"path": _rel(path), "sha256": _sha256(path), "size": path.stat().st_size}


def _write(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n",
                            encoding="utf-8")


def _package_versions() -> dict:
    versions: dict[str, str] = {"python": platform.python_version()}
    try:
        import capstone

        versions["capstone"] = str(capstone.__version__)
    except Exception:  # noqa: BLE001
        versions["capstone"] = "unavailable"
    try:
        import lief

        versions["lief"] = str(lief.__version__)
    except Exception:  # noqa: BLE001
        versions["lief"] = "unavailable"
    try:
        import elftools

        versions["pyelftools"] = str(getattr(elftools, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        versions["pyelftools"] = "unavailable"
    return versions


# ---------------------------------------------------------------------------
# 1. P0-1 CFG + direct call graph evidence on the required real fixture
# ---------------------------------------------------------------------------


def build_cfg_evidence() -> dict:
    path = FIXTURES["elf_strcpy_x86_64"]
    data = path.read_bytes()
    container = detect_container(data)
    cfg = build_cfg(data, container=container)
    call_graph = build_call_graph(data, cfg, container=container)
    named = {function.name: function for function in cfg.functions}
    selected = [named["main"], named["vuln_copy"]]
    selected_vas = {function.va for function in selected}
    edges = [edge.to_dict() for edge in call_graph.edges
             if edge.from_va in selected_vas]
    function_index = [
        {
            "va": function.va,
            "name": function.name,
            "source": function.source,
            "size": function.size,
            "block_count": len(function.blocks),
            "instruction_count": function.instruction_count,
        }
        for function in cfg.functions
    ]
    return {
        "schema_version": 1,
        "tool": "m2-analysis-cfg-callgraph",
        "input": _input(path),
        "format": cfg.format,
        "arch": cfg.arch,
        "bits": cfg.bits,
        "entry": cfg.entry,
        "statistics": cfg.statistics,
        "callgraph_statistics": call_graph.statistics,
        "functions": [function.to_dict(include_instructions=True)
                      for function in selected],
        "function_index": function_index,
        "edges_from_selected_functions": edges,
        "edges_total": len(call_graph.edges),
        "limitations": cfg.limitations[:40],
        "limitations_total": len(cfg.limitations),
        "limitations_note": ("only the first 40 of the full CFG limitation list are "
                             "inlined; the count is limitations_total"),
        "reproduce": ("scripts/analyze_crossfn.py --elf fixtures/elf/"
                      "vuln-strcpy-x86_64.elf --json (the CLI also exposes the "
                      "cross-function dataflow for this image)"),
    }


# ---------------------------------------------------------------------------
# 2. P0-2 cross-function dataflow evidence on the new fixtures
# ---------------------------------------------------------------------------


def build_crossfn_analysis(path: Path, function_names: list[str]) -> dict:
    data = path.read_bytes()
    container = detect_container(data)
    payload = analyze_crossfn(data, container=container)
    payload["input"] = _input(path)
    cfg = build_cfg(data, container=container)
    wanted = set(function_names)
    payload["cfg_functions"] = [
        function.to_dict(include_instructions=True)
        for function in cfg.functions
        if function.name in wanted
    ]
    payload["reproduce"] = (
        f"scripts/analyze_crossfn.py --elf {_rel(path)} --json --functions "
        f"{','.join(function_names)}"
    )
    return payload


# ---------------------------------------------------------------------------
# 3. current deterministic engine probe (read-only; no candidate bytes kept)
# ---------------------------------------------------------------------------


def build_engine_probe() -> dict:
    probes = [
        ("elf_strcpy_x86_64", "vuln_copy", True),
        ("crossfn_param", "copy_payload", True),
        ("crossfn_param", "wrapper", True),
        ("crossfn_param", None, False),
        ("crossfn_global", "store_out", True),
        ("crossfn_global", None, False),
        ("heap_canary", "heap_bad", True),
    ]
    rows: list[dict] = []
    for fixture, target, require_target in probes:
        path = FIXTURES[fixture]
        data = path.read_bytes()
        kwargs: dict = {"require_target": require_target}
        if target is not None:
            kwargs["target"] = target
        outcome = repair_any(data, **kwargs)
        report = outcome.report
        universal = report.universal or {}
        rows.append({
            "fixture": _rel(path),
            "fixture_sha256": _sha256(path),
            "target": target,
            "require_target": require_target,
            "status": report.status,
            "disposition": report.disposition,
            "error": report.error,
            "mode": report.mode,
            "backend": report.backend,
            "strategy": report.strategy,
            "capacity": report.capacity,
            "target_scope": universal.get("target_scope"),
            "target_policy": universal.get("target_policy"),
            "universal_reason": universal.get("reason"),
            "candidate_returned": outcome.candidate is not None,
            "candidate_bytes_persisted": False,
            "download_allowed": bool(outcome.download_allowed),
            "limitations": list(report.limitations)[:8],
        })
    return {
        "schema_version": 1,
        "tool": "m2-current-engine-readonly-probe",
        "policy": ("read-only: repair_any is called in memory with the declared "
                   "target; candidate bytes, if any, are discarded and never "
                   "written; the M2 increment produces no candidate artifact"),
        "engine": "same-function/leaf-only deterministic analyzer in binary_pipeline",
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# 4. comparison: current engine vs prototype
# ---------------------------------------------------------------------------


def _prototype_summary(payload: dict) -> dict:
    sinks = payload.get("sinks") or []
    if not sinks:
        return {"sinks": 0}
    sink = sinks[0]
    destination = sink["destination"]
    return {
        "sink": {
            "site_va": sink["site_va"],
            "callee": sink["callee"],
            "function": sink["function"],
        },
        "destination_origin": destination["origin"],
        "capacity": destination["capacity"],
        "capacity_source": destination["capacity_source"],
        "agreement": destination["agreement"],
        "resolution": destination["resolution"],
        "confidence": sink["confidence"],
        "call_paths": [
            {
                "caller": (path_entry.get("caller") or {}).get("name"),
                "origin": path_entry["origin"],
                "capacity": path_entry["capacity"],
                "capacity_source": path_entry["capacity_source"],
                "resolution": path_entry["resolution"],
            }
            for path_entry in destination["paths"]
        ],
    }


def build_comparison(param_payload: dict, global_payload: dict,
                     heap_payload: dict) -> dict:
    engine_probe = build_engine_probe()
    engine_by_fixture: dict[str, list[dict]] = {}
    for row in engine_probe["rows"]:
        engine_by_fixture.setdefault(row["fixture"], []).append(row)

    def engine_rows(name: str) -> list[dict]:
        path = _rel(FIXTURES[name])
        return [
            {
                "target": row["target"],
                "disposition": row["disposition"],
                "status": row["status"],
                "error": row["error"],
                "candidate_returned": row["candidate_returned"],
            }
            for row in engine_by_fixture.get(path, [])
        ]

    return {
        "schema_version": 1,
        "tool": "m2-engine-vs-prototype-comparison",
        "engine": "current same-function/leaf-only deterministic engine",
        "prototype": "app/services/analysis/** (read-only analysis evidence)",
        "rows": [
            {
                "fixture": _rel(FIXTURES["crossfn_param"]),
                "failure_class": "cross-function dataflow (capacity lives in callers)",
                "engine": engine_rows("crossfn_param"),
                "prototype": _prototype_summary(param_payload),
                "verdict": (
                    "engine finds no patchable sink inside copy_payload/wrapper and "
                    "returns analysis_only; the prototype locates the sink and "
                    "traces both caller-specific capacity origins (stack frame upper "
                    "bound 32 for wrapper, exact STT_OBJECT size 16 through the "
                    "ret_buffer return value for wrapper2)"
                ),
                "honest_limit": (
                    "the prototype reports the frame-geometry capacity as an UPPER "
                    "BOUND, so it does not claim the exact 16 for wrapper's buffer; "
                    "DWARF object sizes are not analyzed in this increment"
                ),
            },
            {
                "fixture": _rel(FIXTURES["crossfn_global"]),
                "failure_class": "global destination capacity (symbol size, not frame)",
                "engine": engine_rows("crossfn_global"),
                "prototype": _prototype_summary(global_payload),
                "verdict": (
                    "engine returns analysis_only for store_out; the prototype "
                    "resolves the global destination to the STT_OBJECT symbol g_out "
                    "and reports the exact capacity 16 (object_symbol_size)"
                ),
                "honest_limit": (
                    "the copied data length is still unbounded program input "
                    "(argv[1]); no repair invariant is claimed"
                ),
            },
            {
                "fixture": _rel(FIXTURES["heap_canary"]),
                "failure_class": (
                    "same-function immediate-malloc heap capacity (already inside "
                    "the deterministic engine's class; known over-estimate)"
                ),
                "engine": engine_rows("heap_canary"),
                "prototype": _prototype_summary(heap_payload),
                "verdict": (
                    "prototype recovers the same allocation-size capacity (24) the "
                    "engine's heap model uses and flags the documented over-estimate "
                    "against the 16-byte struct member; this is a cross-check of the "
                    "known LIMITATIONS section 21 residual, not a new capability"
                ),
                "honest_limit": (
                    "member layout needs DWARF; the recovered 24 is the allocation "
                    "size, not the char data[16] size"
                ),
            },
        ],
    }


# ---------------------------------------------------------------------------
# 5. P2 cross-check: same-function capacity class
# ---------------------------------------------------------------------------


def build_capacity_crosscheck() -> dict:
    path = FIXTURES["capacity_param"]
    data = path.read_bytes()
    container = detect_container(data)
    payload = analyze_crossfn(data, container=container)
    cfg = build_cfg(data, container=container)
    render = next((function for function in cfg.functions
                   if function.name == "render"), None)
    summary = payload["statistics"]
    return {
        "schema_version": 1,
        "tool": "m2-capacity-class-crosscheck",
        "input": _input(path),
        "why_not_the_same_gap": (
            "the reviewed capacity_confusion defect keeps out_size/data_size as "
            "parameters of the same function render(); the deterministic capacity "
            "strategy already reasons about those register-allocated capacities. "
            "The M2 cross-function gap is different: the capacity is in a caller "
            "frame and the sink sits in another function, so no same-function "
            "value is available at the sink."
        ),
        "prototype_statistics": summary,
        "prototype_sample_sinks": [
            {
                "site_va": sink["site_va"],
                "callee": sink["callee"],
                "function": sink["function"],
                "destination_origin": sink["destination"]["origin"],
                "capacity": sink["destination"]["capacity"],
                "resolution": sink["destination"]["resolution"],
            }
            for sink in payload["sinks"][:3]
        ],
        "render_function": ({
            "va": render.va,
            "block_count": len(render.blocks),
            "instruction_count": render.instruction_count,
            "note": ("capacity is an argument of render(); prototype does not treat "
                     "it as a copy destination capacity and reports unknown for "
                     "pointer-arithmetic destinations"),
        } if render is not None else None),
        "stripped_image_observation": {
            "function_list": [
                {"va": function.va, "name": function.name, "source": function.source,
                 "block_count": len(function.blocks)}
                for function in cfg.functions
            ],
            "cfg_statistics": cfg.statistics,
            "note": ("vuln-capacity-param-x86_64.elf is a stripped image (-s): the "
                     "prototype is anchored on authoritative symbols, so it only "
                     "reconstructs the entry point and direct-call-target "
                     "functions and finds no copy sink. The deterministic capacity "
                     "strategy works from scanned code blocks instead of symbols; "
                     "stripped-binary function discovery is an explicit M2 "
                     "limitation, not a capability claim."),
        },
        "reproduce": (f"scripts/analyze_crossfn.py --elf {_rel(path)} --json"),
    }


# ---------------------------------------------------------------------------
# 6. envelope / environment / explicit not_run list
# ---------------------------------------------------------------------------


def build_envelope() -> dict:
    hashes = {}
    if (CROSSFN / "original.sha256").is_file():
        for line in (CROSSFN / "original.sha256").read_text().splitlines():
            parts = line.split()
            if len(parts) == 2:
                hashes[parts[1]] = parts[0]
    return {
        "schema_version": 1,
        "tool": "m2-analysis-evidence-envelope",
        "generated_by": "artifacts/m2-analysis-2026-11-16/generate_evidence.py",
        "deterministic": ("no timestamps or random values are written; rerunning "
                          "produces identical JSON and SHA256SUMS"),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "note": ("x86-64 Linux ELF fixtures cannot be executed on this host; "
                     "runtime expectations are declared, not measured"),
        },
        "toolchain": {
            "fixtures_c": ("zig 0.17.1 bundled at binary-repair-gui/.tmp/zigpkg/"
                           "site/ziglang/zig (not committed); build flags recorded "
                           "in fixtures/crossfn/build.sh"),
            "compile_flags": ("-target x86_64-linux-gnu -O0 -g0 -fno-pie -no-pie "
                              "-fno-stack-protector -fno-sanitize=all"),
            "packages": _package_versions(),
        },
        "fixture_sha256": hashes,
        "not_run": [
            {"item": "runtime PoC / regression execution on the new fixtures",
             "status": "not_run",
             "reason": ("x86-64 Linux ELF on a macOS arm64 host; no local runtime "
                        "oracle; manifests are declared_not_run")},
            {"item": "DWARF object-size capacity recovery",
             "status": "not_run",
             "reason": ("not implemented in this increment; stack capacities stay "
                        "frame-geometry upper bounds")},
            {"item": "indirect call target resolution",
             "status": "not_run",
             "reason": ("indirect calls are explicit unresolved edges; no target "
                        "is guessed")},
            {"item": "path-sensitive / concurrency / struct-layout analysis",
             "status": "not_run",
             "reason": "out of the minimal Phase-9 P0-2 scope"},
            {"item": "repair candidate production or gate integration",
             "status": "not_run",
             "reason": ("M2 red line: analysis evidence only; repair_any behavior "
                        "is unchanged and no candidate is produced")},
            {"item": "multi-model / provider validation",
             "status": "not_run",
             "reason": "no live model or provider call is made by M2"},
        ],
        "design_boundaries": [
            "module scope: app/services/analysis/**, scripts/analyze_crossfn.py, "
            "tests/test_analysis_*.py, fixtures/crossfn/**, this artifact directory",
            "the prototype is not imported by repair_any, unified_verification or "
            "any planner/gate",
            "no git operation is performed; integration is the Lead's job",
        ],
    }


def build_sha256sums() -> None:
    lines = []
    for path in sorted(OUT.iterdir()):
        if path.name in {"SHA256SUMS"} or path.is_dir():
            continue
        if path.name.endswith(".pyc"):
            continue
        lines.append(f"{_sha256(path)}  {path.name}")
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    missing = [name for name, path in FIXTURES.items() if not path.is_file()]
    if missing:
        print(f"error: missing fixtures: {missing}", file=sys.stderr)
        return 2
    _write("cfg-elf-strcpy-x86_64.json", build_cfg_evidence())
    param_payload = build_crossfn_analysis(
        FIXTURES["crossfn_param"],
        ["main", "wrapper", "wrapper2", "copy_payload", "ret_buffer"],
    )
    _write("crossfn-param.analysis.json", param_payload)
    global_payload = build_crossfn_analysis(
        FIXTURES["crossfn_global"], ["main", "store_out"],
    )
    _write("crossfn-global.analysis.json", global_payload)
    heap_payload = build_crossfn_analysis(
        FIXTURES["heap_canary"], ["heap_bad", "main"],
    )
    _write("heap-canary.analysis.json", heap_payload)
    _write("capacity-param.crosscheck.json", build_capacity_crosscheck())
    _write("engine-probe.json", build_engine_probe())
    _write("comparison.json", build_comparison(param_payload, global_payload,
                                               heap_payload))
    _write("envelope.json", build_envelope())
    build_sha256sums()
    print(f"wrote evidence to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
