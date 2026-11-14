"""P0 target selector + patch-ownership gate + target-strict benchmark.

Contract T1: a repair may only be reported as repairing the *declared* target
function, and the gate must prove that every recorded action belongs to it.

Coverage:

* ``containers.resolve_function_scope``: exact symbol, unique substring,
  ambiguous, missing, explicit ``{"va", "end"}`` range (with derived end);
* target-scoped heap repair: candidate actions all inside the declared
  function, real/mocked PoC evidence gates with ``patch.target_scope=passed``;
* wrong target / missing target (``require_target``) / unresolved target fail
  closed with no candidate; target mode never falls back to the whole-image
  legacy immediate engine;
* the default (no target) whole-image path is unchanged and records
  ``target_scope=None`` / the whole-image policy note;
* capacity sites are filtered by the declared scope;
* the appended required ``patch.target_scope`` gate check passes/fails closed
  (action outside scope, missing ``site_va``, empty action list) and the scope
  is hashed into ``report_sha256``;
* the benchmark target-strict deterministic baseline and the
  ``baseline_expected_target_strict`` declarations in ``cases.json``;
* P1 legacy-gate convergence in the pipeline: a PoC-manifest request (with or
  without a target) never runs the whole-image legacy engine and never surfaces
  a schema_version=1 legacy packet.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import app.services.poc_runner as poc_runner
from app.services.binary_pipeline import repair_any
from app.services.containers import (
    ContainerInfo,
    SectionInfo,
    detect_container,
    resolve_function_scope,
)
from app.services.repair.analyzer import analyze
from app.services.repair.capacity import (
    detect_capacity_confusion,
    repair_capacity_confusion,
)
from app.services.repair.writer import repair_with_sinks
from app.services.unified_verification import build

ROOT = Path(__file__).resolve().parents[1]
HEAP = ROOT / "fixtures" / "hard-cases" / "vuln-heap-malloc-x86_64.elf"
HEAP_POC = ROOT / "fixtures" / "poc" / "heap-malloc.json"
CAPACITY = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"
CASES = ROOT / "fixtures" / "hard-cases" / "cases.json"

#: heap fixture: ``heap_bad`` owns the strcpy guard site; ``main`` does not.
HEAP_TARGET = "heap_bad"
HEAP_FUNCTION_VA = 0x401130
HEAP_FUNCTION_END = 0x40116C
HEAP_CALL_VA = 0x40114D
#: capacity fixture: the reviewed inlined-check rewrite block.
CAPACITY_SITE_VA = 0x4020D9


def _read(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def _load_json(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _guest_runner_available() -> bool:
    try:
        from app.services.guest_runner import find_guest_runner

        return find_guest_runner("x86_64") is not None
    except Exception:  # noqa: BLE001 - a missing runner is a skip, not a failure
        return False


class _FakePocEvidence:
    """Minimal passing PocEvidence stand-in (same shape as run_poc.to_dict)."""

    def __init__(self, status: str = "pass") -> None:
        self._payload = {
            "schema_version": 1,
            "status": status,
            "runner": "limactl",
            "tier": "emulated_run",
            "stdout_signature": "matched",
            "no_input": False,
            "original_sha256": "",
            "candidate_sha256": "",
            "poc": [
                self._case("poc", "original", 255, True, ""),
                self._case("poc", "candidate", 0, False, "AAAA\n"),
            ],
            "regression": [
                self._case("regression", "original", 0, False, "hi\n"),
                self._case("regression", "candidate", 0, False, "hi\n"),
            ],
            "limitations": [],
        }

    @staticmethod
    def _case(kind: str, executable: str, exit_code: int, crashed: bool,
              stdout: str) -> dict:
        return {
            "case_id": "case",
            "kind": kind,
            "executable": executable,
            "exit_code": exit_code,
            "crashed": crashed,
            "stdout": stdout,
            "stderr": "",
            "stdout_hex": stdout.encode().hex(),
            "timed_out": False,
            "error": None,
            "expected_ok": True,
        }

    def to_dict(self) -> dict:
        return json.loads(json.dumps(self._payload))


def _fake_passing_runner(monkeypatch) -> None:
    monkeypatch.setattr(
        poc_runner, "run_poc",
        lambda *args, **kwargs: _FakePocEvidence("pass"),
    )


# ---------------------------------------------------------------------------
# 1. Scope resolution
# ---------------------------------------------------------------------------


def test_scope_exact_symbol_name():
    container = detect_container(_read(HEAP))
    scope = resolve_function_scope(container, HEAP_TARGET)
    assert scope == {
        "name": HEAP_TARGET,
        "va": HEAP_FUNCTION_VA,
        "end": HEAP_FUNCTION_END,
        "source": "symbol",
    }
    assert scope["va"] <= HEAP_CALL_VA < scope["end"]


def test_scope_unique_substring_fallback():
    container = detect_container(_read(HEAP))
    scope = resolve_function_scope(container, "heap_ba")
    assert scope is not None
    assert scope["name"] == HEAP_TARGET
    assert scope["va"] == HEAP_FUNCTION_VA
    assert scope["source"] == "symbol"


def test_scope_ambiguous_and_missing_targets_fail_closed():
    container = detect_container(_read(HEAP))
    # "_" matches several symbols: ambiguous substring must not pick one.
    assert resolve_function_scope(container, "_") is None
    assert resolve_function_scope(container, "no_such_function_anywhere") is None
    assert resolve_function_scope(container, "") is None
    assert resolve_function_scope(container, None) is None

    synthetic = ContainerInfo(format="elf", arch="x86_64", bits=64)
    synthetic.sections = [SectionInfo(
        name=".text", segment="", va=0x1000, size=0x2000, offset=0,
        executable=True,
    )]
    synthetic.symbols = {0x1000: "foo_alpha", 0x2000: "foo_beta"}
    assert resolve_function_scope(synthetic, "foo") is None  # two candidates
    unique = resolve_function_scope(synthetic, "alpha")
    assert unique is not None
    assert (unique["va"], unique["end"]) == (0x1000, 0x2000)


def test_scope_explicit_range_and_derived_end():
    container = detect_container(_read(HEAP))
    explicit = resolve_function_scope(
        container, {"va": HEAP_FUNCTION_VA, "end": HEAP_FUNCTION_END}
    )
    assert explicit is not None
    assert explicit["source"] == "explicit"
    assert explicit["name"] == HEAP_TARGET
    assert (explicit["va"], explicit["end"]) == (HEAP_FUNCTION_VA, HEAP_FUNCTION_END)

    derived = resolve_function_scope(container, {"va": HEAP_FUNCTION_VA})
    assert derived is not None
    # end is derived from the next symbol in the executable region.
    assert derived["end"] == HEAP_FUNCTION_END

    assert resolve_function_scope(
        container, {"va": HEAP_FUNCTION_VA, "end": HEAP_FUNCTION_VA}
    ) is None
    assert resolve_function_scope(container, {"va": -1, "end": 0x10}) is None


# ---------------------------------------------------------------------------
# 2. Target-scoped heap repair (analyzer/writer path)
# ---------------------------------------------------------------------------


def test_writer_actions_carry_numeric_site_and_function_va():
    data = _read(HEAP)
    container = detect_container(data)
    sinks = [
        sink for sink in analyze(data).patchable()
        if int(sink.function_va or 0) == HEAP_FUNCTION_VA
    ]
    assert sinks
    result = repair_with_sinks(data, container, sinks)
    assert result.patched is not None
    assert result.actions
    for action in result.actions:
        # New numeric fields, old keys preserved.
        assert isinstance(action["site_va"], int)
        assert action["function_va"] == HEAP_FUNCTION_VA
        assert HEAP_FUNCTION_VA <= action["site_va"] < HEAP_FUNCTION_END
        assert isinstance(action["site"], str)
        assert action["kind"] in {"guard", "immediate"}
        assert "callee" in action


def test_heap_target_repair_is_scoped_and_gate_passes(monkeypatch):
    data = _read(HEAP)
    manifest = _load_json(HEAP_POC)
    _fake_passing_runner(monkeypatch)
    outcome = repair_any(
        data, target=HEAP_TARGET, require_target=True, poc_manifest=manifest,
    )
    report = outcome.report

    assert outcome.verified is True
    assert outcome.candidate is not None
    assert report.disposition == "verified_patch"

    scope = report.universal["target_scope"]
    assert scope["name"] == HEAP_TARGET
    assert (scope["va"], scope["end"]) == (HEAP_FUNCTION_VA, HEAP_FUNCTION_END)
    assert report.universal["target_policy"] == "target_scoped"
    assert report.actions
    assert all(
        HEAP_FUNCTION_VA <= action["site_va"] < HEAP_FUNCTION_END
        for action in report.actions
    )

    packet = report.verification["packet"]
    statuses = {check["id"]: check["status"] for check in packet["checks"]}
    assert statuses["patch.target_scope"] == "passed"
    # The gate scope carries the target identity (and hashes it).
    assert packet["scope"]["target"]["name"] == HEAP_TARGET
    assert packet["scope"]["target"]["va"] == HEAP_FUNCTION_VA


def test_wrong_target_repairs_nothing():
    outcome = repair_any(
        _read(HEAP), target="main", require_target=True,
    )
    report = outcome.report
    assert outcome.candidate is None
    assert outcome.verified is False
    assert report.disposition == "analysis_only"
    assert report.actions == []
    # The target does resolve, but the only patchable sink lives elsewhere.
    assert report.universal["target_scope"]["name"] == "main"
    assert HEAP_FUNCTION_VA not in range(
        report.universal["target_scope"]["va"],
        report.universal["target_scope"]["end"],
    )
    assert "no patchable sink" in (report.error or "")


def test_require_target_without_target_fails_closed():
    outcome = repair_any(_read(HEAP), require_target=True)
    report = outcome.report
    assert outcome.candidate is None
    assert report.disposition == "unsupported"
    assert report.universal["target_policy"] == "strict_no_target"
    assert "requires an explicit target" in (report.error or "")


def test_unresolved_target_fails_closed():
    outcome = repair_any(
        _read(HEAP), target="does_not_exist", require_target=True,
    )
    report = outcome.report
    assert outcome.candidate is None
    assert report.disposition == "unsupported"
    assert report.universal["target_scope"] is None
    assert "could not be resolved" in (report.error or "")


def test_target_mode_never_uses_the_legacy_whole_image_engine(monkeypatch):
    import app.services.binary_repair_engine as legacy_engine

    def _forbidden(*_args, **_kwargs):
        raise AssertionError(
            "legacy whole-image engine must not run when a target is declared"
        )

    monkeypatch.setattr(legacy_engine, "repair_elf", _forbidden)
    config = _load_json(CASES)
    case = next(
        item for item in config["cases"]
        if item["id"] == "inline-byte-loop"
    )
    data = _read(ROOT / case["binary"])
    outcome = repair_any(data, target=case["target"], require_target=True)
    report = outcome.report
    assert outcome.candidate is None
    # The whole-image baseline for this fixture produces a rejected candidate
    # from the legacy engine; the target-strict path must not reach it and the
    # measured result must match the declared target-strict expectation.
    assert report.disposition == case["baseline_expected_target_strict"]
    assert report.disposition == "analysis_only"
    assert report.strategy != "strict-template"
    assert report.universal["target_scope"]["name"] == case["target"]
    assert "no patchable sink" in (report.error or "")


def test_manifest_request_never_uses_the_legacy_engine(monkeypatch):
    """P1: a manifest-bearing legacy-only fixture is unified-gate-only.

    The legacy fixture would otherwise produce a schema_version=1 legacy
    "verified" packet through the stack/emulated builder; with a manifest the
    pipeline must never run that engine and must fail closed (no candidate, no
    legacy packet) instead.
    """
    import app.services.binary_repair_engine as legacy_engine

    def _forbidden(*_args, **_kwargs):
        raise AssertionError(
            "legacy engine must not run for a PoC-manifest request"
        )

    monkeypatch.setattr(legacy_engine, "repair_elf", _forbidden)
    vuln = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
    # Safe default would short-circuit before the manifest route; pass the
    # explicit whole-image opt-in so the P1 "manifest never uses the legacy
    # engine" rule itself is exercised.
    outcome = repair_any(
        _read(vuln), verify=True, poc_manifest={"schema_version": 1},
        allow_whole_image=True,
    )
    report = outcome.report
    assert outcome.candidate is None
    assert report.disposition == "analysis_only"
    assert report.status != "patched"
    assert "unified evidence-profile gate" in (report.error or "")
    verification = report.verification or {}
    packet = verification.get("packet")
    # Either no verification packet at all (fail closed) or a unified
    # evidence-profile packet -- never the schema_version=1 legacy packet.
    if packet is not None:
        assert packet.get("schema_version") != 1
        assert "profile.evidence" in {
            check.get("id") for check in packet.get("checks") or []
        }
    assert verification.get("gate", {}).get("success") is not True


def test_target_plus_manifest_is_deterministic_only_and_fails_closed():
    """Target + manifest: target-scoped deterministic paths only, no legacy."""
    outcome = repair_any(
        _read(HEAP), target="main", require_target=True,
        poc_manifest={"schema_version": 1},
    )
    report = outcome.report
    assert outcome.candidate is None
    assert report.disposition == "analysis_only"
    assert report.status != "patched"
    assert report.universal["target_scope"]["name"] == "main"
    assert "unified evidence-profile gate" in (report.error or "")
    packet = (report.verification or {}).get("packet")
    assert packet is None or packet.get("schema_version") != 1


def test_no_target_keeps_whole_image_policy():
    outcome = repair_any(_read(HEAP), verify=True, allow_whole_image=True)
    report = outcome.report
    # A whole-image candidate is still produced, but target identity is not
    # claimed anywhere in the report or the gate packet.
    assert report.actions
    assert report.universal["target_scope"] is None
    assert report.universal["target_policy"] == "whole_image"
    assert "target identity not claimed" in report.universal["target_note"]
    packet = (report.verification or {}).get("packet") or {}
    check_ids = {check["id"] for check in packet.get("checks") or []}
    assert "patch.target_scope" not in check_ids
    assert "target" not in (packet.get("scope") or {})


@pytest.mark.skipif(
    not _guest_runner_available(),
    reason="no native/qemu/Lima runner for x86_64 ELF on this host",
)
def test_heap_target_repair_with_real_poc_is_verified():
    """One real end-to-end acceptance run (Lima/qemu guest PoC + gate)."""
    data = _read(HEAP)
    manifest = _load_json(HEAP_POC)
    outcome = repair_any(
        data, target=HEAP_TARGET, require_target=True, poc_manifest=manifest,
    )
    report = outcome.report
    assert outcome.verified is True, report.verification.get("gate")
    assert report.disposition == "verified_patch"
    statuses = {
        check["id"]: check["status"]
        for check in report.verification["packet"]["checks"]
    }
    assert statuses["patch.target_scope"] == "passed"
    assert all(
        HEAP_FUNCTION_VA <= action["site_va"] < HEAP_FUNCTION_END
        for action in report.actions
    )


# ---------------------------------------------------------------------------
# 3. Capacity site filtering
# ---------------------------------------------------------------------------


def test_capacity_site_is_filtered_by_explicit_scope():
    data = _read(CAPACITY)
    in_scope = {"va": CAPACITY_SITE_VA, "end": CAPACITY_SITE_VA + 0x10}
    sites, _limitations = detect_capacity_confusion(data, in_scope)
    assert [site.site_va for site in sites] == [CAPACITY_SITE_VA]

    patched, report = repair_capacity_confusion(data, in_scope)
    assert patched is not None
    assert [action.site_va for action in report.actions] == [CAPACITY_SITE_VA]

    out_of_scope = {"va": CAPACITY_SITE_VA + 0x100, "end": CAPACITY_SITE_VA + 0x200}
    sites, limitations = detect_capacity_confusion(data, out_of_scope)
    assert sites == []
    assert any("outside target" in text for text in limitations)

    patched, report = repair_capacity_confusion(data, out_of_scope)
    assert patched is None
    assert any(
        "no reviewed capacity-check site inside target" in text
        for text in report.limitations
    )


def test_pipeline_capacity_target_repair_is_verified(monkeypatch):
    data = _read(CAPACITY)
    _fake_passing_runner(monkeypatch)
    target = {"va": CAPACITY_SITE_VA, "end": CAPACITY_SITE_VA + 0x10}
    outcome = repair_any(
        data, target=target, require_target=True, strategy="capacity",
        poc_manifest={"schema_version": 1},
    )
    report = outcome.report
    assert outcome.verified is True
    assert report.strategy == "capacity"
    assert report.actions
    assert all(
        CAPACITY_SITE_VA <= action["site_va"] < CAPACITY_SITE_VA + 0x10
        for action in report.actions
    )
    statuses = {
        check["id"]: check["status"]
        for check in report.verification["packet"]["checks"]
    }
    assert statuses["patch.target_scope"] == "passed"
    assert report.universal["target_scope"]["source"] == "explicit"


def test_pipeline_capacity_outside_target_is_analysis_only():
    data = _read(CAPACITY)
    target = {"va": CAPACITY_SITE_VA + 0x100, "end": CAPACITY_SITE_VA + 0x200}
    outcome = repair_any(
        data, target=target, require_target=True, strategy="capacity",
    )
    report = outcome.report
    assert outcome.candidate is None
    assert report.disposition == "analysis_only"
    assert report.universal["target_scope"]["va"] == CAPACITY_SITE_VA + 0x100


# ---------------------------------------------------------------------------
# 4. Gate check: patch.target_scope
# ---------------------------------------------------------------------------


def _capacity_gate(*, actions=None, target_scope=None, **overrides):
    data = _read(CAPACITY)
    patched, report = repair_capacity_confusion(data)
    assert patched is not None
    payload = report.to_dict()
    payload_actions = [dict(action) for action in payload["actions"]]
    kwargs = dict(
        format_name="elf",
        arch="x86_64",
        original=data,
        candidate=patched,
        actions=(
            [dict(action) for action in actions]
            if actions is not None else payload_actions
        ),
        runtime=None,
        reparse_ok=True,
        original_sha256=_sha(data),
        patched_sha256=_sha(patched),
        capacity=payload,
        target_scope=target_scope,
    )
    kwargs.update(overrides)
    return data, patched, payload, build(**kwargs)


def _check_status(verification, check_id: str) -> str | None:
    for check in verification.packet["checks"]:
        if check["id"] == check_id:
            return check["status"]
    return None


def test_gate_target_scope_passes_inside_and_rejects_outside():
    in_scope = {
        "name": "explicit", "va": CAPACITY_SITE_VA,
        "end": CAPACITY_SITE_VA + 0x10, "source": "explicit",
    }
    _data, _patched, payload, verification = _capacity_gate(target_scope=in_scope)
    assert _check_status(verification, "patch.target_scope") == "passed"
    assert verification.packet["scope"]["target"]["va"] == CAPACITY_SITE_VA

    outside_actions = [dict(action) for action in payload["actions"]]
    outside_actions[0]["site_va"] = CAPACITY_SITE_VA + 0x100
    _data, _patched, _payload, verification = _capacity_gate(
        actions=outside_actions, target_scope=in_scope,
    )
    check = next(
        item for item in verification.packet["checks"]
        if item["id"] == "patch.target_scope"
    )
    assert check["status"] == "failed"
    assert "outside the declared target" in check["detail"]
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"


def test_gate_target_scope_fails_closed_without_site_va_or_actions():
    in_scope = {
        "name": "explicit", "va": CAPACITY_SITE_VA,
        "end": CAPACITY_SITE_VA + 0x10, "source": "explicit",
    }
    _data, _patched, payload, _verification = _capacity_gate(target_scope=in_scope)

    missing_site = [dict(action) for action in payload["actions"]]
    missing_site[0].pop("site_va", None)
    _data, _patched, _payload, verification = _capacity_gate(
        actions=missing_site, target_scope=in_scope,
    )
    assert _check_status(verification, "patch.target_scope") == "failed"
    assert any(
        "no numeric site_va" in check["detail"]
        for check in verification.packet["checks"]
        if check["id"] == "patch.target_scope"
    )

    _data, _patched, _payload, verification = _capacity_gate(
        actions=[], target_scope=in_scope,
    )
    assert _check_status(verification, "patch.target_scope") == "failed"
    assert verification.gate.outcome == "rejected"


def test_gate_scope_is_hashed_into_report_sha256():
    in_scope = {
        "name": "explicit", "va": CAPACITY_SITE_VA,
        "end": CAPACITY_SITE_VA + 0x10, "source": "explicit",
    }
    _data, _patched, _payload, with_scope = _capacity_gate(target_scope=in_scope)
    _data, _patched, _payload, without_scope = _capacity_gate()
    assert (
        with_scope.packet["report_sha256"]
        != without_scope.packet["report_sha256"]
    )
    assert "patch.target_scope" not in {
        check["id"] for check in without_scope.packet["checks"]
    }


# ---------------------------------------------------------------------------
# 5. Benchmark target-strict mode
# ---------------------------------------------------------------------------


def test_benchmark_target_strict_result_for_target_without_sink():
    from scripts.run_hard_benchmark import _baseline_target_strict

    config = _load_json(CASES)
    case = next(
        item for item in config["cases"]
        if item["id"] == "cwe121-unchecked-strcpy"
    )
    data = _read(ROOT / case["binary"])
    result = _baseline_target_strict(data, case["target"])
    assert result["attempted"] is True
    assert result["disposition"] == "analysis_only"
    assert result["target_scope"]["name"] == case["target"]
    assert result["target_scope"]["va"] < result["target_scope"]["end"]
    assert result["actions"] == []
    assert result["target_in_scope"] is False
    assert result["verified"] is False


def test_benchmark_actions_in_target_scope_helper():
    from scripts.run_hard_benchmark import _actions_in_target_scope

    scope = {"va": 0x1000, "end": 0x1100}
    assert _actions_in_target_scope([{"site_va": 0x1000}], scope)
    assert _actions_in_target_scope([{"site_va": 0x10FF}], scope)
    assert not _actions_in_target_scope([{"site_va": 0x1100}], scope)
    assert not _actions_in_target_scope([{"site_va": 0x0FFF}], scope)
    assert not _actions_in_target_scope([], scope)
    assert not _actions_in_target_scope([{"site_va": True}], scope)


def test_cases_json_declares_target_strict_expectations():
    config = _load_json(CASES)
    declared = [
        case for case in config["cases"]
        if case.get("baseline_expected_target_strict") is not None
    ]
    assert declared, "at least one case must declare a target-strict baseline"
    for case in declared:
        assert case["baseline_expected_target_strict"] in {
            "analysis_only", "rejected", "unsupported",
        }
        # The new field records a target-strict result that differs from the
        # historical whole-image baseline; baseline_expected itself is frozen.
        assert (
            case["baseline_expected_target_strict"] != case["baseline_expected"]
        )
