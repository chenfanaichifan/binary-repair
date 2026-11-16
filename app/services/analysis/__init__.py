"""Read-only cross-function analysis prototypes (Phase-9 E-01/E-02/E-03).

This package is the M2 prototype layer described in M2任务.md.  It is
**analysis evidence only**:

* it is not imported by, and must not be wired into, repair_any,
  unified_verification or any gate;
* it never produces a patch, candidate or download;
* it never executes a target binary and never calls a model/provider;
* every limitation is surfaced in the output limitations list; unknowns are
  marked unresolved/unknown instead of being guessed.

Modules:

cfg
    Capstone basic-block CFG + function boundaries from authoritative
    metadata (E-01).
callgraph
    Direct call / PLT / import edges, indirect calls explicitly unresolved
    (E-01).
dataflow
    Conservative cross-function value-origin tracing (E-02).
alias
    Conservative may-alias / points-to summary (E-03).
"""
from __future__ import annotations

from typing import Any

from app.services.analysis.alias import (
    Location,
    UNKNOWN,
    analyze_points_to,
    locations_may_alias,
    must_alias,
    must_not_alias,
    points_to_at,
    sets_may_alias,
)
from app.services.analysis.callgraph import CallGraph, build_call_graph
from app.services.analysis.cfg import CfgResult, FunctionCfg, build_cfg
from app.services.analysis.dataflow import (
    analyze_crossfn,
    find_copy_sinks,
    object_symbols,
)
from app.services.containers import ContainerInfo, detect_container

__all__ = [
    "CallGraph",
    "CfgResult",
    "FunctionCfg",
    "Location",
    "UNKNOWN",
    "analyze_binary",
    "analyze_crossfn",
    "analyze_points_to",
    "build_call_graph",
    "build_cfg",
    "find_copy_sinks",
    "locations_may_alias",
    "must_alias",
    "must_not_alias",
    "object_symbols",
    "points_to_at",
    "sets_may_alias",
]

_SCHEMA_VERSION = 1


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def analyze_binary(
    data: bytes,
    *,
    container: ContainerInfo | None = None,
    include_instructions: bool = True,
) -> dict[str, Any]:
    """Return the stable combined CFG + call-graph JSON for one image.

    The returned mapping is the P0-1 contract::

        {format, arch, bits, entry, functions:[{va,name,blocks}],
         edges:[{from,to,kind,resolved}], limitations: [...]}
    """
    if container is None:
        container = detect_container(data)
    cfg = build_cfg(data, container=container)
    call_graph = build_call_graph(data, cfg, container=container)
    payload = cfg.to_dict(include_instructions=include_instructions)
    call_graph_json = call_graph.to_dict()
    payload["tool"] = "m2-analysis-cfg-callgraph"
    payload["edges"] = call_graph_json["edges"]
    payload["callgraph_statistics"] = call_graph_json["statistics"]
    payload["limitations"] = _dedupe(
        list(payload["limitations"]) + list(call_graph_json["limitations"])
    )
    return payload
