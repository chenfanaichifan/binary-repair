"""Contract-hash parity between the guest Route A worker and the host boundary.

The 2026-11-07 Route A bundle wrote ``canonical_json_hash(contract.json)`` while
the host trust boundary recomputes ``app.domain.contracts.contract_sha256``.
V0 failed on the real bundle because the two rules differ. These tests pin the
single rule the worker must use.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.domain.contracts import contract_sha256

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "workers/route_a/worker.py"
CWE416_NOINPUT = (
    ROOT
    / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json"
)
CWE121_ARGV = ROOT / "fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"


def _load_worker_module():
    spec = importlib.util.spec_from_file_location("route_a_guest_worker", WORKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_contract_hash_matches_the_product_rule() -> None:
    worker = _load_worker_module()
    raw = json.loads(CWE416_NOINPUT.read_text(encoding="utf-8"))
    assert worker.contract_hash_for(raw) == contract_sha256(raw)
    assert worker.contract_hash_for(raw) == (
        "c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c"
    )


def test_worker_contract_hash_really_differs_from_the_old_json_dumps_rule() -> None:
    worker = _load_worker_module()
    raw = json.loads(CWE416_NOINPUT.read_text(encoding="utf-8"))
    # The old rule is what the 2026-11-07 guest bundle recorded; it must not be
    # the value the worker writes any more.
    assert worker.canonical_json_hash(raw) == (
        "2dea9b4c0a84a92450c029e3e17acc5894268b75594d401910cb98a7a2d44719"
    )
    assert worker.contract_hash_for(raw) != worker.canonical_json_hash(raw)


def test_worker_contract_hash_matches_product_rule_for_the_argv_fixture() -> None:
    worker = _load_worker_module()
    raw = json.loads(CWE121_ARGV.read_text(encoding="utf-8"))
    assert worker.contract_hash_for(raw) == contract_sha256(raw)


def test_collector_contract_hash_matches_the_product_rule() -> None:
    collector_path = ROOT / "workers/route_a/result_bundle.py"
    spec = importlib.util.spec_from_file_location("route_a_result_bundle", collector_path)
    assert spec is not None and spec.loader is not None
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    raw = json.loads(CWE416_NOINPUT.read_text(encoding="utf-8"))
    assert collector.product_contract_hash(raw) == contract_sha256(raw)
    assert collector.product_contract_hash(raw) != collector.canonical_json_hash(raw)
