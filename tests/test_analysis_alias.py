"""P0-2 acceptance: conservative points-to / may-alias (Phase-9 E-03).

The contract under test is fail-closed: concrete alias claims only when the
prototype proves them, and every unknown/parameter/ambiguous case must return
may-alias or refuse a must-not-alias claim.  No repair capability is claimed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.analysis.alias import (
    UNKNOWN,
    analyze_points_to,
    global_location,
    locations_may_alias,
    must_alias,
    must_not_alias,
    points_to_at,
    sets_may_alias,
    stack_local,
)
from app.services.analysis.callgraph import build_call_graph
from app.services.analysis.cfg import build_cfg

ROOT = Path(__file__).resolve().parents[1]
PARAM = ROOT / "fixtures" / "crossfn" / "crossfn_param.elf"
GLOBAL = ROOT / "fixtures" / "crossfn" / "crossfn_global.elf"


@pytest.fixture(scope="module")
def param_fixture():
    if not PARAM.is_file():  # pragma: no cover
        pytest.skip(f"fixture missing: {PARAM}")
    data = PARAM.read_bytes()
    cfg = build_cfg(data)
    call_graph = build_call_graph(data, cfg)
    functions = {function.name: function for function in cfg.functions}
    globals_ = {0x1003910: ("s_ret", 16)}
    snapshots = {
        name: analyze_points_to(cfg, functions[name], globals_)
        for name in ("wrapper", "wrapper2", "copy_payload")
    }
    return functions, snapshots, globals_


@pytest.fixture(scope="module")
def global_fixture():
    if not GLOBAL.is_file():  # pragma: no cover
        pytest.skip(f"fixture missing: {GLOBAL}")
    data = GLOBAL.read_bytes()
    cfg = build_cfg(data)
    functions = {function.name: function for function in cfg.functions}
    store_out = functions["store_out"]
    snapshot = analyze_points_to(cfg, store_out, {0x1003820: ("g_out", 16)})
    call_site = next(
        ins.va for block in store_out.blocks for ins in block.instructions
        if ins.branch == "call" and ins.mnemonic == "call"
    )
    return store_out, snapshot, call_site


def _call_site_va(function, callee_name: str, cfg) -> int:
    callee = next(fn for fn in cfg.functions if fn.name == callee_name)
    for block in function.blocks:
        for ins in block.instructions:
            if ins.branch == "call" and ins.target == callee.va:
                return ins.va
    raise AssertionError(f"call site to {callee_name} not found")


def test_stack_alias_chain_is_concrete(param_fixture):
    functions, snapshots, _globals = param_fixture
    wrapper = functions["wrapper"]
    cfg = None  # cfg not needed: call target resolved through function VAs
    del cfg
    copy_payload = functions["copy_payload"]
    site = next(
        ins.va for block in wrapper.blocks for ins in block.instructions
        if ins.branch == "call" and ins.target == copy_payload.va
    )
    locations = points_to_at(snapshots["wrapper"], site, "rdi")
    assert locations == frozenset({stack_local(wrapper.va, -0x20)})
    assert must_alias(locations, locations)
    # a second, distinct frame slot must be provably disjoint
    assert must_not_alias(locations, {stack_local(wrapper.va, -0x28)})
    assert must_not_alias(locations, {stack_local(wrapper.va + 0x1000, -0x20)})
    assert not must_not_alias(locations, {UNKNOWN})


def test_parameter_fails_closed(param_fixture):
    functions, snapshots, _globals = param_fixture
    copy_payload = functions["copy_payload"]
    strcpy_va = next(
        ins.target for block in copy_payload.blocks for ins in block.instructions
        if ins.branch == "call"
    )
    site = next(
        ins.va for block in copy_payload.blocks for ins in block.instructions
        if ins.branch == "call" and ins.target == strcpy_va
    )
    locations = points_to_at(snapshots["copy_payload"], site, "rdi")
    assert {location.kind for location in locations} == {"parameter"}
    assert sets_may_alias(locations, {stack_local(functions["wrapper"].va, -0x20)})
    assert not must_not_alias(locations, {stack_local(functions["wrapper"].va, -0x20)})
    assert not must_alias(locations, {UNKNOWN})


def test_global_object_carries_exact_symbol_size(global_fixture):
    store_out, snapshot, site = global_fixture
    locations = points_to_at(snapshot, site, "rdi")
    sole = next(iter(locations))
    assert sole.kind == "global_object"
    assert sole.symbol == "g_out"
    assert sole.size == 16
    assert sole.address and sole.address > 0
    assert must_alias(locations, locations)
    assert must_not_alias(locations, {stack_local(store_out.va, -8)})
    assert must_not_alias(locations, {global_location(0xDEAD0000)})


def test_unknown_and_multiple_locations_refuse_certainty():
    first = stack_local(0x1000, -0x20)
    second = stack_local(0x1000, -0x40)
    heap_site_a = global_location(1)
    # manual lattice properties
    assert locations_may_alias(UNKNOWN, first)
    assert not must_not_alias({UNKNOWN}, {first})
    assert not must_alias({UNKNOWN}, {UNKNOWN})
    assert not locations_may_alias(first, second)
    assert must_not_alias({first}, {second})
    # a may-set joined from two paths is not a single concrete location
    joined = {first, second}
    assert sets_may_alias(joined, {first})
    assert not must_not_alias(joined, {second})
    assert must_not_alias({heap_site_a}, {first})
    # empty sets are unknown, not "aliases nothing"
    assert sets_may_alias(set(), {first})
    assert not must_not_alias(set(), {first})


def test_points_to_unknown_instruction_is_unknown():
    assert points_to_at({}, 0x1234, "rdi") == frozenset({UNKNOWN})
