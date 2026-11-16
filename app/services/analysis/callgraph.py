"""Read-only direct call-graph recovery (Phase-9 E-01 prototype).

Reads the CFG produced by :mod:`app.services.analysis.cfg` and emits typed
call/tail-jump edges.  This module never executes bytes, never writes a patch
and is not wired into ``repair_any`` or any gate.

Resolution policy (fail-closed; indirect calls are explicit unknowns):

* **direct call** (x86 ``E8 rel32`` / AArch64 ``bl`` immediate): the target
  address is computed from the instruction itself and is therefore
  ``resolved=true``; ``callee`` is the symbol name when the target is a known
  function start and ``null`` otherwise;
* **PLT / import stub call**: a direct call whose target is an executable
  import stub recorded by the container layer becomes ``kind="plt"`` with the
  imported name;
* **import call through a GOT/IAT slot** (``call [rip+disp]`` /
  ``call [abs]``): the slot address is static, the pointee is an import, so
  the edge is ``kind="import"``, ``to=null``, ``import_slot=<va>``,
  ``resolved=true`` (the imported *name* is resolved, the runtime address is
  not claimed);
* **register/unknown-memory indirect call**: ``kind="indirect"``,
  ``resolved=false``, with an explicit ``reason`` -- never guessed;
* **tail jumps**: a block terminator that leaves the function by a direct
  ``jmp`` to a known function start / import stub is ``kind="tail_jmp"`` /
  ``"tail_plt"``; indirect tail jumps are ``kind="tail_indirect"``,
  unresolved.  Jump-table dispatch sites are reported, not expanded.

Edges from PLT-stub pseudo-functions are suppressed (their bodies are
trampolines; the interesting edge is caller -> import).  The suppressed count
is reported in ``statistics["plt_stub_edges_suppressed"]``.

JSON edge shape (stable)::

    {"from": <function va>, "to": <target va|null>, "kind": "direct",
     "resolved": true, "callee": "vuln_copy", "site_va": <call va>}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.analysis.cfg import CfgResult, FunctionCfg, Instruction
from app.services.containers import ContainerInfo, detect_container

_SCHEMA_VERSION = 1

_CALL_KINDS = {"call", "indirect_call"}
_TAIL_TERMINATORS = {"tail_jmp", "unresolved_jmp", "jmp_out"}


@dataclass
class CallEdge:
    from_va: int
    to_va: int | None
    kind: str
    resolved: bool
    callee: str | None = None
    site_va: int = 0
    reason: str = ""
    import_slot: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "from": self.from_va,
            "to": self.to_va,
            "kind": self.kind,
            "resolved": self.resolved,
            "callee": self.callee,
            "site_va": self.site_va,
        }
        if self.reason:
            payload["reason"] = self.reason
        if self.import_slot is not None:
            payload["import_slot"] = self.import_slot
        return payload


@dataclass
class CallGraph:
    edges: list[CallEdge] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "tool": "m2-analysis-callgraph",
            "edges": [edge.to_dict() for edge in self.edges],
            "limitations": list(self.limitations),
            "statistics": dict(self.statistics),
        }


def _is_executable_target(container: ContainerInfo, va: int) -> bool:
    section = container.section_at(va)
    return bool(section is not None and section.executable)


def _function_name(container: ContainerInfo, function_by_va: dict[int, FunctionCfg], va: int) -> str | None:
    function = function_by_va.get(va)
    if function is not None and function.name:
        return function.name
    return container.symbols.get(va)


def _resolve_direct_target(
    container: ContainerInfo,
    function_by_va: dict[int, FunctionCfg],
    target: int,
) -> tuple[str, str | None, str, int | None]:
    """Classify a statically computed direct call target.

    Returns ``(kind, callee, reason, import_slot)``.
    """
    if target in container.imports and _is_executable_target(container, target):
        return "plt", container.imports[target], "", None
    function = function_by_va.get(target)
    if function is not None:
        if function.source == "plt_stub":
            return "plt", container.imports.get(target, function.name), "", None
        return "direct", function.name or container.symbols.get(target), "", None
    if not _is_executable_target(container, target):
        return ("direct", None,
                f"direct call target 0x{target:x} is outside executable sections "
                "(statically computed; not a call-graph node)", None)
    return ("direct", container.symbols.get(target),
            f"direct call target 0x{target:x} is inside an executable section but "
            "not a known function start (address is static; identity unknown)", None)


def build_call_graph(
    data: bytes,
    cfg: CfgResult,
    *,
    container: ContainerInfo | None = None,
) -> CallGraph:
    """Build typed call/tail-jump edges from an already-built CFG (read-only)."""
    if container is None:
        container = detect_container(data)
    graph = CallGraph()
    function_by_va = {function.va: function for function in cfg.functions}
    edges: list[CallEdge] = []
    suppressed_stub_edges = 0

    def emit(edge: CallEdge) -> None:
        edges.append(edge)

    for function in cfg.functions:
        if function.source == "plt_stub":
            # PLT trampolines are recorded as functions so that caller->stub
            # edges resolve; their own indirect body edges are not useful noise.
            suppressed_stub_edges += sum(
                1 for block in function.blocks for ins in block.instructions
                if ins.branch in _CALL_KINDS
                or (ins.branch in {"jmp", "indirect_jmp"}
                    and block.terminator in _TAIL_TERMINATORS)
            )
            continue
        for block in function.blocks:
            for ins in block.instructions:
                if ins.branch not in _CALL_KINDS:
                    continue
                if ins.branch == "call" and not ins.indirect and ins.target is not None:
                    kind, callee, reason, slot = _resolve_direct_target(
                        container, function_by_va, ins.target,
                    )
                    emit(CallEdge(
                        from_va=function.va, to_va=ins.target, kind=kind,
                        resolved=True, callee=callee, site_va=ins.va,
                        reason=reason, import_slot=slot,
                    ))
                elif ins.mem_slot is not None:
                    slot = ins.mem_slot
                    imported = container.imports.get(slot)
                    if imported is not None:
                        emit(CallEdge(
                            from_va=function.va, to_va=None, kind="import",
                            resolved=True, callee=imported, site_va=ins.va,
                            import_slot=slot,
                        ))
                    else:
                        emit(CallEdge(
                            from_va=function.va, to_va=None, kind="indirect",
                            resolved=False, site_va=ins.va,
                            reason=(
                                f"memory-indirect call through non-import slot "
                                f"0x{slot:x}: pointee is not statically known"
                            ),
                        ))
                else:
                    emit(CallEdge(
                        from_va=function.va, to_va=None, kind="indirect",
                        resolved=False, site_va=ins.va,
                        reason=(ins.reason or "register-indirect call: target depends "
                                "on runtime register state"),
                    ))

            # tail jumps: only the block-terminating instruction leaves the fn
            if block.terminator not in _TAIL_TERMINATORS or not block.instructions:
                continue
            last = block.instructions[-1]
            if last.branch in {"jmp"} and not last.indirect and last.target is not None:
                target = last.target
                kind, callee, reason, slot = _resolve_direct_target(
                    container, function_by_va, target,
                )
                if kind == "plt":
                    emit(CallEdge(from_va=function.va, to_va=target, kind="tail_plt",
                                  resolved=True, callee=callee, site_va=last.va,
                                  reason=reason))
                elif kind == "direct" and target in function_by_va:
                    emit(CallEdge(from_va=function.va, to_va=target, kind="tail_jmp",
                                  resolved=True, callee=callee, site_va=last.va,
                                  reason=reason))
                else:
                    emit(CallEdge(from_va=function.va, to_va=target, kind="tail_jmp",
                                  resolved=True, callee=callee, site_va=last.va,
                                  reason=reason or "tail jump to a non-symbol target"))
            elif last.branch == "jmp" and last.mem_slot is not None:
                slot = last.mem_slot
                imported = container.imports.get(slot)
                if imported is not None:
                    emit(CallEdge(from_va=function.va, to_va=None, kind="import_tail",
                                  resolved=True, callee=imported, site_va=last.va,
                                  import_slot=slot))
                else:
                    emit(CallEdge(from_va=function.va, to_va=None, kind="tail_indirect",
                                  resolved=False, site_va=last.va,
                                  reason=(f"memory-indirect tail jump through non-import "
                                          f"slot 0x{slot:x}")))
            else:
                emit(CallEdge(from_va=function.va, to_va=None, kind="tail_indirect",
                              resolved=False, site_va=last.va,
                              reason=(last.reason or "indirect tail jump: target depends "
                                      "on runtime state")))

    edges.sort(key=lambda edge: (edge.site_va, edge.from_va, edge.kind))
    graph.edges = edges

    by_kind: dict[str, int] = {}
    for edge in edges:
        by_kind[edge.kind] = by_kind.get(edge.kind, 0) + 1
    unresolved = [edge for edge in edges if not edge.resolved]
    unresolved_sites = sum(
        1 for function in cfg.functions if function.source != "plt_stub"
        for block in function.blocks for ins in block.instructions
        if ins.branch in _CALL_KINDS and not (
            ins.branch == "call" and not ins.indirect and ins.target is not None
        ) and ins.mem_slot is None
    )
    unlabeled_direct = sum(
        1 for edge in edges
        if edge.kind == "direct" and edge.callee is None and edge.resolved
    )
    if unlabeled_direct:
        graph.limitations.append(
            f"{unlabeled_direct} direct call edge(s) target an address that is not a "
            "known function start; the address is static but the callee identity is "
            "not claimed"
        )
    if unresolved:
        graph.limitations.append(
            f"{len(unresolved)} call/tail-jump site(s) are indirect and unresolved "
            "(register or non-import memory target); no target is guessed"
        )
    tail_count = sum(1 for edge in edges if edge.kind.startswith("tail_")
                     or edge.kind == "import_tail")
    if tail_count:
        graph.limitations.append(
            f"{tail_count} tail-jump edge(s) are reported; a tail jump is not proven "
            "to be a call in the source program"
        )
    if suppressed_stub_edges:
        graph.limitations.append(
            f"{suppressed_stub_edges} edge(s) from executable import stubs are "
            "suppressed (trampoline bodies, not user code)"
        )
    graph.statistics = {
        "edges": len(edges),
        "edges_resolved": sum(1 for edge in edges if edge.resolved),
        "edges_unresolved": len(unresolved),
        "edges_by_kind": dict(sorted(by_kind.items())),
        "unresolved_call_sites": unresolved_sites,
        "plt_stub_edges_suppressed": suppressed_stub_edges,
        "functions_with_outgoing_edges": len({edge.from_va for edge in edges}),
    }
    return graph
