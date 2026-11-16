"""P0-1 acceptance: read-only CFG + direct call graph (Phase-9 E-01 prototype).

These tests assert *structure and honesty properties* of the prototype
analysis layer -- stable JSON shape, no overlapping/duplicated blocks, direct
calls resolved, indirect calls explicitly unresolved, import/PLT edges
resolved against container metadata.  They deliberately claim no repair
capability: the prototype is analysis evidence only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.analysis import analyze_binary
from app.services.containers import detect_container

ROOT = Path(__file__).resolve().parents[1]
ELF_X86_64 = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
ELF_ARM64 = ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf"
ELF_I386_DYN = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86-dyn.elf"
ELF_X86_64_TINY = ROOT / "fixtures" / "hard-cases" / "vuln-heap-malloc-x86_64.elf"

TOP_LEVEL_KEYS = {"schema_version", "tool", "format", "arch", "bits", "entry",
                  "functions", "edges", "limitations", "statistics",
                  "callgraph_statistics"}
FUNCTION_KEYS = {"va", "name", "source", "size", "end_va", "instruction_count",
                 "block_count", "blocks"}
BLOCK_KEYS = {"va", "end_va", "terminator", "successors"}
INSTRUCTION_KEYS = {"va", "size", "bytes", "mnemonic", "op_str"}
EDGE_KEYS = {"from", "to", "kind", "resolved", "callee", "site_va"}
TERMINATORS = {"ret", "jmp", "jcc", "tail_jmp", "jmp_out", "fallthrough",
               "fallthrough_end", "decode_gap", "unresolved_jmp", "stop",
               "function_boundary", "budget_exhausted"}
EDGE_KINDS = {"direct", "plt", "import", "indirect", "tail_jmp", "tail_plt",
              "tail_indirect", "import_tail"}


def _load(path: Path) -> dict:
    if not path.is_file():  # pragma: no cover - fixtures are committed
        pytest.skip(f"fixture missing: {path}")
    return analyze_binary(path.read_bytes())


@pytest.fixture(scope="module")
def x86_64_payload() -> dict:
    return _load(ELF_X86_64)


@pytest.fixture(scope="module")
def arm64_payload() -> dict:
    return _load(ELF_ARM64)


@pytest.fixture(scope="module")
def i386_dyn_payload() -> dict:
    return _load(ELF_I386_DYN)


@pytest.fixture(scope="module")
def tiny_payload() -> dict:
    return _load(ELF_X86_64_TINY)


def _named(payload: dict) -> dict[str, dict]:
    return {fn["name"]: fn for fn in payload["functions"] if fn.get("name")}


def _edges_from(payload: dict, va: int) -> list[dict]:
    return [edge for edge in payload["edges"] if edge["from"] == va]


def _callee_contains(edges: list[dict], token: str) -> bool:
    return any(edge.get("callee") and token in edge["callee"] for edge in edges)


# ---------------------------------------------------------------------------
# JSON contract / structure
# ---------------------------------------------------------------------------


def test_fixed_json_shape(x86_64_payload):
    payload = x86_64_payload
    assert TOP_LEVEL_KEYS <= set(payload)
    assert payload["schema_version"] == 1
    assert payload["format"] == "elf"
    assert payload["arch"] == "x86_64"
    assert isinstance(payload["functions"], list) and payload["functions"]
    assert isinstance(payload["edges"], list)
    assert isinstance(payload["limitations"], list)

    for function in payload["functions"]:
        assert FUNCTION_KEYS <= set(function)
        assert isinstance(function["va"], int) and function["va"] > 0
        assert function["name"] is None or isinstance(function["name"], str)
        assert function["source"] in {"symtab", "symbol", "entry", "plt_stub",
                                      "call_target"}
        assert isinstance(function["blocks"], list)

        block_vas = [block["va"] for block in function["blocks"]]
        assert len(block_vas) == len(set(block_vas)), "duplicate block start"

        instruction_vas: set[int] = set()
        for block in function["blocks"]:
            assert BLOCK_KEYS <= set(block)
            assert block["terminator"] in TERMINATORS, block["terminator"]
            assert all(isinstance(va, int) for va in block["successors"])
            assert set(block["successors"]) <= set(block_vas), (
                "intra-function successor must be a block of the same function"
            )
            for instruction in block["instructions"]:
                assert INSTRUCTION_KEYS <= set(instruction)
                assert instruction["va"] not in instruction_vas, (
                    "instruction decoded twice inside one function"
                )
                instruction_vas.add(instruction["va"])

    for edge in payload["edges"]:
        assert EDGE_KEYS <= set(edge)
        assert edge["kind"] in EDGE_KINDS, edge["kind"]
        assert isinstance(edge["resolved"], bool)
        assert edge["to"] is None or isinstance(edge["to"], int)
        assert isinstance(edge["site_va"], int)
        if not edge["resolved"]:
            assert edge["to"] is None, "an unresolved edge must not carry a target"
            assert edge.get("reason"), "an unresolved edge must carry a reason"


def test_non_binary_input_fails_closed():
    payload = analyze_binary(b"this is not an executable image")
    assert payload["functions"] == []
    assert payload["edges"] == []
    assert payload["limitations"]
    assert payload["format"] == "unknown"


# ---------------------------------------------------------------------------
# real-fixture CFG behaviour
# ---------------------------------------------------------------------------


def test_required_fixture_functions_and_blocks(x86_64_payload):
    payload = x86_64_payload
    functions = _named(payload)
    assert {"main", "vuln_copy"} <= set(functions)
    assert payload["statistics"]["functions"] > 100  # static musl image

    vuln_copy = functions["vuln_copy"]
    assert vuln_copy["source"] == "symtab"
    assert vuln_copy["block_count"] >= 1
    assert vuln_copy["instruction_count"] >= 5
    assert vuln_copy["blocks"][0]["terminator"] == "ret"
    mnemonics = [ins["mnemonic"] for block in vuln_copy["blocks"]
                 for ins in block["instructions"]]
    assert "call" in mnemonics
    assert "ret" in mnemonics

    main = functions["main"]
    assert main["block_count"] > 1  # the argc/argv branch must be visible


def test_direct_call_edges_are_resolved(x86_64_payload):
    payload = x86_64_payload
    functions = _named(payload)
    vuln_copy = functions["vuln_copy"]
    edges = _edges_from(payload, vuln_copy["va"])
    assert len(edges) == 2, edges
    assert all(edge["kind"] == "direct" and edge["resolved"] for edge in edges)
    assert _callee_contains(edges, "strcpy")
    assert _callee_contains(edges, "puts")
    for edge in edges:
        assert vuln_copy["va"] <= edge["site_va"] < vuln_copy["end_va"]

    callers = [edge for edge in payload["edges"]
               if edge["from"] == functions["main"]["va"]
               and edge["to"] == vuln_copy["va"]]
    assert callers, "main -> vuln_copy direct call edge missing"
    assert all(edge["kind"] == "direct" and edge["resolved"] for edge in callers)


def test_indirect_calls_are_explicitly_unresolved(x86_64_payload):
    payload = x86_64_payload
    unresolved = [edge for edge in payload["edges"] if not edge["resolved"]]
    assert unresolved, "the static musl image has indirect calls; they must be reported"
    assert all(edge["to"] is None for edge in unresolved)
    assert all(edge.get("reason") for edge in unresolved)
    assert any("register-indirect call" in edge["reason"] for edge in unresolved)
    stats = payload["callgraph_statistics"]
    assert stats["edges_unresolved"] == len(unresolved)
    assert stats["edges_resolved"] + stats["edges_unresolved"] == stats["edges"]


# ---------------------------------------------------------------------------
# import / PLT resolution against container metadata
# ---------------------------------------------------------------------------


def test_import_edges_use_static_got_slots(tiny_payload):
    payload = tiny_payload
    assert payload["arch"] == "x86_64"
    imports = [edge for edge in payload["edges"] if edge["kind"] in {"import", "import_tail"}]
    assert imports, payload["limitations"][:5]
    assert all(edge["resolved"] and edge["to"] is None for edge in imports)
    assert any(edge.get("import_slot") for edge in imports)
    assert _callee_contains(imports, "malloc") or _callee_contains(imports, "strcpy")
    assert "plt_stub_edges_suppressed" in payload["callgraph_statistics"]


def test_dynamic_elf_plt_calls_resolve_import_names(i386_dyn_payload):
    payload = i386_dyn_payload
    assert payload["arch"] == "i386"
    functions = _named(payload)
    vuln_copy = functions["vuln_copy"]
    edges = _edges_from(payload, vuln_copy["va"])
    plt_edges = [edge for edge in edges if edge["kind"] == "plt"]
    assert len(plt_edges) == 2, edges
    assert all(edge["resolved"] and edge["to"] is not None for edge in plt_edges)
    assert _callee_contains(plt_edges, "strcpy")
    assert _callee_contains(plt_edges, "puts")
    # The i386 image also defines the imported names as size-0 STT_FUNC symbols
    # at the PLT stubs, so the stub may carry source="symtab"; the honest check
    # is against the container import table, not against the source label.
    container = detect_container(ELF_I386_DYN.read_bytes())
    assert {edge["to"] for edge in plt_edges} <= set(container.imports)
    assert any("executable import stub(s) are present" in text
               for text in payload["limitations"])


# ---------------------------------------------------------------------------
# call-target function augmentation (assembly labels without .type)
# ---------------------------------------------------------------------------


def test_arm64_call_target_function_is_justified(arm64_payload):
    payload = arm64_payload
    assert payload["arch"] == "arm64"
    functions = _named(payload)
    # The arm64 fixture declares `.globl vuln_copy` without `.type`, so it is
    # not STT_FUNC; it must be recovered from the direct call, never guessed.
    vuln_copy = functions["vuln_copy"]
    assert vuln_copy["source"] == "call_target"
    assert any("direct call target(s) fell outside" in text
               for text in payload["limitations"])
    edges = _edges_from(payload, vuln_copy["va"])
    assert len(edges) == 2
    assert all(edge["kind"] == "direct" and edge["resolved"] for edge in edges)
    assert _callee_contains(edges, "strcpy")
    assert _callee_contains(edges, "puts")
    callers = [edge for edge in payload["edges"]
               if edge["from"] == functions["main"]["va"]
               and edge["to"] == vuln_copy["va"]]
    assert callers and all(edge["resolved"] for edge in callers)


# ---------------------------------------------------------------------------
# serialization determinism / instruction toggle
# ---------------------------------------------------------------------------


def test_instructions_toggle_and_deterministic_output():
    data = ELF_X86_64_TINY.read_bytes()
    without = analyze_binary(data, include_instructions=False)
    assert all("instructions" not in block
               for function in without["functions"] for block in function["blocks"])
    with_instructions = analyze_binary(data, include_instructions=True)
    assert any(block.get("instructions")
               for function in with_instructions["functions"]
               for block in function["blocks"])

    # stripping the instruction bodies must reproduce the compact payload
    # exactly; a diff would mean non-deterministic analysis output.
    stripped = json.loads(json.dumps(with_instructions))
    for function in stripped["functions"]:
        for block in function["blocks"]:
            block.pop("instructions", None)
    # the two runs recompute `model`-free, metadata-only structures: equal
    assert json.dumps(stripped, sort_keys=True) == json.dumps(without, sort_keys=True)
    assert json.dumps(without, sort_keys=True) == json.dumps(
        analyze_binary(data, include_instructions=False), sort_keys=True)
