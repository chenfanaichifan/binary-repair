"""P0-2 acceptance: cross-function dataflow / sink capacity origins (E-02).

These tests pin the evidence contract: for a known copy sink the prototype must
say where the destination capacity comes from (or say unknown with a reason),
including across one level of call edges and return values.  They claim no
repair capability.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.analysis.dataflow import (
    _argument_register,
    _summarize_paths,
    analyze_crossfn,
    copy_token,
)
from app.services.containers import ContainerInfo

ROOT = Path(__file__).resolve().parents[1]
PARAM = ROOT / "fixtures" / "crossfn" / "crossfn_param.elf"
GLOBAL = ROOT / "fixtures" / "crossfn" / "crossfn_global.elf"
HEAP_CANARY = ROOT / "fixtures" / "hard-cases" / "vuln-heap-canary-x86_64.elf"


@pytest.fixture(scope="module")
def param_payload() -> dict:
    if not PARAM.is_file():  # pragma: no cover
        pytest.skip(f"fixture missing: {PARAM}")
    return analyze_crossfn(PARAM.read_bytes())


@pytest.fixture(scope="module")
def global_payload() -> dict:
    if not GLOBAL.is_file():  # pragma: no cover
        pytest.skip(f"fixture missing: {GLOBAL}")
    return analyze_crossfn(GLOBAL.read_bytes())


@pytest.fixture(scope="module")
def heap_payload() -> dict:
    if not HEAP_CANARY.is_file():  # pragma: no cover
        pytest.skip(f"fixture missing: {HEAP_CANARY}")
    return analyze_crossfn(HEAP_CANARY.read_bytes())


def _sink_in(payload: dict, function_name: str, token: str | None = None) -> dict:
    for sink in payload["sinks"]:
        if sink["function"]["name"] != function_name:
            continue
        if token is None or sink["copy_token"] == token:
            return sink
    raise AssertionError(f"no {token or ''} sink in {function_name}: "
                         f"{[s['function']['name'] for s in payload['sinks']]}")


def test_sink_json_shape(param_payload):
    payload = param_payload
    assert {"schema_version", "tool", "format", "arch", "bits", "entry",
            "sinks", "limitations", "statistics"} <= set(payload)
    assert payload["format"] == "elf" and payload["arch"] == "x86_64"
    for sink in payload["sinks"]:
        assert {"site_va", "callee", "copy_token", "function", "destination",
                "source_argument", "alias", "confidence", "limitations"} <= set(sink)
        destination = sink["destination"]
        assert {"origin", "capacity", "capacity_source", "agreement",
                "resolution", "paths"} <= set(destination)
        assert destination["resolution"] in {
            "resolved", "partially_resolved", "unknown", "unsupported_arch",
        }
        for path in destination["paths"]:
            assert {"caller", "origin", "capacity", "capacity_source",
                    "resolution", "steps", "alias"} <= set(path)
            assert isinstance(path["steps"], list)


def test_param_fixture_has_two_call_site_paths(param_payload):
    sink = _sink_in(param_payload, "copy_payload", "strcpy")
    destination = sink["destination"]
    assert destination["origin"] == "parameter"
    # the two callers have different capacities -> conflict, never averaged
    assert destination["agreement"] == "conflict"
    assert destination["capacity"] is None
    assert destination["resolution"] == "partially_resolved"
    assert sink["confidence"] in {"low", "medium", "high"}
    callers = {path["caller"]["name"]: path for path in destination["paths"]}
    assert set(callers) == {"wrapper", "wrapper2"}
    assert callers["wrapper"]["origin"] == "stack_local"
    assert callers["wrapper"]["capacity"] == 32  # frame geometry upper bound
    assert callers["wrapper"]["capacity_source"] == "frame_geometry_upper_bound"
    assert any("UPPER BOUND" in text
               for text in callers["wrapper"]["limitations"])
    step_kinds = {step["kind"] for step in callers["wrapper"]["steps"]}
    assert "stack_frame_local" in step_kinds
    assert "call_site" in step_kinds


def test_param_fixture_return_value_path_recovers_exact_capacity(param_payload):
    sink = _sink_in(param_payload, "copy_payload", "strcpy")
    wrapper2_path = next(path for path in sink["destination"]["paths"]
                         if path["caller"]["name"] == "wrapper2")
    # ret_buffer() returns the static s_ret[16]; its STT_OBJECT st_size gives
    # the exact capacity across the return-value edge.
    assert wrapper2_path["origin"] == "global_object"
    assert wrapper2_path["capacity"] == 16
    assert wrapper2_path["capacity_source"] == "object_symbol_size"
    assert wrapper2_path["resolution"] == "resolved"
    step_kinds = {step["kind"] for step in wrapper2_path["steps"]}
    assert "return_value" in step_kinds
    assert "call_site" in step_kinds
    assert "global_address" in step_kinds
    # inside the callee the destination is opaque (parameter), fail-closed
    assert sink["alias"]["destination_may_alias_anything"] is True


def test_global_destination_capacity_is_exact(global_payload):
    sink = _sink_in(global_payload, "store_out", "strcpy")
    destination = sink["destination"]
    assert destination["origin"] == "global_object"
    assert destination["capacity"] == 16
    assert destination["capacity_source"] == "object_symbol_size"
    assert destination["agreement"] == "all_paths"
    assert destination["resolution"] == "resolved"
    assert sink["confidence"] == "high"
    locations = sink["alias"]["destination_locations"]
    assert any(location.get("kind") == "global_object"
               and location.get("symbol") == "g_out"
               and location.get("size") == 16 for location in locations)
    assert sink["alias"]["destination_may_alias_anything"] is False


def test_existing_hard_case_heap_capacity_and_overestimate(heap_payload):
    """Cross-check against LIMITATIONS section 21: malloc(24) for char data[16]."""
    sink = _sink_in(heap_payload, "heap_bad", "strcpy")
    destination = sink["destination"]
    assert destination["origin"] == "heap_allocation"
    assert destination["capacity"] == 24
    assert destination["capacity_source"] == "allocation_immediate_size"
    assert destination["resolution"] == "resolved"
    limitations = " ".join(sink["limitations"])
    assert "OVER-ESTIMATE" in limitations or "over-estimate" in limitations
    # a memcpy sink must also expose the length-argument analysis slot
    memcpy_sinks = [item for item in heap_payload["sinks"]
                    if item["copy_token"] in {"memcpy", "memmove"}]
    assert memcpy_sinks
    first = memcpy_sinks[0]
    assert "length_argument" in first
    assert {"origin", "resolution"} <= set(first["length_argument"])


def test_non_binary_input_fails_closed():
    payload = analyze_crossfn(b"not an executable image at all")
    assert payload["sinks"] == []
    assert payload["limitations"]
    assert payload["format"] == "unknown"


def test_unsupported_arch_is_explicit():
    assert _argument_register(ContainerInfo(format="elf", arch="arm64")) is None
    assert _argument_register(ContainerInfo(format="elf", arch="x86_64")) == "rdi"
    assert _argument_register(ContainerInfo(format="pe", arch="x86_64")) == "rcx"


def test_path_summary_never_averages_conflicts():
    capacity, source, agreement, resolution = _summarize_paths(
        None,
        [{"capacity": 16, "capacity_source": "object_symbol_size",
          "origin": "global_object"},
         {"capacity": 32, "capacity_source": "frame_geometry_upper_bound",
          "origin": "stack_local"}],
    )
    assert capacity is None and source is None
    assert agreement == "conflict"
    assert resolution == "partially_resolved"
    capacity, source, agreement, resolution = _summarize_paths(
        None,
        [{"capacity": 16, "capacity_source": "object_symbol_size",
          "origin": "global_object"},
         {"capacity": 16, "capacity_source": "object_symbol_size",
          "origin": "global_object"}],
    )
    assert capacity == 16 and source == "object_symbol_size"
    assert agreement == "all_paths" and resolution == "resolved"


@pytest.mark.parametrize("name,expected", [
    ("strcpy", "strcpy"),
    ("__strcpy_chk", "__strcpy_chk"),
    ("c.string.strcpy", "strcpy"),
    ("strcpy@GLIBC_2.2.5", "strcpy"),
    ("malloc", None),
    ("memmove", "memmove"),
])
def test_copy_token_canonicalization(name, expected):
    assert copy_token(name) == expected
